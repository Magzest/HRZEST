# -*- coding: utf-8 -*-
"""Documents blueprint -- admin and employee document management."""
import os
import uuid
import datetime
from flask import Blueprint, request, session, redirect, render_template, flash, send_from_directory
from extensions import app
from database import get_db_connection
from werkzeug.utils import secure_filename
from utils.auth import admin_required, enforce_ownership
from utils.helpers import tpath, _audit, _validate_upload, _safe_referrer_redirect, get_pending_action_counts

documents_bp = Blueprint("documents", __name__)

_DOC_ALLOWED_EXT = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx'}


def _doc_admin_ctx(cursor):
    cursor.execute("SELECT company_name FROM company_settings LIMIT 1")
    row = cursor.fetchone()
    co = type('Co', (), {'company_name': row[0] if row else 'My Company'})()
    pending_leaves, pending_resignations, pending_tickets = get_pending_action_counts(cursor)
    return co, pending_leaves, pending_resignations, pending_tickets


@documents_bp.route("/documents")
@admin_required
def documents():
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    co, pending_leaves, pending_resignations, pending_tickets = _doc_admin_ctx(cursor)

    cursor.execute("SELECT employee_id, name FROM employees ORDER BY name")
    employees = cursor.fetchall()

    sel_emp = request.args.get('emp_id', '')
    sel_emp_name = ''

    if sel_emp:
        cursor.execute("SELECT name FROM employees WHERE employee_id=%s", (sel_emp,))
        r = cursor.fetchone()
        sel_emp_name = r[0] if r else sel_emp
        cursor.execute("""
            SELECT d.id, d.employee_id, e.name, d.doc_type, d.original_name, d.stored_name,
                   d.uploaded_by, d.uploaded_at, d.expiry_date
            FROM employee_documents d JOIN employees e ON e.employee_id=d.employee_id
            WHERE d.employee_id=%s ORDER BY d.uploaded_at DESC
        """, (sel_emp,))
    else:
        cursor.execute("""
            SELECT d.id, d.employee_id, e.name, d.doc_type, d.original_name, d.stored_name,
                   d.uploaded_by, d.uploaded_at, d.expiry_date
            FROM employee_documents d JOIN employees e ON e.employee_id=d.employee_id
            ORDER BY d.uploaded_at DESC
        """)
    docs = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template("documents.html",
                           co=co,
                           pending_leaves=pending_leaves,
                           pending_resignations=pending_resignations,
                           pending_tickets=pending_tickets,
                           employees=employees, docs=docs,
                           sel_emp=sel_emp, sel_emp_name=sel_emp_name,
                           today=datetime.date.today(),
                           )


@documents_bp.route("/upload_document", methods=["POST"])
@admin_required
def upload_document():
    emp_id = request.form.get('employee_id', '').strip()
    doc_type = request.form.get('doc_type', '').strip()
    f = request.files.get('document')
    if not emp_id or not doc_type or not f or not f.filename:
        flash("All fields required.", "danger")
        return redirect(tpath("/documents"))
    ok, err = _validate_upload(f, _DOC_ALLOWED_EXT)
    if not ok:
        flash(err, "danger")
        return redirect(tpath(f"/documents?emp_id={emp_id}"))
    folder = os.path.join(app.root_path, 'static', 'employee_docs', emp_id)
    os.makedirs(folder, exist_ok=True)
    orig_name = f.filename
    stored_name = str(uuid.uuid4()) + '_' + secure_filename(orig_name)
    f.save(os.path.join(folder, stored_name))
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    expiry_raw = request.form.get("expiry_date", "").strip()
    expiry_date = expiry_raw if expiry_raw else None
    cursor.execute(
        "INSERT INTO employee_documents (employee_id, doc_type, original_name, stored_name, uploaded_by, expiry_date) "
        "VALUES (%s,%s,%s,%s,'admin',%s)",
        (emp_id, doc_type, orig_name, stored_name, expiry_date)
    )
    db.commit()
    cursor.close()
    db.close()
    _audit("upload_document", "employee_documents", emp_id,
           f"doc_type={doc_type} file={orig_name} expiry={expiry_date or 'none'}")
    flash("Document uploaded successfully.", "success")
    raw_redirect = request.form.get('redirect_to') or f'/documents?emp_id={emp_id}'
    # Reject any redirect that leaves this origin (open-redirect prevention).
    # Only allow relative URLs (no scheme, no netloc).
    from urllib.parse import urlparse as _urlparse
    _p = _urlparse(raw_redirect)
    safe_redirect = raw_redirect if (not _p.scheme and not _p.netloc) else f'/documents?emp_id={emp_id}'
    return redirect(tpath(safe_redirect))


@documents_bp.route("/delete_document/<int:did>", methods=["POST"])
@admin_required
def delete_document(did):
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT employee_id, stored_name FROM employee_documents WHERE id=%s", (did,))
    row = cursor.fetchone()
    if row:
        emp_id, stored_name = row
        fpath = os.path.join(app.root_path, 'static', 'employee_docs', emp_id, stored_name)
        try:
            os.remove(fpath)
        except Exception:
            pass
        cursor.execute("DELETE FROM employee_documents WHERE id=%s", (did,))
        db.commit()
    cursor.close()
    db.close()
    flash("Document deleted.", "success")
    return redirect(_safe_referrer_redirect(request.referrer or "", "/documents"))


@documents_bp.route("/download_document/<int:did>")
def download_document(did):
    is_admin = session.get("admin_logged_in")
    emp_session = session.get("employee_id")
    if not is_admin and not emp_session:
        return redirect(tpath("/login"))
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT employee_id, original_name, stored_name FROM employee_documents WHERE id=%s", (did,))
    row = cursor.fetchone()
    cursor.close()
    db.close()
    if not row:
        flash("Document not found.", "danger")
        return redirect(tpath("/documents"))
    doc_emp_id, original_name, stored_name = row
    # This check existed before but never logged a denial -- a real IDOR
    # probe against someone else's payslip/ID-document upload would have
    # been invisible. enforce_ownership() logs it at ERROR, which feeds the
    # same alerting webhook the payslip endpoint already uses.
    if not enforce_ownership(doc_emp_id, "document", did):
        flash("Access denied.", "danger")
        return redirect(tpath("/employee_portal"))
    folder = os.path.join(app.root_path, 'static', 'employee_docs', doc_emp_id)
    return send_from_directory(folder, stored_name, as_attachment=True, download_name=original_name)


@documents_bp.route("/upload_my_document", methods=["POST"])
def upload_my_document():
    emp_id = session.get("employee_id")
    if not emp_id:
        return redirect(tpath("/login"))
    doc_type = request.form.get('doc_type', '').strip()
    f = request.files.get('document')
    if not doc_type or not f or not f.filename:
        flash("All fields required.", "danger")
        return redirect(tpath("/employee_portal"))
    ok, err = _validate_upload(f, _DOC_ALLOWED_EXT)
    if not ok:
        flash(err, "danger")
        return redirect(tpath("/employee_portal"))
    folder = os.path.join(app.root_path, 'static', 'employee_docs', emp_id)
    os.makedirs(folder, exist_ok=True)
    orig_name = f.filename
    stored_name = str(uuid.uuid4()) + '_' + secure_filename(orig_name)
    f.save(os.path.join(folder, stored_name))
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute(
        "INSERT INTO employee_documents (employee_id, doc_type, original_name, stored_name, uploaded_by) VALUES (%s,%s,%s,%s,'employee')",
        (emp_id, doc_type, orig_name, stored_name)
    )
    db.commit()
    cursor.close()
    db.close()
    flash("Document uploaded successfully.", "success")
    return redirect(tpath("/employee_portal#documents"))


@documents_bp.route("/delete_my_document/<int:did>", methods=["POST"])
def delete_my_document(did):
    emp_id = session.get("employee_id")
    if not emp_id:
        return redirect(tpath("/login"))
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT employee_id, stored_name FROM employee_documents WHERE id=%s AND employee_id=%s", (did, emp_id))
    row = cursor.fetchone()
    if row:
        fpath = os.path.join(app.root_path, 'static', 'employee_docs', emp_id, row[1])
        try:
            os.remove(fpath)
        except Exception:
            pass
        cursor.execute("DELETE FROM employee_documents WHERE id=%s AND employee_id=%s", (did, emp_id))
        db.commit()
    cursor.close()
    db.close()
    flash("Document deleted.", "success")
    return redirect(tpath("/employee_portal#documents"))
