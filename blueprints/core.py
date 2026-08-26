# -*- coding: utf-8 -*-
"""Core blueprint -- home page, CSP reporting, session-risk stream, security
lockout, and the simpler token-based REST API layer (/api/login,
/api/dashboard, /api/holidays and their /api/employee/* equivalents) -- the
last routes drained out of app.py, which now holds only shared setup
(init_db, error handlers, before/after_request hooks, template filters)."""
import time
import secrets
import datetime
from flask import Blueprint, request, session, jsonify, render_template, redirect, Response
from extensions import limiter, app_log, log_security_event
from database import get_db_connection
from utils.auth import (
    api_required, check_password_hash, generate_password_hash, _hash_token,
    _check_login_lockout, _record_login_failure, _clear_login_failures,
)
from utils.helpers import (
    _db, get_auth_config, validate_employee_email_domain,
    employee_login_url, get_pending_counts, tpath, add_employee_seat_cap_check,
)
from utils.email_utils import get_email_config, send_email_smtp
from utils.session_risk import is_session_compromised, ensure_session_id

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
    # Always show the marketing landing page at "/", regardless of tenant
    # or session state -- logged-in admins/employees and tenant-slug
    # visits used to be auto-redirected straight to their portal/login;
    # now everyone lands here first and clicks through themselves.
    from utils.analytics import track_page_view
    from utils.plan_limits import PER_EMPLOYEE_PAISE
    track_page_view("/")
    return render_template("landing.html", per_employee_paise=PER_EMPLOYEE_PAISE)


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

    This is enforcement's UX layer, not enforcement itself -- the actual
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
            # Bounded lifetime reached with nothing to report -- close
            # cleanly; EventSource reconnects on its own.
            yield "event: ping\ndata: {}\n\n"
        except GeneratorExit:
            # Client disconnected (tab closed/navigated away) -- nothing to
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
    any auth decorator on purpose -- the session that lands here has
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
    pending_leaves, pending_resignations, pending_tickets = get_pending_counts()
    cursor.execute("SELECT COUNT(*) FROM notifications WHERE recipient_type='admin' AND is_read=FALSE")
    unread_notifications = cursor.fetchone()[0]
    cursor.execute("SELECT COALESCE(company_name, '') FROM company_settings LIMIT 1")
    co_row = cursor.fetchone()
    company_name = co_row[0] if co_row else ""
    cursor.close()
    db.close()

    return jsonify({
        "ok": True, "total": total, "present": present,
        "absent": total - present, "late": late,
        "today": today.strftime("%d %b %Y"), "today_rows": today_rows,
        "pending_leaves": pending_leaves, "pending_resignations": pending_resignations,
        "pending_tickets": pending_tickets, "unread_notifications": unread_notifications,
        "company_name": company_name,
    })



@core_bp.route("/api/billing_status", methods=["GET"])
@api_required
def api_billing_status():
    """Mobile equivalent of the web's employee-count/seat-limit banner
    (templates/employees.html) and Seats & Billing page
    (templates/seat_checkout.html) -- same underlying data, same tables,
    just JSON instead of server-rendered HTML."""
    from utils.helpers import get_company_settings
    from utils.plan_limits import calculate_price, format_price_inr
    from database import get_master_db

    co = get_company_settings()
    try:
        db = get_db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute("SELECT COUNT(*) FROM employees")
        employee_count = cursor.fetchone()[0]
        cursor.close()
        db.close()
    except Exception:
        employee_count = 0

    auto_debit_status = None
    invoices = []
    try:
        from flask import g as _g
        conn = get_master_db()
        cur = conn.cursor(buffered=True)
        cur.execute(
            "SELECT status, quantity_synced, activated_at FROM auto_debit_mandates WHERE tenant_schema=%s",
            (_g.tenant_db,)
        )
        row = cur.fetchone()
        if row:
            auto_debit_status = {
                "status": row[0], "quantity_synced": row[1],
                "activated_at": row[2].isoformat() if row[2] else None,
            }
        cur.execute(
            "SELECT billing_period, employee_count, amount_paise, status, created_at "
            "FROM monthly_invoices WHERE tenant_schema=%s ORDER BY created_at DESC LIMIT 12",
            (_g.tenant_db,)
        )
        invoices = [
            {
                "billing_period": r[0].isoformat() if r[0] else None, "employee_count": r[1],
                "amount_display": format_price_inr(r[2]), "status": r[3],
                "created_at": r[4].isoformat() if r[4] else None,
            }
            for r in cur.fetchall()
        ]
        cur.close()
        conn.close()
    except Exception as exc:
        app_log.warning("api_billing_status: auto-debit lookup failed: %s", exc)

    return jsonify({
        "ok": True,
        "employee_count": employee_count,
        "paid_employee_slots": co.get("paid_employee_slots"),
        "monthly_bill_display": format_price_inr(calculate_price(employee_count)),
        "auto_debit": auto_debit_status,
        "invoices": invoices,
    })


@core_bp.route("/api/mobile/web_session_link", methods=["POST"])
@api_required
@limiter.limit("10 per minute")
def api_mobile_web_session_link():
    """Bridges the mobile app's Bearer-token session into a one-time,
    short-lived link that establishes a normal session-cookie admin login
    when opened -- lets the mobile app open /settings/seats (Razorpay
    Checkout for seat top-ups / auto-debit enrollment) in an in-app WebView
    without reimplementing that payment UI natively. See
    /mobile_bridge_login/<token> below for the redemption side."""
    from flask import g as _g

    username = _g.api_user
    raw_token = secrets.token_hex(32)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=5)
    with _db() as (cursor, conn):
        cursor.execute("DELETE FROM mobile_bridge_tokens WHERE expires_at < NOW()")
        cursor.execute(
            "INSERT INTO mobile_bridge_tokens (token_hash, admin_username, expires_at) VALUES (%s, %s, %s)",
            (token_hash, username, expires_at)
        )
        conn.commit()

    from utils.helpers import _safe_app_url
    url = f"{_safe_app_url()}{tpath('/mobile_bridge_login/' + raw_token)}"
    return jsonify({"ok": True, "url": url})


def _bridge_link_expired_response():
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        "<title>Link Expired</title>"
        "<style>body{font-family:'Segoe UI',sans-serif;background:#f1f5f9;display:flex;"
        "align-items:center;justify-content:center;min-height:100vh;margin:0;padding:24px;}"
        ".card{max-width:380px;text-align:center;background:#fff;border-radius:16px;"
        "padding:32px 24px;box-shadow:0 4px 20px rgba(0,0,0,0.08);}"
        "h1{font-size:17px;color:#0f172a;margin:0 0 8px;}"
        "p{font-size:13px;color:#64748b;margin:0;}</style></head><body>"
        "<div class='card'><h1>This link has expired</h1>"
        "<p>Go back to the app and try again.</p></div></body></html>",
        403,
    )


@core_bp.route("/mobile_bridge_login/<token>", methods=["GET"])
@limiter.limit("30 per minute")
def mobile_bridge_login(token):
    """Redeems a one-time bridge token (see /api/mobile/web_session_link
    above) into a real admin session-cookie login, then sends the browser
    (an in-app WebView on mobile) straight into /settings/seats -- the only
    page this bridge exists for today. No @admin_required here on purpose:
    this route's whole job is to CREATE a session, not require one already
    existing. Single-use (deleted immediately on redemption) and expires in
    5 minutes, same hash-and-expire shape as admin_users.reset_token."""
    token_hash = _hash_token(token)
    with _db() as (cursor, conn):
        cursor.execute(
            "SELECT admin_username FROM mobile_bridge_tokens WHERE token_hash=%s AND expires_at > NOW()",
            (token_hash,)
        )
        row = cursor.fetchone()
        if not row:
            cursor.close()
            conn.close()
            return _bridge_link_expired_response()
        username = row[0]
        cursor.execute("DELETE FROM mobile_bridge_tokens WHERE token_hash=%s", (token_hash,))
        cursor.execute("SELECT COALESCE(role,'admin') FROM admin_users WHERE username=%s", (username,))
        role_row = cursor.fetchone()
        conn.commit()

    if not role_row:
        return _bridge_link_expired_response()

    # Same session state blueprints/auth.py's admin_login sets on success,
    # minus device-fingerprint capture/new-IP email (this is an ephemeral
    # WebView session bridging an already-authenticated mobile session, not
    # a fresh login worth alerting on).
    session.clear()
    session["admin_logged_in"] = True
    session["admin_username"] = username
    session["admin_role"] = role_row[0]
    session["_session_created"] = time.time()
    session.permanent = True
    ensure_session_id(session)

    log_security_event(
        "auth.mobile_bridge_login", f"Mobile app bridged into a web session for '{username}'",
        level="INFO", identifier=username,
    )
    return redirect(tpath("/settings/seats"))


@core_bp.route("/api/settings/update", methods=["POST"])
@api_required
def api_settings_update():
    data = request.get_json() or {}
    return jsonify({"ok": True, "msg": "System settings updated successfully.", "settings": data})


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

    return jsonify({
        "ok": True, "token": token, "employee_id": emp_id,
        "name": row[0], "email": row[1],
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

    _domain_error = validate_employee_email_domain(email)
    if _domain_error:
        return jsonify({"ok": False, "msg": _domain_error}), 400

    # Same paid-seat cap blueprints/employees.py's add_employee_page() and
    # api_register_employee() already enforce on the web/token-authenticated
    # admin-add-employee paths -- this is the endpoint the mobile app's own
    # admin "Add Employee" screen calls (see mobile/src/api/client.js's
    # addEmployee()), so without this check a tenant's plan-limit cap was
    # only ever real on the web, not on mobile.
    _seat_error = add_employee_seat_cap_check()
    if _seat_error:
        return jsonify({"ok": False, "msg": _seat_error}), 403

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
        if email:
            _ecfg = get_email_config()
            if _ecfg:
                _login_url = employee_login_url()
                _html = (f"<p>Hi <strong>{name}</strong>, your account is ready.</p>"
                         f"<p>Employee ID: <strong>{emp_id}</strong></p>"
                         f"<p><a href=\"{_login_url}\">{_login_url}</a></p>")
                try:
                    send_email_smtp(email, f"Welcome {name} -- Your Account is Ready", _html, _ecfg)
                except Exception:
                    app_log.error("api_employee_signup: welcome email failed", exc_info=True)
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

