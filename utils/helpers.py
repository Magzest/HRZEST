"""Shared utility helpers used across multiple blueprints."""
import os
import re
import datetime
import threading
from contextlib import contextmanager

_SAFE_IDENT_RE = re.compile(r'^[a-z][a-z0-9_]*$')

# Employee IDs are used to build filesystem paths (dataset/<emp_id>.jpg,
# static/qrcodes/<emp_id>.png) before the DB row necessarily exists yet
# (registration), so a DB existence check can't be relied on to reject
# path-traversal characters the way it does for update-in-place routes.
_EMP_ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,32}$')


def validate_emp_id(emp_id: str) -> bool:
    return bool(emp_id) and bool(_EMP_ID_RE.match(emp_id))


from flask import session, request
from database import get_db_connection
from extensions import app_log, log_security_event


def tpath(path: str) -> str:
    """Prefix an absolute-path link/redirect target with the current
    tenant's URL prefix (request.script_root -- "" on marketing/platform-
    admin routes, "/<company-slug>" once the WSGI tenant-prefix wrapper in
    wsgi.py has stripped that slug into SCRIPT_NAME for a resolved tenant
    request). Used in place of bare redirect("/x")/href="/x" everywhere a
    link should stay within the current tenant's path, since this codebase
    builds links as literal absolute-path strings rather than via
    url_for(), which would pick up SCRIPT_NAME automatically.

    Idempotent by design: some inputs (e.g. a path pulled out of the raw
    Referer header in _safe_referrer_redirect, which reflects the real
    browser URL the visitor was on) already carry the tenant prefix, while
    most call sites pass a bare, unprefixed literal like "/admin" -- rather
    than track which is which at every call site, tpath() just checks
    whether the prefix is already there before adding it."""
    if not path.startswith("/"):
        return path
    try:
        prefix = request.script_root
    except RuntimeError:
        return path  # no request context (e.g. called from a script/test)
    if not prefix or path == prefix or path.startswith(prefix + "/"):
        return path
    return prefix + path


def employee_login_url() -> str:
    """Absolute URL to the current tenant's own login page (e.g.
    "https://www.hrzest.com/acme/login") -- used in employee-welcome-email
    templates so a new hire has a clickable link straight to their
    company's portal, not just credentials with nowhere to use them.

    Built from session["tenant_slug"] rather than tpath()/request.script_root:
    the admin registering this employee may have reached the page via a
    bare, slug-less URL (an already-resolved tenant session cached from an
    earlier request -- the same edge case blueprints/core.py's home()
    documents), in which case tpath() would silently drop the slug and
    hand a brand-new employee, who has no session of their own yet, a
    link the WSGI tenant-prefix middleware can't resolve to any company."""
    try:
        slug = session.get("tenant_slug")
        base = request.host_url.rstrip("/")
    except RuntimeError:
        return "/login"
    return f"{base}/{slug}/login" if slug else f"{base}/login"


_APP_URL = os.environ.get("APP_URL", "").rstrip("/")


def _safe_app_url() -> str:
    """Return a trusted base URL. In production APP_URL must be set — falling
    back to request.host_url is unsafe because the Host header is attacker-controlled."""
    if _APP_URL:
        return _APP_URL
    if os.environ.get("APP_ENV", "production") != "development":
        app_log.warning(
            "APP_URL is not set in hashi/.env — password-reset links will use the "
            "request Host header, which is unsafe in production. "
            "Set APP_URL=https://yourdomain.com in hashi/.env to fix this."
        )
    return request.host_url.rstrip("/")


def _safe_redirect(dest: str, fallback: str = "/admin") -> str:
    """Validate that a redirect target is a relative path (prevents open
    redirect), then stamp it with the current tenant's URL prefix via
    tpath() so every caller gets a correctly-scoped link for free."""
    if dest and dest.startswith("/") and not dest.startswith("//"):
        return tpath(dest)
    return tpath(fallback)


def _safe_referrer_redirect(referrer: str, fallback: str) -> str:
    """Like _safe_redirect, but also accepts an absolute Referer header as long
    as it points back at this same app (scheme+host), reducing it to a
    relative path first. Referer is client-supplied and can be forged by
    non-browser HTTP clients, so it's never trusted as-is."""
    if not referrer:
        return tpath(fallback)
    from urllib.parse import urlparse as _urlparse
    p = _urlparse(referrer)
    if not p.scheme and not p.netloc:
        return _safe_redirect(referrer, fallback)
    if p.netloc == request.host:
        path = p.path or "/"
        return _safe_redirect(path + (("?" + p.query) if p.query else ""), fallback)
    return tpath(fallback)


# ── PII encryption (Fernet) — fail-secure bootstrap ────────────────────────────
# Canonical location for this check. app.py used to carry a second,
# stricter copy (hard-fail in production, silent plaintext fallback in
# development) while this file's copy silently no-op'd in every
# environment — a real gap: any future caller of THIS copy would have
# stored PAN/UAN/bank-account numbers in plaintext with no warning
# louder than a log line nobody was necessarily watching.
#
# Policy is now unconditional: missing or invalid ENCRYPTION_KEY is a hard
# abort in every environment, including local dev and CI, no exception.
# The previous "allow it in development" carve-out was itself the
# mechanism that let this exact class of bug hide — a working-in-dev,
# broken-in-prod bootstrap teaches nobody to notice until it's live.
# Every environment that runs this code now needs a real key; generate
# one with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
from cryptography.fernet import Fernet, InvalidToken as _FernetInvalid

_ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "").strip()
if not _ENCRYPTION_KEY:
    app_log.critical(
        "FATAL: ENCRYPTION_KEY is not set. PAN, UAN, and bank account numbers "
        "require encryption at rest in every environment this application runs "
        "in — refusing to start rather than silently storing PII as plaintext. "
        "Generate a key: python -c \"from cryptography.fernet import Fernet; "
        "print(Fernet.generate_key().decode())\""
    )
    raise RuntimeError("ENCRYPTION_KEY is not set — refusing to start (fail-secure).")
try:
    _fernet = Fernet(_ENCRYPTION_KEY.encode())
except Exception as _key_err:
    app_log.critical(
        "FATAL: ENCRYPTION_KEY is set but malformed (%s) — refusing to start "
        "rather than silently storing PII as plaintext. Regenerate with: "
        "python -c \"from cryptography.fernet import Fernet; "
        "print(Fernet.generate_key().decode())\"",
        type(_key_err).__name__,
    )
    raise RuntimeError("ENCRYPTION_KEY is malformed — refusing to start (fail-secure).") from _key_err


def encrypt_pii(value: str) -> str:
    if not value:
        return value
    return _fernet.encrypt(value.encode()).decode()


def decrypt_pii(value: str) -> str:
    if not value:
        return value
    try:
        return _fernet.decrypt(value.encode()).decode()
    except (_FernetInvalid, Exception):
        return value


def decrypt_pii_date(value):
    """decrypt_pii() for employees.dob: that column used to be a native DATE
    and callers throughout the app call .strftime() on what it returns —
    widening it to TEXT so Fernet ciphertext fits (see app.py's
    employee_pii_columns_to_text_v1 migration) would otherwise silently
    turn every one of those call sites into an AttributeError. Returns a
    datetime.date (or None), never a bare string, so existing .strftime()
    call sites keep working unchanged."""
    if not value:
        return None
    decrypted = decrypt_pii(value)
    if isinstance(decrypted, datetime.date):
        return decrypted
    try:
        return datetime.datetime.strptime(str(decrypted), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None




# ── DB context manager ────────────────────────────────────────────────────────
@contextmanager
def _db():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        yield cursor, conn
    finally:
        try:
            cursor.close()
        except Exception as _e:
            app_log.debug("cursor.close() failed: %s", _e)
        try:
            conn.close()
        except Exception as _e:
            app_log.debug("conn.close() failed: %s", _e)


# ── Audit logging ──────────────────────────────────────────────────────────────
def _audit(action, table=None, record_id=None, detail=None):
    try:
        actor = session.get("admin_username") or session.get("employee_id") or "system"
        actor_type = "admin" if session.get("admin_logged_in") else "employee"
        ip = request.remote_addr or ""
        db = get_db_connection()
        cursor = db.cursor()
        try:
            cursor.execute(
                "INSERT INTO audit_logs (actor, actor_type, action, target_table, target_id, detail, ip_address) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (actor, actor_type, action, table, str(record_id) if record_id is not None else None, detail, ip)
            )
            db.commit()
        finally:
            cursor.close()
            db.close()
    except Exception:
        pass


# ── Notification helper ───────────────────────────────────────────────────────
def _create_notification(recipient_type, title, message, employee_id=None):
    try:
        db = get_db_connection()
        cursor = db.cursor()
        try:
            cursor.execute(
                "INSERT INTO notifications (recipient_type, employee_id, title, message) VALUES (%s,%s,%s,%s)",
                (recipient_type, employee_id, title, message)
            )
            db.commit()
        finally:
            cursor.close()
            db.close()
    except Exception:
        pass


# ── Malware scanning (ClamAV) ─────────────────────────────────────────────────
try:
    import clamd as _clamd_lib
    _clamav_available = True
except ImportError:
    _clamd_lib = None
    _clamav_available = False

_CLAMAV_HOST = os.environ.get("CLAMAV_HOST", "clamav")
_CLAMAV_PORT = int(os.environ.get("CLAMAV_PORT", "3310"))
_MALWARE_SCAN_ENABLED = os.environ.get("MALWARE_SCAN_ENABLED", "true").strip().lower() not in ("false", "0", "no")


def _scan_for_malware(file_storage):
    """Scan an uploaded file with ClamAV before it's saved. Returns (is_clean, error_msg).
    Fails closed (rejects the upload) in production if the scanner is unavailable
    or unreachable; fails open with a logged warning in development, so a missing
    local ClamAV instance doesn't block day-to-day dev work.

    Set MALWARE_SCAN_ENABLED=false to turn this off deliberately (e.g. a
    memory-constrained deployment that can't run ClamAV) — that's a clean
    skip, not a failure, so it doesn't trigger the fail-closed behavior
    below and permanently block uploads."""
    if not _MALWARE_SCAN_ENABLED:
        return True, None
    _dev = os.environ.get("APP_ENV", "production") == "development"
    if not _clamav_available:
        app_log.error("clamd package not installed — malware scanning skipped")
        return (True, None) if _dev else (False, "Malware scanning is unavailable — upload rejected.")
    try:
        cd = _clamd_lib.ClamdNetworkSocket(host=_CLAMAV_HOST, port=_CLAMAV_PORT, timeout=15)
        pos = file_storage.stream.tell()
        file_storage.stream.seek(0)
        result = cd.instream(file_storage.stream)
        file_storage.stream.seek(pos)
        status, signature = result.get("stream", (None, None))
        if status == "FOUND":
            log_security_event("validation.failure", "Malware detected in upload", level="ERROR",
                               upload_filename=file_storage.filename, signature=signature)
            return False, "This file was flagged by malware scanning and cannot be uploaded."
        return True, None
    except Exception as _e:
        app_log.error("ClamAV scan failed (%s): %s", type(_e).__name__, _e)
        return (True, None) if _dev else (False, "File could not be scanned for malware — please try again shortly.")


# ── File upload validation ─────────────────────────────────────────────────────
_ALLOWED_MIME_MAP = {
    "pdf": {"application/pdf"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "png": {"image/png"},
    "doc": {"application/msword"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "xls": {"application/vnd.ms-excel"},
    "xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
}
_MAX_DOC_SIZE_MB = 10


def _validate_upload(file_storage, allowed_exts=None):
    if not file_storage or not file_storage.filename:
        return False, "No file selected."
    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if allowed_exts and ext not in allowed_exts:
        log_security_event("validation.failure", "Upload rejected: disallowed extension",
                           level="INFO", upload_filename=file_storage.filename, ext=ext)
        return False, f"File type .{ext} not allowed. Allowed: {', '.join(sorted(allowed_exts))}"
    ct = (file_storage.content_type or "").split(";")[0].strip().lower()
    if ct and ext in _ALLOWED_MIME_MAP and ct not in _ALLOWED_MIME_MAP[ext]:
        log_security_event("validation.failure", "Upload rejected: content-type/extension mismatch",
                           level="WARNING", upload_filename=file_storage.filename, ext=ext, content_type=ct)
        return False, "File content does not match its extension."
    header = file_storage.stream.read(8)
    file_storage.stream.seek(0)
    if ext == "pdf" and not header.startswith(b"%PDF"):
        log_security_event("validation.failure", "Upload rejected: magic bytes don't match .pdf",
                           level="WARNING", upload_filename=file_storage.filename)
        return False, "Invalid PDF file."
    if ext == "png" and not header.startswith(b"\x89PNG"):
        log_security_event("validation.failure", "Upload rejected: magic bytes don't match .png",
                           level="WARNING", upload_filename=file_storage.filename)
        return False, "Invalid PNG file."
    if ext in ("jpg", "jpeg") and not header.startswith(b"\xff\xd8"):
        log_security_event("validation.failure", "Upload rejected: magic bytes don't match .jpg",
                           level="WARNING", upload_filename=file_storage.filename)
        return False, "Invalid JPEG file."
    file_storage.stream.seek(0, 2)
    size_mb = file_storage.stream.tell() / (1024 * 1024)
    file_storage.stream.seek(0)
    if size_mb > _MAX_DOC_SIZE_MB:
        log_security_event("validation.failure", "Upload rejected: exceeds size limit",
                           level="INFO", upload_filename=file_storage.filename, size_mb=round(size_mb, 1))
        return False, f"File too large ({size_mb:.1f} MB). Maximum: {_MAX_DOC_SIZE_MB} MB."
    clean, scan_err = _scan_for_malware(file_storage)
    if not clean:
        return False, scan_err
    return True, None


_ALLOWED_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
_ALLOWED_IMG_MIME = {"image/jpeg", "image/png", "image/webp", "image/bmp", "image/gif"}
_MAX_PHOTO_SIZE_MB = 5
_IMG_MAGIC = {
    ".jpg": (b"\xff\xd8",),
    ".jpeg": (b"\xff\xd8",),
    ".png": (b"\x89PNG",),
    ".webp": (b"RIFF",),
    ".bmp": (b"BM",),
}


def _validate_image_file(file):
    if not file or not file.filename:
        return False, "No file selected."
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in _ALLOWED_IMG_EXT:
        log_security_event("validation.failure", "Photo upload rejected: disallowed extension",
                           level="INFO", upload_filename=file.filename, ext=ext)
        return False, f"Invalid file type '{ext}'. Only JPG, PNG, WEBP or BMP allowed."
    ct = (file.content_type or "").lower().split(";")[0].strip()
    if ct and ct not in _ALLOWED_IMG_MIME:
        log_security_event("validation.failure", "Photo upload rejected: disallowed content-type",
                           level="WARNING", upload_filename=file.filename, content_type=ct)
        return False, f"Invalid content type '{ct}'. Only image files accepted."
    header = file.stream.read(8)
    file.stream.seek(0)
    for magic in _IMG_MAGIC.get(ext, ()):
        if not header.startswith(magic):
            log_security_event("validation.failure", "Photo upload rejected: magic bytes mismatch",
                               level="WARNING", upload_filename=file.filename, ext=ext)
            return False, "File content does not match its extension."
    file.stream.seek(0, 2)
    size_mb = file.stream.tell() / (1024 * 1024)
    file.stream.seek(0)
    if size_mb > _MAX_PHOTO_SIZE_MB:
        return False, f"Photo too large ({size_mb:.1f} MB). Maximum: {_MAX_PHOTO_SIZE_MB} MB."
    clean, scan_err = _scan_for_malware(file)
    if not clean:
        return False, scan_err
    return True, ""


# ── Company settings cache (60-second TTL) ────────────────────────────────────
_co_cache = {"data": None, "expires": None}
_auth_cache = {"data": None, "expires": None}
_settings_lock = threading.Lock()
_CO_CACHE_TTL = 60


def _co_expired(cache):
    return cache["data"] is None or datetime.datetime.now() >= cache["expires"]


def invalidate_settings_cache():
    with _settings_lock:
        _co_cache["data"] = None
        _auth_cache["data"] = None


def get_company_settings():
    with _settings_lock:
        if not _co_expired(_co_cache):
            return dict(_co_cache["data"])
    try:
        db = get_db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute("SELECT * FROM company_settings LIMIT 1")
        row = cursor.fetchone()
        row_dict = {}
        if row:
            if hasattr(row, "keys"):
                row_dict = {k.lower(): row[k] for k in row.keys()}
            elif cursor.description:
                cols = [desc[0].lower() for desc in cursor.description]
                row_dict = dict(zip(cols, row))
        cursor.close()
        db.close()
        
        if row_dict:
            result = {
                "company_name": row_dict.get("company_name") or "My Company",
                "company_tagline": row_dict.get("company_tagline") or "HRzest.com",
                "company_logo": row_dict.get("company_logo"),
                "currency_symbol": row_dict.get("currency_symbol") or "₹",
                "company_code": row_dict.get("company_code") or "COMP",
                "timezone": row_dict.get("timezone") or "Asia/Kolkata",
                "setup_done": bool(row_dict.get("setup_done")),
                "session_timeout": row_dict.get("session_timeout") or 30,
                "logo_url": row_dict.get("logo_url") or "",
                "plan": row_dict.get("plan") or "basic",
                "email_domain": row_dict.get("email_domain") or "",
            }
            with _settings_lock:
                _co_cache["data"] = result
                _co_cache["expires"] = datetime.datetime.now() + datetime.timedelta(seconds=_CO_CACHE_TTL)
            return dict(result)
    except Exception:
        pass
    return {"company_name": "My Company", "company_tagline": "HRzest.com",
            "company_logo": None, "currency_symbol": "₹", "timezone": "Asia/Kolkata",
            "setup_done": False, "company_code": "", "session_timeout": 30, "logo_url": "", "plan": "basic",
            "email_domain": ""}


# ── Company email domain (employee-registration gate) ────────────────────────
_DOMAIN_RE = re.compile(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$')


def clean_email_domain(raw: str) -> str:
    """Normalize a user-entered company domain -- strips a leading
    scheme/"@"/"www.", any path, and lowercases it, so "https://Acme.com/"
    and "acme.com" both land on "acme.com"."""
    s = (raw or "").strip().lower()
    s = re.sub(r'^https?://', '', s)
    s = s.lstrip('@')
    s = s.split('/')[0].split(':')[0]
    if s.startswith('www.'):
        s = s[4:]
    return s


def validate_email_domain_format(domain: str) -> str:
    """Returns an error message, or None if the domain string is a
    plausible one (e.g. "acme.com") -- format only, no DNS/MX lookup."""
    if not domain:
        return "Company email domain is required."
    if not _DOMAIN_RE.match(domain):
        return "Enter a valid domain, e.g. acme.com."
    return None


def validate_employee_email_domain(email) -> str:
    """Enforces "employee email must match the company's configured
    domain" -- but only once a company has actually set one
    (get_company_settings()["email_domain"]); companies that haven't
    configured a domain yet keep today's behavior (email optional, no
    domain check), so this never breaks an existing tenant that predates
    the feature. Returns an error message, or None if OK."""
    domain = (get_company_settings().get("email_domain") or "").strip().lower()
    if not domain:
        return None
    email = (email or "").strip().lower()
    if not email:
        return f"Employee email is required (must be a @{domain} address)."
    if not email.endswith("@" + domain):
        return f"Employee email must be a @{domain} address."
    return None


# ── Paid employee-seat cap (employee-registration gate) ──────────────────────
# ── Companies list + overdue-onboarding count caches (short TTL) ─────────────
# Both back per-request context processors (app.py's inject_companies_context
# / inject_overdue_onboardings) that previously ran on every single
# admin-rendered page with no cache at all, stacking on top of the
# always-fresh security checks (_enforce_ip_ban, _enforce_admin_mfa_enrollment)
# that must stay uncached. These two are pure reference/reporting data — a
# few seconds of staleness (a brand-new company not yet in the switcher, an
# onboarding-overdue badge lagging slightly) is an acceptable trade for
# cutting 2 of the ~4 DB round trips every admin page load previously paid.
_companies_cache = {"data": None, "expires": None}
_onboarding_cache = {"data": None, "expires": None}
_COMPANIES_CACHE_TTL = 30
_ONBOARDING_CACHE_TTL = 20


def invalidate_companies_cache():
    with _settings_lock:
        _companies_cache["data"] = None


def get_companies_list():
    """Cached list of (id, name, code, has_pin) tuples from the companies
    table. Call invalidate_companies_cache() after any write to companies
    (add/edit/delete/set-pin/rename-code)."""
    with _settings_lock:
        if not _co_expired(_companies_cache):
            return list(_companies_cache["data"])
    try:
        db = get_db_connection()
        cur = db.cursor(buffered=True)
        cur.execute("""
            SELECT id, name, COALESCE(code,''), COALESCE(pin,'')
            FROM companies ORDER BY name
        """)
        rows = cur.fetchall()
        cur.close()
        db.close()
        with _settings_lock:
            _companies_cache["data"] = rows
            _companies_cache["expires"] = datetime.datetime.now() + datetime.timedelta(seconds=_COMPANIES_CACHE_TTL)
        return list(rows)
    except Exception:
        return []


def get_overdue_onboarding_count():
    """Cached count of non-completed onboarding tasks past their due date."""
    with _settings_lock:
        if not _co_expired(_onboarding_cache):
            return _onboarding_cache["data"]
    try:
        db = get_db_connection()
        cur = db.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM employee_onboarding
            WHERE status != 'Completed' AND due_date < %s
        """, (datetime.date.today(),))
        count = cur.fetchone()[0]
        cur.close()
        db.close()
        with _settings_lock:
            _onboarding_cache["data"] = count
            _onboarding_cache["expires"] = datetime.datetime.now() + datetime.timedelta(seconds=_ONBOARDING_CACHE_TTL)
        return count
    except Exception:
        return 0


_AUTH_CONFIG_DEFAULTS = {
    "fingerprint_enabled": False, "qr_enabled": True, "face_enabled": True,
    "location_enabled": True, "employee_password_auth": True,
    "geo_radius": 100, "office_lat": None, "office_lon": None,
}


def get_auth_config():
    with _settings_lock:
        if not _co_expired(_auth_cache):
            return dict(_auth_cache["data"])
    try:
        db = get_db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute("""
            SELECT COALESCE(fingerprint_enabled,0), COALESCE(qr_enabled,1),
                   COALESCE(face_enabled,1), COALESCE(location_enabled,1),
                   COALESCE(employee_password_auth,1), COALESCE(geo_radius,100),
                   office_lat, office_lon
            FROM company_settings LIMIT 1
        """)
        row = cursor.fetchone()
        cursor.close()
        db.close()
        if row:
            result = {
                "fingerprint_enabled": bool(row[0]), "qr_enabled": bool(row[1]),
                "face_enabled": bool(row[2]), "location_enabled": bool(row[3]),
                "employee_password_auth": bool(row[4]), "geo_radius": row[5],
                "office_lat": row[6], "office_lon": row[7],
            }
            with _settings_lock:
                _auth_cache["data"] = result
                _auth_cache["expires"] = datetime.datetime.now() + datetime.timedelta(seconds=_CO_CACHE_TTL)
            return dict(result)
    except Exception:
        pass
    return dict(_AUTH_CONFIG_DEFAULTS)


def _read_global_features():
    try:
        db = get_db_connection()
        cur = db.cursor(buffered=True)
        cur.execute("""
            SELECT face_auth_enabled, geo_enabled, COALESCE(geo_radius,300), qr_enabled,
                   pin_enabled, COALESCE(fingerprint_enabled,0), COALESCE(biometric_enabled,0),
                   COALESCE(notify_leave,1), COALESCE(notify_payslip,1),
                   COALESCE(notify_resignation,1), COALESCE(notify_doc_expiry,1),
                   COALESCE(session_timeout,30),
                   COALESCE(late_deduction_pct,10), COALESCE(half_day_deduction_pct,50),
                   COALESCE(grace_minutes,15), COALESCE(holiday_pay,'paid'),
                   COALESCE(leave_pay,'exclude'),
                   COALESCE(shift_start,'09:00:00'), COALESCE(shift_half,'13:00:00'),
                   COALESCE(shift_end,'18:00:00')
            FROM company_settings LIMIT 1
        """)
        r = cur.fetchone()
        cur.close()
        db.close()
        if r:
            return {
                "face_auth_enabled": bool(r[0]), "geo_enabled": bool(r[1]),
                "geo_radius": r[2], "qr_enabled": bool(r[3]), "pin_enabled": bool(r[4]),
                "fingerprint_enabled": bool(r[5]), "biometric_enabled": bool(r[6]),
                "notify_leave": bool(r[7]), "notify_payslip": bool(r[8]),
                "notify_resignation": bool(r[9]), "notify_doc_expiry": bool(r[10]),
                "session_timeout": r[11], "late_deduction_pct": float(r[12]),
                "half_day_deduction_pct": float(r[13]), "grace_minutes": int(r[14]),
                "holiday_pay": r[15], "leave_pay": r[16],
                "shift_start": r[17], "shift_half": r[18], "shift_end": r[19],
            }
    except Exception:
        pass
    return {
        "face_auth_enabled": True, "geo_enabled": False, "geo_radius": 300,
        "qr_enabled": True, "pin_enabled": True, "fingerprint_enabled": False,
        "biometric_enabled": False, "notify_leave": True, "notify_payslip": True,
        "notify_resignation": True, "notify_doc_expiry": True, "session_timeout": 30,
        "late_deduction_pct": 10.0, "half_day_deduction_pct": 50.0, "grace_minutes": 15,
        "holiday_pay": "paid", "leave_pay": "exclude",
        "shift_start": "09:00:00", "shift_half": "13:00:00", "shift_end": "18:00:00",
    }


def get_co_features(company_id=None):
    if not company_id:
        return _read_global_features()
    try:
        db = get_db_connection()
        cur = db.cursor(buffered=True)
        cur.execute("""
            SELECT face_auth_enabled, geo_enabled, geo_radius, qr_enabled,
                   pin_enabled, fingerprint_enabled, biometric_enabled,
                   notify_leave, notify_payslip, notify_resignation, notify_doc_expiry,
                   session_timeout, late_deduction_pct, half_day_deduction_pct,
                   grace_minutes, holiday_pay, leave_pay, shift_start, shift_half, shift_end
            FROM company_feature_settings WHERE company_id=%s
        """, (company_id,))
        r = cur.fetchone()
        cur.close()
        db.close()
        if r:
            return {
                "face_auth_enabled": bool(r[0]), "geo_enabled": bool(r[1]),
                "geo_radius": r[2], "qr_enabled": bool(r[3]), "pin_enabled": bool(r[4]),
                "fingerprint_enabled": bool(r[5]), "biometric_enabled": bool(r[6]),
                "notify_leave": bool(r[7]), "notify_payslip": bool(r[8]),
                "notify_resignation": bool(r[9]), "notify_doc_expiry": bool(r[10]),
                "session_timeout": r[11], "late_deduction_pct": float(r[12]),
                "half_day_deduction_pct": float(r[13]), "grace_minutes": int(r[14]),
                "holiday_pay": r[15], "leave_pay": r[16],
                "shift_start": r[17], "shift_half": r[18], "shift_end": r[19],
            }
    except Exception:
        pass
    return _read_global_features()


# shift_start/shift_half/shift_end/holiday_pay/leave_pay were missing from
# this allowlist versus app.py's copy — not a security gap on their own
# (both copies fail closed on anything not listed), but a functional one:
# any caller trying to persist a per-company shift override through this
# copy would have been silently rejected while app.py's identical-looking
# function accepted it. Added to match.
_VALID_CFS_COLS = frozenset({
    "face_auth_enabled", "geo_enabled", "geo_radius", "qr_enabled", "pin_enabled",
    "fingerprint_enabled", "biometric_enabled", "notify_leave", "notify_payslip",
    "notify_resignation", "notify_doc_expiry", "session_timeout",
    "late_deduction_pct", "half_day_deduction_pct", "grace_minutes",
    "shift_start", "shift_half", "shift_end", "holiday_pay", "leave_pay",
})


def _upsert_co_feature(company_id, field, value):
    if not company_id:
        return
    # Double-gate: frozenset membership + regex ensures only safe identifier chars
    if field not in _VALID_CFS_COLS or not _SAFE_IDENT_RE.match(field):
        app_log.error("_upsert_co_feature: rejected column %r", field)
        return
    try:
        db = get_db_connection()
        cur = db.cursor(buffered=True)
        cur.execute(f"""
            INSERT INTO company_feature_settings (company_id, {field})
            VALUES (%s, %s)
            ON CONFLICT (company_id) DO UPDATE SET {field}=EXCLUDED.{field}
        """, (company_id, value))  # nosec B608
        db.commit()
        cur.close()
        db.close()
    except Exception:
        pass


def _upsert_co_features(company_id, fields_dict):
    if not company_id or not fields_dict:
        return
    # Validate every key against frozenset AND regex before any interpolation
    bad = [k for k in fields_dict if k not in _VALID_CFS_COLS or not _SAFE_IDENT_RE.match(k)]
    if bad:
        app_log.error("_upsert_co_features: rejected columns %s", bad)
        return
    try:
        safe_fields = {k: v for k, v in fields_dict.items() if k in _VALID_CFS_COLS}
        cols = ", ".join(safe_fields.keys())
        vals = list(safe_fields.values())
        placeholders = ", ".join(["%s"] * len(vals))
        updates = ", ".join(f"{k}=EXCLUDED.{k}" for k in safe_fields.keys())
        db = get_db_connection()
        cur = db.cursor(buffered=True)
        cur.execute(f"""
            INSERT INTO company_feature_settings (company_id, {cols})
            VALUES (%s, {placeholders})
            ON CONFLICT (company_id) DO UPDATE SET {updates}
        """, [company_id] + vals)  # nosec B608
        db.commit()
        cur.close()
        db.close()
    except Exception:
        pass


# ── Company-scoping WHERE fragments ─────────────────────────────────────────
# Was hand-repeated (6 near-identical copies) across admin_views.py/leave.py —
# the fragment is always a hardcoded literal chosen by whether an active
# company is selected, never user input; the actual value is always the
# single %s-bound param returned alongside it.
def co_scope_subquery(active_cid, alias=""):
    """WHERE fragment + params scoping by company via a subquery, for tables
    that don't have their own company_id column (attendance, leave_requests,
    tickets, ...). Returns ("", ()) when no active company is selected."""
    if not active_cid:
        return "", ()
    col = f"{alias}.employee_id" if alias else "employee_id"
    return f"AND {col} IN (SELECT employee_id FROM employees WHERE company_id=%s)", (active_cid,)  # nosec B608


def co_scope_column(active_cid, alias=""):
    """WHERE fragment + params scoping by company via a direct company_id
    column (e.g. the employees table itself)."""
    if not active_cid:
        return "", ()
    col = f"{alias}.company_id" if alias else "company_id"
    return f"AND {col}=%s", (active_cid,)


# ── Pending-action header counters ──────────────────────────────────────────
# Was hand-repeated (15+ near-identical copies, some drifted to a narrower
# tickets filter) across admin_views.py/attendance.py/documents.py/
# employees.py/leave.py/payroll.py/performance.py/tickets.py/core.py — the
# small badge counts most admin pages show in their header/sidebar.
def get_pending_action_counts(cursor, active_cid=None, tickets_open_only=False):
    """Returns (pending_leaves, pending_resignations, pending_tickets).

    `active_cid` scopes all three counts to one company (via
    co_scope_subquery) when given, else counts across all companies.
    `tickets_open_only` narrows the ticket count to status='Open' instead of
    the default 'Open'+'In Progress' -- a handful of pages intentionally
    show the narrower count."""
    co_sub, co_args = co_scope_subquery(active_cid)
    cursor.execute(f"SELECT COUNT(*) FROM leave_requests WHERE status='Pending' {co_sub}", co_args)  # nosec B608
    pending_leaves = cursor.fetchone()[0]
    cursor.execute(f"SELECT COUNT(*) FROM resignation_requests WHERE status='Pending' {co_sub}", co_args)  # nosec B608
    pending_resignations = cursor.fetchone()[0]
    ticket_filter = "status='Open'" if tickets_open_only else "status IN ('Open','In Progress')"
    cursor.execute(f"SELECT COUNT(*) FROM tickets WHERE {ticket_filter} {co_sub}", co_args)  # nosec B608
    pending_tickets = cursor.fetchone()[0]
    return pending_leaves, pending_resignations, pending_tickets


# ── Error page renderer ───────────────────────────────────────────────────────
# This used to render_template("error.html", ...) — that template doesn't
# exist anywhere in templates/. Every call would have raised
# jinja2.exceptions.TemplateNotFound, turning a 404/403/500 handler into a
# second, unhandled 500. Never triggered because nothing called this copy
# (app.py's own separate, working implementation handled every real error
# page) — found by checking whether the "weaker" duplicate was even
# functional, not just less-featured, before deciding which one to keep.
# Replaced with app.py's version (session-aware back-navigation, inline
# styling, no template dependency) rather than fixing the missing
# template, since that's what every real error page has actually looked
# like in production.
def _error_page(code, icon, title, subtitle, hint):
    back_admin = session.get("admin_logged_in")
    back_emp = session.get("employee_id")
    back_link = "/admin" if back_admin else ("/employee_portal" if back_emp else "/")
    back_label = "Go to Admin Dashboard" if back_admin else ("Go to My Portal" if back_emp else "Go to Home")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{code} – {title}</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box;font-family:"Segoe UI",sans-serif}}
  body{{min-height:100vh;background:#f1f5f9;display:flex;align-items:center;justify-content:center;}}
  .box{{background:#fff;border:1px solid #e2e8f0;border-radius:20px;padding:52px 44px;text-align:center;max-width:480px;width:90%;box-shadow:0 8px 32px rgba(0,0,0,0.08);}}
  .icon{{font-size:72px;margin-bottom:18px;}}
  .code{{font-size:80px;font-weight:900;line-height:1;color:#1e3a8a;margin-bottom:6px;}}
  .title{{font-size:22px;font-weight:700;color:#1e293b;margin-bottom:8px;}}
  .sub{{font-size:14px;color:#64748b;margin-bottom:6px;line-height:1.6;}}
  .hint{{font-size:12px;color:#94a3b8;margin-bottom:28px;}}
  a.btn{{display:inline-block;padding:12px 28px;background:#1e3a8a;color:#fff;border-radius:10px;font-size:14px;font-weight:700;text-decoration:none;transition:0.2s;margin:4px;}}
  a.btn:hover{{background:#1d4ed8;}}
  a.sec{{display:inline-block;padding:12px 20px;background:#f1f5f9;color:#374151;border-radius:10px;font-size:14px;font-weight:600;text-decoration:none;transition:0.2s;margin:4px;border:1px solid #e2e8f0;}}
  a.sec:hover{{background:#e2e8f0;}}
</style></head><body>
<div class="box">
  <div class="icon">{icon}</div>
  <div class="code">{code}</div>
  <div class="title">{title}</div>
  <div class="sub">{subtitle}</div>
  <div class="hint">{hint}</div>
  <a href="{back_link}" class="btn">{back_label}</a>
  <a href="javascript:history.back()" class="sec">← Go Back</a>
</div>
</body></html>""", code
