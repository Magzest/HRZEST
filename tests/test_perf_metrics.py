"""Tests for the real-instrumentation Performance & Quality panel:
utils/perf_metrics.py's recorder (hooked into app.py's before/after_request
on every request) and the gated route that serves it,
/api/secops/performance (blueprints/secops.py's SOC dashboard)."""
import time
import pytest
import utils.perf_metrics as perf_metrics
import utils.totp as totp_module


def _admin_session(client, username, role="admin"):
    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True
        sess["admin_username"] = username
        sess["admin_role"] = role


@pytest.fixture
def soc_admin(seed_admin, db_engine):
    """A seeded admin promoted to soc_analyst with TOTP enrolled+enabled --
    /api/secops/performance moved here from the retired Settings -> Security
    hub, so it's gated the same way the rest of the SOC dashboard is."""
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


class TestPerfMetricsRecorder:
    def test_snapshot_shape(self):
        d = perf_metrics.snapshot()
        for key in ("uptime_seconds", "requests_served", "avg_response_ms",
                    "p95_response_ms", "max_response_ms", "error_rate_pct",
                    "status_4xx_count", "status_5xx_count"):
            assert key in d

    def test_record_increments_count_and_error_buckets(self):
        before = perf_metrics.snapshot()
        perf_metrics.record(12.5, 200)
        perf_metrics.record(40.0, 404)
        perf_metrics.record(80.0, 500)
        after = perf_metrics.snapshot()
        assert after["requests_served"] == before["requests_served"] + 3
        assert after["status_4xx_count"] == before["status_4xx_count"] + 1
        assert after["status_5xx_count"] == before["status_5xx_count"] + 1

    def test_real_request_through_app_gets_recorded(self, client):
        """The app.py before/after_request hooks should record every
        non-static request automatically — this is what makes the panel
        real instrumentation rather than a static claim."""
        before = perf_metrics.snapshot()
        client.get("/healthz")
        after = perf_metrics.snapshot()
        assert after["requests_served"] == before["requests_served"] + 1

    def test_static_assets_not_recorded(self, client):
        before = perf_metrics.snapshot()
        client.get("/static/shared.min.css")
        after = perf_metrics.snapshot()
        assert after["requests_served"] == before["requests_served"]


class TestPerformanceRoute:
    def test_without_stepup_is_404(self, client, soc_admin):
        username, _ = soc_admin
        _admin_session(client, username, role="soc_analyst")
        resp = client.get("/api/secops/performance")
        assert resp.status_code == 404

    def test_with_stepup_returns_metrics(self, client, soc_admin):
        username, _ = soc_admin
        _admin_session(client, username, role="soc_analyst")
        with client.session_transaction() as sess:
            sess["soc_2fa_verified_at"] = time.time()

        resp = client.get("/api/secops/performance")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert "performance" in data
        assert "requests_served" in data["performance"]
        assert "db_pool" in data
        assert set(data["db_pool"]) == {"active", "idle", "max"}
        assert data["db_healthy"] is True
        assert data["coverage_gate_pct"] == 80

    def test_requires_login(self, client):
        resp = client.get("/api/secops/performance", follow_redirects=False)
        assert resp.status_code == 404
