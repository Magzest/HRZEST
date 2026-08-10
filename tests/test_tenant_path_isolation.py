"""
Path-based tenant resolution + cross-tenant session isolation.

Tenants are now identified by URL path (www.hrzest.com/<company-slug>/...)
via utils/tenant_routing.py's WSGI middleware, not by subdomain. Subdomains
used to make cross-tenant session leakage impossible for free (a host-only
cookie for acme.hrzest.com is never sent to beta.hrzest.com by the browser
itself); now every tenant shares one hostname, so app.py's _resolve_tenant()
has to enforce that binding itself -- session["tenant_slug"] must match the
slug in the current URL, or the session is hard-cleared. This file is the
dedicated regression coverage for that mechanism, per the migration plan.

Provisions two real tenant schemas (same heavy-but-necessary pattern as
tests/test_org.py's TestSuccessfulProvisioning), with explicit DROP SCHEMA
cleanup after each test.
"""
import pytest


def _drop_schema(db_engine, schema_name):
    cur = db_engine.cursor()
    cur.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')
    cur.execute("DELETE FROM att_master.tenants WHERE db_name=%s", (schema_name,))
    cur.close()


def _provision(client, subdomain, admin_username, admin_password):
    resp = client.post("/create_org", data={
        "company_name": f"{subdomain} Inc",
        "subdomain": subdomain,
        "admin_username": admin_username,
        "admin_password": admin_password,
        "admin_email": f"{admin_username}@test.local",
    }, follow_redirects=False)
    assert resp.status_code == 200, resp.data
    return "att_" + subdomain.replace("-", "_")


@pytest.fixture
def two_tenants(client, db_engine):
    from app import init_master_db
    init_master_db()

    slug_a, slug_b = "tpi-tenant-a", "tpi-tenant-b"
    schema_a = "att_" + slug_a.replace("-", "_")
    schema_b = "att_" + slug_b.replace("-", "_")
    _drop_schema(db_engine, schema_a)
    _drop_schema(db_engine, schema_b)
    try:
        _provision(client, slug_a, "tpi_admin_a", "password123")
        _provision(client, slug_b, "tpi_admin_b", "password123")
        # Provisioning itself resolves g.tenant_db/session["tenant_db"] as a
        # side effect (blueprints/org.py's provision_tenant -> init_tenant_db)
        # -- clear the session so the isolation tests below start from a
        # clean, logged-out slate rather than accidentally inheriting it.
        with client.session_transaction() as sess:
            sess.clear()
        yield slug_a, schema_a, slug_b, schema_b
    finally:
        _drop_schema(db_engine, schema_a)
        _drop_schema(db_engine, schema_b)


class TestPathBasedLogin:
    def test_login_under_company_slug_sets_tenant_session(self, client, two_tenants):
        slug_a, schema_a, _, _ = two_tenants
        resp = client.post(f"/{slug_a}/login", data={
            "identifier": "tpi_admin_a", "password": "password123",
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"].startswith(f"/{slug_a}/")
        with client.session_transaction() as sess:
            assert sess.get("admin_logged_in") is True
            assert sess.get("tenant_db") == schema_a
            assert sess.get("tenant_slug") == slug_a

    def test_unknown_slug_falls_through_unresolved(self, client, two_tenants):
        # A path segment that isn't a real tenant is just... not a tenant.
        # No WSGI strip happens, so this 404s (or otherwise fails) like any
        # other nonexistent route -- it must not be silently treated as a
        # valid company.
        resp = client.get("/not-a-real-company-xyz/admin", follow_redirects=False)
        assert resp.status_code in (404, 302)
        if resp.status_code == 302:
            # If it redirects (e.g. to a login page), it must not be
            # anyone's actual tenant dashboard.
            assert "not-a-real-company-xyz" not in resp.headers.get("Location", "")


class TestCrossTenantSessionIsolation:
    def test_switching_company_url_hard_clears_session(self, client, two_tenants):
        """The core security property: a session bound to company A must
        not remain usable once the browser is on company B's URL."""
        slug_a, schema_a, slug_b, schema_b = two_tenants

        client.post(f"/{slug_a}/login", data={
            "identifier": "tpi_admin_a", "password": "password123",
        }, follow_redirects=False)
        with client.session_transaction() as sess:
            assert sess.get("tenant_slug") == slug_a  # sanity check

        # Same browser/cookie jar, now requests company B's dashboard.
        resp = client.get(f"/{slug_b}/admin", follow_redirects=False)

        # Must NOT serve company A's admin dashboard under B's URL.
        assert resp.status_code == 302
        assert resp.headers["Location"].startswith(f"/{slug_b}/")

        # The stale A-bound session must be gone entirely, not just
        # "not admin_logged_in for B" -- a hard clear, per product decision.
        with client.session_transaction() as sess:
            assert not sess.get("admin_logged_in")
            assert sess.get("tenant_db") != schema_a
            assert sess.get("tenant_slug") != slug_a

    def test_matching_slug_does_not_clear_session(self, client, two_tenants):
        """Sanity check for the mismatch logic itself: repeated requests to
        the SAME company's URL must never trigger a false-positive clear."""
        slug_a, schema_a, _, _ = two_tenants
        client.post(f"/{slug_a}/login", data={
            "identifier": "tpi_admin_a", "password": "password123",
        }, follow_redirects=False)

        resp = client.get(f"/{slug_a}/admin", follow_redirects=False)
        assert resp.status_code == 200

        with client.session_transaction() as sess:
            assert sess.get("admin_logged_in") is True
            assert sess.get("tenant_slug") == slug_a

    def test_global_route_does_not_clear_tenant_session(self, client, two_tenants):
        """Requests that carry no company slug at all (marketing pages,
        health checks, token-based API calls) must not be treated as a
        mismatch -- only an actual DIFFERENT company's URL should clear."""
        slug_a, _, _, _ = two_tenants
        client.post(f"/{slug_a}/login", data={
            "identifier": "tpi_admin_a", "password": "password123",
        }, follow_redirects=False)

        resp = client.get("/healthz", follow_redirects=False)
        assert resp.status_code == 200

        with client.session_transaction() as sess:
            assert sess.get("admin_logged_in") is True
            assert sess.get("tenant_slug") == slug_a
