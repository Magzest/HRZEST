"""Dedicated HR Portal — separate login/credentials and a scoped dashboard
covering only employee-lifecycle modules (employees, attendance, leave,
onboarding, performance, tickets, documents). Mirrors the separation already
established for SOC analysts (see blueprints/secops.py): a distinct
admin_users role (HR_ROLE) that is explicitly blocked from completing the
regular /admin_login, gets its own login route, and lands on its own
dashboard rather than the full /admin one, which also carries payroll,
tenant/system settings, company management, and analytics."""
import re
import time
from flask import Blueprint, request, session, redirect, render_template

from utils.auth import (
    generate_password_hash, check_password_hash,
    _check_login_lockout, _record_login_failure, _clear_login_failures,
    _get_failed_count, verify_turnstile, turnstile_enabled,
    CAPTCHA_AFTER_ATTEMPTS, _TURNSTILE_SITE_KEY, HR_ROLE, role_required,
)
from utils.helpers import get_company_settings, co_scope_subquery, _db
from utils.email_utils import notify_if_new_login_ip
from utils.session_risk import ensure_session_id
from database import get_db_connection
from extensions import app, limiter, log_security_event
from blueprints.auth import _start_login_mfa

hr_bp = Blueprint("hr_portal", __name__)

# Detection only, mirrors blueprints/auth.py's _INJECTION_PATTERN_RE -- never
# a security control, every query here is parameterized already.
_INJECTION_PATTERN_RE = re.compile(
    r"('|--|;|\bunion\b|\bor\b\s+['\"0-9]|<script\b)", re.IGNORECASE
)


@hr_bp.route("/hr_login", methods=["GET", "POST"])
@limiter.limit("5 per 15 minutes")
@limiter.limit("5 per minute")
def hr_login():
    co = get_company_settings()
    if session.get("admin_logged_in") and session.get("admin_role") == HR_ROLE:
        return redirect("/hr")

    if request.method != "POST":
        return render_template("hr_login.html", co=co)

    identifier = request.form.get("identifier", "").strip()
    password = request.form.get("password", "").strip()

    _inj_match = _INJECTION_PATTERN_RE.search(identifier)
    if _inj_match:
        log_security_event(
            "auth.injection_attempt",
            "HR login identifier matched a SQL-injection/XSS-shaped pattern",
            level="ERROR", pattern=_inj_match.group(1)[:20],
        )

    locked, until = _check_login_lockout(identifier)
    if locked:
        return render_template("hr_login.html", co=co,
                               error=f"Account locked until {until} due to too many failed attempts.")

    current_failed_count = _get_failed_count(identifier)
    needs_captcha = turnstile_enabled() and current_failed_count >= CAPTCHA_AFTER_ATTEMPTS
    if needs_captcha:
        token = request.form.get("cf-turnstile-response", "")
        if not verify_turnstile(token, request.remote_addr):
            return render_template("hr_login.html", co=co,
                                   error="Please complete the verification challenge.",
                                   show_captcha=True, turnstile_site_key=_TURNSTILE_SITE_KEY)

    will_need_captcha = turnstile_enabled() and (current_failed_count + 1) >= CAPTCHA_AFTER_ATTEMPTS

    with _db() as (cursor, db):
        cursor.execute(
            "SELECT password, COALESCE(role,'admin'), email FROM admin_users WHERE username=%s",
            (identifier,)
        )
        admin_row = cursor.fetchone()

    # Role must ALREADY be 'hr' in the DB before the password is even
    # checked -- otherwise a regular admin's credentials would also work
    # here, defeating the point of this being a separate, narrowly-scoped
    # credential. Same generic error either way.
    if not (admin_row and admin_row[1] == HR_ROLE and check_password_hash(admin_row[0], password)):
        _record_login_failure(identifier)
        return render_template("hr_login.html", co=co,
                               error="Invalid credentials. Check your ID and password.",
                               show_captcha=will_need_captcha, turnstile_site_key=_TURNSTILE_SITE_KEY)

    _clear_login_failures(identifier)
    if admin_row[0] and not admin_row[0].startswith("$2"):
        with _db() as (_uc, _ud):
            _uc.execute("UPDATE admin_users SET password=%s WHERE username=%s",
                        (generate_password_hash(password), identifier))
            _ud.commit()

    if app.config.get("MANDATORY_LOGIN_MFA", True):
        return _start_login_mfa(co, "hr_login.html", "admin_users", identifier, admin_row[2], "HR Administrator")

    session.clear()
    session["admin_logged_in"] = True
    session["admin_username"] = identifier
    session["admin_role"] = HR_ROLE
    session["_session_created"] = time.time()
    session.permanent = True
    ensure_session_id(session)
    if admin_row[2]:
        notify_if_new_login_ip(identifier, "hr", request.remote_addr, identifier, admin_row[2])
    return redirect("/hr")


@hr_bp.route("/hr")
@role_required(HR_ROLE)
def hr_dashboard():
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    active_cid = session.get("active_company_id")
    _co_sub, _co_args = co_scope_subquery(active_cid)

    if active_cid:
        cursor.execute("SELECT COUNT(*) FROM employees WHERE company_id=%s", _co_args)
    else:
        cursor.execute("SELECT COUNT(*) FROM employees")
    total_employees = cursor.fetchone()[0]

    cursor.execute(f"SELECT COUNT(*) FROM leave_requests WHERE status='Pending' {_co_sub}", _co_args)  # nosec B608
    pending_leaves = cursor.fetchone()[0]

    cursor.execute(f"SELECT COUNT(*) FROM tickets WHERE status IN ('Open','In Progress') {_co_sub}", _co_args)  # nosec B608
    open_tickets = cursor.fetchone()[0]

    cursor.close()
    db.close()
    return render_template(
        "hr_dashboard.html", co=get_company_settings(), active_nav="dashboard",
        total_employees=total_employees, pending_leaves=pending_leaves,
        open_tickets=open_tickets,
    )
