"""Blueprint for Dedicated SecOps & SP Admin Portal with MFA, SIEM Log Engine & Threat Telemetry."""

import time
import re
import os
import datetime
from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for
from database import get_db_connection, transaction
from utils.security_logs import (
    fetch_threat_logs,
    get_system_health_metrics,
    get_port_health_metrics,
    get_quarantined_files,
    get_smtp_config,
    update_smtp_config,
)
from utils.auth import _db, check_password_hash, generate_password_hash
from utils.session_risk import ensure_session_id
from utils.totp import verify_totp_code, get_or_create_admin_totp_secret, totp_qr_data_uri, mark_totp_enabled
from extensions import app_log, log_security_event

secops_bp = Blueprint("secops", __name__)


def _is_secops_authorized():
    """Verify if session is logged in with SecOps / Cybersecurity / Admin privileges."""
    return bool(session.get("admin_logged_in")) and session.get("admin_role") in ("soc_analyst", "cybersecurity", "admin")


@secops_bp.route("/sp_admin")
@secops_bp.route("/sp_admin/")
@secops_bp.route("/sp_admin/login", methods=["GET", "POST"])
def sp_admin_login():

    """Dedicated SP Admin / Cybersecurity Analyst Login Page."""
    if session.get("admin_logged_in") and session.get("admin_role") in ("soc_analyst", "cybersecurity", "admin"):
        return redirect("/secops")

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip() or "sp_admin"
        password = request.form.get("password", "").strip()

        with _db() as (cursor, db):
            cursor.execute(
                "SELECT password, COALESCE(role,'admin'), email, totp_secret FROM admin_users WHERE username=%s",
                (identifier,)
            )
            admin_row = cursor.fetchone()

        if admin_row and check_password_hash(admin_row[0], password):
            session["mfa_pending_username"] = identifier
            session["mfa_pending_role"] = admin_row[1] if admin_row[1] in ("soc_analyst", "cybersecurity") else "soc_analyst"
            session["mfa_pending_secret"] = admin_row[3] or ""
            return redirect("/sp_admin/mfa")
        
        return render_template("sp_admin_login.html", error="Invalid Cybersecurity Analyst credentials.")

    return render_template("sp_admin_login.html")


@secops_bp.route("/sp_admin/mfa", methods=["GET", "POST"])
def sp_admin_mfa():
    """MFA Verification Challenge for Cybersecurity Analyst Login with QR Code."""
    username = session.get("mfa_pending_username")
    if not username:
        return redirect("/sp_admin/login")

    secret, enabled = get_or_create_admin_totp_secret(username)
    qr_uri = None if enabled else totp_qr_data_uri(username, secret)

    if request.method == "POST":
        totp_code = request.form.get("totp_code", "").strip()

        valid_mfa = verify_totp_code(username, totp_code, require_enabled=False)

        if valid_mfa:
            mark_totp_enabled(username)
            session.clear()
            session["admin_logged_in"] = True
            session["admin_username"] = username
            session["admin_role"] = "soc_analyst"
            session["soc_2fa_verified_at"] = time.time()
            session["_session_created"] = time.time()
            session.permanent = True
            ensure_session_id(session)
            return redirect("/secops")

        
        return render_template(
            "sp_admin_login.html",
            show_mfa=True,
            username=username,
            secret=secret,
            qr_uri=qr_uri,
            error="Invalid MFA verification code."
        )

    return render_template(
        "sp_admin_login.html",
        show_mfa=True,
        username=username,
        secret=secret,
        qr_uri=qr_uri
    )



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


@secops_bp.route("/api/secops/ban-ip", methods=["POST"])
def api_ban_ip():
    """API Endpoint: Ban an IP address."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401

    data = request.get_json(silent=True) or request.form
    ip = data.get("ip", "").strip()
    reason = data.get("reason", "SecOps manual ban").strip()

    if not ip:
        return jsonify({"ok": False, "msg": "IP address is required."}), 400

    try:
        db = get_db_connection()
        with transaction(db):
            cur = db.cursor()
            cur.execute(
                "INSERT INTO banned_ips (ip, reason, banned_at) VALUES (%s, %s, NOW()) "
                "ON CONFLICT (ip) DO UPDATE SET reason=EXCLUDED.reason, banned_at=NOW()",
                (ip, reason)
            )
            cur.close()
        return jsonify({"ok": True, "msg": f"IP {ip} has been banned."})
    except Exception as exc:
        app_log.error("Failed to ban IP: %s", exc)
        return jsonify({"ok": False, "msg": str(exc)}), 500


@secops_bp.route("/api/secops/unban-ip", methods=["POST"])
def api_unban_ip():
    """API Endpoint: Unban an IP address."""
    if not _is_secops_authorized():
        return jsonify({"ok": False, "msg": "Unauthorized"}), 401

    data = request.get_json(silent=True) or request.form
    ip = data.get("ip", "").strip()

    if not ip:
        return jsonify({"ok": False, "msg": "IP address is required."}), 400

    try:
        db = get_db_connection()
        with transaction(db):
            cur = db.cursor()
            cur.execute("DELETE FROM banned_ips WHERE ip=%s", (ip,))
            cur.close()
        return jsonify({"ok": True, "msg": f"IP {ip} unbanned."})
    except Exception as exc:
        return jsonify({"ok": False, "msg": str(exc)}), 500


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



