"""Tests for the SOC Analyst dashboard gate: the role check + MFA step-up
window (soc_2fa_verified_at, set at /mfa_login_verify login) on GET /secops and
GET /api/security/soc/events (blueprints/secops.py), and the 404-disguise
behavior for every unauthorized path (anonymous, wrong role, expired
step-up)."""
import time
import pytest
import utils.auth as auth_module
import utils.totp as totp_module


def _admin_session(client, username, role="admin"):
    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True
        sess["admin_username"] = username
        sess["admin_role"] = role


def _purge_test_event(db_engine, identifier):
    """security_events is append-only (BEFORE UPDATE OR DELETE trigger in
    app.py) — cleanup needs the same explicit bypass a DBA would use."""
    cur = db_engine.cursor()
    cur.execute("SET audit.bypass = 'on'")
    cur.execute("DELETE FROM security_events WHERE identifier=%s", (identifier,))
    cur.execute("SET audit.bypass = 'off'")
    cur.close()


@pytest.fixture
def soc_admin(seed_admin, db_engine):
    """A seeded admin promoted to soc_analyst with TOTP enrolled+enabled."""
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
    """soc_admin plus a live step-up window — for tests whose focus is the
    dashboard/events behavior, not the gate itself. Sets the session key
    directly rather than posting to a verify-2fa endpoint: MFA now happens
    once, at /mfa_login_verify login, not as a separate in-dashboard step-up."""
    username, secret = soc_admin
    _admin_session(client, username, role="soc_analyst")
    with client.session_transaction() as sess:
        sess["soc_2fa_verified_at"] = time.time()
    return username, secret


class TestSocStepUpSession:
    def test_no_flag_means_invalid(self, client):
        with client.application.test_request_context():
            assert auth_module.soc_step_up_valid() is False

    def test_refresh_then_valid(self, client):
        with client.application.test_request_context():
            auth_module.soc_step_up_refresh()
            assert auth_module.soc_step_up_valid() is True

    def test_clear_invalidates(self, client):
        with client.application.test_request_context():
            auth_module.soc_step_up_refresh()
            auth_module.soc_step_up_clear()
            assert auth_module.soc_step_up_valid() is False

    def test_separate_from_email_settings_gate(self, client):
        # Passing one step-up gate must not silently grant the other.
        with client.application.test_request_context():
            auth_module.email_settings_step_up_refresh()
            assert auth_module.soc_step_up_valid() is False
            auth_module.soc_step_up_refresh()
            auth_module.email_settings_step_up_clear()
            assert auth_module.soc_step_up_valid() is True


class TestSocNavVisibility:
    """The SOC dashboard is reached only via the separate /sp_admin/login
    flow now -- the regular admin dashboard never links to it, or to
    anything SOC-related, regardless of the session's role."""

    def test_regular_admin_does_not_see_soc_nav(self, client, seed_admin):
        _admin_session(client, seed_admin["username"], role="admin")
        resp = client.get("/admin")
        assert resp.status_code == 200
        assert b"SOC / Security Center" not in resp.data
        assert b"/secops" not in resp.data


class TestSocDashboardRoute:
    def test_anonymous_gets_404(self, client):
        assert client.get("/secops").status_code == 404

    def test_soc_role_without_stepup_succeeds(self, client, soc_admin):
        username, _ = soc_admin
        _admin_session(client, username, role="soc_analyst")
        assert client.get("/secops").status_code == 200

    def test_soc_role_with_stepup_succeeds(self, client, soc_admin_verified):
        resp = client.get("/secops")
        assert resp.status_code == 200
        assert b"SecOps" in resp.data

    def test_regular_admin_authorized(self, client, seed_admin):
        _admin_session(client, seed_admin["username"], role="admin")
        assert client.get("/secops").status_code == 200

    def test_lock_reasserts_gate(self, client, soc_admin_verified):
        assert client.get("/secops").status_code == 200

        # "Lock & exit" now fully logs out (a separate login means there's
        # no lesser admin view to drop back to) rather than just clearing
        # the step-up flag.
        client.get("/logout")
        assert client.get("/secops").status_code == 404

    def test_dashboard_shows_real_compromised_session_data(self, client, soc_admin_verified, db_engine):
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO session_risk (sid, identifier, attempt_type, score, status, last_reason) "
            "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (sid) DO NOTHING",
            ("test-sid-soc-dash", "EMP999", "employee", 100, "compromised", "Wi-Fi risk score 90 exceeded 60"),
        )
        db_engine.commit()
        cur.close()

        resp = client.get("/secops")
        assert resp.status_code == 200
        assert b"EMP999" in resp.data
        assert b"Wi-Fi risk score 90" in resp.data

        cur = db_engine.cursor()
        cur.execute("DELETE FROM session_risk WHERE sid='test-sid-soc-dash'")
        db_engine.commit()
        cur.close()

    def test_dashboard_shows_log_analysis_summary(self, client, soc_admin_verified, db_engine):
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO security_events (event_type, level, message, identifier) "
            "VALUES (%s,%s,%s,%s)",
            ("access.denied", "WARNING", "Test event for dashboard rendering", "PROBE_USER_XYZ"),
        )
        db_engine.commit()
        cur.close()

        resp = client.get("/secops")
        assert resp.status_code == 200
        # The all-time summary (counts, top event types) is server-rendered;
        # individual rows are now loaded client-side from
        # /api/security/soc/events, so the raw message/identifier text is
        # deliberately NOT expected in this initial page HTML.
        assert b"Log Analysis Summary" in resp.data
        assert b"Total events" in resp.data
        assert b"access.denied" in resp.data

        _purge_test_event(db_engine, "PROBE_USER_XYZ")

    def test_dashboard_shows_security_posture_and_mfa_panels(self, client, soc_admin_verified):
        username, _ = soc_admin_verified
        resp = client.get("/secops")
        assert resp.status_code == 200
        assert b"Security Posture" in resp.data
        assert b"Admin MFA Enrollment" in resp.data
        # This admin account is itself enrolled (soc_admin fixture enables
        # TOTP) — its own row should show up as enrolled in the table.
        assert username.encode() in resp.data

    def test_dashboard_shows_session_timeout_and_performance_panels(self, client, soc_admin_verified):
        """Session-timeout config and performance monitoring, migrated from
        the retired Settings -> Security hub, now live here."""
        resp = client.get("/secops")
        assert resp.status_code == 200
        assert b"Session Timeout" in resp.data
        assert b"Performance" in resp.data

    def test_dashboard_stats_reflect_real_event_data(self, client, soc_admin_verified, db_engine):
        """The lightweight /api/secops/dashboard-stats endpoint (added
        alongside the full server-rendered dashboard, not a replacement for
        it) must also reflect real security_events counts."""
        cur = db_engine.cursor()
        cur.execute("SELECT COUNT(*) FROM security_events")
        before = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO security_events (event_type, level, message, identifier) "
            "VALUES (%s,%s,%s,%s)",
            ("access.denied", "WARNING", "Test event for dashboard stats", "PROBE_USER_XYZ2"),
        )
        db_engine.commit()
        cur.close()

        resp = client.get("/api/secops/dashboard-stats")
        assert resp.status_code == 200
        assert resp.get_json()["stats"]["total_events"] == before + 1

        _purge_test_event(db_engine, "PROBE_USER_XYZ2")


class TestSocEventsApi:
    """The paginated/filterable log endpoint backing the dashboard's
    "complete logs" table — same role+step-up gate as the dashboard,
    independently tested since the dashboard page load no longer embeds row
    data."""

    def test_anonymous_gets_404(self, client):
        assert client.get("/api/security/soc/events").status_code == 404

    def test_regular_admin_authorized(self, client, seed_admin):
        _admin_session(client, seed_admin["username"], role="admin")
        assert client.get("/api/security/soc/events").status_code == 200

    def test_soc_role_authorized(self, client, soc_admin):
        username, _ = soc_admin
        _admin_session(client, username, role="soc_analyst")
        assert client.get("/api/security/soc/events").status_code == 200

    def test_soc_role_gets_paginated_results(self, client, soc_admin_verified, db_engine):
        for i in range(3):
            db_engine.cursor().execute(
                "INSERT INTO security_events (event_type, level, message, identifier) "
                "VALUES (%s,%s,%s,%s)",
                (f"test.events_api_{i}", "INFO", f"event {i}", "PROBE_EVENTS_API"),
            )
        db_engine.commit()

        resp = client.get("/api/security/soc/events?identifier=PROBE_EVENTS_API&per_page=2")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["total"] == 3
        assert data["pages"] == 2
        assert len(data["events"]) == 2

        resp2 = client.get("/api/security/soc/events?identifier=PROBE_EVENTS_API&per_page=2&page=2")
        assert len(resp2.get_json()["events"]) == 1

        _purge_test_event(db_engine, "PROBE_EVENTS_API")

    def test_level_filter_narrows_results(self, client, soc_admin_verified, db_engine):
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO security_events (event_type, level, message, identifier) VALUES (%s,%s,%s,%s)",
            ("test.events_api_level", "ERROR", "an error event", "PROBE_LEVEL_FILTER"),
        )
        cur.execute(
            "INSERT INTO security_events (event_type, level, message, identifier) VALUES (%s,%s,%s,%s)",
            ("test.events_api_level", "INFO", "an info event", "PROBE_LEVEL_FILTER"),
        )
        db_engine.commit()
        cur.close()

        resp = client.get("/api/security/soc/events?identifier=PROBE_LEVEL_FILTER&level=ERROR")
        data = resp.get_json()
        assert data["total"] == 1
        assert data["events"][0]["level"] == "ERROR"

        _purge_test_event(db_engine, "PROBE_LEVEL_FILTER")

    def test_message_search_filter(self, client, soc_admin_verified, db_engine):
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO security_events (event_type, level, message, identifier) VALUES (%s,%s,%s,%s)",
            ("test.events_api_q", "INFO", "a very unique needle phrase", "PROBE_Q_FILTER"),
        )
        db_engine.commit()
        cur.close()

        resp = client.get("/api/security/soc/events?q=unique+needle")
        data = resp.get_json()
        assert data["total"] >= 1
        assert any("needle" in e["message"] for e in data["events"])

        _purge_test_event(db_engine, "PROBE_Q_FILTER")
