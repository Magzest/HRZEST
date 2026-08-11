"""Tests for POST /api/employee/device_risk (blueprints/employee_portal.py)
— the relay endpoint that feeds a native device-posture agent's Wi-Fi risk
score into the existing session-risk kill switch (utils/session_risk.py).
This endpoint never computes a risk score itself; it only accepts one
already-computed by a trusted caller and, above 60, force-compromises the
current session using the same mechanism already covered by
tests/test_session_risk.py."""
import time
import pytest
from utils.session_risk import is_session_compromised


def _wait_compromised(sid, timeout=2):
    """evaluate_session_risk() enqueues its DB write to a background writer
    thread (see utils/session_risk.py) — poll briefly rather than asserting
    immediately, same pattern as test_session_risk.py's own async test."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_session_compromised(sid):
            return True
        time.sleep(0.05)
    return False


@pytest.fixture(autouse=True)
def _cleanup(seed_employee, db_engine):
    yield
    cur = db_engine.cursor()
    cur.execute("DELETE FROM session_risk WHERE identifier=%s", (seed_employee["employee_id"],))
    db_engine.commit()
    cur.close()


class TestDeviceRiskEndpoint:
    def test_requires_employee_login(self, client):
        resp = client.post("/api/employee/device_risk", json={"risk_score": 90}, follow_redirects=False)
        assert resp.status_code in (302, 401)

    def test_low_score_does_not_block(self, client, seed_employee):
        with client.session_transaction() as sess:
            sess["employee_id"] = seed_employee["employee_id"]
        resp = client.post("/api/employee/device_risk", json={"risk_score": 30})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["blocked"] is False

    def test_score_at_threshold_does_not_block(self, client, seed_employee):
        """> 60 blocks, per spec — exactly 60 should not."""
        with client.session_transaction() as sess:
            sess["employee_id"] = seed_employee["employee_id"]
        resp = client.post("/api/employee/device_risk", json={"risk_score": 60})
        assert resp.get_json()["blocked"] is False

    def test_high_score_blocks_and_compromises_session(self, client, seed_employee):
        with client.session_transaction() as sess:
            sess["employee_id"] = seed_employee["employee_id"]
            sid = sess.setdefault("_sid", "test-sid-device-risk")

        resp = client.post("/api/employee/device_risk",
                           json={"risk_score": 85, "threat_vectors": ["weak_encryption", "arp_spoof"]})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["blocked"] is True

        assert _wait_compromised(sid) is True

    def test_next_request_after_block_is_rejected(self, client, seed_employee):
        with client.session_transaction() as sess:
            sess["employee_id"] = seed_employee["employee_id"]
            sid = sess.setdefault("_sid", "test-sid-device-risk-2")

        block_resp = client.post("/api/employee/device_risk", json={"risk_score": 95})
        assert block_resp.get_json()["blocked"] is True
        assert _wait_compromised(sid) is True

        # The existing kill switch (employee_required -> _reject_if_compromised)
        # should now reject this same session's very next request, on any route.
        next_resp = client.get("/employee_portal", follow_redirects=False)
        assert next_resp.status_code == 302
        assert "/login" in next_resp.headers.get("Location", "")

    def test_non_integer_score_rejected(self, client, seed_employee):
        with client.session_transaction() as sess:
            sess["employee_id"] = seed_employee["employee_id"]
        resp = client.post("/api/employee/device_risk", json={"risk_score": "not-a-number"})
        assert resp.status_code == 400

    def test_score_out_of_range_is_clamped_not_rejected(self, client, seed_employee):
        with client.session_transaction() as sess:
            sess["employee_id"] = seed_employee["employee_id"]
        resp = client.post("/api/employee/device_risk", json={"risk_score": 999})
        assert resp.status_code == 200
        assert resp.get_json()["blocked"] is True  # clamped to 100, still > 60

    def test_missing_body_treated_as_zero_score(self, client, seed_employee):
        with client.session_transaction() as sess:
            sess["employee_id"] = seed_employee["employee_id"]
        resp = client.post("/api/employee/device_risk", json={})
        assert resp.status_code == 200
        assert resp.get_json()["blocked"] is False

    def test_non_list_threat_vectors_ignored_not_crashed(self, client, seed_employee):
        with client.session_transaction() as sess:
            sess["employee_id"] = seed_employee["employee_id"]
        resp = client.post("/api/employee/device_risk",
                           json={"risk_score": 20, "threat_vectors": "not-a-list"})
        assert resp.status_code == 200
