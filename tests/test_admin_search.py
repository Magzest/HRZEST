"""Tests for the admin dashboard omnisearch: GET /api/admin/search
(blueprints/admin_views.py) plus the search bar markup on /admin
(templates/admin.html)."""


def _admin_session(client, seed_admin):
    resp = client.post("/login", data={
        "identifier": seed_admin["username"],
        "password": seed_admin["password"],
    }, follow_redirects=True)
    assert resp.status_code == 200
    return resp


class TestAdminDashboardHasSearchMarkup:
    def test_renders_search_bar(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.get("/admin")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "adminSearchInput" in body
        assert "/api/admin/search" in body


class TestAdminSearchEndpoint:
    def test_requires_admin_login(self, client):
        resp = client.get("/api/admin/search?q=test", follow_redirects=False)
        assert resp.status_code in (302, 401)

    def test_short_query_returns_empty(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.get("/api/admin/search?q=a")
        assert resp.status_code == 200
        assert resp.get_json()["results"] == []

    def test_finds_employee_by_name(self, client, seed_admin, seed_employee):
        _admin_session(client, seed_admin)
        resp = client.get("/api/admin/search?q=Test Employee")
        assert resp.status_code == 200
        results = resp.get_json()["results"]
        emp_hits = [r for r in results if r["type"] == "employee"]
        assert len(emp_hits) == 1
        assert emp_hits[0]["sub"].startswith(seed_employee["employee_id"])
        assert emp_hits[0]["url"] == f"/employees?hl={seed_employee['employee_id']}"

    def test_finds_employee_by_id(self, client, seed_admin, seed_employee):
        _admin_session(client, seed_admin)
        resp = client.get(f"/api/admin/search?q={seed_employee['employee_id']}")
        results = resp.get_json()["results"]
        assert any(r["type"] == "employee" for r in results)

    def test_finds_ticket_by_subject(self, client, seed_admin, seed_employee, db_engine):
        # att_test is a persistent, shared DB (see conftest.py) — a plain
        # trailing DELETE never runs if an assertion below fails, leaving a
        # row that inflates every future run's hit count. try/finally
        # guarantees cleanup regardless of outcome.
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO tickets (employee_id, category, subject, description, priority) "
            "VALUES (%s,'IT','VeryUniqueTicketSubject','desc','Low')",
            (seed_employee["employee_id"],),
        )
        db_engine.commit()
        cur.close()

        try:
            _admin_session(client, seed_admin)
            resp = client.get("/api/admin/search?q=VeryUniqueTicketSubject")
            results = resp.get_json()["results"]
            ticket_hits = [r for r in results if r["type"] == "ticket"]
            assert len(ticket_hits) == 1
            assert ticket_hits[0]["label"] == "VeryUniqueTicketSubject"
        finally:
            cur = db_engine.cursor()
            cur.execute("DELETE FROM tickets WHERE subject='VeryUniqueTicketSubject'")
            db_engine.commit()
            cur.close()

    def test_finds_leave_request_by_reason(self, client, seed_admin, seed_employee, db_engine):
        import datetime
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO leave_requests (employee_id, leave_date, reason, status) VALUES (%s,%s,%s,'Pending')",
            (seed_employee["employee_id"], datetime.date.today(), "VeryUniqueLeaveReasonXYZ"),
        )
        db_engine.commit()
        cur.close()

        try:
            _admin_session(client, seed_admin)
            resp = client.get("/api/admin/search?q=VeryUniqueLeaveReasonXYZ")
            results = resp.get_json()["results"]
            leave_hits = [r for r in results if r["type"] == "leave"]
            assert len(leave_hits) == 1
        finally:
            cur = db_engine.cursor()
            cur.execute("DELETE FROM leave_requests WHERE reason='VeryUniqueLeaveReasonXYZ'")
            db_engine.commit()
            cur.close()

    def test_no_match_returns_empty_results(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.get("/api/admin/search?q=NoSuchThingExistsAnywhereXYZ123")
        assert resp.get_json()["results"] == []
