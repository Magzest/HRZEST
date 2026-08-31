# -*- coding: utf-8 -*-
"""Authentication decorators, login lockout, and password hashing."""
import os
import json
import time
import datetime
import hashlib
import urllib.request  # noqa: F401 -- module-level so tests can monkeypatch auth_module.urllib.request.urlopen
import bcrypt as _bcrypt
from functools import wraps
from flask import session, request, jsonify, redirect, url_for, g as _flask_g
from werkzeug.security import check_password_hash as _wz_check_pw
from extensions import app_log, log_security_event
from utils.session_risk import is_session_compromised, evaluate_session_risk
from utils.async_writer import enqueue_write

# ── Password hashing (bcrypt with legacy pbkdf2 fallback) ────────────────────


def generate_password_hash(pw: str, **_) -> str:
    return _bcrypt.hashpw(pw.encode(), _bcrypt.gensalt(rounds=12)).decode()


def check_password_hash(pw_hash: str, pw: str) -> bool:
    if not pw_hash:
        return False
    if pw_hash.startswith("$2b$") or pw_hash.startswith("$2a$"):
        try:
            return _bcrypt.checkpw(pw.encode(), pw_hash.encode())
        except Exception:
            return False
    return _wz_check_pw(pw_hash, pw)


# ── Token hashing ─────────────────────────────────────────────────────────────
def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


from utils.helpers import _db


# ── Account lockout ───────────────────────────────────────────────────────────
# 5 matches what app.py's now-removed duplicate decorators actually enforced
# in production -- adopted as canonical here rather than the 10 this module
# used before consolidation, to avoid silently loosening lockout as a side
# effect of removing the duplicate.
_LOGIN_MAX_ATTEMPTS = 4
_LOGIN_LOCKOUT_MINUTES = 15

# ── CAPTCHA gate (Cloudflare Turnstile) ────────────────────────────────────────
# Unconfigured (no TURNSTILE_SECRET_KEY) means the gate is simply never
# triggered -- deliberately fail-open on missing config, not fail-closed.
# Failing closed here would mean "every login past attempt 2 is permanently
# rejected until an admin sets the key," a self-inflicted denial of service
# on the login system itself, unlike e.g. the malware-scan fail-closed
# default in utils/helpers.py where the blast radius is one rejected upload.
_TURNSTILE_SITE_KEY = os.environ.get("TURNSTILE_SITE_KEY", "")
_TURNSTILE_SECRET_KEY = os.environ.get("TURNSTILE_SECRET_KEY", "")
_TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
CAPTCHA_AFTER_ATTEMPTS = 2


def turnstile_enabled() -> bool:
    return bool(_TURNSTILE_SITE_KEY and _TURNSTILE_SECRET_KEY)


def _mask_identifier(identifier: str) -> str:
    """Obscure a username/employee-ID/email before it ever reaches a log
    line -- logs get shipped to less-trusted places (CloudWatch, a Slack
    webhook channel) than the DB itself, and there's no operational need
    for the full identifier to appear in either. The DB-side lockout logic
    (_check_login_lockout etc.) always uses the real, unmasked identifier --
    only what gets logged is obscured."""
    if not identifier:
        return "(empty)"
    if "@" in identifier:
        local, _, domain = identifier.partition("@")
        return f"{local[:1]}***@{domain}"
    if len(identifier) <= 3:
        return identifier[0] + "*" * (len(identifier) - 1)
    return identifier[:2] + "*" * (len(identifier) - 3) + identifier[-1]


def _get_failed_count(identifier: str, attempt_type: str = "admin") -> int:
    """Synchronous read of the current failed-attempt count -- used only to
    decide whether to render the CAPTCHA widget for the *next* attempt.
    Deliberately NOT read-after-write against _record_login_failure, which
    enqueues its DB write onto the background writer thread (see its own
    docstring) and may not have landed yet; callers instead compute
    "current + 1" against this value rather than re-querying post-write."""
    try:
        with _db() as (cur, _):
            cur.execute(
                "SELECT failed_count FROM login_attempts WHERE identifier=%s AND attempt_type=%s",
                (identifier, attempt_type),
            )
            row = cur.fetchone()
        return row[0] if row else 0
    except Exception:
        return 0


def verify_turnstile(token: str, remote_ip: str) -> bool:
    """Server-side verification against Cloudflare's siteverify endpoint --
    the client-submitted token proves nothing on its own without this
    round trip. Same urllib.request pattern already used for webhook
    delivery (utils/alerts.py) and the AI assistant's API call
    (utils/ai_assistant.py) -- no new dependency."""
    if not _TURNSTILE_SECRET_KEY or not token:
        return False
    try:
        import urllib.parse
        body = urllib.parse.urlencode({
            "secret": _TURNSTILE_SECRET_KEY,
            "response": token,
            "remoteip": remote_ip or "",
        }).encode()
        req = urllib.request.Request(_TURNSTILE_VERIFY_URL, data=body, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
            result = json.loads(resp.read().decode("utf-8"))
        return bool(result.get("success"))
    except Exception as e:
        app_log.warning("Turnstile verification request failed: %s", e)
        return False


def _check_login_lockout(identifier: str, attempt_type: str = "admin"):
    try:
        with _db() as (cur, _):
            cur.execute(
                "SELECT locked_until FROM login_attempts WHERE identifier=%s AND attempt_type=%s",
                (identifier, attempt_type)
            )
            row = cur.fetchone()
        if row and row[0] and row[0] > datetime.datetime.now():
            return True, row[0].strftime("%H:%M")
    except Exception:
        pass
    return False, None


def _record_login_failure(identifier: str, attempt_type: str = "admin"):
    """Called from the request-handling thread on every failed login -- must
    stay fast unconditionally, including under a brute-force flood, which is
    exactly when this gets called the most. The actual DB write (measured:
    3s median / 5.8s max latency under 60 concurrent attempts against one
    identifier, from row-lock + connection-pool contention) is handed off to
    the single background writer thread instead of run here. See
    utils/async_writer.py for why this is an in-process queue, not Celery.

    Trade-off, stated plainly: lockout becomes eventually consistent rather
    than exact-on-the-5th-request -- the counter increment and lockout check
    happen slightly after the response for attempt N has already been sent.
    Bounded by queue throughput (a single writer processing sequentially,
    typically sub-millisecond per write once decoupled from contention), not
    unbounded. Acceptable for a defense-in-depth control; would not be
    acceptable for the password check itself, which stays fully synchronous.
    """
    log_security_event(
        "auth.failure", "Failed login attempt", level="WARNING",
        identifier=_mask_identifier(identifier), attempt_type=attempt_type,
    )
    enqueue_write(_record_login_failure_db, identifier, attempt_type)


def _record_login_failure_db(identifier: str, attempt_type: str = "admin"):
    """The actual DB write -- runs only on the background writer thread,
    never on a request thread. Do not call this directly from a route."""
    try:
        with _db() as (cur, conn):
            cur.execute(
                "INSERT INTO login_attempts (identifier, attempt_type, failed_count, last_attempt) "
                "VALUES (%s, %s, 1, NOW()) "
                "ON CONFLICT (identifier, attempt_type) DO UPDATE SET "
                "failed_count=login_attempts.failed_count+1, last_attempt=NOW()",
                (identifier, attempt_type)
            )
            conn.commit()
            cur.execute(
                "SELECT failed_count FROM login_attempts WHERE identifier=%s AND attempt_type=%s",
                (identifier, attempt_type)
            )
            row = cur.fetchone()
            if row and row[0] >= _LOGIN_MAX_ATTEMPTS:
                lockout_until = datetime.datetime.now() + datetime.timedelta(minutes=_LOGIN_LOCKOUT_MINUTES)
                cur.execute(
                    "UPDATE login_attempts SET locked_until=%s WHERE identifier=%s AND attempt_type=%s",
                    (lockout_until, identifier, attempt_type)
                )
                conn.commit()
                log_security_event(
                    "auth.lockout", "Account locked after repeated failed logins", level="ERROR",
                    identifier=_mask_identifier(identifier), attempt_type=attempt_type,
                    failed_count=row[0], locked_until=lockout_until.isoformat(),
                )
    except Exception:
        pass


def _clear_login_failures(identifier: str, attempt_type: str = "admin"):
    """Enqueued onto the SAME writer queue as _record_login_failure_db, not
    written synchronously -- critical for correctness, not just speed. If
    this ran immediately while a burst of recent failures was still queued
    (e.g. a user's 5th failed attempt followed instantly by a correct 6th),
    a synchronous clear could run BEFORE those queued failure-writes land,
    and the failures would then land AFTER the clear -- undoing it, leaving
    a phantom failed_count despite the successful login. Routing both
    through one FIFO queue with a single consumer thread guarantees this
    clear always executes after every failure recorded before it, with no
    ordering race possible.
    """
    enqueue_write(_clear_login_failures_db, identifier, attempt_type)


def _clear_login_failures_db(identifier: str, attempt_type: str = "admin"):
    try:
        with _db() as (cur, conn):
            cur.execute(
                "DELETE FROM login_attempts WHERE identifier=%s AND attempt_type=%s",
                (identifier, attempt_type)
            )
            conn.commit()
    except Exception:
        pass


# ── Session kill-switch enforcement ───────────────────────────────────────────
def _reject_if_compromised(login_endpoint: str):
    """The actual kill switch. Checked on every authenticated request, not
    just at login -- a session flagged 'compromised' mid-lifetime (see
    utils/session_risk.py) is dead on its very next request regardless of
    whether the browser tab that owns it ever sees the SSE push telling it
    to log itself out. Returns a redirect Response if the session should be
    killed, or None if it's fine to proceed."""
    sid = session.get("_sid")
    if sid and is_session_compromised(sid):
        log_security_event("session.rejected", "Rejected a request from a compromised session",
                           level="WARNING", identifier=session.get("admin_username")
                           or session.get("employee_id"))
        session.clear()
        return redirect(url_for(login_endpoint, locked="1"))
    return None


# ── Web session guards ────────────────────────────────────────────────────────
def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("admin_logged_in") and session.get("employee_id"):
            session.pop("employee_id", None)
            session.pop("employee_name", None)
            session.pop("employee_role", None)
        if not session.get("admin_logged_in"):
            # employee_id present but no admin session = an authenticated
            # employee reaching for an admin-only route, not just an
            # anonymous visitor -- that's the signal worth a WARNING; a
            # plain anonymous hit is routine enough to log at INFO only.
            _level = "WARNING" if session.get("employee_id") else "INFO"
            log_security_event("access.denied", "Unauthenticated request to admin-only route",
                               level=_level, required="admin")
            is_ajax = (
                request.headers.get("X-Requested-With") == "XMLHttpRequest"
                or request.headers.get("Accept", "").startswith("application/json")
                or request.headers.get("Content-Type", "").startswith("application/json")
                or request.is_json
            )
            if is_ajax:
                return jsonify({"ok": False, "msg": "Session expired. Please log in again.",
                                "redirect": url_for("auth.admin_login")}), 401
            return redirect(url_for("auth.admin_login"))
        _killed = _reject_if_compromised("auth.admin_login")
        if _killed:
            return _killed
        return f(*args, **kwargs)
    return wrapper


def employee_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("admin_logged_in") and session.get("employee_id"):
            session.pop("employee_id", None)
            session.pop("employee_name", None)
            session.pop("employee_role", None)
            return redirect("/admin")
        if not session.get("employee_id"):
            log_security_event("access.denied", "Unauthenticated request to employee-only route",
                               level="INFO", required="employee")
            # There is no standalone "employee_login" endpoint anymore --
            # employee and admin credentials are both checked by the one
            # unified /login page. The literal "/employee_login" path this
            # used to redirect to 404s (dead route); auth.admin_login is
            # also what url_for(...) resolves to a build error for below.
            return redirect(url_for("auth.admin_login"))
        _killed = _reject_if_compromised("auth.admin_login")
        if _killed:
            return _killed
        # Prevent bypassing forced password change by navigating directly to portal
        from flask import request as _req
        if session.get("_fpc") and _req.endpoint not in ("auth.force_change_pin", "force_change_pin"):
            return redirect("/force_change_pin")
        return f(*args, **kwargs)
    return wrapper


def role_required(*allowed_roles):
    """Like admin_required, but also requires session['admin_role'] to be one
    of allowed_roles. admin_required alone only checks admin_logged_in, so it
    grants every admin-side role (admin/manager/soc_analyst) equally -- use
    this instead for routes that must stay admin-only (payroll mutation,
    employee deletion, credential resets, PII-bearing payslip views)."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not session.get("admin_logged_in"):
                log_security_event("access.denied", "Unauthenticated request to role-restricted route",
                                   level="INFO", required="|".join(allowed_roles))
                is_ajax = (
                    request.headers.get("X-Requested-With") == "XMLHttpRequest"
                    or request.headers.get("Accept", "").startswith("application/json")
                    or request.is_json
                )
                if is_ajax:
                    return jsonify({"ok": False, "msg": "Session expired. Please log in again.",
                                    "redirect": url_for("auth.admin_login")}), 401
                return redirect(url_for("auth.admin_login"))
            _killed = _reject_if_compromised("auth.admin_login")
            if _killed:
                return _killed
            user_role = session.get("admin_role", "admin")
            if user_role not in allowed_roles and user_role != "superadmin":
                log_security_event("access.denied", "Insufficient role for restricted route",
                                   level="ERROR", required="|".join(allowed_roles),
                                   actual_role=session.get("admin_role"),
                                   identifier=session.get("admin_username"))
                sid = session.get("_sid")
                if sid:
                    evaluate_session_risk(
                        sid, session.get("admin_username") or "unknown", "admin",
                        weight=25, event_type="access.denied",
                        reason="Repeated insufficient-role access attempts",
                    )
                return jsonify({"ok": False, "msg": "Insufficient permissions."}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ── API Bearer token guards ───────────────────────────────────────────────────
def api_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            log_security_event("access.denied", "API request missing Bearer token",
                               level="INFO", required="admin_api")
            return jsonify({"ok": False, "msg": "Unauthorized"}), 401
        # Never log the token or its hash -- it's the literal credential /
        # DB lookup key, and logging it would hand anyone with log access
        # something they could use to fingerprint or replay-correlate it.
        token_hash = _hash_token(auth[7:])
        with _db() as (cursor, _conn):
            cursor.execute("DELETE FROM api_tokens WHERE expires_at < NOW()")
            _conn.commit()
            cursor.execute(
                """
                SELECT t.identity, COALESCE(u.is_active, 1)
                FROM api_tokens t
                LEFT JOIN admin_users u ON u.username = t.identity
                WHERE t.token=%s AND t.token_type='admin' AND t.expires_at > NOW()
                """,
                (token_hash,)
            )
            row = cursor.fetchone()
        if not row:
            log_security_event("access.denied", "API request with invalid or expired admin token",
                               level="WARNING", required="admin_api")
            return jsonify({"ok": False, "msg": "Invalid or expired token"}), 401
        # Re-checked on every request (not just at login) so that
        # deactivating an account revokes its existing tokens immediately,
        # instead of leaving them valid until natural expiry.
        if not row[1]:
            log_security_event("access.denied", "API request from deactivated admin account",
                               level="WARNING", required="admin_api", identifier=row[0])
            return jsonify({"ok": False, "msg": "This account has been deactivated. Contact your administrator."}), 403
        _flask_g.api_user = row[0]
        return f(*args, **kwargs)
    return wrapper


def api_role_required(*allowed_roles):
    """Session-based role_required's counterpart for Bearer-token API routes.

    api_required alone only proves the token is valid -- every admin API
    token is treated as equally privileged regardless of the issuing
    admin's actual role, so a manager's or soc_analyst's token gets the
    same bulk salary/PII data an admin's token would. Must sit UNDER
    @api_required (i.e. @api_required above, this decorator below) so
    _flask_g.api_user is already set by the time this runs.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            username = getattr(_flask_g, "api_user", None)
            with _db() as (cursor, _conn):
                cursor.execute("SELECT COALESCE(role,'admin') FROM admin_users WHERE username=%s", (username,))
                row = cursor.fetchone()
            actual_role = row[0] if row else None
            if actual_role not in allowed_roles:
                log_security_event(
                    "access.denied", "API token's role insufficient for restricted endpoint",
                    level="ERROR", required="|".join(allowed_roles),
                    actual_role=actual_role, identifier=username,
                )
                return jsonify({"ok": False, "msg": "Insufficient permissions."}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator


def employee_api_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            log_security_event("access.denied", "API request missing Bearer token",
                               level="INFO", required="employee_api")
            return jsonify({"ok": False, "msg": "Unauthorized"}), 401
        token_hash = _hash_token(auth[7:])
        with _db() as (cursor, _conn):
            cursor.execute("DELETE FROM api_tokens WHERE expires_at < NOW()")
            _conn.commit()
            cursor.execute(
                "SELECT identity FROM api_tokens WHERE token=%s AND token_type='employee' AND expires_at > NOW()",
                (token_hash,)
            )
            row = cursor.fetchone()
        if not row:
            log_security_event("access.denied", "API request with invalid or expired employee token",
                               level="WARNING", required="employee_api")
            return jsonify({"ok": False, "msg": "Invalid or expired token"}), 401
        _flask_g.api_emp_id = row[0]
        return f(*args, **kwargs)
    return wrapper


def resolve_admin_identity():
    """Session (web) or Bearer admin token (mobile) -- for routes usable
    from both without a route-level decorator, since admin_required
    redirects to a login page rather than returning JSON, which breaks a
    Bearer-token mobile client. Returns the admin username, or None if
    neither proves a logged-in, active admin. Used by blueprints/ai_hrms.py
    and blueprints/email_blast.py.

    Mirrors admin_required's compromised-session check (a session flagged
    mid-lifetime by utils/session_risk.py must not keep working just
    because this helper skips the decorator) -- but only checks, doesn't
    clear()/redirect like the decorator does, since callers here are JSON
    sub-actions, not full page loads.
    """
    if session.get("admin_logged_in"):
        sid = session.get("_sid")
        if sid and is_session_compromised(sid):
            return None
        return session.get("admin_username", "admin")
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token_hash = _hash_token(auth[7:])
    with _db() as (cursor, _conn):
        cursor.execute(
            """
            SELECT t.identity, COALESCE(u.is_active, 1)
            FROM api_tokens t
            LEFT JOIN admin_users u ON u.username = t.identity
            WHERE t.token=%s AND t.token_type='admin' AND t.expires_at > NOW()
            """,
            (token_hash,)
        )
        row = cursor.fetchone()
    if not row or not row[1]:
        return None
    return row[0]


# ── Email Settings 2FA step-up gate ───────────────────────────────────────────
# Same time.time()-in-session idiom as the WebAuthn fingerprint window
# (utils/webauthn_utils.py:_WA_FP_VERIFY_WINDOW_SEC), but NOT single-use/popped
# -- this gate needs to stay valid across several requests (view, edit, reveal
# password) within the window, and the window is refreshed on every authorized
# request so it reads as "15 minutes of inactivity", matching the requirement,
# rather than a fixed 15 minutes from the moment the code was entered.
EMAIL_2FA_WINDOW_SEC = 15 * 60


def email_settings_step_up_valid() -> bool:
    ts = session.get("email_2fa_verified_at", 0)
    return bool(ts) and (time.time() - ts) <= EMAIL_2FA_WINDOW_SEC


def email_settings_step_up_refresh():
    session["email_2fa_verified_at"] = time.time()


def email_settings_step_up_clear():
    session.pop("email_2fa_verified_at", None)


# ── SOC Analyst security dashboard step-up gate ───────────────────────────────
# Deliberately a SEPARATE step-up flag from the Email Settings one above, even
# though both ultimately check the same enrolled TOTP secret (utils/totp.py --
# one MFA seed per admin account, reused across every step-up gate, matching
# how a real authenticator app works: one enrollment, many uses). Passing the
# Email Settings gate must not silently also unlock the SOC dashboard, and
# vice versa -- each sensitive area gets its own proof-of-recent-verification,
# not one that leaks scope to the others.
#
# Shorter window than Email Settings (10 min vs 15) because this gate sits in
# front of security telemetry (who's compromised, who's locked out) rather
# than a config form -- a smaller blast radius if a SOC analyst's unlocked tab
# is left unattended, but still short enough not to force re-entering a code
# on every click while actively triaging.
SOC_ANALYST_ROLE = "soc_analyst"
SOC_2FA_WINDOW_SEC = 10 * 60

# HR accounts (created/managed via blueprints/admin_views.py's /hr_accounts
# page) log in through the same general /login as admin, unlike
# SOC_ANALYST_ROLE -- but role_required("admin") elsewhere still scopes
# them to employees/attendance/leave/onboarding/performance/tickets/
# documents, away from tenant/system settings, company management, and
# analytics that a full admin session carries.
HR_ROLE = "hr"


def soc_step_up_refresh():
    session["soc_2fa_verified_at"] = time.time()


# ── Security Settings hub step-up gate ────────────────────────────────────────
# Same time.time()-in-session step-up pattern as Email Settings, guarding the
# consolidated "Security" tab in Settings (session timeout, audit log, MFA
# status, SOC entry point, security posture -- all in one place, per the
# row-wise hub requirement).
#
# This one has NO role restriction -- every admin can open this hub with just
# their own TOTP code.


def security_settings_step_up_clear():
    session.pop("security_settings_2fa_verified_at", None)


def require_email_2fa(f):
    """Gate for Email Settings routes (SMTP config, including a
    reveal-plaintext-password action) behind a recent TOTP step-up --
    see email_settings_step_up_valid() above."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not email_settings_step_up_valid():
            log_security_event(
                "access.denied", "Email Settings accessed without a valid 2FA step-up",
                level="WARNING", identifier=session.get("admin_username"),
            )
            return jsonify({"ok": False, "msg": "2FA verification required"}), 403
        return f(*args, **kwargs)
    return wrapper


# ── Object-level authorization (BOLA/IDOR guard) ──────────────────────────────
def enforce_ownership(resource_owner_id, resource_type, resource_id=None):
    """Check whether the current session may access a resource it doesn't own.

    Centralizes the ownership idiom that already existed hand-rolled in
    payroll.py (view_payslip) and documents.py (download_document): admin
    bypass, else the session's own employee_id must equal the resource's
    owning employee_id. Call this AFTER fetching the row (you need to know
    who owns it), not as a pre-request decorator -- most resources here are
    looked up by an opaque row id (document id, payslip period), not by an
    id that itself encodes the owner.

    Every denial logs at ERROR, which utils/alerts.py turns into a real-time
    webhook alert (extensions.py:log_security_event) -- a BOLA probe is never
    silently swallowed, regardless of which route calls this.

    Returns True if access is allowed, False if it should be denied (caller
    decides the response -- redirect, flash, 403 JSON, etc., to match its
    existing route style).
    """
    if session.get("admin_logged_in"):
        return True
    requester = session.get("employee_id")
    if requester and requester == resource_owner_id:
        return True
    log_security_event(
        "access.denied", f"Attempted cross-employee access to {resource_type}",
        level="ERROR", identifier=requester or "anonymous",
        resource_type=resource_type, resource_id=resource_id,
        requested_owner=resource_owner_id,
    )
    return False
