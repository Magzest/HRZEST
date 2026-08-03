"""Org blueprint — multi-tenant org self-registration."""
import re
from flask import Blueprint, request, redirect, render_template, flash
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


@org_bp.route("/get-started", methods=["GET"])
def get_started_page():
    """Public entry point for the SaaS product: 'login to your existing
    company' (redirects to <subdomain>.hrms.gradzest.com/admin_login) vs
    'register a new company' (/create_org). Kept separate from the root
    "/" route (blueprints/core.py's home()), which still serves the
    existing single-tenant attendance kiosk for the operator's own
    currently-live company -- switching root itself over is deferred
    until that company is migrated to its own subdomain."""
    return render_template("get_started.html")


@org_bp.route("/create_org", methods=["GET"])
def create_org_page():
    return render_template(
        "create_org.html",
        plan_tiers=PLAN_TIERS,
        show_captcha=turnstile_enabled(),
        turnstile_site_key=_TURNSTILE_SITE_KEY,
    )


@org_bp.route("/create_org", methods=["POST"])
def create_org():
    # Signup has no prior-failure signal to key a captcha off (unlike
    # login's CAPTCHA_AFTER_ATTEMPTS) -- it's shown unconditionally
    # whenever Turnstile is configured, since this is the one endpoint
    # that creates a brand-new schema. Fails open (signup stays reachable)
    # when Turnstile isn't configured, matching how the rest of the app
    # treats an unconfigured gate.
    if turnstile_enabled():
        token = request.form.get("cf-turnstile-response", "")
        if not verify_turnstile(token, request.remote_addr):
            flash("Captcha verification failed. Please try again.", "error")
            return redirect("/create_org")

    company_name = request.form.get("company_name", "").strip()
    subdomain = request.form.get("subdomain", "").strip().lower()
    admin_username = request.form.get("admin_username", "").strip()
    admin_password = request.form.get("admin_password", "").strip()
    admin_email = request.form.get("admin_email", "").strip()
    plan = request.form.get("plan", "starter").strip()

    # Validate
    if not all([company_name, subdomain, admin_username, admin_password, admin_email]):
        flash("All fields (company name, subdomain, admin email/username/password) are required.", "error")
        return redirect("/create_org")
    if not _EMAIL_RE.match(admin_email):
        flash("Enter a valid admin email address.", "error")
        return redirect("/create_org")
    if not _SUBDOMAIN_RE.match(subdomain):
        flash("Subdomain may only contain lowercase letters, digits, and hyphens.", "error")
        return redirect("/create_org")
    if subdomain in _RESERVED_SUBDOMAINS:
        flash(f"Subdomain '{subdomain}' is reserved. Choose another.", "error")
        return redirect("/create_org")
    if len(admin_password) < 8:
        flash("Admin password must be at least 8 characters.", "error")
        return redirect("/create_org")
    if plan not in PLAN_TIERS:
        flash("Choose a valid plan.", "error")
        return redirect("/create_org")

    # Derive DB name
    db_name = "att_" + subdomain.replace("-", "_")

    # Check subdomain not taken — and, critically, that the derived schema
    # name doesn't already exist at all. Checking only the `tenants` registry
    # row (as before) missed two cases: (1) a subdomain like "master" derives
    # db_name "att_master", which IS the tenant-registry schema itself —
    # CREATE SCHEMA IF NOT EXISTS would then silently no-op and the rest of
    # this flow would run tenant-schema migrations and INSERT an
    # attacker-controlled admin account *inside the registry schema*; (2) a
    # schema left over from a previously failed provisioning attempt (schema
    # created, but the tenants-row insert further down failed) has no
    # `tenants` row, so it would look "available" and get silently reused —
    # and the old `ON CONFLICT ... DO UPDATE SET password=...` below would
    # have let a new signup overwrite an existing admin's password in it.
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
            flash(f"Subdomain '{subdomain}' is already taken. Choose another.", "error")
            return redirect("/create_org")
    except Exception as exc:
        app_log.error("create_org subdomain check failed: %s", exc)
        flash("Could not check subdomain availability. Please try again.", "error")
        return redirect("/create_org")

    try:
        from database import create_tenant_schema
        create_tenant_schema(db_name)
    except Exception as exc:
        app_log.error("create_org DB creation failed: %s", exc)
        flash("Failed to create organisation. Please contact support.", "error")
        return redirect("/create_org")

    try:
        from flask import g as _g
        _g.tenant_db = db_name
        from app import init_tenant_db
        init_tenant_db(db_name)
    except Exception as exc:
        app_log.error("create_org schema init failed: %s", exc)
        flash("Failed to initialise organisation schema. Please contact support.", "error")
        return redirect("/create_org")

    # Insert company settings and admin user into the new tenant DB
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
        # genuine race (two signups for the same subdomain at once) rather
        # than legitimate reuse — fail loudly via the except below instead of
        # silently overwriting whichever admin_users row won the race.
        tcur.execute(
            "INSERT INTO admin_users (username, password, email) VALUES (%s, %s, %s)",
            (admin_username, generate_password_hash(admin_password), admin_email)
        )
        tconn.commit()
        tcur.close()
        tconn.close()
    except Exception as exc:
        flash(f"Failed to seed tenant data: {exc}", "error")
        return redirect("/create_org")

    # Register tenant in master DB
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
        flash(f"Tenant registered in DB but master registry failed: {exc}", "error")
        return redirect("/create_org")

    # Best-effort welcome email with the tenant's dedicated portal link --
    # not a plaintext password (the admin already chose their own above,
    # so there's nothing secret left to email), just where to find their
    # new HRMS. Never blocks the signup on failure: the same link is
    # rendered on the success page below regardless of whether this send
    # (or its underlying SMTP config) works.
    portal_url = f"https://{subdomain}.{_TENANT_DOMAIN_SUFFIX}/admin_login"
    email_sent = False
    try:
        email_cfg = get_email_config()
        if email_cfg:
            html_body = f"""
<div style="font-family:Segoe UI,sans-serif;max-width:520px;margin:auto;background:#f8fafc;border-radius:16px;overflow:hidden;border:1px solid #dbeafe;">
  <div style="background:#1e3a8a;padding:24px 28px;color:white;">
    <div style="font-size:20px;font-weight:700;">Your HRMS portal is ready</div>
    <div style="font-size:13px;opacity:0.75;margin-top:4px;">{company_name}</div>
  </div>
  <div style="padding:28px;">
    <p style="font-size:15px;color:#1e293b;margin-bottom:20px;">Your organisation's dedicated HRMS portal has been created.</p>
    <a href="{portal_url}" style="display:block;text-align:center;padding:14px 28px;background:#1e3a8a;color:white;border-radius:10px;text-decoration:none;font-size:15px;font-weight:700;margin-bottom:20px;">
      Go to Your Dashboard
    </a>
    <p style="font-size:13px;color:#64748b;">Log in with the admin username you created during signup: <strong>{admin_username}</strong></p>
    <p style="font-size:12px;color:#94a3b8;margin-top:12px;">Or copy this link: {portal_url}</p>
  </div>
</div>"""
            send_email_async(admin_email, f"Your HRMS portal is ready — {company_name}", html_body, email_cfg)
            email_sent = True
    except Exception as exc:
        app_log.error("create_org welcome email failed: %s", exc)

    return render_template(
        "org_created.html",
        company_name=company_name, subdomain=subdomain,
        admin_username=admin_username, admin_email=admin_email,
        portal_url=portal_url, email_sent=email_sent,
    )
