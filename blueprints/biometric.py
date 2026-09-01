# -*- coding: utf-8 -*-
"""Biometric attendance terminal integration.

Connects physical fingerprint/face attendance terminals -- ZKTeco and the
many OEM clones (eSSL, Realtime, Matrix, iFace, etc.) that share the same
firmware lineage and the same "ADMS/iClock" push protocol -- to the exact
same attendance pipeline the mobile app's check-in already uses
(blueprints/attendance.py's process_punch()).

Two route groups:
  - Admin-facing (session, @admin_required): register a device, enroll a
    device's internal user PIN against a real employee_id, list/manage
    both. Ordinary tenant-scoped routes -- work the normal g.tenant_db way.
  - Device-facing (no @admin_required/@api_required -- the terminal has no
    session cookie or Bearer token, only its own serial number): the
    /iclock/* endpoints the physical terminal itself talks to once its
    Comm > Cloud Server Setting points at this server. These resolve their
    tenant explicitly from biometric_devices (master schema, keyed by
    device_serial) via get_tenant_db(), since there's no URL slug or
    session for _resolve_tenant() to work with here.

SECURITY NOTE: the ADMS/iClock push protocol predates any notion of
per-request auth -- a device identifies itself with nothing but its serial
number (SN=... in the query string), which isn't a secret, it's printed on
a sticker on the unit. biometric_devices.api_key_hash exists for the admin
management UI and for the (uncommon) device model that does support
signing its own requests -- it is NOT verified against every /iclock/*
call, because most real terminals have no way to send it. Treat network-
level restriction (site VPN, IP allowlist, or a reverse proxy in front of
these two routes) as the real access control for this endpoint family.

The exact OPTION-response fields a device expects on handshake can vary a
little by firmware/OEM; the defaults below are the commonly documented
ones and are a starting point to validate against your actual hardware,
not a guarantee every clone behaves identically.
"""
import datetime
import secrets
from flask import Blueprint, request, jsonify, session, Response, g, render_template
from extensions import limiter, log_security_event, app_log
from database import get_db_connection, get_master_db, get_tenant_db
from utils.auth import admin_required, _hash_token
from utils.helpers import tpath, _audit, get_company_settings, get_pending_action_counts
from blueprints.attendance import process_punch

biometric_bp = Blueprint("biometric", __name__)


# ── Admin page (session-based HTML) ──────────────────────────────────────────

@biometric_bp.route("/biometric_devices")
@admin_required
def biometric_devices_page():
    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute(
        "SELECT device_serial, location_name, last_seen_at, created_at "
        "FROM biometric_devices WHERE tenant_schema=%s ORDER BY created_at DESC",
        (g.tenant_db,)
    )
    devices = cur.fetchall()
    cur.close()
    conn.close()

    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT employee_id, name FROM employees ORDER BY name")
    employees = cursor.fetchall()
    pending_leaves, pending_resignations, pending_tickets = get_pending_action_counts(cursor)
    cursor.close()
    db.close()

    return render_template(
        "biometric_devices.html",
        co=get_company_settings(),
        pending_leaves=pending_leaves,
        pending_resignations=pending_resignations,
        pending_tickets=pending_tickets,
        devices=devices,
        employees=employees,
        active_nav="biometric_devices",
    )


# ── Admin API (session-based JSON, same page's own fetch() calls) ───────────

@biometric_bp.route("/api/biometric/devices", methods=["GET"])
@admin_required
def list_biometric_devices():
    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute(
        "SELECT device_serial, location_name, last_seen_at, created_at "
        "FROM biometric_devices WHERE tenant_schema=%s ORDER BY created_at DESC",
        (g.tenant_db,)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    devices = [
        {
            "device_serial": r[0],
            "location_name": r[1],
            "last_seen_at": r[2].isoformat() if r[2] else None,
            "created_at": r[3].isoformat() if r[3] else None,
        }
        for r in rows
    ]
    return jsonify({"ok": True, "devices": devices})


@biometric_bp.route("/api/biometric/devices", methods=["POST"])
@admin_required
def register_biometric_device():
    data = request.get_json() or {}
    device_serial = (data.get("device_serial") or "").strip()
    location_name = (data.get("location_name") or "").strip() or None
    if not device_serial:
        return jsonify({"ok": False, "msg": "device_serial is required -- it's printed on the device and shown under its Comm/Network menu."}), 400

    api_key = secrets.token_hex(24)
    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute(
        "INSERT INTO biometric_devices (device_serial, tenant_schema, api_key_hash, location_name, registered_by) "
        "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (device_serial) DO NOTHING",
        (device_serial, g.tenant_db, _hash_token(api_key), location_name, session.get("admin_username"))
    )
    if cur.rowcount == 0:
        cur.close()
        conn.close()
        return jsonify({"ok": False, "msg": "A device with this serial number is already registered."}), 409
    conn.commit()
    cur.close()
    conn.close()
    _audit("register_biometric_device", "biometric_devices", device_serial, f"location={location_name or 'n/a'}")
    return jsonify({
        "ok": True,
        "msg": "Device registered. Point the terminal's Comm/Cloud Server setting at this server, "
               "then enroll each employee's device PIN below.",
        "device_serial": device_serial,
        "api_key": api_key,  # shown once; only the hash is stored
    })


@biometric_bp.route("/api/biometric/devices/<device_serial>", methods=["DELETE"])
@admin_required
def remove_biometric_device(device_serial):
    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute(
        "DELETE FROM biometric_devices WHERE device_serial=%s AND tenant_schema=%s",
        (device_serial, g.tenant_db)
    )
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    if not deleted:
        return jsonify({"ok": False, "msg": "Device not found."}), 404
    _audit("remove_biometric_device", "biometric_devices", device_serial)
    return jsonify({"ok": True, "msg": "Device removed."})


def _device_belongs_to_tenant(device_serial):
    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute(
        "SELECT 1 FROM biometric_devices WHERE device_serial=%s AND tenant_schema=%s",
        (device_serial, g.tenant_db)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return bool(row)


@biometric_bp.route("/api/biometric/devices/<device_serial>/mappings", methods=["GET"])
@admin_required
def list_biometric_mappings(device_serial):
    if not _device_belongs_to_tenant(device_serial):
        return jsonify({"ok": False, "msg": "Device not found."}), 404
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute(
        "SELECT m.device_pin, m.employee_id, e.name FROM device_pin_map m "
        "JOIN employees e ON e.employee_id = m.employee_id "
        "WHERE m.device_serial=%s ORDER BY m.device_pin",
        (device_serial,)
    )
    rows = cursor.fetchall()
    cursor.close()
    db.close()
    mappings = [{"device_pin": r[0], "employee_id": r[1], "name": r[2]} for r in rows]
    return jsonify({"ok": True, "mappings": mappings})


@biometric_bp.route("/api/biometric/devices/<device_serial>/enroll", methods=["POST"])
@admin_required
def enroll_biometric_pin(device_serial):
    if not _device_belongs_to_tenant(device_serial):
        return jsonify({"ok": False, "msg": "Device not found."}), 404
    data = request.get_json() or {}
    device_pin = (data.get("device_pin") or "").strip()
    employee_id = (data.get("employee_id") or "").strip()
    if not device_pin or not employee_id:
        return jsonify({"ok": False, "msg": "device_pin and employee_id are both required."}), 400

    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT 1 FROM employees WHERE employee_id=%s", (employee_id,))
    if not cursor.fetchone():
        cursor.close()
        db.close()
        return jsonify({"ok": False, "msg": f"Unknown employee_id '{employee_id}'."}), 400
    cursor.execute(
        "INSERT INTO device_pin_map (device_serial, device_pin, employee_id) VALUES (%s,%s,%s) "
        "ON CONFLICT (device_serial, device_pin) DO UPDATE SET employee_id=EXCLUDED.employee_id",
        (device_serial, device_pin, employee_id)
    )
    db.commit()
    cursor.close()
    db.close()
    _audit("enroll_biometric_pin", "device_pin_map", f"{device_serial}:{device_pin}", f"employee_id={employee_id}")
    return jsonify({"ok": True, "msg": "Enrolled."})


@biometric_bp.route("/api/biometric/devices/<device_serial>/mappings/<device_pin>", methods=["DELETE"])
@admin_required
def remove_biometric_mapping(device_serial, device_pin):
    if not _device_belongs_to_tenant(device_serial):
        return jsonify({"ok": False, "msg": "Device not found."}), 404
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute(
        "DELETE FROM device_pin_map WHERE device_serial=%s AND device_pin=%s",
        (device_serial, device_pin)
    )
    deleted = cursor.rowcount
    db.commit()
    cursor.close()
    db.close()
    if not deleted:
        return jsonify({"ok": False, "msg": "Mapping not found."}), 404
    _audit("remove_biometric_pin_mapping", "device_pin_map", f"{device_serial}:{device_pin}")
    return jsonify({"ok": True, "msg": "Mapping removed."})


# ── Device-facing ADMS/iClock push protocol (no session, no Bearer token) ───

def _resolve_device_tenant(device_serial):
    """device_serial -> tenant_schema, or None if unregistered. Master-DB
    lookup since a device push carries no URL slug/session for the normal
    g.tenant_db resolution to work with."""
    conn = get_master_db()
    cur = conn.cursor(buffered=True)
    cur.execute("SELECT tenant_schema FROM biometric_devices WHERE device_serial=%s", (device_serial,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None


def _touch_device_last_seen(device_serial):
    try:
        conn = get_master_db()
        cur = conn.cursor()
        cur.execute("UPDATE biometric_devices SET last_seen_at=NOW() WHERE device_serial=%s", (device_serial,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as exc:
        app_log.debug("Could not update last_seen_at for biometric device %s: %s", device_serial, exc)


@biometric_bp.route("/iclock/cdata", methods=["GET", "POST"])
@limiter.limit("120 per minute")
def iclock_cdata():
    device_serial = (request.args.get("SN") or "").strip()
    if not device_serial:
        return Response("ERROR", mimetype="text/plain"), 400

    tenant_schema = _resolve_device_tenant(device_serial)
    if not tenant_schema:
        log_security_event(
            "biometric.unknown_device", "Push from an unregistered biometric device serial",
            level="WARNING", identifier=device_serial,
        )
        return Response("ERROR", mimetype="text/plain"), 404

    if request.method == "GET":
        # Handshake -- the device is asking what it should do. We don't
        # push commands or user data back to the device today, so this is
        # a minimal "just upload logs normally" OPTION response.
        body = (
            f"GET OPTION FROM: {device_serial}\n"
            "Stamp=9999\n"
            "OpStamp=0\n"
            "ErrorDelay=30\n"
            "Delay=10\n"
            "TransFlag=1111000000\n"
            "Realtime=1\n"
            "Encrypt=0\n"
        )
        _touch_device_last_seen(device_serial)
        return Response(body, mimetype="text/plain")

    # POST -- log upload. table=ATTLOG is the one we act on; anything else
    # (OPERLOG device-side user-management events, etc.) is accepted and
    # discarded so the device doesn't get stuck retrying an upload this
    # server will never consume.
    table = (request.args.get("table") or "ATTLOG").strip()
    _touch_device_last_seen(device_serial)
    if table != "ATTLOG":
        return Response("OK", mimetype="text/plain")

    raw = request.get_data(as_text=True) or ""
    conn = get_tenant_db(tenant_schema)
    cur = conn.cursor(buffered=True)
    processed = 0
    try:
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            device_pin, time_str = parts[0].strip(), parts[1].strip()
            try:
                punch_dt = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                app_log.warning("biometric: unparseable punch timestamp %r from device %s", time_str, device_serial)
                continue

            cur.execute(
                "SELECT employee_id FROM device_pin_map WHERE device_serial=%s AND device_pin=%s",
                (device_serial, device_pin)
            )
            row = cur.fetchone()
            if not row:
                app_log.warning("biometric: punch from unenrolled PIN %s on device %s", device_pin, device_serial)
                continue
            emp_id = row[0]

            # Dedup: devices commonly resend already-delivered logs (a
            # dropped connection retry, or a manual "re-upload" on the
            # device itself). process_punch()'s login/logout/relogin state
            # machine is a toggle, not idempotent -- replaying the same
            # punch would wrongly flip a login into a logout.
            cur.execute(
                "INSERT INTO device_punch_log (device_serial, device_pin, punch_time, employee_id) "
                "VALUES (%s,%s,%s,%s) ON CONFLICT (device_serial, device_pin, punch_time) DO NOTHING",
                (device_serial, device_pin, punch_dt, emp_id)
            )
            if cur.rowcount == 0:
                continue  # already processed this exact punch

            cur.execute("SELECT name FROM employees WHERE employee_id=%s", (emp_id,))
            erow = cur.fetchone()
            if not erow:
                continue
            process_punch(cur, conn, emp_id, erow[0], punch_dt=punch_dt)
            processed += 1
    finally:
        cur.close()
        conn.close()

    log_security_event(
        "biometric.punches_received", f"Processed {processed} punch(es) from biometric device",
        level="INFO", identifier=device_serial,
    )
    return Response("OK", mimetype="text/plain")


@biometric_bp.route("/iclock/getrequest", methods=["GET"])
@limiter.limit("120 per minute")
def iclock_getrequest():
    """Devices poll this periodically for pending commands. We never push
    commands/user data to the device today, so "OK" (the documented
    "nothing to do" response) is always correct here."""
    device_serial = (request.args.get("SN") or "").strip()
    if device_serial:
        _touch_device_last_seen(device_serial)
    return Response("OK", mimetype="text/plain")
