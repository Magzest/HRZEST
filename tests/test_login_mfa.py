"""Tests for the mandatory emailed-OTP login step (blueprints/auth.py's
MANDATORY_LOGIN_MFA / _start_login_mfa / /mfa_verify): admin, employee,
and HR logins (HR uses the same general /login as admin -- see
test_hr_role_can_use_admin_login_and_completes_mfa) all stop at a pending
OTP state instead of completing immediately, and only build a real
session once the emailed code is verified.

Disabled globally in tests/conftest.py (MANDATORY_LOGIN_MFA=False), same
reasoning as disabling flask-limiter and MANDATORY_ADMIN_MFA, since almost
the entire suite uses a plain POST /login or /hr_login as its "get an
authenticated session" setup. Re-enabled locally here."""
import time
import pytest


@pytest.fixture
def mandatory_login_mfa_enabled(client):
    client.application.config["MANDATORY_LOGIN_MFA"] = True
    yield
    client.application.config["MANDATORY_LOGIN_MFA"] = False


class TestAdminLoginMfa:
    def test_correct_password_does_not_grant_session_yet(self, client, seed_admin, mandatory_login_mfa_enabled):
        resp = client.post("/login", data={
            "identifier": seed_admin["username"], "password": seed_admin["password"],
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers.get("Location") == "/mfa_verify"
        with client.session_transaction() as sess:
            assert not sess.get("admin_logged_in")
            assert sess.get("mfa_pending") is True
            assert sess.get("mfa_kind") == "admin_users"
            assert sess.get("mfa_user") == seed_admin["username"]

    def test_correct_otp_completes_login(self, client, seed_admin, mandatory_login_mfa_enabled):
        client.post("/login", data={
            "identifier": seed_admin["username"], "password": seed_admin["password"],
        })
        with client.session_transaction() as sess:
            code = sess["mfa_otp_code"]

        resp = client.post("/mfa_verify", data={"otp_code": code}, follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers.get("Location") == "/admin"
        with client.session_transaction() as sess:
            assert sess.get("admin_logged_in") is True
            assert sess.get("admin_username") == seed_admin["username"]
            assert not sess.get("mfa_pending")

    def test_wrong_otp_rejected(self, client, seed_admin, mandatory_login_mfa_enabled):
        client.post("/login", data={
            "identifier": seed_admin["username"], "password": seed_admin["password"],
        })
        resp = client.post("/mfa_verify", data={"otp_code": "000000"})
        assert resp.status_code == 200
        assert b"Invalid code" in resp.data
        with client.session_transaction() as sess:
            assert not sess.get("admin_logged_in")

    def test_expired_otp_rejected(self, client, seed_admin, mandatory_login_mfa_enabled):
        client.post("/login", data={
            "identifier": seed_admin["username"], "password": seed_admin["password"],
        })
        with client.session_transaction() as sess:
            code = sess["mfa_otp_code"]
            sess["mfa_issued_at"] = time.time() - 301

        resp = client.post("/mfa_verify", data={"otp_code": code})
        assert resp.status_code == 200
        assert b"expired" in resp.data.lower()

    def test_soc_analyst_role_cannot_use_admin_login_even_with_mfa_enabled(self, client, seed_admin, db_engine, mandatory_login_mfa_enabled):
        """SOC analyst stays a separate credential (blueprints/secops.py's
        /sp_admin/login) -- unlike HR (see the hr_role tests below), it's
        never let through the general admin login."""
        db_engine.cursor().execute("UPDATE admin_users SET role='soc_analyst' WHERE username=%s", (seed_admin["username"],))
        db_engine.commit()
        resp = client.post("/login", data={
            "identifier": seed_admin["username"], "password": seed_admin["password"],
        })
        assert b"Invalid credentials" in resp.data
        db_engine.cursor().execute("UPDATE admin_users SET role='admin' WHERE username=%s", (seed_admin["username"],))
        db_engine.commit()

    def test_hr_role_can_use_admin_login_and_completes_mfa(self, client, seed_admin, db_engine, mandatory_login_mfa_enabled):
        """HR accounts (blueprints/admin_views.py's /hr_accounts management
        page) use the same general login as admin, and land on /employees
        instead of /admin after MFA -- role_required("admin") elsewhere
        scopes them away from admin-only pages regardless."""
        db_engine.cursor().execute("UPDATE admin_users SET role='hr' WHERE username=%s", (seed_admin["username"],))
        db_engine.commit()
        try:
            client.post("/login", data={
                "identifier": seed_admin["username"], "password": seed_admin["password"],
            })
            with client.session_transaction() as sess:
                code = sess["mfa_otp_code"]
            resp = client.post("/mfa_verify", data={"otp_code": code}, follow_redirects=False)
            assert resp.status_code == 302
            assert resp.headers.get("Location") == "/employees"
            with client.session_transaction() as sess:
                assert sess.get("admin_logged_in") is True
                assert sess.get("admin_role") == "hr"
        finally:
            db_engine.cursor().execute("UPDATE admin_users SET role='admin' WHERE username=%s", (seed_admin["username"],))
            db_engine.commit()

    def test_admin_with_no_email_on_file_rejected_generically(self, client, db_engine, mandatory_login_mfa_enabled):
        from utils.auth import generate_password_hash
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO admin_users (username, password, email) VALUES (%s,%s,NULL) "
            "ON CONFLICT (username) DO NOTHING",
            ("noemail_admin", generate_password_hash("NoEmail@123")),
        )
        db_engine.commit()
        resp = client.post("/login", data={"identifier": "noemail_admin", "password": "NoEmail@123"})
        assert b"Invalid credentials" in resp.data
        with client.session_transaction() as sess:
            assert not sess.get("mfa_pending")
        cur.execute("DELETE FROM admin_users WHERE username='noemail_admin'")
        db_engine.commit()


class TestEmployeeLoginMfa:
    def test_correct_password_does_not_grant_session_yet(self, client, seed_employee, mandatory_login_mfa_enabled):
        resp = client.post("/login", data={
            "identifier": seed_employee["employee_id"], "password": seed_employee["password"],
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers.get("Location") == "/mfa_verify"
        with client.session_transaction() as sess:
            assert not sess.get("employee_id")
            assert sess.get("mfa_kind") == "employee"
            assert sess.get("mfa_user") == seed_employee["employee_id"]

    def test_correct_otp_completes_login(self, client, seed_employee, mandatory_login_mfa_enabled):
        client.post("/login", data={
            "identifier": seed_employee["employee_id"], "password": seed_employee["password"],
        })
        with client.session_transaction() as sess:
            code = sess["mfa_otp_code"]

        resp = client.post("/mfa_verify", data={"otp_code": code}, follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers.get("Location") == "/employee_portal"
        with client.session_transaction() as sess:
            assert sess.get("employee_id") == seed_employee["employee_id"]

    def test_otp_never_leaks_into_page_html(self, client, seed_employee, mandatory_login_mfa_enabled):
        client.post("/login", data={
            "identifier": seed_employee["employee_id"], "password": seed_employee["password"],
        })
        with client.session_transaction() as sess:
            code = sess["mfa_otp_code"]
        resp = client.get("/mfa_verify")
        assert code.encode() not in resp.data


# The standalone HR Portal (blueprints/hr_portal.py: its own /hr_login and
# /hr dashboard) was intentionally removed from the codebase (see git log
# "chore: remove HR portal, SuperAdmin, SecOps, Compliance modules & cleanup
# duplicates") -- there is no /hr_login route to test login-MFA against
# anymore. The one security property worth keeping (an admin_users row
# with role='hr' must never complete a session through the regular /login)
# is still covered, and still enforced in blueprints/auth.py, by
# TestAdminLoginMfa::test_hr_role_cannot_use_admin_login_even_with_mfa_enabled
# above.


class TestGateDisabledByDefault:
    def test_admin_login_completes_immediately_without_the_fixture(self, client, seed_admin):
        resp = client.post("/login", data={
            "identifier": seed_admin["username"], "password": seed_admin["password"],
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers.get("Location") == "/admin"
