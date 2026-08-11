"""Tests for the Turnstile CAPTCHA gate on /login (blueprints/auth.py)
and its supporting helpers in utils/auth.py: _get_failed_count,
_mask_identifier, verify_turnstile, turnstile_enabled. The existing
5-strikes/15-minute lockout (utils/auth.py's _LOGIN_MAX_ATTEMPTS) is
already covered elsewhere — these tests focus on what's new."""
import pytest
import utils.auth as auth_module
import blueprints.auth as auth_bp_module
from utils.auth import _mask_identifier, _get_failed_count, turnstile_enabled


class TestMaskIdentifier:
    def test_masks_email_local_part(self):
        assert _mask_identifier("john.doe@company.com") == "j***@company.com"

    def test_masks_middle_of_username(self):
        assert _mask_identifier("TST001") == "TS***1"

    def test_short_identifier_still_masked(self):
        result = _mask_identifier("ab")
        assert result.startswith("a")
        assert "b" not in result  # the second char must not appear in plain

    def test_empty_identifier_handled(self):
        assert _mask_identifier("") == "(empty)"

    def test_never_returns_the_original_string_for_longer_ids(self):
        original = "admin_super_user"
        assert _mask_identifier(original) != original


class TestTurnstileEnabled:
    def test_disabled_when_keys_unset(self, monkeypatch):
        monkeypatch.setattr(auth_module, "_TURNSTILE_SITE_KEY", "")
        monkeypatch.setattr(auth_module, "_TURNSTILE_SECRET_KEY", "")
        assert turnstile_enabled() is False

    def test_enabled_when_both_keys_set(self, monkeypatch):
        monkeypatch.setattr(auth_module, "_TURNSTILE_SITE_KEY", "site-key")
        monkeypatch.setattr(auth_module, "_TURNSTILE_SECRET_KEY", "secret-key")
        assert turnstile_enabled() is True

    def test_disabled_when_only_one_key_set(self, monkeypatch):
        monkeypatch.setattr(auth_module, "_TURNSTILE_SITE_KEY", "site-key")
        monkeypatch.setattr(auth_module, "_TURNSTILE_SECRET_KEY", "")
        assert turnstile_enabled() is False


class TestVerifyTurnstile:
    def test_no_secret_configured_returns_false(self, monkeypatch):
        monkeypatch.setattr(auth_module, "_TURNSTILE_SECRET_KEY", "")
        assert auth_module.verify_turnstile("some-token", "1.2.3.4") is False

    def test_empty_token_returns_false(self, monkeypatch):
        monkeypatch.setattr(auth_module, "_TURNSTILE_SECRET_KEY", "secret")
        assert auth_module.verify_turnstile("", "1.2.3.4") is False

    def test_successful_verification(self, monkeypatch):
        import json as _json

        class _FakeResp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return _json.dumps({"success": True}).encode()

        monkeypatch.setattr(auth_module, "_TURNSTILE_SECRET_KEY", "secret")
        monkeypatch.setattr(auth_module.urllib.request, "urlopen", lambda req, timeout=None: _FakeResp())
        assert auth_module.verify_turnstile("valid-token", "1.2.3.4") is True

    def test_failed_verification(self, monkeypatch):
        import json as _json

        class _FakeResp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return _json.dumps({"success": False, "error-codes": ["invalid-input-response"]}).encode()

        monkeypatch.setattr(auth_module, "_TURNSTILE_SECRET_KEY", "secret")
        monkeypatch.setattr(auth_module.urllib.request, "urlopen", lambda req, timeout=None: _FakeResp())
        assert auth_module.verify_turnstile("bad-token", "1.2.3.4") is False

    def test_network_failure_returns_false_not_exception(self, monkeypatch):
        def _boom(req, timeout=None):
            raise OSError("simulated network failure")

        monkeypatch.setattr(auth_module, "_TURNSTILE_SECRET_KEY", "secret")
        monkeypatch.setattr(auth_module.urllib.request, "urlopen", _boom)
        assert auth_module.verify_turnstile("token", "1.2.3.4") is False


class TestGetFailedCount:
    def test_zero_when_no_record(self, db_engine):
        cur = db_engine.cursor()
        cur.execute("DELETE FROM login_attempts WHERE identifier='nosuchuser'")
        db_engine.commit()
        cur.close()
        assert _get_failed_count("nosuchuser") == 0

    def test_reflects_recorded_failures(self, db_engine):
        cur = db_engine.cursor()
        cur.execute("DELETE FROM login_attempts WHERE identifier='counttest'")
        cur.execute(
            "INSERT INTO login_attempts (identifier, attempt_type, failed_count, last_attempt) "
            "VALUES ('counttest', 'admin', 3, NOW())"
        )
        db_engine.commit()
        cur.close()
        assert _get_failed_count("counttest") == 3
        cur = db_engine.cursor()
        cur.execute("DELETE FROM login_attempts WHERE identifier='counttest'")
        db_engine.commit()
        cur.close()


class TestAdminLoginCaptchaGate:
    @pytest.fixture(autouse=True)
    def _cleanup(self, seed_employee, db_engine):
        yield
        cur = db_engine.cursor()
        cur.execute("DELETE FROM login_attempts WHERE identifier=%s", (seed_employee["employee_id"],))
        db_engine.commit()
        cur.close()

    def test_no_captcha_widget_when_turnstile_unconfigured(self, client, seed_employee, monkeypatch):
        monkeypatch.setattr(auth_bp_module, "turnstile_enabled", lambda: False)
        resp = client.post("/login", data={
            "identifier": seed_employee["employee_id"], "password": "wrong",
        })
        assert resp.status_code == 200
        assert b"cf-turnstile" not in resp.data

    def test_captcha_widget_appears_after_two_failures(self, client, seed_employee, db_engine, monkeypatch):
        monkeypatch.setattr(auth_bp_module, "turnstile_enabled", lambda: True)
        monkeypatch.setattr(auth_bp_module, "_TURNSTILE_SITE_KEY", "test-site-key")

        cur = db_engine.cursor()
        cur.execute("DELETE FROM login_attempts WHERE identifier=%s", (seed_employee["employee_id"],))
        cur.execute(
            "INSERT INTO login_attempts (identifier, attempt_type, failed_count, last_attempt) "
            "VALUES (%s, 'admin', 1, NOW())",
            (seed_employee["employee_id"],),
        )
        db_engine.commit()
        cur.close()

        # This is the 2nd failure (count was 1) -> widget should be shown for the NEXT attempt.
        resp = client.post("/login", data={
            "identifier": seed_employee["employee_id"], "password": "wrong",
        })
        assert resp.status_code == 200
        assert b"cf-turnstile" in resp.data
        assert b"test-site-key" in resp.data

    def test_third_attempt_rejected_without_valid_captcha_token(self, client, seed_employee, db_engine, monkeypatch):
        monkeypatch.setattr(auth_bp_module, "turnstile_enabled", lambda: True)
        monkeypatch.setattr(auth_bp_module, "_TURNSTILE_SITE_KEY", "test-site-key")
        monkeypatch.setattr(auth_bp_module, "verify_turnstile", lambda token, ip: False)

        cur = db_engine.cursor()
        cur.execute("DELETE FROM login_attempts WHERE identifier=%s", (seed_employee["employee_id"],))
        cur.execute(
            "INSERT INTO login_attempts (identifier, attempt_type, failed_count, last_attempt) "
            "VALUES (%s, 'admin', 2, NOW())",
            (seed_employee["employee_id"],),
        )
        db_engine.commit()
        cur.close()

        resp = client.post("/login", data={
            "identifier": seed_employee["employee_id"], "password": seed_employee["password"],
        })
        assert resp.status_code == 200
        assert b"verification challenge" in resp.data

    def test_valid_captcha_token_allows_login_through_gate(self, client, seed_employee, db_engine, monkeypatch):
        monkeypatch.setattr(auth_bp_module, "turnstile_enabled", lambda: True)
        monkeypatch.setattr(auth_bp_module, "_TURNSTILE_SITE_KEY", "test-site-key")
        monkeypatch.setattr(auth_bp_module, "verify_turnstile", lambda token, ip: True)

        cur = db_engine.cursor()
        cur.execute("DELETE FROM login_attempts WHERE identifier=%s", (seed_employee["employee_id"],))
        cur.execute(
            "INSERT INTO login_attempts (identifier, attempt_type, failed_count, last_attempt) "
            "VALUES (%s, 'admin', 2, NOW())",
            (seed_employee["employee_id"],),
        )
        db_engine.commit()
        cur.close()

        resp = client.post("/login", data={
            "identifier": seed_employee["employee_id"], "password": seed_employee["password"],
            "cf-turnstile-response": "any-nonempty-token",
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers.get("Location", "").endswith("/employee_portal") or "force_change_pin" in resp.headers.get("Location", "")
