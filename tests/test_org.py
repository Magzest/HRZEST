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

class TestGatedSignupFlow:
    """Signup is no longer instant: POST /create_org now only starts a
    pending application (blocking a duplicate company name up front) and
    emails an OTP; provision_tenant() isn't called until a platform admin
    approves the application (blueprints/platform_admin.py) after
    reviewing the uploaded KYC documents. These tests walk the real
    pipeline end-to-end rather than assuming the old single-request
    instant-provision behavior."""

    import io as _io

    _FAKE_PDF = b"%PDF-1.4\n" + b"x" * 20
    _FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 20

    def _start_application(self, client, monkeypatch, **overrides):
        import blueprints.org as org_module
        captured = {}
        monkeypatch.setattr(
            org_module, "send_org_signup_otp_email",
            lambda email, company, otp: captured.setdefault("otp", otp) or True
        )
        payload = {
            "company_name": "Gated Flow Org", "subdomain": "gated-flow-org",
            "admin_username": "gf_admin", "admin_password": "password123",
            "admin_email": "gf@test.local", "email_domain": "test.local",
        }
        payload.update(overrides)
        resp = client.post("/create_org", data=payload, follow_redirects=False)
        return resp, captured.get("otp")

    def _application_id_from_redirect(self, resp):
        location = resp.headers["Location"]
        return int(location.rsplit("=", 1)[-1])

    def _verify_otp(self, client, application_id, otp_code):
        return client.post("/create_org/verify_otp", data={
            "application_id": application_id, "otp_code": otp_code,
        }, follow_redirects=False)

    def _upload_documents(self, client, application_id):
        data = {
            "application_id": str(application_id),
            "registration_cert": (self._io.BytesIO(self._FAKE_PDF), "cert.pdf"),
            "address_proof": (self._io.BytesIO(self._FAKE_PDF), "address.pdf"),
            "visiting_card": (self._io.BytesIO(self._FAKE_PNG), "card.png"),
            "name_board_photo": (self._io.BytesIO(self._FAKE_PNG), "board.png"),
        }
        return client.post("/create_org/upload_documents", data=data,
                            content_type="multipart/form-data", follow_redirects=False)

    def _login_platform_admin(self, client):
        import time as _time
        with client.session_transaction() as sess:
            sess["platform_admin_logged_in"] = True
            sess["platform_admin_username"] = "test_platform_admin"
            sess["platform_admin_last_activity"] = _time.time()

    def _run_full_pipeline(self, client, monkeypatch, **overrides):
        """Start -> verify OTP -> upload docs, leaving the application at
        status='pending_review'. Returns application_id."""
        resp, otp = self._start_application(client, monkeypatch, **overrides)
        assert resp.status_code in (301, 302), resp.data
        application_id = self._application_id_from_redirect(resp)
        assert otp is not None, "OTP email was never sent"

        resp = self._verify_otp(client, application_id, otp)
        assert resp.status_code in (301, 302)
        assert "/create_org/upload_documents" in resp.headers["Location"]

        resp = self._upload_documents(client, application_id)
        assert resp.status_code in (301, 302)
        assert "/create_org/pending" in resp.headers["Location"]

        return application_id

    def test_full_flow_provisions_real_tenant_schema(self, client, db_engine, monkeypatch):
        from app import init_master_db
        init_master_db()

        subdomain = "e2e-gated-org"
        schema_name = "att_" + subdomain.replace("-", "_")
        _drop_schema(db_engine, schema_name)
        try:
            application_id = self._run_full_pipeline(
                client, monkeypatch, subdomain=subdomain, company_name="E2E Gated Org",
                admin_username="e2e_admin", admin_email="e2e-gated@test.local",
            )

            cur = db_engine.cursor()
            cur.execute("SELECT status FROM att_master.tenant_applications WHERE id=%s", (application_id,))
            assert cur.fetchone()[0] == "pending_review"

            self._login_platform_admin(client)
            resp = client.post(f"/super_admin/applications/{application_id}/approve", follow_redirects=False)
            assert resp.status_code in (301, 302)

            cur.execute(
                "SELECT schema_name FROM information_schema.schemata WHERE schema_name=%s", (schema_name,)
            )
            assert cur.fetchone() is not None, "tenant schema was not created"

            cur.execute("SELECT db_name, status, plan FROM att_master.tenants WHERE subdomain=%s", (subdomain,))
            row = cur.fetchone()
            assert row is not None, "tenant was not registered in att_master.tenants"
            assert row[0] == schema_name
            assert row[1] == "active"
            import utils.plan_limits as plan_limits
            assert row[2] == plan_limits.PLAN_LABEL

            cur.execute(f'SELECT username FROM "{schema_name}".admin_users WHERE username=%s', ("e2e_admin",))
            assert cur.fetchone() is not None, "admin user was not seeded into the new tenant schema"

            cur.execute("SELECT status, tenant_id FROM att_master.tenant_applications WHERE id=%s", (application_id,))
            app_row = cur.fetchone()
            assert app_row[0] == "provisioned"
            assert app_row[1] is not None
            cur.close()
        finally:
            _drop_schema(db_engine, schema_name)

    def test_subdomain_colliding_with_master_registry_schema_rejected(self, client, db_engine):
        # subdomain "master" is caught by the reserved-subdomain blocklist
        # at step 1, before any application row is even created --
        # unchanged behavior from before the gated flow.
        from app import init_master_db
        init_master_db()

        resp = client.post("/create_org", data={
            "company_name": "Evil Org", "subdomain": "master",
            "admin_username": "evil_admin", "admin_password": "password123",
            "admin_email": "evil@test.local",
        }, follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers.get("Location") == "/create_org"

        cur = db_engine.cursor()
        cur.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='att_master' AND table_name='admin_users'"
        )
        polluted = cur.fetchone() is not None
        cur.close()
        assert not polluted, "tenant schema migration leaked into the master registry schema"

    def test_duplicate_subdomain_rejected_at_approval(self, client, db_engine, monkeypatch):
        # Subdomain availability is only enforced at provision_tenant()
        # time now (approval), not at step-1 submission -- two applicants
        # could both submit the same slug, but only the first can ever be
        # approved.
        from app import init_master_db
        init_master_db()

        subdomain = "e2e-dup-org"
        schema_name = "att_" + subdomain.replace("-", "_")
        _drop_schema(db_engine, schema_name)
        try:
            app1 = self._run_full_pipeline(
                client, monkeypatch, subdomain=subdomain, company_name="Dup Org One",
                admin_username="dup_admin1", admin_email="dup1@test.local",
            )
            app2 = self._run_full_pipeline(
                client, monkeypatch, subdomain=subdomain, company_name="Dup Org Two",
                admin_username="dup_admin2", admin_email="dup2@test.local",
            )

            self._login_platform_admin(client)
            resp1 = client.post(f"/super_admin/applications/{app1}/approve", follow_redirects=False)
            assert resp1.status_code in (301, 302)

            resp2 = client.post(f"/super_admin/applications/{app2}/approve", follow_redirects=True)
            assert resp2.status_code == 200
            assert b"already taken" in resp2.data

            cur = db_engine.cursor()
            cur.execute("SELECT status FROM att_master.tenant_applications WHERE id=%s", (app2,))
            assert cur.fetchone()[0] == "pending_review", "a failed approval must not silently mark provisioned"
            cur.close()
        finally:
            _drop_schema(db_engine, schema_name)

    def test_duplicate_company_name_blocked_with_generic_message_and_alert(self, client, db_engine, monkeypatch):
        from app import init_master_db
        init_master_db()

        subdomain = "e2e-dupname-org"
        schema_name = "att_" + subdomain.replace("-", "_")
        _drop_schema(db_engine, schema_name)
        try:
            application_id = self._run_full_pipeline(
                client, monkeypatch, subdomain=subdomain, company_name="Acme Duplicate Test",
                admin_username="dupname_admin", admin_email="dupname@test.local",
            )
            self._login_platform_admin(client)
            client.post(f"/super_admin/applications/{application_id}/approve", follow_redirects=False)

            cur = db_engine.cursor()
            cur.execute("SELECT status FROM att_master.tenants WHERE subdomain=%s", (subdomain,))
            assert cur.fetchone()[0] == "active"

            # A second, unrelated registrant tries the SAME company name
            # (different case/whitespace) -- must be blocked with a
            # generic message that never reveals the real owner's details.
            resp = client.post("/create_org", data={
                "company_name": "  acme duplicate test  ", "subdomain": "some-other-slug",
                "admin_username": "impersonator", "admin_password": "password123",
                "admin_email": "impersonator@test.local", "email_domain": "impersonator.test",
            }, follow_redirects=True)
            assert resp.status_code == 200
            assert b"already" in resp.data
            assert b"dupname@test.local" not in resp.data

            cur.execute(
                "SELECT conflicting_company_name, conflicting_admin_email "
                "FROM att_master.tenant_duplicate_alerts WHERE attempted_admin_email=%s",
                ("impersonator@test.local",)
            )
            alert = cur.fetchone()
            assert alert is not None, "duplicate attempt was not recorded for platform-admin review"
            assert alert[0] == "Acme Duplicate Test"
            assert alert[1] == "dupname@test.local"
            cur.execute("DELETE FROM att_master.tenant_duplicate_alerts WHERE attempted_admin_email=%s",
                        ("impersonator@test.local",))
            db_engine.commit()
            cur.close()
        finally:
            _drop_schema(db_engine, schema_name)

    def test_otp_lockout_after_max_attempts(self, client, db_engine, monkeypatch):
        from app import init_master_db
        init_master_db()

        subdomain = "e2e-otp-lockout"
        try:
            resp, otp = self._start_application(
                client, monkeypatch, subdomain=subdomain, company_name="OTP Lockout Org",
                admin_username="lockout_admin", admin_email="lockout@test.local",
            )
            application_id = self._application_id_from_redirect(resp)
            wrong_otp = "000000" if otp != "000000" else "111111"

            for _ in range(5):
                self._verify_otp(client, application_id, wrong_otp)

            # Even the CORRECT code is now refused -- the attempt cap trips
            # regardless of what's submitted next.
            resp = self._verify_otp(client, application_id, otp)
            assert resp.status_code in (301, 302)
            assert resp.headers["Location"].startswith("/create_org/verify_otp")

            resp = client.get(f"/create_org/verify_otp?application_id={application_id}", follow_redirects=True)
            assert b"Too many incorrect attempts" in resp.data
        finally:
            cur = db_engine.cursor()
            cur.execute("DELETE FROM att_master.tenant_applications WHERE subdomain=%s", (subdomain,))
            db_engine.commit()
            cur.close()

    def test_application_rejected_by_platform_admin_never_provisions(self, client, db_engine, monkeypatch):
        from app import init_master_db
        init_master_db()

        subdomain = "e2e-reject-org"
        try:
            application_id = self._run_full_pipeline(
                client, monkeypatch, subdomain=subdomain, company_name="Reject Me Org",
                admin_username="reject_admin", admin_email="reject@test.local",
            )
            self._login_platform_admin(client)
            resp = client.post(f"/super_admin/applications/{application_id}/reject",
                                data={"reason": "Documents did not match."}, follow_redirects=False)
            assert resp.status_code in (301, 302)

            cur = db_engine.cursor()
            cur.execute("SELECT status, rejection_reason FROM att_master.tenant_applications WHERE id=%s",
                        (application_id,))
            row = cur.fetchone()
            assert row[0] == "rejected"
            assert row[1] == "Documents did not match."
            cur.execute("SELECT 1 FROM att_master.tenants WHERE subdomain=%s", (subdomain,))
            assert cur.fetchone() is None, "a rejected application must never provision a tenant"
            cur.close()
        finally:
            cur = db_engine.cursor()
            cur.execute("DELETE FROM att_master.tenant_applications WHERE subdomain=%s", (subdomain,))
            db_engine.commit()
            cur.close()
