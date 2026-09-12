"""Tests for utils/webauthn_utils.py — WebAuthn/mobile-biometric helpers.

_wa_verify_and_store_registration's success path (a real signature/
attestation check) needs an actual authenticator ceremony and isn't
exercised here — only its early-return and exception-handling paths are,
since those are this module's own logic rather than the webauthn library's.
"""
import time
import pytest
from extensions import app as flask_app
import utils.webauthn_utils as wa


@pytest.fixture(autouse=True)
def _cleanup_mobile_proofs(seed_employee, db_engine):
    yield
    cur = db_engine.cursor()
    cur.execute("DELETE FROM mobile_biometric_proofs WHERE employee_id=%s", (seed_employee["employee_id"],))
    db_engine.commit()
    cur.close()


# ── _wa_rp_id / _wa_check_rp_id / _wa_origins ───────────────────────────────

class TestWaRpId:
    def test_loopback_127_returns_exact_host(self):
        with flask_app.test_request_context("/", base_url="http://127.0.0.1:5000"):
            assert wa._wa_rp_id() == "127.0.0.1"

    def test_loopback_localhost_returns_exact_host(self):
        with flask_app.test_request_context("/", base_url="http://localhost:5000"):
            assert wa._wa_rp_id() == "localhost"

    def test_named_host_uses_pinned_allowed_origin(self, monkeypatch):
        monkeypatch.setattr(wa, "_allowed_origins", ["https://attendance.example.com"])
        with flask_app.test_request_context("/", base_url="http://192.168.1.50:5000"):
            assert wa._wa_rp_id() == "attendance.example.com"

    def test_falls_back_to_raw_host_when_origins_unconfigured(self, monkeypatch):
        monkeypatch.setattr(wa, "_allowed_origins", "*")
        with flask_app.test_request_context("/", base_url="http://192.168.1.50:5000"):
            assert wa._wa_rp_id() == "192.168.1.50"


class TestWaCheckRpId:
    def test_loopback_ids_are_valid(self):
        assert wa._wa_check_rp_id("127.0.0.1") is None
        assert wa._wa_check_rp_id("::1") is None
        assert wa._wa_check_rp_id("localhost") is None

    def test_lan_ip_is_rejected_with_explanation(self):
        err = wa._wa_check_rp_id("192.168.1.50")
        assert err is not None
        assert "IP addresses" in err

    def test_real_hostname_is_valid(self):
        assert wa._wa_check_rp_id("attendance.example.com") is None


class TestWaOrigins:
    def test_127_gets_localhost_equivalent_added(self):
        with flask_app.test_request_context("/", base_url="http://127.0.0.1:5000"):
            origins = wa._wa_origins()
            assert "http://127.0.0.1:5000" in origins
            assert "http://localhost:5000" in origins

    def test_localhost_gets_127_equivalent_added(self):
        with flask_app.test_request_context("/", base_url="http://localhost:5000"):
            origins = wa._wa_origins()
            assert "http://localhost:5000" in origins
            assert "http://127.0.0.1:5000" in origins

    def test_lan_ip_gets_single_origin_only(self):
        with flask_app.test_request_context("/", base_url="http://192.168.1.50:5000"):
            origins = wa._wa_origins()
            assert origins == ["http://192.168.1.50:5000"]


# ── b64url helpers ───────────────────────────────────────────────────────────

class TestB64UrlHelpers:
    def test_round_trip(self):
        raw = b"\x00\x01\xff\xfe\xa1binary-data-here"
        encoded = wa._wa_b64url_encode(raw)
        assert wa._wa_b64url_decode(encoded) == raw

    def test_encode_strips_padding(self):
        encoded = wa._wa_b64url_encode(b"x")
        assert "=" not in encoded

    def test_decode_handles_missing_padding(self):
        # 5-char base64url string with no '=' padding at all
        encoded = wa._wa_b64url_encode(b"hello")
        assert wa._wa_b64url_decode(encoded) == b"hello"


# ── _wa_fingerprint_recently_verified ───────────────────────────────────────

class TestWaFingerprintRecentlyVerified:
    def test_no_prior_verification_returns_false(self):
        with flask_app.test_request_context("/"):
            assert wa._wa_fingerprint_recently_verified("EMP1") is False

    def test_matching_recent_verification_returns_true(self):
        with flask_app.test_request_context("/"):
            from flask import session
            session["wa_fp_verified_emp_id"] = "EMP1"
            session["wa_fp_verified_at"] = time.time()
            assert wa._wa_fingerprint_recently_verified("emp1") is True  # case-insensitive

    def test_wrong_employee_returns_false(self):
        with flask_app.test_request_context("/"):
            from flask import session
            session["wa_fp_verified_emp_id"] = "EMP1"
            session["wa_fp_verified_at"] = time.time()
            assert wa._wa_fingerprint_recently_verified("EMP2") is False

    def test_expired_verification_returns_false(self):
        with flask_app.test_request_context("/"):
            from flask import session
            session["wa_fp_verified_emp_id"] = "EMP1"
            session["wa_fp_verified_at"] = time.time() - wa._WA_FP_VERIFY_WINDOW_SEC - 10
            assert wa._wa_fingerprint_recently_verified("EMP1") is False

    def test_proof_is_consumed_single_use(self):
        with flask_app.test_request_context("/"):
            from flask import session
            session["wa_fp_verified_emp_id"] = "EMP1"
            session["wa_fp_verified_at"] = time.time()
            assert wa._wa_fingerprint_recently_verified("EMP1") is True
            # Second call must fail — the session values were popped.
            assert wa._wa_fingerprint_recently_verified("EMP1") is False

    def test_empty_emp_id_returns_false(self):
        with flask_app.test_request_context("/"):
            from flask import session
            session["wa_fp_verified_emp_id"] = "EMP1"
            session["wa_fp_verified_at"] = time.time()
            assert wa._wa_fingerprint_recently_verified("") is False


# ── Mobile biometric nonce issue/attest/verify ──────────────────────────────

class TestMobileBiometricFlow:
    def test_issue_nonce_then_attest_succeeds(self, seed_employee):
        emp_id = seed_employee["employee_id"]
        nonce = wa._mobile_biometric_issue_nonce(emp_id)
        assert len(nonce) == 32

        ok, err = wa._mobile_biometric_attest(emp_id, nonce)
        assert ok is True
        assert err is None

    def test_attest_with_wrong_nonce_fails(self, seed_employee):
        emp_id = seed_employee["employee_id"]
        wa._mobile_biometric_issue_nonce(emp_id)
        ok, err = wa._mobile_biometric_attest(emp_id, "wrong-nonce-value")
        assert ok is False
        assert "Invalid or expired" in err

    def test_attest_with_missing_nonce_fails(self, seed_employee):
        ok, err = wa._mobile_biometric_attest(seed_employee["employee_id"], "")
        assert ok is False
        assert err == "Missing nonce"

    def test_attest_consumes_nonce_single_use(self, seed_employee):
        emp_id = seed_employee["employee_id"]
        nonce = wa._mobile_biometric_issue_nonce(emp_id)
        ok1, _ = wa._mobile_biometric_attest(emp_id, nonce)
        assert ok1 is True
        ok2, err2 = wa._mobile_biometric_attest(emp_id, nonce)
        assert ok2 is False  # nonce already cleared

    def test_reissuing_nonce_replaces_prior_one(self, seed_employee):
        emp_id = seed_employee["employee_id"]
        nonce1 = wa._mobile_biometric_issue_nonce(emp_id)
        nonce2 = wa._mobile_biometric_issue_nonce(emp_id)
        assert nonce1 != nonce2
        ok, _ = wa._mobile_biometric_attest(emp_id, nonce1)
        assert ok is False  # superseded by nonce2

    def test_recently_verified_true_right_after_attest(self, seed_employee):
        emp_id = seed_employee["employee_id"]
        nonce = wa._mobile_biometric_issue_nonce(emp_id)
        wa._mobile_biometric_attest(emp_id, nonce)
        assert wa._mobile_biometric_recently_verified(emp_id) is True

    def test_recently_verified_is_single_use(self, seed_employee):
        emp_id = seed_employee["employee_id"]
        nonce = wa._mobile_biometric_issue_nonce(emp_id)
        wa._mobile_biometric_attest(emp_id, nonce)
        assert wa._mobile_biometric_recently_verified(emp_id) is True
        assert wa._mobile_biometric_recently_verified(emp_id) is False

    def test_recently_verified_false_without_attest(self, seed_employee):
        assert wa._mobile_biometric_recently_verified(seed_employee["employee_id"]) is False

    def test_recently_verified_empty_emp_id_returns_false(self):
        assert wa._mobile_biometric_recently_verified("") is False
        assert wa._mobile_biometric_recently_verified(None) is False

    def test_recently_verified_expired_window_returns_false(self, seed_employee, db_engine):
        emp_id = seed_employee["employee_id"]
        cur = db_engine.cursor()
        # Computed via Postgres's own NOW() (matching how the production code
        # now compares, and how nonce_expires_at/verified_at are populated),
        # not Python's datetime.datetime.now() -- that's the local system
        # clock, which on a non-UTC server (e.g. IST) doesn't line up with
        # the naive-but-UTC timestamps Postgres stores in this "timestamp
        # without time zone" column, and would make this "stale" value look
        # recent instead.
        cur.execute(
            "INSERT INTO mobile_biometric_proofs (employee_id, verified_at) "
            "VALUES (%s, NOW() - %s * INTERVAL '1 second') "
            "ON CONFLICT (employee_id) DO UPDATE SET verified_at=EXCLUDED.verified_at",
            (emp_id, wa._MOBILE_BIO_VERIFY_WINDOW_SEC + 30),
        )
        db_engine.commit()
        cur.close()
        assert wa._mobile_biometric_recently_verified(emp_id) is False


# ── _wa_verify_and_store_registration early-return / error paths ───────────

class TestWaVerifyAndStoreRegistration:
    def test_returns_false_when_credential_missing(self, seed_employee, db_engine):
        cur = db_engine.cursor()
        ok, err = wa._wa_verify_and_store_registration(
            seed_employee["employee_id"], None, "some-challenge", cur, db_engine
        )
        cur.close()
        assert ok is False
        assert "Missing credential" in err

    def test_returns_false_when_challenge_missing(self, seed_employee, db_engine):
        cur = db_engine.cursor()
        ok, err = wa._wa_verify_and_store_registration(
            seed_employee["employee_id"], {"id": "x"}, None, cur, db_engine
        )
        cur.close()
        assert ok is False
        assert "Missing credential" in err

    def test_returns_false_on_invalid_credential_payload(self, seed_employee, db_engine):
        """A structurally-invalid credential should fail verification
        gracefully (caught exception -> (False, msg)), never raise."""
        cur = db_engine.cursor()
        with flask_app.test_request_context("/", base_url="http://localhost:5000"):
            ok, err = wa._wa_verify_and_store_registration(
                seed_employee["employee_id"], {"not": "a real credential"}, "ZmFrZQ==", cur, db_engine
            )
        cur.close()
        assert ok is False
        assert err is not None

    def test_unavailable_webauthn_short_circuits(self, seed_employee, db_engine, monkeypatch):
        monkeypatch.setattr(wa, "_webauthn_available", False)
        cur = db_engine.cursor()
        ok, err = wa._wa_verify_and_store_registration(
            seed_employee["employee_id"], {"id": "x"}, "chal", cur, db_engine
        )
        cur.close()
        assert ok is False
        assert "not available" in err

    def test_credential_as_json_string_is_parsed(self, seed_employee, db_engine):
        """credential may arrive as a raw JSON string (from a form field)
        rather than an already-decoded dict — json.loads(credential) must
        run before verification, not raise on the str branch itself."""
        cur = db_engine.cursor()
        with flask_app.test_request_context("/", base_url="http://localhost:5000"):
            ok, err = wa._wa_verify_and_store_registration(
                seed_employee["employee_id"], '{"not": "a real credential"}', "ZmFrZQ==", cur, db_engine
            )
        cur.close()
        assert ok is False
        assert err is not None


# ── _enroll_fingerprint_from_form ───────────────────────────────────────────

class TestEnrollFingerprintFromForm:
    def test_noop_when_field_empty(self, seed_employee, db_engine):
        cur = db_engine.cursor()
        with flask_app.test_request_context("/", data={}):
            # Should return without touching the DB or raising.
            wa._enroll_fingerprint_from_form(seed_employee["employee_id"], cur, db_engine)
        cur.close()

    def test_calls_verify_and_flashes_on_failure(self, seed_employee, db_engine, monkeypatch):
        calls = []

        def _fake_verify(emp_id, credential, challenge_b64, cursor, db):
            calls.append((emp_id, credential, challenge_b64))
            return False, "simulated failure"
        monkeypatch.setattr(wa, "_wa_verify_and_store_registration", _fake_verify)

        cur = db_engine.cursor()
        with flask_app.test_request_context(
            "/", method="POST", data={"fingerprint_attestation": "some-attestation-json"}
        ):
            from flask import session
            session["wa_reg_challenge"] = "chal123"
            wa._enroll_fingerprint_from_form(seed_employee["employee_id"], cur, db_engine)
            # Challenge/alg-id session keys must be cleared either way.
            assert "wa_reg_challenge" not in session
        cur.close()
        assert len(calls) == 1
        assert calls[0][0] == seed_employee["employee_id"]
        assert calls[0][1] == "some-attestation-json"
