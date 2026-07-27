"""Step-Up MFA & Session IP Binding Middleware.

Enforces:
1. Step-Up MFA re-verification before executing high-privilege structural config
   or role modification operations.
2. IP binding and session pinning to prevent session hijacking.
"""
import time
from functools import wraps
from flask import session, redirect, request, jsonify
from utils.auth import _db
from utils.totp import verify_totp_code
from extensions import app_log, log_security_event

_STEP_UP_VALIDITY_SECONDS = 900  # 15 minutes validity for step-up verification


def require_step_up_mfa(f):
    """Decorator requiring fresh TOTP step-up verification for sensitive admin actions."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect("/admin_login")

        # Check IP Binding (Session Pinning)
        current_ip = request.remote_addr
        bound_ip = session.get("_bound_ip")
        if bound_ip and bound_ip != current_ip:
            log_security_event(
                "session.ip_mismatch",
                f"Session IP mismatch detected! Bound: {bound_ip}, Request IP: {current_ip}",
                level="ERROR",
                identifier=session.get("admin_username"),
                bound_ip=bound_ip,
                current_ip=current_ip
            )
            session.clear()
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"ok": False, "msg": "Session IP binding mismatch. Re-authentication required."}), 401
            return redirect("/admin_login?error=session_ip_mismatch")

        # Set bound IP on first request
        if not bound_ip:
            session["_bound_ip"] = current_ip

        # Check Step-Up MFA Verification Status
        step_up_time = session.get("_step_up_mfa_verified_at", 0)
        now = time.time()
        if (now - step_up_time) > _STEP_UP_VALIDITY_SECONDS:
            session["_step_up_target_url"] = request.url
            log_security_event(
                "mfa.step_up_required",
                "High-privilege operation requested — Step-Up MFA re-challenge required",
                level="INFO",
                identifier=session.get("admin_username"),
                path=request.path
            )
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({
                    "ok": False,
                    "code": "STEP_UP_MFA_REQUIRED",
                    "msg": "Step-Up MFA re-verification required for high-privilege action.",
                    "redirect": "/admin/step-up-mfa"
                }), 403
            return redirect("/admin/step-up-mfa")

        return f(*args, **kwargs)
    return decorated_function
