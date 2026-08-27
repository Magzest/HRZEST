# -*- coding: utf-8 -*-
"""Per-employee flat-rate billing for the multi-tenant SaaS.

Tiered plans (Basic/Medium/Prime) were retired in favor of a single flat
rate per employee -- every feature is available to every tenant
regardless of headcount; the only billing lever left is employee count.
att_master.tenants.plan is kept as a column (historical/audit value only,
always written as PLAN_LABEL below) rather than dropped, since altering
it out is a destructive migration with no functional upside -- nothing
reads it as a live feature/pricing switch anymore.
"""
from database import get_tenant_db

# ₹99/employee/month, flat. No minimum charge, no employee cap, no tiers.
PER_EMPLOYEE_PAISE = 9900

# Written into att_master.tenants.plan on every new tenant -- a fixed
# audit-trail label, not a lookup key into any tier table (there isn't one).
PLAN_LABEL = "per_employee"


def get_tenant_employee_count(schema_name: str) -> int:
    """Live employee count for a tenant schema -- the sole input to billing
    now. Fails to 0 on any DB error rather than raising, since this is used
    in dashboard/pricing display contexts that shouldn't 500 on a transient
    connection hiccup."""
    try:
        conn = get_tenant_db(schema_name)
        cur = conn.cursor(buffered=True)
        cur.execute("SELECT COUNT(*) FROM employees")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count
    except Exception:
        return 0


def calculate_price(employee_count: int) -> int:
    """Price in paise for `employee_count` employees -- flat rate, no
    bands, no tiers. Single source of truth for both display (create_org,
    Platform Admin dashboard) and the Razorpay order amount
    (blueprints/billing.py's create_order), so those never compute
    different numbers for the same input."""
    if employee_count < 0:
        employee_count = 0
    return employee_count * PER_EMPLOYEE_PAISE


def format_price_inr(paise: int) -> str:
    """paise -> "₹1,999" style display string (no decimal paise shown --
    every price here is a whole-rupee amount already)."""
    return f"₹{paise // 100:,}"


def get_billing_snapshot(schema_name: str) -> dict:
    """Single source of truth for a tenant's auto-debit mandate status and
    recent invoice history -- used by both the web Seats & Billing page
    (blueprints/seats.py's seats_page()) and the mobile billing-status API
    (blueprints/core.py's api_billing_status()) so the two can never drift
    on what "auto-debit status"/"billing history" means. Deliberately
    doesn't include employee_count -- get_tenant_employee_count() above is
    already that single source and callers already have it.

    Returns raw values (real datetimes, integer paise) rather than
    pre-formatted display strings -- callers format for their own
    presentation layer (Jinja's .strftime() vs JSON's .isoformat() /
    format_price_inr()). Every date/timestamp is passed through
    coerce_datetime() first: under the local-fallback SQLite path these
    columns come back as plain strings (see coerce_datetime's docstring),
    and a caller blindly calling .strftime()/.isoformat() on a str would
    crash -- coercing once here means neither caller has to know or care
    which DB backend is live. Fails soft (auto_debit=None, invoices=[]) on
    any DB error, matching get_tenant_employee_count()'s posture."""
    from database import get_master_db
    from utils.helpers import coerce_datetime

    auto_debit = None
    invoices = []
    try:
        conn = get_master_db()
        cur = conn.cursor(buffered=True)
        cur.execute(
            "SELECT status, quantity_synced, activated_at FROM auto_debit_mandates WHERE tenant_schema=%s",
            (schema_name,)
        )
        row = cur.fetchone()
        if row:
            auto_debit = {
                "status": row[0], "quantity_synced": row[1],
                "activated_at": coerce_datetime(row[2]),
            }
        cur.execute(
            "SELECT billing_period, employee_count, amount_paise, status, created_at, failure_reason "
            "FROM monthly_invoices WHERE tenant_schema=%s ORDER BY created_at DESC LIMIT 12",
            (schema_name,)
        )
        invoices = [
            {
                "billing_period": coerce_datetime(r[0]), "employee_count": r[1],
                "amount_paise": r[2], "status": r[3],
                "created_at": coerce_datetime(r[4]), "failure_reason": r[5],
            }
            for r in cur.fetchall()
        ]
        cur.close()
        conn.close()
    except Exception as exc:
        from extensions import app_log
        app_log.warning("get_billing_snapshot(%s): auto-debit/invoice lookup failed: %s", schema_name, exc)
    return {"auto_debit": auto_debit, "invoices": invoices}
