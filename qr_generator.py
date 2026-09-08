import qrcode
import os
import hmac
import hashlib


def _qr_signature(emp_id: str) -> str:
    """HMAC-SHA256(SECRET_KEY, "qr:"+emp_id), truncated to 16 hex chars (64
    bits) -- signs the employee ID embedded in a QR code so a scanner can't
    just guess or type another employee's ID and have it accepted. Employee
    IDs are often sequential (EMP001, EMP002, ...), so encoding the raw ID
    alone let anyone who knew or guessed a coworker's ID spoof their
    attendance via the QR-only check-in path with zero further
    verification. Reads SECRET_KEY fresh on every call (not cached at
    import time) so key rotation naturally invalidates old QR codes too,
    same as it already invalidates sessions.

    "qr:" prefix domain-separates this HMAC from any other use of
    SECRET_KEY (e.g. Flask's own session signing) using the same key."""
    secret = os.environ.get("SECRET_KEY", "")
    return hmac.new(secret.encode(), f"qr:{emp_id}".encode(), hashlib.sha256).hexdigest()[:16]


def generate_qr(emp_id):
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "qrcodes")

    if not os.path.exists(folder):
        os.makedirs(folder)

    path = os.path.join(folder, f"{emp_id}.png")
    qr_value = f"{emp_id}.{_qr_signature(emp_id)}"
    img = qrcode.make(qr_value)
    img.save(path)
    return f"static/qrcodes/{emp_id}.png"


def verify_qr_value(qr_value: str):
    """Split a scanned QR payload of the form "<employee_id>.<signature>"
    into (employee_id, is_valid). Returns (None, False) for anything
    malformed or whose signature doesn't match -- callers must not trust
    the returned employee_id unless is_valid is True. Case-insensitive on
    the signature so callers that upper() the whole scanned string (as
    several check-in routes already did before this existed) don't break
    a legitimate scan."""
    if not qr_value or "." not in qr_value:
        return None, False
    emp_id, _, sig = qr_value.rpartition(".")
    if not emp_id or not sig:
        return None, False
    expected = _qr_signature(emp_id)
    if not hmac.compare_digest(expected, sig.lower()):
        return None, False
    return emp_id, True
