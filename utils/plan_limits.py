"""Pricing-tier definitions and plan-limit enforcement for the multi-tenant
SaaS. Tenant plan is read from att_master.tenants.plan (see app.py's
init_master_db/blueprints/org.py's create_org).

Tier definitions are plain Python constants on purpose, not a DB table --
there's no payment gateway yet to keep in sync with a DB-editable price
list, and this stays easy to find/grep/edit as pricing is worked out.
"""
from database import get_master_db, get_tenant_db

PLAN_TIERS = {
    "starter": {
        "display_name": "Starter",
        "price_placeholder": "Contact us",
        "employee_limit": 25,
        "features": frozenset({"qr", "pin"}),
    },
    "growth": {
        "display_name": "Growth",
        "price_placeholder": "Contact us",
        "employee_limit": 150,
        "features": frozenset({"qr", "pin", "face", "fingerprint", "geo"}),
    },
    "enterprise": {
        "display_name": "Enterprise",
        "price_placeholder": "Contact us",
        "employee_limit": None,  # unlimited
        "features": frozenset({"qr", "pin", "face", "fingerprint", "geo", "biometric"}),
    },
}

_DEFAULT_PLAN = "starter"


def get_tenant_plan(schema_name: str) -> str:
    """Look up a tenant's plan from the registry. Fails to the most
    restrictive tier on any error, and on an unrecognized/stale plan value
    -- this is a billing control, so a DB hiccup or a since-retired plan
    name should never silently grant unlimited employees/features. Not
    cached on purpose: a downgrade or suspension must affect the very next
    write attempt, not wait for some TTL to expire."""
    try:
        conn = get_master_db()
        cur = conn.cursor(buffered=True)
        cur.execute("SELECT plan FROM tenants WHERE db_name=%s", (schema_name,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row[0] in PLAN_TIERS:
            return row[0]
    except Exception:
        pass
    return _DEFAULT_PLAN


def check_employee_limit(schema_name: str):
    """Returns (allowed: bool, message: str) -- message is "" when allowed.
    Counts every employee in the tenant schema with no company_id filter:
    billing is per tenant/subdomain, not per intra-tenant sub-company (the
    `companies` table's HR-agency-style multi-company-per-schema feature is
    an orthogonal, display-scoping concern -- see admin_views.py's
    active_cid-conditional counts, which are NOT what this checks)."""
    plan = get_tenant_plan(schema_name)
    limit = PLAN_TIERS[plan]["employee_limit"]
    if limit is None:
        return True, ""
    try:
        conn = get_tenant_db(schema_name)
        cur = conn.cursor(buffered=True)
        cur.execute("SELECT COUNT(*) FROM employees")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
    except Exception:
        # Can't verify -- fail restrictive rather than silently allow past a
        # billing limit on a transient DB error.
        return False, "Could not verify your plan's employee limit. Please try again."
    if count >= limit:
        return False, (
            f"Your {PLAN_TIERS[plan]['display_name']} plan is limited to {limit} employees. "
            "Upgrade your plan to add more."
        )
    return True, ""


def check_feature_allowed(schema_name: str, feature_key: str):
    """feature_key is one of: qr, pin, face, fingerprint, geo, biometric."""
    plan = get_tenant_plan(schema_name)
    if feature_key in PLAN_TIERS[plan]["features"]:
        return True, ""
    return False, (
        f"This feature isn't included in your {PLAN_TIERS[plan]['display_name']} plan. "
        "Upgrade your plan to enable it."
    )
