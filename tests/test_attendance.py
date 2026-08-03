"""
Attendance blueprint tests — check-in/out state machine, geofencing,
shifts, breaks, and admin reports.

Written specifically to close the coverage gap left after the app.py ->
blueprints/attendance.py migration, and to regression-guard the two
check-in crash bugs found during that migration: a local `cfg` variable
shadowing the module-level `utils.config as cfg` import caused
AttributeError on every office check-in with location enabled (the
default). See TestCheckinGeofencing below.

Run with:
    python -m pytest tests/test_attendance.py -v
"""
import datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _admin_session(client, seed_admin):
    resp = client.post("/admin_login", data={
        "identifier": seed_admin["username"],
        "password": seed_admin["password"],
    }, follow_redirects=True)
    assert resp.status_code == 200
    return resp


def _make_office_employee(db_engine, employee_id="ATT_OFF01", name="Office Emp"):
    """Insert an employee with work_mode='office' (the default check-in path
    that hits cfg.OFFICE_LAT/OFFICE_LON — the exact branch the shadowing
    bug broke)."""
    cur = db_engine.cursor()
    cur.execute(
        "INSERT INTO employees (employee_id, name, email, password, force_pin_change, work_mode) "
        "VALUES (%s,%s,%s,%s,0,'office') ON CONFLICT (employee_id) DO UPDATE SET work_mode='office'",
        (employee_id, name, f"{employee_id.lower()}@test.local", "x"),
    )
    cur.close()
    return employee_id


def _cleanup_employee(db_engine, employee_id):
    cur = db_engine.cursor()
    cur.execute("DELETE FROM attendance WHERE employee_id=%s", (employee_id,))
    cur.execute("DELETE FROM employees WHERE employee_id=%s", (employee_id,))
    cur.close()


# ===========================================================================
# Check-in geofencing — regression coverage for the cfg-shadowing bug
# ===========================================================================

class TestCheckinGeofencing:
    def test_checkin_office_employee_outside_radius_returns_json_not_500(self, client, db_engine):
        """The exact bug: auth_cfg = get_auth_config() used to be named `cfg`,
        shadowing `import utils.config as cfg` for the whole function. Once
        an office employee with valid lat/lon hit the geofence-distance
        branch (now utils.attendance_utils.is_within_office_range, reading
        company_settings.office_lat/office_lon instead of the old
        process-wide cfg.OFFICE_LAT/OFFICE_LON), cfg was a dict (no
        .OFFICE_LAT attribute) -> AttributeError -> 500.

        is_within_office_range() is a no-op (never rejects) unless the
        tenant has actually configured an office location, so this test
        sets one -- coordinates near the equator/prime meridian are never
        within radius of it, reliably exercising the distance-check branch."""
        from utils.helpers import invalidate_settings_cache
        emp_id = _make_office_employee(db_engine)
        cur = db_engine.cursor()
        cur.execute("UPDATE company_settings SET location_enabled=1, office_lat=17.4, office_lon=78.4, geo_radius=300")
        cur.close()
        invalidate_settings_cache()
        try:
            resp = client.post("/attendance", json={
                "employee_id": emp_id,
                "auth_combo": "qr_only",
                "lat": "1.0",
                "lon": "1.0",
            })
            assert resp.status_code == 200
            body = resp.get_json()
            assert body["ok"] is False
            assert "office premises" in body["msg"]
        finally:
            _cleanup_employee(db_engine, emp_id)
            cur = db_engine.cursor()
            cur.execute("UPDATE company_settings SET office_lat=NULL, office_lon=NULL")
            cur.close()
            invalidate_settings_cache()

    def test_checkin_unknown_employee_returns_not_found(self, client):
        resp = client.post("/attendance", json={
            "employee_id": "NO_SUCH_EMP",
            "auth_combo": "qr_only",
        })
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is False


class TestIsWithinOfficeRange:
    """Direct unit tests for utils.attendance_utils.is_within_office_range,
    which replaced always-on geofencing against a single process-wide
    OFFICE_LAT/LON with a per-tenant, opt-in check. See TestCheckinGeofencing
    above for the route-level regression test.

    get_auth_config() (which this function calls) reads via
    get_db_connection(), which resolves the tenant schema from
    flask.g.tenant_db -- a plain function call outside of a real
    client.get/post() has no before_request hook to set that, so each test
    establishes it explicitly via test_request_context()."""

    def _in_context(self, client, fn, *args):
        import os
        from flask import g as _g
        with client.application.test_request_context("/"):
            _g.tenant_db = os.environ.get("DB_NAME")
            return fn(*args)

    def test_no_op_when_office_location_not_configured(self, client, db_engine):
        from utils.attendance_utils import is_within_office_range
        from utils.helpers import invalidate_settings_cache
        cur = db_engine.cursor()
        cur.execute("UPDATE company_settings SET location_enabled=1, office_lat=NULL, office_lon=NULL")
        cur.close()
        invalidate_settings_cache()
        # Coordinates nowhere near any real office -- must still pass,
        # since no office location has been set yet.
        assert self._in_context(client, is_within_office_range, 1.0, 1.0) is True

    def test_no_op_when_location_disabled_even_if_configured(self, client, db_engine):
        from utils.attendance_utils import is_within_office_range
        from utils.helpers import invalidate_settings_cache
        cur = db_engine.cursor()
        cur.execute("UPDATE company_settings SET location_enabled=0, office_lat=17.4, office_lon=78.4, geo_radius=300")
        cur.close()
        invalidate_settings_cache()
        try:
            assert self._in_context(client, is_within_office_range, 1.0, 1.0) is True
        finally:
            cur = db_engine.cursor()
            cur.execute("UPDATE company_settings SET location_enabled=1, office_lat=NULL, office_lon=NULL")
            cur.close()
            invalidate_settings_cache()

    def test_rejects_outside_radius_when_configured(self, client, db_engine):
        from utils.attendance_utils import is_within_office_range
        from utils.helpers import invalidate_settings_cache
        cur = db_engine.cursor()
        cur.execute("UPDATE company_settings SET location_enabled=1, office_lat=17.4, office_lon=78.4, geo_radius=300")
        cur.close()
        invalidate_settings_cache()
        try:
            assert self._in_context(client, is_within_office_range, 1.0, 1.0) is False
            assert self._in_context(client, is_within_office_range, 17.4, 78.4) is True
        finally:
            cur = db_engine.cursor()
            cur.execute("UPDATE company_settings SET office_lat=NULL, office_lon=NULL")
            cur.close()
            invalidate_settings_cache()

    def test_checkin_invalid_auth_combo_rejected(self, client, db_engine):
        emp_id = _make_office_employee(db_engine, "ATT_OFF02")
        try:
            resp = client.post("/attendance", json={
                "employee_id": emp_id,
                "auth_combo": "not_a_real_combo",
            })
            assert resp.status_code == 200
            assert resp.get_json()["ok"] is False
        finally:
            _cleanup_employee(db_engine, emp_id)

    def test_checkin_missing_employee_id(self, client):
        resp = client.post("/attendance", json={"auth_combo": "qr_only"})
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is False


# ===========================================================================
# Check-in state machine — login -> logout -> re-login, bypassing geofencing
# via auth_combo="fingerprint_only" is not possible without a verified
# fingerprint proof, so these use location_enabled-independent coverage by
# targeting a wfh employee with matching home coordinates instead.
# ===========================================================================

class TestCheckinStateMachine:
    def _make_wfh_employee(self, db_engine, employee_id="ATT_WFH01"):
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO employees (employee_id, name, email, password, force_pin_change, "
            "work_mode, work_lat, work_lon) VALUES (%s,%s,%s,%s,0,'wfh',%s,%s) "
            "ON CONFLICT (employee_id) DO UPDATE SET work_mode='wfh', work_lat=%s, work_lon=%s",
            (employee_id, "WFH Emp", f"{employee_id.lower()}@test.local", "x",
             12.9716, 77.5946, 12.9716, 77.5946),
        )
        cur.close()
        return employee_id

    def test_first_checkin_of_day_creates_login_record(self, client, db_engine):
        emp_id = self._make_wfh_employee(db_engine)
        try:
            resp = client.post("/attendance", json={
                "employee_id": emp_id,
                "auth_combo": "qr_only",
                "lat": "12.9716",
                "lon": "77.5946",
            })
            assert resp.status_code == 200
            body = resp.get_json()
            assert body["ok"] is True
            assert body["type"] == "login"
            assert body["status"] in ("Full Day Login", "Late Login", "Half Day Login")
        finally:
            _cleanup_employee(db_engine, emp_id)

    def test_second_checkin_same_day_is_logout(self, client, db_engine):
        emp_id = self._make_wfh_employee(db_engine, "ATT_WFH02")
        try:
            payload = {"employee_id": emp_id, "auth_combo": "qr_only", "lat": "12.9716", "lon": "77.5946"}
            r1 = client.post("/attendance", json=payload)
            assert r1.get_json()["type"] == "login"
            r2 = client.post("/attendance", json=payload)
            assert r2.status_code == 200
            body2 = r2.get_json()
            assert body2["ok"] is True
            assert body2["type"] == "logout"
        finally:
            _cleanup_employee(db_engine, emp_id)

    def test_third_checkin_same_day_reopens_session(self, client, db_engine):
        emp_id = self._make_wfh_employee(db_engine, "ATT_WFH03")
        try:
            payload = {"employee_id": emp_id, "auth_combo": "qr_only", "lat": "12.9716", "lon": "77.5946"}
            client.post("/attendance", json=payload)
            client.post("/attendance", json=payload)
            r3 = client.post("/attendance", json=payload)
            assert r3.status_code == 200
            assert r3.get_json()["ok"] is True
        finally:
            _cleanup_employee(db_engine, emp_id)


# ===========================================================================
# /location — plain geofence check (no attendance write)
# ===========================================================================

class TestLocationEndpoint:
    def test_location_missing_fields(self, client):
        resp = client.post("/location", json={})
        assert resp.status_code in (200, 400)


# ===========================================================================
# Admin dashboard / reports — session-authenticated routes
# ===========================================================================

class TestAdminAttendanceViews:
    def test_today_present_requires_admin(self, client):
        resp = client.get("/today_present", follow_redirects=False)
        assert resp.status_code in (302, 401, 403)

    def test_today_present_renders_for_admin(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.get("/today_present")
        assert resp.status_code == 200

    def test_today_absent_renders_for_admin(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.get("/today_absent")
        assert resp.status_code == 200

    def test_today_late_renders_for_admin(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.get("/today_late")
        assert resp.status_code == 200

    def test_monthly_report_renders_for_admin(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.get("/monthly_report")
        assert resp.status_code == 200

    def test_monthly_report_export_returns_file(self, client, seed_admin):
        _admin_session(client, seed_admin)
        today = datetime.date.today()
        resp = client.get(f"/monthly_report_export?year={today.year}&month={today.month}")
        assert resp.status_code == 200

    def test_employee_attendance_detail_for_admin(self, client, seed_admin, seed_employee):
        _admin_session(client, seed_admin)
        today = datetime.date.today()
        resp = client.get(
            f"/employee_attendance_detail/{seed_employee['employee_id']}/{today.year}/{today.month}"
        )
        assert resp.status_code == 200

    def test_bulk_mark_attendance_get_renders(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.get("/bulk_mark_attendance")
        assert resp.status_code == 200

    def test_correct_attendance_requires_admin(self, client):
        resp = client.post("/correct_attendance", data={}, follow_redirects=False)
        assert resp.status_code in (302, 401, 403)

    def test_send_absentee_report_requires_admin(self, client):
        resp = client.post("/send_absentee_report", data={}, follow_redirects=False)
        assert resp.status_code in (302, 401, 403)


# ===========================================================================
# Shifts CRUD — admin-only
# ===========================================================================

class TestShiftsCRUD:
    def test_shifts_page_redirects_to_settings(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.get("/shifts", follow_redirects=False)
        assert resp.status_code in (301, 302)

    def test_add_shift_and_delete(self, client, seed_admin, db_engine):
        _admin_session(client, seed_admin)
        resp = client.post("/add_shift", data={
            "shift_name": "Test Shift", "start_time": "09:00",
            "half_time": "13:00", "end_time": "18:00",
        }, follow_redirects=False)
        assert resp.status_code in (301, 302)
        cur = db_engine.cursor()
        cur.execute("SELECT id FROM shifts WHERE name='Test Shift'")
        row = cur.fetchone()
        assert row is not None
        shift_id = row[0]
        cur.close()
        del_resp = client.post(f"/delete_shift/{shift_id}", follow_redirects=False)
        assert del_resp.status_code in (301, 302)
        cur2 = db_engine.cursor()
        cur2.execute("SELECT id FROM shifts WHERE id=%s", (shift_id,))
        assert cur2.fetchone() is None
        cur2.close()

    def test_edit_shift_nonexistent(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.post("/edit_shift/999999", data={
            "name": "X", "start_time": "09:00", "half_time": "13:00", "end_time": "18:00",
        }, follow_redirects=False)
        assert resp.status_code in (301, 302)

    def test_update_default_shift_requires_admin(self, client):
        resp = client.post("/update_default_shift", data={}, follow_redirects=False)
        assert resp.status_code in (302, 401, 403)

    def test_bulk_assign_shift_requires_admin(self, client):
        resp = client.post("/bulk_assign_shift", data={}, follow_redirects=False)
        assert resp.status_code in (302, 401, 403)

    def test_assign_shift_requires_admin(self, client):
        resp = client.post("/assign_shift", data={}, follow_redirects=False)
        assert resp.status_code in (302, 401, 403)


# ===========================================================================
# Shift swaps
# ===========================================================================

class TestShiftSwaps:
    def test_admin_shift_swaps_page_for_admin(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.get("/admin_shift_swaps")
        assert resp.status_code == 200

    def test_submit_shift_swap_requires_employee_session(self, client):
        resp = client.post("/submit_shift_swap", data={}, follow_redirects=False)
        assert resp.status_code in (302, 401, 403)

    def test_respond_shift_swap_nonexistent(self, client, seed_employee):
        with client.session_transaction() as sess:
            sess["employee_id"] = seed_employee["employee_id"]
        resp = client.post("/respond_shift_swap/999999", data={"response": "accept"}, follow_redirects=False)
        assert resp.status_code in (200, 302, 404)

    def test_admin_shift_swap_nonexistent(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.post("/admin_shift_swap/999999", data={"action": "approve"}, follow_redirects=False)
        assert resp.status_code in (200, 302, 404)


# ===========================================================================
# Breaks
# ===========================================================================

class TestBreaks:
    def test_break_config_page_for_admin(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.get("/break_config")
        assert resp.status_code in (200, 302)

    def test_add_break_persists_row(self, client, seed_admin, db_engine):
        _admin_session(client, seed_admin)
        resp = client.post("/add_break", data={
            "break_name": "Test Break", "break_time": "13:00", "duration_minutes": "30",
        }, follow_redirects=False)
        assert resp.status_code in (301, 302)
        cur = db_engine.cursor()
        cur.execute("SELECT id FROM break_config WHERE break_name='Test Break'")
        row = cur.fetchone()
        assert row is not None
        cur.execute("DELETE FROM break_config WHERE id=%s", (row[0],))
        cur.close()

    def test_add_break_missing_time_rejected_not_500(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.post("/add_break", data={
            "break_name": "No Time Break", "break_time": "",
        }, follow_redirects=False)
        assert resp.status_code in (301, 302)

    def test_update_break_nonexistent(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.post("/update_break/999999", data={
            "break_name": "X", "break_time": "13:00", "duration_minutes": "15",
        }, follow_redirects=False)
        assert resp.status_code in (301, 302)

    def test_delete_break_nonexistent(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.post("/delete_break/999999", follow_redirects=False)
        assert resp.status_code in (301, 302)
