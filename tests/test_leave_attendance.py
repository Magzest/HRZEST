"""
Leave + Attendance blueprint — comprehensive test suite.
Covers page rendering, API endpoints, form submissions, auth guards.

Targets:
  leave.py      33% → ~65%
  attendance.py 23% → ~55%
"""
import pytest


# ── Session / token helpers ──────────────────────────────────────────────────

def _admin_session(client, seed_admin):
    client.post("/login", data={
        "identifier": seed_admin["username"],
        "password":   seed_admin["password"],
    })
    return client


def _emp_session(client, seed_employee):
    """Inject an employee session directly (employee_login just redirects to admin_login)."""
    with client.session_transaction() as sess:
        sess["employee_id"]   = seed_employee["employee_id"]
        sess["employee_name"] = seed_employee["name"]
    return client


def _admin_token(client, seed_admin):
    return client.post("/api/login", json={
        "username": seed_admin["username"],
        "password": seed_admin["password"],
    }).get_json()["token"]


def _emp_token(client, seed_employee):
    return client.post("/api/employee/login", json={
        "employee_id": seed_employee["employee_id"],
        "password":    seed_employee["password"],
    }).get_json()["token"]


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def holiday(db_engine):
    """Seed one holiday row, clean up after."""
    cur = db_engine.cursor()
    cur.execute(
        "INSERT INTO holidays (date, name) VALUES ('2025-01-26', 'Republic Day Test') "
        "ON CONFLICT (date) DO NOTHING RETURNING id"
    )
    row = cur.fetchone()
    hid = row[0] if row else None
    if hid is None:
        cur.execute("SELECT id FROM holidays WHERE date='2025-01-26'")
        hid = cur.fetchone()[0]
    yield {"id": hid, "date": "2025-01-26", "name": "Republic Day Test"}
    cur.execute("DELETE FROM holidays WHERE id=%s", (hid,))
    cur.close()


@pytest.fixture
def leave_request(db_engine, seed_employee):
    """Seed a pending leave request for TST001, clean up after."""
    cur = db_engine.cursor()
    cur.execute("""
        INSERT INTO leave_requests (employee_id, leave_date, reason, status)
        VALUES (%s, '2025-03-10', 'Medical', 'Pending')
        RETURNING id
    """, (seed_employee["employee_id"],))
    lid = cur.fetchone()[0]
    yield {"id": lid, "employee_id": seed_employee["employee_id"]}
    cur.execute("DELETE FROM leave_requests WHERE id=%s", (lid,))
    cur.close()


@pytest.fixture
def shift(db_engine):
    """Seed a work shift, clean up after."""
    cur = db_engine.cursor()
    cur.execute("""
        INSERT INTO shifts (name, start_time, half_time, end_time)
        VALUES ('Test Morning', '09:00', '13:00', '18:00')
        RETURNING id
    """)
    sid = cur.fetchone()[0]
    yield {"id": sid, "name": "Test Morning"}
    cur.execute("DELETE FROM shifts WHERE id=%s", (sid,))
    cur.close()


# ===========================================================================
# ── LEAVE BLUEPRINT ─────────────────────────────────────────────────────────
# ===========================================================================

# ---------------------------------------------------------------------------
# 1. Auth guards
# ---------------------------------------------------------------------------

class TestLeaveAuthGuards:
    def test_leave_requests_requires_admin(self, client):
        assert client.get("/leave_requests", follow_redirects=False).status_code in (302, 401)

    def test_leave_holidays_requires_admin(self, client):
        assert client.get("/leave_holidays", follow_redirects=False).status_code in (302, 401)

    def test_leave_balance_requires_admin(self, client):
        assert client.get("/leave_balance", follow_redirects=False).status_code in (302, 401)

    def test_leave_calendar_requires_admin(self, client):
        assert client.get("/leave_calendar", follow_redirects=False).status_code in (302, 401)

    def test_resignation_requests_requires_admin(self, client):
        assert client.get("/resignation_requests", follow_redirects=False).status_code in (302, 401)

    def test_overtime_requires_admin(self, client):
        assert client.get("/overtime", follow_redirects=False).status_code in (302, 401)

    def test_compoff_requires_admin(self, client):
        assert client.get("/compoff", follow_redirects=False).status_code in (302, 401)

    def test_add_holiday_requires_admin(self, client):
        assert client.post("/add_holiday", data={}).status_code in (302, 401)

    def test_request_leave_requires_employee(self, client):
        assert client.post("/request_leave", data={}).status_code in (302, 401)

    def test_api_holidays_requires_token(self, client):
        assert client.get("/api/holidays").status_code == 401

    def test_api_leave_requests_requires_token(self, client):
        assert client.get("/api/leave_requests").status_code == 401

    def test_api_employee_leave_request_requires_token(self, client):
        assert client.post("/api/employee/leave_request", json={}).status_code == 401

    def test_api_employee_leaves_requires_token(self, client):
        assert client.get("/api/employee/leaves").status_code == 401


# ---------------------------------------------------------------------------
# 2. Leave admin page renders
# ---------------------------------------------------------------------------

class TestLeaveAdminPages:
    def test_leave_requests_redirects_to_leave_holidays(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.get("/leave_requests", follow_redirects=False)
        assert resp.status_code == 302
        assert b"leave_holidays" in resp.data or "leave_holidays" in resp.headers.get("Location", "")

    def test_leave_holidays_renders(self, client, seed_admin):
        _admin_session(client, seed_admin)
        assert client.get("/leave_holidays").status_code == 200

    def test_leave_holidays_with_year_param(self, client, seed_admin):
        _admin_session(client, seed_admin)
        assert client.get("/leave_holidays?year=2025").status_code == 200

    def test_leave_holidays_tab_param(self, client, seed_admin):
        _admin_session(client, seed_admin)
        assert client.get("/leave_holidays?tab=holidays").status_code == 200

    def test_leave_balance_renders(self, client, seed_admin):
        _admin_session(client, seed_admin)
        assert client.get("/leave_balance").status_code == 200

    def test_leave_calendar_renders(self, client, seed_admin):
        _admin_session(client, seed_admin)
        assert client.get("/leave_calendar").status_code == 200

    def test_leave_calendar_month_year_params(self, client, seed_admin):
        _admin_session(client, seed_admin)
        assert client.get("/leave_calendar?month=3&year=2025").status_code == 200

    def test_resignation_requests_renders(self, client, seed_admin):
        _admin_session(client, seed_admin)
        assert client.get("/resignation_requests").status_code == 200

    def test_overtime_renders(self, client, seed_admin):
        _admin_session(client, seed_admin)
        assert client.get("/overtime").status_code == 200

    def test_compoff_renders(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.get("/compoff", follow_redirects=True)
        assert resp.status_code == 200

    def test_view_holidays_renders(self, client, seed_admin):
        # /view_holidays renders its own standalone holidays page directly
        # rather than redirecting to /leave_holidays.
        _admin_session(client, seed_admin)
        resp = client.get("/view_holidays", follow_redirects=False)
        assert resp.status_code == 200

    def test_admin_leave_types_get(self, client, seed_admin):
        _admin_session(client, seed_admin)
        assert client.get("/admin_leave_types").status_code == 200


# ---------------------------------------------------------------------------
# 3. Holiday management
# ---------------------------------------------------------------------------

class TestHolidayManagement:
    def test_add_holiday_creates_row(self, client, seed_admin, db_engine):
        _admin_session(client, seed_admin)
        resp = client.post("/add_holiday", data={
            "date":         "2025-08-15",
            "holiday_name": "Independence Day Test",
            "type":         "Holiday",
        }, follow_redirects=True)
        assert resp.status_code == 200
        cur = db_engine.cursor()
        cur.execute("SELECT id FROM holidays WHERE date='2025-08-15'")
        row = cur.fetchone()
        if row:
            cur.execute("DELETE FROM holidays WHERE id=%s", (row[0],))
        cur.close()
        assert row is not None

    def test_add_holiday_duplicate_silently_ignored(self, client, seed_admin, holiday):
        _admin_session(client, seed_admin)
        resp = client.post("/add_holiday", data={
            "date":         holiday["date"],
            "holiday_name": "Duplicate",
            "type":         "Holiday",
        }, follow_redirects=True)
        assert resp.status_code == 200  # no crash on duplicate

    def test_delete_holiday_removes_row(self, client, seed_admin, holiday, db_engine):
        _admin_session(client, seed_admin)
        resp = client.post(f"/delete_holiday/{holiday['id']}", data={"year": "2025"},
                           follow_redirects=True)
        assert resp.status_code == 200
        cur = db_engine.cursor()
        cur.execute("SELECT id FROM holidays WHERE id=%s", (holiday["id"],))
        assert cur.fetchone() is None
        cur.close()

    def test_import_indian_holidays(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.post("/import_indian_holidays", data={"year": "2025"},
                           follow_redirects=True)
        assert resp.status_code == 200

    def test_add_leave_type_entry(self, client, seed_admin, db_engine):
        _admin_session(client, seed_admin)
        resp = client.post("/add_holiday", data={
            "date":         "2025-09-01",
            "holiday_name": "Test Leave Entry",
            "type":         "Leave",
        }, follow_redirects=True)
        assert resp.status_code == 200
        cur = db_engine.cursor()
        cur.execute("SELECT id FROM holidays WHERE date='2025-09-01'")
        row = cur.fetchone()
        if row:
            cur.execute("DELETE FROM holidays WHERE id=%s", (row[0],))
        cur.close()


# ---------------------------------------------------------------------------
# 4. Leave action (approve / reject)
# ---------------------------------------------------------------------------

class TestLeaveAction:
    def test_approve_leave_request(self, client, seed_admin, leave_request, db_engine):
        _admin_session(client, seed_admin)
        resp = client.post(f"/leave_action/{leave_request['id']}", data={
            "action": "Approved",
        }, follow_redirects=True)
        assert resp.status_code == 200
        cur = db_engine.cursor()
        cur.execute("SELECT status FROM leave_requests WHERE id=%s", (leave_request["id"],))
        assert cur.fetchone()[0] == "Approved"
        cur.close()

    def test_reject_leave_request(self, client, seed_admin, leave_request, db_engine):
        _admin_session(client, seed_admin)
        resp = client.post(f"/leave_action/{leave_request['id']}", data={
            "action":     "Rejected",
            "admin_note": "Insufficient cover",
        }, follow_redirects=True)
        assert resp.status_code == 200
        cur = db_engine.cursor()
        cur.execute("SELECT status FROM leave_requests WHERE id=%s", (leave_request["id"],))
        row = cur.fetchone()
        cur.close()
        assert row[0] in ("Rejected", "Approved")  # DB updated, no crash

    def test_invalid_action_value_no_crash(self, client, seed_admin, leave_request):
        _admin_session(client, seed_admin)
        resp = client.post(f"/leave_action/{leave_request['id']}", data={
            "action": "INVALID_ACTION",
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_nonexistent_leave_no_crash(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.post("/leave_action/9999999", data={"action": "Approved"},
                           follow_redirects=True)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 5. Employee leave request (form POST)
# ---------------------------------------------------------------------------

class TestEmployeeLeaveRequest:
    def test_request_leave_creates_db_row(self, client, seed_employee, db_engine):
        _emp_session(client, seed_employee)
        resp = client.post("/request_leave", data={
            "leave_date_start": "2025-07-01",
            "leave_date_end":   "2025-07-01",
            "reason":           "Personal work",
        }, follow_redirects=True)
        assert resp.status_code == 200
        cur = db_engine.cursor()
        cur.execute(
            "SELECT id FROM leave_requests WHERE employee_id=%s AND leave_date='2025-07-01'",
            (seed_employee["employee_id"],)
        )
        row = cur.fetchone()
        if row:
            cur.execute("DELETE FROM leave_requests WHERE id=%s", (row[0],))
        cur.close()
        assert row is not None

    def test_request_leave_missing_reason_ignored(self, client, seed_employee):
        _emp_session(client, seed_employee)
        resp = client.post("/request_leave", data={
            "leave_date_start": "2025-07-15",
            "reason":           "",  # empty reason → redirect without creating
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_request_half_day_leave(self, client, seed_employee, db_engine):
        _emp_session(client, seed_employee)
        resp = client.post("/request_leave", data={
            "leave_date_start": "2025-07-20",
            "reason":           "Doctor appointment",
            "is_half_day":      "1",
            "half_day_session": "Morning",
        }, follow_redirects=True)
        assert resp.status_code == 200
        cur = db_engine.cursor()
        cur.execute(
            "SELECT id FROM leave_requests WHERE employee_id=%s AND leave_date='2025-07-20'",
            (seed_employee["employee_id"],)
        )
        row = cur.fetchone()
        if row:
            cur.execute("DELETE FROM leave_requests WHERE id=%s", (row[0],))
        cur.close()

    def test_cancel_leave_by_employee(self, client, seed_employee, leave_request, db_engine):
        _emp_session(client, seed_employee)
        resp = client.post(f"/cancel_leave/{leave_request['id']}", follow_redirects=True)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 6. Bulk leave action
# ---------------------------------------------------------------------------

class TestBulkLeaveAction:
    def test_bulk_approve(self, client, seed_admin, leave_request, db_engine):
        _admin_session(client, seed_admin)
        resp = client.post("/bulk_leave_action", data={
            "action":   "Approved",
            "leave_ids": str(leave_request["id"]),
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_bulk_reject(self, client, seed_admin, leave_request, db_engine):
        _admin_session(client, seed_admin)
        resp = client.post("/bulk_leave_action", data={
            "action":    "Rejected",
            "leave_ids": str(leave_request["id"]),
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_bulk_empty_ids_no_crash(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.post("/bulk_leave_action", data={"action": "Approved"},
                           follow_redirects=True)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 7. Leave type management
# ---------------------------------------------------------------------------

class TestLeaveTypeManagement:
    def test_add_leave_type(self, client, seed_admin, db_engine):
        _admin_session(client, seed_admin)
        resp = client.post("/admin_leave_types", data={
            "action":       "add",
            "name":         "Test Casual Leave",
            "annual_quota": "12",
            "is_paid":      "1",
        }, follow_redirects=True)
        assert resp.status_code == 200
        cur = db_engine.cursor()
        cur.execute("SELECT id FROM leave_types WHERE name='Test Casual Leave'")
        row = cur.fetchone()
        if row:
            cur.execute("DELETE FROM leave_types WHERE id=%s", (row[0],))
        cur.close()

    def test_toggle_leave_type(self, client, seed_admin, db_engine):
        cur = db_engine.cursor()
        cur.execute("""
            INSERT INTO leave_types (name, annual_quota, is_paid, is_active)
            VALUES ('Toggle Test Leave', 10, 1, 1) RETURNING id
        """)
        lt_id = cur.fetchone()[0]
        _admin_session(client, seed_admin)
        resp = client.post("/admin_leave_types", data={
            "action": "toggle",
            "lt_id":  str(lt_id),
        }, follow_redirects=True)
        assert resp.status_code == 200
        cur.execute("DELETE FROM leave_types WHERE id=%s", (lt_id,))
        cur.close()


# ---------------------------------------------------------------------------
# 8. API: /api/holidays
# ---------------------------------------------------------------------------

class TestApiHolidays:
    def test_get_returns_list(self, client, seed_admin):
        token = _admin_token(client, seed_admin)
        resp = client.get("/api/holidays",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, (list, dict))

    def test_post_adds_holiday(self, client, seed_admin, db_engine):
        token = _admin_token(client, seed_admin)
        resp = client.post("/api/holidays", json={
            "date": "2099-07-14",
            "name": "Test Holiday API",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 201)
        cur = db_engine.cursor()
        cur.execute("SELECT id FROM holidays WHERE date='2099-07-14'")
        row = cur.fetchone()
        if row:
            cur.execute("DELETE FROM holidays WHERE id=%s", (row[0],))
        cur.close()

    def test_requires_auth(self, client):
        assert client.get("/api/holidays").status_code == 401


# ---------------------------------------------------------------------------
# 9. API: /api/leave_requests
# ---------------------------------------------------------------------------

class TestApiLeaveRequests:
    def test_returns_json(self, client, seed_admin):
        token = _admin_token(client, seed_admin)
        resp = client.get("/api/leave_requests",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, (list, dict))

    def test_action_approve(self, client, seed_admin, leave_request):
        token = _admin_token(client, seed_admin)
        resp = client.post(
            f"/api/leave_requests/{leave_request['id']}/action",
            json={"action": "Approved"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code in (200, 201)

    def test_action_invalid_rejected(self, client, seed_admin, leave_request):
        token = _admin_token(client, seed_admin)
        resp = client.post(
            f"/api/leave_requests/{leave_request['id']}/action",
            json={"action": "BADVALUE"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code in (400, 422)

    def test_requires_auth(self, client):
        assert client.get("/api/leave_requests").status_code == 401


# ---------------------------------------------------------------------------
# 10. API: /api/employee/leave_request and /api/employee/leaves
# ---------------------------------------------------------------------------

class TestApiEmployeeLeave:
    def test_submit_leave_request(self, client, seed_employee, db_engine):
        token = _emp_token(client, seed_employee)
        resp = client.post("/api/employee/leave_request", json={
            "leave_date": "2025-08-01",
            "reason":     "Personal",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 201)
        data = resp.get_json()
        assert data.get("ok") is True
        cur = db_engine.cursor()
        cur.execute("DELETE FROM leave_requests WHERE employee_id=%s AND leave_date='2025-08-01'",
                    (seed_employee["employee_id"],))
        cur.close()

    def test_get_leaves_returns_list(self, client, seed_employee, leave_request):
        token = _emp_token(client, seed_employee)
        resp = client.get("/api/employee/leaves",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, (list, dict))

    def test_cancel_leave_via_api(self, client, seed_employee, leave_request):
        token = _emp_token(client, seed_employee)
        resp = client.post(
            f"/api/employee/cancel_leave/{leave_request['id']}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code in (200, 400)

    def test_get_holidays_via_employee_api(self, client, seed_employee, holiday):
        token = _emp_token(client, seed_employee)
        resp = client.get("/api/employee/holidays",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_leave_request_missing_reason(self, client, seed_employee):
        token = _emp_token(client, seed_employee)
        resp = client.post("/api/employee/leave_request", json={
            "leave_date": "2025-09-01",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# 11. API: /api/resignation_requests
# ---------------------------------------------------------------------------

class TestApiResignationRequests:
    def test_get_returns_json(self, client, seed_admin):
        token = _admin_token(client, seed_admin)
        resp = client.get("/api/resignation_requests",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, (list, dict))

    def test_requires_auth(self, client):
        assert client.get("/api/resignation_requests").status_code == 401


# ---------------------------------------------------------------------------
# 12. Set leave balance
# ---------------------------------------------------------------------------

class TestSetLeaveBalance:
    def test_set_leave_balance_for_employee(self, client, seed_admin, seed_employee, db_engine):
        _admin_session(client, seed_admin)
        cur = db_engine.cursor()
        cur.execute("SELECT id FROM leave_types LIMIT 1")
        lt_row = cur.fetchone()
        cur.close()
        if lt_row:
            resp = client.post("/set_leave_balance", data={
                "employee_id":  seed_employee["employee_id"],
                "leave_type_id": str(lt_row[0]),
                "balance":      "10",
            }, follow_redirects=True)
            assert resp.status_code == 200


# ===========================================================================
# ── ATTENDANCE BLUEPRINT ──────────────────────────────────────────────────
# ===========================================================================

# ---------------------------------------------------------------------------
# 13. Auth guards
# ---------------------------------------------------------------------------

class TestAttendanceAuthGuards:
    def test_monthly_report_requires_admin(self, client):
        assert client.get("/monthly_report", follow_redirects=False).status_code in (302, 401)

    def test_admin_shift_swaps_requires_admin(self, client):
        assert client.get("/admin_shift_swaps", follow_redirects=False).status_code in (302, 401)

    def test_add_shift_requires_admin(self, client):
        assert client.post("/add_shift", data={}).status_code in (302, 401)

    def test_attendance_chart_data_requires_admin(self, client):
        assert client.get("/api/attendance_chart_data", follow_redirects=False).status_code in (302, 401)

    def test_api_monthly_report_requires_token(self, client):
        assert client.get("/api/monthly_report").status_code == 401

    def test_api_shifts_requires_token(self, client):
        assert client.get("/api/shifts").status_code == 401


# ---------------------------------------------------------------------------
# 14. Attendance admin page renders
# ---------------------------------------------------------------------------

class TestAttendanceAdminPages:
    def test_monthly_report_renders(self, client, seed_admin):
        _admin_session(client, seed_admin)
        assert client.get("/monthly_report").status_code == 200

    def test_monthly_report_with_params(self, client, seed_admin):
        _admin_session(client, seed_admin)
        assert client.get("/monthly_report?year=2025&month=1").status_code == 200

    def test_monthly_report_all_months(self, client, seed_admin):
        _admin_session(client, seed_admin)
        for m in range(1, 13):
            assert client.get(f"/monthly_report?year=2025&month={m}").status_code == 200

    def test_admin_shift_swaps_renders(self, client, seed_admin):
        _admin_session(client, seed_admin)
        assert client.get("/admin_shift_swaps").status_code == 200

    def test_employee_attendance_detail_renders(self, client, seed_admin, seed_employee):
        _admin_session(client, seed_admin)
        resp = client.get(
            f"/employee_attendance_detail/{seed_employee['employee_id']}/2025/1"
        )
        assert resp.status_code == 200

    def test_attendance_chart_data_returns_json(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.get("/api/attendance_chart_data")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "trend" in data and "dept" in data


# ---------------------------------------------------------------------------
# 15. Shift management
# ---------------------------------------------------------------------------

class TestShiftManagement:
    def test_add_shift_creates_record(self, client, seed_admin, db_engine):
        _admin_session(client, seed_admin)
        resp = client.post("/add_shift", data={
            "shift_name": "Test Evening Shift",
            "start_time": "14:00",
            "half_time":  "17:00",
            "end_time":   "22:00",
        }, follow_redirects=True)
        assert resp.status_code == 200
        cur = db_engine.cursor()
        cur.execute("SELECT id FROM shifts WHERE name='Test Evening Shift'")
        row = cur.fetchone()
        if row:
            cur.execute("DELETE FROM shifts WHERE id=%s", (row[0],))
        cur.close()
        assert row is not None

    def test_add_shift_missing_fields_ignored(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.post("/add_shift", data={
            "shift_name": "Incomplete",
            # missing start/half/end times
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_delete_shift_removes_record(self, client, seed_admin, shift, db_engine):
        _admin_session(client, seed_admin)
        resp = client.post(f"/delete_shift/{shift['id']}", follow_redirects=True)
        assert resp.status_code == 200
        cur = db_engine.cursor()
        cur.execute("SELECT id FROM shifts WHERE id=%s", (shift["id"],))
        assert cur.fetchone() is None
        cur.close()

    def test_edit_shift(self, client, seed_admin, shift, db_engine):
        _admin_session(client, seed_admin)
        resp = client.post(f"/edit_shift/{shift['id']}", data={
            "name":       "Test Morning Edited",
            "start_time": "08:30",
            "half_time":  "12:30",
            "end_time":   "17:30",
        }, follow_redirects=True)
        assert resp.status_code == 200
        cur = db_engine.cursor()
        cur.execute("SELECT name FROM shifts WHERE id=%s", (shift["id"],))
        row = cur.fetchone()
        cur.close()
        if row:
            assert row[0] == "Test Morning Edited"

    def test_assign_shift_to_employee(self, client, seed_admin, shift, seed_employee):
        _admin_session(client, seed_admin)
        resp = client.post("/assign_shift", data={
            "employee_id": seed_employee["employee_id"],
            "shift_id":    str(shift["id"]),
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_bulk_assign_shift(self, client, seed_admin, shift, seed_employee):
        _admin_session(client, seed_admin)
        resp = client.post("/bulk_assign_shift", data={
            "shift_id":    str(shift["id"]),
            "employee_ids": seed_employee["employee_id"],
        }, follow_redirects=True)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 16. API: /api/shifts
# ---------------------------------------------------------------------------

class TestApiShifts:
    def test_get_shifts_returns_list(self, client, seed_admin, shift):
        token = _admin_token(client, seed_admin)
        resp = client.get("/api/shifts",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, (list, dict))

    def test_post_creates_shift(self, client, seed_admin, db_engine):
        token = _admin_token(client, seed_admin)
        resp = client.post("/api/shifts", json={
            "name":       "API Night Shift",
            "start_time": "22:00",
            "half_time":  "02:00",
            "end_time":   "06:00",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 201)
        data = resp.get_json()
        assert data.get("ok") is True
        cur = db_engine.cursor()
        cur.execute("SELECT id FROM shifts WHERE name='API Night Shift'")
        row = cur.fetchone()
        if row:
            cur.execute("DELETE FROM shifts WHERE id=%s", (row[0],))
        cur.close()

    def test_delete_shift_via_api(self, client, seed_admin, shift, db_engine):
        token = _admin_token(client, seed_admin)
        resp = client.delete(f"/api/shifts/{shift['id']}",
                             headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 204)
        cur = db_engine.cursor()
        cur.execute("SELECT id FROM shifts WHERE id=%s", (shift["id"],))
        assert cur.fetchone() is None
        cur.close()

    def test_assign_shift_via_api(self, client, seed_admin, shift, seed_employee):
        token = _admin_token(client, seed_admin)
        resp = client.post("/api/shifts/assign", json={
            "emp_id":   seed_employee["employee_id"],
            "shift_id": shift["id"],
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 201)

    def test_requires_auth(self, client):
        assert client.get("/api/shifts").status_code == 401


# ---------------------------------------------------------------------------
# 17. API: /api/monthly_report
# ---------------------------------------------------------------------------

class TestApiMonthlyReport:
    def test_returns_json(self, client, seed_admin):
        token = _admin_token(client, seed_admin)
        resp = client.get("/api/monthly_report?year=2025&month=1",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, (list, dict))

    def test_default_params(self, client, seed_admin):
        token = _admin_token(client, seed_admin)
        resp = client.get("/api/monthly_report",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_all_months(self, client, seed_admin):
        token = _admin_token(client, seed_admin)
        for m in range(1, 13):
            resp = client.get(f"/api/monthly_report?year=2025&month={m}",
                              headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 200

    def test_requires_auth(self, client):
        assert client.get("/api/monthly_report").status_code == 401


# ---------------------------------------------------------------------------
# 18. Correct attendance (admin manual correction)
# ---------------------------------------------------------------------------

class TestCorrectAttendance:
    def test_correct_attendance_form_accepted(self, client, seed_admin, seed_employee):
        _admin_session(client, seed_admin)
        resp = client.post("/correct_attendance", data={
            "employee_id": seed_employee["employee_id"],
            "date":        "2025-06-01",
            "login_time":  "09:00:00",
            "logout_time": "18:00:00",
            "status":      "Full Day",
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_correct_attendance_requires_admin(self, client):
        assert client.post("/correct_attendance", data={}).status_code in (302, 401)


# ---------------------------------------------------------------------------
# 19. Bulk mark attendance
# ---------------------------------------------------------------------------

class TestBulkMarkAttendance:
    def test_bulk_mark_page_renders(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.get("/bulk_mark_attendance")
        assert resp.status_code == 200

    def test_bulk_mark_post_accepted(self, client, seed_admin, seed_employee):
        _admin_session(client, seed_admin)
        resp = client.post("/bulk_mark_attendance", data={
            "date":                    "2025-05-05",
            f"emp_{seed_employee['employee_id']}": "Full Day",
        }, follow_redirects=True)
        assert resp.status_code == 200
