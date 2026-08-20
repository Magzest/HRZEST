# -*- coding: utf-8 -*-
"""Billing blueprint -- Razorpay-backed paid signup for the public
/create_org flow (templates/create_org.html).

Flow: create_order() creates a Razorpay order + a staging `payment_orders`
row (att_master schema) BEFORE any tenant exists -- the tenant schema only
gets provisioned once verify_payment() confirms the payment signature.
This mirrors blueprints/org.py's provision_tenant() core but never collects
or stores a plaintext password: the new admin account gets a random,
never-surfaced password, and the customer sets their own via the same
password-reset-token mechanism blueprints/auth.py's admin_forgot_password
already uses (confirmed with the user: no plaintext password in email,
consistent with this codebase's existing never-email-passwords posture --
see org.py's send_portal_ready_email docstring).

The Platform Admin's own "Create a new company" form (blueprints/
platform_admin.py) is untouched and stays free/unmetered -- this billing
flow only gates the public self-service signup path.
"""
import secrets
import hashlib
import datetime
from flask import Blueprint, request, jsonify
from extensions import app_log, limiter, log_security_event
from database import get_master_db
from utils.plan_limits import PLAN_LABEL, calculate_price, format_price_inr
from utils.razorpay_utils import (
    create_order as razorpay_create_order, verify_payment_signature,
    key_id as razorpay_key_id, razorpay_configured,
)
from utils.auth import turnstile_enabled, verify_turnstile

billing_bp = Blueprint("billing", __name__)

# Used only to satisfy blueprints.org._validate_new_tenant_fields()'s
# "password required, >=8 chars" check -- the billing flow no longer
# collects a password from the customer at all (see module docstring), so
# this placeholder stands in for validation purposes only and is NEVER
# passed to provision_tenant() as the real account password.
_VALIDATION_PLACEHOLDER_PASSWORD = "billing-flow-placeholder"

# Demo/test-mode checkout, used only while RAZORPAY_KEY_ID/SECRET aren't
# configured -- lets the full register -> pay -> provisioned flow be
# exercised end-to-end (e.g. templates/create_org.html's mock checkout
# modal) without real payment credentials. Real Razorpay order IDs are
# always "order_<their own id>" and never carry this prefix, and
# verify_payment() below additionally refuses to honor this prefix at all
# once real keys ARE configured -- so this can never become a bypass in
# production, only a local/demo convenience before Razorpay is wired up.
_DEMO_ORDER_PREFIX = "demo_order_"


@billing_bp.route("/api/billing/create_order", methods=["POST"])
@limiter.limit("10 per minute")
def create_order():
    from blueprints.org import _validate_new_tenant_fields
    from utils.helpers import clean_email_domain

    if turnstile_enabled():
        token = request.form.get("cf-turnstile-response") or (request.get_json(silent=True) or {}).get("cf_turnstile_response", "")
        if not verify_turnstile(token, request.remote_addr):
            return jsonify({"ok": False, "msg": "Captcha verification failed. Please try again."}), 400

    data = request.get_json(silent=True) or request.form
    company_name = (data.get("company_name") or "").strip()
    subdomain = (data.get("subdomain") or "").strip().lower()
    admin_username = (data.get("admin_username") or "").strip()
    admin_email = (data.get("admin_email") or "").strip()
    email_domain = clean_email_domain(data.get("email_domain") or "")
    try:
        employee_count = int(data.get("employee_count") or 1)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "msg": "Employee count must be a number."}), 400
    if employee_count < 1:
        return jsonify({"ok": False, "msg": "Employee count must be at least 1."}), 400

    error = _validate_new_tenant_fields(
        company_name, subdomain, admin_username, _VALIDATION_PLACEHOLDER_PASSWORD, admin_email, email_domain
    )
    if error:
        return jsonify({"ok": False, "msg": error}), 400

    # Logo, if the signup form's file input was used -- staged now (before
    # any tenant/payment exists) since request.files is only available on
    # this request, not the later verify_payment() call that actually
    # provisions the tenant. Optional: signup proceeds with no logo on a
    # validation failure too, same as an unset file input.
    logo_path = None
    logo_file = request.files.get("logo")
    if logo_file and logo_file.filename:
        from utils.helpers import save_uploaded_logo
        logo_path, logo_err = save_uploaded_logo(logo_file, subdomain)
        if logo_err:
            return jsonify({"ok": False, "msg": f"Company logo: {logo_err}"}), 400

    amount_paise = calculate_price(employee_count)

    is_demo = not razorpay_configured()
    if is_demo:
        # No real Razorpay call -- see _DEMO_ORDER_PREFIX comment above.
        order_id = _DEMO_ORDER_PREFIX + secrets.token_hex(12)
    else:
        receipt_id = f"signup_{subdomain}_{int(datetime.datetime.now().timestamp())}"
        order_id, error = razorpay_create_order(amount_paise, receipt_id)
        if not order_id:
            app_log.error("billing.create_order failed: %s", error)
            return jsonify({"ok": False, "msg": error}), 502

    try:
        conn = get_master_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO payment_orders (razorpay_order_id, plan, employee_count, amount_paise, "
            "company_name, subdomain, admin_username, admin_email, email_domain, logo_path, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'created')",
            (order_id, PLAN_LABEL, employee_count, amount_paise, company_name, subdomain, admin_username, admin_email,
             email_domain, logo_path)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as exc:
        app_log.error("billing.create_order: failed to stage payment_orders row: %s", exc)
        return jsonify({"ok": False, "msg": "Could not start checkout. Please try again."}), 500

    return jsonify({
        "ok": True,
        "order_id": order_id,
        "amount_paise": amount_paise,
        "amount_display": format_price_inr(amount_paise),
        "currency": "INR",
        "key_id": razorpay_key_id(),
        "demo": is_demo,
    })


@billing_bp.route("/api/billing/verify_payment", methods=["POST"])
@limiter.limit("20 per minute")
def verify_payment():
    from blueprints.org import provision_tenant, send_payment_confirmation_email
    from utils.helpers import _safe_app_url

    data = request.get_json(silent=True) or request.form
    razorpay_order_id = (data.get("razorpay_order_id") or "").strip()
    razorpay_payment_id = (data.get("razorpay_payment_id") or "").strip()
    razorpay_signature = (data.get("razorpay_signature") or "").strip()

    is_demo_order = razorpay_order_id.startswith(_DEMO_ORDER_PREFIX)
    if is_demo_order:
        if razorpay_configured():
            # Real keys exist now but this order was minted before that --
            # never honor the demo bypass once real payments are live.
            return jsonify({"ok": False, "msg": "This was a demo order. Please start checkout again."}), 400
        log_security_event(
            "billing.demo_checkout_completed", "Demo/test-mode checkout completed (no real payment)",
            level="INFO", order_id=razorpay_order_id,
        )
    elif not verify_payment_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
        log_security_event(
            "billing.signature_invalid", "Razorpay payment signature verification failed",
            level="ERROR", order_id=razorpay_order_id,
        )
        return jsonify({"ok": False, "msg": "Payment verification failed."}), 400

    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute(
        "SELECT employee_count, company_name, subdomain, admin_username, admin_email, email_domain, logo_path, status "
        "FROM payment_orders WHERE razorpay_order_id=%s",
        (razorpay_order_id,)
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return jsonify({"ok": False, "msg": "Unknown order."}), 404

    employee_count, company_name, subdomain, admin_username, admin_email, email_domain, logo_path, status = row

    # Idempotent: a retried/duplicate client POST for an already-provisioned
    # order must not attempt to re-provision (the subdomain is now taken,
    # which provision_tenant() would correctly reject as "already taken" --
    # but there's no reason to even try).
    if status == "provisioned":
        cur.close()
        conn.close()
        portal_url = f"{_safe_app_url()}/{subdomain}/login"  # "/admin_login" hasn't been a real route since an earlier rename
        return jsonify({"ok": True, "portal_url": portal_url, "already_provisioned": True})

    cur.execute(
        "UPDATE payment_orders SET status='paid', razorpay_payment_id=%s, paid_at=NOW() "
        "WHERE razorpay_order_id=%s",
        (razorpay_payment_id, razorpay_order_id)
    )
    conn.commit()
    cur.close()
    conn.close()

    # Random password, never stored/emailed/logged in plaintext -- the new
    # admin sets their own via the reset-token link below. See module
    # docstring for why (agreed with the user: no plaintext password in
    # email, matching this codebase's existing posture everywhere else).
    random_password = secrets.token_urlsafe(24)
    ok, error, portal_url, checkin_url = provision_tenant(
        company_name, subdomain, admin_username, random_password, admin_email,
        email_domain=email_domain, employee_count=employee_count, logo_path=logo_path
    )
    if not ok:
        app_log.error("billing.verify_payment: provisioning failed for order %s: %s", razorpay_order_id, error)
        conn = get_master_db()
        cur = conn.cursor()
        cur.execute("UPDATE payment_orders SET status='failed' WHERE razorpay_order_id=%s", (razorpay_order_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"ok": False, "msg": f"Payment received, but provisioning failed: {error}. Contact support with order ID {razorpay_order_id}."}), 500

    # Set-your-password token -- same generation scheme as
    # blueprints/auth.py's admin_forgot_password (secrets.token_hex(32),
    # stored as its SHA-256 hash, 1-hour expiry), written directly into the
    # freshly-provisioned tenant schema's admin_users row. Can't reuse
    # admin_forgot_password's route directly: that looks the account up by
    # email against whatever tenant the CURRENT request's Host header
    # resolves to, which here is the billing/create_org host, not the
    # brand-new tenant subdomain.
    reset_token = secrets.token_hex(32)
    token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
    expiry = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    db_name = "att_" + subdomain.replace("-", "_")
    try:
        from database import get_tenant_db
        tconn = get_tenant_db(db_name)
        tcur = tconn.cursor()
        tcur.execute(
            "UPDATE admin_users SET reset_token=%s, reset_token_expiry=%s WHERE username=%s",
            (token_hash, expiry, admin_username)
        )
        tconn.commit()
        tcur.close()
        tconn.close()
    except Exception as exc:
        app_log.error("billing.verify_payment: failed to set reset token for order %s: %s", razorpay_order_id, exc)

    set_password_url = f"{_safe_app_url()}/{subdomain}/admin_reset_password/{reset_token}"

    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute("SELECT id, amount_paise FROM payment_orders WHERE razorpay_order_id=%s", (razorpay_order_id,))
    tenant_row = None
    order_row = cur.fetchone()
    if order_row:
        cur.execute("SELECT id FROM tenants WHERE subdomain=%s", (subdomain,))
        tenant_row = cur.fetchone()
    amount_paise = order_row[1] if order_row else 0
    cur.execute(
        "UPDATE payment_orders SET status='provisioned', tenant_id=%s WHERE razorpay_order_id=%s",
        (tenant_row[0] if tenant_row else None, razorpay_order_id)
    )
    conn.commit()
    cur.close()
    conn.close()

    send_payment_confirmation_email(
        admin_email, company_name, portal_url, set_password_url,
        employee_count, amount_paise, razorpay_payment_id, checkin_url=checkin_url,
    )

    log_security_event(
        "billing.tenant_provisioned", f"Paid tenant '{company_name}' provisioned via Razorpay",
        level="INFO", subdomain=subdomain, employee_count=employee_count, order_id=razorpay_order_id,
    )

    return jsonify({
        "ok": True, "portal_url": portal_url,
        "employee_count": employee_count, "amount_display": format_price_inr(amount_paise),
    })
