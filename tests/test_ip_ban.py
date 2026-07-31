"""Tests for the application-layer IP ban: app.py's _enforce_ip_ban
before_request hook (runs before every other hook, blocking a banned source
before session/auth logic even runs) and the SOC dashboard's tactical
mitigation endpoints (blueprints/secops.py: ban-ip/unban-ip/banned-ips)."""
import datetime
import time
import pytest
import blueprints.org as org_module
import utils.totp as totp_module


def _drop_schema(db_engine, schema_name):
    cur = db_engine.cursor()
    cur.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')
    cur.execute("DELETE FROM att_master.tenants WHERE db_name=%s", (schema_name,))
    db_engine.commit()
    cur.close()


@pytest.fixture
def signup_enabled_org(client, db_engine):
    """Provisions one real tenant schema via the actual /create_org flow —
    the multi-tenant hook-ordering bug this file regression-tests is
    specifically about which physical schema a query lands in, so a mocked
    tenant wouldn't exercise it. Yields (subdomain, schema_name)."""
    from app import init_master_db
    init_master_db()

    original_secret = org_module._SIGNUP_SECRET
    org_module._SIGNUP_SECRET = "test-ip-ban-signup-secret"
    subdomain = "ipban-test-org"
    schema_name = "att_" + subdomain.replace("-", "_")
    _drop_schema(db_engine, schema_name)
    try:
        resp = client.post("/create_org", data={
            "signup_secret": org_module._SIGNUP_SECRET,
            "company_name": "IP Ban Test Org",
            "subdomain": subdomain,
            "admin_username": "ipban_admin",
            "admin_password": "password123",
        }, follow_redirects=False)
        assert resp.status_code in (301, 302), "test setup failed: org provisioning did not succeed"
        yield subdomain, schema_name
    finally:
        org_module._SIGNUP_SECRET = original_secret
        _drop_schema(db_engine, schema_name)


def _admin_session(client, username, role="admin"):
    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True
        sess["admin_username"] = username
        sess["admin_role"] = role


def _ban(db_engine, ip, reason="test", banned_by="tester", expires_at=None):
    cur = db_engine.cursor()
    cur.execute(
        "INSERT INTO banned_ips (ip, reason, banned_by, expires_at) VALUES (%s,%s,%s,%s) "
        "ON CONFLICT (ip) DO UPDATE SET reason=EXCLUDED.reason, expires_at=EXCLUDED.expires_at",
        (ip, reason, banned_by, expires_at),
    )
    db_engine.commit()
    cur.close()


def _unban(db_engine, ip):
    cur = db_engine.cursor()
    cur.execute("DELETE FROM banned_ips WHERE ip=%s", (ip,))
    db_engine.commit()
    cur.close()


@pytest.fixture
def soc_admin(seed_admin, db_engine):
    cur = db_engine.cursor()
    cur.execute("UPDATE admin_users SET role='soc_analyst' WHERE username=%s", (seed_admin["username"],))
    db_engine.commit()
    cur.close()
    secret, _ = totp_module.get_or_create_admin_totp_secret(seed_admin["username"])
    totp_module.mark_totp_enabled(seed_admin["username"])
    yield seed_admin["username"], secret
    cur = db_engine.cursor()
    cur.execute("UPDATE admin_users SET role='admin', totp_secret=NULL, totp_enabled=0 WHERE username=%s",
                (seed_admin["username"],))
    db_engine.commit()
    cur.close()


@pytest.fixture
def soc_admin_verified(client, soc_admin):
    """soc_admin plus a live step-up window, set directly rather than via a
    verify-2fa POST — MFA now happens once, at /mfa_login_verify login, not as a
    separate in-dashboard step-up (see blueprints/secops.py)."""
    username, secret = soc_admin
    _admin_session(client, username, role="soc_analyst")
    with client.session_transaction() as sess:
        sess["soc_2fa_verified_at"] = time.time()
    return username, secret


class TestEnforceIpBanHook:
    def test_banned_ip_gets_403(self, client, db_engine):
        _ban(db_engine, "203.0.113.9")
        resp = client.get("/admin_login", environ_overrides={"REMOTE_ADDR": "203.0.113.9"})
        assert resp.status_code == 403
        _unban(db_engine, "203.0.113.9")

    def test_non_banned_ip_unaffected(self, client, db_engine):
        resp = client.get("/admin_login", environ_overrides={"REMOTE_ADDR": "203.0.113.10"})
        assert resp.status_code == 200

    def test_expired_ban_does_not_block(self, client, db_engine):
        _ban(db_engine, "203.0.113.11", expires_at=datetime.datetime.now() - datetime.timedelta(minutes=1))
        resp = client.get("/admin_login", environ_overrides={"REMOTE_ADDR": "203.0.113.11"})
        assert resp.status_code == 200
        _unban(db_engine, "203.0.113.11")

    def test_permanent_ban_has_no_expiry(self, client, db_engine):
        _ban(db_engine, "203.0.113.12", expires_at=None)
        resp = client.get("/admin_login", environ_overrides={"REMOTE_ADDR": "203.0.113.12"})
        assert resp.status_code == 403
        _unban(db_engine, "203.0.113.12")

    def test_static_assets_stay_reachable_for_banned_ip(self, client, db_engine):
        _ban(db_engine, "203.0.113.13")
        resp = client.get("/static/shared.css", environ_overrides={"REMOTE_ADDR": "203.0.113.13"})
        assert resp.status_code != 403
        _unban(db_engine, "203.0.113.13")


class TestSocBanEndpoints:
    def test_anonymous_gets_404_on_all_three(self, client):
        assert client.get("/api/security/soc/banned-ips").status_code == 404
        assert client.post("/api/security/soc/ban-ip", json={"ip": "1.2.3.4"}).status_code == 404
        assert client.post("/api/security/soc/unban-ip", json={"ip": "1.2.3.4"}).status_code == 404

    def test_regular_admin_authorized(self, client, seed_admin):
        _admin_session(client, seed_admin["username"], role="admin")
        assert client.post("/api/security/soc/ban-ip", json={"ip": "1.2.3.4"}).status_code == 200

    def test_soc_role_authorized(self, client, soc_admin):
        username, _ = soc_admin
        _admin_session(client, username, role="soc_analyst")
        assert client.post("/api/security/soc/ban-ip", json={"ip": "1.2.3.4"}).status_code == 200

    def test_ban_invalid_ip_rejected(self, client, soc_admin_verified):
        resp = client.post("/api/security/soc/ban-ip", json={"ip": "not-an-ip"})
        assert resp.status_code == 400

    def test_ban_then_it_blocks_and_appears_in_list(self, client, soc_admin_verified, db_engine):
        resp = client.post("/api/security/soc/ban-ip", json={"ip": "198.51.100.5", "reason": "test ban"})
        assert resp.get_json()["ok"] is True

        listing = client.get("/api/security/soc/banned-ips").get_json()
        assert any(b["ip"] == "198.51.100.5" for b in listing["banned_ips"])

        blocked = client.get("/admin_login", environ_overrides={"REMOTE_ADDR": "198.51.100.5"})
        assert blocked.status_code == 403

        _unban(db_engine, "198.51.100.5")

    def test_unban_removes_block(self, client, soc_admin_verified, db_engine):
        _ban(db_engine, "198.51.100.6")
        resp = client.post("/api/security/soc/unban-ip", json={"ip": "198.51.100.6"})
        assert resp.get_json()["ok"] is True

        listing = client.get("/api/security/soc/banned-ips").get_json()
        assert not any(b["ip"] == "198.51.100.6" for b in listing["banned_ips"])

        # This client is already logged in (soc_admin_verified), so
        # /admin_login itself would 302 regardless of ban status — the
        # thing under test is that the ban no longer 403s, not the redirect.
        allowed = client.get("/admin_login", environ_overrides={"REMOTE_ADDR": "198.51.100.6"})
        assert allowed.status_code != 403

    def test_temporary_ban_sets_expiry(self, client, soc_admin_verified, db_engine):
        resp = client.post("/api/security/soc/ban-ip", json={"ip": "198.51.100.7", "duration_minutes": 30})
        assert resp.get_json()["ok"] is True

        cur = db_engine.cursor()
        cur.execute("SELECT expires_at FROM banned_ips WHERE ip=%s", ("198.51.100.7",))
        expires_at = cur.fetchone()[0]
        cur.close()
        assert expires_at is not None
        assert expires_at > datetime.datetime.now()

        _unban(db_engine, "198.51.100.7")


class TestMultiTenantIpBanScopesToCorrectSchema:
    """Regression test for a hook-ordering bug: _enforce_ip_ban (and
    _enforce_admin_mfa_enrollment) call get_db_connection(), which reads
    flask.g.tenant_db and falls back to the "public" schema if it isn't set
    yet (database.py). _resolve_tenant is what actually sets g.tenant_db from
    the request's Host header — it must run BEFORE both of those hooks, or
    every tenant's ban check silently queries "public".banned_ips instead of
    its own schema, making the ban a permanent no-op for every multi-tenant
    org. Uses a real provisioned tenant schema, not a mock, since the bug is
    specifically about which physical schema a query lands in."""

    def test_ban_in_tenant_schema_blocks_requests_to_that_subdomain(self, client, db_engine, signup_enabled_org):
        subdomain, schema_name = signup_enabled_org
        banned_ip = "192.0.2.55"

        cur = db_engine.cursor()
        cur.execute(
            f'INSERT INTO "{schema_name}".banned_ips (ip, reason, banned_by) VALUES (%s,%s,%s)',  # nosec B608 — schema_name comes from this test's own provisioning call above, not user input
            (banned_ip, "regression test", "tester"),
        )
        db_engine.commit()
        cur.close()

        host = f"{subdomain}.example.com"
        resp = client.get("/admin_login", headers={"Host": host},
                          environ_overrides={"REMOTE_ADDR": banned_ip})
        assert resp.status_code == 403, (
            "IP banned in the tenant's own schema was not enforced — "
            "_enforce_ip_ban likely ran before _resolve_tenant and checked "
            "the wrong (public) schema"
        )

    def test_ban_in_one_tenant_does_not_leak_to_default_schema(self, client, db_engine, signup_enabled_org):
        subdomain, schema_name = signup_enabled_org
        banned_ip = "192.0.2.56"

        cur = db_engine.cursor()
        cur.execute(
            f'INSERT INTO "{schema_name}".banned_ips (ip, reason, banned_by) VALUES (%s,%s,%s)',  # nosec B608 — same as above
            (banned_ip, "regression test", "tester"),
        )
        db_engine.commit()
        cur.close()

        # No tenant-matching Host header this time — resolves to the default
        # "public" schema, which never got this ban row.
        resp = client.get("/admin_login", environ_overrides={"REMOTE_ADDR": banned_ip})
        assert resp.status_code != 403
