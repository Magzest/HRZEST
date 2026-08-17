# -*- coding: utf-8 -*-
"""Data Loss Prevention: field-level PII masking and clearance checks.

Generalizes a pattern that already existed hand-rolled in one place --
payroll.py's view_payslip restricts unmasked PAN/UAN/bank details to
admin_role=="admin" specifically, and utils/salary_utils.py masks the bank
account to its last 4 digits -- so every other admin-tier route showing the
same class of data (employee_detail, employee_profile, bulk salary lists)
can reuse one definition of "who has clearance" and one masking format
instead of each hand-rolling its own.
"""
from flask import session


def has_pii_clearance() -> bool:
    """True if the current admin-tier session may see unmasked PAN/Aadhaar/
    bank/salary data. Mirrors the existing role model: "admin" is the
    finance/HR-clearance tier; "manager" and "soc_analyst" do not get it,
    matching the restriction payroll.py's view_payslip already enforces for
    payslips specifically. Not meaningful for employee sessions -- those
    routes already scope PII to the caller's own record via
    utils.auth.enforce_ownership()."""
    return session.get("admin_role", "admin") == "admin"


def mask_tail(value, keep: int = 4, mask_char: str = "*") -> str:
    """Masks all but the last `keep` characters -- e.g. bank account
    1234567890 -> ******7890. Short/empty values are masked entirely rather
    than raising, since "value too short to partially mask" should never
    itself leak length information about a genuinely sensitive field."""
    if not value:
        return value
    value = str(value)
    if len(value) <= keep:
        return mask_char * len(value)
    return mask_char * (len(value) - keep) + value[-keep:]
