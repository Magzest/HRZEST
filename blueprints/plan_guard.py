"""
plan_guard.py — Plan-tier enforcement for the Employee Attendance Platform.

Plans:  basic   → max 30–60 employees, no MFA, no SecOps, no fingerprint
        medium  → max 70–150 employees, fingerprint + dashboard QR + daily email
        premium → unlimited employees, all features (MFA, SecOps, mobile, auth QR)

Usage:
    from blueprints.plan_guard import require_plan, check_employee_limit, get_company_plan

    @app.route("/secops")
    @require_plan("premium")
    def secops():
        ...

    # In employee creation:
    ok, msg = check_employee_limit()
    if not ok:
        flash(msg, "danger")
        return redirect(...)
"""
import functools
from flask import session, redirect, url_for, jsonify, request, flash
from database import get_db_connection
from extensions import app_log

# ── Plan definitions ────────────────────────────────────────────────────────

PLANS = {
    "basic": {
        "label": "Basic",
        "max_employees": 60,
        "features": ["face_login", "qr_login", "attendance", "leave", "payroll", "portal", "dashboard"],
    },
    "medium": {
        "label": "Medium",
        "max_employees": 150,
        "features": ["face_login", "qr_login", "fingerprint", "dashboard_qr", "daily_email", "secops",
                     "attendance", "leave", "payroll", "portal", "dashboard"],
    },
    "premium": {
        "label": "Premium",
        "max_employees": None,          # unlimited
        "features": ["face_login", "qr_login", "fingerprint", "dashboard_qr", "daily_email",
                     "mfa", "secops", "auth_qr_email", "mobile",
                     "attendance", "leave", "payroll", "portal", "dashboard"],
    },
}

PLAN_ORDER = ["basic", "medium", "premium"]


def _plan_rank(plan_name: str) -> int:
    """Return numeric rank so we can do >= comparisons."""
    try:
        return PLAN_ORDER.index(plan_name.lower())
    except (ValueError, AttributeError):
        return 0


# ── DB helpers ───────────────────────────────────────────────────────────────

def get_company_plan(username: str | None = None) -> str:
    """
    Return the plan for the currently logged-in admin (or a specific username).
    Falls back to 'basic' if unset or on any error.
    """
    try:
        user = username or session.get("username")
        if not user:
            return "basic"
        db = get_db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute("SELECT plan FROM admin_users WHERE username=%s", (user,))
        row = cursor.fetchone()
        cursor.close()
        db.close()
        if row and row[0] in PLANS:
            return row[0]
    except Exception:
        app_log.exception("plan_guard: failed to read plan from DB")
    return "basic"


def get_employee_count() -> int:
    """Return the current total number of employees in the DB."""
    try:
        db = get_db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute("SELECT COUNT(*) FROM employees")
        count = cursor.fetchone()[0]
        cursor.close()
        db.close()
        return count
    except Exception:
        app_log.exception("plan_guard: failed to count employees")
        return 0


def check_employee_limit(username: str | None = None) -> tuple[bool, str]:
    """
    Check if adding one more employee would exceed the plan cap.
    Returns (True, "") if allowed, or (False, error_message) if blocked.
    """
    plan = get_company_plan(username)
    max_emp = PLANS[plan]["max_employees"]
    if max_emp is None:
        return True, ""          # unlimited
    current = get_employee_count()
    if current >= max_emp:
        return False, (
            f"Your {PLANS[plan]['label']} plan allows a maximum of {max_emp} employees. "
            f"You currently have {current}. Please upgrade to add more employees."
        )
    return True, ""


def plan_has_feature(feature: str, username: str | None = None) -> bool:
    """Return True if the current plan includes the given feature key."""
    plan = get_company_plan(username)
    return feature in PLANS[plan]["features"]


# ── Decorator ────────────────────────────────────────────────────────────────

def require_plan(minimum_plan: str):
    """
    Decorator that blocks access if the logged-in admin's plan is below minimum_plan.

    For API routes (Accept: application/json or /api/ prefix) → returns 403 JSON.
    For page routes → redirects to /dashboard with a flash message.
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            current_plan = get_company_plan()
            if _plan_rank(current_plan) < _plan_rank(minimum_plan):
                required_label = PLANS.get(minimum_plan, {}).get("label", minimum_plan.title())
                current_label  = PLANS.get(current_plan, {}).get("label", current_plan.title())
                msg = (
                    f"This feature requires the {required_label} plan. "
                    f"You are on the {current_label} plan. Please upgrade to access this."
                )
                is_api = (
                    request.path.startswith("/api/")
                    or "application/json" in request.headers.get("Accept", "")
                )
                if is_api:
                    return jsonify({"ok": False, "msg": msg, "upgrade_required": True,
                                    "required_plan": minimum_plan}), 403
                flash(msg, "warning")
                return redirect("/pricing")
            return f(*args, **kwargs)
        return wrapped
    return decorator
