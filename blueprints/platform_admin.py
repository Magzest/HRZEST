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

from database import get_master_db, get_tenant_db
from extensions import app_log, log_security_event, limiter
from utils.auth import check_password_hash
from utils.totp import send_mfa_login_email
from utils.plan_limits import PLAN_TIERS, FEATURE_LABELS

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
    try:
        conn = get_tenant_db(schema_name)
        cur = conn.cursor(buffered=True)
        cur.execute("SELECT COUNT(*) FROM employees")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
    except Exception:
        count = 0
    _employee_count_cache[schema_name] = (count, now)
    return count


@platform_admin_bp.route("/super_admin")
@_platform_admin_required
def platform_admin_dashboard():
    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute(
        "SELECT id, company_name, subdomain, db_name, plan, status, created_at "
        "FROM tenants ORDER BY created_at DESC"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    tenants = []
    for r in rows:
        tid, company_name, subdomain, db_name, plan, status, created_at = r
        limit = PLAN_TIERS.get(plan, PLAN_TIERS["starter"])["employee_limit"]
        tenants.append({
            "id": tid, "company_name": company_name, "subdomain": subdomain,
            "db_name": db_name, "plan": plan, "status": status, "created_at": created_at,
            "employee_count": _tenant_employee_count(db_name),
            "employee_limit": limit,
        })

    return render_template("super_admin_dashboard.html", tenants=tenants, plan_tiers=PLAN_TIERS,
                            feature_labels=FEATURE_LABELS)


@platform_admin_bp.route("/super_admin/tenants/<int:tenant_id>/plan", methods=["POST"])
@_platform_admin_required
def platform_admin_set_plan(tenant_id):
    plan = request.form.get("plan", "").strip()
    if plan not in PLAN_TIERS:
        flash("Choose a valid plan.", "error")
        return redirect("/super_admin")
    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute("UPDATE tenants SET plan=%s WHERE id=%s", (plan, tenant_id))
    conn.commit()
    cur.close()
    conn.close()
    log_security_event(
        "platform_admin.plan_changed", f"Tenant {tenant_id} plan changed to '{plan}'",
        level="INFO", identifier=session.get("platform_admin_username"), tenant_id=tenant_id, plan=plan,
    )
    flash("Plan updated.", "success")
    return redirect("/super_admin")


@platform_admin_bp.route("/super_admin/tenants/create", methods=["POST"])
@_platform_admin_required
def platform_admin_create_tenant():
    """Operator-initiated company creation -- the same provisioning core
    the public /create_org signup uses, so a sales-assisted or manually
    onboarded company gets an identical, fully-isolated schema rather than
    a second, softer path into tenant creation."""
    from blueprints.org import _validate_new_tenant_fields, provision_tenant, send_portal_ready_email

    company_name = request.form.get("company_name", "").strip()
    subdomain = request.form.get("subdomain", "").strip().lower()
    admin_username = request.form.get("admin_username", "").strip()
    admin_password = request.form.get("admin_password", "").strip()
    admin_email = request.form.get("admin_email", "").strip()
    plan = request.form.get("plan", "starter").strip()

    error = _validate_new_tenant_fields(company_name, subdomain, admin_username, admin_password, admin_email, plan)
    if error:
        flash(error, "error")
        return redirect("/super_admin")

    ok, error, portal_url = provision_tenant(company_name, subdomain, admin_username, admin_password, admin_email, plan)
    if not ok:
        flash(error, "error")
        return redirect("/super_admin")

    send_portal_ready_email(admin_email, company_name, admin_username, portal_url)

    log_security_event(
        "platform_admin.tenant_created",
        f"Platform admin created tenant '{company_name}' (subdomain={subdomain}, plan={plan})",
        level="INFO", identifier=session.get("platform_admin_username"), subdomain=subdomain, plan=plan,
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
