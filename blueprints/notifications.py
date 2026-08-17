# -*- coding: utf-8 -*-
"""Notifications blueprint -- in-app notification feeds.

Migrated from app.py (lines 13255–13354). Routes:
  GET  /api/notifications                    → api_get_notifications         (admin, Bearer)
  POST /api/notifications/mark_read          → api_mark_notifications_read   (admin, Bearer)
  GET  /api/employee/notifications           → api_employee_get_notifications (employee, Bearer)
  POST /api/employee/notifications/mark_read → api_employee_mark_notifications_read (employee, Bearer)
  POST /web/notifications/mark_read          → web_employee_mark_notifications_read (employee, session)
  GET  /web/notifications/list               → web_employee_notifications_list      (employee, session)
"""
from flask import Blueprint, jsonify, session, g as _g
from database import get_db_connection
from utils.auth import api_required, employee_api_required, employee_required

notifications_bp = Blueprint("notifications", __name__)


def _fmt(row):
    return {
        "id": row[0],
        "title": row[1],
        "message": row[2],
        "is_read": bool(row[3]),
        "created_at": row[4].strftime("%d %b %Y, %I:%M %p") if row[4] else "",
    }


# ── Admin notifications (Bearer-token API) ────────────────────────────────────

@notifications_bp.route("/api/notifications", methods=["GET"])
@api_required
def api_get_notifications():
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute(
        "SELECT id, title, message, is_read, created_at FROM notifications "
        "WHERE recipient_type='admin' ORDER BY created_at DESC LIMIT 50"
    )
    rows = cursor.fetchall()
    cursor.close()
    db.close()
    return jsonify({"ok": True, "notifications": [_fmt(r) for r in rows]})


@notifications_bp.route("/api/notifications/mark_read", methods=["POST"])
@api_required
def api_mark_notifications_read():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("UPDATE notifications SET is_read=TRUE WHERE recipient_type='admin'")
    db.commit()
    cursor.close()
    db.close()
    return jsonify({"ok": True})


# ── Employee notifications (Bearer-token API) ─────────────────────────────────

@notifications_bp.route("/api/employee/notifications", methods=["GET"])
@employee_api_required
def api_employee_get_notifications():
    emp_id = _g.api_emp_id
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute(
        "SELECT id, title, message, is_read, created_at FROM notifications "
        "WHERE recipient_type='employee' AND employee_id=%s ORDER BY created_at DESC LIMIT 50",
        (emp_id,),
    )
    rows = cursor.fetchall()
    cursor.close()
    db.close()
    return jsonify({"ok": True, "notifications": [_fmt(r) for r in rows]})


@notifications_bp.route("/api/employee/notifications/mark_read", methods=["POST"])
@employee_api_required
def api_employee_mark_notifications_read():
    emp_id = _g.api_emp_id
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE notifications SET is_read=TRUE WHERE recipient_type='employee' AND employee_id=%s",
        (emp_id,),
    )
    db.commit()
    cursor.close()
    db.close()
    return jsonify({"ok": True})


# ── Employee notifications (session-based web) ────────────────────────────────

@notifications_bp.route("/web/notifications/mark_read", methods=["POST"])
@employee_required
def web_employee_mark_notifications_read():
    emp_id = session["employee_id"]
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE notifications SET is_read=TRUE WHERE recipient_type='employee' AND employee_id=%s",
        (emp_id,),
    )
    db.commit()
    cursor.close()
    db.close()
    return jsonify({"ok": True})


@notifications_bp.route("/web/notifications/list")
@employee_required
def web_employee_notifications_list():
    emp_id = session["employee_id"]
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute(
        "SELECT id, title, message, is_read, created_at FROM notifications "
        "WHERE recipient_type='employee' AND employee_id=%s ORDER BY created_at DESC LIMIT 30",
        (emp_id,),
    )
    rows = cursor.fetchall()
    cursor.close()
    db.close()
    return jsonify({"ok": True, "notifications": [_fmt(r) for r in rows]})
