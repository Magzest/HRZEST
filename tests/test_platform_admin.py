"""
Platform admin blueprint tests (blueprints/platform_admin.py) -- the
cross-tenant SaaS operator console at /super_admin/*.

tests/test_org.py already exercises the /super_admin/applications*
approve/reject happy paths (via its gated-signup pipeline helpers) and the
/super_admin/duplicate-alerts creation side (via a blocked duplicate
signup) -- this file deliberately does NOT re-walk those same full
pipelines. It covers everything else in the blueprint: the real
login+MFA+logout flow, the dashboard's summary counts, cost/lead/tenant
management, the applications queue/detail/document-streaming views (access
control specifically), the duplicate-alerts admin-facing list/acknowledge
flow, device inventory management, and the per-tenant support chat.

Most routes only need `_platform_admin_required` to see
session["platform_admin_logged_in"]/["platform_admin_username"] truthy --
they never look up a real att_master.platform_admins row (see
blueprints/platform_admin.py's _platform_admin_required) -- so most tests
below reuse the same session_transaction bypass tests/test_org.py's
TestGatedSignupFlow._login_platform_admin() already established. Only
TestLoginFlow, which tests the real credential+MFA path itself, needs an
actual seeded platform_admins row.

Run with:
    python -m pytest tests/test_platform_admin.py -v
"""
import io
import os
import re
import time
import tempfile

import pytest

PA_USERNAME = "pa_test_bypass_admin"


def _login_platform_admin(client, username=PA_USERNAME):
    with client.session_transaction() as sess:
        sess["platform_admin_logged_in"] = True
        sess["platform_admin_username"] = username
        sess["platform_admin_last_activity"] = time.time()


def _drop_schema(db_engine, schema_name):
    cur = db_engine.cursor()
    cur.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')
    cur.execute("DELETE FROM att_master.tenants WHERE db_name=%s", (schema_name,))
    cur.close()


# ===========================================================================
# Real login + MFA + logout flow
# ===========================================================================

class TestLoginFlow:
    LOGIN_USERNAME = "pa_real_login_admin"
    LOGIN_PASSWORD = "PaRealLogin@123"

    @pytest.fixture(autouse=True)
    def _mfa_enabled(self, client):
        """MANDATORY_PLATFORM_ADMIN_MFA has no conftest.py override (unlike
        MANDATORY_LOGIN_MFA/MANDATORY_ADMIN_MFA) -- it inherits whatever
        this environment's .env says (this repo's own .env sets it False
        for local-dev convenience). Force it True for the real login-flow
        tests below so they exercise the actual MFA step regardless of the
        environment running them, same pattern tests/test_login_mfa.py uses
        for MANDATORY_LOGIN_MFA."""
        original = client.application.config.get("MANDATORY_PLATFORM_ADMIN_MFA")
        client.application.config["MANDATORY_PLATFORM_ADMIN_MFA"] = True
        yield
        client.application.config["MANDATORY_PLATFORM_ADMIN_MFA"] = original

    @pytest.fixture
    def platform_admin_row(self, db_engine):
        from utils.auth import generate_password_hash
        cur = db_engine.cursor()
        cur.execute("DELETE FROM att_master.platform_admins WHERE username=%s", (self.LOGIN_USERNAME,))
        cur.execute(
            "INSERT INTO att_master.platform_admins (username, password, email) VALUES (%s,%s,%s)",
            (self.LOGIN_USERNAME, generate_password_hash(self.LOGIN_PASSWORD), "pa_real_login@test.local"),
        )
        yield
        cur.execute("DELETE FROM att_master.platform_admins WHERE username=%s", (self.LOGIN_USERNAME,))
        cur.close()

    def _capture_otp(self, monkeypatch):
        import blueprints.platform_admin as pa_module
        captured = {}
        monkeypatch.setattr(
            pa_module, "send_mfa_login_email",
            lambda email, username, role_label, secret, otp_code: captured.setdefault("otp", otp_code) or True,
        )
        return captured

    def test_login_page_renders(self, client):
        resp = client.get("/super_admin/login")
        assert resp.status_code == 200

    def test_already_logged_in_redirects_to_dashboard(self, client):
        _login_platform_admin(client)
        resp = client.get("/super_admin/login", follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers["Location"] == "/super_admin"

    def test_wrong_password_rejected(self, client, platform_admin_row):
        resp = client.post("/super_admin/login", data={
            "username": self.LOGIN_USERNAME, "password": "wrong-password",
        })
        assert resp.status_code == 200
        assert b"Invalid credentials." in resp.data
        with client.session_transaction() as sess:
            assert not sess.get("platform_admin_logged_in")

    def test_unknown_username_rejected(self, client):
        resp = client.post("/super_admin/login", data={
            "username": "no_such_platform_admin", "password": "whatever123",
        })
        assert resp.status_code == 200
        assert b"Invalid credentials." in resp.data

    def test_correct_password_redirects_to_mfa_verify(self, client, platform_admin_row, monkeypatch):
        captured = self._capture_otp(monkeypatch)
        resp = client.post("/super_admin/login", data={
            "username": self.LOGIN_USERNAME, "password": self.LOGIN_PASSWORD,
        }, follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers["Location"] == "/super_admin/mfa_verify"
        assert captured.get("otp"), "MFA OTP email was never 'sent'"
        with client.session_transaction() as sess:
            assert sess.get("platform_mfa_pending") is True
            assert sess.get("platform_mfa_user") == self.LOGIN_USERNAME
            assert not sess.get("platform_admin_logged_in")

    def test_mfa_verify_without_pending_session_redirects_to_login(self, client):
        resp = client.get("/super_admin/mfa_verify", follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers["Location"] == "/super_admin/login"

    def test_mfa_verify_wrong_code_rejected(self, client, platform_admin_row, monkeypatch):
        self._capture_otp(monkeypatch)
        client.post("/super_admin/login", data={
            "username": self.LOGIN_USERNAME, "password": self.LOGIN_PASSWORD,
        })
        resp = client.post("/super_admin/mfa_verify", data={"otp_code": "000000"})
        assert resp.status_code == 200
        assert b"Invalid verification code." in resp.data
        with client.session_transaction() as sess:
            assert not sess.get("platform_admin_logged_in")

    def test_mfa_verify_correct_code_completes_login(self, client, db_engine, platform_admin_row, monkeypatch):
        captured = self._capture_otp(monkeypatch)
        client.post("/super_admin/login", data={
            "username": self.LOGIN_USERNAME, "password": self.LOGIN_PASSWORD,
        })
        resp = client.post("/super_admin/mfa_verify", data={"otp_code": captured["otp"]}, follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers["Location"] == "/super_admin"
        with client.session_transaction() as sess:
            assert sess.get("platform_admin_logged_in") is True
            assert sess.get("platform_admin_username") == self.LOGIN_USERNAME
            assert sess.get("platform_admin_last_activity")

        # _complete_platform_admin_login also records a device row.
        cur = db_engine.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM att_master.user_devices WHERE owner_kind='platform_admin' AND owner_id=%s",
            (self.LOGIN_USERNAME,),
        )
        assert cur.fetchone()[0] >= 1
        cur.execute("DELETE FROM att_master.user_devices WHERE owner_kind='platform_admin' AND owner_id=%s",
                    (self.LOGIN_USERNAME,))
        cur.close()

    def test_mfa_code_expires_after_ttl(self, client, platform_admin_row, monkeypatch):
        self._capture_otp(monkeypatch)
        client.post("/super_admin/login", data={
            "username": self.LOGIN_USERNAME, "password": self.LOGIN_PASSWORD,
        })
        with client.session_transaction() as sess:
            sess["platform_mfa_issued_at"] = time.time() - 400  # > _MFA_OTP_TTL_SEC (300)
        resp = client.get("/super_admin/mfa_verify")
        assert resp.status_code == 200
        assert b"Your code expired" in resp.data
        with client.session_transaction() as sess:
            assert not sess.get("platform_mfa_pending")

    def test_logout_clears_session(self, client):
        _login_platform_admin(client)
        resp = client.post("/super_admin/logout", follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers["Location"] == "/super_admin/login"
        with client.session_transaction() as sess:
            assert not sess.get("platform_admin_logged_in")


class TestPlatformAdminRequiredGuard:
    def test_dashboard_requires_login(self, client):
        resp = client.get("/super_admin", follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers["Location"] == "/super_admin/login"

    def test_idle_timeout_clears_session_and_redirects(self, client):
        _login_platform_admin(client)
        with client.session_transaction() as sess:
            sess["platform_admin_last_activity"] = time.time() - 3600  # > 30min idle cap
        resp = client.get("/super_admin", follow_redirects=True)
        assert resp.status_code == 200
        assert b"session expired due to inactivity" in resp.data
        with client.session_transaction() as sess:
            assert not sess.get("platform_admin_logged_in")


# ===========================================================================
# Dashboard
# ===========================================================================

class TestDashboard:
    def test_dashboard_renders_for_logged_in_admin(self, client):
        _login_platform_admin(client)
        resp = client.get("/super_admin")
        assert resp.status_code == 200

    def test_dashboard_reflects_pending_application_and_alert_counts(self, client, db_engine):
        _login_platform_admin(client)
        cur = db_engine.cursor()
        cur.execute("SELECT COUNT(*) FROM att_master.tenant_applications WHERE status='pending_review'")
        before_pending = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM att_master.tenant_duplicate_alerts WHERE acknowledged=0")
        before_alerts = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO att_master.tenant_applications "
            "(company_name, subdomain, admin_username, admin_email, admin_password_hash, access_token_hash, status) "
            "VALUES (%s,%s,%s,%s,%s,%s,'pending_review') RETURNING id",
            ("Dash Count Co", "dash-count-co", "dc_admin", "dc@test.local", "hash", "tok"),
        )
        app_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO att_master.tenant_duplicate_alerts "
            "(attempted_company_name, attempted_admin_email, conflicting_tenant_id, conflicting_company_name) "
            "VALUES (%s,%s,%s,%s) RETURNING id",
            ("Dup Co", "dup@test.local", 999999, "Existing Co"),
        )
        alert_id = cur.fetchone()[0]
        try:
            resp = client.get("/super_admin")
            assert resp.status_code == 200
            m_apps = re.search(rb'Applications\s*<span[^>]*>(\d+)</span>', resp.data)
            assert m_apps, "pending-applications badge not found on dashboard"
            assert int(m_apps.group(1)) == before_pending + 1

            m_alerts = re.search(rb'Duplicate Alerts\s*<span[^>]*>(\d+)</span>', resp.data)
            assert m_alerts, "duplicate-alerts badge not found on dashboard"
            assert int(m_alerts.group(1)) == before_alerts + 1
        finally:
            cur.execute("DELETE FROM att_master.tenant_applications WHERE id=%s", (app_id,))
            cur.execute("DELETE FROM att_master.tenant_duplicate_alerts WHERE id=%s", (alert_id,))
            cur.close()


# ===========================================================================
# Costs
# ===========================================================================

class TestSetCosts:
    def test_requires_login(self, client):
        resp = client.post("/super_admin/costs", data={}, follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers["Location"] == "/super_admin/login"

    def test_valid_costs_update(self, client, db_engine):
        _login_platform_admin(client)
        cur = db_engine.cursor()
        cur.execute("SELECT monthly_aws_paise, monthly_maintenance_paise FROM att_master.platform_costs WHERE id=1")
        original = cur.fetchone()
        try:
            resp = client.post("/super_admin/costs", data={
                "monthly_aws": "123.45", "monthly_maintenance": "67.89",
            }, follow_redirects=False)
            assert resp.status_code in (301, 302)
            cur.execute("SELECT monthly_aws_paise, monthly_maintenance_paise FROM att_master.platform_costs WHERE id=1")
            row = cur.fetchone()
            assert row == (12345, 6789)
        finally:
            cur.execute(
                "UPDATE att_master.platform_costs SET monthly_aws_paise=%s, monthly_maintenance_paise=%s WHERE id=1",
                original,
            )
            cur.close()

    def test_negative_costs_rejected(self, client, db_engine):
        _login_platform_admin(client)
        cur = db_engine.cursor()
        cur.execute("SELECT monthly_aws_paise, monthly_maintenance_paise FROM att_master.platform_costs WHERE id=1")
        original = cur.fetchone()
        resp = client.post("/super_admin/costs", data={
            "monthly_aws": "-5", "monthly_maintenance": "10",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Enter valid non-negative amounts" in resp.data
        cur.execute("SELECT monthly_aws_paise, monthly_maintenance_paise FROM att_master.platform_costs WHERE id=1")
        assert cur.fetchone() == original
        cur.close()


# ===========================================================================
# Leads
# ===========================================================================

class TestSetLeadStatus:
    @pytest.fixture
    def lead_row(self, db_engine):
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO att_master.leads (name, email, company_name, status) "
            "VALUES (%s,%s,%s,'new') RETURNING id",
            ("Lead Status Test", "lead-status@test.local", "Lead Status Co"),
        )
        lead_id = cur.fetchone()[0]
        yield lead_id
        cur.execute("DELETE FROM att_master.leads WHERE id=%s", (lead_id,))
        cur.close()

    def test_requires_login(self, client, lead_row):
        resp = client.post(f"/super_admin/leads/{lead_row}/status", data={"status": "contacted"},
                            follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers["Location"] == "/super_admin/login"

    def test_valid_status_update(self, client, db_engine, lead_row):
        _login_platform_admin(client)
        resp = client.post(f"/super_admin/leads/{lead_row}/status", data={"status": "converted"},
                            follow_redirects=False)
        assert resp.status_code in (301, 302)
        cur = db_engine.cursor()
        cur.execute("SELECT status FROM att_master.leads WHERE id=%s", (lead_row,))
        assert cur.fetchone()[0] == "converted"
        cur.close()

    def test_invalid_status_rejected(self, client, db_engine, lead_row):
        _login_platform_admin(client)
        resp = client.post(f"/super_admin/leads/{lead_row}/status", data={"status": "bogus"},
                            follow_redirects=True)
        assert resp.status_code == 200
        assert b"Invalid lead status." in resp.data
        cur = db_engine.cursor()
        cur.execute("SELECT status FROM att_master.leads WHERE id=%s", (lead_row,))
        assert cur.fetchone()[0] == "new"
        cur.close()


# ===========================================================================
# Tenant creation -- the password-hashing round trip is the key regression
# this covers (provision_tenant() now takes admin_password_hash, not
# plaintext -- a signature change platform_admin_create_tenant() must hash
# for correctly).
# ===========================================================================

class TestCreateTenant:
    def test_requires_login(self, client):
        resp = client.post("/super_admin/tenants/create", data={}, follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers["Location"] == "/super_admin/login"

    def test_create_tenant_hashes_password_and_admin_can_log_in(self, client, db_engine):
        from app import init_master_db
        init_master_db()
        _login_platform_admin(client)

        subdomain = "sa-create-tenant"
        schema_name = "att_" + subdomain.replace("-", "_")
        _drop_schema(db_engine, schema_name)
        try:
            resp = client.post("/super_admin/tenants/create", data={
                "company_name": "SA Create Tenant Co",
                "subdomain": subdomain,
                "admin_username": "sact_admin",
                "admin_password": "SactPass@123",
                "admin_email": "sact@test.local",
                "payment_option": "manual",
                "email_domain": "test.local",
            }, follow_redirects=False)
            assert resp.status_code in (301, 302), resp.data

            cur = db_engine.cursor()
            cur.execute("SELECT db_name, status FROM att_master.tenants WHERE subdomain=%s", (subdomain,))
            row = cur.fetchone()
            assert row is not None, "tenant was not registered"
            assert row[0] == schema_name
            assert row[1] == "active"

            cur.execute(f'SELECT password FROM "{schema_name}".admin_users WHERE username=%s', ("sact_admin",))
            stored_hash = cur.fetchone()[0]
            # Never the plaintext password itself, and looks like a real
            # bcrypt hash -- catches a regression back to passing plaintext
            # straight through to provision_tenant().
            assert stored_hash != "SactPass@123"
            assert stored_hash.startswith("$2")
            cur.close()

            # The actual regression check: the submitted password must
            # round-trip through whatever hash got stored.
            login_resp = client.post(f"/{subdomain}/login", data={
                "identifier": "sact_admin", "password": "SactPass@123",
            }, follow_redirects=False)
            assert login_resp.status_code in (301, 302), login_resp.data
            assert login_resp.headers["Location"].startswith(f"/{subdomain}/")
            with client.session_transaction() as sess:
                assert sess.get("admin_logged_in") is True
                assert sess.get("admin_username") == "sact_admin"
        finally:
            _drop_schema(db_engine, schema_name)

    def test_invalid_fields_rejected_without_provisioning(self, client, db_engine):
        _login_platform_admin(client)
        resp = client.post("/super_admin/tenants/create", data={
            "company_name": "Bad Co",
            "subdomain": "super_admin",  # reserved
            "admin_username": "bad_admin",
            "admin_password": "password123",
            "admin_email": "bad@test.local",
        }, follow_redirects=True)
        assert resp.status_code == 200
        cur = db_engine.cursor()
        cur.execute("SELECT 1 FROM att_master.tenants WHERE subdomain='super_admin'")
        assert cur.fetchone() is None
        cur.close()


# ===========================================================================
# Tenant status (activate/suspend)
# ===========================================================================

class TestTenantStatus:
    @pytest.fixture
    def tenant_row(self, db_engine):
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO att_master.tenants (company_name, subdomain, db_name, status) "
            "VALUES (%s,%s,%s,'active') RETURNING id",
            ("Status Test Co", "status-test-co", "att_status_test_co"),
        )
        tenant_id = cur.fetchone()[0]
        yield tenant_id
        cur.execute("DELETE FROM att_master.tenants WHERE id=%s", (tenant_id,))
        cur.close()

    def test_requires_login(self, client, tenant_row):
        resp = client.post(f"/super_admin/tenants/{tenant_row}/status", data={"status": "suspended"},
                            follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers["Location"] == "/super_admin/login"

    def test_suspend_and_reactivate(self, client, db_engine, tenant_row):
        _login_platform_admin(client)
        resp = client.post(f"/super_admin/tenants/{tenant_row}/status", data={"status": "suspended"},
                            follow_redirects=False)
        assert resp.status_code in (301, 302)
        cur = db_engine.cursor()
        cur.execute("SELECT status FROM att_master.tenants WHERE id=%s", (tenant_row,))
        assert cur.fetchone()[0] == "suspended"

        resp = client.post(f"/super_admin/tenants/{tenant_row}/status", data={"status": "active"},
                            follow_redirects=False)
        assert resp.status_code in (301, 302)
        cur.execute("SELECT status FROM att_master.tenants WHERE id=%s", (tenant_row,))
        assert cur.fetchone()[0] == "active"
        cur.close()

    def test_invalid_status_rejected(self, client, db_engine, tenant_row):
        _login_platform_admin(client)
        resp = client.post(f"/super_admin/tenants/{tenant_row}/status", data={"status": "deleted"},
                            follow_redirects=True)
        assert resp.status_code == 200
        assert b"Invalid status." in resp.data
        cur = db_engine.cursor()
        cur.execute("SELECT status FROM att_master.tenants WHERE id=%s", (tenant_row,))
        assert cur.fetchone()[0] == "active"
        cur.close()


# ===========================================================================
# Applications queue / detail / document streaming
# (approve/reject happy paths are covered by tests/test_org.py already --
# this focuses on the queue list, detail view, and document access control.)
# ===========================================================================

class TestApplicationsQueueAndDetail:
    @pytest.fixture
    def application_row(self, db_engine):
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO att_master.tenant_applications "
            "(company_name, subdomain, admin_username, admin_email, admin_password_hash, access_token_hash, status) "
            "VALUES (%s,%s,%s,%s,%s,%s,'pending_review') RETURNING id",
            ("Queue Test Co", "queue-test-co", "qt_admin", "qt@test.local", "hash", "tok"),
        )
        app_id = cur.fetchone()[0]
        yield app_id
        cur.execute("DELETE FROM att_master.tenant_applications WHERE id=%s", (app_id,))
        cur.close()

    def test_queue_requires_login(self, client):
        resp = client.get("/super_admin/applications", follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers["Location"] == "/super_admin/login"

    def test_queue_lists_pending_application(self, client, application_row):
        _login_platform_admin(client)
        resp = client.get("/super_admin/applications")
        assert resp.status_code == 200
        assert b"Queue Test Co" in resp.data

    def test_queue_default_filter_excludes_rejected(self, client, db_engine, application_row):
        _login_platform_admin(client)
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO att_master.tenant_applications "
            "(company_name, subdomain, admin_username, admin_email, admin_password_hash, access_token_hash, status) "
            "VALUES (%s,%s,%s,%s,%s,%s,'rejected') RETURNING id",
            ("Rejected Queue Co", "rejected-queue-co", "rq_admin", "rq@test.local", "hash", "tok"),
        )
        rejected_id = cur.fetchone()[0]
        try:
            resp = client.get("/super_admin/applications")
            assert resp.status_code == 200
            assert b"Queue Test Co" in resp.data
            assert b"Rejected Queue Co" not in resp.data

            resp_all = client.get("/super_admin/applications?status=all")
            assert resp_all.status_code == 200
            assert b"Queue Test Co" in resp_all.data
            assert b"Rejected Queue Co" in resp_all.data
        finally:
            cur.execute("DELETE FROM att_master.tenant_applications WHERE id=%s", (rejected_id,))
            cur.close()

    def test_detail_requires_login(self, client, application_row):
        resp = client.get(f"/super_admin/applications/{application_row}", follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers["Location"] == "/super_admin/login"

    def test_detail_shows_application(self, client, application_row):
        _login_platform_admin(client)
        resp = client.get(f"/super_admin/applications/{application_row}")
        assert resp.status_code == 200
        assert b"Queue Test Co" in resp.data

    def test_detail_unknown_id_flashes_and_redirects(self, client):
        _login_platform_admin(client)
        resp = client.get("/super_admin/applications/999999999", follow_redirects=True)
        assert resp.status_code == 200
        assert b"Application not found." in resp.data


class TestApplicationDocument:
    @pytest.fixture
    def application_with_doc(self, db_engine):
        fd, path = tempfile.mkstemp(suffix=".pdf")
        with os.fdopen(fd, "wb") as f:
            f.write(b"%PDF-1.4 fake certificate contents")

        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO att_master.tenant_applications "
            "(company_name, subdomain, admin_username, admin_email, admin_password_hash, access_token_hash, "
            "status, doc_registration_cert) "
            "VALUES (%s,%s,%s,%s,%s,%s,'pending_review',%s) RETURNING id",
            ("Doc Test Co", "doc-test-co", "dt_admin", "dt@test.local", "hash", "tok", path),
        )
        app_id = cur.fetchone()[0]
        yield app_id, path
        cur.execute("DELETE FROM att_master.tenant_applications WHERE id=%s", (app_id,))
        cur.close()
        try:
            os.remove(path)
        except OSError:
            pass

    def test_document_route_requires_login(self, client, application_with_doc):
        app_id, _path = application_with_doc
        resp = client.get(f"/super_admin/applications/{app_id}/documents/registration_cert",
                           follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers["Location"] == "/super_admin/login"

    def test_valid_doc_kind_streams_file_from_db_row(self, client, application_with_doc):
        _login_platform_admin(client)
        app_id, _path = application_with_doc
        resp = client.get(f"/super_admin/applications/{app_id}/documents/registration_cert")
        assert resp.status_code == 200
        assert b"fake certificate contents" in resp.data

    def test_path_cannot_be_overridden_by_client_supplied_data(self, client, application_with_doc):
        """The document path always comes from the DB row for the given
        doc_kind -- there is no request field the client could substitute
        an arbitrary path into. Confirm extra client-supplied params are
        simply ignored and the DB-resident file is still what's served."""
        _login_platform_admin(client)
        app_id, _path = application_with_doc
        resp = client.get(
            f"/super_admin/applications/{app_id}/documents/registration_cert?path=/etc/passwd",
            data={"path": "/etc/passwd", "doc_registration_cert": "/etc/passwd"},
        )
        assert resp.status_code == 200
        assert b"fake certificate contents" in resp.data

    @pytest.mark.parametrize("bad_doc_kind", ["passport", "resume", "..", "registration_cert.."])
    def test_doc_kind_outside_whitelist_rejected(self, client, application_with_doc, bad_doc_kind):
        _login_platform_admin(client)
        app_id, _path = application_with_doc
        resp = client.get(f"/super_admin/applications/{app_id}/documents/{bad_doc_kind}",
                           follow_redirects=True)
        assert resp.status_code == 200
        assert b"Invalid document type." in resp.data

    def test_doc_kind_with_path_separator_never_reaches_the_view(self, client, application_with_doc):
        """doc_kind containing a slash can't even match Flask's <doc_kind>
        route converter -- confirming this doesn't fall through to some
        other route that would treat it as a filesystem path."""
        _login_platform_admin(client)
        app_id, _path = application_with_doc
        resp = client.get(f"/super_admin/applications/{app_id}/documents/../../etc/passwd")
        assert resp.status_code == 404

    def test_document_not_uploaded_flashes_not_found(self, client, application_with_doc):
        _login_platform_admin(client)
        app_id, _path = application_with_doc
        # doc_address_proof was never set on this application row.
        resp = client.get(f"/super_admin/applications/{app_id}/documents/address_proof",
                           follow_redirects=True)
        assert resp.status_code == 200
        assert b"Document not found." in resp.data


class TestApplicationApproveRejectEdgeCases:
    """approve/reject happy paths are covered end-to-end in
    tests/test_org.py -- these only cover states that file doesn't."""

    def test_approve_unknown_application(self, client):
        _login_platform_admin(client)
        resp = client.post("/super_admin/applications/999999999/approve", follow_redirects=True)
        assert resp.status_code == 200
        assert b"Application not found." in resp.data

    def test_approve_application_not_pending_review_rejected(self, client, db_engine):
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO att_master.tenant_applications "
            "(company_name, subdomain, admin_username, admin_email, admin_password_hash, access_token_hash, status) "
            "VALUES (%s,%s,%s,%s,%s,%s,'rejected') RETURNING id",
            ("Already Rejected Co", "already-rejected-co", "ar_admin", "ar@test.local", "hash", "tok"),
        )
        app_id = cur.fetchone()[0]
        try:
            _login_platform_admin(client)
            resp = client.post(f"/super_admin/applications/{app_id}/approve", follow_redirects=True)
            assert resp.status_code == 200
            assert b"awaiting review" in resp.data
            cur.execute("SELECT status FROM att_master.tenant_applications WHERE id=%s", (app_id,))
            assert cur.fetchone()[0] == "rejected"
        finally:
            cur.execute("DELETE FROM att_master.tenant_applications WHERE id=%s", (app_id,))
            cur.close()

    def test_reject_unknown_application(self, client):
        _login_platform_admin(client)
        resp = client.post("/super_admin/applications/999999999/reject", data={"reason": "no"},
                            follow_redirects=True)
        assert resp.status_code == 200
        assert b"Application not found." in resp.data


# ===========================================================================
# Duplicate alerts -- admin-facing list/acknowledge flow.
# (Creation-side coverage -- a blocked duplicate signup writing this row --
# lives in tests/test_org.py.)
# ===========================================================================

class TestDuplicateAlerts:
    @pytest.fixture
    def alert_row(self, db_engine):
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO att_master.tenant_duplicate_alerts "
            "(attempted_company_name, attempted_admin_email, conflicting_tenant_id, conflicting_company_name) "
            "VALUES (%s,%s,%s,%s) RETURNING id",
            ("Acme Impersonator", "impersonator@test.local", 999999, "Acme Real Co"),
        )
        alert_id = cur.fetchone()[0]
        yield alert_id
        cur.execute("DELETE FROM att_master.tenant_duplicate_alerts WHERE id=%s", (alert_id,))
        cur.close()

    def test_list_requires_login(self, client):
        resp = client.get("/super_admin/duplicate-alerts", follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers["Location"] == "/super_admin/login"

    def test_list_shows_alert(self, client, alert_row):
        _login_platform_admin(client)
        resp = client.get("/super_admin/duplicate-alerts")
        assert resp.status_code == 200
        assert b"Acme Impersonator" in resp.data
        assert b"Acme Real Co" in resp.data

    def test_acknowledge_requires_login(self, client, alert_row):
        resp = client.post(f"/super_admin/duplicate-alerts/{alert_row}/acknowledge", follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers["Location"] == "/super_admin/login"

    def test_acknowledge_marks_alert(self, client, db_engine, alert_row):
        _login_platform_admin(client, username="ack_platform_admin")
        resp = client.post(f"/super_admin/duplicate-alerts/{alert_row}/acknowledge", follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers["Location"] == "/super_admin/duplicate-alerts"

        cur = db_engine.cursor()
        cur.execute(
            "SELECT acknowledged, acknowledged_by FROM att_master.tenant_duplicate_alerts WHERE id=%s",
            (alert_row,),
        )
        row = cur.fetchone()
        assert row[0] == 1
        assert row[1] == "ack_platform_admin"
        cur.close()


# ===========================================================================
# Device inventory management (att_master.user_devices)
# ===========================================================================

class TestDevices:
    DEVICE_USER = "pa_device_test_admin"

    def test_list_requires_login(self, client):
        resp = client.get("/super_admin/devices", follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers["Location"] == "/super_admin/login"

    def test_list_returns_only_this_admins_devices(self, client, db_engine):
        import secrets
        cur = db_engine.cursor()
        cur.execute("DELETE FROM att_master.user_devices WHERE owner_kind='platform_admin' AND owner_id=%s",
                    (self.DEVICE_USER,))
        cur.execute(
            "INSERT INTO att_master.user_devices (owner_kind, owner_id, device_token, kind, device_name) "
            "VALUES ('platform_admin', %s, %s, 'login', 'Chrome on Windows') RETURNING id",
            (self.DEVICE_USER, secrets.token_hex(24)),
        )
        device_id = cur.fetchone()[0]
        try:
            _login_platform_admin(client, username=self.DEVICE_USER)
            resp = client.get("/super_admin/devices")
            assert resp.status_code == 200
            payload = resp.get_json()
            assert payload["ok"] is True
            assert any(d["id"] == device_id for d in payload["devices"])
        finally:
            cur.execute("DELETE FROM att_master.user_devices WHERE id=%s", (device_id,))
            cur.close()

    def test_rename_requires_login(self, client):
        resp = client.post("/super_admin/devices/1/rename", json={"name": "x"}, follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers["Location"] == "/super_admin/login"

    def test_rename_device(self, client, db_engine):
        import secrets
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO att_master.user_devices (owner_kind, owner_id, device_token, kind, device_name) "
            "VALUES ('platform_admin', %s, %s, 'login', 'Old Name') RETURNING id",
            (self.DEVICE_USER, secrets.token_hex(24)),
        )
        device_id = cur.fetchone()[0]
        try:
            _login_platform_admin(client, username=self.DEVICE_USER)
            resp = client.post(f"/super_admin/devices/{device_id}/rename", json={"name": "My Laptop"})
            assert resp.status_code == 200
            assert resp.get_json()["ok"] is True
            cur.execute("SELECT device_name FROM att_master.user_devices WHERE id=%s", (device_id,))
            assert cur.fetchone()[0] == "My Laptop"
        finally:
            cur.execute("DELETE FROM att_master.user_devices WHERE id=%s", (device_id,))
            cur.close()

    def test_rename_another_admins_device_fails(self, client, db_engine):
        import secrets
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO att_master.user_devices (owner_kind, owner_id, device_token, kind, device_name) "
            "VALUES ('platform_admin', 'someone_else_pa', %s, 'login', 'Other Name') RETURNING id",
            (secrets.token_hex(24),),
        )
        device_id = cur.fetchone()[0]
        try:
            _login_platform_admin(client, username=self.DEVICE_USER)
            resp = client.post(f"/super_admin/devices/{device_id}/rename", json={"name": "Hijacked"})
            assert resp.status_code == 200
            assert resp.get_json()["ok"] is False
            cur.execute("SELECT device_name FROM att_master.user_devices WHERE id=%s", (device_id,))
            assert cur.fetchone()[0] == "Other Name"
        finally:
            cur.execute("DELETE FROM att_master.user_devices WHERE id=%s", (device_id,))
            cur.close()

    def test_revoke_requires_login(self, client):
        resp = client.post("/super_admin/devices/1/revoke", follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers["Location"] == "/super_admin/login"

    def test_revoke_device_removes_it_from_list(self, client, db_engine):
        import secrets
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO att_master.user_devices (owner_kind, owner_id, device_token, kind, device_name) "
            "VALUES ('platform_admin', %s, %s, 'login', 'To Revoke') RETURNING id",
            (self.DEVICE_USER, secrets.token_hex(24)),
        )
        device_id = cur.fetchone()[0]
        try:
            _login_platform_admin(client, username=self.DEVICE_USER)
            resp = client.post(f"/super_admin/devices/{device_id}/revoke")
            assert resp.status_code == 200
            assert resp.get_json()["ok"] is True
            cur.execute("SELECT is_revoked FROM att_master.user_devices WHERE id=%s", (device_id,))
            assert cur.fetchone()[0] == 1
        finally:
            cur.execute("DELETE FROM att_master.user_devices WHERE id=%s", (device_id,))
            cur.close()

    def test_add_and_delete_asset_device(self, client, db_engine):
        _login_platform_admin(client, username=self.DEVICE_USER)
        resp = client.post("/super_admin/devices/asset", json={
            "device_name": "Office Laptop #3", "asset_model": "Dell Latitude", "asset_serial": "SN12345",
        })
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["ok"] is True
        asset_id = payload["id"]
        assert asset_id is not None

        cur = db_engine.cursor()
        try:
            cur.execute("SELECT kind, device_name, asset_model, asset_serial FROM att_master.user_devices WHERE id=%s",
                        (asset_id,))
            row = cur.fetchone()
            assert row == ("asset", "Office Laptop #3", "Dell Latitude", "SN12345")

            del_resp = client.post(f"/super_admin/devices/asset/{asset_id}/delete")
            assert del_resp.status_code == 200
            assert del_resp.get_json()["ok"] is True
            cur.execute("SELECT 1 FROM att_master.user_devices WHERE id=%s", (asset_id,))
            assert cur.fetchone() is None
        finally:
            cur.execute("DELETE FROM att_master.user_devices WHERE id=%s", (asset_id,))
            cur.close()

    def test_add_asset_device_requires_login(self, client):
        resp = client.post("/super_admin/devices/asset", json={"device_name": "x"}, follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers["Location"] == "/super_admin/login"

    def test_add_asset_device_missing_name_fails(self, client):
        _login_platform_admin(client, username=self.DEVICE_USER)
        resp = client.post("/super_admin/devices/asset", json={"device_name": "  "})
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["ok"] is False
        assert payload["id"] is None

    def test_delete_asset_device_requires_login(self, client):
        resp = client.post("/super_admin/devices/asset/1/delete", follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers["Location"] == "/super_admin/login"


# ===========================================================================
# Support chat with a tenant (att_master.chat_messages)
# ===========================================================================

class TestChat:
    @pytest.fixture
    def tenant_row(self, db_engine):
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO att_master.tenants (company_name, subdomain, db_name, status) "
            "VALUES (%s,%s,%s,'active') RETURNING id",
            ("Chat Test Co", "chat-test-co", "att_chat_test_co"),
        )
        tenant_id = cur.fetchone()[0]
        yield tenant_id
        cur.execute("DELETE FROM att_master.chat_messages WHERE tenant_schema='att_chat_test_co'")
        cur.execute("DELETE FROM att_master.tenants WHERE id=%s", (tenant_id,))
        cur.close()

    def test_messages_requires_login(self, client, tenant_row):
        resp = client.get(f"/super_admin/chat/{tenant_row}/messages", follow_redirects=False)
        assert resp.status_code in (301, 302)
        assert resp.headers["Location"] == "/super_admin/login"

    def test_messages_unknown_tenant_404s(self, client):
        _login_platform_admin(client)
        resp = client.get("/super_admin/chat/999999999/messages")
        assert resp.status_code == 404
        assert resp.get_json()["ok"] is False

    def test_send_unknown_tenant_404s(self, client):
        _login_platform_admin(client)
        resp = client.post("/super_admin/chat/999999999/send", json={"message": "hi"})
        assert resp.status_code == 404
        assert resp.get_json()["ok"] is False

    def test_send_and_list_messages(self, client, tenant_row):
        _login_platform_admin(client, username="chat_platform_admin")
        send_resp = client.post(f"/super_admin/chat/{tenant_row}/send", json={"message": "Hello from support"})
        assert send_resp.status_code == 200
        assert send_resp.get_json()["ok"] is True

        list_resp = client.get(f"/super_admin/chat/{tenant_row}/messages")
        assert list_resp.status_code == 200
        payload = list_resp.get_json()
        assert payload["ok"] is True
        assert payload["company_name"] == "Chat Test Co"
        assert any(m["message"] == "Hello from support" and m["sender_kind"] == "platform_admin"
                   for m in payload["messages"])

    def test_send_empty_message_rejected(self, client, tenant_row):
        _login_platform_admin(client)
        resp = client.post(f"/super_admin/chat/{tenant_row}/send", json={"message": "   "})
        assert resp.status_code == 400
        assert resp.get_json()["ok"] is False
