# -*- coding: utf-8 -*-
"""Deception honeypot decoy routes -- fake paths a real user never requests
(scanner-bot bait: /.env, /wp-admin/, /phpmyadmin, etc.), auto-banning
whatever IP touches one. Extracted out of the removed SecOps dashboard
(blueprints/secops.py) so this auto-banning perimeter keeps working without
the dashboard/portal it used to live inside -- this file has no dependency
on that portal or its auth model, it's a plain unauthenticated trap."""
from flask import Blueprint, request, jsonify
from database import get_db_connection, transaction
from extensions import app_log, log_security_event

honeypot_bp = Blueprint("honeypot_routes", __name__)


@honeypot_bp.route("/.env")
@honeypot_bp.route("/.git/config")
@honeypot_bp.route("/wp-admin/")
@honeypot_bp.route("/wp-login.php")
@honeypot_bp.route("/api/v1/internal/admin_dump")
@honeypot_bp.route("/actuator/health")
@honeypot_bp.route("/phpmyadmin")
@honeypot_bp.route("/backup.sql")
@honeypot_bp.route("/server-status")
def honeypot_trap():
    """Deception Honeypot Trap: Intercepts scanner bots and auto-bans attacker IPs."""
    ip = request.remote_addr or "unknown"
    path = request.path
    log_security_event(
        "secops.honeypot_triggered",
        f"Deception honeypot trap '{path}' triggered by automated scanner bot",
        level="CRITICAL",
        ip=ip,
        path=path,
        method=request.method
    )
    # Auto-ban client IP in banned_ips table
    try:
        db = get_db_connection()
        with transaction(db):
            cur = db.cursor()
            cur.execute(
                "INSERT INTO banned_ips (ip, reason, banned_at) VALUES (%s, %s, NOW()) ON CONFLICT (ip) DO NOTHING",
                (ip, f"Honeypot Decoy Trap Triggered ({path})")
            )
            cur.close()
    except Exception as exc:
        app_log.warning("Honeypot auto-ban write error: %s", exc)

    return jsonify({"error": "Resource not found", "status": 404}), 404
