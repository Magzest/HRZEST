"""TOTP (RFC 6238) two-factor auth for the admin Email Settings step-up gate.

The secret is stored encrypted at rest via the same Fernet-based encrypt_pii/
decrypt_pii used for PII fields (utils/helpers.py) — reusing the codebase's
one established encryption idiom rather than introducing a second scheme.
"""
import html as _html
import base64
import io
import pyotp
import qrcode
from database import get_db_connection
from utils.helpers import encrypt_pii, decrypt_pii

_ISSUER = "Attendance System"


def get_or_create_admin_totp_secret(admin_username: str):
    """Return (secret, already_enabled). Generates+stores a new secret the
    first time this admin goes through enrollment; reuses it after."""
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT totp_secret, totp_enabled FROM admin_users WHERE username=%s", (admin_username,))
    row = cursor.fetchone()
    if row and row[0]:
        cursor.close()
        db.close()
        return decrypt_pii(row[0]), bool(row[1])
    secret = pyotp.random_base32()
    cursor.execute(
        "UPDATE admin_users SET totp_secret=%s WHERE username=%s",
        (encrypt_pii(secret), admin_username),
    )
    db.commit()
    cursor.close()
    db.close()
    return secret, False


def mark_totp_enabled(admin_username: str):
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("UPDATE admin_users SET totp_enabled=1 WHERE username=%s", (admin_username,))
    db.commit()
    cursor.close()
    db.close()


def reset_admin_totp_secret(admin_username: str):
    """Wipes the stored secret and disables 2FA so the next call to
    get_or_create_admin_totp_secret issues a brand-new secret/QR — for an
    admin who deleted the entry from their authenticator app and can no
    longer produce a code for the old secret."""
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute(
        "UPDATE admin_users SET totp_secret=NULL, totp_enabled=0 WHERE username=%s",
        (admin_username,),
    )
    db.commit()
    cursor.close()
    db.close()


def verify_totp_code(admin_username: str, code: str, require_enabled: bool = True) -> bool:
    """require_enabled=False is only for the one-time enrollment-confirmation
    step, where totp_enabled is still 0 by definition. Every other caller
    (the actual step-up gate) must use the default True."""
    code = (code or "").strip()
    if not code or len(code) != 6 or not code.isdigit():
        return False
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT totp_secret, totp_enabled FROM admin_users WHERE username=%s", (admin_username,))
    row = cursor.fetchone()
    cursor.close()
    db.close()
    if not row or not row[0]:
        return False
    if require_enabled and not row[1]:
        return False
    secret = decrypt_pii(row[0])
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def send_mfa_login_email(to_email: str, username: str, role_label: str, secret: str, otp_code: str):
    """Email a one-time login code to a SOC/SP-admin account as its MFA
    step (blueprints/secops.py's sp_admin_login()). Deliberately does NOT
    include the TOTP secret in the email body -- only the single-use code
    -- since a raw secret in an inbox would let anyone with mailbox access
    mint valid codes indefinitely, not just for this one login. `secret` is
    accepted for signature compatibility with callers that also enroll TOTP
    but isn't otherwise used here."""
    from utils.email_utils import get_email_config, send_email_async
    _user = _html.escape(str(username))
    _role = _html.escape(str(role_label))
    _code = _html.escape(str(otp_code))
    html_body = f"""
<div style="font-family:Segoe UI,sans-serif;max-width:480px;margin:auto;background:#0f172a;border-radius:16px;overflow:hidden;border:1px solid #1e293b;">
  <div style="background:#1d4ed8;padding:22px 26px;color:#fff;">
    <div style="font-size:18px;font-weight:700;">Login Verification Code</div>
    <div style="font-size:12px;opacity:0.8;margin-top:4px;">{_role} &middot; {_user}</div>
  </div>
  <div style="padding:26px;">
    <p style="color:#cbd5e1;font-size:13px;">Use this code to finish signing in. It expires in 5 minutes and can only be used once.</p>
    <div style="text-align:center;margin:22px 0;padding:16px;background:#090d16;border-radius:12px;">
      <span style="font-size:32px;font-weight:800;letter-spacing:6px;color:#60a5fa;">{_code}</span>
    </div>
    <p style="font-size:12px;color:#64748b;">If you didn't request this, someone may have your password — change it and contact your administrator.</p>
  </div>
</div>"""
    config = get_email_config()
    if not config:
        return False
    send_email_async(to_email, "Your SecOps login code", html_body, config)
    return True


def totp_qr_data_uri(admin_username: str, secret: str) -> str:
    """Base64 PNG data: URI of the provisioning QR code, for the admin to
    scan with Google Authenticator/Authy/etc during enrollment."""
    uri = pyotp.TOTP(secret).provisioning_uri(name=admin_username, issuer_name=_ISSUER)
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
