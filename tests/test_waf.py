"""Tests for the native signature-based WAF: utils/waf.py's pattern
detection + app.py's _waf_inspect_request before_request hook, which runs
immediately after the IP-ban check (tests/test_ip_ban.py) and before
session/CSRF logic — so these hit real routes directly, the same way
test_ip_ban.py exercises _enforce_ip_ban."""
import datetime
import pytest
import utils.waf as waf_module


def _unban(db_engine, ip):
    cur = db_engine.cursor()
    cur.execute("DELETE FROM banned_ips WHERE ip=%s", (ip,))
    db_engine.commit()
    cur.close()


class TestSqliSignature:
    @pytest.mark.parametrize("payload", [
        "' UNION SELECT username,password FROM admin_users--",
        "1 OR 1=1",
        "1' or '1'='1",
        "'; DROP TABLE employees;--",
        "1; EXEC xp_cmdshell('dir')",
        "/* comment */ UNION SELECT NULL--",
    ])
    def test_detects_sqli_payloads(self, payload):
        assert waf_module._sqli_signature(payload) is not None

    @pytest.mark.parametrize("benign", [
        "O'Brien",
        "Mary-Jane Watson-Smith",
        "Please select an option from the dropdown",
        "The order was cancelled or refunded",
        "user@example.com",
        "123 Main St, Apt #4",
    ])
    def test_does_not_flag_benign_input(self, benign):
        assert waf_module._sqli_signature(benign) is None


class TestXssSignature:
    @pytest.mark.parametrize("payload", [
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        "javascript:alert(document.cookie)",
        "<iframe src=evil.com></iframe>",
        "<svg onload=alert(1)>",
    ])
    def test_detects_xss_payloads(self, payload):
        assert waf_module._xss_signature(payload) is not None

    @pytest.mark.parametrize("benign", [
        "Please describe your on-boarding experience",
        "javascript is fun to learn",
        "click here to continue",
    ])
    def test_does_not_flag_benign_input(self, benign):
        assert waf_module._xss_signature(benign) is None


class TestPathTraversalSignature:
    @pytest.mark.parametrize("payload", [
        "../../etc/passwd",
        "..\\..\\windows\\system32",
        "%2e%2e%2fetc%2fpasswd",
        "file%00.jpg",
    ])
    def test_detects_traversal_payloads(self, payload):
        assert waf_module._path_traversal_signature(payload) is not None

    @pytest.mark.parametrize("benign", ["report_2024.pdf", "photos/summer.jpg", "a..b"])
    def test_does_not_flag_benign_input(self, benign):
        assert waf_module._path_traversal_signature(benign) is None


class TestWafBlocksRealRequests:
    """Every test below triggers a WAF block on the test client's default
    IP (127.0.0.1) — 5 of them in a row would otherwise cross
    _BREACH_THRESHOLD and auto-ban that shared IP for real, breaking every
    other test in the suite that uses the default client IP. Reset the
    breach counter and any resulting ban around each test so this class's
    own coverage doesn't poison the rest of the session."""

    @pytest.fixture(autouse=True)
    def _isolate_default_ip_breaches(self, db_engine):
        waf_module._breach_log.pop("127.0.0.1", None)
        _unban(db_engine, "127.0.0.1")
        yield
        waf_module._breach_log.pop("127.0.0.1", None)
        _unban(db_engine, "127.0.0.1")

    def test_sqli_in_query_string_blocked(self, client):
        resp = client.get("/employee_forgot_password", query_string={"next": "' UNION SELECT 1--"})
        assert resp.status_code == 403
        assert resp.get_json()["ok"] is False

    def test_xss_in_form_field_blocked(self, client):
        resp = client.post("/employee_forgot_password", data={
            "employee_id": "<script>alert(1)</script>",
        })
        assert resp.status_code == 403

    def test_sqli_in_json_body_blocked(self, client):
        resp = client.post("/csp-report", json={
            "csp-report": {"blocked-uri": "admin' OR '1'='1"},
        })
        assert resp.status_code == 403

    def test_nested_json_field_scanned(self, client):
        resp = client.post("/csp-report", json={
            "csp-report": {"nested": {"detail": "1; DROP TABLE employees;--"}},
        })
        assert resp.status_code == 403

    def test_clean_login_request_not_blocked(self, client):
        resp = client.post("/login", data={"username": "nobody", "password": "wrong"})
        assert resp.status_code != 403

    def test_static_assets_exempt(self, client):
        resp = client.get("/static/shared.css", query_string={"v": "' UNION SELECT 1--"})
        assert resp.status_code != 403

    def test_credential_check_endpoints_exempt(self, client):
        """admin_login/employee_login/api/login/api/employee/login run their
        own injection-shape detection and must degrade to a normal invalid-
        credentials response, not a WAF 403 — see app.py's _WAF_EXEMPT_PATHS
        and tests/test_auth_routes.py's
        test_injection_shaped_identifier_still_gets_invalid_credentials."""
        resp = client.post("/login", data={
            "identifier": "' OR '1'='1", "password": "x",
        }, follow_redirects=True)
        assert resp.status_code != 403
        resp = client.post("/api/login", json={"username": "admin'--", "password": "x"})
        assert resp.status_code != 403

    def test_block_is_logged(self, client, monkeypatch):
        calls = []
        import app as app_module
        monkeypatch.setattr(app_module, "log_security_event",
                            lambda event_type, message, level="WARNING", **f: calls.append((event_type, level)))
        client.get("/employee_forgot_password", query_string={"next": "<script>alert(1)</script>"})
        assert any(evt == "waf.xss_blocked" and lvl == "ERROR" for evt, lvl in calls)


class TestProgressiveAutoBan:
    def test_repeated_breaches_ban_the_ip(self, db_engine):
        ip = "198.51.100.201"
        waf_module._breach_log.pop(ip, None)
        _unban(db_engine, ip)
        try:
            for _ in range(waf_module._BREACH_THRESHOLD):
                waf_module.record_breach_and_maybe_ban(ip, "test breach")
            cur = db_engine.cursor()
            cur.execute("SELECT expires_at FROM banned_ips WHERE ip=%s", (ip,))
            row = cur.fetchone()
            cur.close()
            assert row is not None
            assert row[0] > datetime.datetime.now()
        finally:
            waf_module._breach_log.pop(ip, None)
            _unban(db_engine, ip)

    def test_below_threshold_does_not_ban(self, db_engine):
        ip = "198.51.100.202"
        waf_module._breach_log.pop(ip, None)
        _unban(db_engine, ip)
        try:
            for _ in range(waf_module._BREACH_THRESHOLD - 1):
                waf_module.record_breach_and_maybe_ban(ip, "test breach")
            cur = db_engine.cursor()
            cur.execute("SELECT 1 FROM banned_ips WHERE ip=%s", (ip,))
            assert cur.fetchone() is None
            cur.close()
        finally:
            waf_module._breach_log.pop(ip, None)
