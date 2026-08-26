# -*- coding: utf-8 -*-
"""Auth blueprint -- login, logout, password reset, WebAuthn."""
import os
import re
import time
import base64
import secrets
import hashlib
import datetime
import html as _html
from flask import (
    Blueprint, request, session, redirect, jsonify, render_template, g,
)

from extensions import app, limiter, app_log, log_security_event
from database import get_db_connection
from utils.auth import (
    generate_password_hash, check_password_hash, _hash_token,
    _check_login_lockout, _record_login_failure, _clear_login_failures,
    admin_required, role_required, employee_required, employee_api_required,
    _get_failed_count, verify_turnstile, turnstile_enabled,
    CAPTCHA_AFTER_ATTEMPTS, _TURNSTILE_SITE_KEY, SOC_ANALYST_ROLE, HR_ROLE,
    api_required,
)
from utils.helpers import tpath, get_company_settings, _audit, _db, _safe_app_url
from utils.email_utils import get_email_config, send_email_smtp, send_email_async, notify_if_new_login_ip
from utils.session_risk import ensure_session_id
from utils.device_utils import get_or_create_device_token, set_device_cookie, record_login_device
from utils.totp import verify_totp_code, send_mfa_login_email, mark_totp_enabled
from utils.face_utils import verify_uploaded_face
from utils.webauthn_utils import (
    webauthn, _webauthn_available, _wa_rp_id, _wa_check_rp_id, _wa_origins,
    _wa_b64url_encode, _wa_b64url_decode, _wa_verify_and_store_registration,
    _mobile_biometric_issue_nonce, _mobile_biometric_attest,
)

UPLOAD_FOLDER = app.config["UPLOAD_FOLDER"]

# How long a successful kiosk face-match (see api_kiosk_enroll_face_verify)
# stays valid as proof of identity before it must be redone. Mirrors the
# window pattern used for wa_fp_verified_at/soc_2fa_verified_at elsewhere --
# short enough that a stolen session cookie right after enrollment can't
# reuse a stale face-match to enroll a second, different employee_id.
KIOSK_FACE_VERIFY_WINDOW_SEC = 5 * 60
if _webauthn_available:
    from utils.webauthn_utils import (
        AuthenticatorSelectionCriteria, AuthenticatorAttachment,
        UserVerificationRequirement, ResidentKeyRequirement,
        PublicKeyCredentialDescriptor, AuthenticatorTransport,
        COSEAlgorithmIdentifier, AttestationConveyancePreference,
    )

auth_bp = Blueprint("auth", __name__)

# Detection only -- never a security control. Every query in this codebase
# is already parameterized (verified separately), so a payload matching
# this can't actually inject anything; it just tells us someone is
# probing rather than mistyping a username. Deliberately narrow (classic
_INJECTION_PATTERN_RE = re.compile(
    r"('|--|;|\bunion\b|\bor\b\s+['\"0-9]|<script\b)", re.IGNORECASE
)

_MFA_OTP_TTL_SEC = 300


def _start_login_mfa(co, login_template, kind, identifier, email, role_label):
    """Common second step once a password has already checked out (called
    from admin_login()'s admin/employee branches): email a one-time code
    instead of completing the session immediately, and redirect to
    /mfa_verify to finish."""
    if not email:
        log_security_event(
            "auth.mfa_email_missing", "Account has no email on file for login MFA delivery",
            level="ERROR", identifier=identifier,
        )
        _record_login_failure(identifier)
        return render_template(login_template, co=co, error="Invalid credentials. Check your ID and password.")

    otp_code = f"{secrets.randbelow(900000) + 100000}"
    send_mfa_login_email(email, identifier, role_label, "", otp_code)
    session.clear()
    session["mfa_pending"] = True
    session["mfa_kind"] = kind
    session["mfa_user"] = identifier
    session["mfa_otp_code"] = otp_code
    session["mfa_issued_at"] = time.time()
    return redirect(tpath("/mfa_verify"))


def _capture_and_cookie_device(resp, owner_kind, owner_id, sid):
    """Best-effort: record this login's device (utils/device_utils.py) on
    whichever schema get_db_connection() currently resolves to, and stamp
    the browser's device-token cookie on the response we're about to
    return. Never fails or blocks the login itself -- a device-tracking
    hiccup must not be able to lock someone out of signing in."""
    try:
        token, is_new = get_or_create_device_token(request)
        record_login_device(get_db_connection, owner_kind, owner_id, token, sid, request)
        if is_new:
            set_device_cookie(resp, token)
    except Exception as exc:
        app_log.warning("device capture failed for %s '%s': %s", owner_kind, owner_id, exc)
    return resp


@auth_bp.route("/login", methods=["GET", "POST"])
@auth_bp.route("/admin_login", methods=["GET", "POST"])
@auth_bp.route("/admin-login", methods=["GET", "POST"])
@limiter.limit("60 per 15 minutes")
@limiter.limit("20 per minute")
@limiter.limit("150 per hour")
def admin_login():
    co = get_company_settings()
    if session.get("admin_logged_in"):
        return redirect(tpath("/admin"))
    if session.get("employee_id"):
        return redirect(tpath("/employee_portal"))
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "").strip()
        # Password is intentionally never inspected or logged here -- only
        # the identifier field is checked, and only its shape (matched
        # pattern name), never the raw value, goes into the alert.
        _inj_match = _INJECTION_PATTERN_RE.search(identifier)
        if _inj_match:
            log_security_event(
                "auth.injection_attempt",
                "Login identifier matched a SQL-injection/XSS-shaped pattern",
                level="ERROR", pattern=_inj_match.group(1)[:20],
            )
        # Check lockout before attempting any credential check
        locked, until = _check_login_lockout(identifier)
        if locked:
            return render_template("admin_login.html", co=co,
                                   error=f"Account locked until {until} due to too many failed attempts.")

        # CAPTCHA gate: once this identifier has CAPTCHA_AFTER_ATTEMPTS (2)
        # failures already on record, every further attempt must carry a
        # verified Turnstile token before the password is even checked.
        # No-op entirely when Turnstile isn't configured (turnstile_enabled()
        # is False) -- see utils/auth.py's fail-open rationale.
        current_failed_count = _get_failed_count(identifier)
        needs_captcha = turnstile_enabled() and current_failed_count >= CAPTCHA_AFTER_ATTEMPTS
        if needs_captcha:
            token = request.form.get("cf-turnstile-response", "")
            if not verify_turnstile(token, request.remote_addr):
                return render_template("admin_login.html", co=co,
                                       error="Please complete the verification challenge.",
                                       show_captcha=True, turnstile_site_key=_TURNSTILE_SITE_KEY)

        # Whether the failure paths below should show the widget on the
        # NEXT attempt -- computed from current_failed_count rather than a
        # fresh DB read, since _record_login_failure's write is async and
        # may not have landed by the time this response is built.
        will_need_captcha = turnstile_enabled() and (current_failed_count + 1) >= CAPTCHA_AFTER_ATTEMPTS

        # Try admin credentials first
        with _db() as (cursor, db):
            cursor.execute(
                "SELECT password, COALESCE(role,'admin'), email, COALESCE(is_active,1) FROM admin_users WHERE username=%s",
                (identifier,)
            )
            admin_row = cursor.fetchone()
        if admin_row and admin_row[1] == SOC_ANALYST_ROLE and check_password_hash(admin_row[0], password):
            # SOC analyst accounts are deliberately a separate credential
            # (blueprints/secops.py's /sp_admin/login) -- letting it also
            # complete the regular admin login here would grant it a full
            # admin_required session (payroll, tenant settings, company
            # management, everything), which that dedicated, narrowly-scoped
            # login exists specifically to avoid. Same generic error either
            # way, no distinction leaked between "wrong role" and "wrong
            # password". HR accounts use this same general login instead
            # (see the is_active check and role='hr' redirect below) --
            # role_required("admin") already scopes them away from
            # admin-only pages, so a second gate here was redundant.
            _record_login_failure(identifier)
            return render_template(
                "admin_login.html", co=co,
                error="Invalid credentials. Check your ID and password.",
                show_captcha=will_need_captcha, turnstile_site_key=_TURNSTILE_SITE_KEY,
            )
        if admin_row and check_password_hash(admin_row[0], password):
            if not admin_row[3]:
                # Terminated account -- same generic error as a wrong
                # password, so a probe can't distinguish "deactivated" from
                # "doesn't exist"/"wrong password".
                _record_login_failure(identifier)
                log_security_event(
                    "access.denied", "Login attempt against a terminated admin account",
                    level="WARNING", identifier=identifier,
                )
                return render_template(
                    "admin_login.html", co=co,
                    error="Invalid credentials. Check your ID and password.",
                    show_captcha=will_need_captcha, turnstile_site_key=_TURNSTILE_SITE_KEY,
                )
            _clear_login_failures(identifier)
            # Upgrade legacy hash to bcrypt on first successful login
            if admin_row[0] and not admin_row[0].startswith("$2"):
                with _db() as (_uc, _ud):
                    _uc.execute("UPDATE admin_users SET password=%s WHERE username=%s",
                                (generate_password_hash(password), identifier))
                    _ud.commit()
            if app.config.get("MANDATORY_LOGIN_MFA", False):
                return _start_login_mfa(co, "admin_login.html", "admin_users", identifier, admin_row[2],
                                         "Executive Administrator" if admin_row[1] == "admin" else admin_row[1].title())
            session.clear()
            session["admin_logged_in"] = True
            session["admin_username"] = identifier
            session["admin_role"] = admin_row[1]
            session["_session_created"] = time.time()
            session["soc_step_up_until"] = time.time() + 600
            session.permanent = True
            sid = ensure_session_id(session)
            log_security_event(
                "auth.admin_login_success", f"Admin login for '{identifier}' (role={admin_row[1]})",
                level="INFO", identifier=identifier,
            )
            if admin_row[2]:
                notify_if_new_login_ip(identifier, "admin", request.remote_addr, identifier, admin_row[2])
            if admin_row[1] == HR_ROLE:
                dest = redirect(tpath("/employees"))
            else:
                dest = redirect(tpath("/admin"))
            return _capture_and_cookie_device(dest, HR_ROLE if admin_row[1] == HR_ROLE else "admin", identifier, sid)
        # Try employee credentials
        with _db() as (cursor, db):
            cursor.execute(
                "SELECT employee_id, name, role, password, COALESCE(force_pin_change,0), email FROM employees WHERE employee_id=%s",
                (identifier,)
            )
            emp_row = cursor.fetchone()
        if emp_row:
            stored_pwd = emp_row[3]
            if not stored_pwd or not check_password_hash(stored_pwd, password):
                _record_login_failure(identifier)
                return render_template("admin_login.html", co=co, error="Invalid credentials. Check your ID and password.",
                                       show_captcha=will_need_captcha, turnstile_site_key=_TURNSTILE_SITE_KEY)
            _clear_login_failures(identifier)
            # Upgrade legacy hash to bcrypt on first successful login
            if stored_pwd and not stored_pwd.startswith("$2"):
                with _db() as (_uc, _ud):
                    _uc.execute("UPDATE employees SET password=%s WHERE employee_id=%s",
                                (generate_password_hash(password), emp_row[0]))
                    _ud.commit()
            if app.config.get("MANDATORY_LOGIN_MFA", True):
                return _start_login_mfa(co, "admin_login.html", "employee", emp_row[0], emp_row[5], "Employee")
            session.clear()
            session["employee_id"] = emp_row[0]
            session["employee_name"] = emp_row[1]
            session["employee_role"] = emp_row[2] or ""
            session["_session_created"] = time.time()
            session["_fpc"] = bool(emp_row[4])  # force_pin_change flag in session
            session.permanent = True
            sid = ensure_session_id(session)
            if emp_row[5]:
                notify_if_new_login_ip(emp_row[0], "employee", request.remote_addr, emp_row[1], emp_row[5])
            dest = redirect(tpath("/force_change_pin")) if emp_row[4] else redirect(tpath("/employee_portal"))
            return _capture_and_cookie_device(dest, "employee", emp_row[0], sid)
        _record_login_failure(identifier)
        return render_template("admin_login.html", error="Invalid credentials. Check your ID and password.",
                               show_captcha=will_need_captcha, turnstile_site_key=_TURNSTILE_SITE_KEY)
    return render_template("admin_login.html", co=co)


@auth_bp.route("/mfa_verify", methods=["GET", "POST"])
# Raised from 8/15min for the same reason as admin_login above -- all
# visitors share one apparent IP under rootless Podman's port-forwarding.
# The OTP itself is still the real defense (short TTL, compare_digest).
@limiter.limit("40 per 15 minutes")
def mfa_verify():
    """Completion step for _start_login_mfa(): checks the emailed one-time
    code, then builds the real admin/HR/employee session. Deliberately
    separate from secops.py's own /mfa_login_verify -- SOC keeps its own
    dedicated flow untouched, rather than risking that already-tested
    portal by sharing this route with it."""
    username = session.get("mfa_user")
    kind = session.get("mfa_kind")
    if not username or not session.get("mfa_pending") or kind not in ("admin_users", "employee"):
        return redirect(tpath("/login"))

    issued_at = session.get("mfa_issued_at") or 0
    if (time.time() - issued_at) > _MFA_OTP_TTL_SEC:
        session.clear()
        return render_template("mfa_verify.html", error="Your code expired. Please log in again.")

    if request.method == "POST":
        submitted = (request.form.get("otp_code") or "").strip()
        expected = session.get("mfa_otp_code") or ""
        if submitted and expected and secrets.compare_digest(submitted, expected):
            if kind == "employee":
                with _db() as (cursor, db):
                    cursor.execute(
                        "SELECT employee_id, name, role, COALESCE(force_pin_change,0), email "
                        "FROM employees WHERE employee_id=%s", (username,)
                    )
                    row = cursor.fetchone()
                if not row:
                    session.clear()
                    return redirect(tpath("/login"))
                session.clear()
                session["employee_id"] = row[0]
                session["employee_name"] = row[1]
                session["employee_role"] = row[2] or ""
                session["_session_created"] = time.time()
                session["_fpc"] = bool(row[3])
                session.permanent = True
                sid = ensure_session_id(session)
                if row[4]:
                    notify_if_new_login_ip(row[0], "employee", request.remote_addr, row[1], row[4])
                dest = redirect(tpath("/force_change_pin")) if row[3] else redirect(tpath("/employee_portal"))
                return _capture_and_cookie_device(dest, "employee", row[0], sid)
            else:
                with _db() as (cursor, db):
                    cursor.execute("SELECT role, email FROM admin_users WHERE username=%s", (username,))
                    row = cursor.fetchone()
                if not row:
                    session.clear()
                    return redirect(tpath("/login"))
                role = row[0] or "admin"
                # This emailed code IS this login's MFA -- mark enrolled so
                # app.py's _enforce_admin_mfa_enrollment (which still applies
                # to admin/manager/hr sessions) doesn't also demand a
                # separate authenticator-app enrollment right after.
                mark_totp_enabled(username)
                session.clear()
                session["admin_logged_in"] = True
                session["admin_username"] = username
                session["admin_role"] = role
                session["_session_created"] = time.time()
                session.permanent = True
                sid = ensure_session_id(session)
                if row[1]:
                    notify_if_new_login_ip(username, "admin", request.remote_addr, username, row[1])
                dest = redirect(tpath("/employees" if role == HR_ROLE else "/admin"))
                return _capture_and_cookie_device(dest, HR_ROLE if role == HR_ROLE else "admin", username, sid)

        log_security_event("auth.mfa_failure", "Invalid login MFA code", level="WARNING", identifier=username)
        return render_template("mfa_verify.html", username=username, error="Invalid code. Please try again.")

    return render_template("mfa_verify.html", username=username)


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    # "/" is the platform operator's own login (see blueprints/core.py's
    # home()), not somewhere a tenant admin logging out should land --
    # send them back to the check-in kiosk instead, same as before "/"
    # was repurposed.
    return redirect(tpath("/checkin"))


@auth_bp.route("/change_admin_password", methods=["POST"])
@admin_required
def change_admin_password():
    current_pw = request.form.get("current_password", "")
    new_pw = request.form.get("new_password", "")
    confirm_pw = request.form.get("confirm_password", "")
    # Use the logged-in admin's username, not a hardcoded 'admin' string.
    # A hardcoded value lets any admin account change the 'admin' password
    # if they know its current value -- a cross-account privilege escalation.
    logged_in_as = session.get("admin_username", "admin")
    if not new_pw or new_pw != confirm_pw:
        return redirect(tpath("/admin?pwd_error=mismatch"))
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT password FROM admin_users WHERE username=%s", (logged_in_as,))
    row = cursor.fetchone()
    if not row or not check_password_hash(row[0], current_pw):
        cursor.close()
        db.close()
        return redirect(tpath("/admin?pwd_error=wrong"))
    cursor.execute(
        "UPDATE admin_users SET password=%s WHERE username=%s",
        (generate_password_hash(new_pw), logged_in_as)
    )
    db.commit()
    cursor.close()
    db.close()
    return redirect(tpath("/admin?pwd_ok=1"))


@auth_bp.route("/api/admin/password", methods=["POST"])
@api_required
def api_change_admin_password():
    """Bearer-token twin of change_admin_password() above -- same
    own-account-only scoping (the Bearer token's identity, not a
    caller-supplied username, so this can't be used to change a different
    account's password) and no role restriction, matching @admin_required
    above (any admin-panel role, not just Admin, can change their own
    password on web)."""
    from flask import g as _g
    data = request.get_json(silent=True) or {}
    current_pw = data.get("current_password") or ""
    new_pw = data.get("new_password") or ""
    confirm_pw = data.get("confirm_password") or ""
    username = _g.api_user

    if not new_pw or new_pw != confirm_pw:
        return jsonify({"ok": False, "msg": "New password and confirmation must match."}), 400
    if len(new_pw) < 8:
        return jsonify({"ok": False, "msg": "New password must be at least 8 characters."}), 400

    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT password FROM admin_users WHERE username=%s", (username,))
    row = cursor.fetchone()
    if not row or not check_password_hash(row[0], current_pw):
        cursor.close()
        db.close()
        return jsonify({"ok": False, "msg": "Current password is incorrect."}), 400
    cursor.execute(
        "UPDATE admin_users SET password=%s WHERE username=%s",
        (generate_password_hash(new_pw), username)
    )
    db.commit()
    cursor.close()
    db.close()
    log_security_event("auth.password_changed", f"Password changed for '{username}' via mobile app",
                        level="INFO", identifier=username)
    return jsonify({"ok": True, "msg": "Password updated."})


@auth_bp.route("/admin_set_recovery_email", methods=["POST"])
@admin_required
def admin_set_recovery_email():
    email = request.form.get("recovery_email", "").strip()
    username = session.get("admin_username", "admin")
    if email:
        db = get_db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute("UPDATE admin_users SET email=%s WHERE username=%s", (email, username))
        db.commit()
        cursor.close()
        db.close()
    return redirect(tpath("/admin?email_ok=1#password-management"))


@auth_bp.route("/admin_forgot_password", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def admin_forgot_password():
    if request.method == "GET":
        return render_template("admin_forgot_password.html",
                               sent=False, error=None)
    admin_email = request.form.get("email", "").strip().lower()
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT id FROM admin_users WHERE LOWER(email)=%s", (admin_email,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        db.close()
        # Return the same message whether the email exists or not (no account enumeration)
        return render_template("admin_forgot_password.html", sent=True, error=None)
    token = secrets.token_hex(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expiry = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    admin_id = row[0]
    cursor.execute(
        "UPDATE admin_users SET reset_token=%s, reset_token_expiry=%s WHERE id=%s",
        (token_hash, expiry, admin_id)
    )
    db.commit()
    cursor.close()
    db.close()
    cfg = get_email_config()
    if not cfg:
        return render_template("admin_forgot_password.html", sent=False,
                               error="Email service not configured. Go to Admin → Email Settings first.")
    reset_url = f"{_safe_app_url()}/admin_reset_password/{token}"
    html_body = f"""
<div style="font-family:Segoe UI,sans-serif;max-width:520px;margin:auto;background:#f8fafc;border-radius:16px;overflow:hidden;border:1px solid #dbeafe;">
  <div style="background:#1e3a8a;padding:24px 28px;color:white;">
    <div style="font-size:20px;font-weight:700;">🔐 Admin Password Reset</div>
    <div style="font-size:13px;opacity:0.75;margin-top:4px;">HRzest.com</div>
  </div>
  <div style="padding:28px;">
    <p style="font-size:15px;color:#1e293b;margin-bottom:20px;">You requested a password reset for the admin account.</p>
    <a href="{reset_url}" style="display:block;text-align:center;padding:14px 28px;background:#1e3a8a;color:white;border-radius:10px;text-decoration:none;font-size:15px;font-weight:700;margin-bottom:20px;">
      Reset My Password
    </a>
    <p style="font-size:13px;color:#64748b;">This link expires in <strong>1 hour</strong>. If you did not request this, ignore this email.</p>
    <p style="font-size:12px;color:#94a3b8;margin-top:12px;">Or copy this link: {reset_url}</p>
  </div>
</div>"""
    try:
        send_email_smtp(admin_email, "Admin Password Reset -- HRzest.com", html_body, cfg)
    except Exception:
        app_log.error("Failed to send admin password reset email", exc_info=True)
        return render_template("admin_forgot_password.html", sent=False,
                               error="Failed to send email. Please check your email settings.")
    return render_template("admin_forgot_password.html", sent=True, error=None)


@auth_bp.route("/admin_reset_password/<token>", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def admin_reset_password(token):
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    cursor.execute(
        "SELECT id FROM admin_users WHERE reset_token=%s AND reset_token_expiry > %s",
        (token_hash, datetime.datetime.utcnow())
    )
    row = cursor.fetchone()
    if not row:
        cursor.close()
        db.close()
        return render_template("admin_reset_password.html", valid=False, done=False, token=token)
    if request.method == "GET":
        cursor.close()
        db.close()
        return render_template("admin_reset_password.html", valid=True, done=False, token=token, error=None)
    new_pw = request.form.get("new_password", "").strip()
    confirm_pw = request.form.get("confirm_password", "").strip()
    if len(new_pw) < 8:
        cursor.close()
        db.close()
        return render_template("admin_reset_password.html", valid=True, done=False,
                               token=token, error="Password must be at least 8 characters.")
    if new_pw != confirm_pw:
        cursor.close()
        db.close()
        return render_template("admin_reset_password.html", valid=True, done=False,
                               token=token, error="Passwords do not match.")
    admin_id = row[0]
    cursor.execute(
        "UPDATE admin_users SET password=%s, reset_token=NULL, reset_token_expiry=NULL WHERE id=%s",
        (generate_password_hash(new_pw), admin_id)
    )
    db.commit()
    cursor.close()
    db.close()
    return render_template("admin_reset_password.html", valid=True, done=True, token=token, error=None)


@auth_bp.route("/employee_forgot_password", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def employee_forgot_password():
    if request.method == "GET":
        return render_template("employee_forgot_password.html", sent=False, error=None)
    emp_id = request.form.get("employee_id", "").strip()
    if not emp_id:
        return render_template("employee_forgot_password.html", sent=False, error="Please enter your Employee ID.")
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT employee_id, email, name FROM employees WHERE employee_id=%s", (emp_id,))
    row = cursor.fetchone()
    if not row or not row[1]:
        cursor.close()
        db.close()
        # Generic message to avoid account enumeration; also covers "no email on file"
        return render_template("employee_forgot_password.html", sent=True, error=None)
    db_email = row[1]
    emp_name = _html.escape(row[2] or emp_id)
    token = secrets.token_hex(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expiry = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    cursor.execute("UPDATE employees SET reset_token=%s, reset_token_expiry=%s WHERE employee_id=%s",
                   (token_hash, expiry, emp_id))
    db.commit()
    cursor.close()
    db.close()
    cfg = get_email_config()
    if not cfg:
        return render_template("employee_forgot_password.html", sent=False,
                               error="Email service not configured. Please contact HR.")
    reset_url = f"{_safe_app_url()}/employee_reset_password/{token}"
    html_body = f"""
<div style="font-family:Segoe UI,sans-serif;max-width:520px;margin:auto;background:#f8fafc;border-radius:16px;overflow:hidden;border:1px solid #dbeafe;">
  <div style="background:#1e3a8a;padding:24px 28px;color:white;">
    <div style="font-size:20px;font-weight:700;">🔐 Password Reset</div>
    <div style="font-size:13px;opacity:0.75;margin-top:4px;">Employee Portal</div>
  </div>
  <div style="padding:28px;">
    <p style="font-size:15px;color:#1e293b;margin-bottom:20px;">Hi <strong>{emp_name}</strong>, you requested a password reset for Employee ID <strong>{emp_id}</strong>.</p>
    <a href="{reset_url}" style="display:block;text-align:center;padding:14px 28px;background:#1e3a8a;color:white;border-radius:10px;text-decoration:none;font-size:15px;font-weight:700;margin-bottom:20px;">
      Reset My Password
    </a>
    <p style="font-size:13px;color:#64748b;">This link expires in <strong>1 hour</strong>. If you did not request this, please ignore this email.</p>
    <p style="font-size:12px;color:#94a3b8;margin-top:12px;">Or copy this link: {reset_url}</p>
  </div>
</div>"""
    send_email_async(db_email, "Password Reset -- Employee Portal", html_body, cfg)
    return render_template("employee_forgot_password.html", sent=True, error=None)


@auth_bp.route("/employee_reset_password/<token>", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def employee_reset_password(token):
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    cursor.execute("SELECT employee_id FROM employees WHERE reset_token=%s AND reset_token_expiry > %s",
                   (token_hash, datetime.datetime.utcnow()))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        db.close()
        return render_template("employee_reset_password.html", valid=False, done=False, token=token)
    if request.method == "GET":
        cursor.close()
        db.close()
        return render_template("employee_reset_password.html", valid=True, done=False, token=token, error=None)
    new_pw = request.form.get("new_password", "").strip()
    confirm_pw = request.form.get("confirm_password", "").strip()
    if len(new_pw) < 8:
        cursor.close()
        db.close()
        return render_template("employee_reset_password.html", valid=True, done=False,
                               token=token, error="Password must be at least 8 characters.")
    if new_pw != confirm_pw:
        cursor.close()
        db.close()
        return render_template("employee_reset_password.html", valid=True, done=False,
                               token=token, error="Passwords do not match.")
    emp_id = row[0]
    cursor.execute("UPDATE employees SET password=%s, reset_token=NULL, reset_token_expiry=NULL WHERE employee_id=%s",
                   (generate_password_hash(new_pw), emp_id))
    db.commit()
    cursor.close()
    db.close()
    _audit("employee_password_reset", "employees", emp_id, "Password reset via email link")
    return render_template("employee_reset_password.html", valid=True, done=True, token=token, error=None)


@auth_bp.route("/employee_logout", methods=["GET", "POST"])
def employee_logout():
    session.clear()
    return redirect(tpath("/login"))


@auth_bp.route("/change_password", methods=["POST"])
@employee_required
def change_password():
    emp_id = session["employee_id"]
    current = request.form.get("current_password", "").strip()
    new_pwd = request.form.get("new_password", "").strip()
    confirm = request.form.get("confirm_password", "").strip()
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT password FROM employees WHERE employee_id=%s", (emp_id,))
    row = cursor.fetchone()
    if not row or not check_password_hash(row[0], current):
        cursor.close()
        db.close()
        return redirect(tpath("/employee_portal?pwd_error=wrong#my-profile"))
    if len(new_pwd) < 8:
        cursor.close()
        db.close()
        return redirect(tpath("/employee_portal?pwd_error=short#my-profile"))
    if new_pwd != confirm:
        cursor.close()
        db.close()
        return redirect(tpath("/employee_portal?pwd_error=mismatch#my-profile"))
    cursor.execute(
        "UPDATE employees SET password=%s WHERE employee_id=%s",
        (generate_password_hash(new_pwd), emp_id)
    )
    db.commit()
    cursor.close()
    db.close()
    return redirect(tpath("/employee_portal?pwd_ok=1#my-profile"))


@auth_bp.route("/force_change_pin", methods=["GET", "POST"])
@employee_required
def force_change_pin():
    emp_id = session["employee_id"]
    error = None
    if request.method == "POST":
        new_pwd = request.form.get("new_password", "").strip()
        confirm = request.form.get("confirm_password", "").strip()
        if len(new_pwd) < 8:
            error = "Password must be at least 8 characters."
        elif new_pwd != confirm:
            error = "Passwords do not match."
        elif new_pwd in ("1234", "12345678", "password", "admin123"):
            error = "That password is too common. Please choose a stronger one."
        else:
            db = get_db_connection()
            cursor = db.cursor(buffered=True)
            cursor.execute(
                "UPDATE employees SET password=%s, force_pin_change=0 WHERE employee_id=%s",
                (generate_password_hash(new_pwd), emp_id)
            )
            db.commit()
            cursor.close()
            db.close()
            session.pop("_fpc", None)  # clear forced-change flag so portal is accessible
            return redirect(tpath("/employee_portal"))
    return render_template("force_change_pin.html", error=error,
                           emp_name=session.get("employee_name", ""))


@auth_bp.route("/webauthn/status", methods=["GET"])
def webauthn_status():
    """Diagnostic endpoint -- shows WebAuthn config without exposing sensitive data."""
    return jsonify({
        "webauthn_available": _webauthn_available,
        "rp_id": _wa_rp_id() if _webauthn_available else None,
        "expected_origins": _wa_origins() if _webauthn_available else [],
        "challenge_in_session": bool(session.get("wa_reg_challenge")),
        "request_host": request.host,
        "request_scheme": request.scheme,
    })


def _wa_authorize_enrollment(emp_id):
    """Return None if this session is allowed to enroll a passkey for emp_id,
    else an error string. Three legitimate paths, none of which trust a bare
    client-supplied emp_id on its own:
      - an authenticated admin, enrolling on an employee's behalf
      - an authenticated employee, enrolling their own credential
      - a kiosk visitor who just passed a real face match against emp_id's
        on-file photo (see api_kiosk_enroll_face_verify) within the last
        KIOSK_FACE_VERIFY_WINDOW_SEC seconds
    Without this, /webauthn/registration-options + webauthn-register(-kiosk)
    would let anyone enroll their own device's biometric against ANY
    employee_id and then check in as that employee indefinitely."""
    if session.get("admin_logged_in") and session.get("admin_role") == "admin":
        return None
    session_emp = session.get("employee_id")
    if session_emp:
        return None if session_emp.strip().upper() == emp_id else "Not authorized to enroll a passkey for this employee."
    face_emp = session.get("wa_face_verified_emp_id")
    face_at = session.get("wa_face_verified_at", 0)
    if face_emp and face_emp.upper() == emp_id and (time.time() - face_at) < KIOSK_FACE_VERIFY_WINDOW_SEC:
        return None
    return "Identity not verified. Please verify your face or log in first."


@auth_bp.route("/api/employee/kiosk-enroll-face-verify", methods=["POST"])
@limiter.limit("10 per minute")
def api_kiosk_enroll_face_verify():
    """Public kiosk endpoint: proves the person at the kiosk is the employee
    they claim before /webauthn/registration-options will hand out enrollment
    options for that employee_id. This is the real identity check that was
    previously missing entirely -- a QR scan or typed employee_id alone proves
    nothing about who is physically present."""
    employee_id = (request.form.get("employee_id") or "").strip().upper()
    face_photo = request.files.get("face_photo")
    if not employee_id:
        return jsonify({"ok": False, "msg": "employee_id required"}), 400
    if not face_photo:
        return jsonify({"ok": False, "msg": "Face photo required."}), 400

    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT face_image FROM employees WHERE employee_id=%s", (employee_id,))
    row = cursor.fetchone()
    cursor.close()
    db.close()
    if not row:
        return jsonify({"ok": False, "msg": "Employee not found"}), 404

    face_dir = os.path.join(UPLOAD_FOLDER, "face_logs")
    ok, msg = verify_uploaded_face(employee_id, row[0], face_photo, face_dir)
    if not ok:
        return jsonify({"ok": False, "msg": msg}), 401

    session["wa_face_verified_emp_id"] = employee_id
    session["wa_face_verified_at"] = time.time()
    return jsonify({"ok": True})


@auth_bp.route("/webauthn/registration-options", methods=["GET"])
def webauthn_registration_options():
    """Server-generated WebAuthn registration options with challenge stored in session."""
    if not _webauthn_available:
        return jsonify({"ok": False, "msg": "Fingerprint enrollment is not available on this server."}), 503
    try:
        emp_id = (request.args.get("emp_id") or session.get("employee_id") or "employee").strip().upper()
        emp_name = (request.args.get("name") or emp_id).strip()

        auth_err = _wa_authorize_enrollment(emp_id)
        if auth_err:
            return jsonify({"ok": False, "msg": auth_err}), 403
        # Single-use: a face match only ever authorizes the enrollment it was
        # taken for, never a second later request in the same session.
        session.pop("wa_face_verified_emp_id", None)
        session.pop("wa_face_verified_at", None)

        rp_id = _wa_rp_id()
        rp_err = _wa_check_rp_id(rp_id)
        if rp_err:
            return jsonify({"ok": False, "error": rp_err}), 422
        _reg_algs = [COSEAlgorithmIdentifier.ECDSA_SHA_256, COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256]
        options = webauthn.generate_registration_options(
            rp_id=rp_id,
            rp_name="Employee Attendance",
            user_id=emp_id.encode(),
            user_name=emp_id,
            user_display_name=emp_name,
            authenticator_selection=AuthenticatorSelectionCriteria(
                authenticator_attachment=AuthenticatorAttachment.PLATFORM,
                user_verification=UserVerificationRequirement.REQUIRED,
                resident_key=ResidentKeyRequirement.PREFERRED,
            ),
            supported_pub_key_algs=_reg_algs,
            attestation=AttestationConveyancePreference.NONE,
        )
        session["wa_reg_challenge"] = _wa_b64url_encode(options.challenge)
        session["wa_reg_emp_id"] = emp_id
        session["wa_reg_alg_ids"] = [a.value for a in _reg_algs]
        return webauthn.options_to_json(options), 200, {"Content-Type": "application/json"}
    except Exception as exc:
        app_log.error("WebAuthn registration-options failed: %s", exc, exc_info=True)
        return jsonify({"ok": False, "error": str(exc)}), 500


@auth_bp.route("/webauthn/authentication-options", methods=["GET"])
def webauthn_authentication_options():
    """Server-generated WebAuthn authentication options with challenge stored in session."""
    if not _webauthn_available:
        return jsonify({"ok": False, "msg": "Fingerprint verification is not available on this server."}), 503
    try:
        emp_id = (request.args.get("emp_id") or "").strip().upper()
        rp_id = _wa_rp_id()
        rp_err = _wa_check_rp_id(rp_id)
        if rp_err:
            return jsonify({"ok": False, "error": rp_err}), 422

        allow_creds = []
        if emp_id:
            try:
                db = get_db_connection()
                cur = db.cursor(buffered=True)
                cur.execute("SELECT fingerprint_credential_id FROM employees WHERE employee_id=%s", (emp_id,))
                row = cur.fetchone()
                cur.close()
                db.close()
                if row and row[0]:
                    allow_creds = [PublicKeyCredentialDescriptor(
                        id=_wa_b64url_decode(row[0]), transports=[AuthenticatorTransport.INTERNAL]
                    )]
            except Exception as db_exc:
                app_log.warning("WebAuthn auth-options: DB lookup failed for emp=%s: %s", emp_id, db_exc)

        options = webauthn.generate_authentication_options(
            rp_id=rp_id, allow_credentials=allow_creds, user_verification=UserVerificationRequirement.REQUIRED,
        )
        session["wa_auth_challenge"] = _wa_b64url_encode(options.challenge)
        session["wa_auth_emp_id"] = emp_id
        return webauthn.options_to_json(options), 200, {"Content-Type": "application/json"}
    except Exception as exc:
        app_log.error("WebAuthn authentication-options failed: %s", exc, exc_info=True)
        return jsonify({"ok": False, "error": str(exc)}), 500


@auth_bp.route("/api/employee/webauthn-verify-challenge", methods=["POST"])
def webauthn_verify_challenge():
    """
    Real server-side WebAuthn assertion verification: checks the ECDSA/RSA
    signature in the assertion against the employee's stored public key (not
    just the clientDataJSON fields, which are trivially forgeable on their
    own). On success, sets a short-lived, one-time, employee-bound session
    flag that /attendance and /api/employee/qr-face-checkin consume to allow
    the actual check-in -- this stops a verified fingerprint for employee A
    from being reused to check in as employee B.
    """
    if not _webauthn_available:
        return jsonify({"ok": False, "msg": "Fingerprint verification is not available on this server."}), 503
    data = request.get_json(force=True, silent=True) or {}
    emp_id = (data.get("emp_id") or session.get("wa_auth_emp_id") or "").strip().upper()
    credential = data.get("credential")
    challenge_b64 = session.get("wa_auth_challenge")

    if not credential or not challenge_b64:
        return jsonify({"ok": False, "msg": "Missing credential or challenge"}), 400

    try:
        db = get_db_connection()
        cur = db.cursor(buffered=True)

        if emp_id:
            # QR + Fingerprint mode: employee already identified by QR scan
            cur.execute(
                "SELECT employee_id, name, fingerprint_public_key, fingerprint_sign_count FROM employees WHERE employee_id=%s",
                (emp_id,)
            )
        else:
            # Passkey mode: employee is identified by the credential ID inside the assertion.
            # credential["id"] is the base64url credential ID the browser signed with.
            cred_id = (credential.get("id") or "") if isinstance(credential, dict) else ""
            if not cred_id:
                cur.close()
                db.close()
                return jsonify({"ok": False, "msg": "Missing credential ID"}), 400
            cur.execute(
                "SELECT employee_id, name, fingerprint_public_key, fingerprint_sign_count FROM employees WHERE fingerprint_credential_id=%s",
                (cred_id,)
            )

        row = cur.fetchone()
        if not row or not row[2]:
            cur.close()
            db.close()
            return jsonify({"ok": False, "msg": "No passkey enrolled. Please enrol from the employee portal."}), 401

        emp_id = row[0]
        emp_name = row[1] or emp_id
        stored_pubkey = base64.b64decode(row[2])
        stored_sign_count = int(row[3] or 0)

        verified = webauthn.verify_authentication_response(
            credential=credential,
            expected_challenge=_wa_b64url_decode(challenge_b64),
            expected_rp_id=_wa_rp_id(),
            expected_origin=_wa_origins(),
            credential_public_key=stored_pubkey,
            # Per W3C WebAuthn §7.2 step 21: pass the stored count so py_webauthn
            # can reject a cloned credential (new ≤ stored when stored > 0).
            # Authenticators that never increment (Windows Hello, Touch ID) always
            # return 0, so stored stays 0 and the check is skipped automatically.
            credential_current_sign_count=stored_sign_count,
        )
    except Exception as e:
        try:
            cur.close()
            db.close()
        except Exception:
            pass
        app_log.warning("WebAuthn authentication verification failed for emp_id=%s: %s",
                        emp_id or "(passkey mode)", e, exc_info=True)
        return jsonify({"ok": False, "msg": f"Verification failed: {e}"}), 401

    session.pop("wa_auth_challenge", None)
    session.pop("wa_auth_emp_id", None)

    # Persisting the new sign count is best-effort bookkeeping (anti-clone
    # detection) -- a failure here doesn't invalidate a verification that
    # already succeeded above, so it's swallowed rather than failing the
    # whole request. Reuses the connection from the SELECT above instead of
    # opening a second one.
    try:
        cur.execute(
            "UPDATE employees SET fingerprint_sign_count=%s WHERE employee_id=%s",
            (verified.new_sign_count, emp_id)
        )
        db.commit()
    except Exception:
        pass
    finally:
        cur.close()
        db.close()

    session["wa_fp_verified_emp_id"] = emp_id
    session["wa_fp_verified_at"] = time.time()
    return jsonify({"ok": True, "emp_id": emp_id, "name": emp_name})


@auth_bp.route("/api/employee/webauthn-register", methods=["POST"])
@limiter.limit("10 per minute")
def webauthn_register():
    """Save a WebAuthn credential after successful enrollment. Requires active employee session."""
    # Use session employee_id; fall back to wa_reg_emp_id stored when options were generated.
    # Both values live in the same signed session cookie, so this is equivalent security.
    emp_id = session.get("employee_id") or session.get("wa_reg_emp_id")
    if not emp_id:
        return jsonify({"ok": False, "msg": "Session expired -- please log in again"}), 401
    data = request.get_json(force=True, silent=True) or {}
    credential = data.get("credential")
    challenge_b64 = session.get("wa_reg_challenge")
    if not challenge_b64:
        return jsonify({"ok": False, "msg": "Enrollment session expired -- please start again"}), 401
    try:
        db = get_db_connection()
        cursor = db.cursor(buffered=True)
        ok, err = _wa_verify_and_store_registration(emp_id, credential, challenge_b64, cursor, db)
        cursor.close()
        db.close()
    except Exception:
        app_log.error("WebAuthn registration endpoint failed", exc_info=True)
        return jsonify({"ok": False, "msg": "WebAuthn registration failed. Please try again."}), 500
    session.pop("wa_reg_challenge", None)
    session.pop("wa_reg_emp_id", None)
    session.pop("wa_reg_alg_ids", None)
    if not ok:
        return jsonify({"ok": False, "msg": err}), 401
    return jsonify({"ok": True})


@auth_bp.route("/api/employee/webauthn-unenroll", methods=["POST"])
@limiter.limit("10 per minute")
def webauthn_unenroll():
    """Remove the stored WebAuthn credential for the logged-in employee."""
    emp_id = session.get("employee_id")
    if not emp_id:
        return jsonify({"ok": False, "msg": "Not logged in"}), 401
    try:
        db = get_db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute(
            "UPDATE employees SET fingerprint_credential_id=NULL, fingerprint_public_key=NULL, "
            "fingerprint_sign_count=0 WHERE employee_id=%s",
            (emp_id,)
        )
        db.commit()
        cursor.close()
        db.close()
        return jsonify({"ok": True})
    except Exception:
        app_log.error("WebAuthn unenroll failed", exc_info=True)
        return jsonify({"ok": False, "msg": "Failed to remove credential. Please try again."}), 500


@auth_bp.route("/api/employee/<emp_id>/webauthn-credential", methods=["GET"])
@limiter.limit("30 per minute")
def get_employee_webauthn_credential(emp_id):
    """Return the stored WebAuthn credential_id -- requires an active admin or employee session."""
    is_admin = session.get("admin_logged_in")
    session_emp = session.get("employee_id")
    if not (is_admin or session_emp):
        # Also accept a valid Bearer token (kiosk uses admin token)
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token_hash = _hash_token(auth[7:])
            with _db() as (cursor, _):
                cursor.execute(
                    "SELECT 1 FROM api_tokens WHERE token=%s AND expires_at > NOW()", (token_hash,)
                )
                if not cursor.fetchone():
                    return jsonify({"ok": False, "msg": "Unauthorized"}), 401
        else:
            return jsonify({"ok": False, "msg": "Unauthorized"}), 401
    emp_id = emp_id.strip().upper()
    # Employees may only retrieve their own credential; admins and Bearer tokens can retrieve any
    if session_emp and not is_admin and session_emp.upper() != emp_id:
        return jsonify({"ok": False, "msg": "Unauthorized"}), 403
    try:
        db = get_db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute(
            "SELECT fingerprint_credential_id FROM employees WHERE employee_id=%s LIMIT 1",
            (emp_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        db.close()
        return jsonify({"ok": True, "credential_id": row[0] if row else None})
    except Exception:
        return jsonify({"ok": True, "credential_id": None})


@auth_bp.route("/api/employee/webauthn-register-kiosk", methods=["POST"])
@limiter.limit("5 per minute")
def webauthn_register_kiosk():
    """Enrol a passkey from the attendance kiosk. No employee session required."""
    if not _webauthn_available:
        return jsonify({"ok": False, "msg": "Fingerprint enrollment is not available on this server."}), 503
    data = request.get_json(force=True, silent=True) or {}
    emp_id = (data.get("emp_id") or "").strip().upper()
    credential = data.get("credential")
    challenge_b64 = session.get("wa_reg_challenge")
    if not emp_id:
        return jsonify({"ok": False, "msg": "Employee ID required"}), 400
    if not challenge_b64:
        app_log.warning("WebAuthn kiosk enrolment: no challenge in session for emp=%s", emp_id)
        return jsonify({"ok": False, "msg": "Session expired -- please refresh the page and try again"}), 400
    if session.get("wa_reg_emp_id", "").upper() != emp_id:
        app_log.warning("WebAuthn kiosk: emp_id mismatch -- session=%s post=%s",
                        session.get("wa_reg_emp_id"), emp_id)
        return jsonify({"ok": False, "msg": "Employee ID mismatch. Please restart enrollment."}), 403
    try:
        db = get_db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute("SELECT employee_id FROM employees WHERE employee_id=%s", (emp_id,))
        if not cursor.fetchone():
            cursor.close()
            db.close()
            return jsonify({"ok": False, "msg": "Employee ID not found"}), 404
        ok, err = _wa_verify_and_store_registration(emp_id, credential, challenge_b64, cursor, db)
        cursor.close()
        db.close()
    except Exception as exc:
        app_log.error("WebAuthn kiosk registration unexpected error: %s", exc, exc_info=True)
        return jsonify({"ok": False, "msg": f"Registration error: {exc}"}), 500
    session.pop("wa_reg_challenge", None)
    session.pop("wa_reg_alg_ids", None)
    if not ok:
        return jsonify({"ok": False, "msg": err}), 400
    app_log.info("WebAuthn kiosk enrolment: emp_id=%s", emp_id)
    return jsonify({"ok": True})


@auth_bp.route("/api/admin/employee/<emp_id>/reset-fingerprint", methods=["POST"])
@role_required("admin")
def admin_reset_employee_fingerprint(emp_id):
    """Admin: clear a specific employee's WebAuthn credential so they can re-enroll on a new device."""
    emp_id = emp_id.strip().upper()
    try:
        db = get_db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute(
            "UPDATE employees SET fingerprint_credential_id=NULL, fingerprint_public_key=NULL, "
            "fingerprint_sign_count=0 WHERE employee_id=%s",
            (emp_id,)
        )
        db.commit()
        affected = cursor.rowcount
        cursor.close()
        db.close()
        if affected == 0:
            return jsonify({"ok": False, "msg": "Employee not found"}), 404
        _audit("admin_reset_fingerprint", "employees", emp_id)
        return jsonify({"ok": True})
    except Exception:
        app_log.error("Failed to reset employee fingerprint", exc_info=True)
        return jsonify({"ok": False, "msg": "Failed to reset fingerprint. Please try again."}), 500


@auth_bp.route("/api/employee/mobile-biometric-nonce", methods=["POST"])
@limiter.limit("10 per minute")
@employee_api_required
def api_mobile_biometric_nonce():
    """Mobile app calls this (with its employee Bearer token) right before
    prompting the device's local biometric/PIN check. The returned nonce
    must be echoed back to /mobile-biometric-attest within 60s."""
    nonce = _mobile_biometric_issue_nonce(g.api_emp_id)
    return jsonify({"ok": True, "nonce": nonce})


@auth_bp.route("/api/employee/mobile-biometric-attest", methods=["POST"])
@limiter.limit("10 per minute")
@employee_api_required
def api_mobile_biometric_attest():
    """Mobile app calls this immediately after a successful local
    LocalAuthentication.authenticateAsync(), turning that local-only signal
    into a server-side, employee-bound, single-use, time-boxed proof that
    /api/employee/qr-face-checkin will accept for fingerprint combos."""
    data = request.get_json(force=True, silent=True) or {}
    nonce = (data.get("nonce") or "").strip()
    ok, err = _mobile_biometric_attest(g.api_emp_id, nonce)
    if not ok:
        return jsonify({"ok": False, "msg": err}), 401
    return jsonify({"ok": True})


@auth_bp.route("/admin/step-up-mfa", methods=["GET", "POST"])
def step_up_mfa():
    """Step-Up MFA challenge: a fresh TOTP re-check before a high-privilege
    action, on top of (not instead of) the admin session already
    established at login."""
    username = session.get("admin_username")
    if not username:
        return redirect(tpath("/login"))

    if request.method == "POST":
        totp_code = request.form.get("totp_code", "").strip()
        valid = verify_totp_code(username, totp_code, require_enabled=False)

        if valid:
            session["_step_up_mfa_verified_at"] = time.time()
            target_url = session.pop("_step_up_target_url", "/admin")
            log_security_event(
                "mfa.step_up_success",
                "Step-Up MFA verified successfully",
                level="INFO",
                identifier=username
            )
            return redirect(target_url)

        return render_template("step_up_mfa.html", error="Invalid MFA verification code.")

    return render_template("step_up_mfa.html")
