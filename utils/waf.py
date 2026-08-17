# -*- coding: utf-8 -*-
"""Native, signature-based Web Application Firewall.

Complements the structural defenses already in place elsewhere (parameterized
SQL everywhere a query is built, CSP + html.escape for XSS, secure_filename +
magic-byte checks for uploads -- see utils/helpers.py) with an interception
layer that inspects every incoming request for known attack *shapes* and
rejects them before a route handler ever runs. Registered as an
app.before_request hook in app.py, right after _enforce_ip_ban.

Patterns are deliberately multi-token / structural rather than single
characters or words, so a legitimate apostrophe in a name ("O'Brien"), a
hyphenated address, or the word "select" in a dropdown label never trips a
false positive -- each pattern requires the *shape* of an actual injection
attempt (a keyword next to the syntax that would make it executable).
"""
import re
import time
import datetime
import threading
from collections import defaultdict, deque

from extensions import log_security_event, redis_client

_SQLI_PATTERNS = [
    # UNION-based exfiltration
    re.compile(r"\bunion\b[^;]{0,40}\bselect\b", re.IGNORECASE),
    # Stacked/terminated statements
    re.compile(r";\s*(drop|delete|update|insert|exec|alter|truncate)\b", re.IGNORECASE),
    # Numeric tautologies: OR 1=1, AND 2=2, etc.
    re.compile(r"\bor\b\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+['\"]?", re.IGNORECASE),
    re.compile(r"\band\b\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+['\"]?", re.IGNORECASE),
    # String tautologies: OR 'a'='a', OR 'x'='x, OR ''='', etc.
    re.compile(r"\bor\b\s+['\"]([^'\"]{0,20})['\"]\s*=\s*['\"]\1['\"]?", re.IGNORECASE),
    re.compile(r"\bor\b\s+'[^']*'\s*=\s*'[^']*'", re.IGNORECASE),
    re.compile(r"\bor\b\s+\"[^\"]*\"\s*=\s*\"[^\"]*\"", re.IGNORECASE),
    # Classic login-bypass comment terminator: admin'-- or '-- or 1=1--
    re.compile(r"['\"]\s*--"),
    re.compile(r"--\s"),
    re.compile(r"/\*.*?\*/", re.DOTALL),
    # OR true/false literals
    re.compile(r"\bor\b\s+(true|false)\b", re.IGNORECASE),
    re.compile(r"\band\b\s+(true|false)\b", re.IGNORECASE),
    # Dangerous proc/functions
    re.compile(r"\bxp_cmdshell\b", re.IGNORECASE),
    re.compile(r"\bexec\s*\(", re.IGNORECASE),
    re.compile(r"\bwaitfor\s+delay\b", re.IGNORECASE),
    # Schema enumeration
    re.compile(r"\bselect\b[^;]{0,60}\bfrom\b[^;]{0,60}\binformation_schema\b", re.IGNORECASE),
    # Hex/char encoding evasion
    re.compile(r"0x[0-9a-fA-F]{4,}"),
    re.compile(r"\bchar\s*\(\s*\d+", re.IGNORECASE),
]

_XSS_PATTERNS = [
    re.compile(r"<script\b", re.IGNORECASE),
    re.compile(r"\bon(?:load|error|click|mouseover|focus|blur|change|submit)\s*=", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"<iframe\b", re.IGNORECASE),
    re.compile(r"<svg\b[^>]*\bonload\b", re.IGNORECASE),
    re.compile(r"data\s*:\s*text/html", re.IGNORECASE),
]

_PATH_TRAVERSAL_PATTERNS = [
    re.compile(r"\.\./"),
    re.compile(r"\.\.\\"),
    re.compile(r"%2e%2e", re.IGNORECASE),
    re.compile(r"%00"),
    re.compile(r"\x00"),
]


def _first_match(patterns, value):
    for pat in patterns:
        m = pat.search(value)
        if m:
            return m.group(0)
    return None


def _sqli_signature(s):
    return _first_match(_SQLI_PATTERNS, s)


def _xss_signature(s):
    return _first_match(_XSS_PATTERNS, s)


def _path_traversal_signature(s):
    return _first_match(_PATH_TRAVERSAL_PATTERNS, s)


_CHECKS = (
    ("waf.sqli_blocked", _sqli_signature),
    ("waf.xss_blocked", _xss_signature),
    ("waf.path_traversal_blocked", _path_traversal_signature),
)


def _inspect_value(field, value):
    """Returns (event_type, field, matched) for the first signature that
    fires against a single string value, or None."""
    if not isinstance(value, str) or not value:
        return None
    for event_type, check in _CHECKS:
        matched = check(value)
        if matched:
            return event_type, field, matched
    return None


def _flatten_json(obj, prefix=""):
    """Yields (field_path, string_value) pairs from an arbitrarily nested
    JSON body -- attack payloads can hide in any nested string field, not
    just top-level ones."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _flatten_json(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _flatten_json(v, f"{prefix}[{i}]")
    elif isinstance(obj, str):
        yield prefix, obj


def inspect_request(request):
    """Scans query string, form fields (not file bodies), JSON body, and
    path segments for known attack signatures. Returns the first
    (event_type, field, matched) found, or None if the request looks clean.
    """
    for key, value in request.args.items():
        hit = _inspect_value(f"args.{key}", value)
        if hit:
            return hit

    if request.form:
        for key, value in request.form.items():
            hit = _inspect_value(f"form.{key}", value)
            if hit:
                return hit

    if request.files:
        for key, file_storage in request.files.items():
            hit = _inspect_value(f"files.{key}.filename", file_storage.filename or "")
            if hit:
                return hit

    if request.is_json:
        body = request.get_json(silent=True)
        if body is not None:
            for field, value in _flatten_json(body):
                hit = _inspect_value(f"json.{field}", value)
                if hit:
                    return hit

    if request.view_args:
        for key, value in request.view_args.items():
            hit = _inspect_value(f"path.{key}", str(value))
            if hit:
                return hit

    return None


# ── Progressive auto-ban on repeated breaches ──────────────────────────────
# Per-worker in-memory counter -- same documented limitation as extensions.py's
# Flask-Limiter storage (no Redis in this stack). Under multiple gunicorn
# workers the effective threshold is BREACH_THRESHOLD * worker_count, which
# is an acceptable trade for a mechanism that needs zero extra infrastructure
# and still closes the loop: a scripted attacker sprays multiple workers at
# random, but every worker independently escalates to the same shared
# banned_ips row (database.py), so the ban itself is not per-worker even
# though the counter that triggers it is.
_BREACH_WINDOW_SECONDS = 600
_BREACH_THRESHOLD = 5
_BAN_MINUTES = 15

_breach_lock = threading.Lock()
_breach_log = defaultdict(deque)  # ip -> deque[timestamp]


def record_breach_and_maybe_ban(ip, reason):
    """Call on every WAF block or rate-limit breach. Once an IP crosses
    _BREACH_THRESHOLD breaches inside _BREACH_WINDOW_SECONDS, inserts a
    temporary ban into banned_ips -- the same table and INSERT shape the SOC
    dashboard's manual ban-ip endpoint uses (blueprints/admin_views.py), so
    the existing _enforce_ip_ban before_request hook (app.py) blocks the IP
    on its very next request with no new blocking mechanism needed.

    Uses Redis (shared across gunicorn workers) when extensions.redis_client
    is configured, falling back to the in-memory per-worker counter
    otherwise -- including if a configured Redis becomes unreachable
    mid-request, so a transient Redis blip degrades the counter rather than
    breaking request handling.
    """
    if not ip:
        return
    if redis_client is not None:
        try:
            _record_breach_redis(ip, reason)
            return
        except Exception as e:
            log_security_event(
                "waf.redis_error", f"Redis breach-counter call failed, using in-memory fallback: {e}",
                level="WARNING", identifier=ip,
            )
    if _record_breach_memory(ip):
        _auto_ban(ip, reason)


def _record_breach_redis(ip, reason):
    """Fixed-window counter (INCR + EXPIRE-if-new) rather than the
    in-memory version's exact rolling window -- a reasonable approximation
    for an anti-abuse threshold, and the same fixed-window approach
    Flask-Limiter's own Redis storage uses."""
    key = f"waf:breach:{ip}"
    count = redis_client.incr(key)
    if count == 1:
        redis_client.expire(key, _BREACH_WINDOW_SECONDS)
    if count < _BREACH_THRESHOLD:
        return
    redis_client.delete(key)
    _auto_ban(ip, reason)


def _record_breach_memory(ip):
    """Returns True once the in-memory rolling-window counter for this IP
    crosses _BREACH_THRESHOLD (and resets it), False otherwise."""
    now = time.time()
    with _breach_lock:
        dq = _breach_log[ip]
        dq.append(now)
        while dq and now - dq[0] > _BREACH_WINDOW_SECONDS:
            dq.popleft()
        if len(dq) < _BREACH_THRESHOLD:
            return False
        dq.clear()
    return True


def _auto_ban(ip, reason):
    from database import get_db_connection
    expires_at = datetime.datetime.now() + datetime.timedelta(minutes=_BAN_MINUTES)
    try:
        db = get_db_connection()
        cursor = db.cursor()
        try:
            cursor.execute(
                "INSERT INTO banned_ips (ip, reason, banned_by, expires_at) VALUES (%s,%s,%s,%s) "
                "ON CONFLICT (ip) DO UPDATE SET reason=EXCLUDED.reason, banned_by=EXCLUDED.banned_by, "
                "banned_at=CURRENT_TIMESTAMP, expires_at=EXCLUDED.expires_at",
                (ip, reason, "system:auto", expires_at),
            )
            db.commit()
        finally:
            cursor.close()
            db.close()
        log_security_event(
            "waf.auto_ban", f"IP auto-banned for {_BAN_MINUTES} minutes after repeated breaches",
            level="ERROR", identifier=ip, reason=reason,
        )
    except Exception as e:
        log_security_event(
            "waf.auto_ban_failed", f"Failed to auto-ban IP after repeated breaches: {e}",
            level="ERROR", identifier=ip,
        )
