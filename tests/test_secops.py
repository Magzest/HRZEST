"""Automated Pytest Suite for SecOps & SP Admin Portal."""

import pyotp
import pytest
from utils.security_logs import (
    fetch_threat_logs,
    get_system_health_metrics,
    get_smtp_config,
    update_smtp_config,
)
from utils.totp import get_or_create_admin_totp_secret


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
    assert "/sp_admin/mfa" in res.location

    # 3. Submit a real TOTP code for that account's secret -- the route
    # must reject anything else, including any bare 6-digit string.
    secret, _ = get_or_create_admin_totp_secret(soc_admin["username"])
    valid_code = pyotp.TOTP(secret).now()
    res_mfa = client.post("/sp_admin/mfa", data={"totp_code": valid_code})
    assert res_mfa.status_code == 302
    assert "/secops" in res_mfa.location


def test_sp_admin_login_rejects_unknown_identifier(client, seed_admin):
    """A made-up identifier must be rejected outright, not silently
    authenticated against some other admin's stored password."""
    res = client.post("/sp_admin/login",
                       data={"identifier": "not-a-real-admin", "password": seed_admin["password"]})
    assert res.status_code == 200
    assert b"Invalid Cybersecurity Analyst credentials" in res.data


def test_sp_admin_login_rejects_non_soc_role(client, seed_admin):
    """A real admin_users row with the right password must still be
    rejected here if its DB role isn't soc_analyst -- this is meant to be a
    separate credential, not any admin account with the right password."""
    res = client.post("/sp_admin/login",
                       data={"identifier": seed_admin["username"], "password": seed_admin["password"]})
    assert res.status_code == 200
    assert b"Invalid Cybersecurity Analyst credentials" in res.data


def test_sp_admin_mfa_rejects_arbitrary_six_digits(client, soc_admin):
    """A 6-digit string that isn't the account's actual current TOTP code
    must be rejected -- no digit-shaped fallback."""
    client.post("/sp_admin/login",
                data={"identifier": soc_admin["username"], "password": soc_admin["password"]})
    res_mfa = client.post("/sp_admin/mfa", data={"totp_code": "123456"})
    assert res_mfa.status_code == 200
    assert b"Invalid MFA verification code" in res_mfa.data


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
