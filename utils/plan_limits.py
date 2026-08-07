"""Pricing-tier definitions and plan-limit enforcement for the multi-tenant
SaaS. Tenant plan is read from att_master.tenants.plan (see app.py's
init_master_db/blueprints/org.py's create_org).

Tier definitions are plain Python constants on purpose, not a DB table --
this stays easy to find/grep/edit as pricing is worked out, and the actual
paid orders (see utils/razorpay_utils.py, blueprints/billing.py) reference
these constants at checkout time rather than duplicating numbers in a
separate price list.

Internal keys (starter/growth/enterprise) are kept stable even though the
customer-facing names are Basic/Medium/Prime -- renaming the keys would
break every existing tenant row's `plan` column plus ~15 call sites
(plan_rank/check_feature_allowed callers, tests, secops.py's
plan_rank(...) >= plan_rank("growth") gate) for a purely cosmetic change.
"""
from database import get_master_db, get_tenant_db

PLAN_TIERS = {
    "starter": {
        "display_name": "Basic",
        # (up to this many employees at base_price_paise; beyond it, each
        # extra employee up to employee_limit costs per_employee_paise)
        "employee_band": 30,
        "employee_limit": 60,
        "base_price_paise": 199900,       # ₹1,999/mo
        "per_employee_paise": 4000,       # ₹40/mo per employee beyond employee_band
        "features": frozenset({"qr", "pin", "face"}),
        "description": "Everything a small team needs to go digital — QR and face check-in "
                        "with PIN login, for up to 60 employees.",
    },
    "growth": {
        "display_name": "Medium",
        "employee_band": 70,
        "employee_limit": 150,
        "base_price_paise": 599900,       # ₹5,999/mo
        "per_employee_paise": 3500,       # ₹35/mo per employee beyond employee_band
        "features": frozenset({
            "qr", "pin", "face", "fingerprint", "geo", "totp_mfa",
            "attendance_lockout", "soc_dashboard", "daily_reports",
        }),
        "description": "Automated attendance controls, fingerprint check-in, geofencing, and "
                        "a SecOps dashboard for growing teams up to 150 employees.",
    },
    "enterprise": {
        "display_name": "Prime",
        "employee_band": None,            # unlimited, flat price -- no metering
        "employee_limit": None,
        "base_price_paise": 1499900,      # ₹14,999/mo flat
        "per_employee_paise": 0,
        "features": frozenset({
            "qr", "pin", "face", "fingerprint", "geo", "biometric", "totp_mfa",
            "attendance_lockout", "soc_dashboard", "soc_dashboard_dedicated",
            "daily_reports", "mobile_app", "email_mfa",
        }),
        "description": "Unlimited employees, advanced biometrics, a dedicated SecOps "
                        "dashboard, and mobile app access — built for large organisations.",
    },
}

# Friendly labels for PLAN_TIERS[...]["features"] entries -- shared by the
# Platform Admin plan-details panel (templates/super_admin_dashboard.html)
# and the public pricing page (templates/pricing.html) so the two never
# drift out of sync with different wording for the same feature key.
FEATURE_LABELS = {
    "qr": "QR Attendance",
    "pin": "PIN Login",
    "face": "Face Attendance",
    "fingerprint": "Fingerprint Attendance",
    "geo": "Geofencing",
    "biometric": "Advanced Biometrics",
    "totp_mfa": "Authenticator App MFA",
    "attendance_lockout": "Auto-lock After Failed Check-ins",
    "soc_dashboard": "SecOps Dashboard",
    "soc_dashboard_dedicated": "Dedicated SecOps Dashboard",
    "daily_reports": "Daily Email Reports",
    "mobile_app": "Mobile App Access",
    "email_mfa": "Email MFA Codes",
}

_DEFAULT_PLAN = "starter"

# Ordered low-to-high, for "requires at least tier X" checks (e.g. SecOps
# gating, the nightly digest email) -- distinct from check_feature_allowed's
# per-feature membership checks below, which don't have a linear ordering.
PLAN_ORDER = ["starter", "growth", "enterprise"]


def plan_rank(plan_name: str) -> int:
    """Numeric rank for minimum-tier comparisons. Unknown plan names rank
    lowest (0) rather than raising, matching this module's fail-restrictive
    posture elsewhere."""
    try:
        return PLAN_ORDER.index(plan_name)
    except ValueError:
        return 0


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


def set_tenant_plan(schema_name: str, new_plan: str):
    """Self-service plan change (no payment gateway yet -- see module
    docstring), a straight write with no billing side effect. Callers must
    validate new_plan against PLAN_TIERS.keys() themselves before calling."""
    conn = get_master_db()
    cur = conn.cursor()
    cur.execute("UPDATE tenants SET plan=%s WHERE db_name=%s", (new_plan, schema_name))
    conn.commit()
    cur.close()
    conn.close()


def check_feature_allowed(schema_name: str, feature_key: str):
    """feature_key is one of: qr, pin, face, fingerprint, geo, biometric,
    totp_mfa, attendance_lockout, soc_dashboard, soc_dashboard_dedicated,
    daily_reports, mobile_app, email_mfa."""
    plan = get_tenant_plan(schema_name)
    if feature_key in PLAN_TIERS[plan]["features"]:
        return True, ""
    return False, (
        f"This feature isn't included in your {PLAN_TIERS[plan]['display_name']} plan. "
        "Upgrade your plan to enable it."
    )


def calculate_plan_price(plan_name: str, employee_count: int) -> int:
    """Price in paise for `plan_name` at `employee_count` employees --
    single source of truth for both display (pricing.html, the Platform
    Admin plan-details panel) and the Razorpay order amount
    (blueprints/billing.py's create_order), so those never compute
    different numbers for the same inputs.

    Below/at employee_band: flat base_price_paise. Above it (and up to
    employee_limit): base_price_paise + per_employee_paise for each
    employee past the band. Prime has no band (employee_band is None) so
    it's always the flat base price regardless of employee_count.

    Raises ValueError if plan_name is unknown or employee_count exceeds
    the plan's employee_limit -- callers (billing.py's create_order) must
    catch this and surface it as a 400, never silently clamp a paid
    order's employee count.
    """
    if plan_name not in PLAN_TIERS:
        raise ValueError(f"Unknown plan '{plan_name}'")
    tier = PLAN_TIERS[plan_name]
    limit = tier["employee_limit"]
    if limit is not None and employee_count > limit:
        raise ValueError(
            f"{tier['display_name']} plan supports up to {limit} employees "
            f"(requested {employee_count})."
        )
    band = tier["employee_band"]
    if band is None or employee_count <= band:
        return tier["base_price_paise"]
    return tier["base_price_paise"] + tier["per_employee_paise"] * (employee_count - band)


def format_price_inr(paise: int) -> str:
    """paise -> "₹1,999" style display string (no decimal paise shown --
    every price in PLAN_TIERS is a whole-rupee amount already)."""
    return f"₹{paise // 100:,}"
