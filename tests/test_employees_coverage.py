"""Coverage tests for blueprints/employees.py.
Targets: view_employees, api_employee_info, edit_employee_page,
employee_profile, regenerate_qr, view_qrcodes, view_photos,
generate_emp_id, api_employees, delete_employee.
"""
import hashlib
import datetime
import secrets
import pytest


def _admin_session(client, seed_admin):
    client.post("/login", data={
        "identifier": seed_admin["username"],
        "password":   seed_admin["password"],
    })
    return client


def _make_admin_token(db_engine, identity="admin"):
    raw = secrets.token_hex(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    expiry = datetime.datetime.now() + datetime.timedelta(hours=1)
    cur = db_engine.cursor()
    cur.execute(
        "INSERT INTO api_tokens (identity, token, token_type, expires_at) "
        "VALUES (%s,%s,'admin',%s)",
        (identity, token_hash, expiry)
    )
    cur.close()
    def cleanup():
        c = db_engine.cursor()
        c.execute("DELETE FROM api_tokens WHERE token=%s", (token_hash,))
        c.close()
    return raw, cleanup


# ── view_employees ────────────────────────────────────────────────────────────

class TestViewEmployees:

    def test_unauthenticated_redirects(self, client):
        rv = client.get("/employees")
        assert rv.status_code == 302

    def test_renders_for_admin(self, client, seed_admin):
        _admin_session(client, seed_admin)
        rv = client.get("/employees")
        assert rv.status_code == 200

    def test_renders_with_company_filter(self, client, seed_admin):
        _admin_session(client, seed_admin)
        with client.session_transaction() as sess:
            sess["active_company_id"] = 1
        rv = client.get("/employees")
        assert rv.status_code == 200

    def test_seed_employee_shown(self, client, seed_admin, seed_employee):
        _admin_session(client, seed_admin)
        rv = client.get("/employees")
        assert rv.status_code == 200
        assert seed_employee["employee_id"].encode() in rv.data


# ── api_employee_info ─────────────────────────────────────────────────────────

class TestApiEmployeeInfo:

    def test_unauthenticated_redirects(self, client):
        rv = client.get("/api/employee_info/TST001")
        assert rv.status_code in (302, 401)

    def test_known_employee_returns_json(self, client, seed_admin, seed_employee):
        _admin_session(client, seed_admin)
        rv = client.get(f"/api/employee_info/{seed_employee['employee_id']}")
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["emp_id"] == seed_employee["employee_id"]
        assert data["name"]   == seed_employee["name"]

    def test_unknown_employee_returns_404(self, client, seed_admin):
        _admin_session(client, seed_admin)
        rv = client.get("/api/employee_info/GHOST_99999")
        assert rv.status_code == 404
        assert "error" in rv.get_json()


# ── edit_employee_page ────────────────────────────────────────────────────────

class TestEditEmployeePage:

    def test_unauthenticated_redirects(self, client, seed_employee):
        rv = client.get(f"/edit_employee/{seed_employee['employee_id']}")
        assert rv.status_code == 302

    def test_renders_for_known_employee(self, client, seed_admin, seed_employee):
        _admin_session(client, seed_admin)
        rv = client.get(f"/edit_employee/{seed_employee['employee_id']}")
        assert rv.status_code == 200

    def test_unknown_employee_renders_or_404(self, client, seed_admin):
        _admin_session(client, seed_admin)
        rv = client.get("/edit_employee/GHOST_99999")
        assert rv.status_code in (200, 302, 404)


# ── employee_profile ──────────────────────────────────────────────────────────

class TestEmployeeProfile:

    def test_unauthenticated_redirects(self, client, seed_employee):
        rv = client.get(f"/employee_profile/{seed_employee['employee_id']}")
        assert rv.status_code == 302

    def test_renders_for_admin(self, client, seed_admin, seed_employee):
        _admin_session(client, seed_admin)
        rv = client.get(f"/employee_profile/{seed_employee['employee_id']}")
        assert rv.status_code == 200


# ── regenerate_qr ─────────────────────────────────────────────────────────────

class TestRegenerateQr:

    def test_unauthenticated_redirects(self, client, seed_employee):
        rv = client.post(f"/regenerate_qr/{seed_employee['employee_id']}")
        assert rv.status_code == 302

    def test_regenerates_qr_for_known_employee(self, client, seed_admin, seed_employee):
        _admin_session(client, seed_admin)
        rv = client.post(f"/regenerate_qr/{seed_employee['employee_id']}")
        assert rv.status_code == 302


# ── view_qrcodes / view_photos ────────────────────────────────────────────────

class TestViewQrAndPhotos:

    def test_view_qrcodes_renders(self, client, seed_admin):
        _admin_session(client, seed_admin)
        rv = client.get("/view_qrcodes")
        assert rv.status_code in (200, 302)

    def test_view_photos_renders(self, client, seed_admin):
        _admin_session(client, seed_admin)
        rv = client.get("/view_photos")
        assert rv.status_code == 200


# ── generate_emp_id ───────────────────────────────────────────────────────────

class TestGenerateEmpId:

    def test_unauthenticated_redirects(self, client):
        rv = client.get("/api/generate_emp_id")
        assert rv.status_code in (302, 401)

    def test_returns_json_with_emp_id(self, client, seed_admin):
        _admin_session(client, seed_admin)
        rv = client.get("/api/generate_emp_id")
        assert rv.status_code == 200
        data = rv.get_json()
        assert "emp_id" in data
        assert len(data["emp_id"]) > 0


# ── api_employees ─────────────────────────────────────────────────────────────

class TestApiEmployees:

    def test_unauthenticated_returns_401(self, client):
        rv = client.get("/api/employees")
        assert rv.status_code in (302, 401)

    def test_returns_list_for_admin(self, client, db_engine, seed_admin):
        token, cleanup = _make_admin_token(db_engine, identity=seed_admin["username"])
        try:
            rv = client.get("/api/employees",
                            headers={"Authorization": f"Bearer {token}"})
            assert rv.status_code == 200
            data = rv.get_json()
            assert "employees" in data or isinstance(data, list)
        finally:
            cleanup()


# ── delete_employee ───────────────────────────────────────────────────────────

class TestDeleteEmployee:

    def test_unauthenticated_redirects(self, client):
        rv = client.post("/delete_employee/GHOST_99")
        assert rv.status_code == 302

    def test_unknown_employee_redirects(self, client, seed_admin):
        _admin_session(client, seed_admin)
        rv = client.post("/delete_employee/GHOST_NEVER_EXISTS")
        assert rv.status_code == 302

    def test_deletes_employee(self, client, seed_admin, db_engine):
        from utils.auth import generate_password_hash
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO employees (employee_id, name, email, password) "
            "VALUES ('DEL001','Del Test','del@test.local',%s) ON CONFLICT DO NOTHING",
            (generate_password_hash("Del@123"),)
        )
        cur.close()
        _admin_session(client, seed_admin)
        rv = client.post("/delete_employee/DEL001")
        assert rv.status_code == 302
        cur = db_engine.cursor()
        cur.execute("SELECT 1 FROM employees WHERE employee_id='DEL001'")
        assert cur.fetchone() is None
        cur.close()


# ── edit_employee POST ────────────────────────────────────────────────────────

class TestEditEmployee:

    def test_unauthenticated_redirects(self, client):
        rv = client.post("/edit_employee", data={"emp_id": "TST001"})
        assert rv.status_code == 302

    def test_updates_employee_name(self, client, seed_admin, seed_employee, db_engine):
        _admin_session(client, seed_admin)
        rv = client.post("/edit_employee", data={
            "emp_id":          seed_employee["employee_id"],
            "name":            "Updated Name",
            "role":            "Engineer",
            "email":           "emp@test.local",
            "date_of_joining": "2024-01-01",
            "work_mode":       "office",
            "department":      "Engineering",
        })
        assert rv.status_code == 302
        cur = db_engine.cursor()
        cur.execute("SELECT name FROM employees WHERE employee_id=%s",
                    (seed_employee["employee_id"],))
        name = cur.fetchone()[0]
        cur.close()
        assert name == "Updated Name"
        cur = db_engine.cursor()
        cur.execute("UPDATE employees SET name=%s WHERE employee_id=%s",
                    (seed_employee["name"], seed_employee["employee_id"]))
        cur.close()
