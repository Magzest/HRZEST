# -*- coding: utf-8 -*-
"""Seats blueprint -- lets an existing tenant's Admin/HR buy more employee
seats once they hit company_settings.paid_employee_slots (the cap
add_employee_seat_cap_check() in utils/helpers.py enforces at employee-
registration time, in blueprints/employees.py's add_employee_page() and
api_register_employee()).

Mirrors blueprints/billing.py's Razorpay order/verify pattern used for the
public /create_org signup, but simpler: the tenant already exists here, so
there's no provisioning step -- verify_payment() just tops up this exact
tenant's own paid_employee_slots and returns. Orders are staged in the
master att_master.seat_topup_orders table (not the tenant schema) purely so
the Platform Admin can see seat-purchase history the same way they already
see signup payments via billing.py's payment_orders (see
blueprints/platform_admin.py's _recent_payments()).
"""
import secrets
import datetime
from flask import Blueprint, request, session, redirect, jsonify, render_template, flash, g

from extensions import app_log, limiter, log_security_event
from database import get_db_connection, get_master_db
from utils.auth import admin_required
from utils.helpers import tpath, get_company_settings, invalidate_settings_cache
from utils.plan_limits import calculate_price, format_price_inr, PER_EMPLOYEE_PAISE
from utils.razorpay_utils import (
    create_order as razorpay_create_order, verify_payment_signature,
    key_id as razorpay_key_id, razorpay_configured,
)

seats_bp = Blueprint("seats", __name__)

# Same convention as blueprints/billing.py's _DEMO_ORDER_PREFIX -- lets the
# full buy-seats flow be exercised locally without real Razorpay keys, and
# is refused outright by verify_payment() once real keys ARE configured.
_DEMO_ORDER_PREFIX = "demo_seat_order_"


@seats_bp.route("/settings/seats", methods=["GET"])
@admin_required
def seats_page():
    co = get_company_settings()
    try:
        db = get_db_connection()
        cur = db.cursor()
        cur.execute("SELECT COUNT(*) FROM employees")
        employee_count = cur.fetchone()[0]
        cur.close()
        db.close()
    except Exception:
        employee_count = 0

    auto_debit_status = None
    invoices = []
    try:
        conn = get_master_db()
        cur = conn.cursor(buffered=True)
        cur.execute(
            "SELECT status, quantity_synced, activated_at FROM auto_debit_mandates WHERE tenant_schema=%s",
            (g.tenant_db,)
        )
        row = cur.fetchone()
        if row:
            auto_debit_status = {"status": row[0], "quantity_synced": row[1], "activated_at": row[2]}
        cur.execute(
            "SELECT billing_period, employee_count, amount_paise, status, created_at, failure_reason "
            "FROM monthly_invoices WHERE tenant_schema=%s ORDER BY created_at DESC LIMIT 12",
            (g.tenant_db,)
        )
        invoices = [
            {"billing_period": r[0], "employee_count": r[1], "amount_display": format_price_inr(r[2]),
             "status": r[3], "created_at": r[4], "failure_reason": r[5]}
            for r in cur.fetchall()
        ]
        cur.close()
        conn.close()
    except Exception as exc:
        app_log.warning("seats_page: auto-debit lookup failed: %s", exc)

    return render_template(
        "seat_checkout.html",
        active_nav="seats",
        employee_count=employee_count,
        paid_employee_slots=co.get("paid_employee_slots"),
        per_employee_paise=PER_EMPLOYEE_PAISE,
        per_employee_display=format_price_inr(PER_EMPLOYEE_PAISE),
        monthly_bill_display=format_price_inr(calculate_price(employee_count)),
        razorpay_configured=razorpay_configured(),
        auto_debit_status=auto_debit_status,
        invoices=invoices,
    )


@seats_bp.route("/api/seats/create_order", methods=["POST"])
@admin_required
@limiter.limit("10 per minute")
def create_order():
    co = get_company_settings()
    cap = co.get("paid_employee_slots")
    if cap is None:
        return jsonify({"ok": False, "msg": "Your plan already allows unlimited employees -- no seat purchase needed."}), 400

    data = request.get_json(silent=True) or request.form
    try:
        additional_seats = int(data.get("additional_seats") or 0)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "msg": "Number of seats must be a number."}), 400
    if additional_seats < 1:
        return jsonify({"ok": False, "msg": "Enter at least 1 additional seat."}), 400
    if additional_seats > 10000:
        return jsonify({"ok": False, "msg": "That's too many seats for a single order. Contact support for a bulk upgrade."}), 400

    amount_paise = calculate_price(additional_seats)

    is_demo = not razorpay_configured()
    if is_demo:
        order_id = _DEMO_ORDER_PREFIX + secrets.token_hex(12)
    else:
        receipt_id = f"seats_{g.tenant_db}_{int(datetime.datetime.now().timestamp())}"
        order_id, error = razorpay_create_order(amount_paise, receipt_id)
        if not order_id:
            app_log.error("seats.create_order failed: %s", error)
            return jsonify({"ok": False, "msg": error}), 502

    try:
        conn = get_master_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO seat_topup_orders (tenant_schema, company_name, razorpay_order_id, "
            "seats_purchased, amount_paise, requested_by, status) VALUES (%s, %s, %s, %s, %s, %s, 'created')",
            (g.tenant_db, co.get("company_name") or "", order_id, additional_seats, amount_paise,
             session.get("admin_username"))
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as exc:
        app_log.error("seats.create_order: failed to stage seat_topup_orders row: %s", exc)
        return jsonify({"ok": False, "msg": "Could not start checkout. Please try again."}), 500

    return jsonify({
        "ok": True,
        "order_id": order_id,
        "amount_paise": amount_paise,
        "amount_display": format_price_inr(amount_paise),
        "currency": "INR",
        "key_id": razorpay_key_id(),
        "demo": is_demo,
        "additional_seats": additional_seats,
    })


@seats_bp.route("/api/seats/verify_payment", methods=["POST"])
@admin_required
@limiter.limit("20 per minute")
def verify_payment():
    data = request.get_json(silent=True) or request.form
    razorpay_order_id = (data.get("razorpay_order_id") or "").strip()
    razorpay_payment_id = (data.get("razorpay_payment_id") or "").strip()
    razorpay_signature = (data.get("razorpay_signature") or "").strip()

    is_demo_order = razorpay_order_id.startswith(_DEMO_ORDER_PREFIX)
    if is_demo_order:
        if razorpay_configured():
            return jsonify({"ok": False, "msg": "This was a demo order. Please start checkout again."}), 400
        log_security_event(
            "seats.demo_checkout_completed", "Demo/test-mode seat top-up completed (no real payment)",
            level="INFO", order_id=razorpay_order_id,
        )
    elif not verify_payment_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
        log_security_event(
            "seats.signature_invalid", "Razorpay payment signature verification failed for a seat top-up",
            level="ERROR", order_id=razorpay_order_id,
        )
        return jsonify({"ok": False, "msg": "Payment verification failed."}), 400

    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    # tenant_schema=%s scopes the lookup to THIS tenant -- an order created
    # by one company can never be redeemed against another's seat cap, even
    # if its razorpay_order_id were somehow guessed.
    cur.execute(
        "SELECT seats_purchased, status FROM seat_topup_orders WHERE razorpay_order_id=%s AND tenant_schema=%s",
        (razorpay_order_id, g.tenant_db)
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return jsonify({"ok": False, "msg": "Unknown order."}), 404

    seats_purchased, status = row
    if status == "paid":
        # Idempotent: a retried/duplicate client POST must not credit seats twice.
        cur.close()
        conn.close()
        co = get_company_settings()
        return jsonify({"ok": True, "already_paid": True, "paid_employee_slots": co.get("paid_employee_slots")})

    cur.execute(
        "UPDATE seat_topup_orders SET status='paid', razorpay_payment_id=%s, paid_at=NOW() "
        "WHERE razorpay_order_id=%s AND tenant_schema=%s",
        (razorpay_payment_id, razorpay_order_id, g.tenant_db)
    )
    conn.commit()
    cur.close()
    conn.close()

    try:
        db = get_db_connection()
        cur = db.cursor()
        cur.execute(
            "UPDATE company_settings SET paid_employee_slots = COALESCE(paid_employee_slots, 0) + %s WHERE id=1",
            (seats_purchased,)
        )
        db.commit()
        cur.close()
        db.close()
    except Exception as exc:
        app_log.error("seats.verify_payment: payment captured but failed to update paid_employee_slots for %s: %s",
                       g.tenant_db, exc)
        return jsonify({"ok": False, "msg": f"Payment received, but seat activation failed. Contact support with order ID {razorpay_order_id}."}), 500

    invalidate_settings_cache()
    co = get_company_settings()

    log_security_event(
        "seats.purchased", f"{seats_purchased} additional employee seat(s) purchased",
        level="INFO", order_id=razorpay_order_id, seats_purchased=seats_purchased,
        new_cap=co.get("paid_employee_slots"),
    )

    return jsonify({
        "ok": True,
        "seats_purchased": seats_purchased,
        "paid_employee_slots": co.get("paid_employee_slots"),
    })
