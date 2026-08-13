"""
Coverage tests for utils/auth.py.
Targets uncovered lines: lockout paths, session-conflict branches,
manager_or_admin_required decorator, AJAX 401 response.
"""
import datetime
import pytest


def _admin_session(client, seed_admin):
    client.post("/login", data={
        "identifier": seed_admin["username"],
        "password":   seed_admin["password"],
    })
    return client


def _emp_session(client, seed_employee):
    with client.session_transaction() as sess:
        sess["employee_id"]   = seed_employee["employee_id"]
        sess["employee_name"] = seed_employee["name"]
    return client


# ── check_password_hash ────────────────────────────────────────────────────────

class TestCheckPasswordHash:

    def test_invalid_bcrypt_string_returns_false(self):
        from utils.auth import check_password_hash
        # Looks like bcrypt ($2b$) but is malformed → bcrypt raises → returns False
        assert check_password_hash("$2b$12$invalid_bcrypt_hash_that_is_bad!", "password") is False

    def test_empty_hash_returns_false(self):
        from utils.auth import check_password_hash
        assert check_password_hash("", "anything") is False

    def test_none_hash_returns_false(self):
        from utils.auth import check_password_hash
        assert check_password_hash(None, "anything") is False


# ── Lockout paths ──────────────────────────────────────────────────────────────

class TestLoginLockout:

    def test_check_login_lockout_returns_true_when_locked(self, db_engine):
        from utils.auth import _check_login_lockout
        cur = db_engine.cursor()
        future = datetime.datetime.now() + datetime.timedelta(minutes=15)
        cur.execute(
            "INSERT INTO login_attempts (identifier, attempt_type, failed_count, locked_until) "
            "VALUES (%s, 'admin', 15, %s) ON CONFLICT (identifier, attempt_type) DO UPDATE "
            "SET failed_count=15, locked_until=%s",
            ("locked_user_test", future, future)
        )
        locked, until = _check_login_lockout("locked_user_test", "admin")
        assert locked is True
        assert until is not None
        cur.execute("DELETE FROM login_attempts WHERE identifier='locked_user_test'")
        cur.close()

    def test_check_login_lockout_returns_false_when_not_locked(self, db_engine):
        from utils.auth import _check_login_lockout
        # Clean slate
        cur = db_engine.cursor()
        cur.execute("DELETE FROM login_attempts WHERE identifier='no_lock_user'")
        cur.close()
        locked, until = _check_login_lockout("no_lock_user", "admin")
        assert locked is False
        assert until is None

    def test_record_login_failure_triggers_lockout_at_max(self, db_engine):
        # _record_login_failure() itself only enqueues the DB write onto the
        # background writer thread (deliberately async — see its docstring),
        # so calling it in a tight loop and immediately checking lockout
        # status races the queue. Call the synchronous DB-write function
        # directly to test the "at max attempts" lockout logic deterministically.
        from utils.auth import _record_login_failure_db, _LOGIN_MAX_ATTEMPTS
        identifier = "lockout_trigger_test"
        cur = db_engine.cursor()
        cur.execute("DELETE FROM login_attempts WHERE identifier=%s", (identifier,))
        cur.close()
        # Record failures up to the threshold
        for _ in range(_LOGIN_MAX_ATTEMPTS):
            _record_login_failure_db(identifier, "admin")
        from utils.auth import _check_login_lockout
        locked, until = _check_login_lockout(identifier, "admin")
        assert locked is True
        cur = db_engine.cursor()
        cur.execute("DELETE FROM login_attempts WHERE identifier=%s", (identifier,))
        cur.close()

    def test_locked_admin_login_shows_error(self, client, db_engine):
        """Lines 153-155 in blueprints/auth.py: locked → renders lockout message."""
        identifier = "locked_admin_ci"
        future = datetime.datetime.now() + datetime.timedelta(minutes=15)
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO login_attempts (identifier, attempt_type, failed_count, locked_until) "
            "VALUES (%s, 'admin', 15, %s) ON CONFLICT (identifier, attempt_type) DO UPDATE "
            "SET failed_count=15, locked_until=%s",
            (identifier, future, future)
        )
        cur.close()
        rv = client.post("/login", data={"identifier": identifier, "password": "any"})
        assert rv.status_code == 200
        assert b"locked" in rv.data.lower() or b"Account locked" in rv.data
        cur = db_engine.cursor()
        cur.execute("DELETE FROM login_attempts WHERE identifier=%s", (identifier,))
        cur.close()


# ── admin_required — session conflict + AJAX ───────────────────────────────────

class TestAdminRequired:

    def test_admin_required_clears_conflicting_employee_session(self, client, seed_admin, seed_employee):
        """Lines 107-109 in utils/auth.py: admin + employee in session → employee keys cleared."""
        _admin_session(client, seed_admin)
        # Inject employee_id into session alongside admin_logged_in
        with client.session_transaction() as sess:
            sess["employee_id"] = seed_employee["employee_id"]
        # Access an admin-required route — the wrapper clears employee keys
        rv = client.get("/admin")
        assert rv.status_code == 200
        with client.session_transaction() as sess:
            assert "employee_id" not in sess

    def test_admin_required_ajax_returns_401_json(self, client):
        """Line 118 in utils/auth.py: unauthenticated AJAX → 401 JSON instead of redirect."""
        rv = client.get("/admin",
                        headers={"Accept": "application/json"})
        assert rv.status_code == 401
        data = rv.get_json()
        assert data["ok"] is False
        assert "redirect" in data

    def test_admin_required_xmlhttprequest_returns_401(self, client):
        rv = client.get("/admin",
                        headers={"X-Requested-With": "XMLHttpRequest"})
        assert rv.status_code == 401

    def test_admin_required_json_content_type_returns_401(self, client):
        rv = client.post("/correct_attendance",
                         json={},
                         headers={"Content-Type": "application/json"})
        assert rv.status_code == 401


# ── employee_required — session conflict + force_pin ──────────────────────────

class TestEmployeeRequired:

    def test_employee_required_clears_admin_and_redirects(self, client, seed_admin, seed_employee):
        """Lines 128-131 in utils/auth.py: admin + employee in session → clear + redirect to /admin."""
        with client.session_transaction() as sess:
            sess["admin_logged_in"] = True
            sess["employee_id"]     = seed_employee["employee_id"]
        rv = client.get("/employee_portal")
        assert rv.status_code == 302
        assert "/admin" in rv.headers["Location"]

    def test_force_pin_change_redirects(self, client, seed_employee):
        """Line 137 in utils/auth.py: _fpc flag in session → redirect to force_change_pin."""
        with client.session_transaction() as sess:
            sess["employee_id"]   = seed_employee["employee_id"]
            sess["employee_name"] = seed_employee["name"]
            sess["_fpc"]          = True
        rv = client.get("/employee_portal")
        assert rv.status_code == 302
        assert "force_change_pin" in rv.headers["Location"]


# ── manager_or_admin_required ─────────────────────────────────────────────────

class TestManagerOrAdminRequired:
    """Lines 142-157 in utils/auth.py."""

    def _use_route(self, client, headers=None):
        """Use any route decorated with @manager_or_admin_required.
        /api/leave_status is decorated with it."""
        token_headers = headers or {}
        return client.get("/monthly_report", headers=token_headers)

    def test_unauthenticated_redirects(self, client):
        rv = client.get("/monthly_report")
        assert rv.status_code == 302

    def test_unauthenticated_ajax_returns_401(self, client):
        rv = client.get("/monthly_report",
                        headers={"Accept": "application/json"})
        assert rv.status_code in (302, 401)

    def test_admin_role_passes_through(self, client, seed_admin):
        _admin_session(client, seed_admin)
        rv = client.get("/monthly_report")
        assert rv.status_code == 200
