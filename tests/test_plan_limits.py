"""Tests for utils/plan_limits.py -- pricing-tier definitions and
employee-count/feature-toggle enforcement for the multi-tenant SaaS.

Uses the ambient test tenant schema (DB_NAME env var, same schema
conftest.py's init_db() already sets up) for employee-count checks.
conftest.py's session-scoped _init_test_db already registers this schema
as a permanent (unique db_name) att_master.tenants row on plan='enterprise'
-- these tests temporarily UPDATE that row's plan rather than inserting a
second row (db_name is UNIQUE), restoring 'enterprise' afterward so the
rest of the suite stays unaffected.
"""
import os
import pytest
import utils.plan_limits as plan_limits


_TEST_SCHEMA = os.environ.get("DB_NAME", "employee_attendance")


@pytest.fixture
def tenant_row(db_engine):
    """Yields a setter that changes the test schema's registered plan for
    the duration of one test, restoring 'enterprise' afterward."""
    def _set(plan):
        cur = db_engine.cursor()
        cur.execute("UPDATE att_master.tenants SET plan=%s WHERE db_name=%s", (plan, _TEST_SCHEMA))
        cur.close()

    yield _set
    cur = db_engine.cursor()
    cur.execute("UPDATE att_master.tenants SET plan='enterprise' WHERE db_name=%s", (_TEST_SCHEMA,))
    cur.close()


class TestPlanTiers:
    def test_three_tiers_defined(self):
        assert set(plan_limits.PLAN_TIERS.keys()) == {"starter", "growth", "enterprise"}

    def test_tiers_are_strictly_additive(self):
        starter = plan_limits.PLAN_TIERS["starter"]["features"]
        growth = plan_limits.PLAN_TIERS["growth"]["features"]
        enterprise = plan_limits.PLAN_TIERS["enterprise"]["features"]
        assert starter <= growth <= enterprise

    def test_enterprise_has_unlimited_employees(self):
        assert plan_limits.PLAN_TIERS["enterprise"]["employee_limit"] is None

    def test_starter_and_growth_have_finite_limits(self):
        assert isinstance(plan_limits.PLAN_TIERS["starter"]["employee_limit"], int)
        assert isinstance(plan_limits.PLAN_TIERS["growth"]["employee_limit"], int)


class TestCalculatePlanPrice:
    def test_at_or_below_band_is_flat_base_price(self):
        assert plan_limits.calculate_plan_price("starter", 1) == 199900
        assert plan_limits.calculate_plan_price("starter", 30) == 199900

    def test_one_over_band_adds_one_increment(self):
        assert plan_limits.calculate_plan_price("starter", 31) == 199900 + 4000

    def test_at_employee_limit_is_max_metered_price(self):
        # 60 - 30 = 30 employees billed above the band
        assert plan_limits.calculate_plan_price("starter", 60) == 199900 + 4000 * 30

    def test_growth_band_and_limit(self):
        assert plan_limits.calculate_plan_price("growth", 70) == 599900
        assert plan_limits.calculate_plan_price("growth", 71) == 599900 + 3500
        assert plan_limits.calculate_plan_price("growth", 150) == 599900 + 3500 * 80

    def test_enterprise_is_flat_regardless_of_count(self):
        assert plan_limits.calculate_plan_price("enterprise", 1) == 1499900
        assert plan_limits.calculate_plan_price("enterprise", 10000) == 1499900

    def test_over_employee_limit_raises(self):
        with pytest.raises(ValueError):
            plan_limits.calculate_plan_price("starter", 61)
        with pytest.raises(ValueError):
            plan_limits.calculate_plan_price("growth", 151)

    def test_unknown_plan_raises(self):
        with pytest.raises(ValueError):
            plan_limits.calculate_plan_price("not-a-real-plan", 10)


class TestGetTenantPlan:
    def test_unknown_schema_defaults_to_starter(self):
        assert plan_limits.get_tenant_plan("att_no_such_schema_xyz") == "starter"

    def test_reads_real_plan(self, tenant_row):
        tenant_row("growth")
        assert plan_limits.get_tenant_plan(_TEST_SCHEMA) == "growth"

    def test_unrecognized_plan_value_falls_back_to_starter(self, tenant_row):
        tenant_row("some-retired-plan-name")
        assert plan_limits.get_tenant_plan(_TEST_SCHEMA) == "starter"


class TestCheckEmployeeLimit:
    def test_enterprise_never_blocked(self, tenant_row):
        tenant_row("enterprise")
        allowed, msg = plan_limits.check_employee_limit(_TEST_SCHEMA)
        assert allowed is True
        assert msg == ""

    def test_starter_blocked_once_at_limit(self, tenant_row, db_engine, monkeypatch):
        tenant_row("starter")
        # Force a tiny limit so this test doesn't need to actually insert
        # 25 employees to exercise the "at limit" branch.
        monkeypatch.setitem(plan_limits.PLAN_TIERS["starter"], "employee_limit", 0)
        allowed, msg = plan_limits.check_employee_limit(_TEST_SCHEMA)
        assert allowed is False
        assert "Basic" in msg
        assert "Upgrade" in msg

    def test_unregistered_schema_uses_starter_plan(self):
        # No tenants row at all -- get_tenant_plan() must still fail toward
        # the restrictive default (starter), never an unlimited plan.
        assert plan_limits.get_tenant_plan("att_totally_unregistered") == "starter"


class TestCheckFeatureAllowed:
    def test_starter_allows_qr_pin_and_face(self, tenant_row):
        tenant_row("starter")
        assert plan_limits.check_feature_allowed(_TEST_SCHEMA, "qr")[0] is True
        assert plan_limits.check_feature_allowed(_TEST_SCHEMA, "pin")[0] is True
        assert plan_limits.check_feature_allowed(_TEST_SCHEMA, "face")[0] is True

    def test_starter_blocks_fingerprint_and_mfa(self, tenant_row):
        tenant_row("starter")
        allowed, msg = plan_limits.check_feature_allowed(_TEST_SCHEMA, "fingerprint")
        assert allowed is False
        assert "Basic" in msg
        assert plan_limits.check_feature_allowed(_TEST_SCHEMA, "totp_mfa")[0] is False

    def test_growth_allows_face_fingerprint_geo_but_not_biometric(self, tenant_row):
        tenant_row("growth")
        assert plan_limits.check_feature_allowed(_TEST_SCHEMA, "face")[0] is True
        assert plan_limits.check_feature_allowed(_TEST_SCHEMA, "fingerprint")[0] is True
        assert plan_limits.check_feature_allowed(_TEST_SCHEMA, "geo")[0] is True
        assert plan_limits.check_feature_allowed(_TEST_SCHEMA, "attendance_lockout")[0] is True
        assert plan_limits.check_feature_allowed(_TEST_SCHEMA, "biometric")[0] is False
        assert plan_limits.check_feature_allowed(_TEST_SCHEMA, "mobile_app")[0] is False

    def test_enterprise_allows_everything(self, tenant_row):
        tenant_row("enterprise")
        for key in ("qr", "pin", "face", "fingerprint", "geo", "biometric",
                    "totp_mfa", "attendance_lockout", "soc_dashboard",
                    "soc_dashboard_dedicated", "daily_reports", "mobile_app", "email_mfa"):
            assert plan_limits.check_feature_allowed(_TEST_SCHEMA, key)[0] is True
