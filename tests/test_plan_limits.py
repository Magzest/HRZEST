"""Tests for utils/plan_limits.py -- flat per-employee billing.

Tiered plans (Basic/Medium/Prime) were retired in favor of a single flat
rate per employee, with every feature available to every tenant
regardless of headcount. These tests cover the pure pricing math and the
live employee-count lookup; there's no more tier/feature-gating behavior
to exercise here.
"""
import os
import pytest
import utils.plan_limits as plan_limits


_TEST_SCHEMA = os.environ.get("DB_NAME", "employee_attendance")


class TestCalculatePrice:
    def test_zero_employees_is_zero(self):
        assert plan_limits.calculate_price(0) == 0

    def test_one_employee(self):
        assert plan_limits.calculate_price(1) == plan_limits.PER_EMPLOYEE_PAISE

    def test_scales_linearly_with_headcount(self):
        assert plan_limits.calculate_price(50) == 50 * plan_limits.PER_EMPLOYEE_PAISE

    def test_negative_count_clamped_to_zero(self):
        assert plan_limits.calculate_price(-5) == 0

    def test_no_cap_at_large_headcount(self):
        # No employee limit anymore -- price just keeps scaling.
        assert plan_limits.calculate_price(10000) == 10000 * plan_limits.PER_EMPLOYEE_PAISE


class TestFormatPriceInr:
    def test_formats_whole_rupees(self):
        assert plan_limits.format_price_inr(plan_limits.PER_EMPLOYEE_PAISE) == "₹99"

    def test_adds_thousands_separators(self):
        assert plan_limits.format_price_inr(100000000) == "₹1,000,000"

    def test_zero(self):
        assert plan_limits.format_price_inr(0) == "₹0"


class TestGetTenantEmployeeCount:
    def test_invalid_schema_name_fails_to_zero(self):
        # database.py's _set_search_path validates schema_name against
        # ^[a-zA-Z0-9_]+$ before use and raises on a mismatch -- caught by
        # get_tenant_employee_count's try/except, same fail-safe-to-zero
        # contract as an unreachable DB. (A syntactically valid but
        # unregistered schema name isn't a true negative case here:
        # _set_search_path always appends ", public" as a fallback, so an
        # unknown schema still resolves to whatever's in the public schema
        # rather than erroring.)
        assert plan_limits.get_tenant_employee_count("not a valid schema!") == 0

    def test_reads_real_employee_count(self, db_engine):
        cur = db_engine.cursor()
        cur.execute("SELECT COUNT(*) FROM employees")
        expected = cur.fetchone()[0]
        cur.close()
        assert plan_limits.get_tenant_employee_count(_TEST_SCHEMA) == expected
