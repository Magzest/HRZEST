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
