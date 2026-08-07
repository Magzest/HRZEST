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
    Blueprint, request, session, redirect, jsonify, render_template, flash, abort, g,
)

from database import get_db_connection, transaction
from extensions import app, app_log, log_security_event, limiter
from utils.auth import (
    admin_required, role_required, require_email_2fa, EMAIL_2FA_WINDOW_SEC,
    email_settings_step_up_refresh, email_settings_step_up_clear,
    security_settings_step_up_clear,
    check_password_hash,
)
from utils.helpers import (
    get_company_settings, get_co_features, _upsert_co_feature,
    _upsert_co_features, _safe_redirect, co_scope_subquery, co_scope_column,
    _create_notification, encrypt_pii, decrypt_pii, invalidate_companies_cache,
    _validate_image_file,
)
from utils.plan_limits import check_feature_allowed, set_tenant_plan, PLAN_TIERS
from utils.email_utils import get_email_config, send_email_smtp
from utils.totp import (
    get_or_create_admin_totp_secret, mark_totp_enabled, verify_totp_code, totp_qr_data_uri,
    reset_admin_totp_secret,
)
from utils.attendance_utils import _td_to_time
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
# Maps toggle_auth_method()'s `method` values to utils/plan_limits.py's
# tier feature keys. "password" is deliberately absent -- password login
# stays global/unrestricted regardless of plan (see the _cfs_map comment
# in toggle_auth_method below).
_TOGGLE_PLAN_FEATURE_MAP = {
    "fingerprint": "fingerprint", "qr": "qr", "face": "face", "location": "geo",
}
# Same idea for toggle_feature()'s `feature` values.
_TOGGLE_FEATURE_PLAN_MAP = {
    "face_auth_enabled": "face", "geo_enabled": "geo", "qr_enabled": "qr",
    "pin_enabled": "pin", "fingerprint_enabled": "fingerprint",
    "biometric_enabled": "biometric",
}


@admin_views_bp.route("/admin")
@admin_required
def admin():
    return redirect("/employees")


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
    before_request hook redirects every admin/manager session without TOTP
    enrolled here, and here only, until they complete it (soc_analyst
    sessions can't reach this unenrolled in the first place -- /mfa_login_verify
    already marks TOTP enrolled before that session exists at all). Not a
    TOTP step-up gate -- an unenrolled admin can't pass a step-up gate they
    haven't set up yet, so this page (and the /api/settings/2fa/setup +
    /api/settings/2fa/enable it calls) is deliberately reachable on
    @admin_required alone."""
    return render_template("admin_mfa_required.html")


@admin_views_bp.route("/settings")
@role_required("admin")
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
        "SELECT COALESCE(working_days,'Mon,Tue,Wed,Thu,Fri'), COALESCE(company_name,''), "
        "COALESCE(timezone,'Asia/Kolkata'), office_lat, office_lon FROM company_settings LIMIT 1")
    _gset = cursor.fetchone()
    features = {
        "face_auth": fr["face_auth_enabled"],
        "geo": fr["geo_enabled"],
        "geo_radius": fr["geo_radius"],
        # Always schema-wide (one physical office per tenant) -- unlike
        # everything else in this dict, never sourced from company_feature_settings.
        "office_lat": _gset[3] if _gset else None,
        "office_lon": _gset[4] if _gset else None,
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
@role_required("admin")
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
@role_required("admin")
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
@role_required("admin")
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



@admin_views_bp.route("/save_default_onboarding_template", methods=["POST"])
@role_required("admin")
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
@role_required("admin")
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
@role_required("admin")
def toggle_auth_method():
    method = request.form.get("method", "")
    enabled = request.form.get("enabled", "0") == "1"
    if method not in _TOGGLE_COLUMN_MAP:
        flash("Invalid authentication method.", "danger")
        return redirect("/settings?tab=attendance")
    column = _TOGGLE_COLUMN_MAP[method]
    label = _TOGGLE_LABEL_MAP[method]
    # Turning a method OFF is always allowed regardless of plan -- only
    # enabling something new is a billing decision. "password" isn't a
    # plan_limits feature key (password auth stays global, see _cfs_map
    # below), so it's never plan-gated.
    plan_feature_key = _TOGGLE_PLAN_FEATURE_MAP.get(method)
    if enabled and plan_feature_key:
        _plan_ok, _plan_err = check_feature_allowed(g.tenant_db, plan_feature_key)
        if not _plan_ok:
            flash(_plan_err, "danger")
            return redirect("/settings?tab=attendance")
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
@role_required("admin")
def toggle_fingerprint():
    enabled = request.form.get("enabled", "0") == "1"
    if enabled:
        _plan_ok, _plan_err = check_feature_allowed(g.tenant_db, "fingerprint")
        if not _plan_ok:
            flash(_plan_err, "danger")
            return redirect("/settings?tab=attendance")
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
@role_required("admin")
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
@role_required("admin")
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
@role_required("admin")
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
    plan_feature_key = _TOGGLE_FEATURE_PLAN_MAP.get(feature)
    if value and plan_feature_key:
        _plan_ok, _plan_err = check_feature_allowed(g.tenant_db, plan_feature_key)
        if not _plan_ok:
            return jsonify({"ok": False, "error": _plan_err}), 403
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
@role_required("admin")
def save_geo_radius():
    try:
        radius = int(request.form.get("geo_radius", 100))
        if not (50 <= radius <= 5000):
            raise ValueError
    except (ValueError, TypeError):
        flash("Geo radius must be between 50 and 5000 metres.", "danger")
        return redirect("/settings?tab=attendance")
    # Office lat/lon are optional -- both blank means "not configured yet",
    # which utils/attendance_utils.py's is_within_office_range() treats as
    # geofencing being a no-op regardless of the location_enabled toggle.
    lat_raw = request.form.get("office_lat", "").strip()
    lon_raw = request.form.get("office_lon", "").strip()
    office_lat = office_lon = None
    if lat_raw or lon_raw:
        try:
            office_lat = float(lat_raw)
            office_lon = float(lon_raw)
            if not (-90 <= office_lat <= 90 and -180 <= office_lon <= 180):
                raise ValueError
        except (ValueError, TypeError):
            flash("Office location must be a valid latitude/longitude pair.", "danger")
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
    # Office coordinates are always schema-wide (one physical office per
    # tenant), regardless of which sub-company is active -- unlike radius,
    # which follows the existing per-company_id pattern above.
    if lat_raw or lon_raw:
        db = get_db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute("UPDATE company_settings SET office_lat=%s, office_lon=%s", (office_lat, office_lon))
        db.commit()
        cursor.close()
        db.close()
    flash("Attendance settings saved.", "success")
    return redirect("/settings?tab=attendance")


# save_security_settings retired: the Security tab is now the MFA-gated
# hub above (api_security_settings_session_timeout does the same DB write,
# JSON-based, reachable only after the step-up gate reveals the row).


@admin_views_bp.route("/switch_company", methods=["POST"])
@role_required("admin")
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
@role_required("admin")
def clear_company():
    session.pop("active_company_id", None)
    flash("Viewing all companies.", "success")
    return redirect(_safe_redirect(request.form.get("next", ""), "/admin"))


@admin_views_bp.route("/set_company_pin", methods=["POST"])
@role_required("admin")
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
@role_required("admin")
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
@role_required("admin")
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
@role_required("admin")
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
@role_required("admin")
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
@role_required("admin")
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
@role_required("admin")
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
@role_required("admin")
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
@role_required("admin")
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
@role_required("admin")
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
@role_required("admin")
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
@role_required("admin")
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
@role_required("admin")
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


@admin_views_bp.route("/admin_tools")
@role_required("admin")
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

    co = get_company_settings()
    cursor.close()
    db.close()
    return render_template("admin_tools.html",
                           co=co, tab=tab, departments=departments,
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


# ── Self-Service Plan Upgrade Endpoint ─────────────────────────────────────────
@admin_views_bp.route("/api/admin/upgrade_plan", methods=["POST"])
@admin_required
def api_upgrade_plan():
    """Self-service endpoint for admins to change their tenant's subscription
    plan (no payment gateway yet -- see utils/plan_limits.py module
    docstring; this is a straight write, not tied to any billing charge)."""
    data = request.get_json() or {}
    new_plan = data.get("plan", "").strip().lower()
    if not new_plan:
        new_plan = request.form.get("plan", "").strip().lower()

    if new_plan not in PLAN_TIERS:
        return jsonify({"ok": False, "msg": f"Invalid plan '{new_plan}'. "
                        f"Must be one of: {', '.join(PLAN_TIERS)}."}), 400

    set_tenant_plan(g.tenant_db, new_plan)
    msg = f"Plan successfully updated to {PLAN_TIERS[new_plan]['display_name']}."
    flash(msg, "success")
    return jsonify({"ok": True, "msg": msg, "plan": new_plan})


# ── Instant SMTP Connection Test Endpoint ─────────────────────────────────────
@admin_views_bp.route("/api/admin/test_email", methods=["POST"])
@admin_required
def api_test_email():
    """Send a diagnostic test email using current SMTP configuration."""
    data = request.get_json() or {}
    target_email = data.get("to_email", "").strip() or request.form.get("to_email", "").strip()

    if not target_email:
        target_email = session.get("admin_email") or session.get("email")

    if not target_email:
        return jsonify({"ok": False, "msg": "Target email address is required."}), 400

    cfg = get_email_config()
    if not cfg or not cfg.get("host"):
        return jsonify({"ok": False, "msg": "No SMTP configuration found in system. Please configure SMTP first."}), 400

    subject = "⚡ SMTP Connection Test — Employee Attendance Platform"
    now_str = datetime.datetime.now().strftime("%d %b %Y, %I:%M %p")
    html_body = f"""
    <div style="font-family: Arial, sans-serif; padding: 24px; background: #f8fafc; border-radius: 12px;">
      <h2 style="color: #16a34a; margin-top: 0;">✅ SMTP Connection Test Successful!</h2>
      <p style="color: #334155; font-size: 14px;">
        Your email server configuration is working cleanly. Automated daily attendance reports and security alerts are operational.
      </p>
      <p style="font-size: 12px; color: #64748b;">
        <strong>Host:</strong> {cfg.get('host')}:{cfg.get('port')}<br>
        <strong>Timestamp:</strong> {now_str}
      </p>
    </div>
    """

    try:
        err = send_email_smtp(target_email, subject, html_body, cfg)
        if err:
            return jsonify({"ok": False, "msg": f"SMTP delivery error: {err}"}), 500
        return jsonify({"ok": True, "msg": f"Test email successfully delivered to {target_email}!"})
    except Exception as exc:
        app_log.exception("api_test_email: SMTP delivery exception")
        return jsonify({"ok": False, "msg": f"SMTP test failed: {exc}"}), 500

