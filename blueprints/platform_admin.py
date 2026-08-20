# -*- coding: utf-8 -*-
"""Platform admin blueprint -- cross-tenant SaaS operator panel.

/super_admin/* is deliberately in app.py's _resolve_tenant() skip list, so
g.tenant_db is never set here: every DB access below must go through
get_master_db() (for platform_admins/tenants) or get_tenant_db(schema)
(for one specific tenant's employee count) -- never the bare
get_db_connection(), which would silently operate on the "public" schema.

This identity is deliberately NOT admin_logged_in/admin_role (the
tenant-admin session shape) -- those flags are what app.py's tenant-
oriented before_request hooks (_enforce_admin_mfa_enrollment,
_enforce_idle_timeout) key off of, and this identity has no matching
admin_users row in any schema for them to look up. Using a separate
session key means those hooks simply no-op here, and this blueprint
enforces its own (lighter) idle timeout below.
"""
import time
import secrets
import functools
from flask import Blueprint, request, session, redirect, render_template, flash, jsonify, current_app

from database import get_master_db, get_db_connection
from extensions import app_log, log_security_event, limiter
from utils.auth import check_password_hash
from utils.totp import send_mfa_login_email
from utils.plan_limits import PER_EMPLOYEE_PAISE, calculate_price, format_price_inr, get_tenant_employee_count
from utils.analytics import get_traffic_stats
from utils.device_utils import (
    get_or_create_device_token, set_device_cookie, record_login_device,
    list_devices, rename_device, add_asset_device, delete_asset_device, revoke_device,
)
from utils import chat_utils

platform_admin_bp = Blueprint("platform_admin", __name__)

_MFA_OTP_TTL_SEC = 300  # 5 minutes, same window every other emailed-OTP login uses
_IDLE_TIMEOUT_SEC = 30 * 60  # 30 minutes of inactivity
# Short-TTL cache for the dashboard's per-tenant employee counts -- each
# one opens a real connection to that tenant's schema (database.py's pool
# caps at maxconn=20), so a bare page refresh shouldn't re-open N of them
# every time. Same 60s-cache idea as utils/helpers.py's _co_expired pattern.
_COUNT_CACHE_TTL_SEC = 60
_employee_count_cache = {}


def _complete_platform_admin_login(username):
    """Build the real session once credentials (and MFA, when required)
    have checked out -- shared by the MFA-verify completion below and the
    direct-login path taken when MANDATORY_PLATFORM_ADMIN_MFA is off."""
    session.clear()
    session["platform_admin_logged_in"] = True
    session["platform_admin_username"] = username
    session["platform_admin_last_activity"] = time.time()
    # Picked up by app.py's _enforce_session_lifetime before_request hook
    # (not gated on admin_logged_in -- it checks this key on every
    # request), giving this identity the same 8-hour absolute session cap
    # as every other login flow, for free.
    session["_session_created"] = time.time()
    session.permanent = True
    log_security_event(
        "auth.platform_admin_login_success",
        f"Platform admin session established for '{username}'",
        level="INFO", identifier=username,
    )
    dest = redirect("/super_admin")
    try:
        token, is_new = get_or_create_device_token(request)
        # No session_risk participation here (see this module's docstring
        # on why platform admin keeps its own lighter session model), so
        # last_sid stays unset -- revoke on this owner_kind is row-only,
        # not a live session kill.
        record_login_device(get_master_db, "platform_admin", username, token, None, request)
        if is_new:
            set_device_cookie(dest, token)
    except Exception as exc:
        app_log.warning("device capture failed for platform_admin '%s': %s", username, exc)
    return dest


def _platform_admin_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("platform_admin_logged_in"):
            return redirect("/super_admin/login")
        last_activity = session.get("platform_admin_last_activity", 0)
        if (time.time() - last_activity) > _IDLE_TIMEOUT_SEC:
            session.clear()
            flash("Your session expired due to inactivity. Please log in again.", "error")
            return redirect("/super_admin/login")
        session["platform_admin_last_activity"] = time.time()
        return view(*args, **kwargs)
    return wrapped


@platform_admin_bp.route("/super_admin/login", methods=["GET", "POST"])
@limiter.limit("10 per 15 minutes")
def platform_admin_login():
    if session.get("platform_admin_logged_in"):
        return redirect("/super_admin")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        row = None
        if username:
            conn = get_master_db()
            cur = conn.cursor(buffered=True)
            cur.execute("SELECT password, email FROM platform_admins WHERE username=%s", (username,))
            row = cur.fetchone()
            cur.close()
            conn.close()

        if row and check_password_hash(row[0], password):
            # Local-dev escape hatch, same convention as blueprints/auth.py's
            # MANDATORY_LOGIN_MFA -- defaults True (secure by default), only
            # off when explicitly set in .env. Password is still checked
            # above either way; this only skips the emailed-OTP step.
            if not current_app.config.get("MANDATORY_PLATFORM_ADMIN_MFA", True):
                return _complete_platform_admin_login(username)

            email = row[1]
            otp_code = f"{secrets.randbelow(900000) + 100000}"
            try:
                send_mfa_login_email(email, username, "Platform Administrator", "", otp_code)
            except Exception as exc:
                app_log.warning("Platform admin MFA email send error: %s", exc)

            session.clear()
            session["platform_mfa_pending"] = True
            session["platform_mfa_user"] = username
            session["platform_mfa_otp_code"] = otp_code
            session["platform_mfa_issued_at"] = time.time()
            return redirect("/super_admin/mfa_verify")

        log_security_event(
            "auth.platform_admin_login_failed",
            f"Failed platform admin login attempt for '{username}'",
            level="WARNING", identifier=username,
        )
        return render_template("super_admin_login.html", error="Invalid credentials.")

    return render_template("super_admin_login.html")


@platform_admin_bp.route("/super_admin/mfa_verify", methods=["GET", "POST"])
@limiter.limit("8 per 15 minutes")
def platform_admin_mfa_verify():
    username = session.get("platform_mfa_user")
    if not username or not session.get("platform_mfa_pending"):
        return redirect("/super_admin/login")

    issued_at = session.get("platform_mfa_issued_at") or 0
    if (time.time() - issued_at) > _MFA_OTP_TTL_SEC:
        session.clear()
        return render_template("super_admin_login.html", error="Your code expired. Please log in again.")

    if request.method == "POST":
        submitted = (request.form.get("otp_code") or "").strip()
        expected = session.get("platform_mfa_otp_code") or ""
        if submitted and expected and secrets.compare_digest(submitted, expected):
            return _complete_platform_admin_login(username)

        log_security_event(
            "auth.platform_admin_mfa_failure", "Invalid platform admin login MFA code",
            level="WARNING", identifier=username,
        )
        return render_template("super_admin_mfa_verify.html", error="Invalid verification code.")

    return render_template("super_admin_mfa_verify.html")


@platform_admin_bp.route("/super_admin/logout", methods=["POST"])
def platform_admin_logout():
    session.clear()
    return redirect("/super_admin/login")


def _tenant_employee_count(schema_name: str) -> int:
    now = time.time()
    cached = _employee_count_cache.get(schema_name)
    if cached and (now - cached[1]) < _COUNT_CACHE_TTL_SEC:
        return cached[0]
    count = get_tenant_employee_count(schema_name)
    _employee_count_cache[schema_name] = (count, now)
    return count


def _recent_platform_activity(limit=20):
    """Best-effort recent-activity feed for the dashboard. security_events
    rows written from within this blueprint land in whatever schema
    get_db_connection() resolves to when g.tenant_db is unset (the
    single-tenant DB_NAME fallback -- see app.py's _resolve_tenant()) since
    /super_admin/* deliberately never sets g.tenant_db; that's an existing
    property of how log_security_event()'s async writer persists events,
    not something specific to this query. Never raises -- an activity feed
    failing to load shouldn't take the whole dashboard down with it."""
    try:
        conn = get_db_connection()
        cur = conn.cursor(buffered=True)
        cur.execute(
            "SELECT event_type, level, message, identifier, created_at FROM security_events "
            "WHERE event_type LIKE 'platform_admin.%%' OR event_type LIKE 'auth.platform_admin_%%' "
            "OR event_type LIKE 'billing.%%' "
            "ORDER BY created_at DESC LIMIT %s",
            (limit,)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [
            {"event_type": r[0], "level": r[1], "message": r[2], "identifier": r[3], "created_at": r[4]}
            for r in rows
        ]
    except Exception as exc:
        app_log.warning("platform_admin: recent activity feed failed: %s", exc)
        return []


def _self_signup_tenant_ids():
    """Tenant IDs that came through the public self-service flow
    (blueprints/billing.py's verify_payment -- real Razorpay or the demo
    checkout, doesn't matter which) rather than being created directly by
    a platform admin. A payment_orders row with tenant_id set is only ever
    written by that path, so its presence is the signal -- no separate
    'source' column needed on tenants itself."""
    try:
        conn = get_master_db()
        cur = conn.cursor(buffered=True)
        cur.execute("SELECT DISTINCT tenant_id FROM payment_orders WHERE tenant_id IS NOT NULL")
        ids = {r[0] for r in cur.fetchall()}
        cur.close()
        conn.close()
        return ids
    except Exception as exc:
        app_log.warning("platform_admin: self-signup lookup failed: %s", exc)
        return set()


def _recent_payments(limit=20):
    """Payment history across every tenant -- real and demo-mode orders
    alike (payment_orders.razorpay_order_id starts with "demo_order_" for
    the latter, same table either way per blueprints/billing.py)."""
    try:
        conn = get_master_db()
        cur = conn.cursor(buffered=True)
        cur.execute(
            "SELECT company_name, subdomain, employee_count, amount_paise, status, "
            "razorpay_order_id, razorpay_payment_id, created_at, paid_at, "
            "admin_username, admin_email "
            "FROM payment_orders ORDER BY created_at DESC LIMIT %s",
            (limit,)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [
            {
                "company_name": r[0], "subdomain": r[1], "employee_count": r[2],
                "amount_display": format_price_inr(r[3]), "status": r[4],
                "is_demo": (r[5] or "").startswith("demo_order_"),
                "order_id": r[5], "payment_id": r[6], "created_at": r[7], "paid_at": r[8],
                "admin_username": r[9], "admin_email": r[10],
            }
            for r in rows
        ]
    except Exception as exc:
        app_log.warning("platform_admin: payment history lookup failed: %s", exc)
        return []


def _recent_leads(limit=20):
    """'Request info' submissions from the public landing page
    (templates/landing.html's contact form -> POST /api/leads)."""
    try:
        conn = get_master_db()
        cur = conn.cursor(buffered=True)
        cur.execute(
            "SELECT id, name, email, phone, company_name, message, status, created_at "
            "FROM leads ORDER BY created_at DESC LIMIT %s",
            (limit,)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [
            {
                "id": r[0], "name": r[1], "email": r[2], "phone": r[3], "company_name": r[4],
                "message": r[5], "status": r[6], "created_at": r[7],
            }
            for r in rows
        ]
    except Exception as exc:
        app_log.warning("platform_admin: leads lookup failed: %s", exc)
        return []


# Minimum profit margin the suggested rate targets above break-even --
# purely a "don't suggest exactly zero margin" cushion, not tied to any
# external benchmark.
_SUGGESTED_MARGIN_PCT = 15
# Suggested rates are rounded up to the nearest ₹5 (500 paise) so the
# number reads as a deliberate price point, not a raw division result.
_SUGGESTED_ROUND_TO_PAISE = 500


def _get_platform_costs():
    """Monthly operating costs the platform admin has entered (AWS
    hosting + website maintenance) -- there's no billing API wired up
    that could discover these automatically, so this is admin-entered
    and simply compared against MRR. Fails to zero costs rather than
    raising, so a DB hiccup shows "no known costs" instead of crashing
    the dashboard."""
    try:
        conn = get_master_db()
        cur = conn.cursor(buffered=True)
        cur.execute("SELECT monthly_aws_paise, monthly_maintenance_paise FROM platform_costs WHERE id=1")
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return {"aws_paise": row[0], "maintenance_paise": row[1]}
    except Exception as exc:
        app_log.warning("platform_admin: cost lookup failed: %s", exc)
    return {"aws_paise": 0, "maintenance_paise": 0}


def _compute_pnl(mrr_paise, active_employee_count, costs):
    """Revenue (MRR) vs. admin-entered costs, plus -- only when running at
    a loss and there's an active employee base to spread the suggestion
    across -- a suggested per-employee rate that would clear costs with
    _SUGGESTED_MARGIN_PCT of headroom, rounded to a clean price point."""
    total_cost_paise = costs["aws_paise"] + costs["maintenance_paise"]
    net_paise = mrr_paise - total_cost_paise
    is_loss = net_paise < 0

    suggested_rate_paise = None
    if is_loss and active_employee_count > 0:
        breakeven_rate = total_cost_paise / active_employee_count
        target_rate = breakeven_rate * (1 + _SUGGESTED_MARGIN_PCT / 100)
        suggested_rate_paise = int(
            -(-target_rate // _SUGGESTED_ROUND_TO_PAISE) * _SUGGESTED_ROUND_TO_PAISE  # ceil to nearest ₹5
        )

    # Bar-fill percentages for the two-sided revenue/cost visualization --
    # whichever side is larger anchors at 100%, the other scales relative
    # to it, so the bar always shows the true ratio regardless of scale.
    larger = max(mrr_paise, total_cost_paise, 1)
    return {
        "revenue_paise": mrr_paise,
        "cost_paise": total_cost_paise,
        "net_paise": net_paise,
        "revenue_display": format_price_inr(mrr_paise),
        "cost_display": format_price_inr(total_cost_paise),
        "net_display": format_price_inr(abs(net_paise)),
        "is_loss": is_loss,
        "revenue_pct": round(mrr_paise / larger * 100),
        "cost_pct": round(total_cost_paise / larger * 100),
        "suggested_rate_paise": suggested_rate_paise,
        "suggested_rate_display": format_price_inr(suggested_rate_paise) if suggested_rate_paise else None,
        "suggested_margin_pct": _SUGGESTED_MARGIN_PCT,
    }


@platform_admin_bp.route("/super_admin")
@_platform_admin_required
def platform_admin_dashboard():
    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute(
        "SELECT id, company_name, subdomain, db_name, payment_option, status, created_at "
        "FROM tenants ORDER BY created_at DESC"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    self_signup_ids = _self_signup_tenant_ids()
    tenants = []
    mrr_paise = 0
    active_employee_count = 0
    for r in rows:
        tid, company_name, subdomain, db_name, payment_option, status, created_at = r
        employee_count = _tenant_employee_count(db_name)
        monthly_bill_paise = calculate_price(employee_count)
        if status == "active":
            mrr_paise += monthly_bill_paise
            active_employee_count += employee_count
        tenants.append({
            "id": tid, "company_name": company_name, "subdomain": subdomain,
            "db_name": db_name, "payment_option": payment_option or "online",
            "status": status, "created_at": created_at,
            "employee_count": employee_count,
            "monthly_bill_display": format_price_inr(monthly_bill_paise),
            "self_signup": tid in self_signup_ids,
        })

    costs = _get_platform_costs()
    pnl = _compute_pnl(mrr_paise, active_employee_count, costs)

    return render_template(
        "super_admin_dashboard.html", tenants=tenants,
        per_employee_paise=PER_EMPLOYEE_PAISE,
        mrr_display=format_price_inr(mrr_paise),
        active_tenant_count=sum(1 for t in tenants if t["status"] == "active"),
        total_employee_count=sum(t["employee_count"] for t in tenants),
        self_signup_count=sum(1 for t in tenants if t["self_signup"]),
        recent_activity=_recent_platform_activity(),
        recent_payments=_recent_payments(),
        leads=_recent_leads(),
        traffic=get_traffic_stats(),
        pnl=pnl,
        costs=costs,
    )


@platform_admin_bp.route("/super_admin/costs", methods=["POST"])
@_platform_admin_required
def platform_admin_set_costs():
    """Lets the platform admin update the monthly AWS/maintenance cost
    inputs that _compute_pnl() compares MRR against."""
    def _rupees_to_paise(field):
        raw = request.form.get(field, "0").strip()
        try:
            value = float(raw)
        except ValueError:
            return None
        if value < 0:
            return None
        return round(value * 100)

    aws_paise = _rupees_to_paise("monthly_aws")
    maintenance_paise = _rupees_to_paise("monthly_maintenance")
    if aws_paise is None or maintenance_paise is None:
        flash("Enter valid non-negative amounts for both cost fields.", "error")
        return redirect("/super_admin")

    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute(
        "UPDATE platform_costs SET monthly_aws_paise=%s, monthly_maintenance_paise=%s, "
        "updated_at=CURRENT_TIMESTAMP WHERE id=1",
        (aws_paise, maintenance_paise)
    )
    conn.commit()
    cur.close()
    conn.close()

    log_security_event(
        "platform_admin.costs_updated",
        f"Operating costs updated (aws={format_price_inr(aws_paise)}, "
        f"maintenance={format_price_inr(maintenance_paise)})",
        level="INFO", identifier=session.get("platform_admin_username"),
    )
    flash("Operating costs updated.", "success")
    return redirect("/super_admin")


@platform_admin_bp.route("/super_admin/leads/<int:lead_id>/status", methods=["POST"])
@_platform_admin_required
def platform_admin_set_lead_status(lead_id):
    status = request.form.get("status", "").strip()
    if status not in ("new", "contacted", "converted"):
        flash("Invalid lead status.", "error")
        return redirect("/super_admin")
    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute("UPDATE leads SET status=%s WHERE id=%s", (status, lead_id))
    conn.commit()
    cur.close()
    conn.close()
    flash("Lead updated.", "success")
    return redirect("/super_admin")


@platform_admin_bp.route("/super_admin/tenants/create", methods=["POST"])
@_platform_admin_required
def platform_admin_create_tenant():
    """Operator-initiated company creation -- the same provisioning core
    the public /create_org signup uses, so a sales-assisted or manually
    onboarded company gets an identical, fully-isolated schema rather than
    a second, softer path into tenant creation."""
    from blueprints.org import _validate_new_tenant_fields, provision_tenant, send_portal_ready_email
    from utils.helpers import clean_email_domain

    company_name = request.form.get("company_name", "").strip()
    subdomain = request.form.get("subdomain", "").strip().lower()
    admin_username = request.form.get("admin_username", "").strip()
    admin_password = request.form.get("admin_password", "").strip()
    admin_email = request.form.get("admin_email", "").strip()
    payment_option = request.form.get("payment_option", "manual").strip()
    email_domain = clean_email_domain(request.form.get("email_domain", ""))

    error = _validate_new_tenant_fields(company_name, subdomain, admin_username, admin_password, admin_email,
                                         email_domain)
    if error:
        flash(error, "error")
        return redirect("/super_admin")

    logo_path = None
    logo_file = request.files.get("logo")
    if logo_file and logo_file.filename:
        from utils.helpers import save_uploaded_logo
        logo_path, logo_err = save_uploaded_logo(logo_file, subdomain)
        if logo_err:
            flash(f"Company logo: {logo_err}", "error")
            return redirect("/super_admin")

    ok, error, portal_url, checkin_url = provision_tenant(company_name, subdomain, admin_username, admin_password,
                                                            admin_email, payment_option, email_domain=email_domain,
                                                            logo_path=logo_path)
    if not ok:
        flash(error, "error")
        return redirect("/super_admin")

    send_portal_ready_email(admin_email, company_name, admin_username, portal_url, admin_password,
                             checkin_url=checkin_url)

    log_security_event(
        "platform_admin.tenant_created",
        f"Platform admin created tenant '{company_name}' (subdomain={subdomain}, "
        f"payment_option={payment_option})",
        level="INFO", identifier=session.get("platform_admin_username"), subdomain=subdomain,
    )
    flash(f"Company '{company_name}' created. Portal: {portal_url}", "success")
    return redirect("/super_admin")


@platform_admin_bp.route("/super_admin/tenants/<int:tenant_id>/status", methods=["POST"])
@_platform_admin_required
def platform_admin_set_status(tenant_id):
    status = request.form.get("status", "").strip()
    if status not in ("active", "suspended"):
        flash("Invalid status.", "error")
        return redirect("/super_admin")
    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute("UPDATE tenants SET status=%s WHERE id=%s", (status, tenant_id))
    conn.commit()
    cur.close()
    conn.close()
    log_security_event(
        "platform_admin.status_changed", f"Tenant {tenant_id} status changed to '{status}'",
        level="WARNING" if status == "suspended" else "INFO",
        identifier=session.get("platform_admin_username"), tenant_id=tenant_id, status=status,
    )
    flash("Status updated.", "success")
    return redirect("/super_admin")


# ── Self-service device management (utils/device_utils.py) ─────────────────
# Platform admin's own rows live in att_master's user_devices, not any
# tenant schema -- get_master_db throughout, never get_db_connection.

@platform_admin_bp.route("/super_admin/devices", methods=["GET"])
@_platform_admin_required
def platform_admin_devices():
    username = session["platform_admin_username"]
    token, _ = get_or_create_device_token(request)
    return jsonify({"ok": True, "devices": list_devices(get_master_db, "platform_admin", username, token)})


@platform_admin_bp.route("/super_admin/devices/<int:device_id>/rename", methods=["POST"])
@_platform_admin_required
def platform_admin_device_rename(device_id):
    username = session["platform_admin_username"]
    data = request.get_json(silent=True) or {}
    ok = rename_device(get_master_db, "platform_admin", username, device_id, data.get("name"))
    return jsonify({"ok": ok})


@platform_admin_bp.route("/super_admin/devices/<int:device_id>/revoke", methods=["POST"])
@_platform_admin_required
def platform_admin_device_revoke(device_id):
    username = session["platform_admin_username"]
    ok = revoke_device(get_master_db, "platform_admin", username, device_id, username)
    if ok:
        log_security_event(
            "platform_admin.device_revoked", f"Device {device_id} revoked by '{username}'",
            level="INFO", identifier=username,
        )
    return jsonify({"ok": ok})


@platform_admin_bp.route("/super_admin/devices/asset", methods=["POST"])
@_platform_admin_required
def platform_admin_device_add_asset():
    username = session["platform_admin_username"]
    data = request.get_json(silent=True) or {}
    new_id = add_asset_device(get_master_db, "platform_admin", username,
                               data.get("device_name"), data.get("asset_model"), data.get("asset_serial"))
    return jsonify({"ok": new_id is not None, "id": new_id})


@platform_admin_bp.route("/super_admin/devices/asset/<int:device_id>/delete", methods=["POST"])
@_platform_admin_required
def platform_admin_device_delete_asset(device_id):
    username = session["platform_admin_username"]
    ok = delete_asset_device(get_master_db, "platform_admin", username, device_id)
    return jsonify({"ok": ok})


# ── Internal chat with a company's admin/HR (utils/chat_utils.py) ──────────
# One shared thread per tenant, keyed by that tenant's db_name -- resolved
# fresh from tenant_id on every call rather than trusted from the client, so
# a platform admin can never read/write a thread for a tenant_id that
# doesn't actually exist.

def _tenant_schema_for_id(tenant_id):
    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute("SELECT db_name, company_name FROM tenants WHERE id=%s", (tenant_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


@platform_admin_bp.route("/super_admin/chat/<int:tenant_id>/messages", methods=["GET"])
@_platform_admin_required
def platform_admin_chat_messages(tenant_id):
    row = _tenant_schema_for_id(tenant_id)
    if not row:
        return jsonify({"ok": False, "msg": "Unknown company."}), 404
    schema_name, company_name = row
    chat_utils.mark_read(schema_name, "platform")
    return jsonify({"ok": True, "company_name": company_name, "messages": chat_utils.list_messages(schema_name)})


@platform_admin_bp.route("/super_admin/chat/<int:tenant_id>/send", methods=["POST"])
@_platform_admin_required
def platform_admin_chat_send(tenant_id):
    row = _tenant_schema_for_id(tenant_id)
    if not row:
        return jsonify({"ok": False, "msg": "Unknown company."}), 404
    schema_name, _company_name = row
    data = request.get_json(silent=True) or {}
    username = session["platform_admin_username"]
    sent = chat_utils.send_message(schema_name, "platform_admin", username, data.get("message"))
    if not sent:
        return jsonify({"ok": False, "msg": "Message cannot be empty."}), 400
    return jsonify({"ok": True})
