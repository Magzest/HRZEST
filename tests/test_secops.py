"""Tests for blueprints/secops.py -- the dedicated SecOps / SP-Admin portal:
its own login + email-OTP MFA flow, the auth gate, and the core SIEM
log-viewing / threat-telemetry read routes.

Auth gate: reading the actual decorators in blueprints/secops.py
(_is_secops_authorized, _soc_role_or_404, _soc_session_and_stepup_or_404)
shows this portal does NOT keep a separate session namespace -- it reads
session["admin_logged_in"]/session["admin_role"], the exact same keys the
ordinary /login sets. What IS separate is a second, narrower "live step-up"
gate (session["soc_2fa_verified_at"], refreshed only by /sp_admin/login and
/mfa_login_verify) that several mutation/query APIs additionally require on
top of the shared admin_logged_in flag. Both are exercised below.

Security events are seeded through utils.security_logs.simulate_security_attack()
-- a real, already-shipped code path (the same function
/api/secops/simulate-attack calls) that writes security_events/
login_attempts/banned_ips rows synchronously -- rather than raw INSERTs or
waiting on extensions.log_security_event()'s async background-writer queue.
"""
import pytest

from utils import security_logs
from utils.auth import generate_password_hash


def _admin_session(client, seed_admin):
    """Plain admin login through the ordinary /login route -- NOT
    /sp_admin/login. Used to prove secops reads the same
    session["admin_logged_in"]/session["admin_role"] the rest of the app
    sets, rather than keeping a separate secops-only session namespace."""
    resp = client.post("/login", data={
        "identifier": seed_admin["username"], "password": seed_admin["password"],
    }, follow_redirects=True)
    assert resp.status_code == 200
    return client


def _soc_session(client, seed_admin):
    """Logs in through the dedicated /sp_admin/login route as a plain
    'admin'-role account -- the "Direct admin session login for System
    Administrator accounts" branch, which (unlike the ordinary /login)
    also calls soc_step_up_refresh(), so this session satisfies BOTH
    _is_secops_authorized() and the live step-up gate."""
    resp = client.post("/sp_admin/login", data={
        "identifier": seed_admin["username"], "password": seed_admin["password"],
    }, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/secops")
    return client


def _purge_events(db_engine, identifier):
    """security_events is append-only (a BEFORE UPDATE OR DELETE trigger
    rejects mutation unless the narrow audit.bypass GUC is set) -- same
    cleanup shape as tests/test_security_events_log.py."""
    cur = db_engine.cursor()
    cur.execute("SET audit.bypass = 'on'")
    cur.execute("DELETE FROM security_events WHERE identifier=%s", (identifier,))
    cur.execute("SET audit.bypass = 'off'")
    cur.close()


@pytest.fixture
def seed_soc_analyst(db_engine):
    """A dedicated soc_analyst-role admin account -- the role that goes
    through the email-OTP MFA branch of /sp_admin/login instead of the
    direct-login branch a plain 'admin' role takes."""
    cur = db_engine.cursor()
    cur.execute("DELETE FROM login_attempts WHERE identifier='soc_analyst_test'")
    cur.execute(
        "INSERT INTO admin_users (username, password, email, role) "
        "VALUES (%s,%s,%s,'soc_analyst') "
        "ON CONFLICT (username) DO UPDATE SET role='soc_analyst', "
        "password=EXCLUDED.password, email=EXCLUDED.email, totp_enabled=0",
        ("soc_analyst_test", generate_password_hash("Soc@12345"), "soc_analyst@test.local"),
    )
    yield {"username": "soc_analyst_test", "password": "Soc@12345", "email": "soc_analyst@test.local"}
    cur.execute("DELETE FROM admin_users WHERE username='soc_analyst_test'")
    cur.execute("DELETE FROM login_attempts WHERE identifier='soc_analyst_test'")
    cur.close()


@pytest.fixture
def seeded_bruteforce(db_engine):
    """Seeds 5 real security_events rows (plus a login_attempts lockout
    row) via the app's own simulate_security_attack() -- the same function
    POST /api/secops/simulate-attack calls -- rather than a raw INSERT."""
    identifier = "SECOPS_GAP_USER"
    ip = "203.0.113.77"
    security_logs.simulate_security_attack("bruteforce", ip, identifier)
    yield {"identifier": identifier, "ip": ip}
    _purge_events(db_engine, identifier)
    cur = db_engine.cursor()
    cur.execute("DELETE FROM login_attempts WHERE identifier=%s", (identifier,))
    cur.close()


# ── Auth gate ─────────────────────────────────────────────────────────────────

class TestSecopsAuthGate:
    def test_unauthenticated_dashboard_page_404s(self, client):
        resp = client.get("/secops")
        assert resp.status_code == 404

    def test_unauthenticated_role_gated_api_401s(self, client):
        # _is_secops_authorized()-gated routes answer with a normal 401 ...
        resp = client.get("/api/secops/dashboard-stats")
        assert resp.status_code == 401
        assert resp.get_json()["ok"] is False

    def test_unauthenticated_stepup_gated_api_404s(self, client):
        # ... while _soc_session_and_stepup_or_404()-gated routes abort
        # 404 instead, on purpose (so unauthenticated scanning gets zero
        # information about the endpoint's existence).
        resp = client.post("/api/security/soc/ban-ip", json={"ip": "1.2.3.4"})
        assert resp.status_code == 404

    def test_employee_session_is_not_secops_authorized(self, client, seed_employee):
        with client.session_transaction() as sess:
            sess["employee_id"] = seed_employee["employee_id"]
        resp = client.get("/secops")
        assert resp.status_code == 404
        resp2 = client.get("/api/secops/dashboard-stats")
        assert resp2.status_code == 401

    def test_plain_admin_login_shares_session_and_grants_dashboard_access(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.get("/secops")
        assert resp.status_code == 200
        resp2 = client.get("/api/secops/dashboard-stats")
        assert resp2.status_code == 200
        assert resp2.get_json()["ok"] is True

    def test_plain_admin_login_fails_the_live_stepup_gate(self, client, seed_admin):
        """A plain /login session never calls soc_step_up_refresh(), so it
        satisfies _is_secops_authorized() but NOT the extra live step-up
        _soc_session_and_stepup_or_404() additionally requires -- a real
        second gate layered on top of the shared admin_logged_in flag, not
        just a role check."""
        _admin_session(client, seed_admin)
        resp = client.post("/api/security/soc/ban-ip", json={"ip": "198.51.100.5"})
        assert resp.status_code == 404
        resp2 = client.get("/api/security/soc/banned-ips")
        assert resp2.status_code == 404

    def test_sp_admin_login_grants_both_gates(self, client, seed_admin):
        _soc_session(client, seed_admin)
        resp = client.get("/api/secops/dashboard-stats")
        assert resp.status_code == 200
        resp2 = client.get("/api/security/soc/banned-ips")
        assert resp2.status_code == 200

    def test_invalid_credentials_rejected(self, client, seed_admin):
        resp = client.post("/sp_admin/login", data={
            "identifier": seed_admin["username"], "password": "WrongPassword@1",
        })
        assert resp.status_code == 200
        assert b"Invalid Cybersecurity Analyst credentials" in resp.data
        with client.session_transaction() as sess:
            assert not sess.get("admin_logged_in")

    def test_unknown_identifier_rejected(self, client):
        resp = client.post("/sp_admin/login", data={
            "identifier": "does_not_exist_at_all", "password": "whatever",
        })
        assert resp.status_code == 200
        assert b"Invalid Cybersecurity Analyst credentials" in resp.data

    def test_already_logged_in_soc_session_redirects_straight_to_dashboard(self, client, seed_admin):
        _soc_session(client, seed_admin)
        resp = client.get("/sp_admin/login", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/secops")


# ── SOC analyst email-OTP MFA flow ────────────────────────────────────────────

class TestSocAnalystMfaFlow:
    def test_login_redirects_to_mfa_verify_and_issues_session_otp(self, client, seed_soc_analyst, monkeypatch):
        import blueprints.secops as secops_module
        monkeypatch.setattr(secops_module, "send_secops_mfa_qr_email", lambda *a, **k: None)

        resp = client.post("/sp_admin/login", data={
            "identifier": seed_soc_analyst["username"], "password": seed_soc_analyst["password"],
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/mfa_login_verify")
        with client.session_transaction() as sess:
            assert sess["mfa_pending"] is True
            assert sess["mfa_user"] == seed_soc_analyst["username"]
            otp = sess["mfa_otp_code"]
        assert otp and len(otp) == 6 and otp.isdigit()

    def test_correct_otp_completes_login_and_enrolls_totp(self, client, db_engine, seed_soc_analyst, monkeypatch):
        import blueprints.secops as secops_module
        monkeypatch.setattr(secops_module, "send_secops_mfa_qr_email", lambda *a, **k: None)

        client.post("/sp_admin/login", data={
            "identifier": seed_soc_analyst["username"], "password": seed_soc_analyst["password"],
        })
        with client.session_transaction() as sess:
            otp = sess["mfa_otp_code"]

        resp = client.post("/mfa_login_verify", data={"otp_code": otp}, follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/secops")
        with client.session_transaction() as sess:
            assert sess["admin_logged_in"] is True
            assert sess["admin_role"] == "soc_analyst"
            assert sess["admin_username"] == seed_soc_analyst["username"]
            assert sess.get("soc_2fa_verified_at")
            assert "mfa_pending" not in sess

        cur = db_engine.cursor()
        cur.execute("SELECT totp_enabled FROM admin_users WHERE username=%s", (seed_soc_analyst["username"],))
        assert cur.fetchone()[0] == 1
        cur.close()

    def test_wrong_otp_shows_error_and_keeps_session_pending(self, client, seed_soc_analyst, monkeypatch):
        import blueprints.secops as secops_module
        monkeypatch.setattr(secops_module, "send_secops_mfa_qr_email", lambda *a, **k: None)

        client.post("/sp_admin/login", data={
            "identifier": seed_soc_analyst["username"], "password": seed_soc_analyst["password"],
        })
        resp = client.post("/mfa_login_verify", data={"otp_code": "000000"})
        assert resp.status_code == 200
        assert b"Invalid verification code" in resp.data
        with client.session_transaction() as sess:
            assert sess.get("mfa_pending") is True
            assert not sess.get("admin_logged_in")

    def test_expired_otp_clears_session_and_shows_login_error(self, client, seed_soc_analyst, monkeypatch):
        import blueprints.secops as secops_module
        monkeypatch.setattr(secops_module, "send_secops_mfa_qr_email", lambda *a, **k: None)

        client.post("/sp_admin/login", data={
            "identifier": seed_soc_analyst["username"], "password": seed_soc_analyst["password"],
        })
        with client.session_transaction() as sess:
            sess["mfa_issued_at"] = 0  # far in the past -> expired

        resp = client.get("/mfa_login_verify")
        assert resp.status_code == 200
        assert b"code expired" in resp.data.lower()
        with client.session_transaction() as sess:
            assert not sess.get("mfa_pending")

    def test_verify_without_a_pending_login_redirects_to_sp_admin_login(self, client):
        resp = client.get("/mfa_login_verify", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/sp_admin/login")

    def test_soc_analyst_missing_email_is_rejected_before_mfa(self, client, db_engine):
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO admin_users (username, password, email, role) VALUES (%s,%s,NULL,'soc_analyst') "
            "ON CONFLICT (username) DO UPDATE SET role='soc_analyst', email=NULL, password=EXCLUDED.password",
            ("soc_no_email_test", generate_password_hash("Soc@12345")),
        )
        try:
            resp = client.post("/sp_admin/login", data={
                "identifier": "soc_no_email_test", "password": "Soc@12345",
            })
            assert resp.status_code == 200
            assert b"Invalid Cybersecurity Analyst credentials" in resp.data
            with client.session_transaction() as sess:
                assert not sess.get("mfa_pending")
        finally:
            cur.execute("DELETE FROM admin_users WHERE username='soc_no_email_test'")
            cur.close()


# ── Core SIEM log-viewing / threat-telemetry read routes ─────────────────────

class TestSiemAndThreatTelemetryReadRoutes:
    def test_siem_query_finds_seeded_event(self, client, seed_admin, seeded_bruteforce):
        _soc_session(client, seed_admin)
        resp = client.get(f"/api/secops/siem-query?user_id={seeded_bruteforce['identifier']}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["count"] >= 1
        assert any(l["user_id"] == seeded_bruteforce["identifier"] for l in data["logs"])

    def test_dashboard_stats_reflect_seeded_events(self, client, seed_admin, seeded_bruteforce):
        _soc_session(client, seed_admin)
        resp = client.get("/api/secops/dashboard-stats")
        assert resp.status_code == 200
        assert resp.get_json()["stats"]["total_events"] >= 5

    def test_soc_events_endpoint_filters_by_identifier(self, client, seed_admin, seeded_bruteforce):
        _soc_session(client, seed_admin)
        resp = client.get(f"/api/security/soc/events?identifier={seeded_bruteforce['identifier']}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] >= 5
        assert all(e["identifier"] == seeded_bruteforce["identifier"] for e in data["events"])
        assert data["events"][0]["event_type"] == "auth.bruteforce_detected"

    def test_soc_events_pagination_params_respected(self, client, seed_admin, seeded_bruteforce):
        _soc_session(client, seed_admin)
        resp = client.get(
            f"/api/security/soc/events?identifier={seeded_bruteforce['identifier']}&per_page=2&page=1"
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["per_page"] == 2
        assert len(data["events"]) == 2
        assert data["pages"] >= 3  # >= 5 seeded rows / 2 per page

    def test_soc_events_level_filter(self, client, seed_admin, seeded_bruteforce):
        _soc_session(client, seed_admin)
        resp = client.get(
            f"/api/security/soc/events?identifier={seeded_bruteforce['identifier']}&level=WARNING"
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] >= 5
        assert all(e["level"] == "WARNING" for e in data["events"])

    def test_mitre_matrix_counts_bruteforce_technique(self, client, seed_admin, seeded_bruteforce):
        _soc_session(client, seed_admin)
        resp = client.get("/api/secops/mitre-matrix")
        assert resp.status_code == 200
        matrix = resp.get_json()["matrix"]
        assert matrix["TA0001_Initial_Access"]["techniques"][2]["count"] >= 1

    def test_geo_threats_returns_structure(self, client, seed_admin):
        _soc_session(client, seed_admin)
        resp = client.get("/api/secops/geo-threats")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "threat_nodes" in data and "attack_vectors" in data

    def test_honeypot_stats_returns_structure(self, client, seed_admin):
        _soc_session(client, seed_admin)
        resp = client.get("/api/secops/honeypot-stats")
        assert resp.status_code == 200
        stats = resp.get_json()["stats"]
        assert "active_decoys" in stats

    def test_threat_logs_endpoint(self, client, seed_admin, seeded_bruteforce):
        _soc_session(client, seed_admin)
        resp = client.get("/api/secops/threat-logs")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_system_health_endpoint(self, client, seed_admin):
        _soc_session(client, seed_admin)
        resp = client.get("/api/secops/system-health")
        assert resp.status_code == 200
        assert resp.get_json()["health"]["status"] == "OPERATIONAL"

    def test_port_health_endpoint(self, client, seed_admin):
        _soc_session(client, seed_admin)
        resp = client.get("/api/secops/port-health")
        assert resp.status_code == 200
        assert isinstance(resp.get_json()["ports"], list)

    def test_port_matrix_endpoint(self, client, seed_admin):
        _soc_session(client, seed_admin)
        resp = client.get("/api/secops/port-matrix")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "ports" in data and "nmap_scans" in data

    def test_wifi_risk_endpoint(self, client, seed_admin):
        _soc_session(client, seed_admin)
        resp = client.get("/api/secops/wifi-risk")
        assert resp.status_code == 200
        assert "risk_score" in resp.get_json()["wifi"]

    def test_user_wifi_telemetry_endpoint(self, client, seed_admin):
        _soc_session(client, seed_admin)
        resp = client.get("/api/secops/user-wifi-telemetry")
        assert resp.status_code == 200
        assert isinstance(resp.get_json()["users"], list)

    def test_server_errors_endpoint(self, client, seed_admin, seeded_bruteforce):
        _soc_session(client, seed_admin)
        resp = client.get("/api/secops/server-errors")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_malware_analysis_endpoint(self, client, seed_admin):
        _soc_session(client, seed_admin)
        resp = client.get("/api/secops/malware-analysis")
        assert resp.status_code == 200
        assert resp.get_json()["telemetry"]["status"] == "ACTIVE_PROTECTION"

    def test_threat_intel_cve_endpoint_degrades_gracefully_without_table(self, client, seed_admin):
        # threat_intel_cve has no CREATE TABLE anywhere in app.py's schema
        # -- the route's own try/except degrades to an empty list rather
        # than 500ing, which is what this asserts.
        _soc_session(client, seed_admin)
        resp = client.get("/api/secops/threat-intel/cve")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["cves"] == []

    def test_threat_intel_ips_endpoint_degrades_gracefully_without_table(self, client, seed_admin):
        _soc_session(client, seed_admin)
        resp = client.get("/api/secops/threat-intel/ips")
        assert resp.status_code == 200
        assert resp.get_json()["ips"] == []

    def test_list_admins_includes_seeded_admin(self, client, seed_admin):
        _soc_session(client, seed_admin)
        resp = client.get("/api/secops/list-admins")
        assert resp.status_code == 200
        usernames = [a["username"] for a in resp.get_json()["admins"]]
        assert seed_admin["username"] in usernames

    def test_search_employees_finds_seeded_employee(self, client, seed_admin, seed_employee):
        _soc_session(client, seed_admin)
        resp = client.get(f"/api/secops/search-employees?q={seed_employee['employee_id']}")
        assert resp.status_code == 200
        ids = [e["employee_id"] for e in resp.get_json()["employees"]]
        assert seed_employee["employee_id"] in ids

    def test_ai_investigate_returns_analysis(self, client, seed_admin, seeded_bruteforce):
        _soc_session(client, seed_admin)
        resp = client.get("/api/secops/ai-investigate")
        assert resp.status_code == 200
        analysis = resp.get_json()["analysis"]
        assert "threat_title" in analysis
        assert "actionable_containment_checklist" in analysis

    def test_quarantine_files_endpoint(self, client, seed_admin):
        _soc_session(client, seed_admin)
        resp = client.get("/api/secops/quarantine/files")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True


# ── Step-up-gated mutation routes (auth-gate + effect verification) ──────────

class TestStepupGatedMutationRoutes:
    def test_ban_and_unban_ip_roundtrip(self, client, seed_admin):
        _soc_session(client, seed_admin)
        ip = "198.51.100.201"
        resp = client.post("/api/security/soc/ban-ip", json={"ip": ip, "reason": "test ban"})
        assert resp.status_code == 200

        resp2 = client.get("/api/security/soc/banned-ips")
        assert ip in [b["ip"] for b in resp2.get_json()["banned_ips"]]

        resp3 = client.post("/api/security/soc/unban-ip", json={"ip": ip})
        assert resp3.status_code == 200
        resp4 = client.get("/api/security/soc/banned-ips")
        assert ip not in [b["ip"] for b in resp4.get_json()["banned_ips"]]

    def test_ban_ip_rejects_invalid_ip(self, client, seed_admin):
        _soc_session(client, seed_admin)
        resp = client.post("/api/security/soc/ban-ip", json={"ip": "not-an-ip"})
        assert resp.status_code == 400

    def test_session_timeout_update_and_validation(self, client, seed_admin, db_engine):
        cur = db_engine.cursor()
        cur.execute("SELECT session_timeout FROM company_settings LIMIT 1")
        original = cur.fetchone()[0]
        cur.close()
        _soc_session(client, seed_admin)
        try:
            resp = client.post("/api/secops/session-timeout", json={"timeout": 45})
            assert resp.status_code == 200
            cur = db_engine.cursor()
            cur.execute("SELECT session_timeout FROM company_settings LIMIT 1")
            assert cur.fetchone()[0] == 45
            cur.close()

            resp2 = client.post("/api/secops/session-timeout", json={"timeout": 9999})
            assert resp2.status_code == 400
        finally:
            cur = db_engine.cursor()
            cur.execute("UPDATE company_settings SET session_timeout=%s", (original,))
            cur.close()

    def test_unlock_account(self, client, seed_admin, db_engine):
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO login_attempts (identifier, attempt_type, failed_count, locked_until) "
            "VALUES ('SECOPS_LOCK_TEST', 'employee', 5, NOW() + INTERVAL '1 hour') "
            "ON CONFLICT (identifier, attempt_type) DO UPDATE SET failed_count=5, "
            "locked_until=NOW() + INTERVAL '1 hour'"
        )
        cur.close()
        _soc_session(client, seed_admin)
        try:
            resp = client.post("/api/secops/unlock-account", json={"identifier": "SECOPS_LOCK_TEST"})
            assert resp.status_code == 200
            cur = db_engine.cursor()
            cur.execute("SELECT locked_until, failed_count FROM login_attempts WHERE identifier='SECOPS_LOCK_TEST'")
            row = cur.fetchone()
            cur.close()
            assert row[0] is None
            assert row[1] == 0
        finally:
            cur = db_engine.cursor()
            cur.execute("DELETE FROM login_attempts WHERE identifier='SECOPS_LOCK_TEST'")
            cur.close()

    def test_terminate_session_by_sid(self, client, seed_admin, db_engine):
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO session_risk (sid, identifier, attempt_type, score, status) "
            "VALUES ('secops-test-sid', 'SECOPS_TERM_TEST', 'admin', 90, 'compromised') "
            "ON CONFLICT (sid) DO NOTHING"
        )
        cur.close()
        _soc_session(client, seed_admin)
        try:
            resp = client.post("/api/secops/terminate-session", json={"sid": "secops-test-sid"})
            assert resp.status_code == 200
            cur = db_engine.cursor()
            cur.execute("SELECT status FROM session_risk WHERE sid='secops-test-sid'")
            assert cur.fetchone()[0] == "terminated"
            cur.close()
        finally:
            cur = db_engine.cursor()
            cur.execute("DELETE FROM session_risk WHERE sid='secops-test-sid'")
            cur.close()

    def test_terminate_session_requires_sid_or_identifier(self, client, seed_admin):
        _soc_session(client, seed_admin)
        resp = client.post("/api/secops/terminate-session", json={})
        assert resp.status_code == 400

    def test_performance_endpoint(self, client, seed_admin):
        _soc_session(client, seed_admin)
        resp = client.get("/api/secops/performance")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["db_healthy"] is True
        assert "coverage_gate_pct" in data

    def test_export_logs_returns_csv(self, client, seed_admin):
        _soc_session(client, seed_admin)
        resp = client.get("/api/secops/export-logs")
        assert resp.status_code == 200
        assert resp.mimetype == "text/csv"
        assert b"Event Type" in resp.data

    def test_emergency_lockdown_enable_updates_singleton_row_without_duplicating(
        self, client, seed_admin, db_engine
    ):
        cur = db_engine.cursor()
        cur.execute("SELECT COUNT(*) FROM company_settings")
        rows_before = cur.fetchone()[0]
        cur.execute("SELECT session_timeout FROM company_settings LIMIT 1")
        original = cur.fetchone()[0]
        cur.close()
        _soc_session(client, seed_admin)
        try:
            resp = client.post("/api/secops/emergency-lockdown", json={"enable": True})
            assert resp.status_code == 200
            assert resp.get_json()["lockdown"] is True

            cur = db_engine.cursor()
            cur.execute("SELECT COUNT(*) FROM company_settings")
            rows_after = cur.fetchone()[0]
            cur.execute("SELECT session_timeout FROM company_settings LIMIT 1")
            new_value = cur.fetchone()[0]
            cur.close()

            # Bug fix regression guard: this route used to unconditionally
            # INSERT a brand-new company_settings row (see blueprints/secops.py's
            # api_secops_emergency_lockdown()) instead of updating the
            # existing singleton -- assert the row count is unchanged.
            assert rows_after == rows_before
            assert new_value == 5
        finally:
            cur = db_engine.cursor()
            cur.execute("UPDATE company_settings SET session_timeout=%s", (original,))
            cur.close()

    def test_emergency_lockdown_disable_does_not_write(self, client, seed_admin, db_engine):
        cur = db_engine.cursor()
        cur.execute("SELECT COUNT(*) FROM company_settings")
        rows_before = cur.fetchone()[0]
        cur.close()
        _soc_session(client, seed_admin)
        resp = client.post("/api/secops/emergency-lockdown", json={"enable": False})
        assert resp.status_code == 200
        assert resp.get_json()["lockdown"] is False
        cur = db_engine.cursor()
        cur.execute("SELECT COUNT(*) FROM company_settings")
        rows_after = cur.fetchone()[0]
        cur.close()
        assert rows_after == rows_before


# ── SOAR playbooks / attack simulation ────────────────────────────────────────

class TestSoarPlaybooksAndSimulation:
    def test_simulate_attack_seeds_a_real_security_event(self, client, seed_admin, db_engine):
        _soc_session(client, seed_admin)
        try:
            resp = client.post("/api/secops/simulate-attack", json={
                "attack_type": "sqli", "ip": "203.0.113.250", "user": "SECOPS_SIM_USER",
            })
            assert resp.status_code == 200
            assert resp.get_json()["result"]["status"] == "TRIGGERED"

            cur = db_engine.cursor()
            cur.execute("SELECT 1 FROM security_events WHERE identifier='SECOPS_SIM_USER'")
            found = cur.fetchone() is not None
            cur.close()
            assert found
        finally:
            _purge_events(db_engine, "SECOPS_SIM_USER")

    def test_execute_and_history_playbook(self, client, seed_admin):
        _soc_session(client, seed_admin)
        resp = client.post("/api/secops/playbooks/execute", json={"playbook_id": "rotate_security_nonces"})
        assert resp.status_code == 200
        assert resp.get_json()["result"]["success"] is True

        resp2 = client.get("/api/secops/playbooks/history")
        assert resp2.status_code == 200
        history = resp2.get_json()["history"]
        assert any(h["playbook_id"] == "rotate_security_nonces" for h in history)

    def test_unknown_playbook_id_fails_gracefully(self, client, seed_admin):
        _soc_session(client, seed_admin)
        resp = client.post("/api/secops/playbooks/execute", json={"playbook_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is False


# ── Deception honeypot trap routes (unauthenticated by design) ──────────────

class TestHoneypotTrap:
    def test_hitting_a_decoy_path_returns_404_and_bans_the_ip(self, client, db_engine):
        fake_ip = "203.0.113.222"
        try:
            resp = client.get("/.env", environ_overrides={"REMOTE_ADDR": fake_ip})
            assert resp.status_code == 404
            assert resp.get_json()["error"] == "Resource not found"

            cur = db_engine.cursor()
            cur.execute("SELECT reason FROM banned_ips WHERE ip=%s", (fake_ip,))
            row = cur.fetchone()
            cur.close()
            assert row is not None
            assert "Honeypot" in row[0]
        finally:
            cur = db_engine.cursor()
            cur.execute("DELETE FROM banned_ips WHERE ip=%s", (fake_ip,))
            cur.close()

    def test_multiple_decoy_paths_all_trigger_404(self, client, db_engine):
        # A distinct source IP per path -- hitting the honeypot auto-bans
        # the IP (see the test above), so a *second* decoy hit from the
        # SAME IP would legitimately get a 403 from the app's own IP-ban
        # enforcement before it ever reaches this route again, not a 404
        # from the route itself.
        paths = ("/wp-admin/", "/phpmyadmin", "/backup.sql", "/actuator/health")
        fake_ips = [f"203.0.113.23{i}" for i in range(len(paths))]
        try:
            for path, ip in zip(paths, fake_ips):
                resp = client.get(path, environ_overrides={"REMOTE_ADDR": ip})
                assert resp.status_code == 404
        finally:
            cur = db_engine.cursor()
            cur.execute("DELETE FROM banned_ips WHERE ip = ANY(%s)", (fake_ips,))
            cur.close()
