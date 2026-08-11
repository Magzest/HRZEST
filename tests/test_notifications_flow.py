"""Tests for the notification-bell feature: the /web/notifications/*
endpoints (pre-existing, previously unused by any frontend), and the
in-app notifications now created for ticket and announcement events
(blueprints/tickets.py, blueprints/admin_views.py) alongside the leave
notifications that already existed."""
import pytest


def _admin_session(client, seed_admin):
    resp = client.post("/login", data={
        "identifier": seed_admin["username"],
        "password": seed_admin["password"],
    }, follow_redirects=True)
    assert resp.status_code == 200
    return resp


def _admin_token(client, seed_admin):
    resp = client.post("/api/login", json={
        "username": seed_admin["username"],
        "password": seed_admin["password"],
    })
    assert resp.status_code == 200
    return resp.get_json()["token"]


def _emp_token(client, seed_employee):
    resp = client.post("/api/employee/login", json={
        "employee_id": seed_employee["employee_id"],
        "password": seed_employee["password"],
    })
    assert resp.status_code == 200
    return resp.get_json()["token"]


@pytest.fixture(autouse=True)
def _clean_notifications(db_engine):
    yield
    cur = db_engine.cursor()
    cur.execute("DELETE FROM notifications")
    cur.execute("DELETE FROM tickets")
    cur.execute("DELETE FROM announcements")
    db_engine.commit()
    cur.close()


class TestPortalPageHasBellMarkup:
    def test_employee_portal_renders_bell_widget(self, client, seed_employee):
        with client.session_transaction() as sess:
            sess["employee_id"] = seed_employee["employee_id"]
        resp = client.get("/employee_portal")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "notifBell" in body
        assert "notifPanel" in body
        assert "/web/notifications/list" in body


class TestWebNotificationsEndpoints:
    def test_list_requires_login(self, client):
        resp = client.get("/web/notifications/list", follow_redirects=False)
        assert resp.status_code in (302, 401)

    def test_list_and_mark_read_round_trip(self, client, seed_employee, db_engine):
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO notifications (recipient_type, employee_id, title, message) VALUES ('employee',%s,%s,%s)",
            (seed_employee["employee_id"], "Test Notice", "Hello there"),
        )
        db_engine.commit()
        cur.close()

        with client.session_transaction() as sess:
            sess["employee_id"] = seed_employee["employee_id"]

        resp = client.get("/web/notifications/list")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert len(data["notifications"]) == 1
        assert data["notifications"][0]["title"] == "Test Notice"
        assert data["notifications"][0]["is_read"] is False

        resp2 = client.post("/web/notifications/mark_read")
        assert resp2.status_code == 200

        resp3 = client.get("/web/notifications/list")
        assert resp3.get_json()["notifications"][0]["is_read"] is True

    def test_only_sees_own_notifications(self, client, seed_employee, db_engine):
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO employees (employee_id, name, password) VALUES ('OTHER_EMP', 'Other Employee', 'x') "
            "ON CONFLICT (employee_id) DO NOTHING"
        )
        cur.execute(
            "INSERT INTO notifications (recipient_type, employee_id, title, message) VALUES ('employee','OTHER_EMP',%s,%s)",
            ("Not for you", "..."),
        )
        db_engine.commit()
        cur.close()

        with client.session_transaction() as sess:
            sess["employee_id"] = seed_employee["employee_id"]
        resp = client.get("/web/notifications/list")
        assert resp.get_json()["notifications"] == []

        cur = db_engine.cursor()
        cur.execute("DELETE FROM employees WHERE employee_id='OTHER_EMP'")
        db_engine.commit()
        cur.close()


class TestTicketNotifications:
    def test_raising_ticket_notifies_admin(self, client, seed_employee, seed_admin, db_engine):
        with client.session_transaction() as sess:
            sess["employee_id"] = seed_employee["employee_id"]
        resp = client.post("/raise_ticket", data={
            "category": "IT", "subject": "Laptop issue",
            "description": "Won't boot", "priority": "High",
        }, follow_redirects=False)
        assert resp.status_code in (302, 200)

        cur = db_engine.cursor()
        cur.execute("SELECT title, message FROM notifications WHERE recipient_type='admin'")
        rows = cur.fetchall()
        cur.close()
        assert len(rows) == 1
        assert "Laptop issue" in rows[0][1]

    def test_api_raise_ticket_notifies_admin(self, client, seed_employee, db_engine):
        token = _emp_token(client, seed_employee)
        resp = client.post("/api/employee/raise_ticket",
                           headers={"Authorization": f"Bearer {token}"},
                           json={"category": "HR", "subject": "Payslip query",
                                 "description": "Missing bonus", "priority": "Medium"})
        assert resp.status_code == 200

        cur = db_engine.cursor()
        cur.execute("SELECT COUNT(*) FROM notifications WHERE recipient_type='admin'")
        count = cur.fetchone()[0]
        cur.close()
        assert count == 1

    def test_admin_ticket_action_notifies_employee(self, client, seed_employee, seed_admin, db_engine):
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO tickets (employee_id, category, subject, description, priority) "
            "VALUES (%s,'IT','VPN broken','desc','Low') RETURNING id",
            (seed_employee["employee_id"],),
        )
        tid = cur.fetchone()[0]
        db_engine.commit()
        cur.close()

        _admin_session(client, seed_admin)
        resp = client.post(f"/ticket_action/{tid}", data={
            "status": "Resolved", "admin_response": "Fixed the VPN config.",
        }, follow_redirects=False)
        assert resp.status_code in (302, 200)

        cur = db_engine.cursor()
        cur.execute(
            "SELECT title, message FROM notifications WHERE recipient_type='employee' AND employee_id=%s",
            (seed_employee["employee_id"],),
        )
        rows = cur.fetchall()
        cur.close()
        assert len(rows) == 1
        assert "VPN broken" in rows[0][0]
        assert "Resolved" in rows[0][1]

    def test_api_ticket_action_notifies_employee(self, client, seed_employee, seed_admin, db_engine):
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO tickets (employee_id, category, subject, description, priority) "
            "VALUES (%s,'IT','Monitor flickers','desc','Low') RETURNING id",
            (seed_employee["employee_id"],),
        )
        tid = cur.fetchone()[0]
        db_engine.commit()
        cur.close()

        admin_token = _admin_token(client, seed_admin)
        resp = client.post(f"/api/tickets/{tid}/action",
                           headers={"Authorization": f"Bearer {admin_token}"},
                           json={"status": "In Progress", "admin_response": ""})
        assert resp.status_code == 200

        cur = db_engine.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM notifications WHERE recipient_type='employee' AND employee_id=%s",
            (seed_employee["employee_id"],),
        )
        count = cur.fetchone()[0]
        cur.close()
        assert count == 1


class TestAnnouncementNotifications:
    def test_public_announcement_notifies_all_active_employees(self, client, seed_employee, seed_admin, db_engine):
        _admin_session(client, seed_admin)
        resp = client.post("/announcements", data={
            "action": "add", "title": "Office Closed",
            "content": "Closed for maintenance on Friday.",
            "priority": "Urgent", "visibility": "public",
        }, follow_redirects=False)
        assert resp.status_code in (302, 200)

        cur = db_engine.cursor()
        cur.execute(
            "SELECT title FROM notifications WHERE recipient_type='employee' AND employee_id=%s",
            (seed_employee["employee_id"],),
        )
        rows = cur.fetchall()
        cur.close()
        assert len(rows) == 1
        assert "Office Closed" in rows[0][0]

    def test_private_announcement_notifies_only_target(self, client, seed_employee, seed_admin, db_engine):
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO employees (employee_id, name, email, password, force_pin_change) "
            "VALUES ('TST002','Other Employee','other@test.local','x',0) ON CONFLICT DO NOTHING"
        )
        db_engine.commit()
        cur.close()

        _admin_session(client, seed_admin)
        resp = client.post("/announcements", data={
            "action": "add", "title": "Private Note",
            "content": "Just for you.", "priority": "Normal",
            "visibility": "private", "target_employee_id": seed_employee["employee_id"],
        }, follow_redirects=False)
        assert resp.status_code in (302, 200)

        cur = db_engine.cursor()
        cur.execute("SELECT COUNT(*) FROM notifications WHERE recipient_type='employee' AND employee_id=%s",
                    (seed_employee["employee_id"],))
        target_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM notifications WHERE recipient_type='employee' AND employee_id='TST002'")
        other_count = cur.fetchone()[0]
        cur.execute("DELETE FROM employees WHERE employee_id='TST002'")
        db_engine.commit()
        cur.close()
        assert target_count == 1
        assert other_count == 0
