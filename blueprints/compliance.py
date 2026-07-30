"""Compliance & Security Center — certification attestations, regulatory
deadlines, a searchable audit-log explorer, and a role/feature access
matrix. Locked to the 'admin' role specifically (role_required("admin")),
not just any admin-side session -- HR and SOC accounts are separate,
narrowly-scoped credentials (see blueprints/hr_portal.py, blueprints/secops.py)
that must not reach audit logs or certification records.

Deliberately no auto-computed "compliant" claims: certification status and
deadlines are whatever an admin has genuinely entered (default "Not
Started" / empty), same philosophy as secops._compute_security_posture's
"real facts, not a fabricated score". The access-control matrix is a
static snapshot of the @admin_required / @role_required("admin") /
_soc_session_and_stepup_or_404 / @employee_required gates that already
exist in the blueprints -- not a live-queried "permission system" this app
doesn't have.
"""
import datetime
import math
import os

from flask import Blueprint, request, redirect, render_template, flash

from database import get_db_connection
from utils.auth import role_required
from utils.helpers import _audit

compliance_bp = Blueprint("compliance", __name__)

CERT_STATUSES = ["Not Started", "In Progress", "Compliant", "Needs Attention"]
DEADLINE_CATEGORIES = ["Regulatory", "Tax Filing", "Labour Law", "Audit", "Other"]
DEADLINE_STATUSES = ["Pending", "Completed", "Missed"]

# Snapshot of this app's actual authorization gates -- see module docstring.
ACCESS_MATRIX = [
    {"feature": "Employee Directory & Records", "gate": "@admin_required",
     "admin": True, "hr": True, "soc_analyst": False, "employee": False},
    {"feature": "Payroll & Payslips", "gate": "@role_required(\"admin\")",
     "admin": True, "hr": False, "soc_analyst": False, "employee": False},
    {"feature": "Attendance Management", "gate": "@admin_required",
     "admin": True, "hr": True, "soc_analyst": False, "employee": False},
    {"feature": "Performance Reviews & 9-Box", "gate": "@admin_required",
     "admin": True, "hr": True, "soc_analyst": False, "employee": False},
    {"feature": "Onboarding", "gate": "@admin_required",
     "admin": True, "hr": True, "soc_analyst": False, "employee": False},
    {"feature": "Tenant / System Settings & Company Management", "gate": "@role_required(\"admin\")",
     "admin": True, "hr": False, "soc_analyst": False, "employee": False},
    {"feature": "Compliance & Security Center", "gate": "@role_required(\"admin\")",
     "admin": True, "hr": False, "soc_analyst": False, "employee": False},
    {"feature": "SOC Security Dashboard", "gate": "_soc_session_and_stepup_or_404()",
     "admin": False, "hr": False, "soc_analyst": True, "employee": False},
    {"feature": "Employee Self-Service Portal", "gate": "@employee_required",
     "admin": False, "hr": False, "soc_analyst": False, "employee": True},
]


@compliance_bp.route("/compliance")
@role_required("admin")
def compliance_center():
    db = get_db_connection()
    cursor = db.cursor(buffered=True)

    cursor.execute("SELECT company_name FROM company_settings LIMIT 1")
    row = cursor.fetchone()
    co = type('Co', (), {'company_name': row[0] if row else 'My Company'})()

    cursor.execute(
        "SELECT id, framework, status, owner, last_reviewed, next_review, notes, updated_at "
        "FROM compliance_certifications ORDER BY id ASC"
    )
    certifications = cursor.fetchall()

    cursor.execute(
        "SELECT id, title, jurisdiction, category, due_date, status, notes "
        "FROM compliance_deadlines WHERE status = 'Pending' ORDER BY due_date ASC LIMIT 20"
    )
    upcoming_deadlines = cursor.fetchall()

    cursor.execute(
        "SELECT id, title, jurisdiction, category, due_date, status, notes "
        "FROM compliance_deadlines WHERE status != 'Pending' ORDER BY due_date DESC LIMIT 10"
    )
    past_deadlines = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM audit_logs")
    audit_log_count = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM login_attempts WHERE locked_until IS NOT NULL AND locked_until > NOW()"
    )
    active_lockouts = cursor.fetchone()[0]

    thirty_days_ago = datetime.datetime.now() - datetime.timedelta(days=30)
    cursor.execute(
        "SELECT COUNT(*) FROM security_events WHERE level IN ('WARNING','WARN','ERROR','CRITICAL') "
        "AND created_at >= %s", (thirty_days_ago,)
    )
    recent_security_events = cursor.fetchone()[0]

    db_host = os.environ.get("DB_HOST", "localhost")
    cursor.execute("SELECT current_schema()")
    tenant_schema = cursor.fetchone()[0]

    cursor.close()
    db.close()

    pending_leaves = pending_resignations = pending_tickets = overdue_onboardings = 0

    return render_template(
        "compliance_center.html",
        co=co,
        active_nav="compliance",
        certifications=certifications,
        upcoming_deadlines=upcoming_deadlines,
        past_deadlines=past_deadlines,
        cert_statuses=CERT_STATUSES,
        deadline_categories=DEADLINE_CATEGORIES,
        access_matrix=ACCESS_MATRIX,
        audit_log_count=audit_log_count,
        active_lockouts=active_lockouts,
        recent_security_events=recent_security_events,
        db_host=db_host,
        tenant_schema=tenant_schema,
        pending_leaves=pending_leaves,
        pending_resignations=pending_resignations,
        pending_tickets=pending_tickets,
        overdue_onboardings=overdue_onboardings,
    )


@compliance_bp.route("/compliance/certifications/update", methods=["POST"])
@role_required("admin")
def update_certification():
    framework = (request.form.get("framework") or "").strip()
    status = (request.form.get("status") or "").strip()
    owner = (request.form.get("owner") or "").strip()
    last_reviewed = (request.form.get("last_reviewed") or "").strip() or None
    next_review = (request.form.get("next_review") or "").strip() or None
    notes = (request.form.get("notes") or "").strip()

    if not framework or status not in CERT_STATUSES:
        flash("Invalid certification update.", "error")
        return redirect("/compliance")

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE compliance_certifications SET status=%s, owner=%s, last_reviewed=%s, "
        "next_review=%s, notes=%s WHERE framework=%s",
        (status, owner or None, last_reviewed, next_review, notes or None, framework)
    )
    db.commit()
    cursor.close()
    db.close()

    _audit("compliance.certification_updated", table="compliance_certifications",
           record_id=framework, detail=f"{framework} set to '{status}'")
    flash(f"{framework} status updated to {status}.", "success")
    return redirect("/compliance")


@compliance_bp.route("/compliance/deadlines/add", methods=["POST"])
@role_required("admin")
def add_deadline():
    title = (request.form.get("title") or "").strip()
    jurisdiction = (request.form.get("jurisdiction") or "").strip()
    category = (request.form.get("category") or "Regulatory").strip()
    due_date = (request.form.get("due_date") or "").strip()

    if not title or not due_date or category not in DEADLINE_CATEGORIES:
        flash("Title, category, and due date are required.", "error")
        return redirect("/compliance")

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO compliance_deadlines (title, jurisdiction, category, due_date) "
        "VALUES (%s,%s,%s,%s) RETURNING id",
        (title, jurisdiction or None, category, due_date)
    )
    new_id = cursor.fetchone()[0]
    db.commit()
    cursor.close()
    db.close()

    _audit("compliance.deadline_added", table="compliance_deadlines",
           record_id=new_id, detail=f"Added deadline '{title}' due {due_date}")
    flash("Deadline added.", "success")
    return redirect("/compliance")


@compliance_bp.route("/compliance/deadlines/<int:deadline_id>/status", methods=["POST"])
@role_required("admin")
def update_deadline_status(deadline_id):
    status = (request.form.get("status") or "").strip()
    if status not in DEADLINE_STATUSES:
        flash("Invalid status.", "error")
        return redirect("/compliance")

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE compliance_deadlines SET status=%s WHERE id=%s", (status, deadline_id)
    )
    affected = cursor.rowcount
    db.commit()
    cursor.close()
    db.close()

    if affected:
        _audit("compliance.deadline_status_changed", table="compliance_deadlines",
               record_id=deadline_id, detail=f"Marked {status}")
        flash("Deadline updated.", "success")
    return redirect("/compliance")


@compliance_bp.route("/compliance/audit-logs")
@role_required("admin")
def audit_log_explorer():
    actor = (request.args.get("actor") or "").strip()
    action = (request.args.get("action") or "").strip()
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    per_page = 25

    where_clauses = []
    params = []
    if actor:
        where_clauses.append("actor ILIKE %s")
        params.append(f"%{actor}%")
    if action:
        where_clauses.append("action ILIKE %s")
        params.append(f"%{action}%")
    if date_from:
        where_clauses.append("created_at >= %s")
        params.append(date_from)
    if date_to:
        where_clauses.append("created_at < (%s::date + INTERVAL '1 day')")
        params.append(date_to)
    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    db = get_db_connection()
    cursor = db.cursor(buffered=True)

    cursor.execute(f"SELECT COUNT(*) FROM audit_logs {where_sql}", tuple(params))  # nosec B608
    total_count = cursor.fetchone()[0]
    total_pages = max(1, math.ceil(total_count / per_page))
    page = min(page, total_pages)
    offset = (page - 1) * per_page

    cursor.execute(
        f"SELECT id, actor, actor_type, action, target_table, target_id, detail, ip_address, created_at "  # nosec B608
        f"FROM audit_logs {where_sql} ORDER BY created_at DESC LIMIT %s OFFSET %s",
        tuple(params) + (per_page, offset)
    )
    logs = cursor.fetchall()

    cursor.execute("SELECT company_name FROM company_settings LIMIT 1")
    row = cursor.fetchone()
    co = type('Co', (), {'company_name': row[0] if row else 'My Company'})()

    cursor.close()
    db.close()

    pending_leaves = pending_resignations = pending_tickets = overdue_onboardings = 0

    return render_template(
        "compliance_audit_logs.html",
        co=co,
        active_nav="compliance",
        logs=logs,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        actor=actor,
        action=action,
        date_from=date_from,
        date_to=date_to,
        pending_leaves=pending_leaves,
        pending_resignations=pending_resignations,
        pending_tickets=pending_tickets,
        overdue_onboardings=overdue_onboardings,
    )
