# -*- coding: utf-8 -*-
"""Self-service device management shared by the employee, company-admin,
HR, and platform-admin dashboards -- each owner_kind's rows live in that
schema's user_devices table (tenant schema for employee/admin/hr, att_master
for platform_admin; see app.py's init_db()/init_master_db()).

Callers pass a conn_getter (database.get_db_connection for tenant-schema
owners, database.get_master_db for platform_admin) so this module stays
schema-agnostic -- it never decides which schema to talk to itself.
"""
import re
import secrets

from utils.session_risk import evaluate_session_risk

DEVICE_COOKIE_NAME = "hz_device_tok"
# ~13 months, the same ceiling Chrome enforces on cookies generally -- there's
# nothing session-length-sensitive stored here, just a stable per-browser ID.
DEVICE_COOKIE_MAX_AGE = 400 * 24 * 3600
_TOKEN_RE = re.compile(r'^[a-f0-9]{48}$')

_UA_OS_PATTERNS = [
    (re.compile(r'Windows NT'), 'Windows'),
    (re.compile(r'Mac OS X'), 'macOS'),
    (re.compile(r'Android'), 'Android'),
    (re.compile(r'iPhone|iPad|iPod'), 'iOS'),
    (re.compile(r'Linux'), 'Linux'),
]
_UA_BROWSER_PATTERNS = [
    (re.compile(r'Edg/'), 'Edge'),
    (re.compile(r'OPR/|Opera'), 'Opera'),
    (re.compile(r'Chrome/'), 'Chrome'),
    (re.compile(r'Firefox/'), 'Firefox'),
    (re.compile(r'Safari/'), 'Safari'),
]


def parse_user_agent(ua):
    """Best-effort browser/OS/device-type label from a raw User-Agent
    string. Regex-pattern matching against a stdlib-only string -- no
    external UA-parsing dependency for what's purely a display label, never
    a security decision."""
    ua = ua or ""
    os_name = next((name for pat, name in _UA_OS_PATTERNS if pat.search(ua)), "Unknown OS")
    browser = next((name for pat, name in _UA_BROWSER_PATTERNS if pat.search(ua)), "Unknown Browser")
    device_type = "mobile" if re.search(r'Mobi|Android|iPhone', ua) else (
        "tablet" if re.search(r'iPad|Tablet', ua) else "desktop"
    )
    return device_type, browser, os_name


def get_or_create_device_token(request):
    """Get-or-create the per-browser correlation ID stored in a long-lived
    cookie -- purely a join key between "this browser" and its user_devices
    row, same non-secret role as session_risk's _sid (utils/session_risk.py).
    Returns (token, is_new); is_new tells the caller whether to actually set
    the cookie on the outgoing response."""
    token = request.cookies.get(DEVICE_COOKIE_NAME)
    if token and _TOKEN_RE.match(token):
        return token, False
    return secrets.token_hex(24), True


def set_device_cookie(resp, token):
    resp.set_cookie(DEVICE_COOKIE_NAME, token, max_age=DEVICE_COOKIE_MAX_AGE,
                     httponly=True, samesite="Lax")


def record_login_device(conn_getter, owner_kind, owner_id, device_token, sid, request):
    """Upsert a 'login'-kind device row for this owner on this browser.
    Safe to call on every successful login -- ON CONFLICT just refreshes
    last_active_at/IP/last_sid instead of creating a duplicate row per visit,
    and un-revokes a device the owner had previously signed back into."""
    device_type, browser, os_name = parse_user_agent(request.headers.get("User-Agent"))
    ip = request.remote_addr
    label = f"{browser} on {os_name}"
    conn = conn_getter()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO user_devices
                (owner_kind, owner_id, device_token, kind, device_name, device_type,
                 browser, os, ip_address, last_sid, last_active_at)
            VALUES (%s, %s, %s, 'login', %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (owner_kind, owner_id, device_token) DO UPDATE SET
                device_type = EXCLUDED.device_type,
                browser = EXCLUDED.browser,
                os = EXCLUDED.os,
                ip_address = EXCLUDED.ip_address,
                last_sid = EXCLUDED.last_sid,
                last_active_at = NOW(),
                is_revoked = 0
            """,
            (owner_kind, owner_id, device_token, label, device_type, browser, os_name, ip, sid),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def list_devices(conn_getter, owner_kind, owner_id, current_token):
    conn = conn_getter()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, kind, device_name, device_type, browser, os, ip_address, "
            "asset_model, asset_serial, device_token, last_active_at, first_seen_at "
            "FROM user_devices WHERE owner_kind=%s AND owner_id=%s AND is_revoked=0 "
            "ORDER BY last_active_at DESC NULLS LAST, first_seen_at DESC",
            (owner_kind, owner_id),
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    devices = []
    for r in rows:
        devices.append({
            "id": r[0], "kind": r[1], "device_name": r[2], "device_type": r[3],
            "browser": r[4], "os": r[5], "ip_address": r[6],
            "asset_model": r[7], "asset_serial": r[8],
            "is_current": bool(current_token) and r[9] == current_token,
            "last_active_at": r[10].isoformat() if r[10] else None,
            "first_seen_at": r[11].isoformat() if r[11] else None,
        })
    return devices


def rename_device(conn_getter, owner_kind, owner_id, device_id, new_name):
    new_name = (new_name or "").strip()[:150]
    if not new_name:
        return False
    conn = conn_getter()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE user_devices SET device_name=%s WHERE id=%s AND owner_kind=%s AND owner_id=%s",
            (new_name, device_id, owner_kind, owner_id),
        )
        updated = cursor.rowcount > 0
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return updated


def add_asset_device(conn_getter, owner_kind, owner_id, device_name, asset_model, asset_serial):
    device_name = (device_name or "").strip()[:150]
    if not device_name:
        return None
    conn = conn_getter()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO user_devices (owner_kind, owner_id, device_token, kind, device_name, "
            "asset_model, asset_serial) VALUES (%s, %s, %s, 'asset', %s, %s, %s) RETURNING id",
            (owner_kind, owner_id, secrets.token_hex(24), device_name,
             (asset_model or "").strip()[:150] or None, (asset_serial or "").strip()[:150] or None),
        )
        new_id = cursor.fetchone()[0]
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return new_id


def delete_asset_device(conn_getter, owner_kind, owner_id, device_id):
    """Assets are hard-deleted (not just revoked) -- unlike a login device,
    there's no session tied to one and no value in keeping a tombstone row
    around once the employee removes it."""
    conn = conn_getter()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM user_devices WHERE id=%s AND owner_kind=%s AND owner_id=%s AND kind='asset'",
            (device_id, owner_kind, owner_id),
        )
        deleted = cursor.rowcount > 0
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return deleted


def revoke_device(conn_getter, owner_kind, owner_id, device_id, identifier_for_risk=None):
    """Marks a 'login' device revoked and, when we know its last session ID,
    force-kills that session via the same session_risk kill switch the
    existing device-risk endpoint uses (utils/session_risk.py) -- so revoke
    actually signs the device out on its next request, not just hides it
    from this list. identifier_for_risk lets the caller pass the readable
    username/employee_id session_risk logs against; falls back to owner_id."""
    conn = conn_getter()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT kind, last_sid FROM user_devices WHERE id=%s AND owner_kind=%s AND owner_id=%s",
            (device_id, owner_kind, owner_id),
        )
        row = cursor.fetchone()
        if not row:
            return False
        cursor.execute(
            "UPDATE user_devices SET is_revoked=1 WHERE id=%s AND owner_kind=%s AND owner_id=%s",
            (device_id, owner_kind, owner_id),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    kind, last_sid = row
    if kind == "login" and last_sid:
        evaluate_session_risk(
            last_sid, identifier_for_risk or owner_id, owner_kind, 999,
            "device.revoked", "Device revoked from device-management panel",
        )
    return True
