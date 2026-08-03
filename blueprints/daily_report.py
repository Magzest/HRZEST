"""
daily_report.py — Nightly attendance summary email for Medium & Premium plans.

Scheduled by APScheduler (registered in wsgi.py) to run at 23:59 every day.
Generates a per-company attendance summary and emails it to all admin addresses.

Only runs for admins on 'medium' or 'premium' plans.
"""
import datetime
import threading
from flask import Blueprint

from database import get_db_connection
from extensions import app_log
from utils.email_utils import get_email_config, send_email_async, get_admin_emails
from blueprints.plan_guard import PLANS, PLAN_ORDER, _plan_rank

daily_report_bp = Blueprint("daily_report", __name__)

_report_lock = threading.Lock()


# ── HTML email template ──────────────────────────────────────────────────────

def _build_email_html(date_str: str, stats: dict) -> str:
    present    = stats.get("present", 0)
    absent     = stats.get("absent", 0)
    late       = stats.get("late", 0)
    total      = stats.get("total", 0)
    on_leave   = stats.get("on_leave", 0)
    pending_lv = stats.get("pending_leaves", 0)
    pct        = round((present / total * 100), 1) if total else 0

    rows_html = ""
    for r in stats.get("rows", [])[:30]:   # cap at 30 rows in email
        status_color = {"Present": "#16A34A", "Absent": "#DC2626", "Late": "#D97706"}.get(r["status"], "#64748B")
        rows_html += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #E2E8F0;">{r['employee_id']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #E2E8F0;">{r['name']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #E2E8F0;color:{status_color};font-weight:700;">{r['status']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #E2E8F0;">{r.get('login_time') or '--'}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #E2E8F0;">{r.get('logout_time') or '--'}</td>
        </tr>"""

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Daily Attendance Report</title></head>
<body style="margin:0;padding:0;background:#F1F5F9;font-family:Arial,sans-serif;">
  <div style="max-width:680px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08);">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#0F172A,#1E3A8A);padding:32px;text-align:center;">
      <h1 style="color:#fff;margin:0;font-size:22px;font-weight:800;">📊 Daily Attendance Report</h1>
      <p style="color:rgba(255,255,255,0.75);margin:8px 0 0;font-size:14px;">{date_str}</p>
    </div>

    <!-- KPI cards -->
    <div style="display:flex;justify-content:space-around;padding:24px 16px;background:#F8FAFC;border-bottom:1px solid #E2E8F0;">
      <div style="text-align:center;">
        <div style="font-size:28px;font-weight:800;color:#16A34A;">{present}</div>
        <div style="font-size:12px;color:#64748B;font-weight:600;">PRESENT</div>
      </div>
      <div style="text-align:center;">
        <div style="font-size:28px;font-weight:800;color:#DC2626;">{absent}</div>
        <div style="font-size:12px;color:#64748B;font-weight:600;">ABSENT</div>
      </div>
      <div style="text-align:center;">
        <div style="font-size:28px;font-weight:800;color:#D97706;">{late}</div>
        <div style="font-size:12px;color:#64748B;font-weight:600;">LATE</div>
      </div>
      <div style="text-align:center;">
        <div style="font-size:28px;font-weight:800;color:#8B5CF6;">{on_leave}</div>
        <div style="font-size:12px;color:#64748B;font-weight:600;">ON LEAVE</div>
      </div>
      <div style="text-align:center;">
        <div style="font-size:28px;font-weight:800;color:#0F172A;">{pct}%</div>
        <div style="font-size:12px;color:#64748B;font-weight:600;">ATTENDANCE</div>
      </div>
    </div>

    <!-- Pending alerts -->
    {"" if pending_lv == 0 else f'<div style="margin:16px 24px;padding:14px 18px;background:#FEF3C7;border-left:4px solid #F59E0B;border-radius:8px;font-size:14px;color:#92400E;"><strong>⏳ {pending_lv} leave request{"s" if pending_lv != 1 else ""} pending approval.</strong></div>'}

    <!-- Employee table -->
    <div style="padding:24px;">
      <h2 style="font-size:16px;font-weight:800;color:#0F172A;margin:0 0 16px;">Today's Attendance</h2>
      <table style="width:100%;border-collapse:collapse;font-size:13px;">
        <thead>
          <tr style="background:#F1F5F9;">
            <th style="padding:10px 12px;text-align:left;color:#475569;font-weight:700;">ID</th>
            <th style="padding:10px 12px;text-align:left;color:#475569;font-weight:700;">Name</th>
            <th style="padding:10px 12px;text-align:left;color:#475569;font-weight:700;">Status</th>
            <th style="padding:10px 12px;text-align:left;color:#475569;font-weight:700;">Check-In</th>
            <th style="padding:10px 12px;text-align:left;color:#475569;font-weight:700;">Check-Out</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
      {"<p style='text-align:center;color:#94A3B8;font-size:12px;margin-top:12px;'>Showing first 30 employees. Log in to view full report.</p>" if len(stats.get("rows", [])) > 30 else ""}
    </div>

    <!-- Footer -->
    <div style="padding:20px 24px;background:#F8FAFC;border-top:1px solid #E2E8F0;text-align:center;">
      <p style="color:#94A3B8;font-size:12px;margin:0;">
        This is an automated daily report from the Employee Attendance Platform.<br>
        © {datetime.date.today().year} Employee Attendance Platform
      </p>
    </div>
  </div>
</body>
</html>"""


# ── Core report generation ───────────────────────────────────────────────────

def generate_and_send_daily_report(app=None):
    """
    Main job function — called by APScheduler nightly.
    Iterates over all admin accounts, checks their plan, and sends email if eligible.
    """
    with _report_lock:
        try:
            _run_report(app)
        except Exception:
            app_log.exception("daily_report: unhandled error in report job")


def _run_report(app=None):
    today = datetime.date.today()
    date_str = today.strftime("%A, %d %B %Y")
    app_log.info(f"daily_report: generating report for {date_str}")

    db = get_db_connection()
    cursor = db.cursor(buffered=True)

    # Get all admins on medium or premium plans
    cursor.execute("""
        SELECT username, email, COALESCE(plan, 'basic') as plan
        FROM admin_users
        WHERE email IS NOT NULL AND email != ''
    """)
    admins = cursor.fetchall()

    # Build global attendance stats (shared across all admins for same company)
    cursor.execute("SELECT COUNT(*) FROM employees")
    total = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(DISTINCT employee_id) FROM attendance
        WHERE date=%s AND login_time IS NOT NULL
    """, (today,))
    present = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(DISTINCT employee_id) FROM attendance
        WHERE date=%s AND status='Late Login'
    """, (today,))
    late = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM leave_requests
        WHERE leave_date=%s AND status='Approved'
    """, (today,))
    on_leave = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM leave_requests WHERE status='Pending'")
    pending_leaves = cursor.fetchone()[0]

    absent = max(0, total - present - on_leave)

    # Build employee-level rows
    cursor.execute("""
        SELECT e.employee_id, e.name,
               a.login_time, a.logout_time, a.status,
               CASE WHEN lr.id IS NOT NULL THEN 'On Leave' ELSE NULL END as leave_status
        FROM employees e
        LEFT JOIN attendance a ON e.employee_id=a.employee_id AND a.date=%s
        LEFT JOIN leave_requests lr ON e.employee_id=lr.employee_id
              AND lr.leave_date=%s AND lr.status='Approved'
        ORDER BY e.name
    """, (today, today))
    raw_rows = cursor.fetchall()

    rows = []
    for r in raw_rows:
        emp_status = r[5] or r[4] or ("Present" if r[2] else "Absent")
        rows.append({
            "employee_id": r[0],
            "name": r[1],
            "login_time": str(r[2])[:5] if r[2] else None,
            "logout_time": str(r[3])[:5] if r[3] else None,
            "status": emp_status,
        })

    cursor.close()
    db.close()

    stats = {
        "total": total, "present": present, "absent": absent,
        "late": late, "on_leave": on_leave, "pending_leaves": pending_leaves,
        "rows": rows,
    }

    cfg = get_email_config()
    if not cfg or not cfg.get("host"):
        app_log.warning("daily_report: no email config found, skipping send")
        return

    sent_count = 0
    for username, email, plan in admins:
        if _plan_rank(plan) < _plan_rank("medium"):
            app_log.debug(f"daily_report: skipping {username} (plan={plan})")
            continue
        subject = f"📊 Daily Attendance Report — {date_str}"
        html    = _build_email_html(date_str, stats)
        send_email_async(email, subject, html, cfg)
        sent_count += 1
        app_log.info(f"daily_report: queued email to {email} (plan={plan})")

    app_log.info(f"daily_report: done — sent to {sent_count} admins")


# ── Manual trigger route (for testing) ──────────────────────────────────────

@daily_report_bp.route("/api/admin/trigger_daily_report", methods=["POST"])
def trigger_daily_report():
    """Premium/Medium admins can manually trigger the daily report for testing."""
    from flask import session, jsonify
    from blueprints.plan_guard import require_plan, get_company_plan
    plan = get_company_plan()
    if _plan_rank(plan) < _plan_rank("medium"):
        return jsonify({"ok": False, "msg": "Daily reports require Medium or Premium plan"}), 403
    import threading
    t = threading.Thread(target=generate_and_send_daily_report, daemon=True)
    t.start()
    return jsonify({"ok": True, "msg": "Daily report generation started. Check admin email shortly."})
