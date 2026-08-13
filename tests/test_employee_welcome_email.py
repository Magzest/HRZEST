"""New-employee welcome emails now include a clickable link to the
tenant's own login page, not just bare credentials (previously the email
listed an Employee ID + password with nowhere to use them). Covers all 4
employee-creation entry points: /admin_action (register), /add_employee_page,
the Bearer-token /api/employees, and the self-service /api/employee/signup.

get_email_config()/send_email_smtp() are monkeypatched per call site
(imported directly into each blueprint module, same pattern
tests/test_org.py uses for org_module.get_email_config) so these tests
don't depend on real SMTP being configured.
"""
import io
import datetime
import os
from PIL import Image

import utils.face_utils as face_utils
from extensions import app as flask_app

UPLOAD_FOLDER = flask_app.config["UPLOAD_FOLDER"]
QR_FOLDER = os.path.join(os.path.dirname(os.path.abspath(UPLOAD_FOLDER)), "static", "qrcodes")


def _fake_jpeg_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color=(80, 90, 100)).save(buf, format="JPEG")
    buf.seek(0)
    return buf.read()


def _mock_face_detected(monkeypatch):
    monkeypatch.setattr(face_utils.face_recognition, "load_image_file", lambda p: "img")
    monkeypatch.setattr(face_utils.face_recognition, "face_encodings", lambda img: ["enc"])


def _admin_session(client, seed_admin):
    resp = client.post("/login", data={
        "identifier": seed_admin["username"], "password": seed_admin["password"],
    }, follow_redirects=True)
    assert resp.status_code == 200


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


class TestEmployeeLoginUrlHelper:
    def test_no_session_falls_back_to_bare_login(self, client):
        with flask_app.test_request_context("/"):
            from utils.helpers import employee_login_url
            url = employee_login_url()
            assert url.endswith("/login")
            assert url.startswith("http")

    def test_tenant_slug_in_session_is_included(self, client):
        with flask_app.test_request_context("/"):
            from flask import session
            session["tenant_slug"] = "acme"
            from utils.helpers import employee_login_url
            url = employee_login_url()
            assert url.endswith("/acme/login")


class TestAdminActionWelcomeEmail:
    def test_register_sends_email_with_login_link(self, client, seed_admin, db_engine, monkeypatch):
        _mock_face_detected(monkeypatch)
        import blueprints.employees as employees_module
        monkeypatch.setattr(employees_module, "get_email_config", lambda: {"host": "smtp.test"})
        sent = []
        monkeypatch.setattr(employees_module, "send_email_smtp",
                             lambda to, subject, html, cfg: sent.append((to, subject, html)))

        emp_id = "WELMAIL001"
        try:
            _admin_session(client, seed_admin)
            resp = client.post("/admin_action", data={
                "action": "register", "name": "Welcome Mail Test", "emp_id": emp_id,
                "email": "welmail001@test.local", "role": "Developer",
                "date_of_joining": datetime.date.today().isoformat(), "work_mode": "office",
                "face": (io.BytesIO(_fake_jpeg_bytes()), "face.jpg"),
            }, follow_redirects=True)
            assert resp.status_code == 200

            assert len(sent) == 1
            to, subject, html = sent[0]
            assert to == "welmail001@test.local"
            assert "/login" in html
            assert "http" in html
        finally:
            _cleanup_employee(db_engine, emp_id)


class TestAddEmployeePageWelcomeEmail:
    def test_add_employee_sends_email_with_login_link(self, client, seed_admin, db_engine, monkeypatch):
        _mock_face_detected(monkeypatch)
        import blueprints.employees as employees_module
        monkeypatch.setattr(employees_module, "get_email_config", lambda: {"host": "smtp.test"})
        sent = []
        monkeypatch.setattr(employees_module, "send_email_smtp",
                             lambda to, subject, html, cfg: sent.append((to, subject, html)))

        emp_id = "WELMAIL002"
        try:
            _admin_session(client, seed_admin)
            resp = client.post("/add_employee_page", data={
                "name": "Welcome Mail Test 2", "emp_id": emp_id,
                "email": "welmail002@test.local", "role": "Developer",
                "face": (io.BytesIO(_fake_jpeg_bytes()), "face.jpg"),
            }, follow_redirects=True)
            assert resp.status_code == 200

            assert len(sent) == 1
            to, subject, html = sent[0]
            assert to == "welmail002@test.local"
            assert "/login" in html
        finally:
            _cleanup_employee(db_engine, emp_id)


class TestApiRegisterEmployeeWelcomeEmail:
    def test_api_register_sends_email_with_login_link(self, client, seed_admin, db_engine, monkeypatch):
        _mock_face_detected(monkeypatch)
        import blueprints.employees as employees_module
        monkeypatch.setattr(employees_module, "get_email_config", lambda: {"host": "smtp.test"})
        sent = []
        monkeypatch.setattr(employees_module, "send_email_smtp",
                             lambda to, subject, html, cfg: sent.append((to, subject, html)))

        emp_id = "WELMAIL003"
        try:
            resp = client.post("/api/login", json={
                "username": seed_admin["username"], "password": seed_admin["password"],
            })
            token = resp.get_json()["token"]
            resp = client.post(
                "/api/employees",
                data={
                    "name": "Welcome Mail Test 3", "emp_id": emp_id,
                    "email": "welmail003@test.local",
                    "face": (io.BytesIO(_fake_jpeg_bytes()), "face.jpg"),
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200

            assert len(sent) == 1
            to, subject, html = sent[0]
            assert to == "welmail003@test.local"
            assert "/login" in html
        finally:
            _cleanup_employee(db_engine, emp_id)


class TestApiEmployeeSignupWelcomeEmail:
    def test_self_signup_sends_email_with_login_link_no_password(self, client, db_engine, monkeypatch):
        import blueprints.core as core_module
        monkeypatch.setattr(core_module, "get_email_config", lambda: {"host": "smtp.test"})
        sent = []
        monkeypatch.setattr(core_module, "send_email_smtp",
                             lambda to, subject, html, cfg: sent.append((to, subject, html)))

        emp_id = "WELMAIL004"
        try:
            resp = client.post("/api/employee/signup", json={
                "employee_id": emp_id, "name": "Welcome Mail Test 4",
                "email": "welmail004@test.local", "password": "SelfChosen@1",
            })
            assert resp.status_code == 200

            assert len(sent) == 1
            to, subject, html = sent[0]
            assert to == "welmail004@test.local"
            assert "/login" in html
            # Self-service signup: the employee already knows the password
            # they typed -- don't echo it back into the email.
            assert "SelfChosen@1" not in html
        finally:
            _cleanup_employee(db_engine, emp_id)
