"""Tests for the admin employee-registration flow: POST /admin_action
(action=register), blueprints/employees.py.

att_test is a persistent, shared DB (see conftest.py) — every test here
cleans up its own rows/files in a finally block so a failed assertion can't
leave debris that inflates or breaks a later run (see the incident this
pattern was hardened against in tests/test_admin_search.py).
"""
import io
import os
import datetime
from PIL import Image

import utils.face_utils as face_utils
from extensions import app as flask_app

UPLOAD_FOLDER = flask_app.config["UPLOAD_FOLDER"]
QR_FOLDER = os.path.join(os.path.dirname(os.path.abspath(UPLOAD_FOLDER)), "static", "qrcodes")


def _fake_jpeg_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color=(120, 120, 120)).save(buf, format="JPEG")
    buf.seek(0)
    return buf.read()


def _mock_face_detected(monkeypatch, detected=True):
    monkeypatch.setattr(face_utils.face_recognition, "load_image_file", lambda p: "img")
    monkeypatch.setattr(face_utils.face_recognition, "face_encodings",
                        lambda img: ["enc"] if detected else [])


def _admin_session(client, seed_admin):
    resp = client.post("/login", data={
        "identifier": seed_admin["username"],
        "password": seed_admin["password"],
    }, follow_redirects=True)
    assert resp.status_code == 200


def _registration_payload(emp_id, **overrides):
    payload = {
        "action": "register",
        "name": "Registration Test Employee",
        "emp_id": emp_id,
        "email": "regtest@example.com",
        "role": "Developer",
        "date_of_joining": datetime.date.today().isoformat(),
        "work_mode": "office",
        "face": (io.BytesIO(_fake_jpeg_bytes()), "face.jpg"),
    }
    payload.update(overrides)
    return payload


def _cleanup_employee(db_engine, emp_id):
    cur = db_engine.cursor()
    cur.execute("DELETE FROM leave_balances WHERE employee_id=%s", (emp_id,))
    cur.execute("DELETE FROM salary_config WHERE employee_id=%s", (emp_id,))
    cur.execute("DELETE FROM employees WHERE employee_id=%s", (emp_id,))
    cur.close()
    for path in (os.path.join(UPLOAD_FOLDER, emp_id + ".jpg"),
                 os.path.join(QR_FOLDER, emp_id + ".png")):
        if os.path.exists(path):
            os.remove(path)


class TestEmployeeRegistrationAuthorization:
    def test_anonymous_request_rejected(self, client):
        resp = client.post("/admin_action", data=_registration_payload("REGTST900"), follow_redirects=False)
        assert resp.status_code in (302, 401)
        assert resp.headers.get("Location", "").endswith(("/login", "/login?locked=1")) or \
            "admin_login" in resp.headers.get("Location", "")

    def test_employee_session_rejected(self, client, seed_employee):
        with client.session_transaction() as sess:
            sess["employee_id"] = seed_employee["employee_id"]
        resp = client.post("/admin_action", data=_registration_payload("REGTST901"), follow_redirects=False)
        assert resp.status_code in (302, 401)


class TestEmployeeRegistrationSuccess:
    def test_successful_registration_creates_employee(self, client, seed_admin, db_engine, monkeypatch):
        _mock_face_detected(monkeypatch, detected=True)
        emp_id = "REGTST001"
        try:
            _admin_session(client, seed_admin)
            resp = client.post("/admin_action", data=_registration_payload(
                emp_id, salary_per_day="1500.00"), follow_redirects=True)
            assert resp.status_code == 200

            cur = db_engine.cursor()
            cur.execute("SELECT name, email, role FROM employees WHERE employee_id=%s", (emp_id,))
            row = cur.fetchone()
            assert row is not None
            assert row[0] == "Registration Test Employee"
            assert row[1] == "regtest@example.com"
            assert row[2] == "Developer"

            cur.execute("SELECT salary_per_day FROM salary_config WHERE employee_id=%s", (emp_id,))
            salary_row = cur.fetchone()
            assert salary_row is not None
            assert float(salary_row[0]) == 1500.00
            cur.close()

            assert os.path.exists(os.path.join(UPLOAD_FOLDER, emp_id + ".jpg"))
            assert os.path.exists(os.path.join(QR_FOLDER, emp_id + ".png"))
        finally:
            _cleanup_employee(db_engine, emp_id)

    def test_registration_assigns_leave_balances(self, client, seed_admin, db_engine, monkeypatch):
        _mock_face_detected(monkeypatch, detected=True)
        emp_id = "REGTST002"
        try:
            _admin_session(client, seed_admin)
            client.post("/admin_action", data=_registration_payload(emp_id), follow_redirects=True)

            cur = db_engine.cursor()
            cur.execute("SELECT COUNT(*) FROM leave_types WHERE is_active=1")
            active_leave_types = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM leave_balances WHERE employee_id=%s", (emp_id,))
            balances = cur.fetchone()[0]
            cur.close()
            assert balances == active_leave_types
        finally:
            _cleanup_employee(db_engine, emp_id)


class TestEmployeeRegistrationPiiFields:
    def test_registration_with_aadhar_number_succeeds_and_roundtrips(self, client, seed_admin, db_engine, monkeypatch):
        """aadhar_number/pan_number/bank_account/bank_ifsc/uan_number are
        Fernet-encrypted before insert (encrypt_pii ~100+ chars for any
        input), but their columns are still VARCHAR(20-30) — narrower than
        every other PII field on this table, which was already widened to
        TEXT for exactly this reason. Confirms whether filling one in
        actually works end-to-end."""
        from utils.helpers import decrypt_pii
        _mock_face_detected(monkeypatch, detected=True)
        emp_id = "REGTST010"
        try:
            _admin_session(client, seed_admin)
            resp = client.post("/admin_action", data=_registration_payload(
                emp_id, aadhar_number="123456789012"), follow_redirects=True)
            assert resp.status_code == 200

            cur = db_engine.cursor()
            cur.execute("SELECT aadhar_number FROM employees WHERE employee_id=%s", (emp_id,))
            row = cur.fetchone()
            cur.close()
            assert row is not None, (
                "Employee row was not created when aadhar_number was supplied — "
                "encrypt_pii() output (100+ chars) does not fit VARCHAR(20)"
            )
            assert decrypt_pii(row[0]) == "123456789012"
        finally:
            _cleanup_employee(db_engine, emp_id)


class TestEmployeeRegistrationValidation:
    def test_alpha_prefixed_duplicate_silently_reassigns_new_id(self, client, seed_admin, seed_employee, db_engine, monkeypatch):
        """Registering with an already-taken ID that has a letter prefix
        (like seed_employee's TST001) does NOT error — _admin_action's
        auto-increment logic (blueprints/employees.py ~line 88) strips the
        alpha prefix, finds the next free numeric suffix, and silently
        registers a NEW employee under that ID instead (e.g. TST002). This
        is a real, easy-to-miss requirement: submitting a "duplicate" ID
        here creates a second employee rather than rejecting the request."""
        _mock_face_detected(monkeypatch, detected=True)
        taken_id = seed_employee["employee_id"]
        reassigned_id = "TST002"
        try:
            _admin_session(client, seed_admin)
            resp = client.post("/admin_action", data=_registration_payload(taken_id), follow_redirects=True)
            assert resp.status_code == 200
            body = resp.get_data(as_text=True)
            assert reassigned_id in body

            cur = db_engine.cursor()
            cur.execute("SELECT name FROM employees WHERE employee_id=%s", (taken_id,))
            original = cur.fetchone()
            cur.execute("SELECT name FROM employees WHERE employee_id=%s", (reassigned_id,))
            new_row = cur.fetchone()
            cur.close()
            # Original seed_employee record must be untouched, not overwritten
            assert original[0] == seed_employee["name"]
            # A second, distinct employee was created under the reassigned ID
            assert new_row is not None
            assert new_row[0] == "Registration Test Employee"
        finally:
            _cleanup_employee(db_engine, reassigned_id)

    def test_numeric_only_duplicate_id_rejected(self, client, seed_admin, db_engine, monkeypatch):
        """Unlike an alpha-prefixed collision, a purely numeric ID has no
        prefix to strip, so the auto-increment path (which requires a
        non-empty prefix) can't kick in — this is the one case that
        actually reaches the 'already exists' rejection."""
        _mock_face_detected(monkeypatch, detected=True)
        emp_id = "919191"
        try:
            _admin_session(client, seed_admin)
            first = client.post("/admin_action", data=_registration_payload(emp_id), follow_redirects=True)
            assert first.status_code == 200

            second = client.post("/admin_action", data=_registration_payload(emp_id), follow_redirects=True)
            assert second.status_code == 200
            body = second.get_data(as_text=True)
            assert "already exists" in body.lower()

            cur = db_engine.cursor()
            cur.execute("SELECT COUNT(*) FROM employees WHERE employee_id=%s", (emp_id,))
            assert cur.fetchone()[0] == 1
            cur.close()
        finally:
            _cleanup_employee(db_engine, emp_id)

    def test_invalid_employee_id_format_rejected(self, client, seed_admin, db_engine, monkeypatch):
        _mock_face_detected(monkeypatch, detected=True)
        bad_emp_id = "BAD ID!"
        _admin_session(client, seed_admin)
        try:
            resp = client.post("/admin_action", data=_registration_payload(bad_emp_id), follow_redirects=True)
            assert resp.status_code == 200
            body = resp.get_data(as_text=True)
            assert "letters, digits, hyphens and underscores" in body.lower() or "error" in body.lower()

            cur = db_engine.cursor()
            cur.execute("SELECT COUNT(*) FROM employees WHERE employee_id=%s", (bad_emp_id,))
            assert cur.fetchone()[0] == 0
            cur.close()
        finally:
            _cleanup_employee(db_engine, bad_emp_id)

    def test_missing_required_field_handled_gracefully(self, client, seed_admin, db_engine):
        emp_id = "REGTST003"
        payload = _registration_payload(emp_id)
        del payload["name"]  # simulate a malformed/direct POST missing a required field
        _admin_session(client, seed_admin)
        try:
            resp = client.post("/admin_action", data=payload, follow_redirects=True)
            # Must be handled gracefully (redirect + flash), never a raw 500
            assert resp.status_code == 200
            body = resp.get_data(as_text=True)
            assert "missing or invalid field" in body.lower()

            cur = db_engine.cursor()
            cur.execute("SELECT COUNT(*) FROM employees WHERE employee_id=%s", (emp_id,))
            assert cur.fetchone()[0] == 0
            cur.close()
        finally:
            _cleanup_employee(db_engine, emp_id)

    def test_no_face_detected_rejected(self, client, seed_admin, db_engine, monkeypatch):
        _mock_face_detected(monkeypatch, detected=False)
        emp_id = "REGTST004"
        _admin_session(client, seed_admin)
        try:
            resp = client.post("/admin_action", data=_registration_payload(emp_id), follow_redirects=True)
            assert resp.status_code == 200
            body = resp.get_data(as_text=True)
            assert "no face detected" in body.lower()

            cur = db_engine.cursor()
            cur.execute("SELECT COUNT(*) FROM employees WHERE employee_id=%s", (emp_id,))
            assert cur.fetchone()[0] == 0
            cur.close()
            # Rejected upload must not be left on disk
            assert not os.path.exists(os.path.join(UPLOAD_FOLDER, emp_id + ".jpg"))
        finally:
            _cleanup_employee(db_engine, emp_id)

    def test_auto_increment_on_alpha_prefixed_duplicate(self, client, seed_admin, db_engine, monkeypatch):
        """A collision on an alpha-prefixed ID (e.g. EMP001 taken) should
        silently retry with the next free numeric suffix rather than error."""
        _mock_face_detected(monkeypatch, detected=True)
        base_id = "REGTSTA001"
        next_id = "REGTSTA002"
        try:
            _admin_session(client, seed_admin)
            client.post("/admin_action", data=_registration_payload(base_id), follow_redirects=True)
            client.post("/admin_action", data=_registration_payload(base_id), follow_redirects=True)

            cur = db_engine.cursor()
            cur.execute("SELECT COUNT(*) FROM employees WHERE employee_id IN (%s,%s)", (base_id, next_id))
            assert cur.fetchone()[0] == 2
            cur.close()
        finally:
            _cleanup_employee(db_engine, base_id)
            _cleanup_employee(db_engine, next_id)

    def test_auto_increment_preserves_original_suffix_width(self, client, seed_admin, db_engine, monkeypatch):
        """A collision on a 1-digit suffix (e.g. PADW9) must reassign to
        PADW10, not the old hardcoded-3-digit PADW010 — the padding width
        should follow what the admin actually typed."""
        _mock_face_detected(monkeypatch, detected=True)
        base_id = "PADW9"
        next_id = "PADW10"
        wrong_id = "PADW010"
        try:
            _admin_session(client, seed_admin)
            client.post("/admin_action", data=_registration_payload(base_id), follow_redirects=True)
            resp = client.post("/admin_action", data=_registration_payload(base_id), follow_redirects=True)
            assert next_id in resp.get_data(as_text=True)

            cur = db_engine.cursor()
            cur.execute("SELECT COUNT(*) FROM employees WHERE employee_id=%s", (next_id,))
            assert cur.fetchone()[0] == 1
            cur.execute("SELECT COUNT(*) FROM employees WHERE employee_id=%s", (wrong_id,))
            assert cur.fetchone()[0] == 0
            cur.close()
        finally:
            _cleanup_employee(db_engine, base_id)
            _cleanup_employee(db_engine, next_id)
            _cleanup_employee(db_engine, wrong_id)


class TestEmployeeRegistrationLengthLimits:
    def test_overlong_name_rejected_cleanly(self, client, seed_admin, db_engine, monkeypatch):
        """A name over the VARCHAR(100) column width must be rejected with
        a clear flash message, not an unhandled psycopg2.DataError."""
        _mock_face_detected(monkeypatch, detected=True)
        emp_id = "REGTST020"
        try:
            _admin_session(client, seed_admin)
            resp = client.post("/admin_action", data=_registration_payload(
                emp_id, name="X" * 150), follow_redirects=True)
            assert resp.status_code == 200
            assert "too long" in resp.get_data(as_text=True).lower()

            cur = db_engine.cursor()
            cur.execute("SELECT COUNT(*) FROM employees WHERE employee_id=%s", (emp_id,))
            assert cur.fetchone()[0] == 0
            cur.close()
        finally:
            _cleanup_employee(db_engine, emp_id)

    def test_blank_name_rejected(self, client, seed_admin, db_engine, monkeypatch):
        _mock_face_detected(monkeypatch, detected=True)
        emp_id = "REGTST021"
        try:
            _admin_session(client, seed_admin)
            resp = client.post("/admin_action", data=_registration_payload(
                emp_id, name="   "), follow_redirects=True)
            assert resp.status_code == 200
            assert "full name is required" in resp.get_data(as_text=True).lower()

            cur = db_engine.cursor()
            cur.execute("SELECT COUNT(*) FROM employees WHERE employee_id=%s", (emp_id,))
            assert cur.fetchone()[0] == 0
            cur.close()
        finally:
            _cleanup_employee(db_engine, emp_id)
