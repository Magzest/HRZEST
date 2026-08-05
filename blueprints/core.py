"""Core blueprint — home page, CSP reporting, session-risk stream, security
lockout, and the simpler token-based REST API layer (/api/login,
/api/dashboard, /api/holidays and their /api/employee/* equivalents) — the
last routes drained out of app.py, which now holds only shared setup
(init_db, error handlers, before/after_request hooks, template filters)."""
import time
import secrets
import datetime
from flask import Blueprint, request, session, jsonify, render_template, Response, g, redirect
from extensions import limiter, app_log
from database import get_db_connection
from utils.auth import (
    api_required, check_password_hash, generate_password_hash, _hash_token,
    _check_login_lockout, _record_login_failure, _clear_login_failures,
)
from utils.helpers import _db, get_auth_config
from utils.session_risk import is_session_compromised

core_bp = Blueprint("core", __name__)


@core_bp.route("/csp-report", methods=["POST"])
def csp_report():
    """Receives Content-Security-Policy violation reports from browsers."""
    try:
        report = request.get_json(force=True, silent=True) or {}
        violation = report.get("csp-report", report)
        app_log.warning(
            "CSP violation",
            extra={
                "blocked_uri": violation.get("blocked-uri", ""),
                "violated_directive": violation.get("violated-directive", ""),
                "document_uri": violation.get("document-uri", ""),
                "source_file": violation.get("source-file", ""),
            },
        )
    except Exception:
        pass
    return "", 204


@core_bp.route("/")
def home():
    """Site root is the platform operator's front door: an unauthenticated
    visitor is bounced through to /super_admin/login (MFA-protected), and
    an already-logged-in operator lands straight on the console. The
    per-company attendance kiosk that used to live here moved to
    /checkin -- see checkin_page() below."""
    return redirect("/super_admin")


@core_bp.route("/checkin")
def checkin_page():
    """The QR/PIN/face/fingerprint check-in kiosk -- previously served at
    site root ("/") before that was handed over to the platform admin
    login. No auth required: this is the public kiosk screen a company's
    own employees check in from."""
    return render_template("index.html", auth_cfg=get_auth_config())


@core_bp.route("/api/session/risk-stream")
def session_risk_stream():
    """Server-Sent Events stream: notifies an already-open browser tab the
    moment its session is marked compromised, instead of it having to wait
    for its next click to find out.

    This is enforcement's UX layer, not enforcement itself — the actual
    kill switch is _reject_if_compromised() in utils/auth.py, checked on
    every authenticated request regardless of whether this stream is even
    connected. A client that never opens this connection, or ignores every
    message it sends, still gets rejected on its very next request.

    Each connection is deliberately bounded (~20s of 2s-interval checks),
    not held open indefinitely: this app runs gunicorn's default sync
    worker model, where one open streaming connection occupies one whole
    worker process for as long as it stays open. EventSource reconnects
    automatically the instant a stream closes, so bounding each connection
    keeps the near-real-time push behavior (compromised state is caught
    within one 2-second tick) while capping how long any single browser
    tab can tie up a worker.
    """
    if not session.get("admin_logged_in") and not session.get("employee_id"):
        return jsonify({"ok": False, "msg": "Not authenticated"}), 401
    sid = session.get("_sid")
    if not sid:
        return jsonify({"ok": False, "msg": "No active session to monitor"}), 400

    def _generate(_sid):
        try:
            for _ in range(10):
                if is_session_compromised(_sid):
                    yield "event: compromised\ndata: {}\n\n"
                    return
                yield ": keepalive\n\n"
                time.sleep(2)
            # Bounded lifetime reached with nothing to report — close
            # cleanly; EventSource reconnects on its own.
            yield "event: ping\ndata: {}\n\n"
        except GeneratorExit:
            # Client disconnected (tab closed/navigated away) — nothing to
            # clean up, session_risk rows aren't tied to connection state.
            pass

    return Response(
        _generate(sid),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@core_bp.route("/security_lockout")
def security_lockout():
    """Hard-locked landing page for a force-terminated session. Not behind
    any auth decorator on purpose — the session that lands here has
    already been session.clear()'d by _reject_if_compromised()."""
    return render_template("security_lockout.html"), 403


@core_bp.route("/api/login", methods=["POST"])
@limiter.limit("5 per minute")
@limiter.limit("20 per hour")
def api_login():
    data = request.get_json() or {}
    username = data.get("username", "")
    password = data.get("password", "")
    if "\x00" in username or "\x00" in password:
        return jsonify({"ok": False, "msg": "Invalid credentials"}), 401
    with _db() as (cursor, conn):
        cursor.execute("SELECT password FROM admin_users WHERE username=%s", (username,))
        row = cursor.fetchone()
        if row and check_password_hash(row[0], password):
            token = secrets.token_hex(32)
            cursor.execute(
                "INSERT INTO api_tokens (token, token_type, identity, expires_at) "
                "VALUES (%s, 'admin', %s, NOW() + INTERVAL '24 hours')",
                (_hash_token(token), username)
            )
            conn.commit()
            return jsonify({"ok": True, "token": token, "username": username})
    return jsonify({"ok": False, "msg": "Invalid credentials"}), 401


@core_bp.route("/api/logout", methods=["POST"])
def api_logout():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        with _db() as (cursor, conn):
            cursor.execute("DELETE FROM api_tokens WHERE token=%s", (_hash_token(auth[7:]),))
            conn.commit()
    return jsonify({"ok": True})


@core_bp.route("/api/dashboard", methods=["GET"])
@api_required
def api_dashboard():
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    today = datetime.date.today()

    cursor.execute("SELECT COUNT(*) FROM employees")
    total = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(DISTINCT employee_id) FROM attendance WHERE date=%s AND login_time IS NOT NULL",
        (today,)
    )
    present = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(DISTINCT employee_id) FROM attendance WHERE date=%s AND status='Late Login'",
        (today,)
    )
    late = cursor.fetchone()[0]
    cursor.execute("""
        SELECT e.employee_id, e.name, a.login_time, a.logout_time, a.status,
               a.logout_status, a.attendance_type
        FROM employees e
        LEFT JOIN attendance a ON e.employee_id=a.employee_id AND a.date=%s
        ORDER BY e.name
    """, (today,))
    rows = cursor.fetchall()
    today_rows = [
        {
            "employee_id": r[0], "name": r[1],
            "login_time": str(r[2]) if r[2] else None,
            "logout_time": str(r[3]) if r[3] else None,
            "login_status": r[4], "logout_status": r[5], "attendance_type": r[6],
        }
        for r in rows
    ]
    cursor.execute("SELECT COUNT(*) FROM leave_requests WHERE status='Pending'")
    pending_leaves = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM resignation_requests WHERE status='Pending'")
    pending_resignations = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('Open','In Progress')")
    pending_tickets = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM notifications WHERE recipient_type='admin' AND is_read=FALSE")
    unread_notifications = cursor.fetchone()[0]
    cursor.close()
    db.close()

    return jsonify({
        "ok": True, "total": total, "present": present,
        "absent": total - present, "late": late,
        "today": today.strftime("%d %b %Y"), "today_rows": today_rows,
        "pending_leaves": pending_leaves, "pending_resignations": pending_resignations,
        "pending_tickets": pending_tickets, "unread_notifications": unread_notifications,
    })




@core_bp.route("/api/employee/login", methods=["POST"])
@limiter.limit("5 per minute")
@limiter.limit("20 per hour")
def api_employee_login():
    data = request.get_json() or {}
    emp_id = data.get("employee_id", "").strip()
    password = data.get("password", "").strip()
    if not emp_id:
        return jsonify({"ok": False, "msg": "employee_id required"}), 400
    # Check lockout before hitting the DB with credentials
    locked, until = _check_login_lockout(emp_id, "employee")
    if locked:
        return jsonify({"ok": False, "msg": f"Account locked until {until}. Try again later."}), 429
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT name, email, password FROM employees WHERE employee_id=%s", (emp_id,))
    row = cursor.fetchone()
    cursor.close()
    db.close()
    if not row:
        _record_login_failure(emp_id, "employee")
        return jsonify({"ok": False, "msg": "Invalid credentials"}), 401
    if not password:
        return jsonify({"ok": False, "msg": "Password required"}), 400
    if not row[2] or not check_password_hash(row[2], password):
        _record_login_failure(emp_id, "employee")
        return jsonify({"ok": False, "msg": "Invalid credentials"}), 401
    _clear_login_failures(emp_id, "employee")
    # Upgrade legacy hash to bcrypt transparently
    if row[2] and not row[2].startswith("$2"):
        with _db() as (_uc, _ud):
            _uc.execute("UPDATE employees SET password=%s WHERE employee_id=%s",
                        (generate_password_hash(password), emp_id))
            _ud.commit()
    token = secrets.token_hex(32)
    with _db() as (cursor, conn):
        cursor.execute(
            "INSERT INTO api_tokens (token, token_type, identity, expires_at) "
            "VALUES (%s, 'employee', %s, NOW() + INTERVAL '24 hours')",
            (_hash_token(token), emp_id)
        )
        conn.commit()
    from utils.plan_limits import get_tenant_plan, PLAN_TIERS
    plan_name = get_tenant_plan(g.tenant_db)
    _tier = PLAN_TIERS[plan_name]
    plan_info = {
        "display_name": _tier["display_name"],
        "employee_limit": _tier["employee_limit"],
        "features": sorted(_tier["features"]),  # frozenset isn't JSON-serializable
    }

    return jsonify({
        "ok": True, "token": token, "employee_id": emp_id,
        "name": row[0], "email": row[1],
        "plan": plan_name, "plan_info": plan_info
    })


@core_bp.route("/api/employee/logout", methods=["POST"])
def api_employee_logout():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        with _db() as (cursor, conn):
            cursor.execute("DELETE FROM api_tokens WHERE token=%s", (_hash_token(auth[7:]),))
            conn.commit()
    return jsonify({"ok": True})


@core_bp.route("/api/employee/signup", methods=["POST"])
@limiter.limit("5 per minute")
def api_employee_signup():
    """API endpoint for employee self-registration / sign up."""
    data = request.get_json() or {}
    emp_id = data.get("employee_id", "").strip().upper()
    name = data.get("name", "").strip()
    email = data.get("email", "").strip() or None
    password = data.get("password", "").strip()
    role = data.get("role", "Employee").strip()
    department = data.get("department", "Engineering").strip()

    if not emp_id or not name or not password:
        return jsonify({"ok": False, "msg": "Employee ID, Full Name, and Password are required."}), 400

    if len(password) < 6:
        return jsonify({"ok": False, "msg": "Password must be at least 6 characters."}), 400

    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute("SELECT 1 FROM employees WHERE employee_id=%s", (emp_id,))
        if cursor.fetchone():
            cursor.close()
            db.close()
            return jsonify({"ok": False, "msg": f"Employee ID '{emp_id}' is already registered."}), 400

        hashed_pw = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO employees (employee_id, name, email, role, department, password, date_of_joining) "
            "VALUES (%s, %s, %s, %s, %s, %s, NOW())",
            (emp_id, name, email, role, department, hashed_pw)
        )
        db.commit()
        cursor.close()
        db.close()
        return jsonify({
            "ok": True,
            "msg": f"Employee account for {name} ({emp_id}) created successfully! You can now sign in.",
            "employee_id": emp_id
        })
    except Exception as exc:
        app_log.error("api_employee_signup failed: %s", exc)
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if db:
            try:
                db.close()
            except Exception:
                pass
        return jsonify({"ok": False, "msg": f"Failed to register employee: {exc}"}), 500

