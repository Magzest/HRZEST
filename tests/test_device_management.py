# -*- coding: utf-8 -*-
"""Tests for the self-service device-management panel shared by the
employee, admin, and hr dashboards (utils/device_utils.py, and each
role's /api/*/devices routes) -- login devices are captured automatically
at login and can be renamed/revoked; company-asset entries are fully
owner-managed (add/rename/delete). Platform admin's own copy
(/super_admin/devices/*) isn't covered here since it lives in att_master,
not a tenant schema reachable through this suite's fixtures -- covered
manually instead.
"""
import os
import time
import pytest
from utils.session_risk import is_session_compromised


def _wait_compromised(sid, timeout=2):
    """evaluate_session_risk() enqueues its DB write to a background writer
    thread (utils/session_risk.py) -- poll briefly rather than asserting
    immediately, same pattern as tests/test_device_risk.py."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_session_compromised(sid):
            return True
        time.sleep(0.05)
    return False


def _wipe_shared_rows(db_engine):
    cur = db_engine.cursor()
    cur.execute("DELETE FROM user_devices WHERE owner_id IN ('TST001', 'test_admin')")
    # chat_messages lives in att_master (utils/chat_utils.py), not this
    # tenant schema -- fully-qualified so it's reachable regardless of this
    # connection's current search_path.
    cur.execute("DELETE FROM att_master.chat_messages WHERE tenant_schema=%s", (os.environ["DB_NAME"],))
    db_engine.commit()
    cur.close()


@pytest.fixture(autouse=True)
def _cleanup_devices(db_engine):
    """Wipe before AND after, not just after -- TST001/test_admin are
    shared identifiers used by logins all over the suite (same reasoning as
    conftest.py's own login_attempts cleanup on seed_employee/seed_admin),
    and each test gets a fresh test-client cookie jar with no existing
    device-token cookie, so an unrelated test's employee/admin login
    earlier in the same run leaves behind a real accumulated row here --
    not just other runs' leftovers."""
    _wipe_shared_rows(db_engine)
    yield
    _wipe_shared_rows(db_engine)


class TestEmployeeDeviceManagement:
    def test_login_records_a_device(self, client, seed_employee):
        client.post("/login", data={
            "identifier": seed_employee["employee_id"], "password": seed_employee["password"],
        })
        resp = client.get("/api/employee/devices")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        logins = [d for d in data["devices"] if d["kind"] == "login"]
        assert len(logins) == 1
        assert logins[0]["is_current"] is True

    def test_requires_login(self, client):
        resp = client.get("/api/employee/devices", follow_redirects=False)
        assert resp.status_code in (302, 401)

    def test_add_rename_delete_asset(self, client, seed_employee):
        client.post("/login", data={
            "identifier": seed_employee["employee_id"], "password": seed_employee["password"],
        })
        resp = client.post("/api/employee/devices/asset", json={
            "device_name": "Work Phone", "asset_model": "Pixel 8", "asset_serial": "SN-9",
        })
        assert resp.status_code == 200
        new_id = resp.get_json()["id"]
        assert new_id

        resp = client.get("/api/employee/devices")
        assets = [d for d in resp.get_json()["devices"] if d["kind"] == "asset"]
        assert len(assets) == 1
        assert assets[0]["device_name"] == "Work Phone"
        assert assets[0]["asset_model"] == "Pixel 8"

        resp = client.post(f"/api/employee/devices/{new_id}/rename", json={"name": "Backup Phone"})
        assert resp.get_json()["ok"] is True
        resp = client.get("/api/employee/devices")
        assets = [d for d in resp.get_json()["devices"] if d["kind"] == "asset"]
        assert assets[0]["device_name"] == "Backup Phone"

        resp = client.post(f"/api/employee/devices/asset/{new_id}/delete")
        assert resp.get_json()["ok"] is True
        resp = client.get("/api/employee/devices")
        assert [d for d in resp.get_json()["devices"] if d["kind"] == "asset"] == []

    def test_cannot_manage_another_owners_device(self, client, seed_employee, db_engine):
        """A device row that belongs to a different owner_id must be
        invisible/untouchable through this employee's own session --
        rename/revoke/delete all filter on owner_id, not just id."""
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO user_devices (owner_kind, owner_id, device_token, kind, device_name) "
            "VALUES ('employee', 'OTHER_EMP', %s, 'asset', 'Not Yours') RETURNING id",
            ("x" * 48,),
        )
        other_id = cur.fetchone()[0]
        db_engine.commit()
        cur.close()

        client.post("/login", data={
            "identifier": seed_employee["employee_id"], "password": seed_employee["password"],
        })
        resp = client.post(f"/api/employee/devices/{other_id}/rename", json={"name": "Hijacked"})
        assert resp.get_json()["ok"] is False
        resp = client.post(f"/api/employee/devices/asset/{other_id}/delete")
        assert resp.get_json()["ok"] is False

        cur = db_engine.cursor()
        cur.execute("DELETE FROM user_devices WHERE id=%s", (other_id,))
        db_engine.commit()
        cur.close()

    def test_revoke_marks_device_hidden(self, client, seed_employee, db_engine):
        """Revoking a *different* device (not the one this session is
        currently using) just hides it -- no session to kill for it."""
        client.post("/login", data={
            "identifier": seed_employee["employee_id"], "password": seed_employee["password"],
        })
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO user_devices (owner_kind, owner_id, device_token, kind, device_name) "
            "VALUES ('employee', %s, %s, 'login', 'Other Browser') RETURNING id",
            (seed_employee["employee_id"], "y" * 48),
        )
        other_login_id = cur.fetchone()[0]
        db_engine.commit()
        cur.close()

        resp = client.post(f"/api/employee/devices/{other_login_id}/revoke")
        assert resp.get_json()["ok"] is True

        resp = client.get("/api/employee/devices")
        assert [d for d in resp.get_json()["devices"] if d["id"] == other_login_id] == []

    def test_revoking_current_device_signs_it_out(self, client, seed_employee):
        """Revoking the device this very session is using goes further than
        hiding it -- it force-compromises that session (utils/session_risk.py,
        the same kill switch /api/employee/device_risk uses), so the
        session's next request anywhere is rejected -- an actual sign-out,
        not just a cosmetic list removal."""
        client.post("/login", data={
            "identifier": seed_employee["employee_id"], "password": seed_employee["password"],
        })
        resp = client.get("/api/employee/devices")
        login_id = [d for d in resp.get_json()["devices"] if d["kind"] == "login"][0]["id"]
        with client.session_transaction() as sess:
            sid = sess["_sid"]

        resp = client.post(f"/api/employee/devices/{login_id}/revoke")
        assert resp.get_json()["ok"] is True
        assert _wait_compromised(sid) is True

        resp = client.get("/employee_portal", follow_redirects=False)
        assert resp.status_code == 302
        assert "login" in resp.headers.get("Location", "")


class TestAdminDeviceManagement:
    def test_login_records_a_device_with_admin_owner_kind(self, client, seed_admin, db_engine):
        client.post("/login", data={
            "identifier": seed_admin["username"], "password": seed_admin["password"],
        })
        resp = client.get("/api/admin/devices")
        assert resp.status_code == 200
        logins = [d for d in resp.get_json()["devices"] if d["kind"] == "login"]
        assert len(logins) == 1

        cur = db_engine.cursor()
        cur.execute("SELECT owner_kind FROM user_devices WHERE owner_id=%s", (seed_admin["username"],))
        assert cur.fetchone()[0] == "admin"
        cur.close()

    def test_hr_role_uses_hr_owner_kind(self, client, seed_admin, db_engine):
        cur = db_engine.cursor()
        cur.execute("UPDATE admin_users SET role='hr' WHERE username=%s", (seed_admin["username"],))
        db_engine.commit()
        cur.close()
        try:
            client.post("/login", data={
                "identifier": seed_admin["username"], "password": seed_admin["password"],
            })
            resp = client.get("/api/admin/devices")
            assert resp.status_code == 200
            cur = db_engine.cursor()
            cur.execute("SELECT owner_kind FROM user_devices WHERE owner_id=%s", (seed_admin["username"],))
            assert cur.fetchone()[0] == "hr"
            cur.close()
        finally:
            cur = db_engine.cursor()
            cur.execute("UPDATE admin_users SET role='admin' WHERE username=%s", (seed_admin["username"],))
            db_engine.commit()
            cur.close()

    def test_requires_login(self, client):
        resp = client.get("/api/admin/devices", follow_redirects=False)
        assert resp.status_code in (302, 401)


class TestCompanyChat:
    def test_send_and_list_roundtrip(self, client, seed_admin):
        client.post("/login", data={
            "identifier": seed_admin["username"], "password": seed_admin["password"],
        })
        resp = client.post("/api/admin/chat/send", json={"message": "Need help with billing"})
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

        resp = client.get("/api/admin/chat/messages")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert any(m["message"] == "Need help with billing" and m["sender_kind"] == "admin"
                   for m in data["messages"])

    def test_empty_message_rejected(self, client, seed_admin):
        client.post("/login", data={
            "identifier": seed_admin["username"], "password": seed_admin["password"],
        })
        resp = client.post("/api/admin/chat/send", json={"message": "   "})
        assert resp.status_code == 400

    def test_requires_login(self, client):
        resp = client.get("/api/admin/chat/messages", follow_redirects=False)
        assert resp.status_code in (302, 401)
