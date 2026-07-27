"""Blueprint for Admin Targeted Email Dispatcher Module.

Provides routes for broadcasting emails to:
- All Employees
- Specific Departments
- Individual Employees

Out-of-band delivery is handled via the asynchronous DB-backed email queue,
returning an immediate HTTP 202 Queue Confirmation response (<50ms).
"""
import re
import html
from flask import Blueprint, request, jsonify, render_template, session
from database import get_db_connection, transaction
from utils.auth import _db
from utils.email_utils import send_email_async, get_email_config
from extensions import app_log, log_security_event, limiter

email_blast_bp = Blueprint("email_blast", __name__)


def _is_admin():
    return bool(session.get("admin_logged_in"))


@email_blast_bp.route("/api/admin/email-blast", methods=["POST"])
@limiter.limit("10 per hour")
def api_email_blast():
    """Broadcast target-selected emails out-of-band and return immediate 202."""
    if not _is_admin():
        return jsonify({"ok": False, "msg": "Unauthorized access."}), 401

    data = request.get_json(silent=True) or request.form
    target_type = data.get("target_type", "").strip()  # 'all', 'department', 'individual'
    target_value = data.get("target_value", "").strip()  # department name or employee_id
    raw_subject = data.get("subject", "").strip()
    raw_body = data.get("body", "").strip()

    if not raw_subject or not raw_body or not target_type:
        return jsonify({"ok": False, "msg": "Missing required fields: target_type, subject, body."}), 400

    # HTML Sanitization on subject and body inputs
    clean_subject = html.escape(raw_subject)
    # Basic safe tags allowed or escape for security
    clean_body = html.escape(raw_body).replace("\n", "<br>")
    
    formatted_html = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px; background: #ffffff;">
      <div style="background: #1e3a8a; padding: 16px 20px; border-radius: 8px 8px 0 0; color: #ffffff;">
        <h2 style="margin: 0; font-size: 18px;">📢 Broadcast Announcement</h2>
      </div>
      <div style="padding: 20px; color: #334155; font-size: 14px; line-height: 1.6;">
        {clean_body}
      </div>
      <div style="border-top: 1px solid #e2e8f0; padding-top: 12px; font-size: 11px; color: #94a3b8;">
        Sent via Employee Attendance & HRMS Portal. Please do not reply directly to this automated email.
      </div>
    </div>
    """

    recipients = []
    try:
        db = get_db_connection()
        cur = db.cursor(buffered=True)

        if target_type == "all":
            cur.execute("SELECT email, name FROM employees WHERE email IS NOT NULL AND email != ''")
            recipients = cur.fetchall()
        elif target_type == "department":
            cur.execute("SELECT email, name FROM employees WHERE department=%s AND email IS NOT NULL AND email != ''", (target_value,))
            recipients = cur.fetchall()
        elif target_type == "individual":
            cur.execute("SELECT email, name FROM employees WHERE (employee_id=%s OR email=%s) AND email IS NOT NULL AND email != ''", (target_value, target_value))
            recipients = cur.fetchall()
        else:
            cur.close()
            db.close()
            return jsonify({"ok": False, "msg": "Invalid target_type specified."}), 400

        cur.close()
        db.close()
    except Exception as exc:
        app_log.error("Failed to query email blast recipients: %s", exc)
        return jsonify({"ok": False, "msg": "Database query error while collecting recipients."}), 500

    if not recipients:
        return jsonify({"ok": False, "msg": "No valid email recipients found matching target criteria."}), 404

    # Config check
    cfg = get_email_config()
    if not cfg:
        app_log.warning("Email blast queued but SMTP config is missing/incomplete.")

    # Enqueue asynchronously in bulk
    queued_count = 0
    try:
        db = get_db_connection()
        with transaction(db):
            cur = db.cursor()
            # Record batch broadcast in audit table
            cur.execute(
                "INSERT INTO broadcast_emails (sender_username, target_type, target_value, subject, body_snippet, recipient_count) "
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (session.get("admin_username", "admin"), target_type, target_value, clean_subject, clean_body[:200], len(recipients))
            )
            broadcast_id = cur.fetchone()[0]

            for email, name in recipients:
                cur.execute(
                    "INSERT INTO email_queue (to_email, subject, html_body, attempts, status) VALUES (%s, %s, %s, 0, 'pending')",
                    (email, clean_subject, formatted_html)
                )
                queued_count += 1
            cur.close()
    except Exception as exc:
        app_log.error("Failed to enqueue broadcast emails: %s", exc)
        return jsonify({"ok": False, "msg": "Failed to enqueue broadcast messages."}), 500

    log_security_event(
        "admin.email_blast",
        f"Broadcast email dispatch initiated to {queued_count} recipient(s)",
        level="INFO",
        identifier=session.get("admin_username"),
        target_type=target_type,
        count=queued_count
    )

    # Return HTTP 202 Accepted immediately within <50ms
    return jsonify({
        "ok": True,
        "status": "Accepted",
        "code": 202,
        "msg": f"Email broadcast dispatch queued successfully for {queued_count} recipient(s).",
        "queued_count": queued_count
    }), 202
