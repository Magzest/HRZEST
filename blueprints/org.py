"""Org blueprint — multi-tenant org self-registration."""
import re
from flask import Blueprint, request, redirect, render_template, flash, jsonify, session
from extensions import app_log
from utils.auth import generate_password_hash, turnstile_enabled, verify_turnstile, _TURNSTILE_SITE_KEY
from utils.plan_limits import PLAN_TIERS
from utils.email_utils import get_email_config, send_email_async

org_bp = Blueprint("org", __name__)

_SUBDOMAIN_RE = re.compile(r'^[a-z0-9\-]+$')
_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

# Matches the hardcoded ".hrms.gradzest.com" suffix already shown in
# templates/create_org.html and templates/get_started.html -- kept as one
# constant here since the portal link is also built server-side (welcome
# email + the org_created.html success page).
_TENANT_DOMAIN_SUFFIX = "hrms.gradzest.com"

# Subdomains that must never be self-registered: _resolve_tenant() (app.py)
# treats any 3-label host as <label1>.<rest>, so the bare production domain
# itself (e.g. hrms.gradzest.com) parses as subdomain candidate "hrms" --
# letting someone register that subdomain would silently hijack every
# visitor to the operator's own bare domain from that point on. The rest
# are conventional infrastructure/admin names worth blocking on principle.
_RESERVED_SUBDOMAINS = frozenset({
    "hrms", "www", "api", "admin", "app", "mail", "master", "super_admin",
    "static", "ns1", "ns2", "assets", "cdn",
})


def _clean_subdomain_slug(raw, company_name=""):
    if not raw and company_name:
        raw = company_name
    s = str(raw).strip().lower()
    s = re.sub(r'^https?://', '', s)
    s = s.split('/')[0].split(':')[0]
    for suffix in [".hrms.gradzest.com", ".gradzest.com", ".gradzest.in", ".com", ".in", ".org", ".net", ".io"]:
        if s.endswith(suffix):
            s = s[:-len(suffix)]
    s = re.sub(r'[^a-z0-9\-]', '', s)
    return s

def _validate_new_tenant_fields(company_name, subdomain, admin_username, admin_password, admin_email, plan):
    """Shared field validation for all three tenant-creation entry points
    (/create_org, /api/create_org, and the platform-admin-initiated create
    flow in platform_admin.py) -- keeps the reserved-subdomain and
    email-format checks from drifting out of sync across call sites.
    Returns an error message, or None if every field is valid."""
    subdomain = _clean_subdomain_slug(subdomain, company_name)
    if not all([company_name, subdomain, admin_username, admin_password, admin_email]):
        return "All fields (company name, subdomain, admin email/username/password) are required."
    if not _EMAIL_RE.match(admin_email):
        return "Enter a valid admin email address."
    if not _SUBDOMAIN_RE.match(subdomain):
        return "Subdomain may only contain lowercase letters, digits, and hyphens."
    if subdomain in _RESERVED_SUBDOMAINS:
        return f"Subdomain '{subdomain}' is reserved. Choose another."
    if len(admin_password) < 8:
        return "Admin password must be at least 8 characters."
    if plan not in PLAN_TIERS:
        return "Choose a valid plan."
    return None


def provision_tenant(company_name, subdomain, admin_username, admin_password, admin_email, plan):
    """Shared tenant-provisioning core: schema creation, admin-user seed,
    and master-registry insert. Callers must run
    _validate_new_tenant_fields() first -- this only does the actual
    provisioning, which is where the three call sites would otherwise
    duplicate ~80 near-identical lines.

    Returns (ok, error_message_or_None, portal_url_or_None).
    """
    db_name = "att_" + subdomain.replace("-", "_")

    # See the long comment this replaced in the original /create_org route:
    # checking only the tenants registry misses (1) a subdomain deriving a
    # db_name that collides with an existing schema (e.g. "master"), and
    # (2) a schema orphaned by a previously failed provisioning attempt.
    try:
        from database import get_master_db
        mconn = get_master_db()
        mcur = mconn.cursor(buffered=True)
        mcur.execute("SELECT id FROM tenants WHERE subdomain=%s", (subdomain,))
        taken = mcur.fetchone() is not None
        if not taken:
            mcur.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name=%s", (db_name,))
            taken = mcur.fetchone() is not None
        mcur.close()
        mconn.close()
        if taken:
            return False, f"Subdomain '{subdomain}' is already taken. Choose another.", None
    except Exception as exc:
        app_log.error("provision_tenant subdomain check failed: %s", exc)
        return False, "Could not check subdomain availability. Please try again.", None

    try:
        from database import create_tenant_schema
        create_tenant_schema(db_name)
    except Exception as exc:
        app_log.error("provision_tenant schema creation failed: %s", exc)
        return False, "Failed to create organisation. Please contact support.", None

    try:
        from flask import g as _g
        _g.tenant_db = db_name
        from app import init_tenant_db
        init_tenant_db(db_name)
    except Exception as exc:
        app_log.error("provision_tenant schema init failed: %s", exc)
        return False, "Failed to initialise organisation schema. Please contact support.", None

    try:
        from database import get_tenant_db
        tconn = get_tenant_db(db_name)
        tcur = tconn.cursor()
        tcur.execute(
            "UPDATE company_settings SET company_name=%s, setup_done=1 WHERE id=1",
            (company_name,)
        )
        # Plain INSERT, no ON CONFLICT: the schema-existence check above
        # guarantees this is a brand-new schema, so a conflict here means a
        # genuine race rather than legitimate reuse.
        tcur.execute(
            "INSERT INTO admin_users (username, password, email) VALUES (%s, %s, %s)",
            (admin_username, generate_password_hash(admin_password), admin_email)
        )
        tconn.commit()
        tcur.close()
        tconn.close()
    except Exception as exc:
        return False, f"Failed to seed tenant data: {exc}", None

    try:
        from database import get_master_db
        mconn = get_master_db()
        mcur = mconn.cursor()
        mcur.execute(
            "INSERT INTO tenants (company_name, subdomain, db_name, admin_email, plan, status) "
            "VALUES (%s, %s, %s, %s, %s, 'active')",
            (company_name, subdomain, db_name, admin_email, plan)
        )
        mconn.commit()
        mcur.close()
        mconn.close()
    except Exception as exc:
        return False, f"Tenant registered in DB but master registry failed: {exc}", None

    portal_url = f"https://{subdomain}.{_TENANT_DOMAIN_SUFFIX}/admin_login"
    return True, None, portal_url


def send_portal_ready_email(admin_email, company_name, admin_username, portal_url, admin_password=""):
    """Welcome email with the tenant's dedicated portal link and login credentials."""
    try:
        email_cfg = get_email_config()
        if not email_cfg:
            return False
        
        creds_block = ""
        if admin_password:
            creds_block = f"""
            <div style="background:#f1f5f9;border-left:4px solid #3b82f6;padding:14px;border-radius:6px;margin:18px 0;font-size:14px;color:#334155;">
              <div style="font-weight:700;margin-bottom:6px;color:#1e293b;">🔑 Login Credentials</div>
              <div><strong>Username:</strong> {admin_username}</div>
              <div><strong>Password:</strong> {admin_password}</div>
            </div>
            """
        else:
            creds_block = f"""
            <div style="background:#f1f5f9;border-left:4px solid #3b82f6;padding:14px;border-radius:6px;margin:18px 0;font-size:14px;color:#334155;">
              <div><strong>Admin Username:</strong> {admin_username}</div>
            </div>
            """

        html_body = f"""
<div style="font-family:Segoe UI,sans-serif;max-width:540px;margin:auto;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #e2e8f0;box-shadow:0 10px 30px rgba(0,0,0,0.08);">
  <div style="background:linear-gradient(135deg,#0f172a 0%,#1e3a8a 100%);padding:28px;color:white;text-align:center;">
    <div style="font-size:24px;font-weight:800;">🏢 {company_name}</div>
    <div style="font-size:14px;opacity:0.85;margin-top:6px;">Your Dedicated HRMS Portal is Ready</div>
  </div>
  <div style="padding:28px;">
    <p style="font-size:15px;color:#334155;margin-bottom:16px;line-height:1.6;">
      Welcome to your Attendance & HRMS Platform! Your company workspace has been fully configured and set up by our onboarding team.
    </p>

    {creds_block}

    <a href="{portal_url}" style="display:block;text-align:center;padding:16px 28px;background:linear-gradient(135deg,#0284c7,#2563eb);color:white;border-radius:12px;text-decoration:none;font-size:16px;font-weight:700;margin:24px 0;box-shadow:0 6px 20px rgba(37,99,235,0.35);">
      🚀 Launch Your Branded Dashboard
    </a>

    <p style="font-size:12px;color:#94a3b8;text-align:center;">Or copy this link to your browser: <br><a href="{portal_url}" style="color:#2563eb;">{portal_url}</a></p>
  </div>
</div>"""
        send_email_async(admin_email, f"Your HRMS Portal is Ready — {company_name}", html_body, email_cfg)
        return True
    except Exception as exc:
        app_log.error("send_portal_ready_email failed: %s", exc)
        return False


def send_payment_confirmation_email(admin_email, company_name, portal_url, set_password_url,
                                     plan_display_name, amount_paise, razorpay_payment_id):
    """Post-payment welcome email for the paid /create_org flow
    (blueprints/billing.py's verify_payment). Like send_portal_ready_email,
    never includes a plaintext password -- instead links to a one-time
    "set your password" reset-token URL, plus a payment receipt summary.
    Never raises; billing.py doesn't gate the API response on this
    succeeding, same best-effort contract as send_portal_ready_email."""
    try:
        email_cfg = get_email_config()
        if not email_cfg:
            return False
        from utils.plan_limits import format_price_inr
        import datetime as _dt
        amount_display = format_price_inr(amount_paise)
        paid_on = _dt.datetime.now().strftime("%d %b %Y")
        html_body = f"""
<div style="font-family:Segoe UI,sans-serif;max-width:520px;margin:auto;background:#f8fafc;border-radius:16px;overflow:hidden;border:1px solid #dbeafe;">
  <div style="background:#1e3a8a;padding:24px 28px;color:white;">
    <div style="font-size:20px;font-weight:700;">Payment received — your HRMS portal is ready</div>
    <div style="font-size:13px;opacity:0.75;margin-top:4px;">{company_name}</div>
  </div>
  <div style="padding:28px;">
    <p style="font-size:15px;color:#1e293b;margin-bottom:20px;">Your payment was successful and your organisation's dedicated HRMS portal has been created.</p>
    <a href="{set_password_url}" style="display:block;text-align:center;padding:14px 28px;background:#1e3a8a;color:white;border-radius:10px;text-decoration:none;font-size:15px;font-weight:700;margin-bottom:12px;">
      Set Your Password &amp; Sign In
    </a>
    <p style="font-size:12px;color:#94a3b8;margin-bottom:20px;">This link expires in 1 hour. Or copy it: {set_password_url}</p>
    <div style="background:#f1f5f9;border-radius:10px;padding:16px 18px;margin-bottom:16px;">
      <div style="font-size:13px;font-weight:700;color:#1e293b;margin-bottom:8px;">Payment Receipt</div>
      <div style="font-size:13px;color:#475569;display:flex;justify-content:space-between;margin-bottom:4px;"><span>Plan</span><strong>{plan_display_name}</strong></div>
      <div style="font-size:13px;color:#475569;display:flex;justify-content:space-between;margin-bottom:4px;"><span>Amount Paid</span><strong>{amount_display}</strong></div>
      <div style="font-size:13px;color:#475569;display:flex;justify-content:space-between;margin-bottom:4px;"><span>Date</span><strong>{paid_on}</strong></div>
      <div style="font-size:13px;color:#475569;display:flex;justify-content:space-between;"><span>Payment ID</span><strong>{razorpay_payment_id}</strong></div>
    </div>
    <p style="font-size:12px;color:#94a3b8;">Your portal: {portal_url}</p>
  </div>
</div>"""
        send_email_async(admin_email, f"Payment confirmed — set up your HRMS portal for {company_name}", html_body, email_cfg)
        return True
    except Exception as exc:
        app_log.error("send_payment_confirmation_email failed: %s", exc)
        return False


@org_bp.route("/create_org", methods=["GET", "POST"])
def create_org_disabled():
    return redirect("/login")


@org_bp.route("/org_payment_success", methods=["GET"])
def org_payment_success():
    return redirect("/login")


@org_bp.route("/api/create_org", methods=["POST"])
def api_create_org():
    """JSON API Endpoint to create a new Organisation / Tenant (mobile app's
    registration flow). Mirrors /create_org's validation -- particularly
    the reserved-subdomain check and required, format-checked admin email --
    since this is a second, independent path into the same tenant-creation
    logic and must not be a softer bypass of those protections."""
    try:
        data = request.get_json() or {}
        company_name = data.get("company_name", "").strip()
        raw_subdomain = data.get("subdomain", "").strip().lower()
        # Clean subdomain: convert dots, spaces, special chars to hyphens
        subdomain = re.sub(r'[^a-z0-9\-]', '-', raw_subdomain).strip('-')
        admin_username = data.get("admin_username", "").strip()
        admin_password = data.get("admin_password", "").strip()
        admin_email = data.get("admin_email", "").strip()
        plan = data.get("plan", "starter").strip().lower()

        error = _validate_new_tenant_fields(company_name, subdomain, admin_username, admin_password, admin_email, plan)
        if error:
            return jsonify({"ok": False, "msg": error}), 400

        ok, error, _portal_url = provision_tenant(company_name, subdomain, admin_username, admin_password, admin_email, plan)
        if not ok:
            # "Already taken" is client-correctable (400); anything else is
            # a provisioning-side failure (schema creation, seeding, master
            # registry) worth surfacing as a real server error.
            status = 400 if "already taken" in error else 500
            return jsonify({"ok": False, "msg": error}), status

        return jsonify({
            "ok": True,
            "msg": f"Organisation '{company_name}' created successfully! You can now sign in as {admin_username}.",
            "subdomain": subdomain,
            "username": admin_username
        })
    except Exception as global_exc:
        app_log.error("api_create_org global exception: %s", global_exc)
        return jsonify({"ok": False, "msg": f"Server error: {global_exc}"}), 500


# /superadmin is superseded by /super_admin — redirect for backwards compat
@org_bp.route("/superadmin")
def superadmin_redirect():
    return redirect("/super_admin/login")
