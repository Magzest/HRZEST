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
import datetime
import secrets
import functools
from flask import Blueprint, request, session, redirect, render_template, flash, jsonify, current_app

from database import get_master_db, get_db_connection
from extensions import app_log, log_security_event, limiter
from utils.auth import check_password_hash
from utils.totp import send_mfa_login_email
from utils.plan_limits import get_per_employee_paise, invalidate_rate_paise_cache, calculate_price, format_price_inr, get_tenant_employee_count
from utils.helpers import coerce_datetime, _safe_app_url
from utils.analytics import get_traffic_stats
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
    return redirect("/super_admin")


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
    """Single-page credentials + emailed-OTP MFA login -- one URL, one
    template. Which of the two steps renders is driven entirely by session
    state (platform_mfa_pending), not by a second page: submitting
    username/password here starts the OTP step in place (re-renders this
    same route); submitting otp_code here while that session state is set
    completes it via _complete_platform_admin_login."""
    if session.get("platform_admin_logged_in"):
        return redirect("/super_admin")

    if request.args.get("restart"):
        session.pop("platform_mfa_pending", None)
        session.pop("platform_mfa_user", None)
        session.pop("platform_mfa_otp_code", None)
        session.pop("platform_mfa_issued_at", None)
        return redirect("/super_admin/login")

    mfa_pending = bool(session.get("platform_mfa_pending"))
    if mfa_pending:
        issued_at = session.get("platform_mfa_issued_at") or 0
        if (time.time() - issued_at) > _MFA_OTP_TTL_SEC:
            session.clear()
            return render_template("super_admin_login.html", error="Your code expired. Please log in again.")

    if request.method == "POST" and mfa_pending and "otp_code" in request.form:
        username = session.get("platform_mfa_user")
        submitted = (request.form.get("otp_code") or "").strip()
        expected = session.get("platform_mfa_otp_code") or ""
        if username and submitted and expected and secrets.compare_digest(submitted, expected):
            return _complete_platform_admin_login(username)

        log_security_event(
            "auth.platform_admin_mfa_failure", "Invalid platform admin login MFA code",
            level="WARNING", identifier=username,
        )
        return render_template("super_admin_login.html", mfa_step=True, error="Invalid verification code.")

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
            return render_template("super_admin_login.html", mfa_step=True)

        log_security_event(
            "auth.platform_admin_login_failed",
            f"Failed platform admin login attempt for '{username}'",
            level="WARNING", identifier=username,
        )
        return render_template("super_admin_login.html", error="Invalid credentials.")

    return render_template("super_admin_login.html", mfa_step=mfa_pending)


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
    """Tenant IDs that came through the public self-service flow -- either
    the paid path (blueprints/billing.py's verify_payment, real Razorpay or
    the demo checkout) or the gated free/manual path (a tenant_applications
    row approved directly by platform_admin_approve_application()) -- rather
    than being created directly by a platform admin via
    platform_admin_create_tenant(), which never touches either table. A
    payment_orders or tenant_applications row with tenant_id set is only
    ever written by one of those two self-service paths, so its presence
    is the signal -- no separate 'source' column needed on tenants itself."""
    try:
        conn = get_master_db()
        cur = conn.cursor(buffered=True)
        cur.execute("SELECT DISTINCT tenant_id FROM payment_orders WHERE tenant_id IS NOT NULL")
        ids = {r[0] for r in cur.fetchall()}
        cur.execute("SELECT DISTINCT tenant_id FROM tenant_applications WHERE tenant_id IS NOT NULL")
        ids |= {r[0] for r in cur.fetchall()}
        cur.close()
        conn.close()
        return ids
    except Exception as exc:
        app_log.warning("platform_admin: self-signup lookup failed: %s", exc)
        return set()


def _recent_payments(limit=20):
    """Payment history across every tenant -- real and demo-mode orders
    alike (payment_orders.razorpay_order_id starts with "demo_order_" for
    the latter, same table either way per blueprints/billing.py). Also
    merges in seat_topup_orders (blueprints/seats.py) -- an existing
    tenant paying to raise its paid_employee_slots cap -- and
    monthly_invoices (blueprints/auto_debit.py) -- a tenant's recurring
    per-employee auto-debit charge, collected automatically each cycle --
    so the Platform Admin sees every payment reaching them through any of
    the three flows in one feed."""
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
        signup_payments = [
            {
                "company_name": r[0], "subdomain": r[1], "employee_count": r[2],
                "amount_display": format_price_inr(r[3]), "status": r[4],
                "is_demo": (r[5] or "").startswith("demo_order_"),
                "order_id": r[5], "payment_id": r[6], "created_at": r[7], "paid_at": r[8],
                "admin_username": r[9], "admin_email": r[10], "kind": "Signup",
            }
            for r in cur.fetchall()
        ]

        cur.execute(
            "SELECT t.company_name, t.subdomain, s.seats_purchased, s.amount_paise, s.status, "
            "s.razorpay_order_id, s.razorpay_payment_id, s.created_at, s.paid_at, s.requested_by, "
            "s.company_name AS fallback_company_name "
            "FROM seat_topup_orders s LEFT JOIN tenants t ON t.db_name = s.tenant_schema "
            "ORDER BY s.created_at DESC LIMIT %s",
            (limit,)
        )
        seat_payments = [
            {
                "company_name": r[0] or r[10], "subdomain": r[1] or "—", "employee_count": r[2],
                "amount_display": format_price_inr(r[3]), "status": r[4],
                "is_demo": (r[5] or "").startswith("demo_seat_order_"),
                "order_id": r[5], "payment_id": r[6], "created_at": r[7], "paid_at": r[8],
                "admin_username": r[9], "admin_email": "—", "kind": "Seat Top-up",
            }
            for r in cur.fetchall()
        ]
        cur.execute(
            "SELECT t.company_name, t.subdomain, m.employee_count, m.amount_paise, m.status, "
            "m.razorpay_subscription_id, m.razorpay_payment_id, m.created_at, m.company_name AS fallback_company_name "
            "FROM monthly_invoices m LEFT JOIN tenants t ON t.db_name = m.tenant_schema "
            "ORDER BY m.created_at DESC LIMIT %s",
            (limit,)
        )
        auto_debit_payments = [
            {
                "company_name": r[0] or r[8], "subdomain": r[1] or "—", "employee_count": r[2],
                "amount_display": format_price_inr(r[3]), "status": r[4],
                # Prefix-based, same convention as the signup/seat-topup
                # sources above -- checking the subscription_id (not
                # payment_id, which is a hardcoded "demo_payment" literal in
                # blueprints/auto_debit.py's _maybe_simulate_demo_charge and
                # has no structural relationship to the subscription itself).
                "is_demo": (r[5] or "").startswith("demo_sub_"),
                "order_id": r[5], "payment_id": r[6], "created_at": r[7], "paid_at": r[7],
                "admin_username": "—", "admin_email": "—", "kind": "Auto-Debit",
            }
            for r in cur.fetchall()
        ]
        cur.close()
        conn.close()

        merged = signup_payments + seat_payments + auto_debit_payments
        # coerce_datetime: created_at/paid_at come back as real datetimes
        # from Postgres but as plain strings under the local SQLite
        # fallback (see its docstring) -- sorting a mix of the two raises
        # TypeError and this whole feed goes blank (caught by the except
        # below), so every value is normalized before comparison.
        merged.sort(
            key=lambda p: coerce_datetime(p["paid_at"]) or coerce_datetime(p["created_at"]) or datetime.datetime.min,
            reverse=True,
        )
        return merged[:limit]
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
        "SELECT id, company_name, subdomain, db_name, payment_option, status, created_at, "
        "billing_state, grace_period_ends_at "
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
        (tid, company_name, subdomain, db_name, payment_option, status, created_at,
         billing_state, grace_period_ends_at) = r
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
            "billing_state": billing_state or "current",
            "grace_period_ends_at": coerce_datetime(grace_period_ends_at),
        })

    costs = _get_platform_costs()
    pnl = _compute_pnl(mrr_paise, active_employee_count, costs)

    conn2 = get_master_db()
    cur2 = conn2.cursor(buffered=True)
    cur2.execute("SELECT COUNT(*) FROM tenant_applications WHERE status='pending_review'")
    pending_applications_count = cur2.fetchone()[0]
    cur2.execute("SELECT COUNT(*) FROM tenant_duplicate_alerts WHERE acknowledged=0")
    unacknowledged_alerts_count = cur2.fetchone()[0]
    cur2.close()
    conn2.close()

    return render_template(
        "super_admin_dashboard.html", tenants=tenants,
        portal_base_url=_safe_app_url(),
        per_employee_paise=get_per_employee_paise(),
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
        pending_applications_count=pending_applications_count,
        unacknowledged_alerts_count=unacknowledged_alerts_count,
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


@platform_admin_bp.route("/super_admin/rate", methods=["POST"])
@_platform_admin_required
def platform_admin_set_rate():
    """Updates the flat per-employee monthly rate every price calculation
    in the app reads (utils/plan_limits.py's get_per_employee_paise()) --
    takes effect for new signups, seat top-ups, and manual/dunning bills on
    the very next calculation (invalidate_rate_paise_cache() below), no
    redeploy needed.

    Existing recurring auto-debit subscribers are migrated at their own
    next renewal, not immediately: a fresh Razorpay Plan is created here at
    the new rate (Plans are immutable, so the old one keeps its old price
    forever) and every currently-active mandate is flagged
    needs_rate_migration -- blueprints/auto_debit.py's
    _handle_subscription_charged() checks that flag after each successful
    charge, cancels that subscription once its current (old-rate) cycle is
    paid, and emails the tenant to re-authorize a new one. Nobody is
    charged mid-cycle or has a payment silently change amount."""
    from utils.razorpay_utils import create_plan, razorpay_configured
    from blueprints.auto_debit import _PLAN_ITEM_NAME

    raw = request.form.get("per_employee_rupees", "").strip()
    try:
        rupees = float(raw)
    except ValueError:
        flash("Enter a valid rate in rupees.", "error")
        return redirect("/super_admin")
    if rupees <= 0:
        flash("The rate must be greater than zero.", "error")
        return redirect("/super_admin")

    new_paise = round(rupees * 100)
    old_paise = get_per_employee_paise()

    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute(
        "UPDATE platform_costs SET per_employee_paise=%s, updated_at=CURRENT_TIMESTAMP WHERE id=1",
        (new_paise,)
    )

    migration_note = ""
    if razorpay_configured():
        new_plan_id, plan_error = create_plan(new_paise, _PLAN_ITEM_NAME)
        if plan_error:
            app_log.error("platform_admin.set_rate: failed to create new Razorpay plan: %s", plan_error)
            migration_note = " Warning: creating the new Razorpay plan failed, so auto-debit migration could not be armed -- existing subscribers will keep their old rate until this is retried."
        else:
            cur.execute("UPDATE billing_config SET razorpay_plan_id=%s WHERE id=1", (new_plan_id,))
            cur.execute("UPDATE auto_debit_mandates SET needs_rate_migration=TRUE WHERE status='active'")
            migrated_count = cur.rowcount
            if migrated_count:
                migration_note = f" {migrated_count} active auto-debit subscriber(s) will be migrated to the new rate at their next renewal."

    conn.commit()
    cur.close()
    conn.close()
    invalidate_rate_paise_cache()

    log_security_event(
        "platform_admin.rate_updated",
        f"Per-employee rate changed from {format_price_inr(old_paise)} to {format_price_inr(new_paise)}",
        level="WARNING", identifier=session.get("platform_admin_username"),
    )
    flash(f"Rate updated to {format_price_inr(new_paise)}/employee/month.{migration_note}", "success")
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
    from utils.auth import generate_password_hash
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

    ok, error, portal_url, checkin_url = provision_tenant(company_name, subdomain, admin_username,
                                                            generate_password_hash(admin_password),
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


# ── Gated company-signup review queue (blueprints/org.py's tenant_applications) ──
# Every applicant now goes through email OTP + KYC document upload before
# reaching this queue; provision_tenant() is only ever called from the
# approve action below (or, for paid plans, from billing.py's
# verify_payment() after the post-approval payment step completes).

_APPLICATION_DOC_KINDS = ("registration_cert", "address_proof", "visiting_card", "name_board_photo")
_APPLICATION_STATUS_COLS = (
    "id, company_name, subdomain, admin_username, admin_email, email_domain, employee_count, "
    "payment_option, logo_path, email_verified_at, doc_registration_cert, doc_address_proof, "
    "doc_visiting_card, doc_name_board_photo, documents_submitted_at, status, reviewed_by, "
    "reviewed_at, rejection_reason, tenant_id, created_at"
)
_APPLICATION_COLS = [c.strip() for c in _APPLICATION_STATUS_COLS.split(",")]


def _fetch_application(application_id):
    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute(f"SELECT {_APPLICATION_STATUS_COLS} FROM tenant_applications WHERE id=%s", (application_id,))  # nosec B608 -- _APPLICATION_STATUS_COLS is a fixed module-level constant, never built from request input
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    return dict(zip(_APPLICATION_COLS, row))


@platform_admin_bp.route("/super_admin/applications", methods=["GET"])
@_platform_admin_required
def platform_admin_applications_queue():
    status_filter = request.args.get("status", "pending_review")
    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    if status_filter == "all":
        cur.execute(f"SELECT {_APPLICATION_STATUS_COLS} FROM tenant_applications ORDER BY created_at DESC")  # nosec B608 -- fixed constant, see _fetch_application
    else:
        cur.execute(
            f"SELECT {_APPLICATION_STATUS_COLS} FROM tenant_applications WHERE status=%s ORDER BY created_at ASC",  # nosec B608
            (status_filter,)
        )
    rows = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM tenant_applications WHERE status='pending_review'")
    pending_count = cur.fetchone()[0]
    cur.close()
    conn.close()
    applications = [dict(zip(_APPLICATION_COLS, r)) for r in rows]
    return render_template(
        "super_admin_applications.html", applications=applications,
        status_filter=status_filter, pending_count=pending_count,
    )


@platform_admin_bp.route("/super_admin/applications/<int:application_id>", methods=["GET"])
@_platform_admin_required
def platform_admin_application_detail(application_id):
    application = _fetch_application(application_id)
    if not application:
        flash("Application not found.", "error")
        return redirect("/super_admin/applications")
    return render_template("super_admin_application_detail.html", application=application,
                            doc_kinds=_APPLICATION_DOC_KINDS)


@platform_admin_bp.route("/super_admin/applications/<int:application_id>/documents/<doc_kind>", methods=["GET"])
@_platform_admin_required
def platform_admin_view_document(application_id, doc_kind):
    """Streams one uploaded KYC document. This route + the
    @_platform_admin_required guard above is the ENTIRE access control for
    these files -- they're saved outside static/ (see utils/helpers.py's
    save_application_document()) specifically so there is no other way to
    reach them. doc_kind is checked against a fixed whitelist and the
    actual filesystem path/S3 ref always comes from the DB row, never from
    anything client-supplied, so this can't be tricked into serving an
    arbitrary path.

    Reads via utils/storage.py's open_private() rather than send_file(path)
    directly, since the stored ref may be a local path OR an "s3://..."
    reference (whichever save_application_document() actually used) --
    open_private() handles both transparently, this route doesn't need to
    know or care which mode is active."""
    if doc_kind not in _APPLICATION_DOC_KINDS:
        flash("Invalid document type.", "error")
        return redirect(f"/super_admin/applications/{application_id}")
    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute(f"SELECT doc_{doc_kind} FROM tenant_applications WHERE id=%s", (application_id,))  # nosec B608 -- doc_kind is allowlist-checked against _APPLICATION_DOC_KINDS above, never interpolated from an unchecked value
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row or not row[0]:
        flash("Document not found.", "error")
        return redirect(f"/super_admin/applications/{application_id}")
    import io
    import mimetypes
    from flask import send_file
    from utils.storage import open_private
    try:
        data = open_private(row[0])
    except Exception as exc:
        app_log.warning("Could not read application document %s (application_id=%s): %s", row[0], application_id, exc, exc_info=True)
        flash("Could not read this document.", "error")
        return redirect(f"/super_admin/applications/{application_id}")
    mimetype = mimetypes.guess_type(row[0])[0] or "application/octet-stream"
    return send_file(io.BytesIO(data), mimetype=mimetype, as_attachment=False)


@platform_admin_bp.route("/super_admin/applications/<int:application_id>/approve", methods=["POST"])
@_platform_admin_required
def platform_admin_approve_application(application_id):
    from blueprints.org import provision_tenant, check_duplicate_name, _record_duplicate_alert, \
        send_portal_ready_email, _GENERIC_DUPLICATE_MSG

    application = _fetch_application(application_id)
    if not application:
        flash("Application not found.", "error")
        return redirect("/super_admin/applications")
    if application["status"] != "pending_review":
        flash("This application isn't awaiting review.", "error")
        return redirect("/super_admin/applications")

    # Re-check for a name collision -- state may have shifted since this
    # application was submitted (e.g. a different applicant with the same
    # name was approved first).
    conflicting = check_duplicate_name(application["company_name"])
    if conflicting:
        _record_duplicate_alert(application_id, application["company_name"], application["admin_email"], conflicting)
        flash(_GENERIC_DUPLICATE_MSG + " (duplicate detected at approval time)", "error")
        return redirect(f"/super_admin/applications/{application_id}")

    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    reviewer = session.get("platform_admin_username")

    if application["payment_option"] == "online":
        # Payment happens AFTER approval for paid plans -- provisioning is
        # deferred until blueprints/billing.py's verify_payment() confirms
        # the charge (see create_order()'s new application_id requirement).
        cur.execute(
            "UPDATE tenant_applications SET status='approved_pending_payment', reviewed_by=%s, reviewed_at=NOW(), "
            "updated_at=NOW() WHERE id=%s",
            (reviewer, application_id)
        )
        conn.commit()
        cur.close()
        conn.close()
        from utils.email_utils import get_email_config, send_email_async
        pay_url = f"{request.url_root.rstrip('/')}/create_org/pay/{application_id}"
        email_cfg = get_email_config()
        if email_cfg:
            send_email_async(
                application["admin_email"], f"Your application was approved -- complete payment for {application['company_name']}",
                f"<p>Your company registration for <strong>{application['company_name']}</strong> has been approved.</p>"
                f"<p><a href=\"{pay_url}\">Complete payment to activate your portal</a></p>",
                email_cfg,
            )
        log_security_event("platform_admin.application_approved", f"Application {application_id} approved (awaiting payment)",
                            level="INFO", identifier=reviewer, application_id=application_id)
        flash(f"Application approved. Applicant has been emailed a payment link: {pay_url}", "success")
        return redirect("/super_admin/applications")

    cur.execute("SELECT admin_password_hash FROM tenant_applications WHERE id=%s", (application_id,))
    admin_password_hash = cur.fetchone()[0]
    cur.close()
    conn.close()

    ok, error, portal_url, checkin_url = provision_tenant(
        application["company_name"], application["subdomain"], application["admin_username"], admin_password_hash,
        application["admin_email"], payment_option=application["payment_option"],
        email_domain=application["email_domain"], employee_count=application["employee_count"],
        logo_path=application["logo_path"],
    )
    if not ok:
        flash(f"Approval failed: {error}", "error")
        return redirect(f"/super_admin/applications/{application_id}")

    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute("SELECT id FROM tenants WHERE subdomain=%s", (application["subdomain"],))
    tenant_id = cur.fetchone()[0]
    cur.execute(
        "UPDATE tenant_applications SET status='provisioned', reviewed_by=%s, reviewed_at=NOW(), tenant_id=%s, "
        "updated_at=NOW() WHERE id=%s",
        (reviewer, tenant_id, application_id)
    )
    conn.commit()
    cur.close()
    conn.close()

    send_portal_ready_email(application["admin_email"], application["company_name"], application["admin_username"],
                             portal_url, checkin_url=checkin_url)
    log_security_event("platform_admin.application_approved", f"Application {application_id} approved and provisioned",
                        level="INFO", identifier=reviewer, application_id=application_id, tenant_id=tenant_id)
    flash(f"Company '{application['company_name']}' approved and provisioned. Portal: {portal_url}", "success")
    return redirect("/super_admin/applications")


@platform_admin_bp.route("/super_admin/applications/<int:application_id>/reject", methods=["POST"])
@_platform_admin_required
def platform_admin_reject_application(application_id):
    from blueprints.org import send_application_rejected_email
    reason = request.form.get("reason", "").strip()[:1000]
    application = _fetch_application(application_id)
    if not application:
        flash("Application not found.", "error")
        return redirect("/super_admin/applications")

    reviewer = session.get("platform_admin_username")
    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute(
        "UPDATE tenant_applications SET status='rejected', reviewed_by=%s, reviewed_at=NOW(), rejection_reason=%s, "
        "updated_at=NOW() WHERE id=%s",
        (reviewer, reason, application_id)
    )
    conn.commit()
    cur.close()
    conn.close()

    send_application_rejected_email(application["admin_email"], application["company_name"], reason)
    log_security_event("platform_admin.application_rejected", f"Application {application_id} rejected",
                        level="INFO", identifier=reviewer, application_id=application_id, reason=reason)
    flash("Application rejected.", "success")
    return redirect("/super_admin/applications")


@platform_admin_bp.route("/super_admin/duplicate-alerts", methods=["GET"])
@_platform_admin_required
def platform_admin_duplicate_alerts():
    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute(
        "SELECT id, application_id, attempted_company_name, attempted_admin_email, conflicting_tenant_id, "
        "conflicting_company_name, conflicting_admin_email, match_type, acknowledged, acknowledged_by, "
        "acknowledged_at, source_ip, created_at "
        "FROM tenant_duplicate_alerts ORDER BY acknowledged ASC, created_at DESC"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    cols = ["id", "application_id", "attempted_company_name", "attempted_admin_email", "conflicting_tenant_id",
            "conflicting_company_name", "conflicting_admin_email", "match_type", "acknowledged", "acknowledged_by",
            "acknowledged_at", "source_ip", "created_at"]
    alerts = [dict(zip(cols, r)) for r in rows]
    return render_template("super_admin_duplicate_alerts.html", alerts=alerts)


@platform_admin_bp.route("/super_admin/duplicate-alerts/<int:alert_id>/acknowledge", methods=["POST"])
@_platform_admin_required
def platform_admin_acknowledge_duplicate_alert(alert_id):
    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute(
        "UPDATE tenant_duplicate_alerts SET acknowledged=1, acknowledged_by=%s, acknowledged_at=NOW() WHERE id=%s",
        (session.get("platform_admin_username"), alert_id)
    )
    conn.commit()
    cur.close()
    conn.close()
    flash("Alert acknowledged.", "success")
    return redirect("/super_admin/duplicate-alerts")


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
