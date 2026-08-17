# -*- coding: utf-8 -*-
"""Global runtime configuration -- shift times, deduction rates.

These are loaded from the DB at startup via load_default_shift() and
load_salary_rules(). Blueprints should always access them through
this module (``import utils.config as cfg; cfg.SHIFT_START``) so
they see the updated values after startup loading.
"""
import datetime
import os
from database import get_db_connection

# Office geo-fence (overridable via .env)
OFFICE_LAT = float(os.environ.get("OFFICE_LAT", "17.494664737165042"))
OFFICE_LON = float(os.environ.get("OFFICE_LON", "78.40496618113566"))
OFFICE_RADIUS_M = 300

# Shift timings -- updated by load_default_shift() at startup
SHIFT_START = datetime.time(9, 0)
SHIFT_HALF = datetime.time(13, 0)
SHIFT_END = datetime.time(18, 0)

# Deduction rates -- updated by load_salary_rules() at startup
LATE_DEDUCTION_RATE = 0.10
HALF_DAY_RATE = 0.50
GRACE_MINUTES = 15
HOLIDAY_PAY = "paid"    # "paid" | "unpaid"
LEAVE_PAY = "exclude"  # "exclude" | "absent"


def load_default_shift():
    global SHIFT_START, SHIFT_HALF, SHIFT_END
    try:
        db = get_db_connection()
        cur = db.cursor(buffered=True)
        cur.execute("SELECT shift_start, shift_half, shift_end FROM company_settings LIMIT 1")
        row = cur.fetchone()
        cur.close()
        db.close()
        if row and row[0]:
            def _to_time(v):
                if isinstance(v, datetime.timedelta):
                    total = int(v.total_seconds())
                    return datetime.time(total // 3600, (total % 3600) // 60)
                if isinstance(v, datetime.time):
                    return v
                return datetime.time(9, 0)
            SHIFT_START = _to_time(row[0])
            SHIFT_HALF = _to_time(row[1])
            SHIFT_END = _to_time(row[2])
    except Exception:
        pass


def load_salary_rules():
    global LATE_DEDUCTION_RATE, HALF_DAY_RATE, GRACE_MINUTES, HOLIDAY_PAY, LEAVE_PAY
    try:
        db = get_db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute(
            "SELECT COALESCE(late_deduction_pct,10), COALESCE(half_day_deduction_pct,50), "
            "       COALESCE(grace_minutes,15), COALESCE(holiday_pay,'paid'), COALESCE(leave_pay,'exclude') "
            "FROM company_settings LIMIT 1"
        )
        row = cursor.fetchone()
        cursor.close()
        db.close()
        if row:
            LATE_DEDUCTION_RATE = float(row[0]) / 100.0
            HALF_DAY_RATE = float(row[1]) / 100.0
            GRACE_MINUTES = int(row[2])
            HOLIDAY_PAY = str(row[3])
            LEAVE_PAY = str(row[4])
    except Exception:
        pass
