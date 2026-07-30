"""Tests for the HR Portal separation: a distinct 'hr' admin_users role with
its own login (/hr_login) and dashboard (/hr), explicitly blocked from
completing the regular /admin_login, and explicitly locked out of the
tenant/system-settings and Compliance & Security Center surfaces that a
plain admin session can reach."""
import pytest


def _admin_session(client, username, role="admin"):
    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True
        sess["admin_username"] = username
        sess["admin_role"] = role


@pytest.fixture
def hr_admin(seed_admin, db_engine):
    """A seeded admin promoted to the hr role -- same pattern as
    tests/test_secops.py's soc_admin fixture."""
    cur = db_engine.cursor()
    cur.execute("UPDATE admin_users SET role='hr' WHERE username=%s", (seed_admin["username"],))
    db_engine.commit()
    cur.close()
    yield seed_admin
    cur = db_engine.cursor()
    cur.execute("UPDATE admin_users SET role='admin' WHERE username=%s", (seed_admin["username"],))
    db_engine.commit()
    cur.close()


class TestHrLogin:
    def test_hr_login_page_loads(self, client):
        resp = client.get("/hr_login")
        assert resp.status_code == 200
        assert b"HR Portal" in resp.data

    def test_hr_credentials_succeed_via_hr_login(self, client, hr_admin):
        resp = client.post("/hr_login", data={
            "identifier": hr_admin["username"], "password": hr_admin["password"],
        })
        assert resp.status_code == 302
        assert resp.headers.get("Location") == "/hr"
        with client.session_transaction() as sess:
            assert sess["admin_logged_in"] is True
            assert sess["admin_role"] == "hr"

    def test_wrong_password_fails(self, client, hr_admin):
        resp = client.post("/hr_login", data={
            "identifier": hr_admin["username"], "password": "wrong-password",
        })
        assert resp.status_code == 200
        assert b"Invalid credentials" in resp.data

    def test_regular_admin_cannot_log_in_via_hr_login(self, client, seed_admin):
        # seed_admin defaults to role='admin' -- must not be able to reach
        # the HR portal with regular admin credentials.
        resp = client.post("/hr_login", data={
            "identifier": seed_admin["username"], "password": seed_admin["password"],
        })
        assert resp.status_code == 200
        assert b"Invalid credentials" in resp.data
        with client.session_transaction() as sess:
            assert not sess.get("admin_logged_in")

    def test_hr_credentials_rejected_by_regular_admin_login(self, client, hr_admin):
        # The reverse separation: an hr-role account must not be able to
        # complete the regular /admin_login and get a full admin session.
        resp = client.post("/admin_login", data={
            "identifier": hr_admin["username"], "password": hr_admin["password"],
        })
        assert resp.status_code == 200
        assert b"Invalid credentials" in resp.data
        with client.session_transaction() as sess:
            assert not sess.get("admin_logged_in")


class TestHrDashboardGate:
    def test_anonymous_redirected_to_admin_login(self, client):
        resp = client.get("/hr", follow_redirects=False)
        assert resp.status_code in (302, 401, 403)

    def test_regular_admin_gets_403(self, client, seed_admin):
        _admin_session(client, seed_admin["username"], role="admin")
        resp = client.get("/hr")
        assert resp.status_code == 403

    def test_hr_role_reaches_dashboard(self, client, hr_admin):
        _admin_session(client, hr_admin["username"], role="hr")
        resp = client.get("/hr")
        assert resp.status_code == 200
        assert b"HR Dashboard" in resp.data

    def test_hr_role_redirected_away_from_full_admin_dashboard(self, client, hr_admin):
        _admin_session(client, hr_admin["username"], role="hr")
        resp = client.get("/admin", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers.get("Location") == "/hr"


class TestHrScopeRestrictions:
    """An hr-role session reuses the same admin_logged_in session shape as a
    regular admin (so it can reach the shared employee-lifecycle routes),
    which means the tenant/system-settings and Compliance & Security Center
    routes must explicitly reject it via role_required("admin") rather than
    relying on admin_required alone."""

    @pytest.mark.parametrize("path", [
        "/settings", "/companies", "/analytics", "/admin_tools", "/compliance",
    ])
    def test_hr_role_blocked_from_admin_only_pages(self, client, hr_admin, path):
        _admin_session(client, hr_admin["username"], role="hr")
        resp = client.get(path)
        assert resp.status_code == 403

    @pytest.mark.parametrize("path", [
        "/employees", "/monthly_report", "/leave_holidays", "/overtime",
        "/performance", "/onboarding", "/tickets", "/documents",
    ])
    def test_hr_role_reaches_shared_employee_lifecycle_pages(self, client, hr_admin, path):
        _admin_session(client, hr_admin["username"], role="hr")
        resp = client.get(path)
        assert resp.status_code == 200

    def test_hr_role_blocked_from_payroll(self, client, hr_admin):
        _admin_session(client, hr_admin["username"], role="hr")
        resp = client.get("/salary_report")
        assert resp.status_code == 403
