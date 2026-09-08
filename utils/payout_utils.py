# -*- coding: utf-8 -*-
"""Bank-payout execution -- currently a STUB.

No real payout provider (RazorpayX Payouts, Cashfree Payouts, etc.) is
connected today. execute_payout() below MUST NEVER report success unless a
real transfer actually happened -- an admin (or an employee reading a
payslip email) believing salary was paid when it wasn't is a far worse
failure mode than the feature simply not working yet. Every caller must
treat `ok=False` as the only possible outcome until PAYOUT_PROVIDER is set
and a real implementation replaces the branch below.

To wire a real provider later: branch on os.environ["PAYOUT_PROVIDER"]
(e.g. "razorpayx") and add a real implementation alongside this stub --
do not silently change the stub's return shape, callers depend on
(ok, reference_or_error).
"""
import os
import re

from extensions import app_log

_IFSC_RE = re.compile(r'^[A-Z]{4}0[A-Z0-9]{6}$')


def get_payout_bank_config():
    """Return the tenant's payout_bank_config as a dict (account_number
    decrypted), or None if never configured. Same singleton-row,
    fail-soft-to-None shape as utils/email_utils.py's get_email_config() --
    background code (the disbursement-prep cron job) must never raise just
    because a tenant hasn't set this up yet."""
    from database import get_db_connection
    from utils.helpers import decrypt_pii
    try:
        db = get_db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute(
            "SELECT account_holder_name, bank_name, account_number, ifsc_code, "
            "disbursement_day_of_month, approval_lead_days, enabled "
            "FROM payout_bank_config ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        cursor.close()
        db.close()
        if not row:
            return None
        return {
            "account_holder_name": row[0], "bank_name": row[1],
            "account_number": decrypt_pii(row[2]), "ifsc_code": row[3],
            "disbursement_day_of_month": row[4], "approval_lead_days": row[5],
            "enabled": bool(row[6]),
        }
    except Exception as exc:
        app_log.warning("get_payout_bank_config: lookup failed: %s", exc, exc_info=True)
        return None


def validate_ifsc(ifsc: str):
    """Return (True, None) if ifsc matches the standard Indian IFSC format,
    else (False, error_message). No format-validation precedent existed
    anywhere in this codebase for bank fields before this -- added here
    since this is the account real money actually moves through."""
    ifsc = (ifsc or "").strip().upper()
    if not _IFSC_RE.match(ifsc):
        return False, "IFSC code must be 11 characters (e.g. HDFC0001234)."
    return True, None


def mask_account_number(account_number: str) -> str:
    """Last-4-digits display mask. No masking convention existed anywhere
    in this codebase before this (employee bank details are shown in full
    plaintext once decrypted) -- this is a deliberate improvement for the
    company's own source-of-funds account, not a pattern copied from
    elsewhere."""
    digits = (account_number or "").strip()
    if len(digits) <= 4:
        return "*" * len(digits)
    return "*" * (len(digits) - 4) + digits[-4:]


def payout_provider_configured() -> bool:
    return bool(os.environ.get("PAYOUT_PROVIDER", "").strip())


def execute_payout(from_bank: dict, to_bank: dict, amount, employee_id: str):
    """Attempt one bank transfer. Returns (ok, reference_or_error).

    from_bank / to_bank: {"account_holder_name", "bank_name", "account_number", "ifsc_code"}
    (account_number here is already-decrypted plaintext -- caller's job to
    decrypt just-in-time and never persist the plaintext anywhere).

    Stub behavior: always fails closed. No PAYOUT_PROVIDER is configured
    in this deployment, so there is no real transfer to attempt.
    """
    if not payout_provider_configured():
        return False, "No payout provider configured (PAYOUT_PROVIDER unset) -- no transfer was attempted."
    # A real provider's implementation goes here once PAYOUT_PROVIDER is set.
    # Deliberately unreachable today: raising instead of a soft failure so a
    # misconfigured env var (a typo'd provider name that isn't handled below)
    # can never be silently mistaken for "some transfer path ran".
    raise NotImplementedError(
        f"PAYOUT_PROVIDER={os.environ.get('PAYOUT_PROVIDER')!r} has no real implementation wired up yet."
    )
