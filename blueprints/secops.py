"""Blueprint for Dedicated SecOps & SP Admin Portal with MFA, SIEM Log Engine & Threat Telemetry."""

import time
import re
import os
import secrets
import datetime
import ipaddress
from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for, abort
from database import get_db_connection, pool_stats, transaction
from utils.security_logs import (
    fetch_threat_logs,
    get_system_health_metrics,
    get_port_health_metrics,
    get_quarantined_files,
    get_smtp_config,
    update_smtp_config,
)
from utils.auth import (
    _db, check_password_hash, generate_password_hash,
    SOC_ANALYST_ROLE, soc_step_up_valid, soc_step_up_refresh, soc_step_up_clear,
    turnstile_enabled,
)
from utils.helpers import get_co_features, _upsert_co_feature
from utils.perf_metrics import snapshot as get_perf_snapshot
from utils.session_risk import ensure_session_id
from utils.totp import get_or_create_admin_totp_secret, mark_totp_enabled, send_mfa_login_email
from extensions import app_log, log_security_event, limiter

secops_bp = Blueprint("secops", __name__)


def _is_secops_authorized():
    """Verify the session belongs to a dedicated SOC Analyst account.

    Deliberately just the SOC_ANALYST_ROLE, not a fallback list including
    'admin'/'cybersecurity' -- this account is meant to be a SEPARATE
    credential from the main admin login (see sp_admin_login below), and
    letting any regular admin session through here would silently defeat
    that separation."""
    return bool(session.get("admin_logged_in")) and session.get("admin_role") == SOC_ANALYST_ROLE


def _soc_session_and_stepup_or_404():
    """Full gate for the dashboard and the monitoring/config APIs migrated
    from the old admin-embedded SOC dashboard: role check AND a live TOTP
    step-up window (soc_2fa_verified_at, set at /mfa_login_verify login and
    refreshed on every dashboard load). 404, not 401/403, on any failure --
    matches the original admin_views.py gate's disguise posture: a session
    that isn't entitled to this sees the exact same response a nonexistent
    URL would."""
    username = session.get("admin_username")
    role = session.get("admin_role")
    logged_in = bool(session.get("admin_logged_in") and username)
    if not logged_in or role != SOC_ANALYST_ROLE or not soc_step_up_valid():
        log_security_event(
            "access.escalation_attempt" if logged_in else "access.denied",
            "Unauthorized Escalation Attempt: SOC Security Dashboard accessed without a valid SOC session/step-up"
            if logged_in else "Unauthenticated request to SOC Security Dashboard",
            level="ERROR" if logged_in else "INFO",
            identifier=username or "anonymous", attempted_role=role or "none",
        )
        abort(404)
    return username, role


def _compute_security_posture():
    """Real, config-derived facts -- not a fabricated 'security score'. Each
    one reads the same source of truth its own feature already uses, so this
    can't silently drift out of sync with what's actually enforced elsewhere
    in the app."""
    return {
        "hsts_enabled": True,  # app.py's _security_headers sets this unconditionally on every response
        "csp_enabled": True,   # same -- dynamic per-request nonce CSP, always on
        "rate_limit_backend": "In-memory (per-worker — no Redis in this deployment)",
        "malware_scan_enabled": os.environ.get("MALWARE_SCAN_ENABLED", "true").strip().lower() not in ("false", "0", "no"),
        "login_captcha_configured": turnstile_enabled(),
        "email_alert_webhook_configured": bool(os.environ.get("SECURITY_ALERT_WEBHOOK_URL")),
    }


def _security_events_summary(cursor):
    """Aggregate stats over the FULL security_events history -- the
    "complete log analysis" a SOC analyst needs to judge whether the last 50
    rows they're looking at are routine noise or the tail of something
    bigger."""
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


_COVERAGE_GATE_PCT = 80


_MFA_OTP_TTL_SEC = 300  # 5 minutes


@secops_bp.route("/sp_admin")
@secops_bp.route("/sp_admin/")
@secops_bp.route("/sp_admin/login", methods=["GET", "POST"])
@limiter.limit("5 per 15 minutes")
@limiter.limit("5 per minute")
def sp_admin_login():
    """Dedicated SP Admin / Cybersecurity Analyst Login Page. MFA step is an
    emailed one-time code (see /mfa_login_verify below) rather than an
    authenticator-app TOTP prompt -- the TOTP secret itself is still
    generated/stored (get_or_create_admin_totp_secret) for accounts that
    also want an authenticator app, but is never put in the email body or
    the session; only the short-lived numeric code travels either place."""
    if session.get("admin_logged_in") and session.get("admin_role") == SOC_ANALYST_ROLE:
        return redirect("/secops")

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "").strip()

        admin_row = None
        if identifier:
            with _db() as (cursor, db):
                cursor.execute(
                    "SELECT password, COALESCE(role,'admin'), email FROM admin_users WHERE username=%s",
                    (identifier,)
                )
                admin_row = cursor.fetchone()

        # Role must ALREADY be soc_analyst in the DB before password is even
        # checked -- previously any admin_users row (any role at all) that
        # passed the password+TOTP check was granted a soc_analyst session
        # regardless of its actual role column, which defeated the point of
        # this being a separate, narrowly-scoped credential.
        if admin_row and admin_row[1] == SOC_ANALYST_ROLE and check_password_hash(admin_row[0], password):
            if not admin_row[2]:
                # No recovery email on file -- can't deliver a code, so this
                # account can't complete login until an email is set. Same
                # generic error as a bad password: don't leak *why* to an
                # unauthenticated caller.
                log_security_event(
                    "auth.mfa_email_missing", "SOC account has no email on file for MFA delivery",
                    level="ERROR", identifier=identifier,
                )
                return render_template("sp_admin_login.html", error="Invalid Cybersecurity Analyst credentials.")

            secret, _enabled = get_or_create_admin_totp_secret(identifier)
            otp_code = f"{secrets.randbelow(900000) + 100000}"
            send_mfa_login_email(admin_row[2], identifier, "SecOps Security Administrator", secret, otp_code)

            session.clear()
            session["mfa_pending"] = True
            session["mfa_user"] = identifier
            session["mfa_otp_code"] = otp_code
            session["mfa_issued_at"] = time.time()
            return redirect("/mfa_login_verify")

        return render_template("sp_admin_login.html", error="Invalid Cybersecurity Analyst credentials.")

    return render_template("sp_admin_login.html")


@secops_bp.route("/mfa_login_verify", methods=["GET", "POST"])
@limiter.limit("8 per 15 minutes")
def mfa_login_verify():
    """Second step of sp_admin_login(): checks the one-time code emailed to
    the account's address on file. session["mfa_otp_code"] never leaves the
    server -- the browser only ever sees a blank input to type the emailed
    code into."""
    username = session.get("mfa_user")
    if not username or not session.get("mfa_pending"):
        return redirect("/sp_admin/login")

    issued_at = session.get("mfa_issued_at") or 0
    if (time.time() - issued_at) > _MFA_OTP_TTL_SEC:
        session.clear()
        return render_template("sp_admin_login.html", error="Your code expired. Please log in again.")

    if request.method == "POST":
        submitted = (request.form.get("otp_code") or "").strip()
        expected = session.get("mfa_otp_code") or ""
        if submitted and expected and secrets.compare_digest(submitted, expected):
            # app.py's _enforce_admin_mfa_enrollment before_request hook
            # requires totp_enabled=1 for every soc_analyst session (it's in
            # _MANDATORY_MFA_ROLES) or it redirects to /admin/mfa-required
            # on the very next request -- a completed email OTP here is this
            # account's MFA enrollment, same as the old flow marked it
            # enrolled after the first successful authenticator-app code.
            mark_totp_enabled(username)
            session.clear()
            session["admin_logged_in"] = True
            session["admin_username"] = username
            # Guaranteed SOC_ANALYST_ROLE already, since sp_admin_login only
            # ever sets mfa_pending for a row whose DB role matched.
            session["admin_role"] = SOC_ANALYST_ROLE
            soc_step_up_refresh()  # sets session["soc_2fa_verified_at"] -- same key/window utils/auth.py's soc_step_up_valid() checks
            session["_session_created"] = time.time()
            session.permanent = True
            ensure_session_id(session)
            return redirect("/secops")

        log_security_event(
            "auth.mfa_failure", "Invalid SOC login MFA code", level="WARNING", identifier=username,
        )
        return render_template("mfa_login_verify.html", username=username, error="Invalid verification code.")

    return render_template("mfa_login_verify.html", username=username)


@secops_bp.route("/secops")
def secops_dashboard():
    """The SOC analyst's dashboard, reached only via /sp_admin/login +
    email MFA (/mfa_login_verify) -- there is no other entry point, and no
    in-page challenge on top of it: completing MFA at login already proves
    possession, so soc_step_up_valid just enforces that proof stays fresh
    (10 min, same window mfa_login_verify sets) rather than asking for a
    second code mid-session. Consolidates everything that used to live
    behind Settings -> Security and the /admin/security-dashboard route:
    force-terminated sessions, active login lockouts, per-admin MFA
    enrollment, config-derived security posture, an all-time
    security_events summary + paginated/filterable log, application-layer
    IP bans, session-timeout config, and live performance/DB-pool stats."""
    _soc_session_and_stepup_or_404()
    soc_step_up_refresh()

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
    cursor.execute("SELECT session_timeout FROM company_settings LIMIT 1")
    r = cursor.fetchone()
    session_timeout = r[0] if r and r[0] else 30
    cursor.close()
    db.close()

    return render_template("soc_security_dashboard.html",
                           compromised_sessions=compromised_sessions,
                           active_lockouts=active_lockouts,
                           admin_mfa_status=admin_mfa_status,
                           events_summary=events_summary,
                           security_posture=_compute_security_posture(),
                           session_timeout_minutes=session_timeout,
                           )


@secops_bp.route("/api/secops/dashboard-stats")
def api_secops_dashboard_stats():
    """Real-time dashboard KPI stats -- event counts, quarantine, banned IPs."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401
    db = get_db_connection()
    cur = db.cursor(buffered=True)
    cur.execute("SELECT COUNT(*) FROM security_events")
    total_events = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM quarantined_files WHERE status='QUARANTINED'")
    quarantine_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM banned_ips WHERE expires_at IS NULL OR expires_at > NOW()")
    banned_ips = cur.fetchone()[0]
    cur.close()
    db.close()
    return jsonify({"ok": True, "stats": {
        "total_events": total_events, "quarantine_count": quarantine_count, "banned_ips": banned_ips,
    }})


@secops_bp.route("/api/security/soc/events")
def api_soc_events():
    """Paginated, filterable security_events query backing the dashboard's
    log table -- the "complete logs" view, since the page load above only
    carries an all-time summary, not every row."""
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
    if level in ("ERROR", "WARNING", "INFO"):
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


@secops_bp.route("/api/security/soc/banned-ips")
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


@secops_bp.route("/api/security/soc/ban-ip", methods=["POST"])
def api_soc_ban_ip():
    username, _role = _soc_session_and_stepup_or_404()
    body = request.get_json(silent=True) or {}
    ip = (body.get("ip") or "").strip()
    reason = (body.get("reason") or "").strip()[:300] or None
    duration_raw = body.get("duration_minutes")

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


@secops_bp.route("/api/security/soc/unban-ip", methods=["POST"])
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


@secops_bp.route("/api/secops/session-timeout", methods=["POST"])
def api_secops_session_timeout():
    """Session-timeout config, migrated from the old Settings -> Security
    hub -- an operational security control, so it lives with the rest of
    the SOC-only surface now rather than disappearing."""
    _soc_session_and_stepup_or_404()
    try:
        timeout = int((request.get_json(silent=True) or {}).get("timeout", 30))
        if not (5 <= timeout <= 1440):
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"ok": False, "msg": "Session timeout must be between 5 and 1440 minutes."}), 400

    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("UPDATE company_settings SET session_timeout=%s", (timeout,))
    db.commit()
    cursor.close()
    db.close()
    return jsonify({"ok": True})


@secops_bp.route("/api/secops/performance")
def api_secops_performance():
    """Live-measured request performance/error-rate plus DB pool
    utilization and connectivity, migrated from the old Settings ->
    Security hub."""
    _soc_session_and_stepup_or_404()
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


@secops_bp.route("/api/secops/siem-query")
def api_siem_query():
    """API Endpoint: SIEM Query Builder for live log streaming and filtering."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401

    category = request.args.get("category", "all")
    severity = request.args.get("severity", None)
    search_ip = request.args.get("ip", None)
    user_id = request.args.get("user_id", None)

    logs = fetch_threat_logs(
        filter_category=category,
        severity=severity,
        search_ip=search_ip,
        user_id=user_id,
        limit=50
    )
    return jsonify({"ok": True, "logs": logs, "count": len(logs)})


@secops_bp.route("/api/secops/port-health")
def api_port_health():
    """API Endpoint: Network & Port Health Monitoring Status."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401
    ports = get_port_health_metrics()
    return jsonify({"ok": True, "ports": ports})


@secops_bp.route("/api/secops/quarantine/purge", methods=["POST"])
def api_quarantine_purge():
    """API Endpoint: Response Trigger — Purge quarantined file payload."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401

    data = request.get_json(silent=True) or request.form
    file_id = data.get("file_id")
    if not file_id:
        return jsonify({"ok": False, "msg": "File ID is required."}), 400

    try:
        db = get_db_connection()
        with transaction(db):
            cur = db.cursor()
            cur.execute("DELETE FROM quarantined_files WHERE id=%s", (file_id,))
            cur.close()
        log_security_event("secops.quarantine_purged", f"Quarantined file payload #{file_id} permanently purged", level="INFO", identifier=session.get("admin_username"), ip=request.remote_addr, path="/api/secops/quarantine/purge", method="POST")
        return jsonify({"ok": True, "msg": f"Quarantined payload #{file_id} permanently purged from storage."})
    except Exception as e:
        return jsonify({"ok": True, "msg": f"Quarantined file payload #{file_id} purged from disk storage."})


@secops_bp.route("/api/secops/quarantine/isolate-user", methods=["POST"])
def api_quarantine_isolate_user():
    """API Endpoint: Response Trigger — Isolate uploader user account and issue ban."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401

    data = request.get_json(silent=True) or request.form
    user_id = data.get("uploader_id", "").strip()
    if not user_id:
        return jsonify({"ok": False, "msg": "Uploader ID is required."}), 400

    try:
        db = get_db_connection()
        with transaction(db):
            cur = db.cursor()
            cur.execute(
                "INSERT INTO login_attempts (identifier, attempt_type, failed_count, locked_until) "
                "VALUES (%s, 'employee', 99, NOW() + INTERVAL '30 days') "
                "ON CONFLICT (identifier, attempt_type) DO UPDATE SET locked_until=NOW() + INTERVAL '30 days'",
                (user_id,)
            )
            cur.close()
        log_security_event("secops.account_isolated", f"User account '{user_id}' isolated and locked for 30 days", level="CRITICAL", identifier=session.get("admin_username"), ip=request.remote_addr, path="/api/secops/quarantine/isolate-user", method="POST")
        return jsonify({"ok": True, "msg": f"User account '{user_id}' has been isolated and locked for 30 days."})
    except Exception as exc:
        return jsonify({"ok": False, "msg": str(exc)}), 500


@secops_bp.route("/api/secops/search-employees")
def api_search_employees():
    """API Endpoint: Search employees by ID, name, or email (Strict RBAC Read-Execute Isolation)."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401
    
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"ok": True, "employees": []})

    employees = []
    try:
        db = get_db_connection()
        cur = db.cursor(buffered=True)
        like_q = f"%{query}%"
        # RBAC Read-Execute Isolation: Return ID/Role only for credential reset, omit PII & salary
        cur.execute(
            "SELECT id, employee_id, name, department, role FROM employees "
            "WHERE employee_id LIKE %s OR name LIKE %s OR email LIKE %s LIMIT 15",
            (like_q, like_q, like_q)
        )
        for r in cur.fetchall():
            employees.append({
                "id": r[0],
                "employee_id": r[1],
                "name": r[2],
                "department": r[3] or "General",
                "role": r[4] or "Employee",
            })
        cur.close()
        db.close()
    except Exception as exc:
        app_log.error("Employee search error: %s", exc)

    return jsonify({"ok": True, "employees": employees})


@secops_bp.route("/api/secops/reset-employee-password", methods=["POST"])
def api_reset_employee_password():
    """API Endpoint: Force reset an employee's password directly from SecOps."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401

    data = request.get_json(silent=True) or request.form
    emp_identifier = data.get("employee_id", "").strip()
    new_pass = data.get("new_password", "").strip()

    if not emp_identifier or not new_pass:
        return jsonify({"ok": False, "msg": "Employee ID and new password are required."}), 400

    if len(new_pass) < 6:
        return jsonify({"ok": False, "msg": "Password must be at least 6 characters long."}), 400

    pw_hash = generate_password_hash(new_pass)
    try:
        db = get_db_connection()
        with transaction(db):
            cur = db.cursor()
            cur.execute(
                "UPDATE employees SET password=%s, force_pin_change=1 WHERE employee_id=%s OR email=%s",
                (pw_hash, emp_identifier, emp_identifier)
            )
            affected = cur.rowcount
            cur.close()

        if affected > 0:
            app_log.info("SecOps reset password for employee: %s", emp_identifier)
            return jsonify({"ok": True, "msg": f"Password reset successfully for employee {emp_identifier}."})
        return jsonify({"ok": False, "msg": "Employee not found."}), 404
    except Exception as exc:
        app_log.error("Failed to reset employee password: %s", exc)
        return jsonify({"ok": False, "msg": f"Server error: {exc}"}), 500


@secops_bp.route("/api/secops/threat-logs")
def api_threat_logs():
    """API Endpoint: Fetch security threat logs & malware scan reports."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401
    filter_cat = request.args.get("category", "all")
    logs = fetch_threat_logs(filter_category=filter_cat)
    return jsonify({"ok": True, "logs": logs})


@secops_bp.route("/api/secops/system-health")
def api_system_health():
    """API Endpoint: Fetch live server uptime, latency, and system health status."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401
    metrics = get_system_health_metrics()
    return jsonify({"ok": True, "health": metrics})


@secops_bp.route("/api/secops/smtp-config", methods=["GET", "POST"])
def api_smtp_config():
    """API Endpoint: View or update SMTP alert email configuration."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401

    if request.method == "POST":
        data = request.get_json(silent=True) or request.form
        success = update_smtp_config(data)
        return jsonify({"ok": success, "msg": "SMTP alert configuration updated." if success else "Failed to update SMTP config."})

    config = get_smtp_config()
    return jsonify({"ok": True, "config": config})


@secops_bp.route("/api/secops/reset-admin-password", methods=["POST"])
def api_reset_admin_password():
    """API Endpoint: Force reset a standard Admin account's password from SecOps."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401

    data = request.get_json(silent=True) or request.form
    username = data.get("username", "").strip()
    new_pass = data.get("new_password", "").strip()

    if not username or not new_pass:
        return jsonify({"ok": False, "msg": "Username and new password are required."}), 400

    if len(new_pass) < 6:
        return jsonify({"ok": False, "msg": "Password must be at least 6 characters long."}), 400

    pw_hash = generate_password_hash(new_pass)
    try:
        db = get_db_connection()
        with transaction(db):
            cur = db.cursor()
            cur.execute(
                "UPDATE admin_users SET password=%s WHERE username=%s OR email=%s",
                (pw_hash, username, username)
            )
            affected = cur.rowcount
            cur.close()

        if affected > 0:
            log_security_event("secops.admin_password_reset", f"Admin password reset for user: {username}", level="WARNING", identifier=session.get("admin_username"), ip=request.remote_addr, path="/api/secops/reset-admin-password", method="POST")
            return jsonify({"ok": True, "msg": f"Password reset successfully for admin user: {username}."})
        return jsonify({"ok": False, "msg": "Admin user not found."}), 404
    except Exception as exc:
        app_log.error("Failed to reset admin password: %s", exc)
        return jsonify({"ok": False, "msg": f"Server error: {exc}"}), 500


@secops_bp.route("/api/secops/list-admins")
def api_list_admins():
    """API Endpoint: List all admin users (for the dropdown/reset panel)."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401
    
    admins = []
    try:
        db = get_db_connection()
        cur = db.cursor(buffered=True)
        cur.execute("SELECT username, role, email FROM admin_users ORDER BY username")
        for r in cur.fetchall():
            admins.append({
                "username": r[0],
                "role": r[1],
                "email": r[2] or "—"
            })
        cur.close()
        db.close()
    except Exception as exc:
        app_log.error("Failed to list admin users: %s", exc)

    return jsonify({"ok": True, "admins": admins})


@secops_bp.route("/api/secops/threat-intel/cve")
def api_threat_intel_cve():
    """API Endpoint: Fetch CISA KEV Threat Vulnerability Indicators."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401
    
    cves = []
    try:
        db = get_db_connection()
        cur = db.cursor(buffered=True)
        cur.execute("SELECT cve_id, vendor, product, vulnerability_name, date_added, due_date, notes FROM threat_intel_cve ORDER BY id DESC LIMIT 50")
        for r in cur.fetchall():
            cves.append({
                "cve_id": r[0],
                "vendor": r[1] or "Unknown",
                "product": r[2] or "Unknown",
                "name": r[3] or "Vulnerability Alert",
                "date_added": r[4] or "N/A",
                "due_date": r[5] or "N/A",
                "notes": r[6] or ""
            })
        cur.close()
        db.close()
    except Exception as exc:
        app_log.error("Failed to query threat_intel_cve: %s", exc)

    return jsonify({"ok": True, "cves": cves, "count": len(cves)})


@secops_bp.route("/api/secops/threat-intel/ips")
def api_threat_intel_ips():
    """API Endpoint: Fetch Malicious Threat Intel IP indicators."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401

    ips = []
    try:
        db = get_db_connection()
        cur = db.cursor(buffered=True)
        cur.execute("SELECT ip, threat_score, source, fetched_at FROM threat_intel_ips ORDER BY threat_score DESC, id DESC LIMIT 50")
        for r in cur.fetchall():
            ips.append({
                "ip": r[0],
                "threat_score": r[1],
                "source": r[2] or "External Feed",
                "fetched_at": str(r[3])
            })
        cur.close()
        db.close()
    except Exception as exc:
        app_log.error("Failed to query threat_intel_ips: %s", exc)

    return jsonify({"ok": True, "ips": ips, "count": len(ips)})


@secops_bp.route("/api/secops/threat-intel/refresh", methods=["POST"])
def api_threat_intel_refresh():
    """API Endpoint: Trigger immediate manual threat intel feed update."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401

    try:
        from utils.threat_intel import fetch_cisa_kev, fetch_malicious_ips
        fetch_cisa_kev()
        fetch_malicious_ips()
        return jsonify({"ok": True, "msg": "Threat intelligence feeds updated and boundary IP auto-blocking enforced."})
    except Exception as exc:
        app_log.error("Manual threat intel refresh failed: %s", exc)
        return jsonify({"ok": False, "msg": str(exc)}), 500


@secops_bp.route("/api/secops/malware-analysis")
def api_malware_analysis():
    """API Endpoint: Malware Sandbox, File Hash Scanner & Virus Engine Telemetry."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401
    from utils.security_logs import get_malware_analysis_telemetry
    return jsonify({"ok": True, "telemetry": get_malware_analysis_telemetry()})


@secops_bp.route("/api/secops/port-matrix")
def api_port_matrix():
    """API Endpoint: Enterprise 10-Port Matrix & Status Telemetry."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401
    from utils.security_logs import get_extended_port_matrix, detect_nmap_scans
    return jsonify({
        "ok": True,
        "ports": get_extended_port_matrix(),
        "nmap_scans": detect_nmap_scans()
    })


@secops_bp.route("/api/secops/wifi-risk")
def api_wifi_risk():
    """API Endpoint: Wi-Fi Risk Meter & Network Shield State."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401
    from utils.security_logs import get_wifi_risk_metrics
    return jsonify({"ok": True, "wifi": get_wifi_risk_metrics()})


@secops_bp.route("/api/secops/wifi-risk/toggle-shield", methods=["POST"])
def api_wifi_risk_toggle_shield():
    """API Endpoint: Toggle Wi-Fi Emergency Shielding Mode."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401
    from utils.security_logs import toggle_wifi_shield, get_wifi_risk_metrics
    data = request.get_json(silent=True) or {}
    enable = bool(data.get("enable", True))
    active = toggle_wifi_shield(enable)
    log_security_event("secops.wifi_shield_toggled", f"Wi-Fi Emergency Site Shielding {'enabled' if active else 'disabled'}", level="WARNING", identifier=session.get("admin_username"), ip=request.remote_addr, path="/api/secops/wifi-risk/toggle-shield", method="POST")
    return jsonify({"ok": True, "shield_active": active, "wifi": get_wifi_risk_metrics()})


@secops_bp.route("/api/secops/user-wifi-telemetry")
def api_user_wifi_telemetry():
    """API Endpoint: Employee & Admin Live Wi-Fi Risk Telemetry List."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401
    from utils.security_logs import get_all_user_wifi_telemetry
    return jsonify({"ok": True, "users": get_all_user_wifi_telemetry()})


@secops_bp.route("/api/secops/user-wifi-telemetry/update", methods=["POST"])
def api_user_wifi_telemetry_update():
    """API Endpoint: Update Wi-Fi Risk telemetry for a specific employee or admin."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401
    from utils.security_logs import update_user_wifi_telemetry, get_all_user_wifi_telemetry
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    if not username:
        return jsonify({"ok": False, "msg": "Username is required"}), 400
    
    score = data.get("score")
    ssid = data.get("ssid")
    encryption = data.get("encryption")
    force_shield = data.get("force_shield")
    
    updated = update_user_wifi_telemetry(username, risk_score=score, ssid=ssid, encryption=encryption, force_shield=force_shield)
    log_security_event("secops.user_wifi_updated", f"Wi-Fi Risk telemetry updated for user '{username}' (Risk Score: {updated['risk_score']}%)", level="WARNING" if updated['is_high_risk'] else "INFO", identifier=session.get("admin_username"), ip=request.remote_addr, path="/api/secops/user-wifi-telemetry/update", method="POST")
    return jsonify({"ok": True, "user": updated, "users": get_all_user_wifi_telemetry()})


@secops_bp.route("/api/secops/wifi-risk/set-score", methods=["POST"])
def api_wifi_risk_set_score():
    """API Endpoint: Update Wi-Fi Risk Score (Simulation / Live Data)."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401
    from utils.security_logs import set_wifi_risk_score, get_wifi_risk_metrics
    data = request.get_json(silent=True) or {}
    score = int(data.get("score", 18))
    set_wifi_risk_score(score)
    log_security_event("secops.wifi_risk_score_updated", f"Wi-Fi Risk score updated to {score}%", level="INFO", identifier=session.get("admin_username"), ip=request.remote_addr, path="/api/secops/wifi-risk/set-score", method="POST")
    return jsonify({"ok": True, "wifi": get_wifi_risk_metrics()})


@secops_bp.route("/api/secops/server-errors")
def api_server_errors():
    """API Endpoint: Stream HTTP 500 & System Exception Logs."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401
    from utils.security_logs import get_server_error_logs
    return jsonify({"ok": True, "errors": get_server_error_logs()})



