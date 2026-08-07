"""Tests for blueprints/platform_admin.py -- the cross-tenant SaaS operator
console at /super_admin/*. This identity lives in att_master.platform_admins,
outside every tenant schema, and uses its own session keys
(platform_admin_logged_in) deliberately distinct from admin_logged_in so
app.py's tenant-oriented before_request hooks don't misfire on it.

send_mfa_login_email isn't mocked here -- same approach as
tests/test_login_mfa.py: no SMTP is configured in the test environment, so
it no-ops (returns False) without raising, and the OTP code is read
straight out of the session instead of an actual inbox.
"""
import time
import pytest
from utils.auth import generate_password_hash


@pytest.fixture
def platform_admin(db_engine):
    from app import init_master_db
    init_master_db()
    cur = db_engine.cursor()
    cur.execute(
        "INSERT INTO att_master.platform_admins (username, password, email) "
        "VALUES (%s,%s,%s) ON CONFLICT (username) DO NOTHING",
        ("test_platform_admin", generate_password_hash("Platform@1234"), "platform@test.local"),
    )
    cur.close()
    yield {"username": "test_platform_admin", "password": "Platform@1234"}
    cur = db_engine.cursor()
    cur.execute("DELETE FROM att_master.platform_admins WHERE username='test_platform_admin'")
    cur.close()


@pytest.fixture
def sample_tenant(db_engine):
    from app import init_master_db
    init_master_db()
    cur = db_engine.cursor()
    cur.execute("DELETE FROM att_master.tenants WHERE subdomain='pa-sample-tenant'")
    cur.execute(
        "INSERT INTO att_master.tenants (company_name, subdomain, db_name, admin_email, plan, status) "
        "VALUES (%s,%s,%s,%s,'starter','active') RETURNING id",
        ("Sample Tenant Co", "pa-sample-tenant", "att_pa_sample_tenant", "owner@sample.test"),
    )
    tenant_id = cur.fetchone()[0]
    cur.close()
    yield tenant_id
    cur = db_engine.cursor()
    cur.execute("DELETE FROM att_master.tenants WHERE id=%s", (tenant_id,))
    cur.close()


def _login_and_verify(client, platform_admin):
    resp = client.post("/super_admin/login", data={
        "username": platform_admin["username"], "password": platform_admin["password"],
    }, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers.get("Location") == "/super_admin/mfa_verify"
    with client.session_transaction() as sess:
        code = sess["platform_mfa_otp_code"]
    resp = client.post("/super_admin/mfa_verify", data={"otp_code": code}, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers.get("Location") == "/super_admin"
    return resp


class TestPlatformAdminAccessControl:
    def test_dashboard_unauthenticated_redirects_to_login(self, client):
        resp = client.get("/super_admin")
        assert resp.status_code == 302
        assert resp.headers.get("Location") == "/super_admin/login"

    def test_regular_admin_session_does_not_grant_access(self, client, seed_admin):
        # admin_logged_in is a deliberately different identity/session
        # shape -- a normal tenant admin session must not reach the
        # cross-tenant console.
        with client.session_transaction() as sess:
            sess["admin_logged_in"] = True
            sess["admin_username"] = seed_admin["username"]
            sess["admin_role"] = "admin"
        resp = client.get("/super_admin")
        assert resp.status_code == 302
        assert resp.headers.get("Location") == "/super_admin/login"

    def test_wrong_password_rejected(self, client, platform_admin):
        resp = client.post("/super_admin/login", data={
            "username": platform_admin["username"], "password": "wrong-password",
        })
        assert b"Invalid credentials" in resp.data

    def test_unknown_username_rejected(self, client):
        resp = client.post("/super_admin/login", data={
            "username": "no-such-platform-admin", "password": "whatever",
        })
        assert b"Invalid credentials" in resp.data


class TestPlatformAdminLoginFlow:
    def test_full_login_flow_reaches_dashboard(self, client, platform_admin):
        _login_and_verify(client, platform_admin)
        resp = client.get("/super_admin")
        assert resp.status_code == 200
        assert b"Platform Admin" in resp.data

    def test_wrong_otp_rejected(self, client, platform_admin):
        client.post("/super_admin/login", data={
            "username": platform_admin["username"], "password": platform_admin["password"],
        })
        resp = client.post("/super_admin/mfa_verify", data={"otp_code": "000000"})
        assert b"Invalid verification code" in resp.data

    def test_expired_otp_rejected(self, client, platform_admin):
        client.post("/super_admin/login", data={
            "username": platform_admin["username"], "password": platform_admin["password"],
        })
        with client.session_transaction() as sess:
            code = sess["platform_mfa_otp_code"]
            sess["platform_mfa_issued_at"] = time.time() - 999
        resp = client.post("/super_admin/mfa_verify", data={"otp_code": code})
        assert b"expired" in resp.data.lower()

    def test_logout_clears_session(self, client, platform_admin):
        _login_and_verify(client, platform_admin)
        client.post("/super_admin/logout")
        resp = client.get("/super_admin")
        assert resp.status_code == 302
        assert resp.headers.get("Location") == "/super_admin/login"

    def test_idle_timeout_forces_relogin(self, client, platform_admin):
        _login_and_verify(client, platform_admin)
        with client.session_transaction() as sess:
            sess["platform_admin_last_activity"] = time.time() - 999999
        resp = client.get("/super_admin", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers.get("Location") == "/super_admin/login"


class TestPlatformAdminDashboard:
    def test_lists_tenant(self, client, platform_admin, sample_tenant):
        _login_and_verify(client, platform_admin)
        resp = client.get("/super_admin")
        assert resp.status_code == 200
        assert b"Sample Tenant Co" in resp.data
        assert b"Basic" in resp.data  # display name for the 'starter' plan key (utils/plan_limits.py)

    def test_missing_tenant_schema_does_not_crash_dashboard(self, client, platform_admin, sample_tenant):
        # sample_tenant's db_name doesn't correspond to a real schema (this
        # fixture only registers the att_master.tenants row, not a full
        # provisioned schema) -- _tenant_employee_count() must fail
        # gracefully to 0 rather than 500ing the whole dashboard.
        _login_and_verify(client, platform_admin)
        resp = client.get("/super_admin")
        assert resp.status_code == 200


class TestPlatformAdminTenantActions:
    def test_change_plan(self, client, platform_admin, sample_tenant, db_engine):
        _login_and_verify(client, platform_admin)
        resp = client.post(f"/super_admin/tenants/{sample_tenant}/plan", data={"plan": "growth"},
                           follow_redirects=False)
        assert resp.status_code == 302
        cur = db_engine.cursor()
        cur.execute("SELECT plan FROM att_master.tenants WHERE id=%s", (sample_tenant,))
        assert cur.fetchone()[0] == "growth"
        cur.close()

    def test_change_plan_rejects_unknown_plan(self, client, platform_admin, sample_tenant, db_engine):
        _login_and_verify(client, platform_admin)
        resp = client.post(f"/super_admin/tenants/{sample_tenant}/plan", data={"plan": "not-a-real-plan"},
                           follow_redirects=True)
        assert b"valid plan" in resp.data.lower()
        cur = db_engine.cursor()
        cur.execute("SELECT plan FROM att_master.tenants WHERE id=%s", (sample_tenant,))
        assert cur.fetchone()[0] == "starter"
        cur.close()

    def test_suspend_and_reactivate(self, client, platform_admin, sample_tenant, db_engine):
        _login_and_verify(client, platform_admin)
        resp = client.post(f"/super_admin/tenants/{sample_tenant}/status", data={"status": "suspended"},
                           follow_redirects=False)
        assert resp.status_code == 302
        cur = db_engine.cursor()
        cur.execute("SELECT status FROM att_master.tenants WHERE id=%s", (sample_tenant,))
        assert cur.fetchone()[0] == "suspended"
        cur.close()

        resp = client.post(f"/super_admin/tenants/{sample_tenant}/status", data={"status": "active"},
                           follow_redirects=False)
        assert resp.status_code == 302
        cur = db_engine.cursor()
        cur.execute("SELECT status FROM att_master.tenants WHERE id=%s", (sample_tenant,))
        assert cur.fetchone()[0] == "active"
        cur.close()

    def test_tenant_actions_require_login(self, client, sample_tenant):
        resp = client.post(f"/super_admin/tenants/{sample_tenant}/plan", data={"plan": "growth"},
                           follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers.get("Location") == "/super_admin/login"


def _drop_schema(db_engine, schema_name):
    cur = db_engine.cursor()
    cur.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')
    cur.execute("DELETE FROM att_master.tenants WHERE db_name=%s", (schema_name,))
    cur.close()


class TestPlatformAdminCreateTenant:
    """/super_admin/tenants/create shares its provisioning core
    (blueprints/org.py's provision_tenant()) with the public /create_org
    signup -- same real-schema-creation weight and cleanup as
    tests/test_org.py's TestFullProvisioning, just reached via the
    operator console instead of self-serve signup."""

    def test_requires_login(self, client):
        resp = client.post("/super_admin/tenants/create", data={
            "company_name": "No Auth Co", "subdomain": "pa-noauth",
            "admin_username": "noauth_admin", "admin_password": "password123",
            "admin_email": "noauth@test.local", "plan": "starter",
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers.get("Location") == "/super_admin/login"

    def test_create_tenant_provisions_real_schema(self, client, platform_admin, db_engine):
        _login_and_verify(client, platform_admin)

        subdomain = "pa-e2e-org"
        schema_name = "att_" + subdomain.replace("-", "_")
        _drop_schema(db_engine, schema_name)
        try:
            resp = client.post("/super_admin/tenants/create", data={
                "company_name": "PA E2E Org", "subdomain": subdomain,
                "admin_username": "pa_e2e_admin", "admin_password": "password123",
                "admin_email": "pa_e2e@test.local", "plan": "growth",
            }, follow_redirects=False)
            assert resp.status_code == 302
            assert resp.headers.get("Location") == "/super_admin"

            cur = db_engine.cursor()
            cur.execute(
                "SELECT schema_name FROM information_schema.schemata WHERE schema_name=%s",
                (schema_name,),
            )
            assert cur.fetchone() is not None, "tenant schema was not created"

            cur.execute("SELECT db_name, status, plan FROM att_master.tenants WHERE subdomain=%s", (subdomain,))
            row = cur.fetchone()
            assert row is not None, "tenant was not registered in att_master.tenants"
            assert row[0] == schema_name
            assert row[1] == "active"
            assert row[2] == "growth"

            cur.execute(f'SELECT username FROM "{schema_name}".admin_users WHERE username=%s', ("pa_e2e_admin",))
            assert cur.fetchone() is not None, "admin user was not seeded into the new tenant schema"
            cur.close()

            # The new company shows up on the operator's own dashboard.
            dash = client.get("/super_admin")
            assert b"PA E2E Org" in dash.data
        finally:
            _drop_schema(db_engine, schema_name)

    def test_rejects_reserved_subdomain(self, client, platform_admin, db_engine):
        _login_and_verify(client, platform_admin)
        resp = client.post("/super_admin/tenants/create", data={
            "company_name": "Hijack Co", "subdomain": "www",
            "admin_username": "hijack_admin", "admin_password": "password123",
            "admin_email": "hijack@test.local", "plan": "starter",
        }, follow_redirects=True)
        assert b"reserved" in resp.data.lower()
        cur = db_engine.cursor()
        cur.execute("SELECT 1 FROM att_master.tenants WHERE subdomain='www'")
        assert cur.fetchone() is None
        cur.close()
