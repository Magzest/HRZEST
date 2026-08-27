"""
Biometric attendance terminal integration -- tests for blueprints/biometric.py.

Covers: admin device registration/enrollment (session-based) and the
device-facing /iclock/* ADMS-style push protocol (no session/Bearer token,
authenticated only by a registered device serial).
"""
import datetime
import pytest


def _admin_session(client, seed_admin):
    client.post("/login", data={
        "identifier": seed_admin["username"],
        "password":   seed_admin["password"],
    })
    return client


@pytest.fixture
def biometric_device(db_engine):
    """A registered biometric_devices row, scoped to the test tenant
    (att_master lives in the same Postgres DB as a schema, queried fully
    qualified so this doesn't depend on the connection's search_path)."""
    import os
    serial = "TESTDEV0001"
    cur = db_engine.cursor()
    cur.execute("DELETE FROM att_master.biometric_devices WHERE device_serial=%s", (serial,))
    cur.execute(
        "INSERT INTO att_master.biometric_devices (device_serial, tenant_schema, api_key_hash, location_name) "
        "VALUES (%s, %s, 'testhash', 'Test Office')",
        (serial, os.environ["DB_NAME"]),
    )
    yield serial
    cur.execute("DELETE FROM att_master.biometric_devices WHERE device_serial=%s", (serial,))
    cur.execute("DELETE FROM device_pin_map WHERE device_serial=%s", (serial,))
    cur.execute("DELETE FROM device_punch_log WHERE device_serial=%s", (serial,))
    cur.close()


@pytest.fixture
def enrolled_pin(db_engine, biometric_device, seed_employee):
    """seed_employee's TST001 enrolled as PIN '7' on the test device."""
    cur = db_engine.cursor()
    cur.execute(
        "INSERT INTO device_pin_map (device_serial, device_pin, employee_id) VALUES (%s, '7', %s)",
        (biometric_device, seed_employee["employee_id"]),
    )
    cur.close()
    yield "7"


@pytest.fixture(autouse=True)
def _clean_tst001_attendance(db_engine):
    """seed_employee doesn't clean up attendance rows itself -- do it here
    so punch tests in this file don't see leftover state from each other."""
    cur = db_engine.cursor()
    cur.execute("DELETE FROM attendance WHERE employee_id='TST001'")
    cur.close()
    yield
    cur = db_engine.cursor()
    cur.execute("DELETE FROM attendance WHERE employee_id='TST001'")
    cur.close()


def _attlog_line(pin, dt):
    return f"{pin}\t{dt.strftime('%Y-%m-%d %H:%M:%S')}\t0\t1\t0"


# ── Admin device management ──────────────────────────────────────────────────

class TestDeviceManagement:
    def test_register_device_returns_api_key_once(self, client, seed_admin, db_engine):
        _admin_session(client, seed_admin)
        try:
            resp = client.post("/api/biometric/devices", json={
                "device_serial": "REGTEST001", "location_name": "Front Desk",
            })
            body = resp.get_json()
            assert resp.status_code == 200
            assert body["ok"] is True
            assert body["device_serial"] == "REGTEST001"
            assert "api_key" in body and len(body["api_key"]) > 10
        finally:
            cur = db_engine.cursor()
            cur.execute("DELETE FROM att_master.biometric_devices WHERE device_serial='REGTEST001'")
            cur.close()

    def test_register_duplicate_serial_conflicts(self, client, seed_admin, biometric_device):
        _admin_session(client, seed_admin)
        resp = client.post("/api/biometric/devices", json={"device_serial": biometric_device})
        assert resp.status_code == 409
        assert resp.get_json()["ok"] is False

    def test_list_devices_shows_registered_device(self, client, seed_admin, biometric_device):
        _admin_session(client, seed_admin)
        resp = client.get("/api/biometric/devices")
        body = resp.get_json()
        assert resp.status_code == 200
        serials = [d["device_serial"] for d in body["devices"]]
        assert biometric_device in serials

    def test_unauthenticated_request_is_rejected(self, client, biometric_device):
        resp = client.get("/api/biometric/devices")
        assert resp.status_code in (302, 401, 403)

    def test_enroll_requires_known_employee(self, client, seed_admin, biometric_device):
        _admin_session(client, seed_admin)
        resp = client.post(f"/api/biometric/devices/{biometric_device}/enroll", json={
            "device_pin": "1", "employee_id": "NOSUCHEMP",
        })
        assert resp.status_code == 400
        assert resp.get_json()["ok"] is False

    def test_enroll_then_list_mappings(self, client, seed_admin, biometric_device, seed_employee, db_engine):
        _admin_session(client, seed_admin)
        try:
            resp = client.post(f"/api/biometric/devices/{biometric_device}/enroll", json={
                "device_pin": "3", "employee_id": seed_employee["employee_id"],
            })
            assert resp.get_json()["ok"] is True
            resp2 = client.get(f"/api/biometric/devices/{biometric_device}/mappings")
            pins = {m["device_pin"]: m["employee_id"] for m in resp2.get_json()["mappings"]}
            assert pins.get("3") == seed_employee["employee_id"]
        finally:
            cur = db_engine.cursor()
            cur.execute("DELETE FROM device_pin_map WHERE device_serial=%s", (biometric_device,))
            cur.close()

    def test_remove_unknown_device_is_404(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.delete("/api/biometric/devices/NOSUCHDEVICE")
        assert resp.status_code == 404

    def test_page_renders_with_and_without_devices(self, client, seed_admin, biometric_device):
        _admin_session(client, seed_admin)
        resp = client.get("/biometric_devices")
        assert resp.status_code == 200
        assert b"Biometric Devices" in resp.data
        assert biometric_device.encode() in resp.data
        assert b"iclock/cdata" in resp.data


# ── Device-facing /iclock/* push protocol ────────────────────────────────────

class TestIclockProtocol:
    def test_handshake_returns_option_response(self, client, biometric_device):
        resp = client.get(f"/iclock/cdata?SN={biometric_device}")
        assert resp.status_code == 200
        assert b"GET OPTION FROM" in resp.data

    def test_getrequest_returns_ok(self, client, biometric_device):
        resp = client.get(f"/iclock/getrequest?SN={biometric_device}")
        assert resp.status_code == 200
        assert resp.data == b"OK"

    def test_unknown_device_serial_rejected(self, client):
        resp = client.get("/iclock/cdata?SN=NOT-A-REAL-DEVICE")
        assert resp.status_code == 404
        assert resp.data == b"ERROR"

    def test_missing_serial_rejected(self, client):
        resp = client.post("/iclock/cdata", data="1\t2026-01-01 09:00:00\t0\t1\t0")
        assert resp.status_code == 400

    def test_push_from_unenrolled_pin_is_ignored(self, client, biometric_device, db_engine):
        now = datetime.datetime.now().replace(microsecond=0)
        resp = client.post(
            f"/iclock/cdata?SN={biometric_device}&table=ATTLOG",
            data=_attlog_line("99", now),
            content_type="text/plain",
        )
        assert resp.status_code == 200
        assert resp.data == b"OK"
        cur = db_engine.cursor()
        cur.execute("SELECT COUNT(*) FROM attendance WHERE date=%s", (now.date(),))
        # Can't assert zero globally (other tenants' data), but the specific
        # unenrolled pin must never have created a mapped punch:
        cur.execute("SELECT COUNT(*) FROM device_punch_log WHERE device_serial=%s AND device_pin='99'", (biometric_device,))
        assert cur.fetchone()[0] == 0
        cur.close()

    def test_push_creates_login_then_logout(self, client, biometric_device, enrolled_pin, seed_employee, db_engine):
        today = datetime.date.today()
        login_dt = datetime.datetime.combine(today, datetime.time(9, 5, 0))
        logout_dt = datetime.datetime.combine(today, datetime.time(18, 10, 0))

        resp1 = client.post(
            f"/iclock/cdata?SN={biometric_device}&table=ATTLOG",
            data=_attlog_line(enrolled_pin, login_dt),
            content_type="text/plain",
        )
        assert resp1.data == b"OK"

        cur = db_engine.cursor()
        cur.execute(
            "SELECT login_time, logout_time FROM attendance WHERE employee_id=%s AND date=%s",
            (seed_employee["employee_id"], today),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[1] is None  # not logged out yet
        cur.close()

        resp2 = client.post(
            f"/iclock/cdata?SN={biometric_device}&table=ATTLOG",
            data=_attlog_line(enrolled_pin, logout_dt),
            content_type="text/plain",
        )
        assert resp2.data == b"OK"

        cur = db_engine.cursor()
        cur.execute(
            "SELECT login_time, logout_time FROM attendance WHERE employee_id=%s AND date=%s",
            (seed_employee["employee_id"], today),
        )
        row = cur.fetchone()
        assert row[0] is not None
        assert row[1] is not None
        cur.close()

    def test_duplicate_punch_is_not_double_processed(self, client, biometric_device, enrolled_pin, seed_employee, db_engine):
        today = datetime.date.today()
        login_dt = datetime.datetime.combine(today, datetime.time(9, 5, 0))
        line = _attlog_line(enrolled_pin, login_dt)

        client.post(f"/iclock/cdata?SN={biometric_device}&table=ATTLOG", data=line, content_type="text/plain")
        # Same exact punch delivered again (device retry) -- must NOT flip
        # the toggle into a logout.
        client.post(f"/iclock/cdata?SN={biometric_device}&table=ATTLOG", data=line, content_type="text/plain")

        cur = db_engine.cursor()
        cur.execute(
            "SELECT login_time, logout_time FROM attendance WHERE employee_id=%s AND date=%s",
            (seed_employee["employee_id"], today),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[1] is None, "duplicate punch should not have been processed as a logout"
        cur.close()
