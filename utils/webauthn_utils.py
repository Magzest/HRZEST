# -*- coding: utf-8 -*-
"""WebAuthn (passkey/fingerprint) + mobile-biometric infrastructure.

Extracted from app.py so both the auth blueprint (enrollment/verification
routes) and app.py itself (attendance check-in gating via
_wa_fingerprint_recently_verified/_mobile_biometric_recently_verified, and
admin-side enrollment via _enroll_fingerprint_from_form's call to
_wa_verify_and_store_registration) share one canonical implementation
instead of forking it across a blueprint boundary.
"""
import base64
import json
import re
import secrets
import time
import datetime
from urllib.parse import urlparse

from flask import request, session, flash

from extensions import app_log, _allowed_origins
from utils.helpers import _db

try:
    # typing.Literal was added in Python 3.8; backport it for 3.7 so webauthn imports cleanly
    import typing as _typing
    if not hasattr(_typing, "Literal"):
        from typing_extensions import Literal as _Literal
        _typing.Literal = _Literal
    import webauthn
    # Only COSEAlgorithmIdentifier is used in this file (below); the rest are
    # re-exported for blueprints/auth.py's `from utils.webauthn_utils import
    # AuthenticatorSelectionCriteria, ...` -- flake8 can't see that cross-file
    # usage, so don't "clean up" this import as dead code without checking
    # blueprints/auth.py's registration-options construction first.
    from webauthn.helpers.structs import (  # noqa: F401
        AuthenticatorSelectionCriteria, AuthenticatorAttachment, UserVerificationRequirement,
        ResidentKeyRequirement, PublicKeyCredentialDescriptor, AuthenticatorTransport,
        COSEAlgorithmIdentifier, AttestationConveyancePreference,
    )
    _webauthn_available = True
except Exception as _wa_err:
    webauthn = None
    _webauthn_available = False
    print(f"⚠  webauthn unavailable ({_wa_err}). Fingerprint features disabled. (Needs Python 3.8+; "
          f"runs fine in the production Podman image, which uses Python 3.11.)")

_IP_RE = re.compile(r'^\d{1,3}(\.\d{1,3}){3}$')


def _wa_rp_id():
    """WebAuthn Relying Party ID.
    Loopback: return the exact host so the browser's origin matches.
    Everything else: prefer ALLOWED_ORIGINS[0] (avoids Host-header injection and
    ensures a proper domain name is used even when accessed via LAN IP).
    Falls back to the raw host only when ALLOWED_ORIGINS is unconfigured or '*'."""
    host = request.host.split(":")[0]
    # Loopback: must match the browser origin exactly; return immediately
    if host in ("127.0.0.1", "::1", "localhost"):
        return host
    # Named hosts and LAN IPs: use the pinned production domain when available
    if _allowed_origins != "*" and _allowed_origins:
        canonical = urlparse(_allowed_origins[0]).hostname
        if canonical:
            return canonical
    # NOTE: returning a non-loopback IP here will be rejected by browsers as an RP ID
    return host


def _wa_check_rp_id(rp_id):
    """Return an error string if rp_id is a non-loopback IP (browsers reject these as RP IDs),
    or None if it looks usable."""
    if rp_id in ("127.0.0.1", "::1", "localhost"):
        return None
    if _IP_RE.match(rp_id):
        return (
            f"WebAuthn does not support IP addresses as RP IDs (got '{rp_id}'). "
            "Access the server via 'localhost' on the server machine, or configure a "
            "hostname (e.g. add an entry in your hosts file and set ALLOWED_ORIGINS)."
        )
    return None


def _wa_origins():
    """Return the set of acceptable WebAuthn origins for this host.
    Always accepts both 127.0.0.1 and localhost as equivalent loopback origins.
    For LAN IPs the only valid origin is the exact IP+port the browser used."""
    host = request.host  # includes port if non-standard
    scheme = request.scheme
    origins = {f"{scheme}://{host}"}
    bare = host.split(":")[0]
    if bare == "127.0.0.1":
        origins.add(f"{scheme}://{host.replace('127.0.0.1', 'localhost')}")
    elif bare == "localhost":
        origins.add(f"{scheme}://{host.replace('localhost', '127.0.0.1')}")
    # LAN IPs: the single origin already added above is correct
    return list(origins)


def _wa_b64url_decode(s):
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _wa_b64url_encode(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


# How long a real, just-completed WebAuthn assertion stays usable to authorize
# a single subsequent check-in call, scoped to the specific employee_id that
# completed it. Prevents both replay across employees and indefinite reuse.
_WA_FP_VERIFY_WINDOW_SEC = 120


def _wa_fingerprint_recently_verified(emp_id):
    """One-time, employee-bound check: did this employee just complete a real
    WebAuthn signature verification in this session? Consumes the proof."""
    emp_id = (emp_id or "").strip().upper()
    verified_emp = session.pop("wa_fp_verified_emp_id", None)
    verified_at = session.pop("wa_fp_verified_at", 0)
    return bool(emp_id) and verified_emp == emp_id and (time.time() - verified_at) <= _WA_FP_VERIFY_WINDOW_SEC


# ---- Mobile-app biometric attestation -------------------------------------
# The mobile app has no browser, so it can't do real WebAuthn (no native
# platform-authenticator API in React Native) and has no Flask session
# cookie to piggyback the proof above on. Instead it gets a weaker but still
# meaningfully-bound proof: a server-issued, single-use nonce minted only to
# the holder of a valid employee Bearer token, consumed by a second
# Bearer-authenticated call right after the device's local biometric/PIN
# check succeeds. This is NOT a cryptographic signature -- it cannot detect a
# cloned/replayed device biometric -- but unlike the old flow it cannot be
# satisfied without first proving possession of that exact employee's token.
_MOBILE_BIO_NONCE_TTL_SEC = 60
_MOBILE_BIO_VERIFY_WINDOW_SEC = 120


def _mobile_biometric_issue_nonce(emp_id):
    """Mint a fresh single-use nonce for emp_id, replacing any prior one."""
    nonce = secrets.token_hex(16)
    with _db() as (cursor, conn):
        cursor.execute(
            "INSERT INTO mobile_biometric_proofs (employee_id, nonce, nonce_expires_at, verified_at) "
            "VALUES (%s, %s, NOW() + %s * INTERVAL '1 second', NULL) "
            "ON CONFLICT (employee_id) DO UPDATE SET "
            "nonce=EXCLUDED.nonce, nonce_expires_at=EXCLUDED.nonce_expires_at, verified_at=NULL",
            (emp_id, nonce, _MOBILE_BIO_NONCE_TTL_SEC)
        )
        conn.commit()
    return nonce


def _mobile_biometric_attest(emp_id, nonce):
    """Consume a nonce after the mobile app confirms a local biometric/device
    check for this exact authenticated employee. Returns (ok, err_msg)."""
    if not nonce:
        return False, "Missing nonce"
    with _db() as (cursor, conn):
        cursor.execute(
            "SELECT nonce, nonce_expires_at FROM mobile_biometric_proofs WHERE employee_id=%s",
            (emp_id,)
        )
        row = cursor.fetchone()
        if not row or row[0] != nonce or not row[1] or row[1] < datetime.datetime.now():
            return False, "Invalid or expired nonce"
        cursor.execute(
            "UPDATE mobile_biometric_proofs SET nonce=NULL, nonce_expires_at=NULL, verified_at=NOW() "
            "WHERE employee_id=%s",
            (emp_id,)
        )
        conn.commit()
    return True, None


def _mobile_biometric_recently_verified(emp_id):
    """One-time, employee-bound check mirroring _wa_fingerprint_recently_verified,
    but DB-backed (mobile has no Flask session) and gated by a real employee
    Bearer token at both the nonce-issue and attest steps above."""
    emp_id = (emp_id or "").strip().upper()
    if not emp_id:
        return False
    with _db() as (cursor, conn):
        cursor.execute(
            "SELECT verified_at FROM mobile_biometric_proofs WHERE employee_id=%s",
            (emp_id,)
        )
        row = cursor.fetchone()
        if not row or not row[0]:
            return False
        verified_at = row[0]
        cursor.execute(
            "UPDATE mobile_biometric_proofs SET verified_at=NULL WHERE employee_id=%s",
            (emp_id,)
        )
        conn.commit()
    return (datetime.datetime.now() - verified_at).total_seconds() <= _MOBILE_BIO_VERIFY_WINDOW_SEC


def _wa_verify_and_store_registration(emp_id, credential, challenge_b64, cursor, db):
    """Verify a WebAuthn registration response (real signature/attestation
    check) and persist the credential id + public key + sign count.
    `credential` may be a dict or a JSON string. Returns (ok, err_msg)."""
    if not _webauthn_available:
        return False, "Fingerprint enrollment is not available on this server."
    if not credential or not challenge_b64:
        return False, "Missing credential or challenge -- please try enrolling again"
    # Rebuild the supported-alg list from session if available; fall back to the
    # same two algorithms we offer in generate_registration_options.
    _alg_ids = session.get("wa_reg_alg_ids") or [-7, -257]
    _supported_algs = [COSEAlgorithmIdentifier(v) for v in _alg_ids]
    _rp_id = _wa_rp_id()
    _origins = _wa_origins()
    app_log.info("WebAuthn verify: emp=%s rp_id=%s origins=%s", emp_id, _rp_id, _origins)
    try:
        if isinstance(credential, str):
            credential = json.loads(credential)
        verified = webauthn.verify_registration_response(
            credential=credential,
            expected_challenge=_wa_b64url_decode(challenge_b64),
            expected_rp_id=_rp_id,
            expected_origin=_origins,
            supported_pub_key_algs=_supported_algs,
        )
    except Exception as exc:
        app_log.warning("WebAuthn registration failed: emp=%s rp_id=%s origins=%s err=%s",
                        emp_id, _rp_id, _origins, exc, exc_info=True)
        return False, f"Enrollment failed: {exc}"
    cred_id_b64 = _wa_b64url_encode(verified.credential_id)
    pubkey_b64 = base64.b64encode(verified.credential_public_key).decode()
    cursor.execute(
        "UPDATE employees SET fingerprint_credential_id=%s, fingerprint_public_key=%s, "
        "fingerprint_sign_count=%s WHERE employee_id=%s",
        (cred_id_b64, pubkey_b64, verified.sign_count, emp_id)
    )
    db.commit()
    return True, None


def _enroll_fingerprint_from_form(emp_id, cursor, db):
    """Shared by admin_action()/add_employee_page(): read the WebAuthn
    attestation posted by the registration form (if any), verify and store
    it, flashing a warning on failure. No-op if the field is empty."""
    fp_attestation = request.form.get("fingerprint_attestation", "").strip()
    if not fp_attestation:
        return
    _ok, _err = _wa_verify_and_store_registration(
        emp_id, fp_attestation, session.get("wa_reg_challenge"), cursor, db
    )
    session.pop("wa_reg_challenge", None)
    session.pop("wa_reg_alg_ids", None)
    if not _ok:
        flash(f"⚠️ Fingerprint enrollment failed verification: {_err}", "error")
