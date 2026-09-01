# -*- coding: utf-8 -*-
"""Billing blueprint -- Razorpay-backed paid signup for the public
/create_org flow (templates/create_org.html).

Flow: an applicant first goes through blueprints/org.py's gated signup
(OTP email verification, KYC document upload, platform-admin review) --
only once an application is approved (status='approved_pending_payment')
does this blueprint come into play. create_order() creates a Razorpay
order + a staging `payment_orders` row (att_master schema) keyed off that
already-approved application; the tenant schema only gets provisioned once
verify_payment() confirms the payment signature, using the
admin_password_hash already stored on the application (set, hashed, at
signup step 1 -- well before payment, once OTP + documents were reviewed)
so there's no separate "set your password" reset-link step needed anymore
for this flow, unlike the old instant-provisioning design this replaced.

The Platform Admin's own "Create a new company" form (blueprints/
platform_admin.py) is untouched and stays free/unmetered -- this billing
flow only gates the public self-service signup path.
"""
import secrets
import datetime
from flask import Blueprint, request, jsonify
from extensions import app_log, limiter, log_security_event
from database import get_master_db
from utils.plan_limits import PLAN_LABEL, calculate_price, format_price_inr
from utils.razorpay_utils import (
    create_order as razorpay_create_order, verify_payment_signature,
    key_id as razorpay_key_id, create_id_or_demo, verify_or_demo,
)
billing_bp = Blueprint("billing", __name__)

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
    """Payment now happens AFTER a platform admin approves the applicant's
    gated signup (blueprints/org.py's tenant_applications), not before --
    so this no longer collects fresh company/admin fields from the client
    at all (those were already validated, duplicate-checked, and OTP/KYC
    verified during the application). It only needs application_id
    (identifying an already-approved application) and employee_count
    (the one thing genuinely decided at checkout time)."""
    data = request.get_json(silent=True) or request.form
    try:
        application_id = int(data.get("application_id"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "msg": "Missing or invalid application_id."}), 400

    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute(
        "SELECT company_name, subdomain, admin_username, admin_email, email_domain, logo_path, status "
        "FROM tenant_applications WHERE id=%s",
        (application_id,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return jsonify({"ok": False, "msg": "Application not found."}), 404
    company_name, subdomain, admin_username, admin_email, email_domain, logo_path, status = row
    if status != "approved_pending_payment":
        return jsonify({"ok": False, "msg": "This application isn't ready for payment."}), 400

    try:
        employee_count = int(data.get("employee_count") or 1)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "msg": "Employee count must be a number."}), 400
    if employee_count < 1:
        return jsonify({"ok": False, "msg": "Employee count must be at least 1."}), 400

    amount_paise = calculate_price(employee_count)

    receipt_id = f"signup_{subdomain}_{int(datetime.datetime.now().timestamp())}"
    order_id, is_demo, error = create_id_or_demo(
        _DEMO_ORDER_PREFIX, lambda: razorpay_create_order(amount_paise, receipt_id)
    )
    if error:
        app_log.error("billing.create_order failed: %s", error)
        return jsonify({"ok": False, "msg": error}), 502

    try:
        conn = get_master_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO payment_orders (razorpay_order_id, plan, employee_count, amount_paise, "
            "company_name, subdomain, admin_username, admin_email, email_domain, logo_path, application_id, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'created')",
            (order_id, PLAN_LABEL, employee_count, amount_paise, company_name, subdomain, admin_username, admin_email,
             email_domain, logo_path, application_id)
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
    from utils.auth import generate_password_hash
    from utils.helpers import _safe_app_url

    data = request.get_json(silent=True) or request.form
    razorpay_order_id = (data.get("razorpay_order_id") or "").strip()
    razorpay_payment_id = (data.get("razorpay_payment_id") or "").strip()
    razorpay_signature = (data.get("razorpay_signature") or "").strip()

    ok, is_demo, error = verify_or_demo(
        razorpay_order_id, _DEMO_ORDER_PREFIX, razorpay_payment_id, razorpay_signature, verify_payment_signature
    )
    if is_demo and ok:
        log_security_event(
            "billing.demo_checkout_completed", "Demo/test-mode checkout completed (no real payment)",
            level="INFO", order_id=razorpay_order_id,
        )
    elif not ok:
        if not is_demo:
            log_security_event(
                "billing.signature_invalid", "Razorpay payment signature verification failed",
                level="ERROR", order_id=razorpay_order_id,
            )
        return jsonify({"ok": False, "msg": error}), 400

    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute(
        "SELECT employee_count, company_name, subdomain, admin_username, admin_email, email_domain, logo_path, "
        "status, application_id "
        "FROM payment_orders WHERE razorpay_order_id=%s",
        (razorpay_order_id,)
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return jsonify({"ok": False, "msg": "Unknown order."}), 404

    (employee_count, company_name, subdomain, admin_username, admin_email, email_domain, logo_path, status,
     application_id) = row

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

    # The applicant already set (and it was hashed at) their real admin
    # password during the gated signup application -- OTP-verified and
    # KYC-document-reviewed well before payment ever happens now, unlike
    # the old flow where payment was the very first step and no password
    # had been collected yet. So there's no more random-password +
    # "set your password" reset-link dance needed: provision_tenant() just
    # gets the hash that's already on file.
    admin_password_hash = None
    if application_id:
        aconn = get_master_db()
        acur = aconn.cursor(buffered=True)
        acur.execute("SELECT admin_password_hash FROM tenant_applications WHERE id=%s", (application_id,))
        arow = acur.fetchone()
        acur.close()
        aconn.close()
        admin_password_hash = arow[0] if arow else None
    if not admin_password_hash:
        # Defensive fallback for a payment_orders row with no linked
        # application (shouldn't happen via create_order() above, which
        # now requires one) -- still provisions correctly with a random
        # password the admin can recover via the normal forgot-password flow.
        app_log.warning("billing.verify_payment: order %s has no linked application; using a random password", razorpay_order_id)
        admin_password_hash = generate_password_hash(secrets.token_urlsafe(24))

    ok, error, portal_url, checkin_url = provision_tenant(
        company_name, subdomain, admin_username, admin_password_hash, admin_email,
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
    if application_id and tenant_row:
        cur.execute(
            "UPDATE tenant_applications SET status='provisioned', tenant_id=%s, updated_at=NOW() WHERE id=%s",
            (tenant_row[0], application_id)
        )
    conn.commit()
    cur.close()
    conn.close()

    send_payment_confirmation_email(
        admin_email, company_name, portal_url,
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
