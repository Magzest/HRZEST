# -*- coding: utf-8 -*-
"""Auto-debit blueprint -- monthly per-employee billing (utils/plan_limits.py's
"₹99/employee/month, flat" rate, already shown in admin_base.html's
"₹X/MO" badge) collected automatically via a Razorpay Subscription instead
of manually. Separate concern from blueprints/seats.py's paid_employee_slots
cap: seats.py gates HOW MANY employees a tenant may register at all;
this blueprint bills them for however many they actually have, every month,
without an admin needing to do anything once enrolled.

Design (Razorpay's documented pattern for seat-based recurring billing):
  - One shared Plan ("₹99/employee/month"), created once via the Plans API
    and cached in att_master.billing_config -- not a per-tenant object.
  - One Subscription per enrolled tenant, with `quantity` = that tenant's
    employee count. Total billed each cycle = plan amount * quantity.
    Razorpay's own recurring engine (real mode) or this module's
    sync_and_bill_auto_debit() (demo mode, run by wsgi.py's scheduler)
    charges it on schedule -- no per-request code triggers a charge.
  - quantity is kept in sync with actual headcount by the same daily job,
    via PATCH .../subscriptions/{id} (real) since Razorpay has no way to
    know a tenant's employee table changed.
  - Real-mode charges are confirmed asynchronously via Razorpay's
    "subscription.charged" webhook (POST /webhooks/razorpay below), not by
    any browser round-trip -- the browser is only present for the initial
    enrollment authorization.
"""
import datetime
from flask import Blueprint, request, session, jsonify, g

from extensions import app_log, limiter, log_security_event
from database import get_db_connection, get_master_db
from utils.auth import admin_required
from utils.helpers import get_company_settings
from utils.plan_limits import PER_EMPLOYEE_PAISE, calculate_price, format_price_inr, get_tenant_employee_count
from utils.razorpay_utils import (
    create_plan, create_customer, create_subscription, update_subscription_quantity,
    cancel_subscription as razorpay_cancel_subscription, verify_payment_signature,
    verify_webhook_signature, key_id as razorpay_key_id, razorpay_configured,
)

auto_debit_bp = Blueprint("auto_debit", __name__)

_DEMO_SUBSCRIPTION_PREFIX = "demo_sub_"
_PLAN_ITEM_NAME = "HRzest per-employee monthly fee"


def _get_or_create_plan_id():
    """Returns (plan_id, error). Cached in billing_config so every tenant's
    subscription shares one Plan -- a fresh Plan per tenant would work too,
    but would mean N near-identical Razorpay dashboard objects for no
    benefit, since `quantity` is what actually varies per tenant."""
    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute("SELECT razorpay_plan_id FROM billing_config WHERE id=1")
    row = cur.fetchone()
    existing = row[0] if row else None
    if existing:
        cur.close()
        conn.close()
        return existing, None

    plan_id, error = create_plan(PER_EMPLOYEE_PAISE, _PLAN_ITEM_NAME)
    if error:
        cur.close()
        conn.close()
        return None, error
    cur.execute("UPDATE billing_config SET razorpay_plan_id=%s WHERE id=1", (plan_id,))
    conn.commit()
    cur.close()
    conn.close()
    return plan_id, None


def _get_mandate(tenant_schema: str):
    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute(
        "SELECT status, razorpay_customer_id, razorpay_subscription_id, quantity_synced "
        "FROM auto_debit_mandates WHERE tenant_schema=%s",
        (tenant_schema,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    return {"status": row[0], "customer_id": row[1], "subscription_id": row[2], "quantity_synced": row[3]}


@auto_debit_bp.route("/api/auto_debit/enroll", methods=["POST"])
@admin_required
@limiter.limit("10 per minute")
def enroll():
    co = get_company_settings()
    mandate = _get_mandate(g.tenant_db)
    if mandate and mandate["status"] == "active":
        return jsonify({"ok": False, "msg": "Auto-debit is already enabled for your company."}), 400

    try:
        db = get_db_connection()
        cur = db.cursor()
        cur.execute("SELECT COUNT(*) FROM employees")
        employee_count = cur.fetchone()[0]
        cur.close()
        db.close()
    except Exception:
        employee_count = 0

    is_demo = not razorpay_configured()
    if is_demo:
        subscription_id = _DEMO_SUBSCRIPTION_PREFIX + g.tenant_db
        customer_id = None
    else:
        plan_id, error = _get_or_create_plan_id()
        if error:
            app_log.error("auto_debit.enroll: plan creation failed: %s", error)
            return jsonify({"ok": False, "msg": error}), 502

        cur_db = get_db_connection()
        c = cur_db.cursor(buffered=True)
        c.execute("SELECT email FROM admin_users WHERE username=%s", (session.get("admin_username"),))
        row = c.fetchone()
        c.close()
        cur_db.close()
        admin_email = (row[0] if row else None) or "billing@example.com"

        customer_id, error = create_customer(co.get("company_name") or g.tenant_db, admin_email)
        if error:
            app_log.error("auto_debit.enroll: customer creation failed: %s", error)
            return jsonify({"ok": False, "msg": error}), 502

        subscription_id, error = create_subscription(plan_id, customer_id, employee_count or 1)
        if error:
            app_log.error("auto_debit.enroll: subscription creation failed: %s", error)
            return jsonify({"ok": False, "msg": error}), 502

    conn = get_master_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO auto_debit_mandates (tenant_schema, company_name, razorpay_customer_id, "
        "razorpay_subscription_id, quantity_synced, status, requested_by, created_at) "
        "VALUES (%s, %s, %s, %s, %s, 'pending', %s, NOW()) "
        "ON CONFLICT (tenant_schema) DO UPDATE SET company_name=%s, razorpay_customer_id=%s, "
        "razorpay_subscription_id=%s, quantity_synced=%s, status='pending', requested_by=%s, "
        "created_at=NOW(), cancelled_at=NULL",
        (g.tenant_db, co.get("company_name") or "", customer_id, subscription_id, employee_count,
         session.get("admin_username"), co.get("company_name") or "", customer_id, subscription_id,
         employee_count, session.get("admin_username"))
    )
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({
        "ok": True,
        "subscription_id": subscription_id,
        "key_id": razorpay_key_id(),
        "demo": is_demo,
        "employee_count": employee_count,
        "amount_display": format_price_inr(calculate_price(employee_count)),
    })


@auto_debit_bp.route("/api/auto_debit/confirm", methods=["POST"])
@admin_required
@limiter.limit("20 per minute")
def confirm():
    data = request.get_json(silent=True) or request.form
    subscription_id = (data.get("razorpay_subscription_id") or "").strip()
    payment_id = (data.get("razorpay_payment_id") or "").strip()
    signature = (data.get("razorpay_signature") or "").strip()

    mandate = _get_mandate(g.tenant_db)
    if not mandate or mandate["subscription_id"] != subscription_id:
        return jsonify({"ok": False, "msg": "Unknown or mismatched subscription."}), 404

    is_demo_sub = subscription_id.startswith(_DEMO_SUBSCRIPTION_PREFIX)
    if is_demo_sub:
        if razorpay_configured():
            return jsonify({"ok": False, "msg": "This was a demo enrollment. Please start again."}), 400
        log_security_event(
            "auto_debit.demo_enrolled", "Demo/test-mode auto-debit enrollment completed (no real mandate)",
            level="INFO", subscription_id=subscription_id,
        )
    elif not verify_payment_signature(subscription_id, payment_id, signature):
        log_security_event(
            "auto_debit.signature_invalid", "Razorpay subscription-authorization signature verification failed",
            level="ERROR", subscription_id=subscription_id,
        )
        return jsonify({"ok": False, "msg": "Authorization verification failed."}), 400

    conn = get_master_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE auto_debit_mandates SET status='active', activated_at=NOW() "
        "WHERE tenant_schema=%s AND razorpay_subscription_id=%s",
        (g.tenant_db, subscription_id)
    )
    conn.commit()
    cur.close()
    conn.close()

    log_security_event(
        "auto_debit.activated", "Monthly auto-debit enabled", level="INFO", subscription_id=subscription_id,
    )
    return jsonify({"ok": True})


@auto_debit_bp.route("/api/auto_debit/cancel", methods=["POST"])
@admin_required
@limiter.limit("10 per minute")
def cancel():
    mandate = _get_mandate(g.tenant_db)
    if not mandate or mandate["status"] != "active":
        return jsonify({"ok": False, "msg": "Auto-debit isn't currently enabled."}), 400

    if not mandate["subscription_id"].startswith(_DEMO_SUBSCRIPTION_PREFIX):
        ok, error = razorpay_cancel_subscription(mandate["subscription_id"])
        if not ok:
            app_log.error("auto_debit.cancel: Razorpay cancel failed: %s", error)
            return jsonify({"ok": False, "msg": error}), 502

    conn = get_master_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE auto_debit_mandates SET status='cancelled', cancelled_at=NOW() WHERE tenant_schema=%s",
        (g.tenant_db,)
    )
    conn.commit()
    cur.close()
    conn.close()

    log_security_event("auto_debit.cancelled", "Monthly auto-debit disabled", level="INFO")
    return jsonify({"ok": True})


@auto_debit_bp.route("/webhooks/razorpay", methods=["POST"])
@limiter.limit("120 per minute")
def razorpay_webhook():
    """No @admin_required -- Razorpay's own servers call this directly with
    no session/cookie, authenticated instead by the X-Razorpay-Signature
    header (verify_webhook_signature). Deliberately never touches
    g.tenant_db (this route has no tenant-prefixed URL, same posture as
    blueprints/platform_admin.py's /super_admin/* per that module's own
    docstring) -- everything it needs lives in the master-schema tables."""
    raw_body = request.get_data()
    signature = request.headers.get("X-Razorpay-Signature", "")
    if not verify_webhook_signature(raw_body, signature):
        log_security_event("auto_debit.webhook_signature_invalid",
                            "Razorpay webhook signature verification failed", level="ERROR")
        return jsonify({"ok": False}), 400

    payload = request.get_json(silent=True) or {}
    event = payload.get("event", "")

    if event == "subscription.charged":
        sub_entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        subscription_id = sub_entity.get("id")
        amount_paise = payment_entity.get("amount")
        payment_id = payment_entity.get("id")
        if subscription_id:
            _record_charge(subscription_id, amount_paise, payment_id, status="paid")

    elif event == "subscription.cancelled":
        subscription_id = payload.get("payload", {}).get("subscription", {}).get("entity", {}).get("id")
        if subscription_id:
            conn = get_master_db()
            cur = conn.cursor()
            cur.execute(
                "UPDATE auto_debit_mandates SET status='cancelled', cancelled_at=NOW() "
                "WHERE razorpay_subscription_id=%s", (subscription_id,)
            )
            conn.commit()
            cur.close()
            conn.close()

    elif event in ("payment.failed", "subscription.pending"):
        sub_entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})
        subscription_id = sub_entity.get("id")
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        if subscription_id:
            _record_charge(
                subscription_id, payment_entity.get("amount"), payment_entity.get("id"),
                status="failed", failure_reason=payment_entity.get("error_description"),
            )

    return jsonify({"ok": True})


def _record_charge(subscription_id, amount_paise, payment_id, status, failure_reason=None):
    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute(
        "SELECT tenant_schema, company_name FROM auto_debit_mandates WHERE razorpay_subscription_id=%s",
        (subscription_id,)
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        app_log.warning("auto_debit._record_charge: unknown subscription_id %s", subscription_id)
        return
    tenant_schema, company_name = row
    employee_count = get_tenant_employee_count(tenant_schema)
    billing_period = datetime.date.today().replace(day=1)
    cur.execute(
        "INSERT INTO monthly_invoices (tenant_schema, company_name, employee_count, amount_paise, "
        "razorpay_payment_id, razorpay_subscription_id, status, billing_period, failure_reason) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (tenant_schema, company_name, employee_count, amount_paise or 0, payment_id, subscription_id,
         status, billing_period, failure_reason)
    )
    conn.commit()
    cur.close()
    conn.close()
    log_security_event(
        f"auto_debit.charge_{status}", f"Monthly auto-debit {status} for {company_name}",
        level="INFO" if status == "paid" else "WARNING",
        subscription_id=subscription_id, amount_paise=amount_paise,
    )


def sync_and_bill_auto_debit():
    """Scheduled once daily (wsgi.py). Two jobs in one pass over every
    active mandate:
      1. Real mode: keep each Subscription's `quantity` in sync with the
         tenant's actual current headcount (Razorpay has no way to know an
         employee table changed -- nothing else ever calls
         update_subscription_quantity()). Real charging itself happens on
         Razorpay's own schedule, reported back via the webhook above.
      2. Demo mode: there is no real Razorpay engine to charge a
         "demo_sub_..." subscription on a schedule, so this simulates it --
         once a mandate has gone >=30 days since its last invoice (or since
         activation, if none yet), it writes a paid monthly_invoices row
         itself. This is what makes the whole enroll -> auto-charge ->
         billing-history flow demonstrable with zero Razorpay credentials,
         same as this codebase's existing demo-order conventions elsewhere.
    Every per-tenant step is wrapped so one tenant's failure can't sink the
    others -- same fail-soft posture as utils/plan_limits.py's
    get_tenant_employee_count().
    """
    try:
        conn = get_master_db()
        cur = conn.cursor(buffered=True)
        cur.execute(
            "SELECT tenant_schema, company_name, razorpay_subscription_id, quantity_synced, activated_at "
            "FROM auto_debit_mandates WHERE status='active'"
        )
        mandates = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as exc:
        app_log.error("sync_and_bill_auto_debit: failed to load mandates: %s", exc)
        return

    for tenant_schema, company_name, subscription_id, quantity_synced, activated_at in mandates:
        try:
            current_count = get_tenant_employee_count(tenant_schema)
            is_demo_sub = (subscription_id or "").startswith(_DEMO_SUBSCRIPTION_PREFIX)

            if is_demo_sub:
                _maybe_simulate_demo_charge(tenant_schema, company_name, subscription_id, current_count, activated_at)
            elif current_count != quantity_synced:
                ok, error = update_subscription_quantity(subscription_id, current_count or 1)
                if not ok:
                    app_log.warning("sync_and_bill_auto_debit: quantity sync failed for %s: %s", tenant_schema, error)
                    continue

            if current_count != quantity_synced:
                conn = get_master_db()
                cur = conn.cursor()
                cur.execute(
                    "UPDATE auto_debit_mandates SET quantity_synced=%s WHERE tenant_schema=%s",
                    (current_count, tenant_schema)
                )
                conn.commit()
                cur.close()
                conn.close()
        except Exception as exc:
            app_log.error("sync_and_bill_auto_debit: failed for tenant %s: %s", tenant_schema, exc)


def _maybe_simulate_demo_charge(tenant_schema, company_name, subscription_id, employee_count, activated_at):
    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute(
        "SELECT created_at FROM monthly_invoices WHERE tenant_schema=%s AND status='paid' "
        "ORDER BY created_at DESC LIMIT 1",
        (tenant_schema,)
    )
    row = cur.fetchone()
    last_charge = row[0] if row else activated_at
    due = (last_charge is None) or ((datetime.datetime.now() - last_charge) >= datetime.timedelta(days=30))
    if not due:
        cur.close()
        conn.close()
        return

    amount_paise = calculate_price(employee_count)
    billing_period = datetime.date.today().replace(day=1)
    cur.execute(
        "INSERT INTO monthly_invoices (tenant_schema, company_name, employee_count, amount_paise, "
        "razorpay_payment_id, razorpay_subscription_id, status, billing_period) "
        "VALUES (%s, %s, %s, %s, %s, %s, 'paid', %s)",
        (tenant_schema, company_name, employee_count, amount_paise, "demo_payment", subscription_id, billing_period)
    )
    conn.commit()
    cur.close()
    conn.close()
    app_log.info("sync_and_bill_auto_debit: simulated demo monthly charge for %s (%s employees, %s paise)",
                 tenant_schema, employee_count, amount_paise)
