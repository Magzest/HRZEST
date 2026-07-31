"""Automated Pytest Suite for SecOps & SP Admin Portal."""

import pytest
from utils.security_logs import (
    fetch_threat_logs,
    get_system_health_metrics,
    get_smtp_config,
    update_smtp_config,
)


@pytest.fixture
def soc_admin(seed_admin, db_engine):
    """A seeded admin promoted to soc_analyst -- sp_admin_login() only
    proceeds past the password check for a DB role that's already
    soc_analyst (a separate credential from the main admin login, not any
    admin account that happens to know the right TOTP code)."""
    cur = db_engine.cursor()
    cur.execute("UPDATE admin_users SET role='soc_analyst' WHERE username=%s", (seed_admin["username"],))
    db_engine.commit()
    cur.close()
    yield seed_admin
    cur = db_engine.cursor()
    cur.execute("UPDATE admin_users SET role='admin' WHERE username=%s", (seed_admin["username"],))
    db_engine.commit()
    cur.close()


def test_secops_utils_unit(db_engine):
    # Test threat log retrieval
    logs = fetch_threat_logs()
    assert isinstance(logs, list)

    # Test system health metrics
    health = get_system_health_metrics()
    assert health["status"] == "OPERATIONAL"
    assert "cpu_load" in health

    # Test SMTP config get & update
    config = get_smtp_config()
    assert "smtp_server" in config

    updated = update_smtp_config({
        "smtp_server": "smtp.secops-test.org",
        "smtp_port": 587,
        "smtp_username": "sec-alerts@secops.org",
        "alert_email": "admin@secops.org",
        "smtp_use_tls": True
    })
    assert updated is True


def test_sp_admin_login_and_mfa_flow(client, soc_admin):
    # 1. Access login page
    res = client.get("/sp_admin/login")
    assert res.status_code == 200

    # 2. Submit analyst login with the real seeded admin's credentials --
    # sp_admin_login() looks the identifier up by username, so a made-up
    # one must be rejected (no fallback to some other account's password).
    res = client.post("/sp_admin/login",
                       data={"identifier": soc_admin["username"], "password": soc_admin["password"]})
    assert res.status_code == 302
    assert "/mfa_login_verify" in res.location

    # 3. The one-time code is emailed, never returned in the response --
    # tests read it straight from the session the same way the emailed
    # code would eventually be typed in by hand. Submitting anything else
    # must be rejected.
    with client.session_transaction() as sess:
        otp_code = sess["mfa_otp_code"]
    res_mfa = client.post("/mfa_login_verify", data={"otp_code": otp_code})
    assert res_mfa.status_code == 302
    assert "/secops" in res_mfa.location


def test_mfa_login_verify_page_never_leaks_the_code(client, soc_admin):
    """The emailed OTP must never appear in the page HTML itself -- only
    typed in by the account owner after reading their email."""
    client.post("/sp_admin/login",
                data={"identifier": soc_admin["username"], "password": soc_admin["password"]})
    with client.session_transaction() as sess:
        otp_code = sess["mfa_otp_code"]
    res = client.get("/mfa_login_verify")
    assert res.status_code == 200
    assert otp_code.encode() not in res.data


def test_sp_admin_login_rejects_unknown_identifier(client, seed_admin):
    """A made-up identifier must be rejected outright, not silently
    authenticated against some other admin's stored password."""
    res = client.post("/sp_admin/login",
                       data={"identifier": "not-a-real-admin", "password": seed_admin["password"]})
    assert res.status_code == 200
    assert b"Invalid Cybersecurity Analyst credentials" in res.data


def test_sp_admin_login_allows_admin_role(client, seed_admin):
    """An admin account with valid credentials is authorized to log in to SecOps."""
    res = client.post("/sp_admin/login",
                       data={"identifier": seed_admin["username"], "password": seed_admin["password"]})
    assert res.status_code == 302
    assert "/secops" in res.location


def test_mfa_login_verify_rejects_wrong_code(client, soc_admin):
    """Any code other than the one actually issued for this session must be
    rejected -- no digit-shaped fallback."""
    client.post("/sp_admin/login",
                data={"identifier": soc_admin["username"], "password": soc_admin["password"]})
    with client.session_transaction() as sess:
        real_code = sess["mfa_otp_code"]
    wrong_code = "1" * 6 if real_code != "1" * 6 else "2" * 6
    res_mfa = client.post("/mfa_login_verify", data={"otp_code": wrong_code})
    assert res_mfa.status_code == 200
    assert b"Invalid verification code" in res_mfa.data


def test_sp_admin_login_rejects_account_with_no_email(client, soc_admin, db_engine):
    """MFA has nowhere to deliver a code without an email on file -- must
    fail closed with the same generic error as a bad password, not a
    distinct message that would leak account state to an anonymous caller."""
    cur = db_engine.cursor()
    cur.execute("UPDATE admin_users SET email=NULL WHERE username=%s", (soc_admin["username"],))
    db_engine.commit()
    cur.close()
    try:
        res = client.post("/sp_admin/login",
                           data={"identifier": soc_admin["username"], "password": soc_admin["password"]})
        assert res.status_code == 200
        assert b"Invalid Cybersecurity Analyst credentials" in res.data
    finally:
        cur = db_engine.cursor()
        cur.execute("UPDATE admin_users SET email=%s WHERE username=%s",
                    ("admin@test.local", soc_admin["username"]))
        db_engine.commit()
        cur.close()


def test_secops_api_endpoints(client, seed_admin):
    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True
        sess["admin_username"] = "sp_admin"
        sess["admin_role"] = "soc_analyst"

    # Test /api/secops/threat-logs
    res = client.get("/api/secops/threat-logs")
    assert res.status_code == 200
    assert res.get_json()["ok"] is True

    # Test /api/secops/system-health
    res = client.get("/api/secops/system-health")
    assert res.status_code == 200
    assert res.get_json()["health"]["database_status"] is not None

    # Test /api/secops/smtp-config GET & POST
    res = client.get("/api/secops/smtp-config")
    assert res.status_code == 200
    assert res.get_json()["ok"] is True

    res = client.post("/api/secops/smtp-config", json={
        "smtp_server": "smtp.secops.internal",
        "smtp_port": 2525,
        "smtp_username": "alerts@secops.internal",
        "alert_email": "soc-leads@secops.internal"
    })
    assert res.status_code == 200
    assert res.get_json()["ok"] is True

    # Test /api/secops/dashboard-stats
    res = client.get("/api/secops/dashboard-stats")
    assert res.status_code == 200
    body = res.get_json()
    assert body["ok"] is True
    for key in ("total_events", "quarantine_count", "banned_ips"):
        assert key in body["stats"]


def test_dashboard_stats_requires_soc_session(client):
    res = client.get("/api/secops/dashboard-stats")
    assert res.status_code == 401


def test_soc_analyst_account_cannot_use_regular_admin_login(client, soc_admin):
    """A dedicated SOC account is meant to be a separate credential from
    the main admin login (blueprints/auth.py's admin_login) -- it must not
    be able to obtain a full admin_required session (employees, payroll,
    everything) through the regular login form just because it knows the
    right password."""
    res = client.post("/admin_login",
                       data={"identifier": soc_admin["username"], "password": soc_admin["password"]})
    assert res.status_code == 200
    assert b"Invalid credentials" in res.data
