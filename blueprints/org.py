# -*- coding: utf-8 -*-
"""Org blueprint -- multi-tenant org self-registration."""
import re
from flask import Blueprint, request, redirect, render_template, flash, jsonify, session
from extensions import app_log, limiter
from utils.auth import generate_password_hash, turnstile_enabled, verify_turnstile, _TURNSTILE_SITE_KEY
from utils.plan_limits import PLAN_LABEL, PER_EMPLOYEE_PAISE, format_price_inr
from utils.email_utils import get_email_config, send_email_async
from utils.tenant_routing import RESERVED_PATH_SEGMENTS
from utils.helpers import clean_email_domain, validate_email_domain_format, _safe_app_url

org_bp = Blueprint("org", __name__)

_SUBDOMAIN_RE = re.compile(r'^[a-z0-9\-]+$')
_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

# Tenants are addressed by URL path now (<apex-domain>/<subdomain>/...),
# not subdomain -- portal_url below builds that apex from _safe_app_url()
# (the current request's own host in dev, APP_URL in production) rather
# than a hardcoded domain. The DB column and every internal variable are
# still named "subdomain" (no migration needed, it's just a slug string
# either way).

# Slugs that must never be self-registered -- shared with
# utils/tenant_routing.py's WSGI middleware, which uses the exact same set
# to decide whether a URL's first path segment is a company slug or a real
# top-level route (e.g. registering "login" as a company would otherwise
# make www.hrzest.com/login ambiguous between the global login-picker page
# and a company's own portal).
_RESERVED_SUBDOMAINS = RESERVED_PATH_SEGMENTS


def _clean_subdomain_slug(raw, company_name=""):
    if not raw and company_name:
        raw = company_name
    s = str(raw).strip().lower()
    s = re.sub(r'^https?://', '', s)
    s = s.split('/')[0].split(':')[0]
    for suffix in [".hrzest.com", ".hrms.gradzest.com", ".gradzest.com", ".gradzest.in", ".com", ".in", ".org", ".net", ".io"]:
        if s.endswith(suffix):
            s = s[:-len(suffix)]
    s = re.sub(r'[^a-z0-9\-]', '', s)
    return s

def _validate_new_tenant_fields(company_name, subdomain, admin_username, admin_password, admin_email,
                                 email_domain=None):
    """Shared field validation for all three tenant-creation entry points
    (/create_org, /api/create_org, and the platform-admin-initiated create
    flow in platform_admin.py) -- keeps the reserved-subdomain and
    email-format checks from drifting out of sync across call sites.
    Returns an error message, or None if every field is valid.

    email_domain is required for every new company (e.g. "acme.com") --
    it's what utils/helpers.py's validate_employee_email_domain() later
    checks new employees' emails against. Existing tenants provisioned
    before this field existed simply have none set, which keeps that
    check a no-op for them (see validate_employee_email_domain's
    docstring) -- this requirement only applies going forward."""
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
    domain_error = validate_email_domain_format(clean_email_domain(email_domain))
    if domain_error:
        return domain_error
    return None


_PAYMENT_OPTIONS = frozenset({"online", "manual", "trial"})


def provision_tenant(company_name, subdomain, admin_username, admin_password, admin_email,
                      payment_option="online", email_domain=None, employee_count=None, logo_path=None):
    """Shared tenant-provisioning core: schema creation, admin-user seed,
    and master-registry insert. Callers must run
    _validate_new_tenant_fields() first -- this only does the actual
    provisioning, which is where the three call sites would otherwise
    duplicate ~80 near-identical lines.

    payment_option is a record of how the tenant is billed ("online" via
    Razorpay, "manual" bank-transfer/invoice, or "trial") -- it doesn't
    trigger any charge itself, that already happened (or didn't, for
    "manual"/"trial") before this function is called.

    email_domain (e.g. "acme.com") is stored on the new tenant's own
    company_settings row -- utils/helpers.py's validate_employee_email_domain()
    reads it from there to require/check new employees' emails going forward.

    logo_path is a relative static/ path (e.g. "company_logos/acme.png",
    as returned by utils/helpers.py's save_uploaded_logo()) for the
    company logo collected on the registration form -- written to
    company_settings.logo_url so it's already in place the first time
    anyone (employee, admin, or HR) opens a dashboard. None/omitted means
    no logo was uploaded at signup; the default "no logo" rendering
    (templates already fall back to a generic building icon) applies.

    employee_count is the number of seats actually paid for -- written to
    company_settings.paid_employee_slots (a column that already existed in
    the schema migrations but was never populated or enforced anywhere;
    see utils/helpers.py's add_employee_seat_cap_check() for where it's
    checked). None means unlimited -- used by the free/unmetered callers
    (the local-dev fallback POST /create_org, the mobile app's own
    /api/create_org registration flow, and Platform Admin's own tenant
    creation), which intentionally don't gate on payment.

    Returns (ok, error_message_or_None, portal_url_or_None, checkin_url_or_None).
    """
    if payment_option not in _PAYMENT_OPTIONS:
        payment_option = "online"
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
            return False, f"Subdomain '{subdomain}' is already taken. Choose another.", None, None
    except Exception as exc:
        app_log.error("provision_tenant subdomain check failed: %s", exc)
        return False, "Could not check subdomain availability. Please try again.", None, None

    try:
        from database import create_tenant_schema
        create_tenant_schema(db_name)
    except Exception as exc:
        app_log.error("provision_tenant schema creation failed: %s", exc)
        return False, "Failed to create organisation. Please contact support.", None, None

    try:
        from flask import g as _g
        _g.tenant_db = db_name
        from app import init_tenant_db
        init_tenant_db(db_name)
    except Exception as exc:
        app_log.error("provision_tenant schema init failed: %s", exc)
        return False, "Failed to initialise organisation schema. Please contact support.", None, None

    try:
        from database import get_tenant_db
        tconn = get_tenant_db(db_name)
        tcur = tconn.cursor()
        logo_url = f"/static/{logo_path}" if logo_path else None
        tcur.execute(
            "UPDATE company_settings SET company_name=%s, email_domain=%s, paid_employee_slots=%s, "
            "logo_url=COALESCE(%s, logo_url), setup_done=1 WHERE id=1",
            (company_name, clean_email_domain(email_domain) or None, employee_count, logo_url)
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
        return False, f"Failed to seed tenant data: {exc}", None, None

    try:
        from database import get_master_db
        mconn = get_master_db()
        mcur = mconn.cursor()
        mcur.execute(
            "INSERT INTO tenants (company_name, subdomain, db_name, admin_email, plan, payment_option, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'active')",
            (company_name, subdomain, db_name, admin_email, PLAN_LABEL, payment_option)
        )
        mconn.commit()
        mcur.close()
        mconn.close()
    except Exception as exc:
        return False, f"Tenant registered in DB but master registry failed: {exc}", None, None

    # NOTE: the live tenant-admin login route is "/login" (auth.py's
    # admin_login() view) -- "/admin_login" hasn't been a real route since
    # an earlier rename and 404s. Fixed here since this exact line already
    # needed touching for the path-based URL migration; not otherwise
    # in scope for this change.
    #
    # _safe_app_url() instead of a hardcoded apex domain: the old
    # "https://www.hrzest.com/..." constant meant every successful signup
    # (once /api/create_org actually returns portal_url -- see that route)
    # would redirect the browser to a real external domain instead of
    # wherever this app is actually running (localhost in dev, a staging
    # host, etc).
    portal_url = f"{_safe_app_url()}/{subdomain}/login"
    # Public, unauthenticated kiosk scanner for this company (blueprints/
    # core.py's checkin_page()) -- separate from portal_url above, which is
    # the admin login. Employees mark attendance here without ever logging
    # into a dashboard first.
    checkin_url = f"{_safe_app_url()}/{subdomain}/checkin"
    return True, None, portal_url, checkin_url


def send_portal_ready_email(admin_email, company_name, admin_username, portal_url, admin_password="", checkin_url=None):
    """Welcome email with the tenant's dedicated portal link and login credentials.

    checkin_url is the company's own public attendance-scanner page
    (blueprints/core.py's checkin_page()) -- included so whoever registered
    the company can immediately hand it to employees / post it at the
    office without first finding it themselves in Settings."""
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

        checkin_block = ""
        if checkin_url:
            checkin_block = f"""
            <div style="background:#f0fdf4;border-left:4px solid #16a34a;padding:14px;border-radius:6px;margin:18px 0;font-size:13px;color:#166534;">
              <div style="font-weight:700;margin-bottom:6px;">&#128205; Employee Check-In Page</div>
              <div>Share this link with your employees, or post it as a QR code at the office -- no login required to mark attendance:</div>
              <div style="margin-top:8px;"><a href="{checkin_url}" style="color:#15803d;font-weight:700;">{checkin_url}</a></div>
            </div>
            """

        html_body = f"""
<div style="font-family:Segoe UI,sans-serif;max-width:540px;margin:auto;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #e2e8f0;box-shadow:0 10px 30px rgba(0,0,0,0.08);">
  <div style="background:linear-gradient(135deg,#0f172a 0%,#1e3a8a 100%);padding:28px;color:white;text-align:center;">
    <div style="font-size:24px;font-weight:800;">🏢 {company_name}</div>
    <div style="font-size:14px;opacity:0.85;margin-top:6px;">Your Dedicated HRzest.com Portal is Ready</div>
  </div>
  <div style="padding:28px;">
    <p style="font-size:15px;color:#334155;margin-bottom:16px;line-height:1.6;">
      Welcome to HRzest.com! Your company workspace has been fully configured and set up by our onboarding team.
    </p>

    {creds_block}

    <a href="{portal_url}" style="display:block;text-align:center;padding:16px 28px;background:linear-gradient(135deg,#0284c7,#2563eb);color:white;border-radius:12px;text-decoration:none;font-size:16px;font-weight:700;margin:24px 0;box-shadow:0 6px 20px rgba(37,99,235,0.35);">
      🚀 Launch Your Branded Dashboard
    </a>

    <p style="font-size:12px;color:#94a3b8;text-align:center;">Or copy this link to your browser: <br><a href="{portal_url}" style="color:#2563eb;">{portal_url}</a></p>

    {checkin_block}
  </div>
</div>"""
        send_email_async(admin_email, f"Your HRzest.com Portal is Ready -- {company_name}", html_body, email_cfg)
        return True
    except Exception as exc:
        app_log.error("send_portal_ready_email failed: %s", exc)
        return False


def send_payment_confirmation_email(admin_email, company_name, portal_url, set_password_url,
                                     employee_count, amount_paise, razorpay_payment_id, checkin_url=None):
    """Post-payment welcome email for the paid /create_org flow
    (blueprints/billing.py's verify_payment). Like send_portal_ready_email,
    never includes a plaintext password -- instead links to a one-time
    "set your password" reset-token URL, plus a payment receipt summary.
    Never raises; billing.py doesn't gate the API response on this
    succeeding, same best-effort contract as send_portal_ready_email.

    checkin_url is the company's own public attendance-scanner page, same
    as send_portal_ready_email's -- included here too so a paid signup
    gets it just as readily as a manually-provisioned one."""
    try:
        email_cfg = get_email_config()
        if not email_cfg:
            return False
        import datetime as _dt
        amount_display = format_price_inr(amount_paise)
        plan_display_name = f"₹{PER_EMPLOYEE_PAISE // 100}/employee × {employee_count}"
        paid_on = _dt.datetime.now().strftime("%d %b %Y")
        checkin_block = ""
        if checkin_url:
            checkin_block = f"""
    <div style="background:#f0fdf4;border-left:4px solid #16a34a;padding:14px;border-radius:6px;margin-bottom:16px;font-size:13px;color:#166534;">
      <div style="font-weight:700;margin-bottom:6px;">&#128205; Employee Check-In Page</div>
      <div>Share this link with your employees, or post it as a QR code at the office -- no login required to mark attendance:</div>
      <div style="margin-top:8px;"><a href="{checkin_url}" style="color:#15803d;font-weight:700;">{checkin_url}</a></div>
    </div>
            """
        html_body = f"""
<div style="font-family:Segoe UI,sans-serif;max-width:520px;margin:auto;background:#f8fafc;border-radius:16px;overflow:hidden;border:1px solid #dbeafe;">
  <div style="background:#1e3a8a;padding:24px 28px;color:white;">
    <div style="font-size:20px;font-weight:700;">Payment received -- your HRzest.com portal is ready</div>
    <div style="font-size:13px;opacity:0.75;margin-top:4px;">{company_name}</div>
  </div>
  <div style="padding:28px;">
    <p style="font-size:15px;color:#1e293b;margin-bottom:20px;">Your payment was successful and your organisation's dedicated HRzest.com portal has been created.</p>
    <a href="{set_password_url}" style="display:block;text-align:center;padding:14px 28px;background:#1e3a8a;color:white;border-radius:10px;text-decoration:none;font-size:15px;font-weight:700;margin-bottom:12px;">
      Set Your Password &amp; Sign In
    </a>
    <p style="font-size:12px;color:#94a3b8;margin-bottom:20px;">This link expires in 1 hour. Or copy it: {set_password_url}</p>
    <div style="background:#f1f5f9;border-radius:10px;padding:16px 18px;margin-bottom:16px;">
      <div style="font-size:13px;font-weight:700;color:#1e293b;margin-bottom:8px;">Payment Receipt</div>
      <div style="font-size:13px;color:#475569;display:flex;justify-content:space-between;margin-bottom:4px;"><span>Billing</span><strong>{plan_display_name}</strong></div>
      <div style="font-size:13px;color:#475569;display:flex;justify-content:space-between;margin-bottom:4px;"><span>Amount Paid</span><strong>{amount_display}</strong></div>
      <div style="font-size:13px;color:#475569;display:flex;justify-content:space-between;margin-bottom:4px;"><span>Date</span><strong>{paid_on}</strong></div>
      <div style="font-size:13px;color:#475569;display:flex;justify-content:space-between;"><span>Payment ID</span><strong>{razorpay_payment_id}</strong></div>
    </div>

    {checkin_block}

    <p style="font-size:12px;color:#94a3b8;">Your portal: {portal_url}</p>
  </div>
</div>"""
        send_email_async(admin_email, f"Payment confirmed -- set up your HRzest.com portal for {company_name}", html_body, email_cfg)
        return True
    except Exception as exc:
        app_log.error("send_payment_confirmation_email failed: %s", exc)
        return False


@org_bp.route("/get-started", methods=["GET"])
def get_started_page():
    """Retired standalone chooser page -- the landing page ("/") now shows
    its own "Create Your Company" / "Login" links directly instead of
    sending visitors through this extra hop. Kept as a redirect (rather
    than removed outright) so old bookmarks/links/emails pointing here
    still land somewhere useful; "get-started" also stays in
    RESERVED_PATH_SEGMENTS so no company can ever claim it as a slug."""
    from utils.analytics import track_page_view
    track_page_view("/get-started")
    return redirect("/")


@org_bp.route("/create_org", methods=["GET"])
def create_org_page():
    # Flashed messages live in the session cookie, not scoped to any one
    # page -- an unrelated admin-session-expiry notice (category
    # "warning", queued by app.py's _enforce_session_lifetime /
    # _enforce_idle_timeout / _enforce_csrf hooks on some earlier request
    # in this same browser, possibly a different tab entirely) must never
    # surface on this public signup page just because it shares a cookie
    # with that admin session. This page's own flashes (validation
    # errors, captcha failures, from the POST handler below) are always
    # category "error" -- keep only those, drop everything else.
    if session.get("_flashes"):
        session["_flashes"] = [f for f in session["_flashes"] if f[0] == "error"]
    from utils.analytics import track_page_view
    track_page_view("/create_org")
    return render_template(
        "create_org.html",
        per_employee_paise=PER_EMPLOYEE_PAISE,
        show_captcha=turnstile_enabled(),
        turnstile_site_key=_TURNSTILE_SITE_KEY,
    )


@org_bp.route("/create_org", methods=["POST"])
def create_org():
    """Direct-POST provisioning path. templates/create_org.html's JS no
    longer submits here directly when Razorpay is configured (it goes
    through blueprints/billing.py's create_order/verify_payment instead,
    and no longer collects a password at all) -- but this route stays live
    as a free fallback whenever RAZORPAY_KEY_ID/SECRET aren't set (local
    dev, CI, and every test fixture that provisions a real tenant via this
    exact endpoint, e.g. tests/test_ip_ban.py's signup_enabled_org). Once
    real Razorpay keys are configured, hitting this directly with a
    crafted POST (bypassing payment) is rejected -- the JSON /api/create_org
    endpoint below is unrelated (mobile app's own registration flow) and is
    untouched either way."""
    from utils.razorpay_utils import razorpay_configured
    if razorpay_configured():
        flash("Please use the signup form to complete payment and create your organisation.", "error")
        return redirect("/create_org")

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
    subdomain = _clean_subdomain_slug(request.form.get("subdomain", ""), company_name)
    admin_username = request.form.get("admin_username", "").strip()
    admin_password = request.form.get("admin_password", "").strip()
    admin_email = request.form.get("admin_email", "").strip()
    email_domain = clean_email_domain(request.form.get("email_domain", ""))

    error = _validate_new_tenant_fields(company_name, subdomain, admin_username, admin_password, admin_email,
                                         email_domain)
    if error:
        flash(error, "error")
        return redirect("/create_org")

    logo_path = None
    logo_file = request.files.get("logo")
    if logo_file and logo_file.filename:
        from utils.helpers import save_uploaded_logo
        logo_path, logo_err = save_uploaded_logo(logo_file, subdomain)
        if logo_err:
            flash(f"Company logo: {logo_err}", "error")
            return redirect("/create_org")

    ok, error, portal_url, checkin_url = provision_tenant(company_name, subdomain, admin_username, admin_password,
                                                            admin_email, email_domain=email_domain, logo_path=logo_path)
    if not ok:
        flash(error, "error")
        return redirect("/create_org")

    email_sent = send_portal_ready_email(admin_email, company_name, admin_username, portal_url,
                                          checkin_url=checkin_url)

    return render_template(
        "org_created.html",
        company_name=company_name, subdomain=subdomain,
        admin_username=admin_username, admin_email=admin_email,
        portal_url=portal_url, checkin_url=checkin_url, email_sent=email_sent,
    )


@org_bp.route("/org_payment_success", methods=["GET"])
def org_payment_success():
    """Landing page after templates/create_org.html's JS successfully
    verifies payment (blueprints/billing.py's verify_payment) -- every value
    here is display-only, Jinja auto-escapes all of them so a tampered
    query string can't inject anything, and none of them drive any
    server-side decision (the real charge already happened via Razorpay
    before this page ever loads) -- a tampered employee_count/amount_display
    would at worst show the visitor an inaccurate receipt summary, not
    grant or alter anything. Order ID stays out of the URL regardless,
    since that one IS still only in the confirmation email."""
    portal_url = request.args.get("portal_url", "")
    email = request.args.get("email", "")
    employee_count = request.args.get("employee_count", "")
    amount_display = request.args.get("amount_display", "")
    return render_template(
        "org_payment_success.html", portal_url=portal_url, email=email,
        employee_count=employee_count, amount_display=amount_display,
    )


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

        email_domain = clean_email_domain(data.get("email_domain", ""))

        error = _validate_new_tenant_fields(company_name, subdomain, admin_username, admin_password, admin_email,
                                             email_domain)
        if error:
            return jsonify({"ok": False, "msg": error}), 400

        ok, error, portal_url, checkin_url = provision_tenant(company_name, subdomain, admin_username, admin_password,
                                                                admin_email, email_domain=email_domain)
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
            "username": admin_username,
            # The signup form's submit handler redirects here on success
            # (json.portal_url || '/login') -- this was previously discarded
            # as _portal_url and never included, so every successful signup
            # silently fell through to the bare /login page instead of the
            # new tenant's own portal.
            "portal_url": portal_url,
            "checkin_url": checkin_url,
        })
    except Exception as global_exc:
        app_log.error("api_create_org global exception: %s", global_exc)
        return jsonify({"ok": False, "msg": f"Server error: {global_exc}"}), 500


# /superadmin is superseded by /super_admin -- redirect for backwards compat
@org_bp.route("/superadmin")
def superadmin_redirect():
    return redirect("/super_admin/login")


@org_bp.route("/api/leads", methods=["POST"])
@limiter.limit("5 per minute")
def submit_lead():
    """"Request info" form on the public landing page (templates/landing.html)
    -- for visitors who want more details before self-registering via
    /create_org. Stored in att_master.leads, surfaced on the Platform Admin
    dashboard for manual follow-up. Deliberately has no admin-facing error
    detail beyond "required" -- this is a public, unauthenticated endpoint."""
    if turnstile_enabled():
        token = request.form.get("cf-turnstile-response") or (request.get_json(silent=True) or {}).get("cf_turnstile_response", "")
        if not verify_turnstile(token, request.remote_addr):
            return jsonify({"ok": False, "msg": "Captcha verification failed. Please try again."}), 400

    data = request.get_json(silent=True) or request.form
    name = (data.get("name") or "").strip()[:200]
    email = (data.get("email") or "").strip()[:200]
    phone = (data.get("phone") or "").strip()[:30] or None
    company_name = (data.get("company_name") or "").strip()[:200] or None
    message = (data.get("message") or "").strip()[:2000] or None

    if not name or not email:
        return jsonify({"ok": False, "msg": "Name and email are required."}), 400
    if not _EMAIL_RE.match(email):
        return jsonify({"ok": False, "msg": "Enter a valid email address."}), 400

    try:
        from database import get_master_db
        conn = get_master_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO leads (name, email, phone, company_name, message) VALUES (%s, %s, %s, %s, %s)",
            (name, email, phone, company_name, message)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as exc:
        app_log.error("submit_lead failed: %s", exc)
        return jsonify({"ok": False, "msg": "Could not submit right now. Please try again."}), 500

    return jsonify({"ok": True, "msg": "Thanks! We'll be in touch shortly."})
