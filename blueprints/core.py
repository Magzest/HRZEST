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
from utils.helpers import (
    tpath, _db, get_auth_config, get_company_settings, validate_employee_email_domain,
    validate_employee_seat_available, employee_login_url,
)
from utils.email_utils import get_email_config, send_email_smtp
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
    # session["tenant_db"] is only ever set by _resolve_tenant() (app.py)
    # when the request resolved to a real tenant (either the URL carried a
    # recognized company slug, or -- the case that matters here -- an
    # earlier request in this same session already did, and it's cached).
    # Its absence means this visit is on the bare/apex domain with no live
    # tenant session at all. That's the signal used to decide "marketing
    # landing page" vs. "this company's own portal", without a second
    # lookup.
    #
    # Note this specific route can be hit with NO company slug in the URL
    # even while session["tenant_db"] is set -- e.g. someone already
    # logged into a company bookmarks/types the bare www.hrzest.com and
    # lands here directly. tpath() reflects the *current* request's
    # (slug-less) prefix, which would build an unprefixed destination and
    # lose the company slug from the URL bar -- so these redirects build
    # the destination from the session's own bound tenant_slug instead of
    # tpath(), to always land back on that company's own path.
    if session.get("tenant_db"):
        slug = session.get("tenant_slug")
        prefix = f"/{slug}" if slug else ""
        co = get_company_settings()
        if not co.get("setup_done"):
            return redirect(prefix + "/setup")
        if session.get("admin_logged_in"):
            return redirect(prefix + "/admin")
        if session.get("employee_id"):
            return redirect(prefix + "/employee_portal")
        return redirect(prefix + "/login")

    # Apex/marketing domain: send anyone with a live session straight to
    # where they were going; anonymous visitors get the public pitch.
    if session.get("admin_logged_in"):
        return redirect(tpath("/admin"))
    if session.get("employee_id"):
        return redirect(tpath("/employee_portal"))
    if session.get("platform_admin_logged_in"):
        return redirect(tpath("/super_admin"))
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
    return jsonify({})



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
    _seat_error = validate_employee_seat_available()
    if _seat_error:
        return jsonify({"ok": False, "msg": _seat_error, "buy_seats_url": tpath("/buy_seats")}), 402

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
                    send_email_smtp(email, f"Welcome {name} — Your Account is Ready", _html, _ecfg)
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

