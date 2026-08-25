"""
Org blueprint tests — multi-tenant self-registration (/create_org).

Signup is open by default now (no shared-secret gate) -- Turnstile
protects it instead, and turnstile_enabled() is False in tests (no
TURNSTILE_SITE_KEY/SECRET_KEY configured), so the captcha check no-ops
here exactly like the rest of the suite's login-flow tests already rely
on. Billing is flat per-employee (utils.plan_limits.PER_EMPLOYEE_PAISE)
-- there's no plan tier to select or validate anymore.

The full provisioning path creates a real Postgres schema via
create_tenant_schema() + init_tenant_db() (which runs the entire init_db()
schema bootstrap against it) — genuinely heavy, but this is exactly the
kind of "quiet until it silently breaks" flow worth one real end-to-end
test for, with explicit cleanup (DROP SCHEMA) after.

Run with:
    python -m pytest tests/test_org.py -v
"""
import pytest


def _drop_schema(db_engine, schema_name):
    cur = db_engine.cursor()
    cur.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')
    cur.execute("DELETE FROM att_master.tenants WHERE db_name=%s", (schema_name,))
    cur.close()


# ===========================================================================
# Signup page / validation paths (no schema creation, fast)
# ===========================================================================

class TestSignupPage:
    def test_get_page_renders(self, client):
        resp = client.get("/create_org")
        assert resp.status_code == 200
        assert b"Register Your Organisation" in resp.data

    def test_page_shows_flat_per_employee_rate(self, client):
        """The flat per-employee rate used to be shown on /create_org itself
        -- the "Redesign registration page" commit dropped the marketing
        sidebar it lived in (dead pricing-display JS included). Pricing is
        now shown only on the landing page ("/"), which is where this
        checks instead."""
        import utils.plan_limits as plan_limits
        resp = client.get("/")
        assert plan_limits.format_price_inr(plan_limits.PER_EMPLOYEE_PAISE).encode() in resp.data


class TestGetStartedPage:
    """/get-started is retired -- the landing page ("/") now links directly
    to /login and /create_org instead of routing through this extra hop.
    /get-started is kept only as a redirect to "/" for old bookmarks/links.
    See TestLandingPageLinks below for the replacement coverage."""

    def test_get_page_redirects_to_landing(self, client):
        resp = client.get("/get-started", follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers["Location"].rstrip("/") in ("", "/")


class TestLandingPageLinks:
    """The apex landing page is now the SaaS entry point (login-by-subdomain
    vs register) that /get-started used to be."""

    def test_links_to_create_org_and_login(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"/create_org" in resp.data
        assert b"/login" in resp.data


class TestLeadSubmission:
    """/api/leads backs the landing page's "Request Demo" modal
    (templates/landing.html, static/landing_v2.js) for visitors not ready
    to self-register yet."""

    def test_submit_lead_stores_all_fields(self, client, db_engine):
        resp = client.post("/api/leads", json={
            "name": "Jordan Lead", "email": "jordan.lead@test.local",
            "phone": "+91 98765 43210", "company_name": "Lead Test Co",
        })
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

        cur = db_engine.cursor()
        cur.execute(
            "SELECT name, email, phone, company_name FROM att_master.leads WHERE email=%s",
            ("jordan.lead@test.local",),
        )
        row = cur.fetchone()
        assert row == ("Jordan Lead", "jordan.lead@test.local", "+91 98765 43210", "Lead Test Co")
        cur.execute("DELETE FROM att_master.leads WHERE email=%s", ("jordan.lead@test.local",))
        db_engine.commit()

    def test_missing_email_rejected(self, client):
        resp = client.post("/api/leads", json={"name": "No Email"})
        assert resp.status_code == 400
        assert resp.get_json()["ok"] is False


class TestSignupValidation:
    def test_missing_required_fields_rejected(self, client):
        resp = client.post("/create_org", data={
            "company_name": "", "subdomain": "",
        }, follow_redirects=False)
        assert resp.status_code in (301, 302)

    def test_missing_admin_email_rejected(self, client):
        # admin_email is required now (was optional before) -- needed for
        # password reset and as the tenant's primary contact.
        resp = client.post("/create_org", data={
            "company_name": "Acme", "subdomain": "acme-noemail",
            "admin_username": "admin", "admin_password": "password123",
        }, follow_redirects=False)
        assert resp.status_code in (301, 302)

    def test_invalid_admin_email_rejected(self, client):
        resp = client.post("/create_org", data={
            "company_name": "Acme", "subdomain": "acme-bademail",
            "admin_username": "admin", "admin_password": "password123",
            "admin_email": "not-an-email",
        }, follow_redirects=False)
        assert resp.status_code in (301, 302)

    def test_invalid_subdomain_format_rejected(self, client):
        resp = client.post("/create_org", data={
            "company_name": "Acme", "subdomain": "Not Valid!",
            "admin_username": "admin", "admin_password": "password123",
            "admin_email": "admin@acme.test",
        }, follow_redirects=False)
        assert resp.status_code in (301, 302)

    def test_short_password_rejected(self, client):
        resp = client.post("/create_org", data={
            "company_name": "Acme", "subdomain": "acme-test",
            "admin_username": "admin", "admin_password": "short",
            "admin_email": "admin@acme.test",
        }, follow_redirects=False)
        assert resp.status_code in (301, 302)

    @pytest.mark.parametrize("subdomain", [
        "hrms", "www", "api", "admin", "master", "super_admin",
    ])
    def test_reserved_subdomain_rejected(self, client, subdomain):
        # _resolve_tenant() (app.py) parses any 3-label host as
        # <label1>.<rest> -- registering "www" would silently hijack
        # www.hrzest.com from that point on. "hrms" stays reserved too,
        # a holdover from the old hrms.gradzest.com domain.
        resp = client.post("/create_org", data={
            "company_name": "Evil Org", "subdomain": subdomain,
            "admin_username": "evil_admin", "admin_password": "password123",
            "admin_email": "evil@test.local",
        }, follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers.get("Location") == "/create_org"


# ===========================================================================
# Full provisioning — real schema creation, one end-to-end test
# ===========================================================================

class TestPortalLinkOnSuccess:
    """After signup, the success page must show the tenant's OWN dedicated
    subdomain link -- not a redirect to /login on whatever host the
    signup form happened to be submitted from, which for a fresh company
    would never be their real subdomain until wildcard DNS resolves it."""

    def test_success_page_shows_dedicated_portal_link_no_smtp(self, client, db_engine, monkeypatch):
        import blueprints.org as org_module
        from utils.helpers import _safe_app_url
        monkeypatch.setattr(org_module, "get_email_config", lambda: None)

        from app import init_master_db
        init_master_db()

        subdomain = "e2e-portal-link"
        schema_name = "att_" + subdomain.replace("-", "_")
        _drop_schema(db_engine, schema_name)
        try:
            resp = client.post("/create_org", data={
                "company_name": "Portal Link Org", "subdomain": subdomain,
                "admin_username": "portal_admin", "admin_password": "password123",
                "admin_email": "portal@test.local", "email_domain": "test.local",
            }, follow_redirects=False)
            assert resp.status_code == 200
            # portal_url is built from _safe_app_url() (APP_URL if set, else
            # the request's own host) -- not a hardcoded production domain,
            # since that would send every dev/test/staging signup to a real
            # external host instead of wherever this app is actually running.
            assert f"{_safe_app_url()}/{subdomain}/login".encode() in resp.data
            assert b"portal_admin" in resp.data
            # No SMTP configured -- the page must degrade gracefully to
            # "bookmark this link" rather than falsely claiming an email
            # was sent.
            assert b"Bookmark this link" in resp.data
        finally:
            _drop_schema(db_engine, schema_name)

    def test_success_page_notes_email_sent_when_smtp_configured(self, client, db_engine, monkeypatch):
        import blueprints.org as org_module
        sent = []
        monkeypatch.setattr(org_module, "get_email_config", lambda: {"host": "smtp.test"})
        monkeypatch.setattr(org_module, "send_email_async",
                             lambda *a, **k: sent.append(a))

        from app import init_master_db
        init_master_db()

        subdomain = "e2e-portal-link-email"
        schema_name = "att_" + subdomain.replace("-", "_")
        _drop_schema(db_engine, schema_name)
        try:
            resp = client.post("/create_org", data={
                "company_name": "Portal Link Email Org", "subdomain": subdomain,
                "admin_username": "portal_admin2", "admin_password": "password123",
                "admin_email": "portal2@test.local", "email_domain": "test.local",
            }, follow_redirects=False)
            assert resp.status_code == 200
            assert b"We've also emailed this link to" in resp.data
            assert len(sent) == 1
            assert sent[0][0] == "portal2@test.local"
        finally:
            _drop_schema(db_engine, schema_name)


class TestFullProvisioning:
    def test_create_org_provisions_real_tenant_schema(self, client, db_engine):
        from app import init_master_db
        init_master_db()

        subdomain = "e2e-test-org"
        schema_name = "att_" + subdomain.replace("-", "_")
        _drop_schema(db_engine, schema_name)
        try:
            resp = client.post("/create_org", data={
                "company_name": "E2E Test Org",
                "subdomain": subdomain,
                "admin_username": "e2e_admin",
                "admin_password": "password123",
                "admin_email": "e2e@test.local",
                "email_domain": "test.local",
            }, follow_redirects=False)
            # Success now renders the org_created.html page directly (with
            # the tenant's dedicated portal link) instead of redirecting to
            # /login on whatever host the signup form was submitted
            # from -- that host isn't necessarily the new tenant's subdomain.
            assert resp.status_code == 200
            assert b"Organisation Created" in resp.data
            assert subdomain.encode() in resp.data

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
            import utils.plan_limits as plan_limits
            assert row[2] == plan_limits.PLAN_LABEL  # audit-trail value only, no live tier behind it

            cur.execute(f'SELECT username FROM "{schema_name}".admin_users WHERE username=%s', ("e2e_admin",))
            assert cur.fetchone() is not None, "admin user was not seeded into the new tenant schema"
            cur.close()
        finally:
            _drop_schema(db_engine, schema_name)

    def test_plan_field_in_post_is_ignored(self, client, db_engine):
        # A stray "plan" field (e.g. from an old cached client) must not
        # affect provisioning -- billing is purely employee-count-based now.
        from app import init_master_db
        init_master_db()

        subdomain = "e2e-default-plan"
        schema_name = "att_" + subdomain.replace("-", "_")
        _drop_schema(db_engine, schema_name)
        try:
            resp = client.post("/create_org", data={
                "company_name": "Default Plan Org", "subdomain": subdomain,
                "admin_username": "dp_admin", "admin_password": "password123",
                "admin_email": "dp@test.local", "plan": "not-a-real-plan",
                "email_domain": "test.local",
            }, follow_redirects=False)
            assert resp.status_code == 200
            import utils.plan_limits as plan_limits
            cur = db_engine.cursor()
            cur.execute("SELECT plan, status FROM att_master.tenants WHERE subdomain=%s", (subdomain,))
            row = cur.fetchone()
            assert row[0] == plan_limits.PLAN_LABEL
            assert row[1] == "active"
            cur.close()
        finally:
            _drop_schema(db_engine, schema_name)

    def test_subdomain_colliding_with_master_registry_schema_rejected(self, client, db_engine):
        # subdomain "master" is now caught by the reserved-subdomain
        # blocklist before ever reaching the schema-collision check --
        # kept as its own test since it's the specific vulnerability this
        # regression-guards (see TestSignupValidation's parametrized
        # reserved-subdomain test for the general case).
        from app import init_master_db
        init_master_db()

        resp = client.post("/create_org", data={
            "company_name": "Evil Org", "subdomain": "master",
            "admin_username": "evil_admin", "admin_password": "password123",
            "admin_email": "evil@test.local",
        }, follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers.get("Location") == "/create_org"

        # If the vulnerability were still present, the tenant-schema migration
        # would have run against att_master, creating an admin_users table
        # there (att_master normally only ever has `tenants`) and seeding
        # evil_admin into it.
        cur = db_engine.cursor()
        cur.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='att_master' AND table_name='admin_users'"
        )
        polluted = cur.fetchone() is not None
        cur.close()
        assert not polluted, "tenant schema migration leaked into the master registry schema"

    def test_duplicate_subdomain_rejected(self, client, db_engine):
        from app import init_master_db
        init_master_db()

        subdomain = "e2e-dup-org"
        schema_name = "att_" + subdomain.replace("-", "_")
        _drop_schema(db_engine, schema_name)
        try:
            payload = {
                "company_name": "Dup Org", "subdomain": subdomain,
                "admin_username": "dup_admin", "admin_password": "password123",
                "admin_email": "dup@test.local", "email_domain": "test.local",
            }
            r1 = client.post("/create_org", data=payload, follow_redirects=False)
            assert r1.status_code == 200
            assert b"Organisation Created" in r1.data

            r2 = client.post("/create_org", data=payload, follow_redirects=False)
            assert r2.status_code in (301, 302)
            assert r2.headers.get("Location") == "/create_org"
        finally:
            _drop_schema(db_engine, schema_name)
