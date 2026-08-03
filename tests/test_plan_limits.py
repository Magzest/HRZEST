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
        assert "Starter" in msg
        assert "Upgrade" in msg

    def test_unregistered_schema_uses_starter_plan(self):
        # No tenants row at all -- get_tenant_plan() must still fail toward
        # the restrictive default (starter), never an unlimited plan.
        assert plan_limits.get_tenant_plan("att_totally_unregistered") == "starter"


class TestCheckFeatureAllowed:
    def test_starter_allows_qr_and_pin(self, tenant_row):
        tenant_row("starter")
        assert plan_limits.check_feature_allowed(_TEST_SCHEMA, "qr")[0] is True
        assert plan_limits.check_feature_allowed(_TEST_SCHEMA, "pin")[0] is True

    def test_starter_blocks_face_and_fingerprint(self, tenant_row):
        tenant_row("starter")
        allowed, msg = plan_limits.check_feature_allowed(_TEST_SCHEMA, "face")
        assert allowed is False
        assert "Starter" in msg
        assert plan_limits.check_feature_allowed(_TEST_SCHEMA, "fingerprint")[0] is False

    def test_growth_allows_face_fingerprint_geo_but_not_biometric(self, tenant_row):
        tenant_row("growth")
        assert plan_limits.check_feature_allowed(_TEST_SCHEMA, "face")[0] is True
        assert plan_limits.check_feature_allowed(_TEST_SCHEMA, "fingerprint")[0] is True
        assert plan_limits.check_feature_allowed(_TEST_SCHEMA, "geo")[0] is True
        assert plan_limits.check_feature_allowed(_TEST_SCHEMA, "biometric")[0] is False

    def test_enterprise_allows_everything(self, tenant_row):
        tenant_row("enterprise")
        for key in ("qr", "pin", "face", "fingerprint", "geo", "biometric"):
            assert plan_limits.check_feature_allowed(_TEST_SCHEMA, key)[0] is True
