"""Platform admin blueprint — cross-tenant SaaS operator panel.

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
from flask import Blueprint, request, session, redirect, render_template, flash

from database import get_master_db, get_db_connection
from extensions import app_log, log_security_event, limiter
from utils.auth import check_password_hash
from utils.totp import send_mfa_login_email
from utils.plan_limits import PER_EMPLOYEE_PAISE, calculate_price, format_price_inr, get_tenant_employee_count
from utils.analytics import get_traffic_stats

platform_admin_bp = Blueprint("platform_admin", __name__)

_MFA_OTP_TTL_SEC = 300  # 5 minutes, same window every other emailed-OTP login uses
_IDLE_TIMEOUT_SEC = 30 * 60  # 30 minutes of inactivity
# Short-TTL cache for the dashboard's per-tenant employee counts -- each
# one opens a real connection to that tenant's schema (database.py's pool
# caps at maxconn=20), so a bare page refresh shouldn't re-open N of them
# every time. Same 60s-cache idea as utils/helpers.py's _co_expired pattern.
_COUNT_CACHE_TTL_SEC = 60
_employee_count_cache = {}


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
            session.clear()
            session["platform_admin_logged_in"] = True
            session["platform_admin_username"] = username
            session["platform_admin_last_activity"] = time.time()
            # Picked up by app.py's _enforce_session_lifetime before_request
            # hook (not gated on admin_logged_in -- it checks this key on
            # every request), giving this identity the same 8-hour absolute
            # session cap as every other login flow, for free.
            session["_session_created"] = time.time()
            session.permanent = True
            log_security_event(
                "auth.platform_admin_login_success",
                f"Platform admin session established for '{username}'",
                level="INFO", identifier=username,
            )
            return redirect("/super_admin")

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

    ok, error, portal_url = provision_tenant(company_name, subdomain, admin_username, admin_password, admin_email,
                                              payment_option, email_domain=email_domain)
    if not ok:
        flash(error, "error")
        return redirect("/super_admin")

    send_portal_ready_email(admin_email, company_name, admin_username, portal_url, admin_password)

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
