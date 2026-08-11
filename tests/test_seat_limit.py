"""Paid employee-seat cap on registration, and the "buy more seats" Razorpay
top-up flow that lifts it.

company_settings.paid_employee_slots is None for every tenant that never
went through the metered flow (legacy tenants, Platform-Admin-created
tenants, the shared att_test schema) -- utils/helpers.py's
validate_employee_seat_available() is then a no-op, exactly like the
email-domain gate's no-domain-configured case. These tests mutate
paid_employee_slots on the shared att_test schema to exercise both states,
always restoring it to NULL in a finally block.

The buy-seats endpoints (blueprints/billing.py) run in demo mode here since
RAZORPAY_KEY_ID/SECRET aren't configured for the test suite -- same posture
as tests/test_org.py's paid-signup coverage.
"""
import os
import io
import datetime
import pytest
from PIL import Image

import utils.face_utils as face_utils
from extensions import app as flask_app

UPLOAD_FOLDER = flask_app.config["UPLOAD_FOLDER"]
QR_FOLDER = os.path.join(os.path.dirname(os.path.abspath(UPLOAD_FOLDER)), "static", "qrcodes")
_TEST_DB_NAME = os.environ.get("DB_NAME", "att_test")


def _fake_jpeg_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color=(90, 100, 110)).save(buf, format="JPEG")
    buf.seek(0)
    return buf.read()


def _mock_face_detected(monkeypatch):
    monkeypatch.setattr(face_utils.face_recognition, "load_image_file", lambda p: "img")
    monkeypatch.setattr(face_utils.face_recognition, "face_encodings", lambda img: ["enc"])


def _admin_session(client, seed_admin):
    resp = client.post("/login", data={
        "identifier": seed_admin["username"],
        "password": seed_admin["password"],
    }, follow_redirects=True)
    assert resp.status_code == 200
    # /login resolves the tenant purely from the URL path (empty here, since
    # this test hits the bare route) -- the buy-seats endpoints key off
    # session["tenant_db"] explicitly, so stamp it directly rather than
    # relying on path-based resolution this test file doesn't exercise.
    with client.session_transaction() as sess:
        sess["tenant_db"] = _TEST_DB_NAME


def _registration_payload(emp_id, email="new.hire@test.local", **overrides):
    payload = {
        "action": "register",
        "name": "Seat Limit Test Employee",
        "emp_id": emp_id,
        "email": email,
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


def _set_slots(db_engine, slots):
    cur = db_engine.cursor()
    cur.execute("UPDATE company_settings SET paid_employee_slots=%s WHERE id=1", (slots,))
    cur.close()
    from utils.helpers import invalidate_settings_cache
    invalidate_settings_cache()


def _current_employee_count(db_engine):
    cur = db_engine.cursor()
    cur.execute("SELECT COUNT(*) FROM employees")
    n = cur.fetchone()[0]
    cur.close()
    return n


def _cleanup_seat_orders(db_engine, subdomain="att-test-suite"):
    cur = db_engine.cursor()
    cur.execute("DELETE FROM att_master.seat_orders WHERE subdomain=%s", (subdomain,))
    cur.close()


class TestNoSeatCapConfigured:
    def test_registration_without_slots_still_works(self, client, seed_admin, db_engine, monkeypatch):
        """Baseline every other registration test in the suite assumes: a
        company that never went through the metered flow keeps unlimited
        free registration."""
        _mock_face_detected(monkeypatch)
        emp_id = "SEATCAP001"
        _set_slots(db_engine, None)
        try:
            _admin_session(client, seed_admin)
            resp = client.post("/admin_action", data=_registration_payload(emp_id), follow_redirects=True)
            assert resp.status_code == 200

            cur = db_engine.cursor()
            cur.execute("SELECT employee_id FROM employees WHERE employee_id=%s", (emp_id,))
            assert cur.fetchone() is not None
            cur.close()
        finally:
            _cleanup_employee(db_engine, emp_id)
            _set_slots(db_engine, None)


class TestSeatCapEnforced:
    def test_registration_blocked_when_seats_exhausted(self, client, seed_admin, db_engine, monkeypatch):
        _mock_face_detected(monkeypatch)
        emp_id = "SEATCAP002"
        current = _current_employee_count(db_engine)
        _set_slots(db_engine, current)  # every existing seat already used
        try:
            _admin_session(client, seed_admin)
            resp = client.post("/admin_action", data=_registration_payload(emp_id), follow_redirects=True)
            assert resp.status_code == 200
            assert b"paid employee seats" in resp.data

            cur = db_engine.cursor()
            cur.execute("SELECT employee_id FROM employees WHERE employee_id=%s", (emp_id,))
            assert cur.fetchone() is None, "employee must not be created once seats are exhausted"
            cur.close()
        finally:
            _cleanup_employee(db_engine, emp_id)
            _set_slots(db_engine, None)

    def test_registration_allowed_when_seat_available(self, client, seed_admin, db_engine, monkeypatch):
        _mock_face_detected(monkeypatch)
        emp_id = "SEATCAP003"
        current = _current_employee_count(db_engine)
        _set_slots(db_engine, current + 1)  # exactly one free seat left
        try:
            _admin_session(client, seed_admin)
            resp = client.post("/admin_action", data=_registration_payload(emp_id), follow_redirects=True)
            assert resp.status_code == 200

            cur = db_engine.cursor()
            cur.execute("SELECT employee_id FROM employees WHERE employee_id=%s", (emp_id,))
            assert cur.fetchone() is not None
            cur.close()
        finally:
            _cleanup_employee(db_engine, emp_id)
            _set_slots(db_engine, None)

    def test_add_employee_page_blocked_when_seats_exhausted(self, client, seed_admin, db_engine, monkeypatch):
        """add_employee_page (/employees "Add Employee" modal) is a second,
        independent registration entry point -- must enforce the same cap."""
        _mock_face_detected(monkeypatch)
        emp_id = "SEATCAP004"
        current = _current_employee_count(db_engine)
        _set_slots(db_engine, current)
        try:
            _admin_session(client, seed_admin)
            resp = client.post("/add_employee_page", data=_registration_payload(emp_id), follow_redirects=True)
            assert resp.status_code == 200
            assert b"paid employee seats" in resp.data

            cur = db_engine.cursor()
            cur.execute("SELECT employee_id FROM employees WHERE employee_id=%s", (emp_id,))
            assert cur.fetchone() is None
            cur.close()
        finally:
            _cleanup_employee(db_engine, emp_id)
            _set_slots(db_engine, None)

    def test_api_register_employee_blocked_when_seats_exhausted(self, client, seed_admin, db_engine, monkeypatch):
        """/api/employees (Bearer-token API) is a third, independent
        registration entry point -- must enforce the same cap and surface a
        buy_seats_url for API clients to redirect to."""
        _mock_face_detected(monkeypatch)
        emp_id = "SEATCAP005"
        current = _current_employee_count(db_engine)
        _set_slots(db_engine, current)
        try:
            resp = client.post("/api/login", json={
                "username": seed_admin["username"], "password": seed_admin["password"],
            })
            token = resp.get_json()["token"]
            resp = client.post(
                "/api/employees",
                data={
                    "name": "API Seat Test", "emp_id": emp_id,
                    "face": (io.BytesIO(_fake_jpeg_bytes()), "face.jpg"),
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 402
            body = resp.get_json()
            assert "paid employee seats" in body["msg"]
            assert "buy_seats_url" in body

            cur = db_engine.cursor()
            cur.execute("SELECT employee_id FROM employees WHERE employee_id=%s", (emp_id,))
            assert cur.fetchone() is None
            cur.close()
        finally:
            _cleanup_employee(db_engine, emp_id)
            _set_slots(db_engine, None)


class TestBuySeatsPage:
    def test_renders_unlimited_state(self, client, seed_admin, db_engine):
        _set_slots(db_engine, None)
        try:
            _admin_session(client, seed_admin)
            resp = client.get("/buy_seats")
            assert resp.status_code == 200
            assert b"Unlimited" in resp.data
        finally:
            _set_slots(db_engine, None)

    def test_renders_usage_when_metered(self, client, seed_admin, db_engine):
        current = _current_employee_count(db_engine)
        _set_slots(db_engine, current + 3)
        try:
            _admin_session(client, seed_admin)
            resp = client.get("/buy_seats")
            assert resp.status_code == 200
            assert f"{current} / {current + 3}".encode() in resp.data
        finally:
            _set_slots(db_engine, None)


class TestBuySeatsCheckoutFlow:
    def test_create_seat_order_demo_mode(self, client, seed_admin, db_engine):
        _admin_session(client, seed_admin)
        try:
            resp = client.post("/api/billing/create_seat_order", json={"seats": 5})
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["ok"] is True
            assert data["demo"] is True
            assert data["seats"] == 5
            assert data["order_id"].startswith("demo_order_")
        finally:
            _cleanup_seat_orders(db_engine)

    def test_create_seat_order_rejects_zero_seats(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.post("/api/billing/create_seat_order", json={"seats": 0})
        assert resp.status_code == 400

    def test_verify_seat_payment_increments_paid_slots(self, client, seed_admin, db_engine):
        _set_slots(db_engine, None)
        try:
            _admin_session(client, seed_admin)
            order_resp = client.post("/api/billing/create_seat_order", json={"seats": 4})
            order_id = order_resp.get_json()["order_id"]

            verify_resp = client.post("/api/billing/verify_seat_payment", json={
                "razorpay_order_id": order_id,
                "razorpay_payment_id": "demo_pay_test",
                "razorpay_signature": "demo_signature",
            })
            assert verify_resp.status_code == 200
            data = verify_resp.get_json()
            assert data["ok"] is True
            assert data["seats_added"] == 4
            assert data["paid_employee_slots"] == 4  # COALESCE(NULL,0)+4

            from utils.helpers import get_company_settings, invalidate_settings_cache
            invalidate_settings_cache()
            assert get_company_settings()["paid_employee_slots"] == 4
        finally:
            _set_slots(db_engine, None)
            _cleanup_seat_orders(db_engine)

    def test_verify_seat_payment_is_idempotent(self, client, seed_admin, db_engine):
        _set_slots(db_engine, 2)
        try:
            _admin_session(client, seed_admin)
            order_resp = client.post("/api/billing/create_seat_order", json={"seats": 3})
            order_id = order_resp.get_json()["order_id"]

            payload = {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": "demo_pay_test",
                "razorpay_signature": "demo_signature",
            }
            first = client.post("/api/billing/verify_seat_payment", json=payload)
            assert first.get_json()["paid_employee_slots"] == 5  # 2 + 3

            second = client.post("/api/billing/verify_seat_payment", json=payload)
            assert second.status_code == 200
            assert second.get_json().get("already_applied") is True

            from utils.helpers import get_company_settings, invalidate_settings_cache
            invalidate_settings_cache()
            # Replaying the same paid order must not double-apply the seats.
            assert get_company_settings()["paid_employee_slots"] == 5
        finally:
            _set_slots(db_engine, None)
            _cleanup_seat_orders(db_engine)

    def test_verify_seat_payment_rejects_order_from_another_tenant(self, client, seed_admin, db_engine):
        """A seat_orders row that belongs to a different tenant_id must
        never be redeemable under this session's tenant, even with a
        syntactically valid order id -- see billing.py's
        verify_seat_payment tenant-mismatch check. seat_orders.tenant_id
        is a real FK into tenants, so a throwaway registry row (no actual
        schema) stands in for "some other company"."""
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO att_master.tenants (company_name, subdomain, db_name, status) "
            "VALUES ('Someone Else Inc', 'someone-elses-company', 'att_someone_elses_company', 'active') "
            "RETURNING id"
        )
        foreign_tenant_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO att_master.seat_orders (razorpay_order_id, tenant_id, subdomain, seats, amount_paise, status) "
            "VALUES (%s, %s, 'someone-elses-company', 10, 99000, 'created')",
            ("demo_order_foreign_tenant_test", foreign_tenant_id)
        )
        cur.close()
        try:
            _admin_session(client, seed_admin)
            resp = client.post("/api/billing/verify_seat_payment", json={
                "razorpay_order_id": "demo_order_foreign_tenant_test",
                "razorpay_payment_id": "demo_pay_test",
                "razorpay_signature": "demo_signature",
            })
            assert resp.status_code == 404
        finally:
            cur = db_engine.cursor()
            cur.execute("DELETE FROM att_master.seat_orders WHERE razorpay_order_id=%s", ("demo_order_foreign_tenant_test",))
            cur.execute("DELETE FROM att_master.tenants WHERE id=%s", (foreign_tenant_id,))
            cur.close()
            _set_slots(db_engine, None)
