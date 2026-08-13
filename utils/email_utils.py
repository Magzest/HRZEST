"""Email sending — SMTP + DB-backed queue with retry worker."""
import os
import ssl
import html as _html
import base64
import datetime as _dt
import smtplib
import threading
import time as _time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from database import get_db_connection
from extensions import app_log
from utils.helpers import decrypt_pii


def get_email_config():
    """Return SMTP config dict from DB, falling back to .env values.

    Two bugs fixed here, found by diffing against app.py's copy of this
    same function before either went live in a blueprint:

    1. Wrong column names. email_config's real schema (app.py's init_db())
       is smtp_host/smtp_port/smtp_user/smtp_pass/from_name/from_email —
       this queried host/port/username/password/from_name/from_email,
       none of which exist. Every call would raise "column does not
       exist", get swallowed by the bare except below, and silently fall
       back to .env config — meaning a DB-configured SMTP setup would
       never actually be honored, with no error surfaced anywhere.
    2. Missing decryption. smtp_pass is stored encrypted at rest
       (encrypt_pii on save) — this returned the raw ciphertext as the
       password, which would have failed SMTP auth on every send.

    Also added ORDER BY id DESC: LIMIT 1 with no ORDER BY doesn't
    guarantee which row Postgres returns if more than one exists —
    matches app.py's behavior of always using the most recently saved
    config.
    """
    try:
        db = get_db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute(
            "SELECT smtp_host, smtp_port, smtp_user, smtp_pass, from_name, from_email "
            "FROM email_config ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        cursor.close()
        db.close()
        if row and row[0]:
            return {
                "host": row[0], "port": row[1], "user": row[2], "password": decrypt_pii(row[3]),
                "from_name": row[4], "from_email": row[5] or row[2],
            }
    except Exception:
        pass
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    if smtp_host and smtp_user and smtp_pass:
        return {
            "host": smtp_host,
            "port": int(os.environ.get("SMTP_PORT", 587)),
            "user": smtp_user,
            "password": smtp_pass,
            "from_name": os.environ.get("SMTP_FROM_NAME", "HRzest.com"),
            "from_email": os.environ.get("SMTP_FROM_EMAIL", smtp_user),
        }
    return None


def get_admin_emails():
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT email FROM admin_users WHERE email IS NOT NULL AND email != ''")
    emails = [row[0] for row in cursor.fetchall()]
    cursor.close()
    db.close()
    return emails


def send_email_smtp(to_email, subject, html_body, config,
                    attachment_bytes=None, attachment_filename=None):
    from_addr = config.get("from_email") or config["user"]
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = f"{config['from_name']} <{from_addr}>"
    msg["To"] = to_email
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)
    if attachment_bytes and attachment_filename:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{attachment_filename}"')
        msg.attach(part)
    context = ssl.create_default_context()
    port = int(config.get("port", 587))
    if port == 465:
        with smtplib.SMTP_SSL(config["host"], port, context=context, timeout=20) as server:
            server.login(config["user"], config["password"])
            server.sendmail(from_addr, to_email, msg.as_string())
    else:
        with smtplib.SMTP(config["host"], port, timeout=20) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(config["user"], config["password"])
            server.sendmail(from_addr, to_email, msg.as_string())


def send_email_async(to_email, subject, html_body, config,
                     attachment_bytes=None, attachment_filename=None, **_):
    """Enqueue email for reliable delivery via the DB-backed worker."""
    att_b64 = base64.b64encode(attachment_bytes).decode() if attachment_bytes else None
    try:
        db = get_db_connection()
        cur = db.cursor()
        cur.execute(
            "INSERT INTO email_queue (to_email, subject, html_body, attachment_b64, attachment_filename) "
            "VALUES (%s,%s,%s,%s,%s)",
            (to_email, subject, html_body, att_b64, attachment_filename)
        )
        db.commit()
        cur.close()
        db.close()
    except Exception as e:
        app_log.error("Failed to enqueue email to %s: %s", to_email, e)
        threading.Thread(
            target=lambda: send_email_smtp(to_email, subject, html_body, config,
                                           attachment_bytes=attachment_bytes,
                                           attachment_filename=attachment_filename),
            daemon=True
        ).start()


def _email_queue_worker():
    """Background thread: dequeues and sends emails; retries up to 3 times."""
    while True:
        try:
            cfg = get_email_config()
            if not cfg:
                _time.sleep(30)
                continue
            db = get_db_connection()
            cur = db.cursor(buffered=True)
            cur.execute(
                "SELECT id, to_email, subject, html_body, attachment_b64, attachment_filename "
                "FROM email_queue WHERE status='pending' AND attempts < 3 "
                "ORDER BY created_at LIMIT 10"
            )
            rows = cur.fetchall()
            for row in rows:
                eid, to_email, subject, html_body, att_b64, att_name = row
                cur.execute(
                    "UPDATE email_queue SET status='sending', attempts=attempts+1 WHERE id=%s", (eid,)
                )
                db.commit()
                try:
                    att_bytes = base64.b64decode(att_b64) if att_b64 else None
                    send_email_smtp(to_email, subject, html_body, cfg,
                                    attachment_bytes=att_bytes, attachment_filename=att_name)
                    cur.execute(
                        "UPDATE email_queue SET status='done', sent_at=NOW() WHERE id=%s", (eid,)
                    )
                except Exception as exc:
                    app_log.error("Email queue send failed to %s: %s", to_email, exc)
                    cur.execute(
                        "UPDATE email_queue SET status='pending', last_error=%s WHERE id=%s",
                        (str(exc)[:500], eid)
                    )
                db.commit()
            cur.execute(
                "UPDATE email_queue SET status='failed' WHERE status='pending' AND attempts >= 3"
            )
            db.commit()
            cur.close()
            db.close()
        except Exception as _we:
            app_log.error("Email queue worker error: %s", _we)
        _time.sleep(15)


def build_new_ip_login_email(display_name, identifier, ip_address, login_time_str):
    """Account-owner-facing notification: 'a sign-in happened from an IP we
    haven't seen before for this account.' All interpolated values are
    escaped — this reaches the same HTML-email sink that needed retrofitting
    for missing escaping elsewhere in this codebase, so it's done correctly
    here from the start rather than as a later fix."""
    _name = _html.escape(str(display_name))
    _id = _html.escape(str(identifier))
    _ip = _html.escape(str(ip_address))
    _time_s = _html.escape(str(login_time_str))
    return f"""
<div style="font-family:Segoe UI,sans-serif;max-width:540px;margin:auto;background:#f8fafc;border-radius:16px;overflow:hidden;border:1px solid #fde68a;">
  <div style="background:#92400e;padding:24px 28px;color:white;">
    <div style="font-size:20px;font-weight:700;">🔐 New Sign-In Detected</div>
    <div style="font-size:13px;opacity:0.8;margin-top:4px;">HRzest.com</div>
  </div>
  <div style="padding:28px;">
    <p style="color:#334155;font-size:14px;">Hi <strong>{_name}</strong>,</p>
    <p style="color:#475569;font-size:14px;">We noticed a sign-in to your account (<strong>{_id}</strong>) from an IP address we haven't seen on this account before:</p>
    <table style="width:100%;border-collapse:collapse;font-size:14px;margin:16px 0;">
      <tr style="background:#f1f5f9;"><td style="padding:10px 14px;color:#555;font-weight:600;width:120px;">IP Address</td><td style="padding:10px 14px;">{_ip}</td></tr>
      <tr><td style="padding:10px 14px;color:#555;font-weight:600;">Time</td><td style="padding:10px 14px;">{_time_s}</td></tr>
    </table>
    <div style="background:#fef3c7;border-left:4px solid #d97706;border-radius:8px;padding:16px 18px;margin:20px 0;">
      <p style="margin:0;font-size:13px;color:#92400e;font-weight:700;">Was this you?</p>
      <p style="margin:8px 0 0;font-size:13px;color:#78350f;">If yes — no action needed, you can ignore this email.</p>
      <p style="margin:10px 0 0;font-size:13px;color:#78350f;font-weight:700;">If this wasn't you, please do the following now:</p>
      <ol style="margin:6px 0 0;padding-left:18px;font-size:13px;color:#78350f;">
        <li>Change your password immediately.</li>
        <li>Contact your administrator so they can review your account.</li>
        <li>Check your recent attendance/activity for anything unfamiliar.</li>
      </ol>
    </div>
    <p style="font-size:12px;color:#94a3b8;margin-top:20px;">This is an automated security notification — replies aren't monitored.</p>
  </div>
</div>"""


def notify_if_new_login_ip(identifier, attempt_type, ip_address, display_name, to_email):
    """Record ip_address for this account; queue a 'new sign-in' security
    email to the account owner only if it's genuinely new against an
    already-established history.

    Deliberately does NOT alert on an account's very first-ever recorded
    login — there's no baseline yet to compare against, so treating IP #1
    as "new" would email every user on every fresh account's first login.
    Only IP #2-and-onward, the first time each is seen, triggers a mail.

    Best-effort: any failure here is logged and swallowed, never raised —
    this must not be able to block a login that already succeeded.
    """
    if not ip_address or not to_email:
        return
    try:
        db = get_db_connection()
        cur = db.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM known_login_ips WHERE identifier=%s AND attempt_type=%s",
            (identifier, attempt_type)
        )
        existing_count = cur.fetchone()[0]
        cur.execute(
            "SELECT 1 FROM known_login_ips WHERE identifier=%s AND attempt_type=%s AND ip_address=%s",
            (identifier, attempt_type, ip_address)
        )
        already_known = cur.fetchone() is not None
        if not already_known:
            cur.execute(
                "INSERT INTO known_login_ips (identifier, attempt_type, ip_address) VALUES (%s,%s,%s) "
                "ON CONFLICT (identifier, attempt_type, ip_address) DO NOTHING",
                (identifier, attempt_type, ip_address)
            )
            db.commit()
        cur.close()
        db.close()
    except Exception as e:
        app_log.error("notify_if_new_login_ip: known_login_ips check failed for %s: %s", identifier, e)
        return

    is_first_ever_login = (existing_count == 0)
    if already_known or is_first_ever_login:
        return

    try:
        cfg = get_email_config()
        if not cfg:
            return
        login_time_str = _dt.datetime.now().strftime("%d %b %Y, %I:%M %p")
        html_body = build_new_ip_login_email(display_name, identifier, ip_address, login_time_str)
        send_email_async(to_email, "New Sign-In to Your Account", html_body, cfg)
    except Exception as e:
        app_log.error("notify_if_new_login_ip: failed to queue email for %s: %s", identifier, e)
