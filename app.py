import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# When this file is run directly (`python app.py`, the local-dev entrypoint),
# Python loads it as module "__main__" -- a *different* module identity than
# "app". Every lazy `from app import init_tenant_db` (etc.) done deep inside
# a request handler (blueprints/org.py's provision_tenant() among others)
# then finds no "app" module cached, so Python re-imports this entire file
# from scratch as a second "app" module. extensions.app is the same Flask
# object either way (extensions.py is cached under its own name), so that
# second execution re-runs every @app.route/@app.context_processor/
# @app.errorhandler in this file against the one, already-serving Flask
# instance -- which Flask rejects once it's handled a single request
# ("The setup method ... can no longer be called"). Registering this
# execution under the name "app" up front makes any later `from app import
# X` resolve to this exact already-fully-loaded module instead of
# re-executing it. wsgi.py already imports this file as "app" normally, so
# it never hits this branch -- only a bare `python app.py` needs the alias.
if __name__ == "__main__":
    sys.modules.setdefault("app", sys.modules[__name__])

import os
import re
import psycopg2
import secrets
import threading
import hashlib
import time
import base64
from werkzeug.exceptions import HTTPException
from dotenv import load_dotenv

load_dotenv()
_HASHI_ENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hashi", ".env")
load_dotenv(_HASHI_ENV)

from flask import request, session, jsonify, redirect, url_for, flash, current_app, render_template
import datetime
import html as _html
from database import get_db_connection

# ── Startup: warn if critical env vars are missing ──
_missing_env = [k for k in ("DB_HOST", "DB_USER", "DB_PASS", "DB_NAME") if not os.environ.get(k)]
if _missing_env:
    import warnings
    warnings.warn(
        f"Missing required environment variables: {', '.join(_missing_env)}. "
        "Copy .env.example to .env and fill in the values.",
        stacklevel=2
    )

from extensions import app, app_log, limiter, log_security_event  # noqa: F401 — app/limiter re-exported: tests/conftest.py does app.limiter.enabled = False
# Single source of truth for email — app.py used to carry its own complete
# duplicate of every one of these, including _email_queue_worker. wsgi.py
# (the production entrypoint) already starts utils.email_utils's worker
# thread, then imports app.py as a side effect, which used to
# unconditionally start ITS OWN second worker thread on top — two threads
# racing on the same email_queue table with no row locking, a live
# duplicate-delivery risk in production (every payslip, every security
# alert, sent up to twice). The worker is started exactly once now, see
# the __name__ == "__main__" guard near the bottom of this file — it only
# fires for a bare `python app.py`, never when wsgi.py imports this module.
from utils.email_utils import (
    get_email_config, get_admin_emails, send_email_async,
    _email_queue_worker,
)
# Single source of truth for auth — app.py used to carry its own duplicate
# copies of every one of these (password hashing, lockout, session/API
# guards), which had drifted from utils/auth.py's versions and meant three
# rounds of security work (structured event logging, BOLA risk-scoring,
# the session kill switch) were silently not reaching any route in this
# file. Consolidated onto one implementation; see utils/auth.py.
from utils.auth import generate_password_hash, check_password_hash
from utils.helpers import (
    _error_page, invalidate_settings_cache, get_company_settings,
    get_companies_list, get_overdue_onboarding_count,
)
# Shift timings / deduction rates / office geo-fence — app.py used to carry
# its own separate SHIFT_START / LATE_DEDUCTION_RATE / OFFICE_LAT etc.
# globals, mutated by its own separate load_default_shift()/
# load_salary_rules(). utils/config.py's docstring already stated the
# intent ("blueprints should always access them through this module") —
# app.py just never migrated. Now the single source both use, referenced
# throughout this file as cfg.SHIFT_START etc.
import utils.config as cfg
import utils.waf as waf

# ── Trusted base URL for email links (avoids Host-header injection) ───────────
# Set APP_URL=https://yourdomain.com in .env for production.
# Falls back to request.host_url only when the env var is absent (local dev).
# _APP_URL / _safe_app_url / _safe_redirect / _safe_referrer_redirect moved
# to utils/helpers.py — used across multiple routes still in app.py, not
# just the auth/admin_views blueprints.
# _INJECTION_PATTERN_RE moved to blueprints/auth.py — its only caller
# (admin_login) migrated there.


@app.context_processor
def inject_common_vars():
    return dict(
        shift_start=cfg.SHIFT_START.strftime("%I:%M %p"),
        shift_end=cfg.SHIFT_END.strftime("%I:%M %p"),
    )


@app.template_filter('qr_url')
def _qr_url_filter(p):
    """Normalize QR code paths — old code stored absolute OS paths; extract just static/qrcodes/<file>."""
    import re
    if not p:
        return ''
    m = re.search(r'static[/\\]qrcodes[/\\]([^/\\]+\.png)', str(p))
    return f'static/qrcodes/{m.group(1)}' if m else str(p)

# /favicon.ico and /healthz are served by blueprints/health.py


# Jinja2 filter: handles both datetime.time and datetime.timedelta.
# psycopg2 returns TIME columns as datetime.time (hits the strftime branch
# below); the timedelta branch is a defensive fallback kept from when this
# ran against mysql-connector, which returned TIME columns as timedelta.
@app.template_filter("fmt_time")
def fmt_time_filter(value):
    if value is None:
        return "--"
    if isinstance(value, str):
        return value
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M:%S")
    # timedelta fallback — see comment above
    total = int(value.total_seconds())
    return "{:02d}:{:02d}:{:02d}".format(total // 3600, (total % 3600) // 60, total % 60)

# Templates that need arithmetic on a TIME value (elapsed-time math, HH/MM/SS
# breakdowns) used to rely on mysql-connector's timedelta.seconds. psycopg2
# returns datetime.time instead, which has no .seconds — this filter gives
# templates a type-agnostic "total seconds" so that math still works.


@app.template_filter("time_seconds")
def time_seconds_filter(value):
    if value is None:
        return 0
    if hasattr(value, "hour"):
        return value.hour * 3600 + value.minute * 60 + value.second
    return int(value.total_seconds())


@app.template_filter("plan_price")
def plan_price_filter(paise):
    """paise -> "₹1,999" for billing displays (super_admin_dashboard.html,
    create_org.html) -- thin wrapper so templates don't import utils.plan_limits."""
    from utils.plan_limits import format_price_inr
    return format_price_inr(paise)

# ---------------- CONFIG ----------------
# secret_key, session cookie flags, and PERMANENT_SESSION_LIFETIME are
# authoritative in extensions.py. Do not duplicate them here.


UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ---------------- CSRF PROTECTION ----------------
_EMP_ID_RE = re.compile(r'^[A-Za-z0-9_\-]+$')


def _csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(32)
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = _csrf_token
app.jinja_env.globals["timedelta"] = datetime.timedelta


@app.context_processor
def inject_companies_context():
    """Inject active company and companies list into every admin template.
    Reads through get_companies_list()'s 30s cache rather than querying the
    companies table on every single admin page render."""
    if not session.get("admin_logged_in"):
        return {}
    try:
        rows = get_companies_list()
        active_cid = session.get("active_company_id")
        active_company = None
        for r in rows:
            if r[0] == active_cid:
                active_company = {"id": r[0], "name": r[1], "code": r[2]}
                break
        return {
            "all_companies": [{"id": r[0], "name": r[1], "code": r[2], "has_pin": bool(r[3])} for r in rows],
            "active_company": active_company,
        }
    except Exception:
        return {"all_companies": [], "active_company": None}


@app.context_processor
def inject_overdue_onboardings():
    """Reads through get_overdue_onboarding_count()'s 20s cache rather than
    running a COUNT query on every single admin page render."""
    if not session.get("admin_logged_in"):
        return {}
    try:
        return {"overdue_onboardings": get_overdue_onboarding_count()}
    except Exception:
        return {"overdue_onboardings": 0}


_SESSION_MAX_AGE = 8 * 3600  # 8 hours absolute — stolen cookie cannot be used indefinitely
# How often _resolve_tenant() re-checks tenants.status for an
# already-session-cached tenant. Bounds how long a platform-admin
# suspension (blueprints/platform_admin.py) takes to actually lock out an
# already-logged-in session, rather than never (cookie sessions have no
# server-side store to revoke from outside).
_TENANT_STATUS_RECHECK_SEC = 5 * 60


@app.before_request
def _perf_start_timer():
    """Stash a start time for _perf_record below (registered first so it
    wraps every other before_request hook's cost too)."""
    from flask import g
    g._perf_start = time.perf_counter()


@app.before_request
def _resolve_tenant():
    """Determine the tenant database for this request and store it in
    g.tenant_db. Registered second — right after the perf timer, before
    every other hook — because get_db_connection() (database.py) reads
    g.tenant_db and silently falls back to the "public" schema if it isn't
    set yet. _enforce_ip_ban and _enforce_admin_mfa_enrollment both call
    get_db_connection() directly; running this hook after either of them
    would make both checks query the wrong tenant's data on every single
    request in a multi-tenant deployment — a full bypass of both controls,
    not a rare edge case."""
    from flask import g as _g

    # Skip for static files and special paths
    skip_prefixes = ("/static/", "/healthz", "/create_org", "/super_admin")
    if any(request.path.startswith(p) for p in skip_prefixes):
        return

    # 1. Already resolved in this session -- but re-validate status every
    # _TENANT_STATUS_RECHECK_SEC instead of trusting the cache forever.
    # Without this, a platform admin suspending a tenant (blueprints/
    # platform_admin.py) would have no effect on any session that had
    # already resolved that tenant: this cache is the only thing standing
    # between "suspended" and "still fully working," since cookie-based
    # sessions have no server-side store to revoke from outside.
    if session.get("tenant_db"):
        last_checked = session.get("_tenant_status_checked_at", 0)
        if (time.time() - last_checked) < _TENANT_STATUS_RECHECK_SEC:
            _g.tenant_db = session["tenant_db"]
            return
        try:
            from database import get_master_db
            conn = get_master_db()
            cur = conn.cursor(buffered=True)
            cur.execute("SELECT status FROM tenants WHERE db_name=%s", (session["tenant_db"],))
            row = cur.fetchone()
            cur.close()
            conn.close()
        except Exception:
            row = None  # master DB unreachable -- don't punish the session for it, just skip the recheck this time
        if row is None or row[0] == "active":
            session["_tenant_status_checked_at"] = time.time()
            _g.tenant_db = session["tenant_db"]
            return
        session.clear()
        return jsonify({"ok": False, "msg": "This organisation's access has been suspended. Contact support."}), 403

    # 2. Subdomain resolution
    host = request.host.split(":")[0]  # strip port
    parts = host.split(".")
    if len(parts) >= 3:
        subdomain = parts[0]
        try:
            from database import get_master_db
            conn = get_master_db()
            cur = conn.cursor(buffered=True)
            cur.execute(
                "SELECT db_name FROM tenants WHERE subdomain=%s AND status='active'",
                (subdomain,)
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row:
                _g.tenant_db = row[0]
                session["tenant_db"] = row[0]
                return
        except Exception:
            pass  # master DB not yet set up — fall through to default

    # 3. Default single-tenant fallback
    _g.tenant_db = os.environ.get("DB_NAME", "employee_attendance")


@app.before_request
def _enforce_ip_ban():
    """Application-layer IP ban, enforced before every other before_request
    hook (registered second, right after the perf timer) so a banned source
    never reaches session/auth logic, let alone a route handler. Backs the
    SOC dashboard's one-click ban action (blueprints/admin_views.py). Static
    assets stay reachable — banning is about stopping active app usage
    (login attempts, API calls), not making the banned party's browser look
    broken in a way that itself signals "you got blocked, try harder.\""""
    if request.path.startswith("/static/") or request.path == "/healthz":
        return
    ip = request.remote_addr
    if not ip:
        return
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute(
        "SELECT reason FROM banned_ips WHERE ip=%s AND (expires_at IS NULL OR expires_at > NOW())",
        (ip,),
    )
    row = cursor.fetchone()
    cursor.close()
    db.close()
    if row:
        return jsonify({"ok": False, "msg": "Access denied."}), 403


# Credential-check endpoints are deliberately exempt from the blanket WAF
# block below. blueprints/auth.py's admin_login already detects
# injection-shaped identifiers itself (_INJECTION_PATTERN_RE) and responds
# with the same generic "Invalid credentials" any wrong password gets — a
# real, tested design choice (tests/test_auth_routes.py,
# tests/test_comprehensive.py's TestInputValidation) so a probing attacker
# can't use a distinguishing WAF-block response to tell "malicious-shaped
# input" apart from "wrong password" on the one surface where that
# distinction would be most valuable to them. A hard 403 here would both
# leak that signal and short-circuit the existing detection before it runs.
# Not a real exposure either way — every one of these routes only ever
# uses the identifier in a parameterized query, never executes or reflects
# it — so exempting them costs no actual protection.
_WAF_EXEMPT_PATHS = {"/login", "/admin_login", "/employee_login", "/api/login", "/api/employee/login"}


@app.before_request
def _waf_inspect_request():
    """Native signature-based WAF: rejects requests whose query string,
    form fields, JSON body, uploaded filenames, or path segments match a
    known SQLi/XSS/path-traversal shape. Runs immediately after the IP ban
    check (before session/CSRF/route logic) so a malicious payload is
    rejected before it can reach anything else. See utils/waf.py."""
    if request.path.startswith("/static/") or request.path == "/healthz":
        return
    if request.path in _WAF_EXEMPT_PATHS:
        return
    hit = waf.inspect_request(request)
    if hit:
        event_type, field, matched = hit
        ip = request.remote_addr
        log_security_event(
            event_type, f"WAF blocked request: signature matched in {field}",
            level="ERROR", field=field, matched=matched[:100],
        )
        waf.record_breach_and_maybe_ban(ip, f"Repeated WAF blocks ({event_type})")
        return jsonify({"ok": False, "msg": "Request blocked by security policy."}), 403


@app.before_request
def _enforce_session_lifetime():
    """Expire sessions that are older than the absolute max age, regardless of activity."""
    if request.path.startswith("/static/") or request.path == "/healthz":
        return
    created = session.get("_session_created")
    if created and (time.time() - created) > _SESSION_MAX_AGE:
        session.clear()
        if request.path.startswith("/api/"):
            from flask import jsonify as _jfy
            return _jfy({"ok": False, "msg": "Session expired. Please log in again."}), 401
        flash("Your session expired. Please log in again.", "warning")
        return redirect(url_for("auth.admin_login"))


@app.before_request
def _enforce_idle_timeout():
    """Expire sessions after N minutes of *inactivity* — distinct from the
    absolute max-age check above, which only catches a session once it's
    lived 8 hours regardless of how recently it was used. The threshold
    itself (company_settings.session_timeout, admin-configurable 5-1440 min
    via the SOC dashboard's /api/secops/session-timeout)
    used to be stored and displayed in the UI but was never actually
    enforced anywhere — this closes that gap. Reads through
    get_company_settings()'s existing 60s cache rather than querying the DB
    on every request.
    """
    if request.path.startswith("/static/") or request.path == "/healthz":
        return
    if not (session.get("admin_logged_in") or session.get("employee_id")):
        return
    now = time.time()
    last_activity = session.get("_last_activity")
    if last_activity:
        timeout_minutes = get_company_settings().get("session_timeout", 30)
        if (now - last_activity) > timeout_minutes * 60:
            session.clear()
            if request.path.startswith("/api/"):
                from flask import jsonify as _jfy
                return _jfy({"ok": False, "msg": "Session expired due to inactivity. Please log in again."}), 401
            flash("Your session expired due to inactivity. Please log in again.", "warning")
            return redirect(url_for("auth.admin_login"))
    session["_last_activity"] = now


# Roles that count as "administrative/HR" for the mandatory-MFA requirement
# below — every role that can reach admin-side data or actions.
_MANDATORY_MFA_ROLES = {"admin", "manager", "soc_analyst", "hr"}

# Routes reachable by an admin/manager/soc_analyst/hr session that has NOT
# yet enrolled TOTP — must stay small and deliberate. Anything not on this
# list is unreachable until enrollment is complete, which is the point (a
# genuine "mandatory," not a step-up an admin can defer indefinitely).
_MANDATORY_MFA_EXEMPT_PATHS = {
    "/admin/mfa-required", "/api/settings/2fa/setup", "/api/settings/2fa/enable",
    "/logout", "/admin_login", "/hr_login"
}

app.config.setdefault("MANDATORY_ADMIN_MFA", False)
app.config["MANDATORY_LOGIN_MFA"] = os.environ.get("MANDATORY_LOGIN_MFA", "False").lower() in ("true", "1", "yes")


@app.before_request
def _enforce_admin_mfa_enrollment():
    """Hard requirement: an admin/manager/soc_analyst session with TOTP not
    yet enrolled can reach nothing except the enrollment flow itself (and
    login/logout) — no grace period, no dismissible nag. This is distinct
    from the existing TOTP *step-up* gates (Email Settings, Security hub,
    SOC), which only apply once already enrolled; this is what forces
    enrollment to happen in the first place.

    MANDATORY_ADMIN_MFA defaults on; tests disable it globally (matching the
    existing pattern of disabling flask-limiter under pytest) since most of
    the suite logs in admin sessions directly via session_transaction without
    walking through enrollment, and re-enable it only in the tests that
    specifically exercise this gate.
    """
    if not current_app.config.get("MANDATORY_ADMIN_MFA", True):
        return
    if request.path.startswith("/static/") or request.path == "/healthz":
        return
    if request.path in _MANDATORY_MFA_EXEMPT_PATHS:
        return
    username = session.get("admin_username")
    if not (session.get("admin_logged_in") and username):
        return
    if session.get("admin_role", "admin") not in _MANDATORY_MFA_ROLES:
        return
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT COALESCE(totp_enabled, 0) FROM admin_users WHERE username=%s", (username,))
    row = cursor.fetchone()
    cursor.close()
    db.close()
    if row and row[0]:
        return
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "msg": "MFA enrollment required before continuing.",
                        "redirect": "/admin/mfa-required"}), 403
    return redirect("/admin/mfa-required")


@app.before_request
def _enforce_csrf():
    if request.method != "POST":
        return
    if current_app.testing:
        return  # CSRF disabled in test mode; Bearer-token tests handle auth separately
    if request.path.startswith("/api/"):
        return  # API routes use Bearer-token auth — no session/CSRF needed
    if request.path in ("/login", "/admin_login", "/hr_login"):
        return  # Login routes handle credential verification & rate-limiting
    # NOTE: We intentionally do NOT skip JSON requests here. The auto-inject
    # script (_inject_csrf_meta) adds X-CSRF-Token to every fetch() call, so
    # legitimate JSON POSTs from the web UI already carry the token.
    # Skipping CSRF for is_json would allow XSS payloads to forge state-changing
    # JSON requests without a token.
    token = session.get("_csrf")
    submitted = (request.form.get("_csrf_token")
                 or request.headers.get("X-CSRF-Token")
                 or request.headers.get("X-CSRFToken"))
    if not token or not submitted or not secrets.compare_digest(str(token), str(submitted)):
        # Browser form submissions: redirect to login so the user gets a fresh session+token
        if request.accept_mimetypes.accept_html and not request.headers.get("X-Requested-With"):
            flash("Your session expired. Please log in again.", "warning")
            if request.path.startswith("/employee") or "employee" in request.path:
                login_url = url_for("auth.employee_login")
            elif request.path.startswith("/super_admin"):
                login_url = "/super_admin/login"
            else:
                login_url = url_for("auth.admin_login")
            return redirect(login_url)
        return jsonify({"ok": False, "msg": "Session expired. Please refresh and try again."}), 403


_CSRF_HEAD_RE = re.compile(rb'</head>', re.IGNORECASE)
_CSRF_BODY_RE = re.compile(rb'</body>', re.IGNORECASE)
# Matches <script>/<style> tags without a nonce — used to inject CSP nonces
_SCRIPT_TAG_RE = re.compile(rb'<script(?!\s[^>]*\bnonce\b)(?=[\s>])', re.IGNORECASE)
_STYLE_TAG_RE = re.compile(rb'<style(?!\s[^>]*\bnonce\b)(?=[\s>])', re.IGNORECASE)
# Capture inline event-handler values for dynamic CSP sha256 hash generation.
# Two patterns: double-quoted and single-quoted attribute values.
_CSP_EV_DQ = re.compile(
    rb'\bon(?:animationend|blur|change|click|contextmenu|copy|cut|dblclick|drag|dragend'
    rb'|dragenter|dragleave|dragover|dragstart|drop|error|focus|input|invalid|keydown|keypress'
    rb'|keyup|load|mousedown|mousemove|mouseout|mouseover|mouseup|paste|pointerdown'
    rb'|pointermove|pointerup|reset|scroll|select|submit|touchend|touchmove|touchstart'
    rb'|transitionend|wheel)\s*=\s*"([^"]*)"',
    re.IGNORECASE,
)
_CSP_EV_SQ = re.compile(
    rb"\bon(?:animationend|blur|change|click|contextmenu|copy|cut|dblclick|drag|dragend"
    rb"|dragenter|dragleave|dragover|dragstart|drop|error|focus|input|invalid|keydown|keypress"
    rb"|keyup|load|mousedown|mousemove|mouseout|mouseover|mouseup|paste|pointerdown"
    rb"|pointermove|pointerup|reset|scroll|select|submit|touchend|touchmove|touchstart"
    rb"|transitionend|wheel)\s*=\s*'([^']*)'",
    re.IGNORECASE,
)
_CSRF_SCRIPT = (
    b'<script>(function(){'
    b'var m=document.querySelector(\'meta[name="csrf-token"]\');'
    b'if(!m)return;'
    b'window._csrfToken=function(){return m.content;};'
    b'var _of=window.fetch;'
    b'window.fetch=function(u,o){'
    b'o=o||{};'
    b'var mt=(o.method||"GET").toUpperCase();'
    b'if(mt==="POST"||mt==="PUT"||mt==="PATCH"||mt==="DELETE"){'
    b'if(o.headers instanceof Headers){'
    b'if(!o.headers.has("X-CSRF-Token"))o.headers.set("X-CSRF-Token",m.content);'
    b'}else{o.headers=Object.assign({},o.headers||{});'
    b'if(!o.headers["X-CSRF-Token"])o.headers["X-CSRF-Token"]=m.content;}}'
    b'return _of.call(this,u,o);};'
    b'document.addEventListener("DOMContentLoaded",function(){'
    b'document.querySelectorAll("form").forEach(function(f){'
    b'if(f.method.toLowerCase()==="post"&&!f.querySelector(\'[name="_csrf_token"]\')){'
    b'var i=document.createElement("input");'
    b'i.type="hidden";i.name="_csrf_token";i.value=m.content;'
    b'f.prepend(i);}});});})();</script>'
)
# Session kill-switch listener — only injected on pages rendered for an
# authenticated session (see _inject_csrf_meta below), since the SSE
# endpoint itself requires auth and there's nothing to listen for on public
# pages. EventSource auto-reconnects on its own when a bounded-duration
# stream closes normally (see /api/session/risk-stream), so onerror is
# deliberately a no-op rather than manual reconnect logic.
#
# IMPORTANT, and worth being explicit about: this client-side wipe/redirect
# is a UX nicety, not the security boundary. The session cookie is
# HttpOnly by design (extensions.py), so this script cannot read or clear
# it — that's what HttpOnly means, and weakening it to let JS touch the
# session cookie would be a strictly worse trade for a cosmetic gain. The
# real kill switch is server-side: utils/auth.py's _reject_if_compromised()
# rejects every request on a compromised session regardless of whether
# this script ever runs, and the server's own redirect response is what
# actually clears the session cookie via Set-Cookie. The cookie-wipe loop
# below only ever affects non-HttpOnly cookies (e.g. anything analytics-
# related some future page might add) — harmless to include, not load-
# bearing for security.
_KILLSWITCH_SCRIPT = (
    b'<script>(function(){'
    b'if(typeof EventSource==="undefined")return;'
    b'var es=new EventSource("/api/session/risk-stream");'
    b'function kill(){'
    b'es.close();'
    b'try{alert("Security alert: unusual activity was detected on your account and this session has been ended. Please contact your administrator.");}catch(e){}'
    b'try{localStorage.clear();}catch(e){}'
    b'try{sessionStorage.clear();}catch(e){}'
    b'try{document.cookie.split(";").forEach(function(c){'
    b'var n=c.split("=")[0].trim();'
    b'if(n)document.cookie=n+"=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/";'
    b'});}catch(e){}'
    b'location.replace("/security_lockout");'
    b'}'
    b'es.addEventListener("compromised",kill);'
    b'es.onerror=function(){};'
    b'})();</script>'
)


@app.before_request
def _set_csp_nonce():
    from flask import g
    g.csp_nonce = secrets.token_urlsafe(16)


_SETTINGS_PATHS = {"/settings", "/admin_set_recovery_email",
                   "/save_security_settings", "/toggle_auth_feature",
                   "/toggle_fingerprint", "/save_company_code", "/save_geo_settings",
                   "/save_company_info", "/toggle_feature"}


@app.after_request
def _security_headers(response):
    from flask import g
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=(self)"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Server"] = "AttendanceApp"
    if request.scheme == "https":
        # 2 years (63072000s), the floor major browsers require before a
        # domain is eligible for HSTS preload-list inclusion.
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    ct = response.content_type or ""
    if "text/html" in ct:
        nonce = getattr(g, "csp_nonce", "")
        # _inject_csrf_meta runs before this hook (Flask reverses registration order),
        # so response.get_data() is the final HTML with nonces already injected.
        # Scan for inline event-handler values and compute sha256 hashes so they
        # pass CSP without needing 'unsafe-inline'.
        try:
            data = response.get_data()
            _ev_hashes: set = set()
            for _pat in (_CSP_EV_DQ, _CSP_EV_SQ):
                for _m in _pat.finditer(data):
                    _body = _html.unescape(_m.group(1).decode("utf-8", errors="replace"))
                    _ev_hashes.add(
                        "'sha256-" + base64.b64encode(
                            hashlib.sha256(_body.encode("utf-8")).digest()
                        ).decode() + "'"
                    )
        except Exception:
            _ev_hashes = set()
        _unsafe_hashes = " 'unsafe-hashes'" if _ev_hashes else ""
        _hash_src = (" " + " ".join(sorted(_ev_hashes))) if _ev_hashes else ""
        # Cloudflare Turnstile (admin_login's CAPTCHA gate — utils/auth.py)
        # loads a live script from Cloudflare's own edge and renders in an
        # iframe; neither can be self-hosted the way jsQR/Tabler Icons were,
        # so this is a deliberate, path-scoped exception rather than a
        # blanket relaxation of the CSP for every page.
        _is_turnstile_page = request.path == "/admin_login"
        _turnstile_src = " https://challenges.cloudflare.com" if _is_turnstile_page else ""
        _frame_src = "https://challenges.cloudflare.com" if _is_turnstile_page else "'none'"
        # Employee portal's "DEVICE POSTURE RELAY" script (employee_portal.html)
        # polls a locally-running Wi-Fi posture agent over loopback
        # (desktop_agent/wifi_posture_agent.py, 127.0.0.1:47823) — a
        # deliberate, path-scoped exception, not a blanket relaxation,
        # same pattern as the Turnstile carve-out above.
        _is_employee_portal_page = request.path == "/employee_portal"
        _agent_src = " http://127.0.0.1:47823" if _is_employee_portal_page else ""
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'{_unsafe_hashes}{_hash_src}{_turnstile_src}; "
            f"style-src-elem 'self' 'nonce-{nonce}'; "
            "style-src-attr 'unsafe-inline'; "
            f"style-src 'self' 'nonce-{nonce}'; "
            "img-src 'self' data: blob:; "
            "font-src 'self' data:; "
            f"connect-src 'self'{_turnstile_src}{_agent_src}; "
            f"frame-src {_frame_src}; "
            "frame-ancestors 'none'; "
            # No <object>/<embed>/<applet> use anywhere in this app —
            # explicit 'none' instead of relying on the default-src 'self'
            # fallback closes off Flash/legacy-plugin-based XSS vectors.
            "object-src 'none'; "
            "report-uri /csp-report;"
        )
    return response


# csp_report migrated to blueprints/core.py


@app.after_request
def _bust_settings_cache(response):
    if request.method == "POST" and request.path in _SETTINGS_PATHS:
        invalidate_settings_cache()
    return response


@app.after_request
def _inject_csrf_meta(response):
    """Inject CSRF meta tag and auto-inject script into every HTML page.

    CSP nonce injection (the second half below) must run for EVERY
    text/html response regardless of status code — _security_headers sets
    a nonce-requiring CSP header unconditionally, including on error pages
    (404/403/500). This function used to skip everything for status>=300,
    which meant every error page shipped a <style> tag with no nonce while
    the CSP header demanded one — the browser correctly blocked it, which
    is the "Applying inline style violates CSP" error seen on any page that
    hit an error handler. CSRF meta-tag/script injection still only makes
    sense on normal (status<300) pages, so that part stays gated.
    """
    if not response.content_type.startswith("text/html"):
        return response
    try:
        from flask import g
        data = response.get_data()
        if response.status_code < 300:
            token = _csrf_token()
            meta = f'<meta name="csrf-token" content="{token}" />'.encode()
            data = _CSRF_HEAD_RE.sub(meta + b'</head>', data, count=1)
            _body_scripts = _CSRF_SCRIPT
            if session.get("admin_logged_in") or session.get("employee_id"):
                _body_scripts += _KILLSWITCH_SCRIPT
            data = _CSRF_BODY_RE.sub(_body_scripts + b'</body>', data, count=1)
        nonce = getattr(g, "csp_nonce", None)
        if nonce:
            nb = nonce.encode()
            data = _SCRIPT_TAG_RE.sub(b'<script nonce="' + nb + b'"', data)
            data = _STYLE_TAG_RE.sub(b'<style nonce="' + nb + b'"', data)
        response.set_data(data)
    except Exception:
        pass
    return response


@app.after_request
def _perf_record(response):
    """Record real request timing/error-rate for the Security hub's
    Performance & Quality panel. Skips static assets — they're served
    differently (cached, no app logic) and would skew the average down."""
    from flask import g
    start = getattr(g, "_perf_start", None)
    if start is not None and not request.path.startswith("/static/"):
        from utils.perf_metrics import record as _record_perf
        _record_perf((time.perf_counter() - start) * 1000, response.status_code)
    return response

# ---------------- AUDIT LOGGING ----------------
# (Consolidated onto utils/helpers.py — see import block above.)

# ---------------- FILE UPLOAD VALIDATION ----------------
# (Consolidated onto utils/helpers.py — see the import block above. app.py
# used to carry its own duplicate of _scan_for_malware/_validate_upload/
# _validate_image_file, which meant the security-event logging added to
# the utils/helpers.py versions never reached any of app.py's 10 real
# upload call sites. Same bug class as the auth-decorator duplication
# fixed earlier this session, found the same way: by checking whether an
# edited function's call sites actually resolved to the edited copy.)

# ---------------- COMPANY SETTINGS (with 60-second TTL cache) ----------------
# Consolidated onto utils/helpers.py — app.py used to carry its own
# separate _co_cache/_auth_cache dicts. Both copies were logically
# identical, but being separate meant a settings change saved through
# app.py's real routes (which call app.py's own invalidate_settings_cache())
# would never clear a cache a future blueprint read through
# utils.helpers.get_company_settings() — up to 60 seconds of serving a
# stale company name/logo/setup_done flag to any code path using the
# other copy. One cache now, so one invalidation reaches everyone.

# _VALID_CFS_COLS / _upsert_co_feature / _upsert_co_features consolidated
# onto utils/helpers.py (see import block near the top of this file) — that
# copy double-gates column names (frozenset membership + identifier regex)
# where this one only checked the frozenset. Not independently exploitable
# on its own (the frozenset is an exact-match allowlist, not a pattern, so
# nothing outside the 19 known-safe column names could ever reach the
# f-string SQL below either way) but the two copies had also drifted
# functionally: this file's allowlist had 5 columns
# (shift_start/shift_half/shift_end/holiday_pay/leave_pay) that the
# utils/helpers.py copy was missing, since added there to match.


@app.context_processor
def inject_company():
    return {"co": get_company_settings()}


# Office location, shift timings, and deduction rates now live solely in
# utils/config.py — see the `import utils.config as cfg` note above.
# Startup load still happens here (same timing as before: once, at import,
# inside an app context) since nothing else in this file's import order
# guarantees the DB is reachable earlier than this point.
with app.app_context():
    try:
        cfg.load_default_shift()
        cfg.load_salary_rules()
    except Exception:
        pass

# ── PII Encryption ────────────────────────────────────────────────
# Consolidated onto utils/helpers.py (see import block near the top of this
# file) — that was the weaker of the two copies (silent no-op on a missing
# key, in every environment); it's now the strict, fail-secure canonical
# version instead of being deleted, since app.py importing at module load
# time means its bootstrap check already runs before this file finishes
# loading either way.


# ---------------- DB CONTEXT MANAGER ----------------
# (Consolidated onto utils/helpers.py — see import block above. Note:
# utils/auth.py also carries its own small, identical copy of this same
# contextmanager — out of scope for this pass, which covers app.py +
# utils/helpers.py + email_utils.py + attendance_utils.py + config.py;
# low priority since it's self-contained within the utils package and
# behaviorally identical.)

# ---------------- DB MIGRATION ----------------
# Trigger function backing every `... ON UPDATE CURRENT_TIMESTAMP`-style
# column from the old MySQL schema — Postgres has no column-level
# equivalent, so each such table gets a BEFORE UPDATE trigger calling this.
_UPDATED_AT_TRIGGER_FN = """
    CREATE OR REPLACE FUNCTION _set_updated_at() RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
"""


def _attach_updated_at_trigger(cursor, table):
    cursor.execute(f'DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}')
    cursor.execute(f"""
        CREATE TRIGGER trg_{table}_updated_at BEFORE UPDATE ON {table}
        FOR EACH ROW EXECUTE FUNCTION _set_updated_at()
    """)


def init_db():
    """Create/upgrade the schema, then seed defaults. Split into three
    ordered phases — table creation, ALTER-TABLE migrations for existing
    installs, and one-time seeding — so each phase is independently
    readable/testable instead of one 1000+ line function; the phases must
    still run in exactly this order (migrations assume their tables
    already exist, seeding assumes its columns already exist)."""
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    _init_core_tables(cursor, db)
    _run_schema_migrations(cursor, db)
    _seed_defaults_and_admin(cursor, db)
    cursor.close()
    db.close()


def _init_core_tables(cursor, db):
    """Create every base table (and its triggers/seed rows) this app
     needs, in dependency order — e.g. company_settings before the
     migrations below that ALTER it. Idempotent: every statement is
     CREATE TABLE IF NOT EXISTS, safe to re-run on every startup."""
    cursor.execute(_UPDATED_AT_TRIGGER_FN)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id SERIAL PRIMARY KEY,
            employee_id VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(150) DEFAULT NULL,
            face_image VARCHAR(255),
            qr_code VARCHAR(255)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id SERIAL PRIMARY KEY,
            employee_id VARCHAR(50) NOT NULL,
            date DATE NOT NULL,
            login_time TIME DEFAULT NULL,
            logout_time TIME DEFAULT NULL,
            status VARCHAR(50) DEFAULT NULL,
            logout_status VARCHAR(50) DEFAULT NULL,
            attendance_type VARCHAR(50) DEFAULT NULL,
            UNIQUE (employee_id, date)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS holidays (
            id SERIAL PRIMARY KEY,
            date DATE UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS salary_config (
            id SERIAL PRIMARY KEY,
            employee_id VARCHAR(50) UNIQUE NOT NULL,
            salary_per_day DECIMAL(10,2) DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payroll_config (
            id SERIAL PRIMARY KEY,
            pf_employee_pct DECIMAL(5,2) DEFAULT 12.00,
            pf_employer_pct DECIMAL(5,2) DEFAULT 12.00,
            professional_tax DECIMAL(8,2) DEFAULT 200.00,
            tds_annual_pct DECIMAL(5,2) DEFAULT 0.00,
            pf_basic_cap DECIMAL(10,2) DEFAULT 15000.00
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            email VARCHAR(150) DEFAULT NULL,
            reset_token VARCHAR(64) DEFAULT NULL,
            reset_token_expiry TIMESTAMP DEFAULT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_config (
            id SERIAL PRIMARY KEY,
            smtp_host VARCHAR(150) NOT NULL,
            smtp_port INT NOT NULL DEFAULT 587,
            smtp_user VARCHAR(150) NOT NULL,
            smtp_pass VARCHAR(255) NOT NULL,
            from_name VARCHAR(100) DEFAULT 'HR Department',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _attach_updated_at_trigger(cursor, "email_config")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leave_requests (
            id SERIAL PRIMARY KEY,
            employee_id VARCHAR(50) NOT NULL,
            leave_date DATE NOT NULL,
            reason VARCHAR(500) NOT NULL,
            status VARCHAR(20) DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            recipient_type VARCHAR(20) NOT NULL CHECK (recipient_type IN ('admin', 'employee')),
            employee_id VARCHAR(50) NULL,
            title VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resignation_requests (
            id SERIAL PRIMARY KEY,
            employee_id VARCHAR(50) NOT NULL,
            last_working_day DATE NOT NULL,
            reason TEXT NOT NULL,
            status VARCHAR(20) DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id SERIAL PRIMARY KEY,
            employee_id VARCHAR(50) NOT NULL,
            category VARCHAR(100) NOT NULL,
            subject VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            priority VARCHAR(20) DEFAULT 'Medium',
            status VARCHAR(30) DEFAULT 'Open',
            admin_response TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _attach_updated_at_trigger(cursor, "tickets")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shifts (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            start_time TIME NOT NULL,
            half_time  TIME NOT NULL,
            end_time   TIME NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            content TEXT NOT NULL,
            priority VARCHAR(20) DEFAULT 'Normal' CHECK (priority IN ('Normal','Important','Urgent')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS break_config (
            id SERIAL PRIMARY KEY,
            break_name VARCHAR(100) NOT NULL,
            break_time TIME NOT NULL,
            duration_minutes INT NOT NULL DEFAULT 10,
            is_active SMALLINT DEFAULT 1
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS incentive_goals (
            id SERIAL PRIMARY KEY,
            title VARCHAR(150) NOT NULL,
            description TEXT,
            incentive_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
            is_active SMALLINT DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employee_incentives (
            id SERIAL PRIMARY KEY,
            employee_id VARCHAR(50) NOT NULL,
            goal_id INT NOT NULL,
            month INT NOT NULL,
            year INT NOT NULL,
            amount DECIMAL(10,2) NOT NULL DEFAULT 0,
            notes TEXT,
            awarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employee_experience (
            id SERIAL PRIMARY KEY,
            employee_id VARCHAR(50) NOT NULL,
            company VARCHAR(150) NOT NULL,
            designation VARCHAR(100) NOT NULL,
            from_year VARCHAR(10) NOT NULL,
            to_year VARCHAR(10) DEFAULT NULL,
            is_current SMALLINT DEFAULT 0,
            description TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employee_education (
            id SERIAL PRIMARY KEY,
            employee_id VARCHAR(50) NOT NULL,
            degree VARCHAR(150) NOT NULL,
            institution VARCHAR(200) NOT NULL,
            year_of_passing VARCHAR(10) DEFAULT NULL,
            percentage VARCHAR(20) DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leave_types (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            annual_quota INT NOT NULL DEFAULT 12,
            is_paid SMALLINT DEFAULT 1,
            is_active SMALLINT DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leave_balances (
            id SERIAL PRIMARY KEY,
            employee_id VARCHAR(50) NOT NULL,
            leave_type_id INT NOT NULL,
            year INT NOT NULL,
            total_days INT NOT NULL DEFAULT 0,
            used_days DECIMAL(4,1) NOT NULL DEFAULT 0,
            UNIQUE (employee_id, leave_type_id, year)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employee_documents (
            id SERIAL PRIMARY KEY,
            employee_id VARCHAR(50) NOT NULL,
            doc_type VARCHAR(100) NOT NULL,
            original_name VARCHAR(255) NOT NULL,
            stored_name VARCHAR(255) NOT NULL,
            uploaded_by VARCHAR(20) DEFAULT 'admin',
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS performance_reviews (
            id SERIAL PRIMARY KEY,
            employee_id VARCHAR(50) NOT NULL,
            quarter SMALLINT NOT NULL,
            year INT NOT NULL,
            overall_rating DECIMAL(3,1) DEFAULT 0,
            reviewer_feedback TEXT,
            employee_comment TEXT,
            status VARCHAR(20) DEFAULT 'Draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (employee_id, quarter, year)
        )
    """)
    _attach_updated_at_trigger(cursor, "performance_reviews")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS performance_kpis (
            id SERIAL PRIMARY KEY,
            review_id INT NOT NULL,
            kpi_title VARCHAR(200) NOT NULL,
            description TEXT,
            target VARCHAR(200),
            achievement VARCHAR(200),
            weight INT DEFAULT 20,
            rating SMALLINT DEFAULT 0,
            comments TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hike_config (
            id SERIAL PRIMARY KEY,
            label VARCHAR(80) NOT NULL,
            min_rating DECIMAL(3,1) NOT NULL,
            max_rating DECIMAL(3,1) NOT NULL,
            hike_pct DECIMAL(5,2) DEFAULT 0,
            incentive_pct DECIMAL(5,2) DEFAULT 0,
            color VARCHAR(20) DEFAULT '#1e3a8a'
        )
    """)
    cursor.execute("SELECT COUNT(*) FROM hike_config")
    if cursor.fetchone()[0] == 0:
        for _lbl, _mn, _mx, _hp, _ip, _clr in [
            ("Exceptional", 4.5, 5.0, 20.00, 15.00, "#15803d"),
            ("Exceeds Expectations", 4.0, 4.4, 15.00, 10.00, "#2563eb"),
            ("Meets Expectations", 3.0, 3.9, 10.00, 5.00, "#7c3aed"),
            ("Needs Improvement", 2.0, 2.9, 5.00, 0.00, "#d97706"),
            ("Below Expectations", 0.0, 1.9, 0.00, 0.00, "#dc2626"),
        ]:
            cursor.execute(
                "INSERT INTO hike_config (label, min_rating, max_rating, hike_pct, incentive_pct, color) VALUES (%s,%s,%s,%s,%s,%s)",
                (_lbl, _mn, _mx, _hp, _ip, _clr)
            )
        db.commit()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS overtime_records (
            id SERIAL PRIMARY KEY,
            employee_id VARCHAR(50) NOT NULL,
            date DATE NOT NULL,
            shift_end TIME NOT NULL,
            actual_logout TIME NOT NULL,
            ot_minutes INT NOT NULL DEFAULT 0,
            ot_pay DECIMAL(10,2) DEFAULT 0,
            status VARCHAR(20) DEFAULT 'Pending',
            notes TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (employee_id, date)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS onboarding_templates (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            is_active SMALLINT DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS onboarding_template_tasks (
            id SERIAL PRIMARY KEY,
            template_id INT NOT NULL,
            task_title VARCHAR(300) NOT NULL,
            task_description TEXT,
            requires_document SMALLINT DEFAULT 0,
            due_days INT DEFAULT 7,
            sort_order INT DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employee_onboarding (
            id SERIAL PRIMARY KEY,
            employee_id VARCHAR(50) NOT NULL,
            template_id INT NOT NULL,
            assigned_date DATE NOT NULL,
            due_date DATE,
            status VARCHAR(20) DEFAULT 'In Progress',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employee_onboarding_tasks (
            id SERIAL PRIMARY KEY,
            onboarding_id INT NOT NULL,
            template_task_id INT NOT NULL,
            employee_id VARCHAR(50) NOT NULL,
            task_title VARCHAR(300) NOT NULL,
            task_description TEXT,
            requires_document SMALLINT DEFAULT 0,
            due_days INT DEFAULT 7,
            status VARCHAR(20) DEFAULT 'Pending',
            completed_at TIMESTAMP NULL,
            document_path VARCHAR(500),
            admin_notes TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS offer_letters (
            id SERIAL PRIMARY KEY,
            onboarding_id INT NOT NULL,
            employee_id VARCHAR(50) NOT NULL,
            designation VARCHAR(150),
            department VARCHAR(150),
            work_location VARCHAR(200),
            monthly_ctc DECIMAL(12,2) DEFAULT 0,
            joining_date DATE,
            offer_valid_until DATE,
            probation_months INT DEFAULT 6,
            reporting_to VARCHAR(150),
            additional_notes TEXT,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sent_at TIMESTAMP DEFAULT NULL,
            status VARCHAR(20) DEFAULT 'draft',
            notice_period_days INT DEFAULT 30,
            candidate_address TEXT
        )
    """)
    for _col, _sql in [
        ("notice_period_days", "ALTER TABLE offer_letters ADD COLUMN IF NOT EXISTS notice_period_days INT DEFAULT 30"),
        ("candidate_address", "ALTER TABLE offer_letters ADD COLUMN IF NOT EXISTS candidate_address TEXT"),
        ("response_token", "ALTER TABLE offer_letters ADD COLUMN IF NOT EXISTS response_token VARCHAR(64) DEFAULT NULL"),
        ("candidate_response", "ALTER TABLE offer_letters ADD COLUMN IF NOT EXISTS candidate_response VARCHAR(20) DEFAULT NULL"),
        ("responded_at", "ALTER TABLE offer_letters ADD COLUMN IF NOT EXISTS responded_at TIMESTAMP DEFAULT NULL"),
        ("response_token_expiry", "ALTER TABLE offer_letters ADD COLUMN IF NOT EXISTS response_token_expiry TIMESTAMP DEFAULT NULL"),
    ]:
        try:
            cursor.execute(_sql)
            db.commit()
        except psycopg2.Error:
            db.rollback()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            actor VARCHAR(100) NOT NULL,
            actor_type VARCHAR(20) DEFAULT 'admin',
            action VARCHAR(150) NOT NULL,
            target_table VARCHAR(100),
            target_id VARCHAR(100),
            detail TEXT,
            ip_address VARCHAR(45),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_actor ON audit_logs (actor)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_action ON audit_logs (action)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_created ON audit_logs (created_at)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS login_attempts (
            id SERIAL PRIMARY KEY,
            identifier VARCHAR(150) NOT NULL,
            attempt_type VARCHAR(20) DEFAULT 'admin',
            failed_count INT DEFAULT 0,
            last_attempt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            locked_until TIMESTAMP DEFAULT NULL,
            UNIQUE (identifier, attempt_type)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance_lockouts (
            id SERIAL PRIMARY KEY,
            employee_id VARCHAR(50) NOT NULL,
            date DATE NOT NULL,
            failed_count INT NOT NULL DEFAULT 0,
            locked SMALLINT NOT NULL DEFAULT 0,
            lock_reason VARCHAR(200) DEFAULT NULL,
            locked_at TIMESTAMP DEFAULT NULL,
            unlocked_by VARCHAR(50) DEFAULT NULL,
            UNIQUE (employee_id, date)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS known_login_ips (
            id SERIAL PRIMARY KEY,
            identifier VARCHAR(150) NOT NULL,
            attempt_type VARCHAR(20) DEFAULT 'admin',
            ip_address VARCHAR(45) NOT NULL,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (identifier, attempt_type, ip_address)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS session_risk (
            sid          VARCHAR(64) PRIMARY KEY,
            identifier   VARCHAR(150) NOT NULL,
            attempt_type VARCHAR(20) DEFAULT 'admin',
            score        INT NOT NULL DEFAULT 0,
            status       VARCHAR(20) NOT NULL DEFAULT 'active',
            last_reason  VARCHAR(300) DEFAULT NULL,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS security_events (
            id          SERIAL PRIMARY KEY,
            event_type  VARCHAR(80) NOT NULL,
            level       VARCHAR(10) NOT NULL,
            message     VARCHAR(500) NOT NULL,
            identifier  VARCHAR(150),
            ip          VARCHAR(64),
            path        VARCHAR(255),
            method      VARCHAR(10),
            extra_json  TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_security_events_created ON security_events (created_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_security_events_type ON security_events (event_type)")

    # Immutable audit trail: audit_logs (data/config changes) and
    # security_events (auth/access events) must be append-only — a plain
    # table is only as tamper-resistant as every future line of code that
    # touches it, which isn't a guarantee. This trigger makes tampering
    # (or an attacker who reaches DB access) unable to alter or erase
    # history no matter what app code does, short of dropping the trigger
    # itself (a superuser-only DDL action, not something an app-level bug
    # or compromised web-tier credential can do).
    cursor.execute("""
        CREATE OR REPLACE FUNCTION _reject_audit_mutation() RETURNS TRIGGER AS $$
        BEGIN
            -- Deliberate, narrow escape hatch for test-fixture cleanup only:
            -- the app itself never issues `SET audit.bypass`, so this
            -- doesn't weaken production immutability — a session has to
            -- explicitly opt in via raw SQL the app never sends.
            IF current_setting('audit.bypass', true) = 'on' THEN
                RETURN COALESCE(NEW, OLD);
            END IF;
            RAISE EXCEPTION 'audit tables are append-only: % on % is not permitted', TG_OP, TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
    """)
    for _tbl in ("audit_logs", "security_events"):
        cursor.execute(f'DROP TRIGGER IF EXISTS trg_{_tbl}_immutable ON {_tbl}')
        cursor.execute(f"""
            CREATE TRIGGER trg_{_tbl}_immutable
            BEFORE UPDATE OR DELETE ON {_tbl}
            FOR EACH ROW EXECUTE FUNCTION _reject_audit_mutation()
        """)
    db.commit()

    # Application-layer IP ban list — the SOC dashboard's "one-click ban"
    # tactical mitigation. Not a substitute for a real edge/WAF ban (Cloudflare
    # or AWS Network Firewall, provisioned separately via terraform/), since a
    # request still costs a TLS handshake + one Python request cycle before
    # _enforce_ip_ban rejects it — but it needs no cloud API credentials and
    # takes effect immediately app-wide, which the Terraform-managed edge
    # rules don't do without a redeploy.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS banned_ips (
            ip         VARCHAR(45) PRIMARY KEY,
            reason     VARCHAR(300),
            banned_by  VARCHAR(150),
            banned_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP DEFAULT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_queue (
            id           SERIAL PRIMARY KEY,
            to_email     VARCHAR(255) NOT NULL,
            subject      VARCHAR(500) NOT NULL,
            html_body    TEXT   NOT NULL,
            attachment_b64 TEXT   DEFAULT NULL,
            attachment_filename VARCHAR(255) DEFAULT NULL,
            status       VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending','sending','done','failed')),
            attempts     SMALLINT DEFAULT 0,
            last_error   TEXT DEFAULT NULL,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sent_at      TIMESTAMP DEFAULT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_eq_status ON email_queue (status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_eq_created ON email_queue (created_at)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payroll_runs (
            id SERIAL PRIMARY KEY,
            year INT NOT NULL,
            month INT NOT NULL,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_by VARCHAR(100),
            email_count INT DEFAULT 0,
            UNIQUE (year, month)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS compoff_balance (
            id SERIAL PRIMARY KEY,
            employee_id VARCHAR(50) NOT NULL UNIQUE,
            earned_minutes INT DEFAULT 0,
            used_minutes INT DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _attach_updated_at_trigger(cursor, "compoff_balance")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_tokens (
            token VARCHAR(64) PRIMARY KEY,
            token_type VARCHAR(20) NOT NULL DEFAULT 'admin',
            identity VARCHAR(100) NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mobile_biometric_proofs (
            employee_id VARCHAR(50) PRIMARY KEY,
            nonce VARCHAR(64) DEFAULT NULL,
            nonce_expires_at TIMESTAMP DEFAULT NULL,
            verified_at TIMESTAMP DEFAULT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS regularization_requests (
            id SERIAL PRIMARY KEY,
            employee_id VARCHAR(50) NOT NULL,
            request_date DATE NOT NULL,
            login_time TIME DEFAULT NULL,
            logout_time TIME DEFAULT NULL,
            reason TEXT NOT NULL,
            status VARCHAR(20) DEFAULT 'Pending',
            admin_note TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP DEFAULT NULL,
            UNIQUE (employee_id, request_date)
        )
    """)
    db.commit()
    # Seed default leave types if empty
    cursor.execute("SELECT COUNT(*) FROM leave_types")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO leave_types (name, annual_quota, is_paid) VALUES (%s,%s,%s)",
            [
                ("Casual Leave", 12, 1),
                ("Sick Leave", 12, 1),
                ("Earned Leave", 15, 1),
                ("Maternity Leave", 90, 1),
                ("Paternity Leave", 5, 1),
                ("Comp-off", 0, 1),
            ]
        )
        db.commit()
    # Ensure Comp-off leave type exists
    cursor.execute("SELECT id FROM leave_types WHERE name='Comp-off' LIMIT 1")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO leave_types (name, annual_quota, is_paid) VALUES ('Comp-off', 0, 1)")
        db.commit()
    # Seed default breaks if table is empty
    cursor.execute("SELECT COUNT(*) FROM break_config")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO break_config (break_name, break_time, duration_minutes) VALUES (%s, %s, %s)",
            [
                ("Coffee Break 1", "11:00:00", 10),
                ("Lunch Break", "13:00:00", 60),
                ("Coffee Break 2", "16:00:00", 10),
            ]
        )
        db.commit()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            code VARCHAR(20) DEFAULT NULL,
            working_days VARCHAR(30) DEFAULT 'Mon,Tue,Wed,Thu,Fri',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS company_feature_settings (
            company_id INT PRIMARY KEY,
            face_auth_enabled  SMALLINT DEFAULT 1,
            qr_enabled         SMALLINT DEFAULT 1,
            fingerprint_enabled SMALLINT DEFAULT 0,
            geo_enabled        SMALLINT DEFAULT 0,
            geo_radius         INT DEFAULT 300,
            pin_enabled        SMALLINT DEFAULT 1,
            biometric_enabled  SMALLINT DEFAULT 0,
            notify_leave       SMALLINT DEFAULT 1,
            notify_payslip     SMALLINT DEFAULT 1,
            notify_resignation SMALLINT DEFAULT 1,
            notify_doc_expiry  SMALLINT DEFAULT 1,
            session_timeout    INT DEFAULT 30,
            late_deduction_pct DECIMAL(5,2) DEFAULT 10.00,
            half_day_deduction_pct DECIMAL(5,2) DEFAULT 50.00,
            grace_minutes      INT DEFAULT 15,
            holiday_pay        VARCHAR(20) DEFAULT 'paid' CHECK (holiday_pay IN ('paid','unpaid')),
            leave_pay          VARCHAR(20) DEFAULT 'exclude' CHECK (leave_pay IN ('exclude','absent')),
            shift_start        TIME DEFAULT '09:00:00',
            shift_half         TIME DEFAULT '13:00:00',
            shift_end          TIME DEFAULT '18:00:00',
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """)
    db.commit()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS id_card_templates (
            company_id INT PRIMARY KEY,
            front_image VARCHAR(255) DEFAULT NULL,
            back_image VARCHAR(255) DEFAULT NULL,
            fields TEXT DEFAULT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """)
    db.commit()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shift_swap_requests (
            id SERIAL PRIMARY KEY,
            requester_id VARCHAR(50) NOT NULL,
            target_id VARCHAR(50) NOT NULL,
            requester_shift_id INT NOT NULL,
            target_shift_id INT NOT NULL,
            reason TEXT,
            status VARCHAR(20) DEFAULT 'Pending_Target' CHECK (status IN ('Pending_Target','Pending_Admin','Approved','Rejected','Rejected_Admin')),
            target_response TEXT,
            admin_response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _attach_updated_at_trigger(cursor, "shift_swap_requests")
    db.commit()
    db.commit()

    # Create company_settings table (must precede the migration loop below,
    # which ALTERs this table — on a fresh install with nothing to migrate
    # from, an ALTER before the table exists silently no-ops instead of
    # erroring, so column order here isn't just cosmetic).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS company_settings (
            id SERIAL PRIMARY KEY,
            company_name VARCHAR(200) DEFAULT 'My Company',
            company_tagline VARCHAR(300) DEFAULT 'HRzest.com',
            company_logo VARCHAR(255) DEFAULT NULL,
            currency_symbol VARCHAR(10) DEFAULT '₹',
            timezone VARCHAR(60) DEFAULT 'Asia/Kolkata',
            setup_done SMALLINT DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _attach_updated_at_trigger(cursor, "company_settings")
    db.commit()
    # Add default shift columns if not present
    for col, default in [("shift_start", "09:00:00"), ("shift_half", "13:00:00"), ("shift_end", "18:00:00")]:
        try:
            cursor.execute(f"ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS {col} TIME DEFAULT '{default}'")
            db.commit()
        except Exception:
            pass


def _run_schema_migrations(cursor, db):
    """ALTER existing installs' tables up to the current schema: new
    columns, indexes, FK backstops, and one-time data migrations, split
    into independently ordered phases so each stays small and readable.
    Order matters: column ALTERs must precede everything that assumes
    those columns exist (indexes, PII widening, FK backstops)."""
    _run_column_migrations(cursor, db)
    _run_password_migrations(cursor, db)
    _run_index_migrations(cursor, db)
    _run_data_integrity_migrations(cursor, db)


def _run_column_migrations(cursor, db):
    """Add every column an existing install might be missing —
    idempotent (IF NOT EXISTS) and independently try/except-guarded per
    statement so one unsupported ALTER on an older Postgres can't block
    the rest."""
    # Migrations for existing installs
    for sql in [
        "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS logout_status VARCHAR(50) DEFAULT NULL",
        "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS attendance_type VARCHAR(50) DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS email VARCHAR(150) DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS role VARCHAR(100) DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS password VARCHAR(255) DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS shift_id INT DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS date_of_joining DATE DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS phone VARCHAR(20) DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS gender VARCHAR(20) DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS dob DATE DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS blood_group VARCHAR(10) DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS address TEXT DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS city VARCHAR(100) DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS state VARCHAR(100) DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS pincode VARCHAR(20) DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS emergency_contact_name VARCHAR(100) DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS emergency_contact_phone VARCHAR(20) DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS emergency_contact_relation VARCHAR(50) DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS aadhar_number TEXT DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS pan_number TEXT DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS bank_name VARCHAR(100) DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS bank_account TEXT DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS bank_ifsc TEXT DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS uan_number TEXT DEFAULT NULL",
        "ALTER TABLE employees ALTER COLUMN aadhar_number TYPE TEXT",
        "ALTER TABLE employees ALTER COLUMN pan_number TYPE TEXT",
        "ALTER TABLE employees ALTER COLUMN bank_account TYPE TEXT",
        "ALTER TABLE employees ALTER COLUMN bank_ifsc TYPE TEXT",
        "ALTER TABLE employees ALTER COLUMN uan_number TYPE TEXT",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS work_mode VARCHAR(20) DEFAULT 'office'",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS work_lat DECIMAL(10,8) DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS work_lon DECIMAL(11,8) DEFAULT NULL",
        "ALTER TABLE salary_config ADD COLUMN IF NOT EXISTS last_revised DATE DEFAULT NULL",
        "ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS email VARCHAR(150) DEFAULT NULL",
        "ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS reset_token VARCHAR(64) DEFAULT NULL",
        "ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS reset_token_expiry TIMESTAMP DEFAULT NULL",
        "ALTER TABLE email_config ADD COLUMN IF NOT EXISTS from_email VARCHAR(150) DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS about_me TEXT DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS manager_name VARCHAR(150) DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS manager_id VARCHAR(20) DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS department VARCHAR(100) DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS designation VARCHAR(150) DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS is_active SMALLINT DEFAULT 1",
        "ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS leave_type_id INT DEFAULT NULL",
        "ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS is_half_day SMALLINT DEFAULT 0",
        "ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS half_day_session VARCHAR(10) DEFAULT NULL",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS company_code VARCHAR(10) DEFAULT NULL",
        "ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'admin'",
        "ALTER TABLE companies ADD COLUMN IF NOT EXISTS logo_path VARCHAR(255) DEFAULT NULL",
        "ALTER TABLE companies ADD COLUMN IF NOT EXISTS address TEXT DEFAULT NULL",
        "ALTER TABLE companies ADD COLUMN IF NOT EXISTS website VARCHAR(255) DEFAULT NULL",
        "ALTER TABLE companies ADD COLUMN IF NOT EXISTS email VARCHAR(255) DEFAULT NULL",
        "ALTER TABLE companies ADD COLUMN IF NOT EXISTS phone VARCHAR(30) DEFAULT NULL",
        "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS worked_minutes INT DEFAULT 0",
        "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS last_relogin TIME DEFAULT NULL",
        "ALTER TABLE salary_config ADD COLUMN IF NOT EXISTS monthly_ctc DECIMAL(12,2) DEFAULT 0",
        "ALTER TABLE salary_config ADD COLUMN IF NOT EXISTS basic_pct INT DEFAULT 50",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS compoff_min_ot_minutes INT DEFAULT 120",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS compoff_minutes_per_day INT DEFAULT 480",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS late_deduction_pct DECIMAL(5,2) DEFAULT 10.00",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS half_day_deduction_pct DECIMAL(5,2) DEFAULT 50.00",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS grace_minutes INT DEFAULT 15",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS holiday_pay VARCHAR(20) DEFAULT 'paid' CHECK (holiday_pay IN ('paid','unpaid'))",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS leave_pay VARCHAR(20) DEFAULT 'exclude' CHECK (leave_pay IN ('exclude','absent'))",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS joining_date DATE DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS company_id INT DEFAULT NULL",
        "ALTER TABLE employee_documents ADD COLUMN IF NOT EXISTS expiry_date DATE DEFAULT NULL",
        "ALTER TABLE overtime_records ADD COLUMN IF NOT EXISTS requested_by_employee SMALLINT DEFAULT 0",
        "ALTER TABLE overtime_records ADD COLUMN IF NOT EXISTS employee_reason VARCHAR(500) DEFAULT NULL",
        "ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMP DEFAULT NULL",
        "ALTER TABLE salary_config ADD COLUMN IF NOT EXISTS last_hike_quarter SMALLINT DEFAULT NULL",
        "ALTER TABLE salary_config ADD COLUMN IF NOT EXISTS last_hike_year INT DEFAULT NULL",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS default_onboarding_template_id INT DEFAULT NULL",
        "ALTER TABLE employee_onboarding_tasks ADD COLUMN IF NOT EXISTS employee_note VARCHAR(500) DEFAULT NULL",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS fingerprint_enabled SMALLINT DEFAULT 0",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS qr_enabled SMALLINT DEFAULT 1",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS face_enabled SMALLINT DEFAULT 1",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS location_enabled SMALLINT DEFAULT 1",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS employee_password_auth SMALLINT DEFAULT 1",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS fingerprint_credential_id VARCHAR(512) DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS fingerprint_public_key TEXT DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS fingerprint_sign_count INT DEFAULT 0",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS face_auth_enabled SMALLINT DEFAULT 0",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS geo_enabled SMALLINT DEFAULT 0",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS geo_radius INT DEFAULT 100",
        # NULL = not configured yet, geofencing is a no-op regardless of
        # location_enabled -- see utils/attendance_utils.py's
        # is_within_office_range(). Previously every tenant was silently
        # geofenced against one process-wide OFFICE_LAT/LON env var; this
        # makes office location a real per-tenant setting.
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS office_lat DOUBLE PRECISION DEFAULT NULL",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS office_lon DOUBLE PRECISION DEFAULT NULL",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS pin_enabled SMALLINT DEFAULT 1",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS biometric_enabled SMALLINT DEFAULT 0",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS notify_leave SMALLINT DEFAULT 1",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS notify_payslip SMALLINT DEFAULT 1",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS notify_resignation SMALLINT DEFAULT 1",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS notify_doc_expiry SMALLINT DEFAULT 1",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS session_timeout INT DEFAULT 30",
        "ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS working_days VARCHAR(30) DEFAULT 'Mon,Tue,Wed,Thu,Fri'",
        "ALTER TABLE break_config ADD COLUMN IF NOT EXISTS break_type VARCHAR(20) DEFAULT 'coffee' CHECK (break_type IN ('coffee','lunch','custom'))",
        "ALTER TABLE break_config ADD COLUMN IF NOT EXISTS shift_id INT DEFAULT NULL",
        "ALTER TABLE companies ADD COLUMN IF NOT EXISTS working_days VARCHAR(30) DEFAULT 'Mon,Tue,Wed,Thu,Fri'",
        "ALTER TABLE onboarding_templates ADD COLUMN IF NOT EXISTS role VARCHAR(100) DEFAULT NULL",
        "ALTER TABLE shifts ADD COLUMN IF NOT EXISTS company_id INT DEFAULT NULL",
        "ALTER TABLE companies ADD COLUMN IF NOT EXISTS pin VARCHAR(10) DEFAULT NULL",
        "ALTER TABLE break_config ADD COLUMN IF NOT EXISTS company_id INT DEFAULT NULL",
        "ALTER TABLE announcements ADD COLUMN IF NOT EXISTS visibility VARCHAR(20) DEFAULT 'public' CHECK (visibility IN ('public','private'))",
        "ALTER TABLE announcements ADD COLUMN IF NOT EXISTS target_employee_id VARCHAR(50) DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS reset_token VARCHAR(80) DEFAULT NULL",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS reset_token_expiry TIMESTAMP DEFAULT NULL",
        "ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS totp_secret VARCHAR(255) DEFAULT NULL",
        "ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS totp_enabled SMALLINT NOT NULL DEFAULT 0",
        "ALTER TABLE performance_reviews ADD COLUMN IF NOT EXISTS potential_rating DECIMAL(3,1) DEFAULT 0",
    ]:
        try:
            cursor.execute(sql)
            db.commit()
        except psycopg2.Error:
            db.rollback()


def _run_password_migrations(cursor, db):
    """Back-fill a default PIN for employees with no password hash yet,
    plus the two related one-time migrations tracked in
    _applied_migrations (reset-to-default-PIN, and flagging accounts
    still on that default PIN as needing a forced change)."""
    # Back-fill password for existing employees that have none (default PIN = 1234)
    cursor.execute("SELECT employee_id FROM employees WHERE password IS NULL")
    for (eid,) in cursor.fetchall():
        cursor.execute(
            "UPDATE employees SET password=%s WHERE employee_id=%s",
            (generate_password_hash('1234'), eid)
        )
    db.commit()

    # One-time migration: reset ALL employees to default PIN 1234
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS _applied_migrations (
                name VARCHAR(100) PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.commit()
        cursor.execute("SELECT 1 FROM _applied_migrations WHERE name='default_pin_1234'")
        if not cursor.fetchone():
            cursor.execute("UPDATE employees SET password=%s", (generate_password_hash('1234'),))
            cursor.execute("INSERT INTO _applied_migrations (name) VALUES ('default_pin_1234')")
            db.commit()
    except Exception:
        pass

    # Migration: add force_pin_change column and flag employees on default PIN
    try:
        cursor.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS force_pin_change SMALLINT DEFAULT 0")
        db.commit()
    except psycopg2.Error:
        db.rollback()
    try:
        cursor.execute("SELECT 1 FROM _applied_migrations WHERE name='force_pin_change_flag'")
        if not cursor.fetchone():
            cursor.execute("SELECT employee_id, password FROM employees")
            for eid, pwd_hash in cursor.fetchall():
                if pwd_hash and check_password_hash(pwd_hash, '1234'):
                    cursor.execute("UPDATE employees SET force_pin_change=1 WHERE employee_id=%s", (eid,))
            cursor.execute("INSERT INTO _applied_migrations (name) VALUES ('force_pin_change_flag')")
            db.commit()
    except Exception:
        pass


def _run_index_migrations(cursor, db):
    """Three rounds of performance indexes added as real query-usage
    audits found missing ones — each in its own function since they're
    independent, one-time, _applied_migrations-tracked units."""
    _run_index_migrations_v1(cursor, db)
    _run_index_migrations_v2(cursor, db)
    _run_index_migrations_v3(cursor, db)


def _run_index_migrations_v1(cursor, db):
    # Performance indexes migration
    try:
        cursor.execute("SELECT 1 FROM _applied_migrations WHERE name='perf_indexes_v1'")
        if not cursor.fetchone():
            _idx_stmts = [
                "CREATE INDEX IF NOT EXISTS idx_leave_emp ON leave_requests(employee_id)",
                "CREATE INDEX IF NOT EXISTS idx_leave_status ON leave_requests(status)",
                "CREATE INDEX IF NOT EXISTS idx_tickets_emp ON tickets(employee_id)",
                "CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)",
                "CREATE INDEX IF NOT EXISTS idx_resign_emp ON resignation_requests(employee_id)",
                "CREATE INDEX IF NOT EXISTS idx_notif_emp ON notifications(employee_id)",
                "CREATE INDEX IF NOT EXISTS idx_notif_read ON notifications(is_read)",
                "CREATE INDEX IF NOT EXISTS idx_onboard_emp ON employee_onboarding(employee_id)",
                "CREATE INDEX IF NOT EXISTS idx_onboard_status ON employee_onboarding(status)",
                "CREATE INDEX IF NOT EXISTS idx_payroll_emp ON payroll_runs(employee_id)",
            ]
            for stmt in _idx_stmts:
                try:
                    cursor.execute(stmt)
                    db.commit()
                except Exception:
                    db.rollback()
            cursor.execute("INSERT INTO _applied_migrations (name) VALUES ('perf_indexes_v1')")
            db.commit()
    except Exception:
        pass


def _run_index_migrations_v2(cursor, db):
    """High-traffic columns missing from v1."""
    # Performance indexes v2 — high-traffic columns missing from v1
    try:
        cursor.execute("SELECT 1 FROM _applied_migrations WHERE name='perf_indexes_v2'")
        if not cursor.fetchone():
            _idx_stmts_v2 = [
                "CREATE INDEX IF NOT EXISTS idx_att_date ON attendance(date)",
                "CREATE INDEX IF NOT EXISTS idx_emp_active ON employees(is_active)",
                "CREATE INDEX IF NOT EXISTS idx_emp_company ON employees(company_id)",
                "CREATE INDEX IF NOT EXISTS idx_leave_date ON leave_requests(leave_date)",
            ]
            for stmt in _idx_stmts_v2:
                try:
                    cursor.execute(stmt)
                    db.commit()
                except Exception:
                    db.rollback()
            cursor.execute("INSERT INTO _applied_migrations (name) VALUES ('perf_indexes_v2')")
            db.commit()
    except Exception:
        pass


def _run_index_migrations_v3(cursor, db):
    """Found via a real query-usage audit (grepped every WHERE/JOIN
    against these columns before adding, not guessed):
    offer_letters.response_token is looked up on EVERY candidate-facing
    request (/offer_letter_pdf, /offer_letter_respond) with no index at
    all — the highest-value one here. The rest cover employee-scoped
    tables that were missing from v1/v2 despite the same WHERE
    employee_id=%s pattern as the tables v1 already covers."""
    # Performance indexes v3 — found via a real query-usage audit (grepped
    # every WHERE/JOIN against these columns before adding, not guessed):
    # offer_letters.response_token is looked up on EVERY candidate-facing
    # request (/offer_letter_pdf, /offer_letter_respond) with no index at
    # all — the highest-value one here. The rest cover employee-scoped
    # tables that were missing from v1/v2 despite the same WHERE
    # employee_id=%s pattern as the tables v1 already covers.
    try:
        cursor.execute("SELECT 1 FROM _applied_migrations WHERE name='perf_indexes_v3'")
        if not cursor.fetchone():
            _idx_stmts_v3 = [
                "CREATE INDEX IF NOT EXISTS idx_offer_letters_token ON offer_letters(response_token)",
                "CREATE INDEX IF NOT EXISTS idx_offer_letters_onboarding ON offer_letters(onboarding_id)",
                "CREATE INDEX IF NOT EXISTS idx_ob_tasks_onboarding ON employee_onboarding_tasks(onboarding_id)",
                "CREATE INDEX IF NOT EXISTS idx_perf_kpis_review ON performance_kpis(review_id)",
                "CREATE INDEX IF NOT EXISTS idx_emp_docs_emp ON employee_documents(employee_id)",
                "CREATE INDEX IF NOT EXISTS idx_incentives_emp ON employee_incentives(employee_id)",
                "CREATE INDEX IF NOT EXISTS idx_overtime_emp ON overtime_records(employee_id)",
                "CREATE INDEX IF NOT EXISTS idx_swap_requester_target ON shift_swap_requests(requester_id, target_id)",
            ]
            for stmt in _idx_stmts_v3:
                try:
                    cursor.execute(stmt)
                    db.commit()
                except Exception:
                    db.rollback()
            cursor.execute("INSERT INTO _applied_migrations (name) VALUES ('perf_indexes_v3')")
            db.commit()
    except Exception:
        pass


def _run_data_integrity_migrations(cursor, db):
    """One-time migrations that harden data integrity — each in its own
    function since they are independent, _applied_migrations-tracked
    units: a unique constraint backing the bonus-award idempotency
    check, widening Fernet-encrypted employee PII columns to TEXT so
    ciphertext fits, and NOT VALID foreign-key backstops on every
    employee_id/company_id column that was previously only enforced by
    application code."""
    _run_incentives_unique_constraint_migration(cursor, db)
    _run_pii_widen_migration_v1(cursor, db)
    _run_pii_widen_migration_v2(cursor, db)
    _run_fk_backstop_migration(cursor, db)


def _run_incentives_unique_constraint_migration(cursor, db):
    # Unique constraint backing award_performance_bonus's ON CONFLICT DO
    # NOTHING guard (blueprints/payroll.py) — without it, two concurrent
    # bonus-award requests for the same employee/goal/quarter could both
    # pass the app-level "already awarded?" check and double-pay a bonus.
    # Wrapped like the index migration above: if any deployment already has
    # duplicate rows, this no-ops via rollback rather than crashing startup.
    try:
        cursor.execute("SELECT 1 FROM _applied_migrations WHERE name='incentives_unique_v1'")
        if not cursor.fetchone():
            try:
                cursor.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_incentives_unique "
                    "ON employee_incentives(employee_id, goal_id, month, year)"
                )
                db.commit()
            except Exception:
                db.rollback()
            cursor.execute("INSERT INTO _applied_migrations (name) VALUES ('incentives_unique_v1')")
            db.commit()
    except Exception:
        pass


def _run_pii_widen_migration_v1(cursor, db):
    # Widen employee PII columns to TEXT so they can hold Fernet-encrypted
    # values (utils/helpers.py's encrypt_pii) — a base64 Fernet token has
    # ~100+ chars of fixed IV/HMAC/timestamp overhead even for a 2-character
    # plaintext like a blood group, which overflows every VARCHAR(N) column
    # below (and dob's native DATE type can't hold text/ciphertext at all).
    # Existing plaintext rows keep working unchanged — decrypt_pii() already
    # falls back to returning its input as-is when it isn't a valid Fernet
    # token, so nothing needs to be migrated, only re-saved to pick up
    # encryption going forward, same pattern already used for aadhar/pan/
    # bank_account/bank_ifsc/uan.
    try:
        cursor.execute("SELECT 1 FROM _applied_migrations WHERE name='employee_pii_columns_to_text_v1'")
        if not cursor.fetchone():
            _pii_widen_stmts = [
                "ALTER TABLE employees ALTER COLUMN dob TYPE TEXT USING dob::text",
                "ALTER TABLE employees ALTER COLUMN gender TYPE TEXT",
                "ALTER TABLE employees ALTER COLUMN blood_group TYPE TEXT",
                "ALTER TABLE employees ALTER COLUMN city TYPE TEXT",
                "ALTER TABLE employees ALTER COLUMN state TYPE TEXT",
                "ALTER TABLE employees ALTER COLUMN pincode TYPE TEXT",
                "ALTER TABLE employees ALTER COLUMN emergency_contact_name TYPE TEXT",
                "ALTER TABLE employees ALTER COLUMN emergency_contact_phone TYPE TEXT",
                "ALTER TABLE employees ALTER COLUMN emergency_contact_relation TYPE TEXT",
                "ALTER TABLE employees ALTER COLUMN bank_name TYPE TEXT",
            ]
            for stmt in _pii_widen_stmts:
                try:
                    cursor.execute(stmt)
                    db.commit()
                except Exception:
                    db.rollback()
            cursor.execute("INSERT INTO _applied_migrations (name) VALUES ('employee_pii_columns_to_text_v1')")
            db.commit()
    except Exception:
        pass


def _run_pii_widen_migration_v2(cursor, db):
    """v1 above widened 10 of the 15 Fernet-encrypted employee columns
    to TEXT. These 5 were missed — encrypt_pii() output runs 100+
    chars for any input, but aadhar_number/bank_ifsc stayed
    VARCHAR(20) and bank_account/uan_number VARCHAR(30), so
    registering an employee with any of these fields filled in
    raised psycopg2.StringDataRightTruncation ('value too long for
    type character varying(20)') — a real 500 on a standard field
    for an Indian payroll system, found while verifying the
    registration flow end-to-end rather than just reading the code."""
    # v1 above widened 10 of the 15 Fernet-encrypted employee columns to TEXT.
    # These 5 were missed — encrypt_pii() output runs 100+ chars for any
    # input, but aadhar_number/bank_ifsc stayed VARCHAR(20) and
    # bank_account/uan_number VARCHAR(30), so registering an employee with
    # any of these fields filled in raised psycopg2.StringDataRightTruncation
    # ("value too long for type character varying(20)") — a real 500 on a
    # standard field for an Indian payroll system, found while verifying the
    # registration flow end-to-end rather than just reading the code.
    try:
        cursor.execute("SELECT 1 FROM _applied_migrations WHERE name='employee_pii_columns_to_text_v2'")
        if not cursor.fetchone():
            _pii_widen_stmts_v2 = [
                "ALTER TABLE employees ALTER COLUMN aadhar_number TYPE TEXT",
                "ALTER TABLE employees ALTER COLUMN pan_number TYPE TEXT",
                "ALTER TABLE employees ALTER COLUMN bank_account TYPE TEXT",
                "ALTER TABLE employees ALTER COLUMN bank_ifsc TYPE TEXT",
                "ALTER TABLE employees ALTER COLUMN uan_number TYPE TEXT",
            ]
            for stmt in _pii_widen_stmts_v2:
                try:
                    cursor.execute(stmt)
                    db.commit()
                except Exception:
                    db.rollback()
            cursor.execute("INSERT INTO _applied_migrations (name) VALUES ('employee_pii_columns_to_text_v2')")
            db.commit()
    except Exception:
        pass


def _run_fk_backstop_migration(cursor, db):
    """Every employee_id/company_id column below was previously
    enforced only by application code (each delete path manually
    cleaning up related tables) with no FK constraint backing it, so a
    bug or a crash mid-delete could silently orphan rows instead of
    being caught or cascaded. Added NOT VALID so existing orphans (if
    any) from before this migration don't block it — only rows
    inserted/updated from now on are checked, closing the gap going
    forward without a risky retroactive cleanup of historical data."""
    # Referential-integrity backstop. Every employee_id/company_id column
    # below was previously enforced only by application code (each delete
    # path manually cleaning up related tables) with no FK constraint
    # backing it, so a bug or a crash mid-delete could silently orphan rows
    # instead of being caught or cascaded. Added NOT VALID so existing
    # orphans (if any) from before this migration don't block it — only
    # rows inserted/updated from now on are checked, closing the gap going
    # forward without a risky retroactive cleanup of historical data.
    try:
        cursor.execute("SELECT 1 FROM _applied_migrations WHERE name='fk_constraints_v1'")
        if not cursor.fetchone():
            _fk_stmts = [
                ("attendance", "employee_id", "employees", "employee_id", "CASCADE"),
                ("salary_config", "employee_id", "employees", "employee_id", "CASCADE"),
                ("leave_requests", "employee_id", "employees", "employee_id", "CASCADE"),
                ("resignation_requests", "employee_id", "employees", "employee_id", "CASCADE"),
                ("notifications", "employee_id", "employees", "employee_id", "CASCADE"),
                ("tickets", "employee_id", "employees", "employee_id", "CASCADE"),
                ("employee_incentives", "employee_id", "employees", "employee_id", "CASCADE"),
                ("employee_experience", "employee_id", "employees", "employee_id", "CASCADE"),
                ("employee_education", "employee_id", "employees", "employee_id", "CASCADE"),
                ("leave_balances", "employee_id", "employees", "employee_id", "CASCADE"),
                ("employee_documents", "employee_id", "employees", "employee_id", "CASCADE"),
                ("performance_reviews", "employee_id", "employees", "employee_id", "CASCADE"),
                ("overtime_records", "employee_id", "employees", "employee_id", "CASCADE"),
                ("regularization_requests", "employee_id", "employees", "employee_id", "CASCADE"),
                ("compoff_balance", "employee_id", "employees", "employee_id", "CASCADE"),
                ("employee_onboarding", "employee_id", "employees", "employee_id", "CASCADE"),
                ("employees", "company_id", "companies", "id", "SET NULL"),
                ("shifts", "company_id", "companies", "id", "SET NULL"),
                ("break_config", "company_id", "companies", "id", "SET NULL"),
            ]
            for _tbl, _col, _ref_tbl, _ref_col, _on_delete in _fk_stmts:
                _fk_name = f"fk_{_tbl}_{_col}"
                try:
                    cursor.execute(
                        f'ALTER TABLE {_tbl} ADD CONSTRAINT {_fk_name} '
                        f'FOREIGN KEY ({_col}) REFERENCES {_ref_tbl}({_ref_col}) '
                        f'ON DELETE {_on_delete} NOT VALID'
                    )
                    db.commit()
                except Exception:
                    db.rollback()
            cursor.execute("INSERT INTO _applied_migrations (name) VALUES ('fk_constraints_v1')")
            db.commit()
    except Exception:
        pass


def _seed_defaults_and_admin(cursor, db):
    """One-time seeding for a fresh install: the company_settings row,
     the env-configured admin account, and marking existing installs
     that already have an admin as setup-complete."""
    cursor.execute("SELECT COUNT(*) FROM company_settings")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO company_settings (setup_done) VALUES (0)")
        db.commit()

    # Seed admin from env — only if no admin exists yet
    _admin_user = os.environ.get("ADMIN_USERNAME", "admin").strip()
    _admin_pass = os.environ.get("ADMIN_PASSWORD", "").strip()
    cursor.execute("SELECT COUNT(*) FROM admin_users")
    admin_count = cursor.fetchone()[0]
    if admin_count == 0 and _admin_pass:
        cursor.execute(
            "INSERT INTO admin_users (username, password) VALUES (%s, %s)",
            (_admin_user, generate_password_hash(_admin_pass))
        )
        db.commit()
        app_log.info("Admin created: username=%s", _admin_user)
        admin_count = 1
    elif admin_count == 0 and not _admin_pass:
        app_log.warning("ADMIN_PASSWORD not set in .env — complete setup via /setup")

    # Auto-mark setup done for existing installs that already have an admin
    if admin_count > 0:
        cursor.execute("UPDATE company_settings SET setup_done=1 WHERE setup_done=0")
        db.commit()


# assign_leave_balances_for_employee moved to utils/leave_utils.py


def init_master_db():
    """Create the att_master tenant-registry schema and its tenants table if
    they don't exist. Postgres has no mid-connection database switch, so this
    is a schema within the shared database now, not a separate physical
    database the way MySQL's att_master was."""
    try:
        # Schema must exist before get_master_db() can SET search_path to it,
        # so this first connection stays on the default (public) schema —
        # get_db_connection() now always resets search_path explicitly on
        # every borrow, so it's safe to use here without leaking att_master
        # onto whichever connection the pool hands out next.
        db = get_db_connection()
        cur = db.cursor()
        cur.execute('CREATE SCHEMA IF NOT EXISTS att_master')
        db.commit()
        cur.close()
        db.close()

        from database import get_master_db
        db = get_master_db()
        cur = db.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tenants (
                id SERIAL PRIMARY KEY,
                company_name VARCHAR(200) NOT NULL,
                subdomain VARCHAR(100) UNIQUE NOT NULL,
                db_name VARCHAR(100) UNIQUE NOT NULL,
                admin_email VARCHAR(200) DEFAULT NULL,
                plan VARCHAR(50) DEFAULT 'starter',
                payment_option VARCHAR(20) DEFAULT 'online',
                status VARCHAR(20) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Pre-existing masters created before payment_option existed --
        # CREATE TABLE IF NOT EXISTS above is a no-op against them.
        cur.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS payment_option VARCHAR(20) DEFAULT 'online'")
        # Platform-operator identity (blueprints/platform_admin.py) --
        # lives in att_master, not any tenant schema, since tenant
        # admin_users rows only exist inside their own schema and this
        # identity must not be tied to one. No totp_secret/totp_enabled
        # columns: login MFA is a plain emailed one-time code (session-held,
        # like blueprints/auth.py's _start_login_mfa), not enrolled TOTP --
        # reusing utils/totp.py's enrollment helpers here would silently
        # read/write the wrong schema's admin_users table anyway, since
        # /super_admin/* deliberately has no resolved g.tenant_db.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS platform_admins (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                email VARCHAR(200) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Razorpay orders for the paid public /create_org signup flow (see
        # blueprints/billing.py, utils/razorpay_utils.py). Lives here, not
        # in a tenant schema, because the order is created and paid BEFORE
        # the tenant schema exists -- provisioning only happens once
        # verify_payment confirms the signature. No password/credential
        # field: the provisioned admin account gets a random password
        # (never stored/emailed) and the customer sets their own via the
        # same reset-token link blueprints/auth.py's admin_forgot_password
        # already uses.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS payment_orders (
                id SERIAL PRIMARY KEY,
                razorpay_order_id VARCHAR(100) UNIQUE NOT NULL,
                razorpay_payment_id VARCHAR(100) DEFAULT NULL,
                plan VARCHAR(50) NOT NULL,
                employee_count INT NOT NULL,
                amount_paise INT NOT NULL,
                company_name VARCHAR(200) NOT NULL,
                subdomain VARCHAR(100) NOT NULL,
                admin_username VARCHAR(100) NOT NULL,
                admin_email VARCHAR(200) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'created',
                tenant_id INT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                paid_at TIMESTAMP DEFAULT NULL
            )
        """)
        # Lightweight traffic counter for the public marketing pages
        # (landing page, get-started, create_org) -- one row per
        # (path, day), incremented via ON CONFLICT below rather than one
        # row per visit, so this stays cheap regardless of traffic volume.
        # No cookies/fingerprinting/IP storage -- just a count.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS page_views (
                id SERIAL PRIMARY KEY,
                path VARCHAR(255) NOT NULL,
                view_date DATE NOT NULL,
                count INT NOT NULL DEFAULT 0,
                UNIQUE(path, view_date)
            )
        """)
        # "Request info" / contact-form submissions from the public landing
        # page (templates/landing.html) -- visitors not ready to
        # self-register yet, surfaced to the Platform Admin dashboard for
        # manual follow-up.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id SERIAL PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                email VARCHAR(200) NOT NULL,
                company_name VARCHAR(200) DEFAULT NULL,
                message TEXT DEFAULT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Singleton row (id=1) holding the platform operator's own monthly
        # running costs -- there's no API that can discover real AWS/
        # maintenance spend automatically, so these are admin-entered and
        # compared against MRR to drive the Platform Admin dashboard's
        # Profit & Loss bar and pricing-adjustment suggestion.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS platform_costs (
                id SMALLINT PRIMARY KEY DEFAULT 1,
                monthly_aws_paise INT NOT NULL DEFAULT 0,
                monthly_maintenance_paise INT NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CHECK (id = 1)
            )
        """)
        cur.execute("INSERT INTO platform_costs (id) VALUES (1) ON CONFLICT (id) DO NOTHING")
        db.commit()
        cur.close()
        db.close()
    except Exception as _e:
        app_log.warning("init_master_db failed (non-fatal for single-tenant mode): %s", _e)


def init_tenant_db(schema_name: str):
    """Initialize schema in a freshly created tenant schema."""
    from flask import g as _g
    _g.tenant_db = schema_name
    init_db()


# ---------------- NOTIFICATION HELPER ----------------
# (Consolidated onto utils/helpers.py — see import block above.)

# ---------------- ATTENDANCE HELPERS ----------------
# (Consolidated onto utils/attendance_utils.py — see import block above.
# Became a safe mechanical merge only after the cfg.SHIFT_START migration
# above: before that, this file's copies used bare SHIFT_START/etc. globals
# while utils/attendance_utils.py's copies already used cfg.SHIFT_START —
# genuinely different behavior under a stale-cache scenario, not just
# duplicated source. Now both reference the same cfg module state, so
# there's nothing left to diverge.)

# ---------------- EMAIL HELPERS ----------------
# (Consolidated onto utils/email_utils.py — see the import block above.)

# build_salary_slip_html consolidated onto utils/salary_utils.py
# compute_salary_entry consolidated onto utils/salary_utils.py


# ---------------- ERROR HANDLERS ----------------
import traceback as _traceback

# _error_page consolidated onto utils/helpers.py — that copy rendered a
# template (templates/error.html) that doesn't exist anywhere in this
# project; every call would have raised TemplateNotFound. Replaced with
# this file's working implementation instead of fixing the missing
# template, since this is what every real error page has actually used.

# ---------------- ERROR ALERTING (malfunction detection) ----------------
# The catch-all exception handler below tells users "the team has been
# notified" — this is what actually makes that true. Emails admins on
# unhandled errors, deduped by error signature so one hot failing endpoint
# can't flood inboxes or the email_queue table.
_error_alert_cache = {}
_error_alert_lock = threading.Lock()
_ERROR_ALERT_COOLDOWN = 900  # 15 min — same error signature won't re-alert sooner


def _alert_on_error(tb_text, context=""):
    """Best-effort: any failure here is swallowed so alerting can never
    mask or crash on top of the original error being reported."""
    try:
        # Dedup key = exception type + the line that actually raised it, not
        # the full traceback (which varies request-to-request — different
        # IDs, line numbers in called code, etc. would defeat deduping).
        last_line = tb_text.strip().splitlines()[-1] if tb_text.strip() else "unknown"
        sig = hashlib.sha256(last_line.encode()).hexdigest()[:16]
        now = time.time()
        with _error_alert_lock:
            last_sent = _error_alert_cache.get(sig)
            if last_sent and now - last_sent < _ERROR_ALERT_COOLDOWN:
                return
            _error_alert_cache[sig] = now
            if len(_error_alert_cache) > 500:  # cap unbounded growth
                _error_alert_cache.clear()

        cfg = get_email_config()
        if not cfg:
            return
        admins = get_admin_emails()
        if not admins:
            return

        body = (
            "<pre style='white-space:pre-wrap;font-family:monospace;font-size:13px'>"
            f"Time: {datetime.datetime.now().isoformat()}\n"
            f"Route: {_html.escape(context or 'unknown')}\n"
            f"Method: {_html.escape(request.method if request else 'n/a')}\n"
            f"Remote IP: {_html.escape(request.remote_addr or '') if request else 'n/a'}\n\n"
            f"{_html.escape(tb_text)}</pre>"
        )
        subject = f"⚠️ Application error — {context or 'unknown route'}"
        for admin_email in admins:
            send_email_async(admin_email, subject, body, cfg)
    except Exception as _alert_err:
        app_log.error("Failed to send error alert email: %s", _alert_err)


@app.errorhandler(429)
def rate_limit_exceeded(e):
    """Flask-Limiter raises this (a werkzeug HTTPException) whenever any
    @limiter.limit(...) threshold is crossed. Distinct from _check_login_lockout's
    DB-backed account lockout (utils/auth.py) — this is the generic per-route
    rate ceiling. Logs every breach (feeds the same auto-ban counter WAF
    blocks use — see utils/waf.py) instead of letting it pass through as a
    silent, unlogged 429."""
    waf.record_breach_and_maybe_ban(request.remote_addr, "Repeated rate-limit breaches")
    log_security_event("ratelimit.exceeded", f"Rate limit exceeded: {getattr(e, 'description', '')}",
                       level="WARNING")
    is_ajax = (
        request.path.startswith("/api/")
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.accept_mimetypes.best == "application/json"
    )
    if is_ajax:
        return jsonify({"ok": False, "msg": "Too many requests. Please slow down and try again shortly."}), 429
    return _error_page(429, "⏳", "Too Many Requests",
                       "You've made too many requests in a short period.",
                       "Please wait a moment before trying again.")


@app.errorhandler(404)
def not_found(e):
    return _error_page(404, "🔍", "Page Not Found",
                       "The page you're looking for doesn't exist or has been moved.",
                       "Check the URL or use one of the links below to get back on track.")


@app.errorhandler(403)
def forbidden(e):
    return _error_page(403, "🔒", "Access Denied",
                       "You don't have permission to access this page.",
                       "Please log in with the right account or contact your administrator.")


@app.errorhandler(500)
def internal_error(e):
    tb = _traceback.format_exc()
    app_log.error("500 error: %s", tb.replace('\n', '\\n'))
    _alert_on_error(tb, context=request.path if request else "")
    return _error_page(500, "⚙️", "Internal Server Error",
                       "Something went wrong on our end. The error has been logged.",
                       "Please try again in a moment or contact your administrator.")


@app.errorhandler(Exception)
def unhandled_exception(e):
    if isinstance(e, HTTPException):
        return _error_page(e.code, "⚠️", e.name,
                           "The page you requested could not be processed.",
                           "Use the buttons below to navigate back.")
    tb = _traceback.format_exc()
    app_log.error("Unhandled exception: %s", tb.replace('\n', '\\n'))
    _alert_on_error(tb, context=request.path if request else "")
    return _error_page(500, "⚙️", "Internal Server Error",
                       "An unexpected error occurred. The team has been notified.",
                       "Please try again or contact your administrator.")

# ---------------- HOME ----------------
# home migrated to blueprints/core.py

# ---------------- ADMIN LOGIN ----------------
# setup_wizard migrated to blueprints/auth.py


# admin_login migrated to blueprints/auth.py

# ---------------- LOGOUT ----------------
# logout migrated to blueprints/auth.py

# ---------------- SESSION KILL-SWITCH: SSE PUSH ----------------
# session_risk_stream migrated to blueprints/core.py

# ---------------- SESSION KILL-SWITCH: LOCKOUT PAGE ----------------
# security_lockout migrated to blueprints/core.py

# ---------------- ADMIN DASHBOARD ----------------
# admin migrated to blueprints/admin_views.py

# ---------------- LIVE DASHBOARD API ----------------
# dashboard_live migrated to blueprints/admin_views.py

# ---------------- CHART DATA API ----------------
# attendance_chart_data migrated to blueprints/admin_views.py


# ---------------- TODAY FILTERED VIEWS ----------------
# _today_pending_counts migrated to blueprints/attendance.py

# today_present migrated to blueprints/attendance.py

# today_absent migrated to blueprints/attendance.py

# today_late migrated to blueprints/attendance.py

# ---------------- ADMIN ACTIONS ----------------
# admin_action migrated to blueprints/employees.py

# ---------------- SETTINGS (unified) ----------------
# settings_page migrated to blueprints/admin_views.py

# ---------------- SAVE DEFAULT ONBOARDING TEMPLATE ----------------
# save_default_onboarding_template migrated to blueprints/admin_views.py

# ---------------- SAVE SALARY RULES ----------------
# save_salary_rules migrated to blueprints/admin_views.py

# ---------------- TOGGLE AUTH METHOD ----------------
# _TOGGLE_COLUMN_MAP / _TOGGLE_LABEL_MAP moved to blueprints/admin_views.py

# toggle_auth_method migrated to blueprints/admin_views.py

# toggle_fingerprint migrated to blueprints/admin_views.py

# ---------------- SAVE COMPANY CODE ----------------
# save_company_code migrated to blueprints/admin_views.py

# ---------------- SAVE COMPANY INFO ----------------
# save_company_info migrated to blueprints/admin_views.py

# ---------------- TOGGLE FEATURE (AJAX) ----------------
# toggle_feature migrated to blueprints/admin_views.py

# ---------------- SAVE GEO RADIUS ----------------
# save_geo_radius migrated to blueprints/admin_views.py

# ---------------- SAVE SECURITY SETTINGS ----------------
# save_security_settings migrated to blueprints/admin_views.py


# ---------------- COMPANIES ----------------

# switch_company migrated to blueprints/admin_views.py

# clear_company migrated to blueprints/admin_views.py

# set_company_pin migrated to blueprints/admin_views.py

# view_companies migrated to blueprints/admin_views.py


# add_company migrated to blueprints/admin_views.py


# edit_company migrated to blueprints/admin_views.py


# delete_company migrated to blueprints/admin_views.py


# ---------------- ANNOUNCEMENTS ----------------
# announcements_admin migrated to blueprints/admin_views.py

# ---------------- INDIAN PUBLIC HOLIDAYS ----------------
# get_indian_holidays moved to utils/leave_utils.py

# ---------------- VIEW HOLIDAYS ----------------
# view_holidays migrated to blueprints/leave.py

# add_holiday migrated to blueprints/leave.py

# delete_employee migrated to blueprints/employees.py


# edit_employee_page migrated to blueprints/employees.py


# employee_profile migrated to blueprints/employees.py


# edit_employee migrated to blueprints/employees.py


# api_employee_info migrated to blueprints/employees.py


# view_employees migrated to blueprints/employees.py


# ---------------- EMPLOYEE DETAIL PAGE ----------------
# employee_detail migrated to blueprints/employees.py


# ---------------- ADD EMPLOYEE (from employees page) ----------------
# add_employee_page migrated to blueprints/employees.py


# ---------------- UPDATE EMPLOYEE PHOTO ----------------
# update_employee_photo migrated to blueprints/employees.py


# ---------------- REGENERATE QR ----------------
# regenerate_qr migrated to blueprints/employees.py


# ---------------- LEAVE TYPES ADMIN ----------------
# admin_leave_types migrated to blueprints/leave.py


# change_admin_password migrated to blueprints/auth.py


# admin_set_recovery_email migrated to blueprints/auth.py


# admin_forgot_password migrated to blueprints/auth.py


# admin_reset_password migrated to blueprints/auth.py


# employee_forgot_password migrated to blueprints/auth.py


# employee_reset_password migrated to blueprints/auth.py


# view_qrcodes migrated to blueprints/employees.py


# serve_dataset migrated to blueprints/employees.py


# my_photo migrated to blueprints/employees.py


# view_photos migrated to blueprints/employees.py


# update_photo migrated to blueprints/employees.py

# ---------------- SHIFTS (redirect to settings) ----------------
# shifts migrated to blueprints/attendance.py

# add_shift migrated to blueprints/attendance.py

# delete_shift_form migrated to blueprints/attendance.py

# delete_shift migrated to blueprints/attendance.py

# edit_shift migrated to blueprints/attendance.py

# bulk_assign_shift migrated to blueprints/attendance.py

# update_default_shift migrated to blueprints/attendance.py

# assign_shift migrated to blueprints/attendance.py


# ──────────────────────── SHIFT SWAP REQUESTS ────────────────────────

# submit_shift_swap migrated to blueprints/attendance.py


# respond_shift_swap migrated to blueprints/attendance.py


# admin_shift_swap migrated to blueprints/attendance.py


# admin_shift_swaps migrated to blueprints/attendance.py


# import_indian_holidays migrated to blueprints/leave.py

# delete_holiday migrated to blueprints/leave.py

# ---------------- AUTO GENERATE EMPLOYEE ID ----------------
# generate_emp_id migrated to blueprints/employees.py


# ---------------- BREAK CONFIG ----------------
# api_breaks migrated to blueprints/attendance.py

# view_break_config migrated to blueprints/attendance.py

# add_break migrated to blueprints/attendance.py

# update_break migrated to blueprints/attendance.py

# delete_break migrated to blueprints/attendance.py

# ---------------- VIEW SALARY CONFIG ----------------
# view_salary migrated to blueprints/payroll.py
# update_salary migrated to blueprints/payroll.py
# monthly_report migrated to blueprints/attendance.py

# ---------------- EMPLOYEE ATTENDANCE DETAIL ----------------
# employee_attendance_detail migrated to blueprints/attendance.py

# ---------------- MANUAL ATTENDANCE CORRECTION ----------------
# correct_attendance migrated to blueprints/attendance.py


# ---------------- BULK MARK ATTENDANCE ----------------
# bulk_mark_attendance migrated to blueprints/attendance.py


# ---------------- MONTHLY REPORT EXCEL EXPORT ----------------
# monthly_report_export migrated to blueprints/attendance.py

# ---------------- ABSENTEE REPORT EMAIL ----------------
# send_absentee_report migrated to blueprints/attendance.py

# ---------------- SALARY REPORT ----------------
# salary_report migrated to blueprints/payroll.py
# salary_report_export migrated to blueprints/payroll.py
# email_config migrated to blueprints/payroll.py
# send_salary_email migrated to blueprints/payroll.py
# send_all_salary_emails migrated to blueprints/payroll.py
# lock_payroll migrated to blueprints/payroll.py
# unlock_payroll migrated to blueprints/payroll.py
# test_email migrated to blueprints/admin_views.py

# ---------------- LOCATION ----------------
# location migrated to blueprints/attendance.py

# ---------------- DISTANCE CHECK ----------------
# is_within_range moved to utils/attendance_utils.py

# ---------------- ATTENDANCE (LOGIN + LOGOUT) ----------------
# attendance migrated to blueprints/attendance.py

# ================================================================
#  EMPLOYEE PORTAL
# ================================================================

# employee_login migrated to blueprints/auth.py


# employee_logout migrated to blueprints/auth.py


# change_password migrated to blueprints/auth.py


# force_change_pin migrated to blueprints/auth.py


# update_my_profile migrated to blueprints/employee_portal.py


# update_my_bank_details migrated to blueprints/employee_portal.py


# add_experience migrated to blueprints/employee_portal.py


# delete_experience migrated to blueprints/employee_portal.py


# add_education_entry migrated to blueprints/employee_portal.py


# delete_education_entry migrated to blueprints/employee_portal.py


# update_my_photo migrated to blueprints/employee_portal.py


# my_qr migrated to blueprints/employee_portal.py


# my_id_card migrated to blueprints/employee_portal.py


# _build_id_card_buf migrated to blueprints/employees.py


# admin_id_card migrated to blueprints/employees.py


# admin_view_id_card migrated to blueprints/employees.py


# employee_portal migrated to blueprints/employee_portal.py


# my_payslip_summary migrated to blueprints/payroll.py
# my_attendance_pdf migrated to blueprints/payroll.py
# request_leave migrated to blueprints/leave.py


# leave_balance migrated to blueprints/leave.py


# set_leave_balance migrated to blueprints/leave.py


# ─────────────────────────── PERFORMANCE MANAGEMENT ───────────────────────────
# RATING_LABELS moved to blueprints/performance.py

# performance migrated to blueprints/performance.py


# performance_review migrated to blueprints/performance.py


# performance_save_review migrated to blueprints/performance.py


# performance_add_kpi migrated to blueprints/performance.py


# performance_rate_kpi migrated to blueprints/performance.py


# performance_delete_kpi migrated to blueprints/performance.py


# my_performance migrated to blueprints/performance.py


# performance_employee_comment migrated to blueprints/performance.py


# performance_export migrated to blueprints/performance.py


# performance_import migrated to blueprints/performance.py


# apply_hike migrated to blueprints/payroll.py
# award_performance_bonus migrated to blueprints/payroll.py
# save_hike_config migrated to blueprints/payroll.py
# leave_requests_redirect migrated to blueprints/leave.py
# view_holidays_redirect removed — was a dead, unreferenced duplicate of
# /view_holidays that had been silently shadowed by the real view_holidays()
# (now blueprints/leave.py) since before this migration; moving the real
# route into a blueprint flipped Werkzeug's rule tie-break order and made
# this stub reachable, so it's deleted rather than preserved.
# leave_holidays migrated to blueprints/leave.py


# leave_action migrated to blueprints/leave.py


# leave_calendar migrated to blueprints/leave.py


# request_resignation migrated to blueprints/leave.py


# resignation_requests_view migrated to blueprints/leave.py


# resignation_action migrated to blueprints/leave.py


# bulk_leave_action migrated to blueprints/leave.py


# ================================================================
#  TICKETS  (web)
# ================================================================

# raise_ticket migrated to blueprints/tickets.py


# tickets_view migrated to blueprints/tickets.py


# ticket_action migrated to blueprints/tickets.py


# ================================================================
#  REST API  (used by the Flutter mobile app)
# ================================================================

# api_login migrated to blueprints/core.py


# api_logout migrated to blueprints/core.py


# api_dashboard migrated to blueprints/core.py


# api_employees migrated to blueprints/employees.py


# api_register_employee migrated to blueprints/employees.py


# api_employee_detail migrated to blueprints/employees.py


# api_edit_employee migrated to blueprints/employees.py


# api_delete_employee migrated to blueprints/employees.py


# api_holidays migrated to blueprints/leave.py


# api_add_holiday migrated to blueprints/core.py


# api_salary_config_get migrated to blueprints/payroll.py
# api_salary_config_post migrated to blueprints/payroll.py
# api_monthly_report migrated to blueprints/payroll.py
# api_salary_report migrated to blueprints/payroll.py
# api_get_email_config migrated to blueprints/payroll.py
# api_save_email_config migrated to blueprints/payroll.py
# api_send_salary_email migrated to blueprints/payroll.py
# api_checkin migrated to blueprints/attendance.py


# ---------------- API: LEAVE REQUESTS ----------------

# api_leave_requests migrated to blueprints/leave.py


# api_leave_action migrated to blueprints/leave.py


# ---------------- API: RESIGNATION REQUESTS ----------------

# api_resignation_requests migrated to blueprints/leave.py


# api_resignation_action migrated to blueprints/leave.py


# api_employee_login migrated to blueprints/core.py


# api_employee_logout migrated to blueprints/core.py


# api_employee_change_password migrated to blueprints/employee_portal.py


# _fmt_t moved to blueprints/employee_portal.py

# api_employee_portal migrated to blueprints/employee_portal.py

# api_employee_checkin migrated to blueprints/employee_portal.py


# api_employee_sync_punches migrated to blueprints/employee_portal.py


# api_employee_auth_config migrated to blueprints/employee_portal.py


# WebAuthn/mobile-biometric helper functions moved to utils/webauthn_utils.py
# _enroll_fingerprint_from_form moved to utils/webauthn_utils.py — its only
# two callers (admin_action, add_employee_page) migrated to blueprints/employees.py.
# webauthn_status migrated to blueprints/auth.py


# webauthn_registration_options migrated to blueprints/auth.py


# webauthn_authentication_options migrated to blueprints/auth.py


# webauthn_verify_challenge migrated to blueprints/auth.py


# webauthn_register migrated to blueprints/auth.py


# webauthn_unenroll migrated to blueprints/auth.py
# webauthn_register_kiosk migrated to blueprints/auth.py (was missing from
# the original auth.py migration manifest — found via a pyflakes undefined-
# name sweep after the fact; it referenced _webauthn_available and
# _wa_verify_and_store_registration, which app.py no longer imports).
# admin_reset_employee_fingerprint migrated to blueprints/auth.py
# get_employee_webauthn_credential migrated to blueprints/auth.py


# api_mobile_biometric_nonce migrated to blueprints/auth.py


# api_mobile_biometric_attest migrated to blueprints/auth.py


# api_employee_qr_face_checkin migrated to blueprints/employee_portal.py


# api_employee_leave_request migrated to blueprints/leave.py


# api_employee_resign migrated to blueprints/leave.py


# ---------------- API: TICKETS (employee) ----------------

# api_employee_tickets migrated to blueprints/tickets.py


# api_employee_raise_ticket migrated to blueprints/tickets.py


# api_employee_salary migrated to blueprints/employee_portal.py


# ---------------- API: EMPLOYEE — ATTENDANCE HISTORY ----------------

# api_employee_attendance migrated to blueprints/employee_portal.py


# ---------------- API: EMPLOYEE — LEAVE HISTORY + BALANCE ----------------

# api_employee_leaves migrated to blueprints/leave.py


# ---------------- API: EMPLOYEE — CANCEL LEAVE ----------------

# api_employee_cancel_leave migrated to blueprints/leave.py


# ---------------- WEB: EMPLOYEE — CANCEL LEAVE ----------------

# cancel_leave_web migrated to blueprints/leave.py


# ---------------- API: EMPLOYEE — REQUEST OVERTIME ----------------

# api_employee_request_overtime migrated to blueprints/leave.py


# api_employee_my_overtime migrated to blueprints/leave.py


# ---------------- API: ADMIN — DOCUMENT EXPIRY ALERTS ----------------

# api_expiring_documents migrated to blueprints/admin_views.py


# ---------------- API: EMPLOYEE — HOLIDAYS ----------------

# api_employee_holidays migrated to blueprints/leave.py


# ---------------- API: EMPLOYEE — PROFILE ----------------

# api_employee_profile migrated to blueprints/employee_portal.py


# api_employee_upload_photo migrated to blueprints/employee_portal.py


# ---------------- API: TICKETS (admin) ----------------

# api_tickets migrated to blueprints/tickets.py


# api_ticket_action migrated to blueprints/tickets.py


# ---------------- PAY SLIPS ----------------
# view_payslip migrated to blueprints/payroll.py
# download_payslip migrated to blueprints/payroll.py
# admin_payslips migrated to blueprints/payroll.py
# payroll_settings migrated to blueprints/payroll.py
# api_shifts_get migrated to blueprints/attendance.py


# api_shifts_create migrated to blueprints/attendance.py


# api_shifts_delete migrated to blueprints/attendance.py


# api_shifts_assign migrated to blueprints/attendance.py


# ================================================================
#  FEATURE 1: ANALYTICS
# ================================================================

# analytics migrated to blueprints/admin_views.py


# ================================================================
#  FEATURE 2: DOCUMENT MANAGEMENT
# ================================================================

# _DOC_ALLOWED_EXT moved to blueprints/documents.py

# _doc_admin_ctx migrated to blueprints/documents.py


# documents migrated to blueprints/documents.py


# upload_document migrated to blueprints/documents.py


# delete_document migrated to blueprints/documents.py


# download_document migrated to blueprints/documents.py


# upload_my_document migrated to blueprints/documents.py


# delete_my_document migrated to blueprints/documents.py


# ================================================================
#  FEATURE 3: OVERTIME TRACKING
# ================================================================

# overtime migrated to blueprints/leave.py


# overtime_action migrated to blueprints/leave.py


# ─────────────────────────── COMP-OFF MANAGEMENT ───────────────────────────

# compoff migrated to blueprints/leave.py

# compoff_old migrated to blueprints/leave.py


# compoff_settings migrated to blueprints/leave.py


# my_compoff migrated to blueprints/leave.py


# Notification routes migrated to blueprints/notifications.py


# ── Tenant Provisioning ──────────────────────────────────────────────────────

# _SUBDOMAIN_RE moved to blueprints/org.py
# Signup is open by default (Turnstile-protected, not gated behind a
# shared secret) -- see blueprints/org.py and utils/plan_limits.py.

# create_org_page migrated to blueprints/org.py


# create_org migrated to blueprints/org.py


# ─────────────────────────────────────────
#  ONBOARDING WORKFLOW
# ─────────────────────────────────────────

# onboarding migrated to blueprints/onboarding.py

# onboarding_template_save migrated to blueprints/onboarding.py

# bulk_assign_onboarding migrated to blueprints/onboarding.py


# export_onboarding_csv migrated to blueprints/onboarding.py


# onboarding_template_duplicate migrated to blueprints/onboarding.py


# onboarding_template_delete migrated to blueprints/onboarding.py

# onboarding_task_save migrated to blueprints/onboarding.py

# onboarding_task_delete migrated to blueprints/onboarding.py

# onboarding_template_detail migrated to blueprints/onboarding.py

# onboarding_assign migrated to blueprints/onboarding.py

# onboarding_detail migrated to blueprints/onboarding.py

# onboarding_admin_task_update migrated to blueprints/onboarding.py

# onboarding_close migrated to blueprints/onboarding.py

# ── OFFER LETTER ──────────────────────────────────────────────────────────────
# offer_letter migrated to blueprints/onboarding.py

# offer_letter_save migrated to blueprints/onboarding.py

# offer_letter_view migrated to blueprints/onboarding.py

# _generate_offer_letter_pdf migrated to blueprints/onboarding.py


# offer_letter_send migrated to blueprints/onboarding.py


# offer_letter_pdf migrated to blueprints/onboarding.py


# offer_letter_respond migrated to blueprints/onboarding.py

# Employee portal onboarding
# my_onboarding migrated to blueprints/onboarding.py

# my_onboarding_task_done migrated to blueprints/onboarding.py


# ---------------- ADMIN TOOLS (Org Chart + Audit Logs combined) ----------------
# org_chart_page migrated to blueprints/admin_views.py

# audit_logs_redirect migrated to blueprints/admin_views.py

# admin_tools migrated to blueprints/admin_views.py


# old standalone routes kept for API


# api_org_chart_data migrated to blueprints/admin_views.py


# ── /api/v1/ aliases ──────────────────────────────────────────────────────────
# Register every /api/<path> route also under /api/v1/<path>.  Existing mobile
# clients keep using /api/ with no changes; new integrations can start on v1.
# The view functions (and their decorators: @limiter, @api_required, etc.) are
# shared, so rate-limits and auth are identical on both prefixes.
def _register_api_v1_aliases():
    _seen = set()
    for _rule in list(app.url_map.iter_rules()):
        if not _rule.rule.startswith("/api/") or _rule.rule.startswith("/api/v"):
            continue
        _v1_rule = "/api/v1" + _rule.rule[4:]
        _vf = app.view_functions.get(_rule.endpoint)
        if _vf is None:
            continue
        _ep_v1 = "v1_" + _rule.endpoint
        if _ep_v1 in _seen:
            continue
        _seen.add(_ep_v1)
        app.add_url_rule(
            _v1_rule,
            endpoint=_ep_v1,
            view_func=_vf,
            methods=_rule.methods,
        )


# ── Self-register blueprints when app.py is the entrypoint ────────────────────
# wsgi.py and tests/conftest.py both register every blueprint on the shared
# `app` instance BEFORE importing this module (documented in conftest.py) —
# in that case core.home is already present and this is a no-op. Only a bare
# `python app.py` reaches this branch, so it's the one path where app.py must
# register the blueprints itself before _register_api_v1_aliases() runs,
# otherwise every route (including "/") would 404 and v1 aliases would be
# built from an empty url_map.
if "core.home" not in app.view_functions:
    from blueprints.health import health_bp
    from blueprints.notifications import notifications_bp
    from blueprints.payroll import payroll_bp
    from blueprints.leave import leave_bp
    from blueprints.admin_views import admin_views_bp
    from blueprints.auth import auth_bp
    from blueprints.employees import employees_bp
    from blueprints.attendance import attendance_bp
    from blueprints.tickets import tickets_bp
    from blueprints.performance import performance_bp
    from blueprints.documents import documents_bp
    from blueprints.org import org_bp
    from blueprints.onboarding import onboarding_bp
    from blueprints.employee_portal import employee_portal_bp
    from blueprints.core import core_bp
    from blueprints.ai_hrms import ai_hrms_bp
    from blueprints.email_blast import email_blast_bp
    from blueprints.daily_report import daily_report_bp
    from blueprints.billing import billing_bp
    from blueprints.platform_admin import platform_admin_bp
    from blueprints.secops import secops_bp
    for _bp in (health_bp, notifications_bp, payroll_bp, leave_bp, admin_views_bp,
                auth_bp, employees_bp, attendance_bp, tickets_bp, performance_bp,
                documents_bp, org_bp, onboarding_bp, employee_portal_bp, core_bp,
                ai_hrms_bp, email_blast_bp, daily_report_bp, billing_bp, platform_admin_bp,
                secops_bp):
        app.register_blueprint(_bp)


# ── Billing context (flat per-employee rate) ─────────────────────────────────
@app.context_processor
def inject_billing_context():
    try:
        from flask import g as _g
        from utils.plan_limits import get_tenant_employee_count, calculate_price, format_price_inr, PER_EMPLOYEE_PAISE
        employee_count = get_tenant_employee_count(_g.tenant_db)
        monthly_bill_paise = calculate_price(employee_count)
        return dict(
            employee_count=employee_count,
            per_employee_paise=PER_EMPLOYEE_PAISE,
            monthly_bill_display=format_price_inr(monthly_bill_paise),
        )
    except Exception:
        return dict(employee_count=0, per_employee_paise=9900, monthly_bill_display="₹0")




_register_api_v1_aliases()

# ---------------- RUN ----------------
if __name__ == "__main__":
    init_master_db()
    init_db()
    cfg.load_default_shift()
    cfg.load_salary_rules()
    # Only started here — when app.py is run directly (`python app.py`,
    # local dev). wsgi.py (the real production entrypoint) already starts
    # this exact worker itself before importing app.py; starting it again
    # unconditionally at module level (the old behavior) meant production
    # ran two of these per process, racing on the same email_queue table
    # with no row locking — a live duplicate-delivery bug, not a
    # hypothetical one.
    threading.Thread(target=_email_queue_worker, daemon=True, name="email-queue-worker").start()
    import os as _os
    from werkzeug.serving import WSGIRequestHandler

    class _QuietRequestHandler(WSGIRequestHandler):
        """Werkzeug's dev server writes its own 'Server: Werkzeug/x.x Python/x.x'
        header straight onto the socket (via BaseHTTPRequestHandler.send_response)
        regardless of what _security_headers already set on the response object —
        so the real fix has to happen here, not by adding another header.
        Overriding version_string() replaces that raw value instead of leaking
        the exact Werkzeug/Python versions (only relevant to `python app.py` dev/
        kiosk runs; the gunicorn path in wsgi.py never uses this handler)."""

        def version_string(self):
            return "AttendanceApp"

    _cert = _os.environ.get("SSL_CERT_PATH") or _os.path.join(_os.path.dirname(__file__), "cert.pem")
    _key = _os.environ.get("SSL_KEY_PATH") or _os.path.join(_os.path.dirname(__file__), "key.pem")
    # threaded=True: /api/session/risk-stream (blueprints/core.py) holds an
    # SSE connection open for ~20s, and Werkzeug's dev server is single-
    # threaded by default -- without this, one open stream blocks every
    # other request until it closes.
    if _os.path.exists(_cert) and _os.path.exists(_key):
        print("🔒  SSL cert found — starting on https://0.0.0.0:5000")
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True,  # nosec B104
                ssl_context=(_cert, _key), request_handler=_QuietRequestHandler)
    else:
        print("⚠   No cert.pem / key.pem — starting on http://0.0.0.0:5000")
        print("    Fingerprint / WebAuthn requires HTTPS. Run: python generate_cert.py")
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True,  # nosec B104
                request_handler=_QuietRequestHandler)
