"""Admin views blueprint — dashboard, settings, companies, analytics, audit.

Bandit B608 audit note (applies to every nosec-marked line in this file):
Bandit flags f-string-built SQL as possible injection. Verified false
positive in every case here — the interpolated fragment is always one of:
  (a) a hardcoded literal string chosen by a bool (the `_co_sub`/`_co_join`/
      `_co_filter`/`where` pattern, e.g. `"AND company_id=%s" if active_cid
      else ""`) — never user input;
  (b) a column name from a fixed allowlist dict (`column`/`cs_col`, checked
      against `_TOGGLE_COLUMN_MAP`/`_CS_COL_MAP` before use); or
  (c) a table name iterating a hardcoded Python list literal (`tbl` in
      `related_tables`).
All actual values are always passed as %s-bound params, never interpolated.
"""
import os
import re
import json
import secrets
import datetime
import calendar
from flask import (
    Blueprint, request, session, redirect, jsonify, render_template, flash, abort,
)

from database import get_db_connection, pool_stats, transaction
from extensions import app, app_log, log_security_event, limiter
from utils.auth import (
    admin_required, require_email_2fa, EMAIL_2FA_WINDOW_SEC,
    email_settings_step_up_refresh, email_settings_step_up_clear,
    SOC_ANALYST_ROLE,
    soc_step_up_valid, soc_step_up_refresh, soc_step_up_clear,
    SECURITY_SETTINGS_2FA_WINDOW_SEC, require_security_settings_2fa,
    security_settings_step_up_refresh, security_settings_step_up_clear,
    turnstile_enabled, check_password_hash,
)
from utils.helpers import (
    get_company_settings, get_co_features, _upsert_co_feature,
    _upsert_co_features, _safe_redirect, co_scope_subquery, co_scope_column,
    _create_notification, encrypt_pii, decrypt_pii, invalidate_companies_cache,
    _validate_image_file,
)
from utils.email_utils import get_email_config, send_email_smtp
from utils.totp import (
    get_or_create_admin_totp_secret, mark_totp_enabled, verify_totp_code, totp_qr_data_uri,
    reset_admin_totp_secret,
)
from utils.attendance_utils import _td_to_time
from utils.perf_metrics import snapshot as get_perf_snapshot
import utils.config as cfg

admin_views_bp = Blueprint("admin_views", __name__)

_TOGGLE_COLUMN_MAP = {
    "fingerprint": "fingerprint_enabled",
    "qr": "qr_enabled",
    "face": "face_enabled",
    "location": "location_enabled",
    "password": "employee_password_auth",
}
_TOGGLE_LABEL_MAP = {
    "fingerprint": "Fingerprint / Biometric",
    "qr": "QR Code",
    "face": "Face Recognition",
    "location": "Location Verification",
    "password": "Password Login",
}


@admin_views_bp.route("/admin")
@admin_required
def admin():
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    today = datetime.date.today()
    active_cid = session.get("active_company_id")
    _co_filter, _co_args = co_scope_column(active_cid, alias="e")
    _co_sub, _ = co_scope_subquery(active_cid)

    if active_cid:
        cursor.execute("SELECT COUNT(*) FROM employees WHERE company_id=%s", _co_args)
    else:
        cursor.execute("SELECT COUNT(*) FROM employees")
    total = cursor.fetchone()[0]

    cursor.execute(
        f"SELECT COUNT(DISTINCT employee_id) FROM attendance WHERE date=%s AND login_time IS NOT NULL {_co_sub}",  # nosec B608
        (today,) + _co_args
    )
    present = cursor.fetchone()[0]

    cursor.execute(
        f"SELECT COUNT(DISTINCT employee_id) FROM attendance WHERE date=%s AND status='Late Login' {_co_sub}",  # nosec B608
        (today,) + _co_args
    )
    late = cursor.fetchone()[0]

    cursor.execute(
        f"SELECT e.employee_id, e.name, a.login_time, a.logout_time, a.status, "  # nosec B608
        f"       a.logout_status, a.attendance_type, e.role "
        f"FROM employees e "
        f"LEFT JOIN attendance a ON e.employee_id=a.employee_id AND a.date=%s "
        f"WHERE 1=1 {_co_filter} ORDER BY e.name",
        (today,) + _co_args
    )
    today_rows = cursor.fetchall()

    if active_cid:
        cursor.execute("SELECT employee_id, name FROM employees WHERE company_id=%s ORDER BY name", _co_args)
    else:
        cursor.execute("SELECT employee_id, name FROM employees ORDER BY name")
    all_employees = cursor.fetchall()

    cursor.execute(
        f"SELECT COUNT(*) FROM leave_requests WHERE status='Pending' {_co_sub}",  # nosec B608
        _co_args
    )
    pending_leaves = cursor.fetchone()[0]

    cursor.execute(
        f"SELECT COUNT(*) FROM resignation_requests WHERE status='Pending' {_co_sub}",  # nosec B608
        _co_args
    )
    pending_resignations = cursor.fetchone()[0]

    cursor.execute(
        f"SELECT COUNT(*) FROM tickets WHERE status IN ('Open','In Progress') {_co_sub}",  # nosec B608
        _co_args
    )
    pending_tickets = cursor.fetchone()[0]

    try:
        cursor.execute("SELECT COUNT(*) FROM overtime_records WHERE status='Pending'")
        pending_ot = cursor.fetchone()[0]
    except Exception:
        pending_ot = 0

    cursor.execute("SELECT id, name, COALESCE(code,'') FROM companies ORDER BY name")
    companies_list = cursor.fetchall()

    # Onboarding summary for dashboard widget
    try:
        cursor.execute("""
            SELECT
              SUM(CASE WHEN status != 'Completed' THEN 1 ELSE 0 END),
              SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END),
              SUM(CASE WHEN status != 'Completed' AND due_date < %s THEN 1 ELSE 0 END)
            FROM employee_onboarding
        """, (today,))
        _ob = cursor.fetchone()
        ob_active = int(_ob[0] or 0)
        ob_completed = int(_ob[1] or 0)
        ob_overdue = int(_ob[2] or 0)
        cursor.execute("""
            SELECT eo.id, e.name, ot.name, eo.due_date
            FROM employee_onboarding eo
            JOIN employees e ON eo.employee_id = e.employee_id
            JOIN onboarding_templates ot ON eo.template_id = ot.id
            WHERE eo.status != 'Completed' AND eo.due_date < %s
            ORDER BY eo.due_date LIMIT 5
        """, (today,))
        ob_overdue_list = cursor.fetchall()
    except Exception:
        ob_active = ob_completed = ob_overdue = 0
        ob_overdue_list = []

    cursor.execute("SELECT id, break_name, break_time, duration_minutes, is_active FROM break_config ORDER BY break_time")
    break_rows = cursor.fetchall()
    breaks_display = []
    for b in break_rows:
        bt = b[2]
        if hasattr(bt, 'seconds'):
            h, m = divmod(bt.seconds // 60, 60)
        else:
            h, m = bt.hour, bt.minute
        ampm = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        breaks_display.append({
            "id": b[0], "name": b[1],
            "time_str": "%02d:%02d %s" % (h12, m, ampm),
            "duration": b[3], "is_active": b[4]
        })

    cursor.close()
    db.close()

    return render_template("admin.html",
                           total=total,
                           present=present,
                           absent=total - present,
                           late=late,
                           today=today.strftime("%d %b %Y"),
                           active_nav="dashboard",
                           today_rows=today_rows,
                           all_employees=all_employees,
                           shift_start=cfg.SHIFT_START.strftime("%I:%M %p"),
                           shift_end=cfg.SHIFT_END.strftime("%I:%M %p"),
                           pending_leaves=pending_leaves,
                           pending_resignations=pending_resignations,
                           pending_ot=pending_ot,
                           pending_tickets=pending_tickets,
                           now_month=today.month,
                           now_year=today.year,
                           breaks_display=breaks_display,
                           companies_list=companies_list,
                           ob_active=ob_active,
                           ob_completed=ob_completed,
                           ob_overdue=ob_overdue,
                           ob_overdue_list=ob_overdue_list,
                           )


@admin_views_bp.route("/api/admin/search")
@admin_required
def api_admin_search():
    """Omnisearch across employees, tickets and leave requests for the
    admin dashboard's search bar. Static admin-page matches (Settings,
    Analytics, ...) are matched client-side — no DB query needed for those."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"ok": True, "results": []})
    like = f"%{q}%"
    active_cid = session.get("active_company_id")
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    results = []

    _co_filter, _co_args = co_scope_column(active_cid, alias="e")
    cursor.execute(
        f"SELECT e.employee_id, e.name, e.email, e.role FROM employees e "  # nosec B608
        f"WHERE (e.name ILIKE %s OR e.employee_id ILIKE %s OR e.email ILIKE %s OR e.phone ILIKE %s) {_co_filter} "
        f"ORDER BY e.name LIMIT 8",
        (like, like, like, like) + _co_args
    )
    for eid, name, email, role in cursor.fetchall():
        results.append({
            "type": "employee", "icon": "user",
            "label": name, "sub": eid + (f" · {role}" if role else ""),
            "url": f"/employees?hl={eid}",
        })

    _tk_sub, _tk_args = co_scope_subquery(active_cid, alias="t")
    cursor.execute(
        f"SELECT t.id, t.subject, t.status, e.name FROM tickets t "  # nosec B608
        f"JOIN employees e ON t.employee_id=e.employee_id "
        f"WHERE (t.subject ILIKE %s OR t.category ILIKE %s OR e.name ILIKE %s) {_tk_sub} "
        f"ORDER BY t.created_at DESC LIMIT 6",
        (like, like, like) + _tk_args
    )
    for tid, subject, status, emp_name in cursor.fetchall():
        results.append({
            "type": "ticket", "icon": "ticket",
            "label": subject, "sub": f"{emp_name} · {status}",
            "url": "/tickets",
        })

    _lv_sub, _lv_args = co_scope_subquery(active_cid, alias="lr")
    cursor.execute(
        f"SELECT lr.id, lr.leave_date, lr.status, e.name FROM leave_requests lr "  # nosec B608
        f"JOIN employees e ON lr.employee_id=e.employee_id "
        f"WHERE (e.name ILIKE %s OR lr.reason ILIKE %s) {_lv_sub} "
        f"ORDER BY lr.created_at DESC LIMIT 6",
        (like, like) + _lv_args
    )
    for lid, leave_date, status, emp_name in cursor.fetchall():
        results.append({
            "type": "leave", "icon": "calendar-event",
            "label": f"{emp_name} — {leave_date}", "sub": status,
            "url": "/leave_holidays",
        })

    cursor.close()
    db.close()
    return jsonify({"ok": True, "results": results})


@admin_views_bp.route("/api/dashboard_live")
@admin_required
def dashboard_live():
    def fmt(t):
        if t is None:
            return None
        if hasattr(t, "strftime"):
            return t.strftime("%H:%M:%S")
        total = int(t.total_seconds())
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    today = datetime.date.today()
    active_cid = session.get("active_company_id")
    _co_filter, _co_args = co_scope_column(active_cid, alias="e")
    _co_sub, _ = co_scope_subquery(active_cid)

    if active_cid:
        cursor.execute("SELECT COUNT(*) FROM employees WHERE company_id=%s", _co_args)
    else:
        cursor.execute("SELECT COUNT(*) FROM employees")
    total = cursor.fetchone()[0]

    cursor.execute(
        f"SELECT COUNT(DISTINCT employee_id) FROM attendance WHERE date=%s AND login_time IS NOT NULL {_co_sub}",  # nosec B608
        (today,) + _co_args
    )
    present = cursor.fetchone()[0]

    cursor.execute(
        f"SELECT COUNT(DISTINCT employee_id) FROM attendance WHERE date=%s AND status='Late Login' {_co_sub}",  # nosec B608
        (today,) + _co_args
    )
    late = cursor.fetchone()[0]

    cursor.execute(
        f"SELECT e.employee_id, e.name, a.login_time, a.logout_time, "  # nosec B608
        f"       a.status, a.logout_status, a.attendance_type, e.role "
        f"FROM employees e "
        f"LEFT JOIN attendance a ON e.employee_id=a.employee_id AND a.date=%s "
        f"WHERE 1=1 {_co_filter} ORDER BY e.name",
        (today,) + _co_args
    )
    rows = []
    for emp_id, name, login_t, logout_t, status, logout_s, att_type, role in cursor.fetchall():
        rows.append({
            "emp_id": emp_id,
            "name": name,
            "role": role or "",
            "login_t": fmt(login_t),
            "logout_t": fmt(logout_t),
            "status": status or "",
            "logout_s": logout_s or "",
            "att_type": att_type or "",
        })

    cursor.execute(f"SELECT COUNT(*) FROM leave_requests WHERE status='Pending' {_co_sub}", _co_args)  # nosec B608
    pending_leaves = cursor.fetchone()[0]

    cursor.execute(f"SELECT COUNT(*) FROM resignation_requests WHERE status='Pending' {_co_sub}", _co_args)  # nosec B608
    pending_resignations = cursor.fetchone()[0]

    cursor.execute(f"SELECT COUNT(*) FROM tickets WHERE status IN ('Open','In Progress') {_co_sub}", _co_args)  # nosec B608
    pending_tickets = cursor.fetchone()[0]

    cursor.close()
    db.close()

    return jsonify({
        "total": total,
        "present": present,
        "absent": total - present,
        "late": late,
        "rows": rows,
        "pending_leaves": pending_leaves,
        "pending_resignations": pending_resignations,
        "pending_tickets": pending_tickets,
    })


@admin_views_bp.route("/api/attendance_chart_data")
@admin_required
def attendance_chart_data():
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    today = datetime.date.today()

    active_cid = session.get("active_company_id")
    _co_filter, _co_args = co_scope_column(active_cid, alias="e")
    _co_sub, _ = co_scope_subquery(active_cid, alias="a")

    # Last 30 days: present count per day
    cursor.execute(f"""
        SELECT a.date, COUNT(DISTINCT a.employee_id)
        FROM attendance a
        WHERE a.date >= %s AND a.date <= %s AND a.login_time IS NOT NULL {_co_sub}
        GROUP BY a.date ORDER BY a.date
    """, (today - datetime.timedelta(days=29), today) + _co_args)  # nosec B608
    present_by_day = {str(r[0]): r[1] for r in cursor.fetchall()}

    if active_cid:
        cursor.execute("SELECT COUNT(*) FROM employees WHERE company_id=%s", _co_args)
    else:
        cursor.execute("SELECT COUNT(*) FROM employees")
    total = cursor.fetchone()[0]

    trend_labels, trend_present, trend_absent = [], [], []
    for i in range(29, -1, -1):
        d = today - datetime.timedelta(days=i)
        key = str(d)
        p = present_by_day.get(key, 0)
        trend_labels.append(d.strftime("%d %b"))
        trend_present.append(p)
        trend_absent.append(max(total - p, 0))

    # Today by department
    cursor.execute(f"""
        SELECT COALESCE(e.department, 'Unassigned'),
               COUNT(DISTINCT CASE WHEN a.login_time IS NOT NULL THEN e.employee_id END),
               COUNT(DISTINCT e.employee_id)
        FROM employees e
        LEFT JOIN attendance a ON e.employee_id=a.employee_id AND a.date=%s
        WHERE 1=1 {_co_filter}
        GROUP BY COALESCE(e.department, 'Unassigned')
        ORDER BY COALESCE(e.department, 'Unassigned')
    """, (today,) + _co_args)  # nosec B608
    dept_labels, dept_present, dept_absent = [], [], []
    for dept, p, tot in cursor.fetchall():
        dept_labels.append(dept)
        dept_present.append(p or 0)
        dept_absent.append(max((tot or 0) - (p or 0), 0))

    cursor.close()
    db.close()
    return jsonify({
        "trend": {"labels": trend_labels, "present": trend_present, "absent": trend_absent},
        "dept": {"labels": dept_labels, "present": dept_present, "absent": dept_absent},
    })


@admin_views_bp.route("/admin/mfa-required")
@admin_required
def admin_mfa_required_page():
    """Forced-enrollment landing page: app.py's _enforce_admin_mfa_enrollment
    before_request hook redirects every admin/manager/soc_analyst session
    without TOTP enrolled here, and here only, until they complete it. Not
    @require_security_settings_2fa or similar — an unenrolled admin can't
    pass a TOTP step-up gate they haven't set up yet, so this page (and the
    /api/settings/2fa/setup + /api/settings/2fa/enable it calls) is
    deliberately reachable on @admin_required alone."""
    return render_template("admin_mfa_required.html")


@admin_views_bp.route("/security")
@admin_required
def security_hub_page():
    """Standalone page, not a Settings tab — a first-class sidebar entry
    like Employees or Analytics, matching how the SOC dashboard already has
    its own dedicated page rather than living inside Settings. Renders no
    sensitive data server-side; everything below the gate is fetched by
    templates/security_hub.html's own JS after /api/settings/security/
    verify-2fa succeeds (those API routes are unchanged — only where the
    HTML shell lives has moved)."""
    return render_template("security_hub.html")


@admin_views_bp.route("/settings")
@admin_required
def settings_page():
    tab = request.args.get("tab", "company")
    db = get_db_connection()
    cursor = db.cursor(buffered=True)

    # Email config: intentionally NOT fetched here. The Email Settings tab
    # sits behind a 2FA step-up gate (utils/auth.py:require_email_2fa) and is
    # loaded client-side via /api/settings/email only after verification —
    # never server-rendered, so the password (and the rest of the SMTP
    # config) can't leak into the page's initial HTML before the admin
    # proves identity. See templates/settings.html's #email-2fa-gate.

    # Shifts (with company)
    cursor.execute("""
        SELECT s.id, s.name, s.start_time, s.half_time, s.end_time,
               COALESCE(s.company_id, 0), COALESCE(c.name, '')
        FROM shifts s
        LEFT JOIN companies c ON c.id = s.company_id
        ORDER BY c.name, s.start_time
    """)
    shift_rows = []
    for sid, sname, st, ht, et, scid, scname in cursor.fetchall():
        shift_rows.append({
            "id": sid, "name": sname,
            "start": _td_to_time(st).strftime("%H:%M") if st else "--",
            "half": _td_to_time(ht).strftime("%H:%M") if ht else "--",
            "end": _td_to_time(et).strftime("%H:%M") if et else "--",
            "company_id": scid, "company_name": scname,
        })
    cursor.execute(
        "SELECT e.employee_id, e.name, e.role, s.name FROM employees e LEFT JOIN shifts s ON e.shift_id = s.id ORDER BY e.name")
    emp_list = [{"emp_id": r[0], "name": r[1], "role": r[2] or "", "shift": r[3] or "Default"}
                for r in cursor.fetchall()]

    # Company-specific shifts (company_id IS NOT NULL)
    cursor.execute(
        "SELECT id, name, start_time, half_time, end_time, company_id FROM shifts WHERE company_id IS NOT NULL ORDER BY company_id, start_time")
    _co_shifts_raw = cursor.fetchall()
    company_shifts = {}
    for _csid, _csname, _csstart, _cshalf, _csend, _cscid in _co_shifts_raw:
        def _tdfmt(v):
            if v is None:
                return "--"
            if isinstance(v, datetime.timedelta):
                _s = int(v.total_seconds())
                return "%02d:%02d" % (_s // 3600, (_s % 3600) // 60)
            if isinstance(v, datetime.time):
                return v.strftime("%H:%M")
            return str(v)[:5]
        company_shifts.setdefault(_cscid, []).append(
            (_csid, _csname, _tdfmt(_csstart), _tdfmt(_cshalf), _tdfmt(_csend)))

    # Company-specific breaks (company_id IS NOT NULL), nested per shift
    cursor.execute("SELECT id, break_name, break_time, duration_minutes, is_active, company_id, COALESCE(shift_id,0) FROM break_config WHERE company_id IS NOT NULL ORDER BY company_id, shift_id, break_time")
    _co_breaks_raw = cursor.fetchall()
    company_breaks = {}
    for _cbid, _cbname, _cbt, _cbdur, _cbactive, _cbcid, _cbsid in _co_breaks_raw:
        if _cbt is None:
            _cbt_str = "--"
        elif isinstance(_cbt, datetime.timedelta):
            _s = int(_cbt.total_seconds())
            _cbt_str = "%02d:%02d" % (_s // 3600, (_s % 3600) // 60)
        elif isinstance(_cbt, datetime.time):
            _cbt_str = _cbt.strftime("%H:%M")
        else:
            _cbt_str = str(_cbt)[:5]
        company_breaks.setdefault(_cbcid, {}).setdefault(_cbsid, []).append(
            (_cbid, _cbname, _cbt_str, _cbdur, _cbactive))

    # Breaks (with shift_id) — pre-format break_time as HH:MM
    cursor.execute("SELECT id, break_name, break_time, duration_minutes, is_active, COALESCE(shift_id,0) FROM break_config WHERE company_id IS NULL ORDER BY shift_id, break_time")
    breaks = []
    for _bid, _bname, _bt, _bdur, _bactive, _bshift in cursor.fetchall():
        if _bt is None:
            _bt_str = "--"
        elif isinstance(_bt, datetime.timedelta):
            _s = int(_bt.total_seconds())
            _bt_str = "%02d:%02d" % (_s // 3600, (_s % 3600) // 60)
        elif isinstance(_bt, datetime.time):
            _bt_str = _bt.strftime("%H:%M")
        else:
            _bt_str = str(_bt)[:5]
        breaks.append((_bid, _bname, _bt_str, _bdur, _bactive, _bshift))

    # Salary
    cursor.execute("""
        SELECT e.employee_id, e.name, COALESCE(s.salary_per_day, 0), e.role, s.last_revised,
               COALESCE(e.phone,''), COALESCE(e.email,'')
        FROM employees e
        LEFT JOIN salary_config s ON e.employee_id = s.employee_id
        ORDER BY e.name
    """)
    salaries = cursor.fetchall()

    # Announcements (admin sees all; include visibility and target employee name)
    cursor.execute("""
        SELECT a.id, a.title, a.content, a.priority, a.created_at,
               COALESCE(a.visibility,'public'), COALESCE(a.target_employee_id,''), COALESCE(e.name,'')
        FROM announcements a
        LEFT JOIN employees e ON e.employee_id = a.target_employee_id
        ORDER BY a.created_at DESC
    """)
    ann_list = cursor.fetchall()

    # Pending counts
    cursor.execute("SELECT COUNT(*) FROM leave_requests WHERE status='Pending'")
    pending_leaves = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM resignation_requests WHERE status='Pending'")
    pending_resignations = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status='Open'")
    pending_tickets = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(company_code,''), COALESCE(default_onboarding_template_id,0) FROM company_settings LIMIT 1")
    _cr = cursor.fetchone()
    company_code = _cr[0] if _cr else ""
    default_onboarding_tpl = int(_cr[1]) if _cr and _cr[1] else 0

    # Company stats
    cursor.execute("SELECT COUNT(*) FROM employees")
    total_employees = cursor.fetchone()[0]
    cursor.execute("""
        SELECT COUNT(*) FROM employees e
        WHERE NOT EXISTS (
            SELECT 1 FROM resignation_requests r
            WHERE r.employee_id = e.employee_id AND r.status = 'Approved'
        )
    """)
    active_employees = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT department) FROM employees WHERE department IS NOT NULL AND department != ''")
    total_departments = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM shifts")
    total_shifts = cursor.fetchone()[0]
    cursor.execute("SELECT id, name FROM onboarding_templates WHERE is_active=1 ORDER BY name")
    onboarding_templates = cursor.fetchall()

    cursor.execute("""
        SELECT c.id, c.name, COALESCE(c.code,''), c.created_at,
               COUNT(e.id) AS emp_count,
               COALESCE(c.working_days,'Mon,Tue,Wed,Thu,Fri'),
               CASE WHEN c.pin IS NOT NULL AND c.pin != '' THEN 1 ELSE 0 END AS has_pin,
               COALESCE(c.logo_path,''),
               CASE WHEN t.company_id IS NOT NULL THEN 1 ELSE 0 END AS has_id_template,
               COALESCE(c.address,''),
               COALESCE(c.website,''),
               COALESCE(c.email,''),
               COALESCE(c.phone,'')
        FROM companies c
        LEFT JOIN employees e ON e.company_id = c.id
        LEFT JOIN id_card_templates t ON t.company_id = c.id
        GROUP BY c.id, c.name, c.code, c.created_at, c.working_days, c.pin, c.logo_path, t.company_id,
                 c.address, c.website, c.email, c.phone
        ORDER BY c.name
    """)
    companies = cursor.fetchall()

    # Feature flags — per-company when active, global otherwise
    _active_cid_settings = session.get("active_company_id")
    fr = get_co_features(_active_cid_settings)
    cursor.execute(
        "SELECT COALESCE(working_days,'Mon,Tue,Wed,Thu,Fri'), COALESCE(company_name,''), COALESCE(timezone,'Asia/Kolkata') FROM company_settings LIMIT 1")
    _gset = cursor.fetchone()
    features = {
        "face_auth": fr["face_auth_enabled"],
        "geo": fr["geo_enabled"],
        "geo_radius": fr["geo_radius"],
        "qr": fr["qr_enabled"],
        "pin": fr["pin_enabled"],
        "fingerprint": fr["fingerprint_enabled"],
        "biometric": fr["biometric_enabled"],
        "notify_leave": fr["notify_leave"],
        "notify_payslip": fr["notify_payslip"],
        "notify_resignation": fr["notify_resignation"],
        "notify_doc_expiry": fr["notify_doc_expiry"],
        "session_timeout": fr["session_timeout"],
        "working_days": (_gset[0] if _gset else "Mon,Tue,Wed,Thu,Fri").split(","),
        "company_name": _gset[1] if _gset else "",
        "timezone": _gset[2] if _gset else "Asia/Kolkata",
        # salary rules from company features
        "late_deduction_pct": fr["late_deduction_pct"],
        "half_day_deduction_pct": fr["half_day_deduction_pct"],
        "grace_minutes": fr["grace_minutes"],
        "holiday_pay": fr["holiday_pay"],
        "leave_pay": fr["leave_pay"],
        "shift_start": fr["shift_start"],
        "shift_half": fr["shift_half"],
        "shift_end": fr["shift_end"],
    }

    # Resolve salary/shift display values: company-specific overrides global
    def _td_str(v):
        if v is None:
            return None
        if isinstance(v, str):
            return v[:5]
        if isinstance(v, datetime.timedelta):
            t = int(v.total_seconds())
            return "%02d:%02d" % (t // 3600, (t % 3600) // 60)
        if isinstance(v, datetime.time):
            return v.strftime("%H:%M")
        return str(v)[:5]

    _co_shift_start = _td_str(fr.get("shift_start")) or cfg.SHIFT_START.strftime("%H:%M")
    _co_shift_half = _td_str(fr.get("shift_half")) or cfg.SHIFT_HALF.strftime("%H:%M")
    _co_shift_end = _td_str(fr.get("shift_end")) or cfg.SHIFT_END.strftime("%H:%M")

    cursor.close()
    db.close()
    return render_template("settings.html",
                           tab=tab,
                           company_code=company_code,
                           total_employees=total_employees,
                           active_employees=active_employees,
                           total_departments=total_departments,
                           total_shifts=total_shifts,
                           companies=companies,
                           company_shifts=company_shifts,
                           company_breaks=company_breaks,
                           shifts=shift_rows,
                           emp_list=emp_list,
                           breaks=breaks,
                           salaries=salaries,
                           ann_list=ann_list,
                           pending_leaves=pending_leaves,
                           pending_resignations=pending_resignations,
                           pending_tickets=pending_tickets,
                           saved=request.args.get("saved") == "1",
                           active_nav="settings",
                           default_start=_co_shift_start,
                           default_half=_co_shift_half,
                           default_end=_co_shift_end,
                           now_month=datetime.date.today().month,
                           now_year=datetime.date.today().year,
                           default_onboarding_tpl=default_onboarding_tpl,
                           onboarding_templates=onboarding_templates,
                           late_deduction_pct=round(fr["late_deduction_pct"], 1),
                           half_day_deduction_pct=round(fr["half_day_deduction_pct"], 1),
                           grace_minutes=fr["grace_minutes"],
                           holiday_pay=fr["holiday_pay"],
                           leave_pay=fr["leave_pay"],
                           auth_config={
                               "face_enabled": fr["face_auth_enabled"],
                               "qr_enabled": fr["qr_enabled"],
                               "fingerprint_enabled": fr["fingerprint_enabled"],
                               "location_enabled": fr["geo_enabled"],
                               "employee_password_auth": True,
                           },
                           features=features,
                           )


# ── Email Settings 2FA gate ────────────────────────────────────────────────────
# The SMTP form used to be rendered server-side with the (encrypted) password
# bound straight into a <input value="...">, which leaked ciphertext into the
# page source and would silently re-encrypt that ciphertext as the "new"
# password on every unrelated save (see fixed POST /email_config below). The
# whole Email tab is now API-driven and gated behind TOTP step-up instead.

@admin_views_bp.route("/api/settings/2fa/setup")
@admin_required
def api_email_2fa_setup():
    """Called when the admin has no TOTP enrolled yet — returns a QR code to
    scan with an authenticator app. Idempotent: re-generates the same secret
    (doesn't rotate it) until enrollment is confirmed via /2fa/enable."""
    username = session.get("admin_username")
    secret, enabled = get_or_create_admin_totp_secret(username)
    if enabled:
        return jsonify({"ok": True, "already_enabled": True})
    return jsonify({
        "ok": True, "already_enabled": False,
        "qr_code": totp_qr_data_uri(username, secret),
        "secret": secret,  # shown once, for manual entry if the QR can't be scanned
    })


@admin_views_bp.route("/api/settings/2fa/enable", methods=["POST"])
@admin_required
def api_email_2fa_enable():
    """Confirms enrollment: the admin must prove they actually captured the
    secret by entering one live code before totp_enabled flips on."""
    username = session.get("admin_username")
    code = (request.get_json(silent=True) or {}).get("code", "")
    if not verify_totp_code(username, code, require_enabled=False):
        log_security_event("auth.2fa_enroll_failed", "TOTP enrollment confirmation failed",
                           level="WARNING", identifier=username)
        return jsonify({"ok": False, "msg": "Invalid code"}), 400
    mark_totp_enabled(username)
    # Confirming enrollment with a live code IS proof of possession — as good
    # as verify-2fa. Without this, the frontend's "unlock immediately after
    # enabling" step would hit the require_email_2fa gate with no session
    # flag set yet, get a 403, and fall back to re-showing the enrollment
    # screen — which looks exactly like "my code keeps getting rejected"
    # even though every code was valid the whole time.
    email_settings_step_up_refresh()
    log_security_event("auth.2fa_enrolled", "Admin enabled TOTP 2FA for Email Settings",
                       level="INFO", identifier=username)
    return jsonify({"ok": True})


@admin_views_bp.route("/api/settings/2fa/reset", methods=["POST"])
@admin_required
@limiter.limit("5 per hour")
def api_email_2fa_reset():
    """Re-enrollment for an admin who deleted the entry from their
    authenticator app: without this they can never produce a valid code
    again for any TOTP-gated area (Security hub, SOC, Email Settings), since
    the old secret is gone from their device but still enabled server-side.
    Requires the account password again — an active session alone isn't
    enough proof to strip an existing MFA factor.

    Logged at ERROR (not WARNING) specifically so it fires the real-time
    security webhook alert alongside a best-effort email to the admin's own
    registered address — stripping an MFA factor is exactly the kind of rare,
    high-consequence action that deserves an out-of-band notice, so the
    legitimate owner finds out even if a stolen session + phished password
    did this, not them."""
    username = session.get("admin_username")
    password = (request.get_json(silent=True) or {}).get("password", "")
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT password, email FROM admin_users WHERE username=%s", (username,))
    row = cursor.fetchone()
    cursor.close()
    db.close()
    if not row or not check_password_hash(row[0], password):
        log_security_event("auth.2fa_reset_denied", "TOTP reset attempt failed password check",
                           level="WARNING", identifier=username)
        return jsonify({"ok": False, "msg": "Incorrect password"}), 401
    admin_email = row[1]
    reset_admin_totp_secret(username)
    email_settings_step_up_clear()
    security_settings_step_up_clear()
    log_security_event("auth.2fa_reset", "Admin reset their TOTP secret for re-enrollment",
                       level="ERROR", identifier=username)
    if admin_email:
        config = get_email_config()
        if config:
            try:
                send_email_smtp(
                    admin_email, "Your two-factor authentication was reset",
                    "<p>The two-factor authentication (TOTP) on your admin account "
                    f"(<b>{username}</b>) was just reset, and the old authenticator "
                    "entry no longer works.</p>"
                    "<p>If you just did this yourself to re-enroll, no action is needed.</p>"
                    "<p><b>If you did not do this</b>, someone may have your password — "
                    "change it immediately and review the security event log.</p>",
                    config,
                )
            except Exception:
                app_log.error("Failed to send 2FA-reset notification to admin %s", username, exc_info=True)
    return jsonify({"ok": True})


@admin_views_bp.route("/api/settings/verify-2fa", methods=["POST"])
@admin_required
def api_settings_verify_2fa():
    """The step-up gate itself. On a correct code, opens a rolling 15-minute
    window (utils/auth.py:email_settings_step_up_refresh) that /api/settings/
    email and friends require. Session-based, not a separate cookie — the
    admin session is already HTTP-only/secure per extensions.py's cookie
    config, so a second cookie would add no isolation, just complexity."""
    username = session.get("admin_username")
    code = (request.get_json(silent=True) or {}).get("code", "")
    if not verify_totp_code(username, code, require_enabled=True):
        log_security_event("access.denied", "Invalid 2FA code for Email Settings step-up",
                           level="WARNING", identifier=username)
        return jsonify({"ok": False, "msg": "Invalid verification code"}), 401
    email_settings_step_up_refresh()
    log_security_event("auth.step_up_verified", "Admin completed 2FA step-up for Email Settings",
                       level="INFO", identifier=username)
    return jsonify({"ok": True, "expires_in": EMAIL_2FA_WINDOW_SEC})


@admin_views_bp.route("/api/settings/2fa/lock", methods=["POST"])
@admin_required
def api_settings_lock():
    """Explicit re-lock — called by the frontend's inactivity timer, and
    available for a manual 'Lock' button. Idempotent."""
    email_settings_step_up_clear()
    return jsonify({"ok": True})


@admin_views_bp.route("/api/settings/email")
@admin_required
@require_email_2fa
def api_get_email_settings():
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    # smtp_pass is deliberately never selected here — the password can only
    # reach the client via the separate, individually-logged reveal endpoint.
    cursor.execute(
        "SELECT smtp_host, smtp_port, smtp_user, from_name, from_email, "
        "(smtp_pass IS NOT NULL AND smtp_pass != '') AS has_password "
        "FROM email_config ORDER BY id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    cursor.close()
    db.close()
    if not row:
        return jsonify({"ok": True, "config": None, "expires_in": EMAIL_2FA_WINDOW_SEC})
    return jsonify({
        "ok": True,
        "config": {
            "host": row[0], "port": row[1], "user": row[2],
            "password": "********" if row[5] else "",
            "from_name": row[3], "from_email": row[4] or row[2],
        },
        "expires_in": EMAIL_2FA_WINDOW_SEC,
    })


@admin_views_bp.route("/api/settings/email", methods=["POST"])
@admin_required
@require_email_2fa
def api_save_email_settings():
    data = request.get_json(silent=True) or {}
    host = (data.get("host") or "").strip()
    port = data.get("port")
    user = (data.get("user") or "").strip()
    from_name = (data.get("from_name") or "Attendance System").strip()
    from_email = (data.get("from_email") or "").strip() or user
    password = (data.get("password") or "").strip()
    if not host or not port or not user:
        return jsonify({"ok": False, "msg": "Host, port, and username are required"}), 400
    try:
        port = int(port)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "msg": "Port must be a number"}), 400

    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    # A masked or blank password means "leave it unchanged" — only a genuine
    # new value gets (re-)encrypted. This is the fix for the bug where the
    # server-rendered form used to re-save its own displayed ciphertext as
    # the "new" password on every unrelated edit, corrupting it.
    if password and password != "********":
        encrypted_password = encrypt_pii(password)
    else:
        cursor.execute("SELECT smtp_pass FROM email_config ORDER BY id DESC LIMIT 1")
        prev = cursor.fetchone()
        encrypted_password = prev[0] if prev else ""
    cursor.execute("DELETE FROM email_config")
    cursor.execute(
        "INSERT INTO email_config (smtp_host, smtp_port, smtp_user, smtp_pass, from_name, from_email) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (host, port, user, encrypted_password, from_name, from_email),
    )
    db.commit()
    cursor.close()
    db.close()
    log_security_event("data.update", "Admin updated SMTP configuration",
                       level="INFO", identifier=session.get("admin_username"))
    return jsonify({"ok": True})


@admin_views_bp.route("/api/settings/email/reveal-password", methods=["POST"])
@admin_required
@require_email_2fa
def api_reveal_email_password():
    """Separate from the GET above on purpose: viewing the masked settings
    and revealing the real password are different sensitivity levels, so
    each admin action to actually see the plaintext gets its own audit-log
    line rather than being indistinguishable from a routine page load."""
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT smtp_pass FROM email_config ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    cursor.close()
    db.close()
    if not row or not row[0]:
        return jsonify({"ok": False, "msg": "No SMTP password set"}), 404
    log_security_event("data.reveal", "Admin revealed SMTP password in Email Settings",
                       level="WARNING", identifier=session.get("admin_username"))
    return jsonify({"ok": True, "password": decrypt_pii(row[0])})


# ── SOC Analyst security dashboard: hidden gate ───────────────────────────────
# Deliberately NOT using @admin_required here. That decorator's failure path
# (redirect to /admin_login, or 401 JSON) is itself a distinguishing signal —
# it tells a caller "this route exists and needs a login" even if they get no
# further. The whole point of this gate is that every failure mode (no
# session at all, a real admin who just isn't SOC-tier, a SOC analyst who
# fat-fingered their code) produces the exact same 404 a nonexistent URL
# would — so the checks are hand-rolled here instead of composed from the
# standard decorators.
#
# This 404-for-everything behavior is a SECONDARY, cosmetic layer on top of
# the actual access control (the role check + TOTP step-up below), not a
# replacement for it — hiding a route's existence does not make it secure on
# its own; anyone who already has the URL (view-source, browser history, a
# leaked internal doc) can still hit it, and the same role+TOTP checks still
# gate them exactly as if the route were listed on a public sitemap.
def _soc_session_or_404():
    """Role-only guard, shared by the verify-2fa endpoint below and as the
    first half of the dashboard/events routes' check (both also require a
    live soc_step_up_valid() window on top of this). Must be an
    authenticated soc_analyst session. Returns (username, role) on success;
    aborts 404 (never 401/403 — no acknowledgment this route exists to a
    session that isn't entitled to it) otherwise."""
    username = session.get("admin_username")
    role = session.get("admin_role")
    logged_in = bool(session.get("admin_logged_in") and username)
    if not logged_in or role != SOC_ANALYST_ROLE:
        log_security_event(
            "access.escalation_attempt" if logged_in else "access.denied",
            "Unauthorized Escalation Attempt: SOC Analyst gate probed by a non-SOC session"
            if logged_in else "Unauthenticated request to SOC Analyst gate",
            level="ERROR" if logged_in else "INFO",
            identifier=username or "anonymous", attempted_role=role or "none",
        )
        abort(404)
    return username, role


@admin_views_bp.route("/api/security/soc/verify-2fa", methods=["POST"])
@limiter.limit("10 per minute")
def api_soc_verify_2fa():
    """The step-up gate itself: the admin's TOTP authenticator code
    (utils/totp.py), required on top of the role check above before the
    dashboard or its events API will respond with anything but a 404."""
    username, _role = _soc_session_or_404()
    if not username:
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401

    body = request.get_json(silent=True) or {}
    totp_code = body.get("code", "")

    if not verify_totp_code(username, totp_code, require_enabled=True):
        log_security_event(
            "access.escalation_attempt",
            "Unauthorized Escalation Attempt: invalid TOTP against the SOC Analyst gate "
            "from an otherwise-valid SOC session",
            level="ERROR", identifier=username,
        )
        abort(404)

    soc_step_up_refresh()
    log_security_event("auth.step_up_verified", "SOC Analyst completed MFA step-up",
                       level="INFO", identifier=username)
    return jsonify({"ok": True, "redirect": "/admin/security-dashboard"})


@admin_views_bp.route("/api/security/soc/lock", methods=["POST"])
@limiter.limit("10 per minute")
def api_soc_lock():
    """Explicit re-lock, mirroring /api/settings/2fa/lock. Not gated behind
    the role/step-up check on purpose — dropping your OWN step-up state is
    always safe to allow, and gating it would just mean a stale unlocked tab
    can't be manually locked by the person sitting at it."""
    soc_step_up_clear()
    return jsonify({"ok": True})


def _compute_security_posture():
    """Real, config-derived facts — not a fabricated 'security score'. Each
    one reads the same source of truth its own feature already uses
    (utils/auth.py's turnstile_enabled(), the same MALWARE_SCAN_ENABLED env
    var utils/helpers.py reads), so this can't silently drift out of sync
    with what's actually enforced elsewhere in the app. Shared by both the
    SOC dashboard and the Security Settings hub below rather than computed
    twice."""
    return {
        "hsts_enabled": True,  # app.py's _security_headers sets this unconditionally on every response
        "csp_enabled": True,   # same — dynamic per-request nonce CSP, always on
        "rate_limit_backend": "In-memory (per-worker — no Redis in this deployment)",
        "malware_scan_enabled": os.environ.get("MALWARE_SCAN_ENABLED", "true").strip().lower() not in ("false", "0", "no"),
        "login_captcha_configured": turnstile_enabled(),
        "email_alert_webhook_configured": bool(os.environ.get("SECURITY_ALERT_WEBHOOK_URL")),
    }


def _security_events_summary(cursor):
    """Aggregate stats over the FULL security_events history (not just the
    most-recent page) — the "complete log analysis" a SOC analyst needs to
    judge whether the last 50 rows they're looking at are routine noise or
    the tail of something bigger."""
    cursor.execute("SELECT COUNT(*) FROM security_events")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT level, COUNT(*) FROM security_events GROUP BY level")
    by_level = {level: count for level, count in cursor.fetchall()}
    cursor.execute(
        "SELECT event_type, COUNT(*) c FROM security_events GROUP BY event_type ORDER BY c DESC LIMIT 8"
    )
    top_event_types = cursor.fetchall()
    cursor.execute("SELECT COUNT(DISTINCT identifier) FROM security_events WHERE identifier IS NOT NULL")
    distinct_identifiers = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT ip) FROM security_events WHERE ip IS NOT NULL")
    distinct_ips = cursor.fetchone()[0]
    cursor.execute("SELECT MIN(created_at), MAX(created_at) FROM security_events")
    oldest, newest = cursor.fetchone()
    return {
        "total": total,
        "by_level": by_level,
        "top_event_types": top_event_types,
        "distinct_identifiers": distinct_identifiers,
        "distinct_ips": distinct_ips,
        "oldest": oldest, "newest": newest,
    }


def _soc_session_and_stepup_or_404():
    """Full gate for the dashboard and its events API: role (via
    _soc_session_or_404) AND a live TOTP step-up window. A valid role alone
    is not enough past this point — matches api_soc_verify_2fa's own check,
    just re-asserted on every subsequent request rather than only at
    unlock time."""
    username, role = _soc_session_or_404()
    if not soc_step_up_valid():
        log_security_event(
            "access.escalation_attempt",
            "Unauthorized Escalation Attempt: SOC Security Dashboard accessed without a valid step-up window",
            level="ERROR", identifier=username, attempted_role=role,
        )
        abort(404)
    return username, role


@admin_views_bp.route("/admin/security-dashboard")
def soc_security_dashboard():
    """The page both the sidebar 'SOC / Security Center' link and the hidden
    corner trigger unlock. Real data, not a mockup: recent force-terminated
    sessions (utils/session_risk.py — includes the Wi-Fi device-posture kill
    events from /api/employee/device_risk), active login lockouts, per-admin
    MFA enrollment, config-derived security posture flags, an all-time
    summary of security_events, and a paginated/filterable log table backed
    by /api/security/soc/events — every log_security_event() call anywhere
    in the app (extensions.py), not just the ones severe enough to trigger a
    webhook alert. This is the actual "observe security and vulnerabilities"
    surface for a SOC analyst, not just a kill-switch status page. Guarded by
    the identical role+step-up check as the verify route above, with the
    same 404-disguise — bookmarking or guessing this URL directly buys
    nothing without both a SOC-tier session AND a live step-up window."""
    _soc_session_and_stepup_or_404()
    soc_step_up_refresh()  # rolling window here too, same reasoning as Email Settings

    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("""
        SELECT sid, identifier, attempt_type, score, last_reason, updated_at
        FROM session_risk WHERE status='compromised'
        ORDER BY updated_at DESC LIMIT 50
    """)
    compromised_sessions = cursor.fetchall()
    cursor.execute("""
        SELECT identifier, attempt_type, failed_count, locked_until, last_attempt
        FROM login_attempts WHERE locked_until IS NOT NULL AND locked_until > NOW()
        ORDER BY last_attempt DESC LIMIT 50
    """)
    active_lockouts = cursor.fetchall()
    cursor.execute("SELECT username, role, COALESCE(totp_enabled, 0) FROM admin_users ORDER BY username")
    admin_mfa_status = cursor.fetchall()
    events_summary = _security_events_summary(cursor)
    cursor.close()
    db.close()

    return render_template("soc_security_dashboard.html",
                           compromised_sessions=compromised_sessions,
                           active_lockouts=active_lockouts,
                           admin_mfa_status=admin_mfa_status,
                           events_summary=events_summary,
                           security_posture=_compute_security_posture(),
                           )


_EVENT_LEVELS = {"ERROR", "WARNING", "INFO"}


@admin_views_bp.route("/api/security/soc/events")
@limiter.limit("60 per minute")
def api_soc_events():
    """Paginated, filterable security_events query backing the SOC
    dashboard's log table — the "complete logs" view, since the page load
    above only carries an all-time summary, not every row. Same role+step-up
    gate as the dashboard itself (404-disguised, not a separate trust
    boundary)."""
    _soc_session_and_stepup_or_404()

    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    try:
        per_page = min(200, max(1, int(request.args.get("per_page", 50))))
    except ValueError:
        per_page = 50

    where = []
    params = []
    level = request.args.get("level", "").strip().upper()
    if level in _EVENT_LEVELS:
        where.append("level = %s")
        params.append(level)
    event_type = request.args.get("event_type", "").strip()
    if event_type:
        where.append("event_type = %s")
        params.append(event_type)
    identifier = request.args.get("identifier", "").strip()
    if identifier:
        where.append("identifier ILIKE %s")
        params.append(f"%{identifier}%")
    q = request.args.get("q", "").strip()
    if q:
        where.append("message ILIKE %s")
        params.append(f"%{q}%")
    start_date = request.args.get("start_date", "").strip()
    if start_date:
        where.append("created_at >= %s")
        params.append(start_date)
    end_date = request.args.get("end_date", "").strip()
    if end_date:
        where.append("created_at <= %s")
        params.append(end_date)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute(f"SELECT COUNT(*) FROM security_events {where_sql}", params)  # nosec B608 — where_sql built from a fixed allowlist of hardcoded conditions above, all values passed as %s params
    total = cursor.fetchone()[0]
    cursor.execute(
        f"SELECT event_type, level, message, identifier, ip, path, method, created_at "  # nosec B608 — same as above
        f"FROM security_events {where_sql} ORDER BY created_at DESC LIMIT %s OFFSET %s",
        params + [per_page, (page - 1) * per_page],
    )
    rows = cursor.fetchall()
    cursor.close()
    db.close()

    return jsonify({
        "ok": True,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, -(-total // per_page)),
        "events": [
            {
                "event_type": r[0], "level": r[1], "message": r[2], "identifier": r[3],
                "ip": r[4], "path": r[5], "method": r[6],
                "created_at": r[7].strftime("%Y-%m-%d %H:%M:%S") if r[7] else None,
            }
            for r in rows
        ],
    })


# ── SOC tactical mitigation: application-layer IP ban ─────────────────────────
# One-click ban straight from a row in the events log above (or typed in
# manually). Enforced by app.py's _enforce_ip_ban before_request hook, which
# runs before every other hook in the app — a banned IP never reaches
# session/auth logic. This is NOT a substitute for a real edge/WAF ban
# (terraform/network_firewall.tf provisions one, deploy-time only); it's the
# thing a SOC analyst can do immediately, from this panel, without cloud API
# credentials wired into the app.

@admin_views_bp.route("/api/security/soc/banned-ips")
def api_soc_banned_ips():
    _soc_session_and_stepup_or_404()
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute(
        "SELECT ip, reason, banned_by, banned_at, expires_at FROM banned_ips "
        "WHERE expires_at IS NULL OR expires_at > NOW() ORDER BY banned_at DESC"
    )
    rows = cursor.fetchall()
    cursor.close()
    db.close()
    return jsonify({"ok": True, "banned_ips": [
        {
            "ip": r[0], "reason": r[1], "banned_by": r[2],
            "banned_at": r[3].strftime("%Y-%m-%d %H:%M:%S") if r[3] else None,
            "expires_at": r[4].strftime("%Y-%m-%d %H:%M:%S") if r[4] else None,
        }
        for r in rows
    ]})


@admin_views_bp.route("/api/security/soc/ban-ip", methods=["POST"])
@limiter.limit("20 per minute")
def api_soc_ban_ip():
    username, _role = _soc_session_and_stepup_or_404()
    body = request.get_json(silent=True) or {}
    ip = (body.get("ip") or "").strip()
    reason = (body.get("reason") or "").strip()[:300] or None
    duration_raw = body.get("duration_minutes")

    import ipaddress
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return jsonify({"ok": False, "msg": "Invalid IP address"}), 400

    expires_at = None
    if duration_raw not in (None, "", 0, "0"):
        try:
            minutes = int(duration_raw)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "msg": "Invalid duration"}), 400
        if minutes > 0:
            expires_at = datetime.datetime.now() + datetime.timedelta(minutes=minutes)

    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute(
        "INSERT INTO banned_ips (ip, reason, banned_by, expires_at) VALUES (%s,%s,%s,%s) "
        "ON CONFLICT (ip) DO UPDATE SET reason=EXCLUDED.reason, banned_by=EXCLUDED.banned_by, "
        "banned_at=CURRENT_TIMESTAMP, expires_at=EXCLUDED.expires_at",
        (ip, reason, username, expires_at),
    )
    db.commit()
    cursor.close()
    db.close()

    log_security_event("soc.ip_banned", f"SOC analyst banned IP {ip}",
                       level="ERROR", identifier=username, target_ip=ip, reason=reason or "(none given)")
    return jsonify({"ok": True})


@admin_views_bp.route("/api/security/soc/unban-ip", methods=["POST"])
@limiter.limit("20 per minute")
def api_soc_unban_ip():
    username, _role = _soc_session_and_stepup_or_404()
    body = request.get_json(silent=True) or {}
    ip = (body.get("ip") or "").strip()
    if not ip:
        return jsonify({"ok": False, "msg": "IP required"}), 400

    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("DELETE FROM banned_ips WHERE ip=%s", (ip,))
    db.commit()
    cursor.close()
    db.close()

    log_security_event("soc.ip_unbanned", f"SOC analyst unbanned IP {ip}",
                       level="WARNING", identifier=username, target_ip=ip)
    return jsonify({"ok": True})


# ── Security Settings hub (Settings → System → Security) ─────────────────────
# Consolidates every security-related admin surface into one MFA-gated,
# row-wise view: the SOC dashboard entry point, this admin's own MFA
# enrollment, the Email Settings 2FA gate, login-protection status, the
# existing session-timeout setting, the audit log link, and the same
# security-posture facts the SOC dashboard shows. Any logged-in admin can
# open this hub with their own TOTP code — no role restriction here, unlike
# the SOC dashboard itself, which still enforces admin_role=='soc_analyst'
# independently when its row is followed.
@admin_views_bp.route("/api/settings/security/verify-2fa", methods=["POST"])
@admin_required
@limiter.limit("10 per minute")
def api_security_settings_verify_2fa():
    username = session.get("admin_username")
    code = (request.get_json(silent=True) or {}).get("code", "")
    if not verify_totp_code(username, code, require_enabled=True):
        log_security_event("access.denied", "Invalid 2FA code for Security Settings hub step-up",
                           level="WARNING", identifier=username)
        return jsonify({"ok": False, "msg": "Invalid verification code"}), 401
    security_settings_step_up_refresh()
    log_security_event("auth.step_up_verified", "Admin completed 2FA step-up for Security Settings hub",
                       level="INFO", identifier=username)
    return jsonify({"ok": True, "expires_in": SECURITY_SETTINGS_2FA_WINDOW_SEC})


@admin_views_bp.route("/api/settings/security/overview")
@admin_required
@require_security_settings_2fa
def api_security_settings_overview():
    username = session.get("admin_username")
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT COALESCE(totp_enabled, 0) FROM admin_users WHERE username=%s", (username,))
    row = cursor.fetchone()
    own_totp_enrolled = bool(row and row[0])

    active_cid = session.get("active_company_id")
    if active_cid:
        fr = get_co_features(active_cid)
        session_timeout = fr.get("session_timeout", 30)
    else:
        cursor.execute("SELECT session_timeout FROM company_settings LIMIT 1")
        r = cursor.fetchone()
        session_timeout = r[0] if r and r[0] else 30

    can_manage_roles = session.get("admin_role") == "admin"
    admin_roster = []
    if can_manage_roles:
        # Role assignment is restricted to base 'admin' accounts only (see
        # api_security_settings_roles below for the enforced check — this
        # client-side flag just avoids rendering editable controls someone
        # can't actually use). Without this restriction, a 'manager' or even
        # a 'soc_analyst' account passing only THIS hub's low-bar TOTP check
        # could grant itself the soc_analyst role and immediately satisfy
        # the stricter SOC gate too, since both gates check the same TOTP
        # secret — that would make the role check meaningless.
        cursor.execute("SELECT username, role, COALESCE(totp_enabled, 0) FROM admin_users ORDER BY username")
        admin_roster = [
            {"username": u, "role": r, "totp_enabled": bool(t)}
            for u, r, t in cursor.fetchall()
        ]
    cursor.close()
    db.close()

    return jsonify({
        "ok": True,
        "is_soc_analyst": session.get("admin_role") == SOC_ANALYST_ROLE,
        "own_totp_enrolled": own_totp_enrolled,
        "session_timeout_minutes": session_timeout,
        "can_manage_roles": can_manage_roles,
        "admin_roster": admin_roster,
        "security_posture": _compute_security_posture(),
    })


_ASSIGNABLE_ROLES = ("admin", "manager", "soc_analyst")


@admin_views_bp.route("/api/settings/security/roles", methods=["POST"])
@admin_required
@require_security_settings_2fa
def api_security_settings_roles():
    actor = session.get("admin_username")
    if session.get("admin_role") != "admin":
        log_security_event(
            "access.escalation_attempt",
            "Unauthorized Escalation Attempt: role change attempted by a non-admin session",
            level="ERROR", identifier=actor, attempted_role=session.get("admin_role"),
        )
        abort(404)  # same disguise posture as the SOC routes for this sensitive an action

    data = request.get_json(silent=True) or {}
    target_username = (data.get("username") or "").strip()
    new_role = (data.get("role") or "").strip()
    if new_role not in _ASSIGNABLE_ROLES:
        return jsonify({"ok": False, "msg": "Invalid role."}), 400
    if not target_username:
        return jsonify({"ok": False, "msg": "Username required."}), 400

    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT role FROM admin_users WHERE username=%s", (target_username,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        db.close()
        return jsonify({"ok": False, "msg": "Admin account not found."}), 404
    old_role = row[0]
    cursor.execute("UPDATE admin_users SET role=%s WHERE username=%s", (new_role, target_username))
    db.commit()
    cursor.close()
    db.close()

    # A role change is a privilege-boundary event regardless of direction —
    # ERROR severity (not INFO) so it always feeds the alert webhook; a
    # false negative here (a real escalation nobody noticed) is worse than
    # one extra alert for a routine, intended role change.
    log_security_event(
        "admin.role_changed", f"Admin role changed: {old_role} -> {new_role}",
        level="ERROR", identifier=actor, target_admin=target_username,
        old_role=old_role, new_role=new_role,
    )
    return jsonify({"ok": True})


@admin_views_bp.route("/api/settings/security/session-timeout", methods=["POST"])
@admin_required
@require_security_settings_2fa
def api_security_settings_session_timeout():
    try:
        timeout = int((request.get_json(silent=True) or {}).get("timeout", 30))
        if not (5 <= timeout <= 1440):
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"ok": False, "msg": "Session timeout must be between 5 and 1440 minutes."}), 400

    active_cid = session.get("active_company_id")
    if active_cid:
        _upsert_co_feature(active_cid, "session_timeout", timeout)
    else:
        db = get_db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute("UPDATE company_settings SET session_timeout=%s", (timeout,))
        db.commit()
        cursor.close()
        db.close()
    return jsonify({"ok": True})


@admin_views_bp.route("/api/settings/security/lock", methods=["POST"])
def api_security_settings_lock():
    security_settings_step_up_clear()
    return jsonify({"ok": True})


# CI enforces this floor on every merge (.github/workflows/deploy.yml's
# --cov-fail-under=80) — it's the one real, verifiable "quality" number this
# repo has. Deliberately NOT claiming a live-measured percentage here: no
# coverage report is generated or stored outside CI, so showing anything
# more precise than the enforced gate would be fabricated.
_COVERAGE_GATE_PCT = 80


@admin_views_bp.route("/api/settings/security/performance")
@admin_required
@require_security_settings_2fa
def api_security_settings_performance():
    """Real, live-measured request performance/error-rate (utils/perf_metrics,
    recorded on every request by app.py's before/after_request hooks since
    process start) plus DB pool utilization and connectivity — not a
    fabricated 'quality score'. Gated behind the same Security hub step-up
    as the rest of this file; nothing here is public."""
    try:
        db = get_db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        db.close()
        db_healthy = True
    except Exception:
        db_healthy = False

    return jsonify({
        "ok": True,
        "performance": get_perf_snapshot(),
        "db_pool": pool_stats(),
        "db_healthy": db_healthy,
        "coverage_gate_pct": _COVERAGE_GATE_PCT,
    })


@admin_views_bp.route("/save_default_onboarding_template", methods=["POST"])
@admin_required
def save_default_onboarding_template():
    tpl_id = request.form.get("default_onboarding_template_id") or None
    if tpl_id == "0" or tpl_id == "":
        tpl_id = None
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("UPDATE company_settings SET default_onboarding_template_id=%s", (tpl_id,))
    db.commit()
    cursor.close()
    db.close()
    flash("Default onboarding template saved.", "success")
    return redirect("/onboarding?tab=templates")


@admin_views_bp.route("/save_salary_rules", methods=["POST"])
@admin_required
def save_salary_rules():
    try:
        late_pct = max(0.0, min(100.0, float(request.form.get("late_deduction_pct", 10))))
        half_pct = max(0.0, min(100.0, float(request.form.get("half_day_deduction_pct", 50))))
        grace_min = max(0, min(120, int(request.form.get("grace_minutes", 15))))
    except (ValueError, TypeError):
        flash("Invalid values.", "error")
        return redirect("/settings?tab=salary")
    holiday_pay = request.form.get("holiday_pay", "paid")
    leave_pay = request.form.get("leave_pay", "exclude")
    if holiday_pay not in ("paid", "unpaid"):
        holiday_pay = "paid"
    if leave_pay not in ("exclude", "absent"):
        leave_pay = "exclude"
    shift_start_raw = request.form.get("shift_start", "").strip()
    shift_half_raw = request.form.get("shift_half", "").strip()
    shift_end_raw = request.form.get("shift_end", "").strip()
    active_cid = session.get("active_company_id")
    if active_cid:
        _fields = {
            "late_deduction_pct": late_pct, "half_day_deduction_pct": half_pct,
            "grace_minutes": grace_min, "holiday_pay": holiday_pay, "leave_pay": leave_pay,
        }
        if shift_start_raw and shift_half_raw and shift_end_raw:
            _fields.update({"shift_start": shift_start_raw, "shift_half": shift_half_raw,
                            "shift_end": shift_end_raw})
        _upsert_co_features(active_cid, _fields)
    else:
        db = get_db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute(
            "UPDATE company_settings SET late_deduction_pct=%s, half_day_deduction_pct=%s, "
            "grace_minutes=%s, holiday_pay=%s, leave_pay=%s",
            (late_pct, half_pct, grace_min, holiday_pay, leave_pay)
        )
        if shift_start_raw and shift_half_raw and shift_end_raw:
            cursor.execute(
                "UPDATE company_settings SET shift_start=%s, shift_half=%s, shift_end=%s",
                (shift_start_raw, shift_half_raw, shift_end_raw)
            )
        db.commit()
        cursor.close()
        db.close()
        cfg.load_salary_rules()
        cfg.load_default_shift()
    flash("Salary rules saved.", "success")
    return redirect("/settings?tab=salary")


@admin_views_bp.route("/toggle_auth_method", methods=["POST"])
@admin_required
def toggle_auth_method():
    method = request.form.get("method", "")
    enabled = request.form.get("enabled", "0") == "1"
    if method not in _TOGGLE_COLUMN_MAP:
        flash("Invalid authentication method.", "danger")
        return redirect("/settings?tab=attendance")
    column = _TOGGLE_COLUMN_MAP[method]
    label = _TOGGLE_LABEL_MAP[method]
    active_cid = session.get("active_company_id")
    # Map old column names to company_feature_settings column names
    _cfs_map = {"face_enabled": "face_auth_enabled", "location_enabled": "geo_enabled",
                "employee_password_auth": None}  # password auth stays global
    cfs_col = _cfs_map.get(column, column)
    if active_cid and cfs_col:
        _upsert_co_feature(active_cid, cfs_col, 1 if enabled else 0)
    else:
        _VALID_CS_TOGGLE = frozenset(_TOGGLE_COLUMN_MAP.values())
        if column not in _VALID_CS_TOGGLE:
            flash("Invalid setting.", "danger")
            return redirect("/settings?tab=attendance")
        db = get_db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute(f"UPDATE company_settings SET {column}=%s", (1 if enabled else 0,))  # nosec B608 nosemgrep: python.flask.security.injection.tainted-sql-string.tainted-sql-string
        db.commit()
        cursor.close()
        db.close()
    state = "enabled" if enabled else "disabled"
    flash(f"{label} {state}.", "success")
    return redirect("/settings?tab=attendance")


@admin_views_bp.route("/toggle_fingerprint", methods=["POST"])
@admin_required
def toggle_fingerprint():
    enabled = request.form.get("enabled", "0") == "1"
    active_cid = session.get("active_company_id")
    if active_cid:
        _upsert_co_feature(active_cid, "fingerprint_enabled", 1 if enabled else 0)
    else:
        db = get_db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute("UPDATE company_settings SET fingerprint_enabled=%s", (1 if enabled else 0,))
        db.commit()
        cursor.close()
        db.close()
    state = "enabled" if enabled else "disabled"
    flash(f"Fingerprint authentication {state}.", "success")
    return redirect("/settings?tab=attendance")


@admin_views_bp.route("/save_company_code", methods=["POST"])
@admin_required
def save_company_code():
    code = request.form.get("company_code", "").strip().upper()[:10]
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("UPDATE company_settings SET company_code=%s", (code,))
    db.commit()
    cursor.close()
    db.close()
    flash(f"Company code set to '{code}'.", "success")
    return redirect("/settings?tab=company")


@admin_views_bp.route("/save_company_info", methods=["POST"])
@admin_required
def save_company_info():
    import pytz as _pytz
    _VALID_DAYS = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
    name = request.form.get("company_name", "").strip()[:200]
    code = request.form.get("company_code", "").strip().upper()[:10]
    timezone = request.form.get("timezone", "Asia/Kolkata").strip()
    w_days_raw = request.form.getlist("working_days")
    # Validate timezone against pytz database
    if timezone not in _pytz.all_timezones_set:
        flash("Invalid timezone selected.", "danger")
        return redirect("/settings?tab=company")
    # Validate day names
    w_days_set = set(w_days_raw)
    if w_days_set and not w_days_set.issubset(_VALID_DAYS):
        flash("Invalid working days selected.", "danger")
        return redirect("/settings?tab=company")
    w_days = ",".join(d for d in w_days_raw if d in _VALID_DAYS)
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute(
        "UPDATE company_settings SET company_name=%s, company_code=%s, timezone=%s, working_days=%s",
        (name, code, timezone, w_days or "Mon,Tue,Wed,Thu,Fri")
    )
    db.commit()
    cursor.close()
    db.close()
    flash("Company info saved.", "success")
    return redirect("/settings?tab=company")


@admin_views_bp.route("/toggle_feature", methods=["POST"])
@admin_required
def toggle_feature():
    allowed = {
        "face_auth_enabled", "geo_enabled", "qr_enabled", "pin_enabled",
        "fingerprint_enabled", "biometric_enabled",
        "notify_leave", "notify_payslip", "notify_resignation", "notify_doc_expiry",
    }
    data = request.get_json(force=True) or {}
    feature = data.get("feature", "")
    value = 1 if data.get("value") else 0
    if feature not in allowed:
        return jsonify({"ok": False, "error": "unknown feature"}), 400
    active_cid = session.get("active_company_id")
    # Explicit allowlist maps feature name → exact DB column (no dynamic interpolation)
    _CS_COL_MAP = {
        "face_auth_enabled": "face_auth_enabled",
        "geo_enabled": "geo_enabled",
        "qr_enabled": "qr_enabled",
        "pin_enabled": "pin_enabled",
        "fingerprint_enabled": "fingerprint_enabled",
        "biometric_enabled": "biometric_enabled",
        "notify_leave": "notify_leave",
        "notify_payslip": "notify_payslip",
        "notify_resignation": "notify_resignation",
        "notify_doc_expiry": "notify_doc_expiry",
    }
    cs_col = _CS_COL_MAP.get(feature)
    if not cs_col:
        return jsonify({"ok": False, "error": "unknown feature"}), 400
    if active_cid:
        _upsert_co_feature(active_cid, cs_col, value)
    else:
        db = get_db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute(f"UPDATE company_settings SET {cs_col}=%s", (value,))  # nosec B608 nosemgrep: python.flask.security.injection.tainted-sql-string.tainted-sql-string
        db.commit()
        cursor.close()
        db.close()
    return jsonify({"ok": True})


@admin_views_bp.route("/save_geo_radius", methods=["POST"])
@admin_required
def save_geo_radius():
    try:
        radius = int(request.form.get("geo_radius", 100))
        if not (50 <= radius <= 5000):
            raise ValueError
    except (ValueError, TypeError):
        flash("Geo radius must be between 50 and 5000 metres.", "danger")
        return redirect("/settings?tab=attendance")
    active_cid = session.get("active_company_id")
    if active_cid:
        _upsert_co_feature(active_cid, "geo_radius", radius)
    else:
        db = get_db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute("UPDATE company_settings SET geo_radius=%s", (radius,))
        db.commit()
        cursor.close()
        db.close()
    flash("Attendance settings saved.", "success")
    return redirect("/settings?tab=attendance")


# save_security_settings retired: the Security tab is now the MFA-gated
# hub above (api_security_settings_session_timeout does the same DB write,
# JSON-based, reachable only after the step-up gate reveals the row).


@admin_views_bp.route("/switch_company", methods=["POST"])
@admin_required
def switch_company():
    cid = request.form.get("company_id", "").strip()
    pin = request.form.get("pin", "").strip()
    dest = _safe_redirect(request.form.get("next", ""), "/admin")
    if not cid:
        session.pop("active_company_id", None)
        flash("Switched to: All Companies", "success")
        return redirect(dest)
    try:
        cid = int(cid)
    except ValueError:
        return redirect(dest)
    db = get_db_connection()
    cur = db.cursor(buffered=True)
    cur.execute("SELECT name, COALESCE(pin,'') FROM companies WHERE id=%s", (cid,))
    row = cur.fetchone()
    cur.close()
    db.close()
    if not row:
        flash("Company not found.", "error")
        return redirect(dest)
    cname, stored_pin = row
    if stored_pin and not secrets.compare_digest(stored_pin, pin):
        flash(f"Incorrect PIN for {cname}.", "error")
        return redirect(dest + ("&" if "?" in dest else "?") + "pin_error=1&pin_cid=" + str(cid))
    session["active_company_id"] = cid
    flash(f"Switched to: {cname}", "success")
    return redirect(dest)


@admin_views_bp.route("/clear_company", methods=["POST"])
@admin_required
def clear_company():
    session.pop("active_company_id", None)
    flash("Viewing all companies.", "success")
    return redirect(_safe_redirect(request.form.get("next", ""), "/admin"))


@admin_views_bp.route("/set_company_pin", methods=["POST"])
@admin_required
def set_company_pin():
    cid = request.form.get("company_id", "").strip()
    pin = request.form.get("pin", "").strip()
    if not cid:
        flash("Invalid request.", "error")
        return redirect("/settings?tab=company")
    db = get_db_connection()
    cur = db.cursor(buffered=True)
    cur.execute("UPDATE companies SET pin=%s WHERE id=%s", (pin or None, int(cid)))
    db.commit()
    cur.close()
    db.close()
    invalidate_companies_cache()
    flash("PIN " + ("set." if pin else "removed."), "success")
    return redirect("/settings?tab=company")


@admin_views_bp.route("/companies")
@admin_required
def view_companies():
    return redirect("/settings?tab=company")


def _save_company_image(file_storage, cid, kind):
    """Save an uploaded company logo / ID-card-template image under static/,
    deterministically named by company id so re-uploads just overwrite the
    previous file. `kind` is 'logo', 'front' or 'back'. Returns the relative
    path (under static/) to store in the DB."""
    ext = os.path.splitext(file_storage.filename)[1].lower()
    folder_name = "company_logos" if kind == "logo" else "id_card_templates"
    folder = os.path.join(app.root_path, "static", folder_name)
    os.makedirs(folder, exist_ok=True)
    filename = f"co_{cid}_{kind}{ext}"
    file_storage.save(os.path.join(folder, filename))
    return f"{folder_name}/{filename}"


def _delete_company_image(rel_path):
    """Best-effort cleanup of a previously-stored company logo/template file."""
    if not rel_path:
        return
    try:
        os.remove(os.path.join(app.root_path, "static", rel_path))
    except OSError:
        pass


@admin_views_bp.route("/companies/add", methods=["POST"])
@admin_required
def add_company():
    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip().upper()[:20] or None
    address = request.form.get("address", "").strip() or None
    website = request.form.get("website", "").strip() or None
    email = request.form.get("email", "").strip() or None
    phone = request.form.get("phone", "").strip() or None
    redirect_to = request.form.get("redirect_to", "companies")
    dest = "/settings?tab=company" if redirect_to == "settings" else "/companies"
    if not name:
        flash("Company name is required.", "error")
        return redirect(dest)

    logo_file = request.files.get("logo")
    if logo_file and logo_file.filename:
        logo_ok, logo_err = _validate_image_file(logo_file)
        if not logo_ok:
            flash(f"Company logo: {logo_err}", "error")
            return redirect(dest)

    w_days = ",".join(request.form.getlist("working_days")) or "Mon,Tue,Wed,Thu,Fri"
    db = get_db_connection()
    cursor = db.cursor(buffered=True)

    shift_names = request.form.getlist("shift_name[]")
    shift_starts = request.form.getlist("shift_start[]")
    shift_halfs = request.form.getlist("shift_half[]")
    shift_ends = request.form.getlist("shift_end[]")
    break_names = request.form.getlist("break_name[]")
    break_times = request.form.getlist("break_time[]")
    break_durs = request.form.getlist("break_duration[]")

    try:
        with transaction(db):
            cursor.execute(
                "INSERT INTO companies (name, code, working_days, address, website, email, phone) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (name, code, w_days, address, website, email, phone)
            )
            new_cid = cursor.fetchone()[0]

            for sname, sstart, shalf, send in zip(shift_names, shift_starts, shift_halfs, shift_ends):
                sname = sname.strip()
                sstart = sstart.strip()
                shalf = shalf.strip()
                send = send.strip()
                if sname and sstart and shalf and send:
                    cursor.execute(
                        "INSERT INTO shifts (name, start_time, half_time, end_time, company_id) VALUES (%s,%s,%s,%s,%s)",
                        (sname,
                         sstart + ":00" if len(sstart) == 5 else sstart,
                         shalf + ":00" if len(shalf) == 5 else shalf,
                         send + ":00" if len(send) == 5 else send,
                         new_cid)
                    )

            for bname, btime, bdur in zip(break_names, break_times, break_durs):
                bname = bname.strip()
                btime = btime.strip()
                bdur = bdur.strip()
                if bname and btime and bdur.isdigit():
                    cursor.execute(
                        "INSERT INTO break_config (break_name, break_time, duration_minutes, company_id) VALUES (%s,%s,%s,%s)",
                        (bname, btime + ":00" if len(btime) == 5 else btime, int(bdur), new_cid)
                    )
    except Exception:
        cursor.close()
        db.close()
        app_log.warning("add_company failed mid-transaction for %r, rolled back", name)
        flash("Failed to add company; no changes were made.", "error")
        return redirect(dest)

    if logo_file and logo_file.filename:
        logo_path = _save_company_image(logo_file, new_cid, "logo")
        cursor.execute("UPDATE companies SET logo_path=%s WHERE id=%s", (logo_path, new_cid))
        db.commit()

    cursor.close()
    db.close()
    invalidate_companies_cache()
    flash(f"Company '{name}' added.", "success")
    return redirect(dest)


@admin_views_bp.route("/companies/<int:cid>/edit", methods=["POST"])
@admin_required
def edit_company(cid):
    name = request.form.get("name", "").strip()
    new_code = (request.form.get("code", "").strip().upper()[:20]) or None
    address = request.form.get("address", "").strip() or None
    website = request.form.get("website", "").strip() or None
    email = request.form.get("email", "").strip() or None
    phone = request.form.get("phone", "").strip() or None
    redirect_to = request.form.get("redirect_to", "companies")
    dest = "/settings?tab=company" if redirect_to == "settings" else "/companies"

    if not name:
        flash("Company name is required.", "error")
        return redirect(dest)

    logo_file = request.files.get("logo")
    if logo_file and logo_file.filename:
        logo_ok, logo_err = _validate_image_file(logo_file)
        if not logo_ok:
            flash(f"Company logo: {logo_err}", "error")
            return redirect(dest)

    db = get_db_connection()
    cursor = db.cursor(buffered=True)

    w_days = ",".join(request.form.getlist("working_days")) or "Mon,Tue,Wed,Thu,Fri"

    cursor.execute("SELECT COALESCE(code,''), COALESCE(logo_path,'') FROM companies WHERE id=%s", (cid,))
    row = cursor.fetchone()
    old_code = (row[0] or "").strip().upper() if row else ""
    old_logo_path = row[1] if row and row[1] else None

    renamed_count = 0
    to_rename = []
    try:
        with transaction(db):
            cursor.execute(
                "UPDATE companies SET name=%s, code=%s, working_days=%s, address=%s, "
                "website=%s, email=%s, phone=%s WHERE id=%s",
                (name, new_code, w_days, address, website, email, phone, cid)
            )

            if old_code and new_code and old_code != new_code:
                cursor.execute(
                    "SELECT employee_id FROM employees WHERE company_id=%s AND employee_id LIKE %s",
                    (cid, old_code + "%")
                )
                to_rename = [
                    (r[0], new_code + r[0][len(old_code):])
                    for r in cursor.fetchall() if r[0].startswith(old_code)
                ]

                related_tables = [
                    "attendance", "salary_config", "leave_requests", "notifications",
                    "resignation_requests", "tickets", "employee_incentives",
                    "employee_experience", "employee_education", "leave_balances",
                    "employee_documents", "performance_reviews", "overtime_records",
                    "regularization_requests", "compoff_balance", "employee_onboarding",
                ]

                # One UPDATE per related table for the whole renamed batch (via a
                # Postgres UNNEST mapping table), instead of one UPDATE per table
                # PER renamed employee — a rename of N employees previously issued
                # N*16 round trips here; this issues a flat 16 regardless of N.
                old_ids = [p[0] for p in to_rename]
                new_ids = [p[1] for p in to_rename]
                for tbl in related_tables:
                    try:
                        cursor.execute(
                            f"UPDATE {tbl} AS t SET employee_id = m.new_eid "  # nosec B608
                            f"FROM (SELECT * FROM UNNEST(%s::text[], %s::text[]) AS m(old_eid, new_eid)) AS m "
                            f"WHERE t.employee_id = m.old_eid",
                            (old_ids, new_ids)
                        )
                    except Exception:
                        pass

                for old_eid, new_eid in to_rename:
                    new_img = os.path.join(app.config["UPLOAD_FOLDER"], new_eid + ".jpg")
                    new_qr = os.path.join("static", "qrcodes", new_eid + ".png")
                    cursor.execute(
                        "UPDATE employees SET employee_id=%s, face_image=%s, qr_code=%s "
                        "WHERE employee_id=%s AND company_id=%s",
                        (new_eid, new_img, new_qr, old_eid, cid)
                    )
                    renamed_count += 1
    except Exception:
        cursor.close()
        db.close()
        app_log.warning("edit_company failed mid-transaction for company %s, rolled back", cid)
        flash("Failed to update company; no changes were made.", "error")
        return redirect(dest)

    # File renames happen only after the DB transaction has committed, so a
    # rollback above never leaves files renamed out from under DB rows that
    # still point at the old employee_id.
    for old_eid, new_eid in to_rename:
        old_img = os.path.join(app.config["UPLOAD_FOLDER"], old_eid + ".jpg")
        new_img = os.path.join(app.config["UPLOAD_FOLDER"], new_eid + ".jpg")
        old_qr = os.path.join("static", "qrcodes", old_eid + ".png")
        new_qr = os.path.join("static", "qrcodes", new_eid + ".png")
        if os.path.exists(old_img):
            try:
                os.rename(old_img, new_img)
            except Exception:
                pass
        if os.path.exists(old_qr):
            try:
                os.rename(old_qr, new_qr)
            except Exception:
                pass

    if logo_file and logo_file.filename:
        new_logo_path = _save_company_image(logo_file, cid, "logo")
        cursor.execute("UPDATE companies SET logo_path=%s WHERE id=%s", (new_logo_path, cid))
        db.commit()
        if old_logo_path and old_logo_path != new_logo_path:
            _delete_company_image(old_logo_path)

    if to_rename:
        flash(
            f"Company updated. {renamed_count} employee ID(s) renamed: "
            f"{old_code}xxx → {new_code}xxx.",
            "success"
        )
    else:
        flash("Company updated.", "success")

    cursor.close()
    db.close()
    invalidate_companies_cache()
    return redirect(dest)


@admin_views_bp.route("/companies/<int:cid>/delete", methods=["POST"])
@admin_required
def delete_company(cid):
    redirect_to = request.form.get("redirect_to", "companies")
    dest = "/settings?tab=company" if redirect_to == "settings" else "/companies"
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT COUNT(*) FROM employees WHERE company_id=%s", (cid,))
    count = cursor.fetchone()[0]
    if count > 0:
        cursor.close()
        db.close()
        flash(f"Cannot delete: {count} employee(s) are assigned to this company.", "error")
        return redirect(dest)
    cursor.execute("SELECT COALESCE(logo_path,'') FROM companies WHERE id=%s", (cid,))
    logo_row = cursor.fetchone()
    cursor.execute("SELECT COALESCE(front_image,''), COALESCE(back_image,'') FROM id_card_templates WHERE company_id=%s", (cid,))
    tpl_row = cursor.fetchone()
    cursor.execute("DELETE FROM companies WHERE id=%s", (cid,))
    db.commit()
    cursor.close()
    db.close()
    invalidate_companies_cache()
    _delete_company_image(logo_row[0] if logo_row else None)
    if tpl_row:
        _delete_company_image(tpl_row[0])
        _delete_company_image(tpl_row[1])
    flash("Company deleted.", "success")
    return redirect(dest)


# ── Custom ID card templates (per company) ─────────────────────────────────
_ID_CARD_FIELD_KEYS = {
    "photo", "logo", "name", "employee_id", "designation",
    "email", "phone", "blood_group", "qr",
    "date_of_joining", "company_address", "website",
    "emergency_contact_name", "emergency_contact_phone", "emergency_contact_relation",
    "department", "shift", "reporting_manager", "shift_timing", "work_mode", "company_phone",
}


@admin_views_bp.route("/companies/<int:cid>/id_card_template/upload", methods=["POST"])
@admin_required
def id_card_template_upload(cid):
    front_file = request.files.get("front_image")
    back_file = request.files.get("back_image")
    # bool() of a truthiness check, not a numeric-string parse -- nothing
    # here casts user input to float/complex, so NaN injection doesn't apply.
    has_front = bool(front_file and front_file.filename)  # nosemgrep: python.flask.security.injection.nan-injection.nan-injection
    has_back = bool(back_file and back_file.filename)  # nosemgrep: python.flask.security.injection.nan-injection.nan-injection
    if not has_front and not has_back:
        flash("Upload at least a front or back template image.", "error")
        return redirect("/settings?tab=company")

    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT COUNT(*) FROM companies WHERE id=%s", (cid,))
    if not cursor.fetchone()[0]:
        cursor.close()
        db.close()
        abort(404)

    if has_front:
        ok, err = _validate_image_file(front_file)
        if not ok:
            cursor.close()
            db.close()
            flash(f"Front template: {err}", "error")
            return redirect("/settings?tab=company")
    if has_back:
        ok, err = _validate_image_file(back_file)
        if not ok:
            cursor.close()
            db.close()
            flash(f"Back template: {err}", "error")
            return redirect("/settings?tab=company")

    cursor.execute(
        "SELECT COALESCE(front_image,''), COALESCE(back_image,'') FROM id_card_templates WHERE company_id=%s", (cid,)
    )
    existing = cursor.fetchone()
    old_front = existing[0] if existing and existing[0] else None
    old_back = existing[1] if existing and existing[1] else None

    new_front = _save_company_image(front_file, cid, "front") if has_front else old_front
    new_back = _save_company_image(back_file, cid, "back") if has_back else old_back

    cursor.execute("""
        INSERT INTO id_card_templates (company_id, front_image, back_image, updated_at)
        VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (company_id) DO UPDATE SET
            front_image = EXCLUDED.front_image,
            back_image = EXCLUDED.back_image,
            updated_at = CURRENT_TIMESTAMP
    """, (cid, new_front, new_back))
    db.commit()
    cursor.close()
    db.close()

    if has_front and old_front and old_front != new_front:
        _delete_company_image(old_front)
    if has_back and old_back and old_back != new_back:
        _delete_company_image(old_back)

    flash("Template image(s) uploaded. Now place the fields.", "success")
    return redirect(f"/companies/{cid}/id_card_template/editor")


@admin_views_bp.route("/companies/<int:cid>/id_card_template/editor")
@admin_required
def id_card_template_editor(cid):
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT name FROM companies WHERE id=%s", (cid,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        db.close()
        abort(404)
    company_name = row[0]
    cursor.execute(
        "SELECT front_image, back_image, fields FROM id_card_templates WHERE company_id=%s", (cid,)
    )
    tpl = cursor.fetchone()
    cursor.close()
    db.close()

    front_image = tpl[0] if tpl else None
    back_image = tpl[1] if tpl else None
    try:
        fields = json.loads(tpl[2]) if tpl and tpl[2] else {}
    except (ValueError, TypeError):
        fields = {}

    return render_template(
        "id_card_template_editor.html",
        cid=cid, company_name=company_name,
        front_image=front_image, back_image=back_image,
        fields_json=json.dumps(fields),
    )


@admin_views_bp.route("/companies/<int:cid>/id_card_template/save_positions", methods=["POST"])
@admin_required
def id_card_template_save_positions(cid):
    raw = request.form.get("positions_json", "")
    try:
        positions = json.loads(raw) if raw else {}
    except ValueError:
        positions = None

    if not isinstance(positions, dict):
        flash("Invalid field positions submitted.", "error")
        return redirect(f"/companies/{cid}/id_card_template/editor")

    cleaned = {}
    for key, box in positions.items():
        if key not in _ID_CARD_FIELD_KEYS or not isinstance(box, dict):
            continue
        try:
            x, y, w, h = float(box["x"]), float(box["y"]), float(box["w"]), float(box["h"])
        except (KeyError, TypeError, ValueError):
            continue
        if not all(0 <= v <= 1 for v in (x, y, w, h)):
            continue
        side = box.get("side") if box.get("side") in ("front", "back") else "front"
        entry = {"side": side, "x": x, "y": y, "w": w, "h": h}
        if "font_size" in box:
            try:
                entry["font_size"] = max(6, min(72, int(box["font_size"])))
            except (TypeError, ValueError):
                pass
        if box.get("bold"):
            entry["bold"] = True
        if box.get("square"):
            entry["square"] = True
        if box.get("round"):
            entry["round"] = True
        color = box.get("color")
        if isinstance(color, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            entry["color"] = color
        bg_color = box.get("bg_color")
        if isinstance(bg_color, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", bg_color):
            entry["bg_color"] = bg_color
        cleaned[key] = entry

    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute(
        "UPDATE id_card_templates SET fields=%s, updated_at=CURRENT_TIMESTAMP WHERE company_id=%s",
        (json.dumps(cleaned), cid)
    )
    db.commit()
    cursor.close()
    db.close()
    flash("Field positions saved.", "success")
    return redirect(f"/companies/{cid}/id_card_template/editor")


@admin_views_bp.route("/companies/<int:cid>/id_card_template/reset", methods=["POST"])
@admin_required
def id_card_template_reset(cid):
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute(
        "SELECT COALESCE(front_image,''), COALESCE(back_image,'') FROM id_card_templates WHERE company_id=%s", (cid,)
    )
    row = cursor.fetchone()
    cursor.execute("DELETE FROM id_card_templates WHERE company_id=%s", (cid,))
    db.commit()
    cursor.close()
    db.close()
    if row:
        _delete_company_image(row[0])
        _delete_company_image(row[1])
    flash("ID card template reset to default.", "success")
    return redirect("/settings?tab=company")


@admin_views_bp.route("/announcements", methods=["GET", "POST"])
@admin_required
def announcements_admin():
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            visibility = request.form.get("visibility", "public")
            target_emp = request.form.get("target_employee_id", "").strip() or None
            if visibility == "private" and not target_emp:
                flash("Please select an employee for a private announcement.", "error")
                cursor.close()
                db.close()
                return redirect("/performance?tab=announcements")
            if visibility == "public":
                target_emp = None
            title = request.form["title"]
            content = request.form.get("content", "")
            cursor.execute(
                "INSERT INTO announcements (title, content, priority, visibility, target_employee_id) VALUES (%s,%s,%s,%s,%s)",
                (title, content, request.form.get("priority", "Normal"), visibility, target_emp)
            )
            db.commit()
            snippet = (content[:117] + "...") if len(content) > 120 else content
            if visibility == "private":
                _create_notification('employee', f"📢 {title}", snippet, target_emp)
            else:
                # Batched on the connection already open in this handler,
                # rather than _create_notification's one-connection-per-call
                # pattern, which previously opened/committed/closed a
                # separate pooled connection per active employee.
                cursor.execute("SELECT employee_id FROM employees WHERE is_active=1")
                emp_ids = [eid for (eid,) in cursor.fetchall()]
                if emp_ids:
                    cursor.executemany(
                        "INSERT INTO notifications (recipient_type, employee_id, title, message) "
                        "VALUES ('employee', %s, %s, %s)",
                        [(eid, f"📢 {title}", snippet) for eid in emp_ids]
                    )
                    db.commit()
            flash("Announcement posted.", "success")
        elif action == "delete":
            cursor.execute("DELETE FROM announcements WHERE id=%s", (request.form["ann_id"],))
            db.commit()
            flash("Announcement deleted.", "success")
        cursor.close()
        db.close()
        return redirect("/performance?tab=announcements")
    cursor.close()
    db.close()
    return redirect("/performance?tab=announcements")


@admin_views_bp.route("/test_email", methods=["POST"])
@admin_required
def test_email():
    to_email = request.form.get("test_to", "").strip()
    config = get_email_config()
    if not config:
        return jsonify({"ok": False, "msg": "Email not configured yet."})
    if not to_email:
        return jsonify({"ok": False, "msg": "Enter a test recipient email."})
    try:
        send_email_smtp(
            to_email,
            "Test Email - Attendance System",
            "<h2>Test email from Employee Attendance System</h2><p>Email configuration is working correctly.</p>",
            config,
        )
        return jsonify({"ok": True, "msg": f"Test email sent to {to_email}"})
    except Exception:
        app_log.error("Test email send failed", exc_info=True)
        return jsonify({"ok": False, "msg": "Failed to send test email. Check email settings."})


@admin_views_bp.route("/api/admin/expiring_documents", methods=["GET"])
@admin_required
def api_expiring_documents():
    days = int(request.args.get("days", 30))
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("""
        SELECT d.id, d.employee_id, e.name, d.doc_type, d.original_name, d.expiry_date,
               (d.expiry_date - CURRENT_DATE) AS days_left
        FROM employee_documents d
        JOIN employees e ON e.employee_id = d.employee_id
        WHERE d.expiry_date IS NOT NULL
          AND d.expiry_date >= CURRENT_DATE
          AND d.expiry_date <= CURRENT_DATE + (%s * INTERVAL '1 day')
        ORDER BY d.expiry_date ASC
    """, (days,))
    rows = cursor.fetchall()
    cursor.close()
    db.close()
    return jsonify({
        "ok": True,
        "documents": [
            {"id": r[0], "employee_id": r[1], "employee_name": r[2],
             "doc_type": r[3], "filename": r[4],
             "expiry_date": str(r[5]), "days_left": r[6]}
            for r in rows
        ]
    })


@admin_views_bp.route("/analytics")
@admin_required
def analytics():
    db = get_db_connection()
    cursor = db.cursor(buffered=True)

    cursor.execute("SELECT company_name FROM company_settings LIMIT 1")
    row = cursor.fetchone()
    co = type('Co', (), {'company_name': row[0] if row else 'My Company'})()

    cursor.execute("SELECT COUNT(*) FROM leave_requests WHERE status='Pending'")
    pending_leaves = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM resignation_requests WHERE status='Pending'")
    pending_resignations = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('Open','In Progress')")
    pending_tickets = cursor.fetchone()[0]

    today = datetime.date.today()

    cursor.execute("SELECT COUNT(*) FROM employees")
    total_employees = cursor.fetchone()[0]

    _doj_start = today.replace(day=1)
    _doj_end = datetime.date(today.year + 1, 1, 1) if today.month == 12 else today.replace(month=today.month + 1, day=1)
    cursor.execute(
        "SELECT COUNT(*) FROM employees WHERE date_of_joining >= %s AND date_of_joining < %s",
        (_doj_start, _doj_end)
    )
    new_this_month = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(DISTINCT employee_id) FROM attendance WHERE date=%s AND login_time IS NOT NULL",
        (today,)
    )
    today_present = cursor.fetchone()[0]
    today_absent = max(0, total_employees - today_present)

    cursor.execute("SELECT date FROM holidays")
    all_holidays = {r[0] for r in cursor.fetchall()}

    def _working_days_in_month(y, m):
        _, last_day = calendar.monthrange(y, m)
        days = []
        for d in range(1, last_day + 1):
            dt = datetime.date(y, m, d)
            if dt.weekday() != 6 and dt not in all_holidays:
                days.append(dt)
        return days

    monthly_series = []
    for i in range(5, -1, -1):
        ref = today.replace(day=1) - datetime.timedelta(days=1) * (i * 28)
        ref = ref.replace(day=1)
        y, m = ref.year, ref.month
        working_days = _working_days_in_month(y, m)
        if not working_days:
            continue
        past_days = [d for d in working_days if d <= today]
        total_days = len(past_days)
        if total_days == 0:
            monthly_series.append({
                'month_label': datetime.date(y, m, 1).strftime("%b %Y"),
                'total_days': 0, 'present_days': 0, 'absent_days': 0, 'att_pct': 0
            })
            continue
        month_start = datetime.date(y, m, 1)
        if m == 12:
            month_end = datetime.date(y + 1, 1, 1)
        else:
            month_end = datetime.date(y, m + 1, 1)
        cursor.execute("""
            SELECT COUNT(DISTINCT employee_id) FROM attendance
            WHERE date >= %s AND date < %s AND login_time IS NOT NULL
        """, (month_start, month_end))
        present_records = cursor.fetchone()[0]
        expected = total_days * (total_employees or 1)
        present_pct = round(present_records / expected * 100, 1) if expected else 0
        monthly_series.append({
            'month_label': month_start.strftime("%b %Y"),
            'total_days': total_days,
            'present_days': present_records,
            'absent_days': max(0, expected - present_records),
            'att_pct': present_pct
        })

    if today.month >= 1:
        y, m = today.year, today.month
        working_days = _working_days_in_month(y, m)
        past_days = [d for d in working_days if d <= today]
        total_m = len(past_days)
        if total_m > 0:
            _ms = datetime.date(y, m, 1)
            _me = datetime.date(y + 1, 1, 1) if m == 12 else datetime.date(y, m + 1, 1)
            cursor.execute("""
                SELECT COUNT(DISTINCT employee_id) FROM attendance
                WHERE date >= %s AND date < %s AND login_time IS NOT NULL
            """, (_ms, _me))
            present_m = cursor.fetchone()[0]
            expected_m = total_m * (total_employees or 1)
            avg_attendance_pct = round(present_m / expected_m * 100, 1) if expected_m else 0
        else:
            avg_attendance_pct = 0
    else:
        avg_attendance_pct = 0

    cursor.execute("""
        SELECT department, COUNT(*) as cnt FROM employees
        WHERE department IS NOT NULL AND department != ''
        GROUP BY department ORDER BY cnt DESC
    """)
    dept_data = [{'department': r[0], 'count': r[1]} for r in cursor.fetchall()]

    cursor.execute("""
        SELECT lt.name, COUNT(*) as cnt
        FROM leave_requests lr
        JOIN leave_types lt ON lr.leave_type_id = lt.id
        WHERE lr.status='Approved' AND EXTRACT(YEAR FROM lr.leave_date)=%s
        GROUP BY lt.name ORDER BY cnt DESC
    """, (today.year,))
    leave_by_type = [{'name': r[0], 'count': r[1]} for r in cursor.fetchall()]

    cursor.execute("""
        SELECT e.employee_id, e.name,
               ROUND(COUNT(CASE WHEN a.login_time IS NOT NULL THEN 1 END)::NUMERIC /
                     GREATEST((LEAST((date_trunc('month', %s::date) + INTERVAL '1 month - 1 day')::date, %s::date) - %s::date) + 1, 1) * 100, 1) AS pct
        FROM employees e
        LEFT JOIN attendance a ON e.employee_id=a.employee_id AND EXTRACT(MONTH FROM a.date)=%s AND EXTRACT(YEAR FROM a.date)=%s
        GROUP BY e.employee_id, e.name
        ORDER BY pct DESC LIMIT 5
    """, (datetime.date(today.year, today.month, 1), today, datetime.date(today.year, today.month, 1), today.month, today.year))
    top_present = [{'name': r[1], 'employee_id': r[0], 'pct': float(r[2] or 0)} for r in cursor.fetchall()]

    # gender is Fernet-encrypted (non-deterministic ciphertext — the same
    # plaintext never produces the same bytes twice), so GROUP BY gender at
    # the SQL level would group by ciphertext and put every employee in
    # their own bucket. Aggregate in Python instead, after decrypting.
    cursor.execute("SELECT gender FROM employees WHERE gender IS NOT NULL AND gender != ''")
    _gender_counts = {}
    for (_g_enc,) in cursor.fetchall():
        _g = decrypt_pii(_g_enc)
        if _g:
            _gender_counts[_g] = _gender_counts.get(_g, 0) + 1
    gender_data = [{'gender': g, 'count': c} for g, c in
                   sorted(_gender_counts.items(), key=lambda kv: -kv[1])]

    # Attendance heatmap — last 35 days (5 weeks) present count per day
    heatmap_start = today - datetime.timedelta(days=34)
    cursor.execute("""
        SELECT date, COUNT(DISTINCT employee_id) as cnt
        FROM attendance
        WHERE date BETWEEN %s AND %s AND login_time IS NOT NULL
        GROUP BY date
    """, (heatmap_start, today))
    heatmap_raw = {r[0]: r[1] for r in cursor.fetchall()}
    heatmap_data = []
    for i in range(35):
        d = heatmap_start + datetime.timedelta(days=i)
        heatmap_data.append({'date': d.strftime('%Y-%m-%d'), 'day': d.strftime('%a'), 'count': heatmap_raw.get(d, 0)})

    # Department-wise attendance rate this month
    cursor.execute("""
        SELECT e.department,
               COUNT(DISTINCT e.employee_id) as total_emp,
               COUNT(DISTINCT CASE WHEN a.login_time IS NOT NULL THEN a.employee_id END) as present_emp
        FROM employees e
        LEFT JOIN attendance a ON e.employee_id=a.employee_id AND EXTRACT(MONTH FROM a.date)=%s AND EXTRACT(YEAR FROM a.date)=%s
        WHERE e.department IS NOT NULL AND e.department != ''
        GROUP BY e.department
        ORDER BY present_emp DESC
    """, (today.month, today.year))
    dept_attendance = []
    for r in cursor.fetchall():
        dept, total, present = r[0], r[1], r[2]
        pct = round(present / total * 100, 1) if total else 0
        dept_attendance.append({'dept': dept, 'total': total, 'present': present, 'pct': pct})

    # Late arrival trend — last 14 days
    late_start = today - datetime.timedelta(days=13)
    cursor.execute("""
        SELECT date, COUNT(DISTINCT employee_id) as late_cnt
        FROM attendance
        WHERE date BETWEEN %s AND %s AND status='Late Login'
        GROUP BY date ORDER BY date ASC
    """, (late_start, today))
    late_raw = {r[0]: r[1] for r in cursor.fetchall()}
    late_trend = []
    for i in range(14):
        d = late_start + datetime.timedelta(days=i)
        late_trend.append({'date': d.strftime('%d %b'), 'count': late_raw.get(d, 0)})

    # Employee retention — tenure bands
    cursor.execute("SELECT date_of_joining FROM employees WHERE date_of_joining IS NOT NULL")
    retention = {'0-6m': 0, '6-12m': 0, '1-3y': 0, '3y+': 0}
    for (doj,) in cursor.fetchall():
        if isinstance(doj, str):
            try:
                doj = datetime.date.fromisoformat(doj)
            except Exception as _e:
                app_log.debug("Skipping bad date_of_joining value %r: %s", doj, _e)
                continue
        months = (today.year - doj.year) * 12 + (today.month - doj.month)
        if months < 6:
            retention['0-6m'] += 1
        elif months < 12:
            retention['6-12m'] += 1
        elif months < 36:
            retention['1-3y'] += 1
        else:
            retention['3y+'] += 1

    # Smart Alerts Panel
    smart_alerts = []

    # 1. Employees absent 3+ consecutive working days
    working_days_back = []
    for i in range(1, 15):
        d = today - datetime.timedelta(days=i)
        if d.weekday() != 6 and d not in all_holidays:
            working_days_back.append(d)
        if len(working_days_back) == 5:
            break
    last3 = working_days_back[:3]
    if len(last3) == 3:
        cursor.execute("""
            SELECT e.name, e.employee_id
            FROM employees e
            WHERE NOT EXISTS (
                SELECT 1 FROM attendance a
                WHERE a.employee_id = e.employee_id
                AND a.date IN (%s,%s,%s)
                AND a.login_time IS NOT NULL
            )
        """, (last3[0], last3[1], last3[2]))
        absent3 = cursor.fetchall()
        if absent3:
            names = ', '.join(r[1] for r in absent3[:3])
            extra = f' +{len(absent3)-3} more' if len(absent3) > 3 else ''
            smart_alerts.append({
                'level': 'danger',
                'icon': 'ti-user-off',
                'title': f'{len(absent3)} employee{"s" if len(absent3)>1 else ""} absent for 3+ consecutive days',
                'detail': names + extra,
                'link': '/monthly_report'
            })

    # 2. Leave requests spike this week vs last week
    week_start = today - datetime.timedelta(days=today.weekday())
    last_week_start = week_start - datetime.timedelta(days=7)
    cursor.execute("SELECT COUNT(*) FROM leave_requests WHERE leave_date >= %s", (week_start,))
    leaves_this_week = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM leave_requests WHERE leave_date >= %s AND leave_date < %s",
                   (last_week_start, week_start))
    leaves_last_week = cursor.fetchone()[0]
    if leaves_last_week > 0 and leaves_this_week > leaves_last_week * 1.4:
        pct_jump = round((leaves_this_week - leaves_last_week) / leaves_last_week * 100)
        smart_alerts.append({
            'level': 'warning',
            'icon': 'ti-calendar-up',
            'title': f'Leave requests spiked {pct_jump}% compared to last week',
            'detail': f'{leaves_this_week} requests this week vs {leaves_last_week} last week',
            'link': '/leave_requests'
        })

    # 3. Employees with attendance below 50% this month
    cursor.execute("""
        SELECT e.name, e.employee_id,
               COUNT(CASE WHEN a.login_time IS NOT NULL THEN 1 END) as present_days,
               COUNT(a.date) as total_days
        FROM employees e
        LEFT JOIN attendance a ON e.employee_id=a.employee_id
            AND EXTRACT(MONTH FROM a.date)=%s AND EXTRACT(YEAR FROM a.date)=%s
        GROUP BY e.employee_id, e.name
        HAVING COUNT(a.date) > 0
           AND (COUNT(CASE WHEN a.login_time IS NOT NULL THEN 1 END)::NUMERIC / COUNT(a.date)) < 0.5
    """, (today.month, today.year))
    low_att = cursor.fetchall()
    if low_att:
        names = ', '.join(r[1] for r in low_att[:3])
        extra = f' +{len(low_att)-3} more' if len(low_att) > 3 else ''
        smart_alerts.append({
            'level': 'warning',
            'icon': 'ti-chart-bar-off',
            'title': f'{len(low_att)} employee{"s" if len(low_att)>1 else ""} below 50% attendance this month',
            'detail': names + extra,
            'link': '/monthly_report'
        })

    # 4. High pending leave approvals
    if pending_leaves >= 5:
        smart_alerts.append({
            'level': 'warning',
            'icon': 'ti-clock-pause',
            'title': f'{pending_leaves} leave requests pending approval',
            'detail': 'Employees may be waiting — review and approve',
            'link': '/leave_requests'
        })

    # 5. New joiners who have never logged in
    cursor.execute("""
        SELECT e.name, e.employee_id FROM employees e
        WHERE e.date_of_joining >= %s
        AND NOT EXISTS (SELECT 1 FROM attendance a WHERE a.employee_id=e.employee_id AND a.login_time IS NOT NULL)
    """, (today - datetime.timedelta(days=30),))
    never_logged = cursor.fetchall()
    if never_logged:
        names = ', '.join(r[1] for r in never_logged[:3])
        extra = f' +{len(never_logged)-3} more' if len(never_logged) > 3 else ''
        smart_alerts.append({
            'level': 'info',
            'icon': 'ti-user-question',
            'title': f'{len(never_logged)} new joiner{"s" if len(never_logged)>1 else ""} {"have" if len(never_logged)>1 else "has"} never logged attendance',
            'detail': names + extra,
            'link': '/employees'
        })

    # 6. Pending overtime approvals
    cursor.execute("SELECT COUNT(*) FROM overtime_records WHERE status='Pending'")
    ot_pending_count = cursor.fetchone()[0]
    if ot_pending_count >= 3:
        smart_alerts.append({
            'level': 'info',
            'icon': 'ti-clock-bolt',
            'title': f'{ot_pending_count} overtime requests waiting for approval',
            'detail': 'Review pending OT requests from the dashboard',
            'link': '/overtime'
        })

    # 6. Documents expiring in next 30 days
    cursor.execute("""
        SELECT COUNT(*) FROM employee_documents
        WHERE expiry_date IS NOT NULL
          AND expiry_date >= CURRENT_DATE
          AND expiry_date <= CURRENT_DATE + INTERVAL '30 days'
    """)
    expiring_docs = cursor.fetchone()[0]
    if expiring_docs > 0:
        smart_alerts.append({
            'level': 'warning',
            'icon': 'ti-file-alert',
            'title': f'{expiring_docs} employee document{"s" if expiring_docs > 1 else ""} expiring within 30 days',
            'detail': 'Review and renew documents before they expire',
            'link': '/documents'
        })

    if not smart_alerts:
        smart_alerts.append({
            'level': 'success',
            'icon': 'ti-circle-check',
            'title': 'All systems healthy — no anomalies detected',
            'detail': 'Attendance, leaves and approvals are all on track',
            'link': ''
        })

    cursor.close()
    db.close()

    return render_template("analytics.html",
                           co=co,
                           pending_leaves=pending_leaves,
                           pending_resignations=pending_resignations,
                           pending_tickets=pending_tickets,
                           total_employees=total_employees,
                           new_this_month=new_this_month,
                           today_present=today_present,
                           today_absent=today_absent,
                           avg_attendance_pct=avg_attendance_pct,
                           monthly_series=monthly_series,
                           dept_data=dept_data,
                           leave_by_type=leave_by_type,
                           top_present=top_present,
                           gender_data=gender_data,
                           heatmap_data=heatmap_data,
                           dept_attendance=dept_attendance,
                           late_trend=late_trend,
                           retention=retention,
                           smart_alerts=smart_alerts,
                           active_nav="analytics",
                           )


@admin_views_bp.route("/org_chart")
@admin_required
def org_chart_page():
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    active_cid = session.get("active_company_id")
    _co_sub, _co_args = co_scope_subquery(active_cid)
    cursor.execute(f"SELECT COUNT(*) FROM leave_requests WHERE status='Pending' {_co_sub}", _co_args)  # nosec B608
    pending_leaves = cursor.fetchone()[0]
    cursor.execute(f"SELECT COUNT(*) FROM resignation_requests WHERE status='Pending' {_co_sub}", _co_args)  # nosec B608
    pending_resignations = cursor.fetchone()[0]
    cursor.execute(f"SELECT COUNT(*) FROM tickets WHERE status='Open' {_co_sub}", _co_args)  # nosec B608
    pending_tickets = cursor.fetchone()[0]
    if active_cid:
        cursor.execute(
            "SELECT DISTINCT department FROM employees WHERE department IS NOT NULL AND department != '' AND company_id=%s ORDER BY department", (active_cid,))
    else:
        cursor.execute(
            "SELECT DISTINCT department FROM employees WHERE department IS NOT NULL AND department != '' ORDER BY department")
    departments = [r[0] for r in cursor.fetchall()]
    co = get_company_settings()
    cursor.close()
    db.close()
    return render_template("org_chart.html",
                           co=co, departments=departments,
                           pending_leaves=pending_leaves,
                           pending_resignations=pending_resignations,
                           pending_tickets=pending_tickets,
                           )


@admin_views_bp.route("/audit_logs")
def audit_logs_redirect():
    return redirect("/admin_tools?tab=audit_logs")


@admin_views_bp.route("/admin_tools")
@admin_required
def admin_tools():
    tab = request.args.get("tab", "org_chart")
    db = get_db_connection()
    cursor = db.cursor(buffered=True)

    active_cid = session.get("active_company_id")
    _co_sub, _co_args = co_scope_subquery(active_cid)

    cursor.execute(f"SELECT COUNT(*) FROM leave_requests WHERE status='Pending' {_co_sub}", _co_args)  # nosec B608
    pending_leaves = cursor.fetchone()[0]
    cursor.execute(f"SELECT COUNT(*) FROM resignation_requests WHERE status='Pending' {_co_sub}", _co_args)  # nosec B608
    pending_resignations = cursor.fetchone()[0]
    cursor.execute(f"SELECT COUNT(*) FROM tickets WHERE status='Open' {_co_sub}", _co_args)  # nosec B608
    pending_tickets = cursor.fetchone()[0]

    if active_cid:
        cursor.execute(
            "SELECT DISTINCT department FROM employees WHERE department IS NOT NULL AND department != '' AND company_id=%s ORDER BY department", (active_cid,))
    else:
        cursor.execute(
            "SELECT DISTINCT department FROM employees WHERE department IS NOT NULL AND department != '' ORDER BY department")
    departments = [r[0] for r in cursor.fetchall()]

    # Audit logs — filter by employees of the active company when set
    actor_f = request.args.get("actor", "").strip()
    action_f = request.args.get("action", "").strip()
    date_f = request.args.get("date", "").strip()
    page = max(1, int(request.args.get("page", 1)))
    per_page = 50
    conditions, params = [], []
    if actor_f:
        conditions.append("actor LIKE %s")
        params.append(f"%{actor_f}%")
    if action_f:
        conditions.append("action LIKE %s")
        params.append(f"%{action_f}%")
    if date_f:
        conditions.append("DATE(created_at) = %s")
        params.append(date_f)
    if active_cid:
        # Show logs where the target_id is an employee of the active company,
        # OR the actor is an employee of the active company, OR it's an admin action
        conditions.append(
            "(target_id IN (SELECT employee_id FROM employees WHERE company_id=%s) "
            "OR actor IN (SELECT employee_id FROM employees WHERE company_id=%s) "
            "OR actor_type='admin')"
        )
        params += [active_cid, active_cid]
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    cursor.execute(f"SELECT COUNT(*) FROM audit_logs {where}", params)  # nosec B608
    total = cursor.fetchone()[0]
    total_pages = max(1, (total + per_page - 1) // per_page)
    offset = (page - 1) * per_page
    cursor.execute(
        f"""SELECT id, actor, actor_type, action, target_table, target_id,
                   detail, ip_address, created_at
            FROM audit_logs {where} ORDER BY created_at DESC LIMIT %s OFFSET %s""",  # nosec B608
        params + [per_page, offset]
    )
    logs = cursor.fetchall()
    if active_cid:
        cursor.execute(
            "SELECT DISTINCT actor FROM audit_logs WHERE actor IN "
            "(SELECT employee_id FROM employees WHERE company_id=%s) OR actor_type='admin' ORDER BY actor LIMIT 200",
            (active_cid,)
        )
    else:
        cursor.execute("SELECT DISTINCT actor FROM audit_logs ORDER BY actor LIMIT 200")
    actors = [r[0] for r in cursor.fetchall()]

    co = get_company_settings()
    cursor.close()
    db.close()
    return render_template("admin_tools.html",
                           co=co, tab=tab, departments=departments,
                           logs=logs, total=total, page=page, total_pages=total_pages,
                           actor_f=actor_f, action_f=action_f, date_f=date_f, actors=actors,
                           pending_leaves=pending_leaves, pending_resignations=pending_resignations,
                           pending_tickets=pending_tickets,
                           active_nav="admin_tools",
                           )


@admin_views_bp.route("/api/org_chart_data")
@admin_required
def api_org_chart_data():
    dept_filter = request.args.get("dept", "")
    active_cid = session.get("active_company_id")
    db = get_db_connection()
    cursor = db.cursor()
    query = """
        SELECT e.employee_id, e.name, e.role, e.department,
               e.manager_id, e.face_image,
               COALESCE(e.manager_name, '') as manager_name
        FROM employees e
        WHERE COALESCE(e.is_active, 1) = 1
    """
    params = []
    if active_cid:
        query += " AND e.company_id = %s"
        params.append(active_cid)
    if dept_filter:
        query += " AND e.department = %s"
        params.append(dept_filter)
    query += " ORDER BY e.name"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    cursor.close()
    db.close()

    emp_map = {}
    for r in rows:
        emp_map[r[0]] = {
            "id": r[0],
            "name": r[1],
            "role": r[2] or "Employee",
            "department": r[3] or "",
            "manager_id": r[4],
            "has_photo": bool(r[5] and os.path.exists(r[5])),
            "children": []
        }

    roots = []
    for emp in emp_map.values():
        mid = emp["manager_id"]
        if mid and mid in emp_map and mid != emp["id"]:
            emp_map[mid]["children"].append(emp)
        else:
            roots.append(emp)

    # Sort children alphabetically
    def sort_tree(node):
        node["children"].sort(key=lambda x: x["name"])
        for child in node["children"]:
            sort_tree(child)
        return node

    roots.sort(key=lambda x: x["name"])
    tree = [sort_tree(r) for r in roots]
    return jsonify({"ok": True, "tree": tree, "total": len(emp_map)})
