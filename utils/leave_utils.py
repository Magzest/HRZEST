# -*- coding: utf-8 -*-
"""Pure helper functions for the leave/holiday/overtime blueprint.

Extracted from app.py rather than imported back from it -- wsgi.py registers
blueprints before `import app as _app_module`, so a blueprint importing from
app.py would trigger app.py's full module body (route registration, DB
bootstrap) out of order. Neither function here touches the DB directly
(assign_leave_balances_for_employee takes a cursor as a dependency), so
extraction is safe.
"""
import datetime
from extensions import app_log


def assign_leave_balances_for_employee(cursor, employee_id, year=None):
    """Auto-assign leave balances for all active leave types for a new/existing employee."""
    if year is None:
        year = datetime.date.today().year
    cursor.execute("SELECT id, annual_quota FROM leave_types WHERE is_active=1")
    for lt_id, quota in cursor.fetchall():
        cursor.execute("""
            INSERT INTO leave_balances (employee_id, leave_type_id, year, total_days, used_days)
            VALUES (%s, %s, %s, %s, 0)
            ON CONFLICT (employee_id, leave_type_id, year) DO UPDATE SET
                total_days = CASE WHEN leave_balances.used_days = 0
                                  THEN EXCLUDED.total_days ELSE leave_balances.total_days END
        """, (employee_id, lt_id, year, quota))


def get_indian_holidays(year):
    """Returns sorted list of (date, name) for major Indian public holidays."""
    fixed = [
        (1, 1, "New Year's Day"),
        (1, 26, "Republic Day"),
        (8, 15, "Independence Day"),
        (10, 2, "Gandhi Jayanti"),
        (12, 25, "Christmas Day"),
    ]
    variable_by_year = {
        2025: [
            (1, 14, "Makar Sankranti / Pongal"),
            (2, 26, "Maha Shivaratri"),
            (3, 14, "Holi"),
            (3, 31, "Eid ul-Fitr"),
            (4, 14, "Dr. Ambedkar Jayanti"),
            (4, 18, "Good Friday"),
            (5, 1, "Maharashtra Day / Labour Day"),
            (6, 7, "Eid ul-Adha"),
            (8, 16, "Janmashtami"),
            (10, 2, "Dussehra / Vijayadasami"),
            (10, 20, "Diwali (Lakshmi Puja)"),
            (11, 5, "Guru Nanak Jayanti"),
        ],
        2026: [
            (1, 14, "Makar Sankranti / Pongal"),
            (2, 15, "Maha Shivaratri"),
            (3, 5, "Holi"),
            (3, 20, "Eid ul-Fitr"),
            (4, 3, "Good Friday"),
            (4, 14, "Dr. Ambedkar Jayanti / Baisakhi"),
            (5, 1, "Maharashtra Day / Labour Day"),
            (5, 27, "Eid ul-Adha"),
            (8, 21, "Janmashtami"),
            (10, 21, "Dussehra / Vijayadasami"),
            (10, 30, "Diwali (Lakshmi Puja)"),
            (11, 25, "Guru Nanak Jayanti"),
        ],
        2027: [
            (1, 14, "Makar Sankranti / Pongal"),
            (3, 5, "Maha Shivaratri"),
            (3, 26, "Holi"),
            (4, 2, "Good Friday"),
            (4, 14, "Dr. Ambedkar Jayanti"),
            (5, 1, "Maharashtra Day / Labour Day"),
            (8, 15, "Independence Day"),
            (9, 4, "Janmashtami"),
            (10, 8, "Dussehra / Vijayadasami"),
            (10, 17, "Diwali (Lakshmi Puja)"),
            (11, 14, "Guru Nanak Jayanti"),
        ],
    }
    result = []
    for m, d, name in fixed:
        try:
            result.append((datetime.date(year, m, d), name))
        except ValueError as exc:
            # These are hand-typed literal (month, day) tuples above --
            # a ValueError here means a typo (e.g. day=31 in February),
            # not a runtime data problem, but still worth surfacing.
            app_log.debug("get_indian_holidays: invalid fixed-date entry %r for year %s: %s", (m, d, name), year, exc)
    for m, d, name in variable_by_year.get(year, []):
        try:
            result.append((datetime.date(year, m, d), name))
        except ValueError as exc:
            app_log.debug("get_indian_holidays: invalid variable-date entry %r for year %s: %s", (m, d, name), year, exc)
    return sorted(result, key=lambda x: x[0])
