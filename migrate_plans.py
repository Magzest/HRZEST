#!/usr/bin/env python3
"""
migrate_plans.py — One-time migration to add plan support.

Run once:
    ./venv/bin/python migrate_plans.py

Safe to re-run (uses IF NOT EXISTS / ALTER TABLE ... IF NOT EXISTS).
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from database import get_db_connection

def run():
    db = get_db_connection()
    cursor = db.cursor()

    # 1. Add 'plan' column to admin_users if missing
    cursor.execute("""
        ALTER TABLE admin_users
        ADD COLUMN IF NOT EXISTS plan VARCHAR(20) DEFAULT 'basic' NOT NULL
    """)
    print("✅ admin_users.plan column added (or already exists)")

    # 2. Create company_plan reference table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS company_plans (
            plan_name        VARCHAR(20)  PRIMARY KEY,
            label            VARCHAR(50)  NOT NULL,
            max_employees    INT          DEFAULT NULL,
            features         TEXT         NOT NULL,
            created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✅ company_plans table created (or already exists)")

    # 3. Seed plan definitions
    plans = [
        ("basic",   "Basic",   60,   "face_login,qr_login,attendance,leave,payroll,portal,dashboard"),
        ("medium",  "Medium",  150,  "face_login,qr_login,fingerprint,dashboard_qr,daily_email,secops,attendance,leave,payroll,portal,dashboard"),
        ("premium", "Premium", None, "face_login,qr_login,fingerprint,dashboard_qr,daily_email,mfa,secops,auth_qr_email,mobile,attendance,leave,payroll,portal,dashboard"),
    ]
    for plan_name, label, max_emp, features in plans:
        cursor.execute("""
            INSERT INTO company_plans (plan_name, label, max_employees, features)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (plan_name) DO UPDATE
              SET label=EXCLUDED.label,
                  max_employees=EXCLUDED.max_employees,
                  features=EXCLUDED.features
        """, (plan_name, label, max_emp, features))
    print("✅ company_plans seeded with basic / medium / premium")

    db.commit()
    cursor.close()
    db.close()
    print("\n🎉 Migration complete!")

if __name__ == "__main__":
    run()
