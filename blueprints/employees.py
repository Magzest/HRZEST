# -*- coding: utf-8 -*-
"""Employees blueprint -- CRUD, photos, QR codes, ID cards."""
import os
import json
import datetime
import secrets
import psycopg2
from flask import (
    Blueprint, request, session, redirect, jsonify, render_template, flash, g,
)

from extensions import app, app_log, limiter, log_security_event
from database import get_db_connection, transaction
from qr_generator import generate_qr
from utils.auth import admin_required, generate_password_hash, api_required, role_required, api_role_required
from utils.helpers import (
    tpath, _audit, _db, _validate_image_file, decrypt_pii, decrypt_pii_date, encrypt_pii, validate_emp_id,
    validate_employee_email_domain, get_company_settings, employee_login_url,
)
from utils.dlp import has_pii_clearance, mask_tail
from utils.email_utils import get_email_config, send_email_smtp
from utils.attendance_utils import _td_to_time
from utils.leave_utils import assign_leave_balances_for_employee
from utils.face_utils import face_recognition, _face_recognition_available
from utils.webauthn_utils import _enroll_fingerprint_from_form

employees_bp = Blueprint("employees", __name__)

UPLOAD_FOLDER = app.config["UPLOAD_FOLDER"]


@employees_bp.route("/admin_action", methods=["POST"])
@role_required("admin")
@limiter.limit("20 per minute")
def admin_action():
    action = request.form.get("action")
    db = get_db_connection()
    cursor = db.cursor(buffered=True)

    if action == "register":
        try:
            name = request.form["name"].strip()
            emp_id = request.form["emp_id"].strip()
            email = request.form.get("email", "").strip() or None
            role = request.form.get("role", "").strip() or None
            date_of_joining = request.form.get("date_of_joining", "").strip() or None
            work_mode = request.form.get("work_mode", "office").strip() or "office"
            work_lat_raw = request.form.get("work_lat", "").strip()
            work_lon_raw = request.form.get("work_lon", "").strip()
            work_lat = float(work_lat_raw) if work_lat_raw else None
            work_lon = float(work_lon_raw) if work_lon_raw else None
            company_id_raw = request.form.get("company_id", "").strip()
            company_id = int(company_id_raw) if company_id_raw.isdigit() else None
            # Extended fields
            department = request.form.get("department", "").strip() or None
            # phone (like name/email) is deliberately left plaintext, unlike
            # every other PII field below -- it backs admin search (ILIKE),
            # alphabetical employee listings, and ticket/leave search joins;
            # encrypting it would break those with no equivalent replacement
            # (Fernet ciphertext isn't ILIKE-able or sortable).
            phone = request.form.get("phone", "").strip() or None
            manager_id = request.form.get("manager_id", "").strip() or None
            manager_name = request.form.get("manager_name", "").strip() or None
            salary_per_day_raw = request.form.get("salary_per_day", "").strip()
            salary_per_day = float(salary_per_day_raw) if salary_per_day_raw else None
            gender = encrypt_pii(request.form.get("gender", "").strip() or None)
            dob_raw = request.form.get("dob", "").strip()
            dob = encrypt_pii(dob_raw) if dob_raw else None
            blood_group = encrypt_pii(request.form.get("blood_group", "").strip() or None)
            address = encrypt_pii(request.form.get("address", "").strip() or None)
            city = encrypt_pii(request.form.get("city", "").strip() or None)
            state = encrypt_pii(request.form.get("state", "").strip() or None)
            pincode = encrypt_pii(request.form.get("pincode", "").strip() or None)
            ec_name = encrypt_pii(request.form.get("emergency_contact_name", "").strip() or None)
            ec_phone = encrypt_pii(request.form.get("emergency_contact_phone", "").strip() or None)
            ec_relation = encrypt_pii(request.form.get("emergency_contact_relation", "").strip() or None)
            aadhar = encrypt_pii(request.form.get("aadhar_number", "").strip() or None)
            pan = encrypt_pii(request.form.get("pan_number", "").strip().upper() or None)
            bank_name = encrypt_pii(request.form.get("bank_name", "").strip() or None)
            bank_account = encrypt_pii(request.form.get("bank_account", "").strip() or None)
            bank_ifsc = encrypt_pii(request.form.get("bank_ifsc", "").strip().upper() or None)
            uan = encrypt_pii(request.form.get("uan_number", "").strip() or None)
            file = request.files["face"]
        except (KeyError, ValueError) as _e:
            cursor.close()
            db.close()
            flash(f"Missing or invalid field in registration form: {_e}", "error")
            return redirect(tpath("/admin"))
        if not name:
            cursor.close()
            db.close()
            flash("Full name is required.", "error")
            return redirect(tpath("/admin"))
        _domain_error = validate_employee_email_domain(email)
        if _domain_error:
            cursor.close()
            db.close()
            flash(_domain_error, "error")
            return redirect(tpath("/admin"))
        # Plaintext fields still bounded by a VARCHAR column width (the PII
        # fields below this point are Fernet-encrypted into TEXT columns, so
        # they can't overflow) -- checked here with a clear message instead of
        # letting an oversized value hit psycopg2.errors.StringDataRightTruncation,
        # an unhandled DataError that would otherwise fall through to the
        # generic 500 page without cleaning up the already-uploaded photo.
        _length_limits = (
            (name, "Full name", 100), (email, "Email", 150), (role, "Role", 100),
            (phone, "Phone", 20), (department, "Department", 100),
            (manager_id, "Manager ID", 20), (manager_name, "Manager name", 150),
        )
        for _value, _label, _max_len in _length_limits:
            if _value and len(_value) > _max_len:
                cursor.close()
                db.close()
                flash(f"{_label} is too long (max {_max_len} characters).", "error")
                return redirect(tpath("/admin"))
        if not validate_emp_id(emp_id):
            cursor.close()
            db.close()
            flash("Employee ID may only contain letters, digits, hyphens and underscores.", "error")
            return redirect(tpath("/admin"))
        # Auto-increment emp_id if it's already taken
        cursor.execute("SELECT 1 FROM employees WHERE employee_id = %s", (emp_id,))
        if cursor.fetchone():
            prefix = ''.join(c for c in emp_id if not c.isdigit())
            if prefix:
                original_suffix = emp_id[len(prefix):]
                # Preserve the width the admin actually typed (e.g. "TST001"
                # -> "TST002") instead of always forcing 3 digits, which
                # previously turned a collision on a 1-digit suffix like
                # "EMP9" into the inconsistent "EMP010".
                pad_width = len(original_suffix) if original_suffix.isdigit() else 3
                cursor.execute(
                    "SELECT employee_id FROM employees WHERE employee_id LIKE %s",
                    (prefix + "%",)
                )
                max_seq = 0
                for (eid,) in cursor.fetchall():
                    sfx = eid[len(prefix):]
                    if sfx.isdigit():
                        max_seq = max(max_seq, int(sfx))
                emp_id = f"{prefix}{max_seq + 1:0{pad_width}d}"
        _img_ok, _img_err = _validate_image_file(file)
        if not _img_ok:
            flash(_img_err, "error")
            cursor.close()
            db.close()
            return redirect(tpath("/admin"))
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], emp_id + ".jpg")
        file.save(filepath)

        # Validate that the uploaded photo contains a detectable face
        if _face_recognition_available:
            test_img = face_recognition.load_image_file(filepath)
            if not face_recognition.face_encodings(test_img):
                os.remove(filepath)
                flash("No face detected in the uploaded photo. Please upload a clear, well-lit front-facing photo.", "error")
                cursor.close()
                db.close()
                return redirect(tpath("/admin"))

        qr_path = generate_qr(emp_id)
        auto_pass = secrets.token_urlsafe(8)   # e.g. "aB3xQ7mR"
        hashed_pwd = generate_password_hash(auto_pass)
        try:
            cursor.execute(
                "INSERT INTO employees (name, employee_id, email, role, face_image, qr_code, password, "
                "date_of_joining, work_mode, work_lat, work_lon, company_id, "
                "department, phone, manager_id, manager_name, "
                "gender, dob, blood_group, "
                "address, city, state, pincode, "
                "emergency_contact_name, emergency_contact_phone, emergency_contact_relation, "
                "aadhar_number, pan_number, bank_name, bank_account, bank_ifsc, uan_number, "
                "force_pin_change) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
                "%s,%s,%s,%s,"
                "%s,%s,%s,"
                "%s,%s,%s,%s,"
                "%s,%s,%s,"
                "%s,%s,%s,%s,%s,%s,1)",
                (name, emp_id, email, role, filepath, qr_path, hashed_pwd,
                 date_of_joining, work_mode, work_lat, work_lon, company_id,
                 department, phone, manager_id, manager_name,
                 gender, dob, blood_group,
                 address, city, state, pincode,
                 ec_name, ec_phone, ec_relation,
                 aadhar, pan, bank_name, bank_account, bank_ifsc, uan)
            )
            db.commit()
            if salary_per_day is not None:
                cursor.execute(
                    "INSERT INTO salary_config (employee_id, salary_per_day) VALUES (%s,%s) "
                    "ON CONFLICT (employee_id) DO UPDATE SET salary_per_day=%s",
                    (emp_id, salary_per_day, salary_per_day)
                )
                db.commit()
            _enroll_fingerprint_from_form(emp_id, cursor, db)
            assign_leave_balances_for_employee(cursor, emp_id)
            db.commit()
            flash(f"✅ Employee '{name}' registered! ID: {emp_id} | Password: {auto_pass}", "success")
            # Send welcome email with credentials
            if not email:
                flash("⚠️ No email address provided -- credentials email not sent. Share them manually.", "error")
            else:
                _ecfg = get_email_config()
                if not _ecfg:
                    flash("⚠️ SMTP not configured -- credentials email not sent. Go to Email Settings to set it up.", "error")
                else:
                    _login_url = employee_login_url()
                    _welcome_html = f"""
<div style="font-family:'Segoe UI',sans-serif;max-width:520px;margin:0 auto;background:#f8fafc;padding:32px 24px;border-radius:16px;">
  <div style="background:linear-gradient(135deg,#1e3a8a,#2563eb);border-radius:12px;padding:28px 24px;text-align:center;margin-bottom:24px;">
    <div style="font-size:36px;margin-bottom:8px;">👋</div>
    <h1 style="color:#fff;font-size:22px;margin:0;">Welcome to the Team!</h1>
    <p style="color:rgba(255,255,255,0.8);font-size:14px;margin:6px 0 0;">Your employee account has been created</p>
  </div>
  <p style="color:#1e293b;font-size:15px;margin-bottom:20px;">Hi <strong>{name}</strong>, here are your login credentials for the Attendance Portal:</p>
  <div style="background:#fff;border:1px solid #dbeafe;border-radius:12px;padding:20px 24px;margin-bottom:20px;">
    <table style="width:100%;font-size:14px;border-collapse:collapse;">
      <tr>
        <td style="color:#64748b;padding:8px 0;border-bottom:1px solid #f1f5f9;font-weight:600;width:40%;">Employee ID</td>
        <td style="color:#1e293b;padding:8px 0;border-bottom:1px solid #f1f5f9;font-weight:700;">{emp_id}</td>
      </tr>
      <tr>
        <td style="color:#64748b;padding:8px 0;font-weight:600;">Password</td>
        <td style="color:#1e293b;padding:8px 0;font-weight:700;font-family:monospace;font-size:15px;">{auto_pass}</td>
      </tr>
    </table>
  </div>
  <a href="{_login_url}" style="display:block;text-align:center;padding:14px 24px;background:#1e3a8a;color:#fff;border-radius:10px;text-decoration:none;font-size:15px;font-weight:700;margin-bottom:16px;">Go to Login Page</a>
  <p style="color:#94a3b8;font-size:11px;text-align:center;margin:-8px 0 20px;word-break:break-all;">{_login_url}</p>
  <div style="background:#fffbeb;border:1px solid #fde68a;border-radius:10px;padding:12px 16px;font-size:13px;color:#92400e;margin-bottom:20px;">
    🔒 Please change your password after your first login for security.
  </div>
  <p style="color:#64748b;font-size:12px;text-align:center;margin:0;">This is an automated message -- please do not reply.</p>
</div>"""
                    try:
                        send_email_smtp(email, f"Welcome {name} -- Your Login Credentials", _welcome_html, _ecfg)
                        flash(f"📧 Credentials email sent to {email}", "success")
                    except Exception as _mail_err:
                        flash(f"⚠️ Email delivery failed: {_mail_err}. Share credentials manually.", "error")
        except psycopg2.IntegrityError:
            db.rollback()
            os.remove(filepath)
            flash(f"Employee ID '{emp_id}' already exists. Please use a different ID.", "error")
            cursor.close()
            db.close()
            return redirect(tpath("/admin"))

    elif action == "update_face":
        emp_id = request.form["emp_id"]
        file = request.files["face"]
        cursor.execute("SELECT name FROM employees WHERE employee_id=%s", (emp_id,))
        row = cursor.fetchone()
        if not row:
            flash(f"Employee ID '{emp_id}' not found.", "error")
            cursor.close()
            db.close()
            return redirect(tpath("/admin"))
        name = row[0]
        _img_ok, _img_err = _validate_image_file(file)
        if not _img_ok:
            flash(_img_err, "error")
            cursor.close()
            db.close()
            return redirect(tpath("/admin"))
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], emp_id + ".jpg")
        file.save(filepath)
        if _face_recognition_available:
            test_img = face_recognition.load_image_file(filepath)
            if not face_recognition.face_encodings(test_img):
                os.remove(filepath)
                flash("No face detected in the uploaded photo. Please upload a clear, well-lit front-facing photo.", "error")
                cursor.close()
                db.close()
                return redirect(tpath("/admin"))
        cursor.execute("UPDATE employees SET face_image=%s WHERE employee_id=%s", (filepath, emp_id))
        db.commit()
        flash(f"Face photo updated successfully for '{name}' (ID: {emp_id}).", "success")

    elif action == "reset_password":
        emp_id = request.form.get("emp_id", "").strip()
        cursor.execute("SELECT name FROM employees WHERE employee_id=%s", (emp_id,))
        row = cursor.fetchone()
        if not row:
            flash(f"Employee ID '{emp_id}' not found.", "error")
        else:
            cursor.execute(
                "UPDATE employees SET password=%s WHERE employee_id=%s",
                (generate_password_hash(emp_id), emp_id)
            )
            db.commit()
            flash(
                f"Password reset for '{row[0]}' ({emp_id}). They can now login using their Employee ID as the password.", "success")

    elif action == "holiday":
        cursor.execute(
            "INSERT INTO holidays (date, name) VALUES (%s,%s)",
            (request.form["date"], request.form["holiday_name"])
        )
        db.commit()

    elif action == "salary":
        emp_id = request.form["emp_id"]
        salary = request.form["salary"]
        cursor.execute("SELECT 1 FROM salary_config WHERE employee_id=%s", (emp_id,))
        if cursor.fetchone():
            cursor.execute(
                "UPDATE salary_config SET salary_per_day=%s WHERE employee_id=%s",
                (salary, emp_id)
            )
        else:
            cursor.execute(
                "INSERT INTO salary_config (employee_id, salary_per_day) VALUES (%s,%s)",
                (emp_id, salary)
            )
        db.commit()

    cursor.close()
    db.close()
    return redirect(tpath("/admin"))


@employees_bp.route("/delete_employee/<emp_id>", methods=["POST"])
@role_required("admin")
@limiter.limit("10 per minute")
def delete_employee(emp_id):
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT face_image, qr_code FROM employees WHERE employee_id=%s", (emp_id,))
    row = cursor.fetchone()
    if row:
        try:
            with transaction(db):
                cursor.execute("DELETE FROM attendance WHERE employee_id=%s", (emp_id,))
                cursor.execute("DELETE FROM salary_config WHERE employee_id=%s", (emp_id,))
                cursor.execute("DELETE FROM leave_requests WHERE employee_id=%s", (emp_id,))
                cursor.execute("DELETE FROM resignation_requests WHERE employee_id=%s", (emp_id,))
                cursor.execute("DELETE FROM employees WHERE employee_id=%s", (emp_id,))
        except Exception:
            cursor.close()
            db.close()
            app_log.warning("delete_employee failed mid-transaction for %s, rolled back", emp_id)
            flash(f"Failed to delete employee '{emp_id}'; no changes were made.", "error")
            return redirect(tpath("/employees"))
        for path in row:
            if path and os.path.exists(path):
                os.remove(path)
        _audit("delete_employee", "employees", emp_id, f"Employee {emp_id} permanently deleted")
        flash(f"Employee '{emp_id}' deleted successfully.", "success")
    else:
        flash(f"Employee '{emp_id}' not found.", "error")
    cursor.close()
    db.close()
    return redirect(tpath("/employees"))


@employees_bp.route("/edit_employee/<emp_id>", methods=["GET"])
@admin_required
def edit_employee_page(emp_id):
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute(
        "SELECT employee_id, name, email, role FROM employees WHERE employee_id=%s", (emp_id,)
    )
    emp = cursor.fetchone()
    cursor.close()
    db.close()
    if not emp:
        return "Employee not found", 404
    return render_template("edit_employee.html", emp=emp, active_nav="employees")


@employees_bp.route("/employee_profile/<emp_id>")
@admin_required
def employee_profile(emp_id):
    today = datetime.date.today()
    with _db() as (cursor, db):
        cursor.execute("""
            SELECT employee_id, name, email, role, phone, gender, dob, blood_group,
                   date_of_joining, department, manager_name, work_mode,
                   address, city, state, pincode,
                   emergency_contact_name, emergency_contact_phone, emergency_contact_relation,
                   aadhar_number, pan_number, bank_name, bank_account, bank_ifsc, uan_number,
                   about_me, face_image, shift_id
            FROM employees WHERE employee_id=%s
        """, (emp_id,))
        emp = cursor.fetchone()
        if not emp:
            return "Employee not found", 404
        # Decrypt PII: [5]=gender [7]=blood_group [12]=address [13]=city
        # [14]=state [15]=pincode [16]=ec_name [17]=ec_phone [18]=ec_relation
        # [19]=aadhar_number [20]=pan_number [21]=bank_name [22]=bank_account
        # [23]=bank_ifsc [24]=uan_number. [6]=dob is handled separately since
        # the template calls .strftime() on it (see decrypt_pii_date).
        emp = list(emp)
        for _pii_idx in (5, 7, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24):
            if _pii_idx < len(emp):
                emp[_pii_idx] = decrypt_pii(emp[_pii_idx])
        emp[6] = decrypt_pii_date(emp[6])

        # DLP: aadhar/pan/bank_account/uan are only shown unmasked to the
        # finance/HR-clearance tier (admin_role=="admin") -- mirrors the
        # restriction payroll.py's view_payslip already enforces for
        # payslips. manager/soc_analyst still get the rest of the profile.
        if not has_pii_clearance():
            emp[19] = mask_tail(emp[19])  # aadhar_number
            emp[20] = mask_tail(emp[20])  # pan_number
            emp[22] = mask_tail(emp[22])  # bank_account
            emp[24] = mask_tail(emp[24])  # uan_number
        else:
            log_security_event("data.reveal", "Admin viewed unmasked PII on employee profile",
                               level="WARNING", identifier=session.get("admin_username"),
                               resource_type="employee_profile", resource_id=emp_id)

        # Attendance this month
        cursor.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status IN ('Present','Late Login') THEN 1 ELSE 0 END) AS present,
                SUM(CASE WHEN status='Absent' THEN 1 ELSE 0 END) AS absent,
                SUM(CASE WHEN status='Late Login' THEN 1 ELSE 0 END) AS late,
                SUM(CASE WHEN attendance_type='Half Day' THEN 1 ELSE 0 END) AS halfday
            FROM attendance
            WHERE employee_id=%s AND EXTRACT(MONTH FROM date)=%s AND EXTRACT(YEAR FROM date)=%s
        """, (emp_id, today.month, today.year))
        att = cursor.fetchone()

        # Last 5 attendance records
        cursor.execute("""
            SELECT date, login_time, logout_time, status, attendance_type
            FROM attendance WHERE employee_id=%s
            ORDER BY date DESC LIMIT 5
        """, (emp_id,))
        recent_att = cursor.fetchall()

        # Leave summary this year
        cursor.execute("""
            SELECT lt.name, COUNT(*) as cnt
            FROM leave_requests lr
            LEFT JOIN leave_types lt ON lr.leave_type_id = lt.id
            WHERE lr.employee_id=%s AND lr.status='Approved'
              AND EXTRACT(YEAR FROM lr.leave_date)=%s
            GROUP BY lt.name
        """, (emp_id, today.year))
        leave_used = cursor.fetchall()

        # Pending leaves
        cursor.execute("""
            SELECT COUNT(*) FROM leave_requests
            WHERE employee_id=%s AND status='Pending'
        """, (emp_id,))
        pending_leaves = cursor.fetchone()[0]

        # Salary config
        cursor.execute("SELECT salary_per_day FROM salary_config WHERE employee_id=%s", (emp_id,))
        sal_row = cursor.fetchone()
        salary_per_day = sal_row[0] if sal_row else None
        salary_hidden = bool(salary_per_day) and not has_pii_clearance()
        if salary_hidden:
            salary_per_day = None

        # Open tickets
        cursor.execute("""
            SELECT COUNT(*) FROM tickets WHERE employee_id=%s AND status IN ('Open','In Progress')
        """, (emp_id,))
        open_tickets = cursor.fetchone()[0]

        # Shift info
        shift_name = None
        if emp[27]:
            cursor.execute("SELECT name, start_time, end_time FROM shifts WHERE id=%s", (emp[27],))
            sh = cursor.fetchone()
            if sh:
                shift_name = f"{sh[0]} ({sh[1]} – {sh[2]})"

    return render_template("employee_profile.html",
                           emp=emp,
                           att=att,
                           recent_att=recent_att,
                           leave_used=leave_used,
                           pending_leaves=pending_leaves,
                           salary_per_day=salary_per_day,
                           salary_hidden=salary_hidden,
                           open_tickets=open_tickets,
                           shift_name=shift_name,
                           today=today,
                           active_nav="employees",
                           )


@employees_bp.route("/edit_employee", methods=["POST"])
@admin_required
def edit_employee():
    emp_id = request.form["emp_id"].strip()
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip() or None
    role = request.form.get("role", "").strip() or None
    date_of_joining = request.form.get("date_of_joining", "").strip() or None
    department = request.form.get("department", "").strip() or None
    manager_name = request.form.get("manager_name", "").strip() or None
    manager_id = request.form.get("manager_id", "").strip() or None
    # phone deliberately plaintext -- see the matching comment in add_employee().
    phone = request.form.get("phone", "").strip() or None
    gender = encrypt_pii(request.form.get("gender", "").strip() or None)
    dob = encrypt_pii(request.form.get("dob", "").strip() or None)
    blood_group = encrypt_pii(request.form.get("blood_group", "").strip() or None)
    shift_id_raw = request.form.get("shift_id", "").strip()
    shift_id = int(shift_id_raw) if shift_id_raw else None
    address = encrypt_pii(request.form.get("address", "").strip() or None)
    city = encrypt_pii(request.form.get("city", "").strip() or None)
    state = encrypt_pii(request.form.get("state", "").strip() or None)
    pincode = encrypt_pii(request.form.get("pincode", "").strip() or None)
    ec_name = encrypt_pii(request.form.get("ec_name", "").strip() or None)
    ec_phone = encrypt_pii(request.form.get("ec_phone", "").strip() or None)
    ec_rel = encrypt_pii(request.form.get("ec_rel", "").strip() or None)
    work_mode = request.form.get("work_mode", "office").strip() or "office"
    work_lat_raw = request.form.get("work_lat", "").strip()
    work_lon_raw = request.form.get("work_lon", "").strip()
    work_lat = float(work_lat_raw) if work_lat_raw else None
    work_lon = float(work_lon_raw) if work_lon_raw else None

    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute(
        "UPDATE employees SET name=%s, email=%s, role=%s, date_of_joining=%s, "
        "department=%s, manager_name=%s, manager_id=%s, phone=%s, gender=%s, dob=%s, blood_group=%s, "
        "shift_id=%s, address=%s, city=%s, state=%s, pincode=%s, "
        "emergency_contact_name=%s, emergency_contact_phone=%s, emergency_contact_relation=%s, "
        "work_mode=%s, work_lat=%s, work_lon=%s "
        "WHERE employee_id=%s",
        (name, email, role, date_of_joining, department, manager_name, manager_id,
         phone, gender, dob, blood_group, shift_id,
         address, city, state, pincode,
         ec_name, ec_phone, ec_rel,
         work_mode, work_lat, work_lon, emp_id)
    )
    db.commit()
    cursor.close()
    db.close()
    flash(f"Employee '{emp_id}' updated successfully.", "success")
    return redirect(tpath("/employees"))


@employees_bp.route("/api/employee_info/<emp_id>")
@admin_required
def api_employee_info(emp_id):
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute(
        "SELECT employee_id, name, role, email, date_of_joining, "
        "work_mode, work_lat, work_lon, department, manager_name, face_image, qr_code, "
        "phone, gender, dob, blood_group, shift_id, "
        "address, city, state, pincode, "
        "emergency_contact_name, emergency_contact_phone, emergency_contact_relation, "
        "COALESCE(manager_id,'') "
        "FROM employees WHERE employee_id=%s", (emp_id,)
    )
    row = cursor.fetchone()
    cursor.close()
    db.close()
    if not row:
        return jsonify({"error": "not found"}), 404
    (eid, name, role, email, doj, wm, wlat, wlon, dept, mgr, face_image, qr_code,
     phone, gender, dob, blood_group, shift_id,
     address, city, state, pincode,
     ec_name, ec_phone, ec_rel, mgr_id) = row
    dob_date = decrypt_pii_date(dob)
    return jsonify({
        "emp_id": eid,
        "name": name or "",
        "role": role or "",
        "email": email or "",
        "doj": doj.strftime("%Y-%m-%d") if doj else "",
        "work_mode": wm or "office",
        "work_lat": str(wlat) if wlat else "",
        "work_lon": str(wlon) if wlon else "",
        "department": dept or "",
        "manager_name": mgr or "",
        "manager_id": mgr_id or "",
        "has_photo": bool(face_image and os.path.exists(face_image)),
        "has_qr": bool(qr_code and os.path.exists(qr_code)),
        "phone": phone or "",
        "gender": decrypt_pii(gender) or "",
        "dob": dob_date.strftime("%Y-%m-%d") if dob_date else "",
        "blood_group": decrypt_pii(blood_group) or "",
        "shift_id": shift_id or "",
        "address": decrypt_pii(address) or "",
        "city": decrypt_pii(city) or "",
        "state": decrypt_pii(state) or "",
        "pincode": decrypt_pii(pincode) or "",
        "ec_name": decrypt_pii(ec_name) or "",
        "ec_phone": decrypt_pii(ec_phone) or "",
        "ec_rel": decrypt_pii(ec_rel) or "",
    })


@employees_bp.route("/employees")
@admin_required
def view_employees():
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    active_cid = session.get("active_company_id")
    if active_cid:
        cursor.execute("""
            SELECT e.employee_id, e.name, e.role, e.email, e.date_of_joining,
                   COUNT(a.date)  AS total_days,
                   MAX(a.date)    AS last_seen,
                   e.work_mode, e.work_lat, e.work_lon,
                   e.face_image, e.qr_code,
                   e.department, e.phone, e.gender,
                   s.name AS shift_name, e.shift_id
            FROM employees e
            LEFT JOIN attendance a ON e.employee_id = a.employee_id
            LEFT JOIN shifts     s ON e.shift_id = s.id
            WHERE e.company_id = %s
            GROUP BY e.employee_id, e.name, e.role, e.email, e.date_of_joining,
                     e.work_mode, e.work_lat, e.work_lon, e.face_image, e.qr_code,
                     e.department, e.phone, e.gender, s.name, e.shift_id
            ORDER BY e.name
            LIMIT 500
        """, (active_cid,))
    else:
        cursor.execute("""
            SELECT e.employee_id, e.name, e.role, e.email, e.date_of_joining,
                   COUNT(a.date)  AS total_days,
                   MAX(a.date)    AS last_seen,
                   e.work_mode, e.work_lat, e.work_lon,
                   e.face_image, e.qr_code,
                   e.department, e.phone, e.gender,
                   s.name AS shift_name, e.shift_id
            FROM employees e
            LEFT JOIN attendance a ON e.employee_id = a.employee_id
            LEFT JOIN shifts     s ON e.shift_id = s.id
            GROUP BY e.employee_id, e.name, e.role, e.email, e.date_of_joining,
                     e.work_mode, e.work_lat, e.work_lon, e.face_image, e.qr_code,
                     e.department, e.phone, e.gender, s.name, e.shift_id
            ORDER BY e.name
            LIMIT 500
        """)
    employees_raw = cursor.fetchall()

    cursor.execute("SELECT DISTINCT employee_id FROM resignation_requests WHERE status='Accepted'")
    resigned_set = {r[0] for r in cursor.fetchall()}
    cursor.execute(
        "SELECT DISTINCT employee_id FROM leave_requests "
        "WHERE status='Approved' AND leave_date=CURRENT_DATE"
    )
    on_leave_set = {r[0] for r in cursor.fetchall()}

    employees = []
    for row in employees_raw:
        eid = row[0]
        if eid in resigned_set:
            emp_status = "Resigned"
        elif eid in on_leave_set:
            emp_status = "On Leave"
        else:
            emp_status = "Active"
        row = row[:14] + (decrypt_pii(row[14]),) + row[15:]  # [14]=gender
        employees.append(row + (emp_status,))

    total = len(employees)
    active_count = sum(1 for e in employees if e[-1] == "Active")
    on_leave_count = sum(1 for e in employees if e[-1] == "On Leave")
    resigned_count = sum(1 for e in employees if e[-1] == "Resigned")

    # Full shift details for Schedule tab
    cursor.execute("SELECT id, name, start_time, half_time, end_time FROM shifts ORDER BY start_time")
    shift_full = []
    for sid, sname, st, ht, et in cursor.fetchall():
        shift_full.append({
            "id": sid, "name": sname,
            "start": _td_to_time(st).strftime("%H:%M") if st else "--",
            "half": _td_to_time(ht).strftime("%H:%M") if ht else "--",
            "end": _td_to_time(et).strftime("%H:%M") if et else "--",
        })
    # Simple (id, name) list for dropdowns
    cursor.execute("SELECT id, name FROM shifts ORDER BY name")
    shifts = cursor.fetchall()

    # Breaks list
    cursor.execute("SELECT id, break_name, break_time, duration_minutes, is_active FROM break_config ORDER BY break_time")
    breaks_raw = cursor.fetchall()
    breaks_list = []
    for bid, bname, bt, dur, bactive in breaks_raw:
        def _fmt_bt(v):
            if v is None:
                return "--"
            if isinstance(v, datetime.timedelta):
                h, m = divmod(int(v.total_seconds()) // 60, 60)
                return "%02d:%02d" % (h, m)
            return str(v)[:5]
        breaks_list.append({"id": bid, "name": bname, "time": _fmt_bt(bt), "duration": dur, "active": bactive})

    cursor.execute(
        "SELECT department FROM employees "
        "WHERE department IS NOT NULL AND department != '' "
        "GROUP BY department ORDER BY MIN(id) ASC"
    )
    departments = [r[0] for r in cursor.fetchall()]

    cursor.execute("SELECT COUNT(*) FROM leave_requests WHERE status='Pending'")
    pending_leaves = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM resignation_requests WHERE status='Pending'")
    pending_resignations = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('Open','In Progress')")
    pending_tickets = cursor.fetchone()[0]
    cursor.execute("SELECT id, name FROM companies ORDER BY name")
    companies = cursor.fetchall()
    cursor.execute("SELECT id, name FROM onboarding_templates WHERE is_active=1 ORDER BY name")
    onboarding_templates = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template("employees.html",
                           employees=employees,
                           shifts=shifts,
                           shift_full=shift_full,
                           breaks_list=breaks_list,
                           departments=departments,
                           companies=companies,
                           onboarding_templates=onboarding_templates,
                           total=total,
                           active_count=active_count,
                           on_leave_count=on_leave_count,
                           resigned_count=resigned_count,
                           pending_leaves=pending_leaves,
                           pending_resignations=pending_resignations,
                           pending_tickets=pending_tickets,
                           active_nav="employees",
                           email_domain=get_company_settings().get("email_domain"),
                           )


@employees_bp.route("/api/departments", methods=["GET"])
@api_required
def api_departments():
    """API endpoint to fetch real departments and headcounts from database."""
    with _db() as (cursor, conn):
        cursor.execute("""
            SELECT department, COUNT(*) AS count
            FROM employees
            WHERE department IS NOT NULL AND department != '' AND is_active = 1
            GROUP BY department
            ORDER BY count DESC
        """)
        rows = cursor.fetchall()
        depts = []
        for r in rows:
            depts.append({
                "name": r[0],
                "count": r[1]
            })
        return jsonify({"ok": True, "departments": depts})


@employees_bp.route("/employee_detail/<emp_id>")
@admin_required
def employee_detail(emp_id):
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("""
        SELECT e.employee_id, e.name, e.role, e.email, e.date_of_joining,
               e.work_mode, e.work_lat, e.work_lon,
               e.face_image, e.qr_code,
               e.department, e.phone, e.gender, e.dob, e.blood_group,
               e.shift_id, e.manager_name,
               e.address, e.city, e.state, e.pincode,
               e.emergency_contact_name, e.emergency_contact_phone, e.emergency_contact_relation,
               e.aadhar_number, e.pan_number,
               e.bank_name, e.bank_account, e.bank_ifsc, e.uan_number,
               s.name AS shift_name,
               COUNT(a.date)  AS total_days,
               MAX(a.date)    AS last_seen,
               SUM(CASE WHEN a.attendance_type IN ('Present','Full Day','Approved Leave') OR (a.login_time IS NOT NULL AND a.attendance_type IS NULL) THEN 1 ELSE 0 END) AS full_days,
               SUM(CASE WHEN a.attendance_type='Half Day' THEN 1 ELSE 0 END) AS half_days,
               SUM(CASE WHEN a.attendance_type LIKE 'Late%%' OR a.status='Late Login' THEN 1 ELSE 0 END) AS late_days,
               COALESCE(sc.salary_per_day, 0) AS salary_per_day,
               e.about_me
        FROM employees e
        LEFT JOIN shifts s ON e.shift_id = s.id
        LEFT JOIN attendance a ON e.employee_id = a.employee_id
        LEFT JOIN salary_config sc ON e.employee_id = sc.employee_id
        WHERE e.employee_id = %s
        GROUP BY e.employee_id, e.name, e.role, e.email, e.date_of_joining,
                 e.work_mode, e.work_lat, e.work_lon,
                 e.face_image, e.qr_code,
                 e.department, e.phone, e.gender, e.dob, e.blood_group,
                 e.shift_id, e.manager_name,
                 e.address, e.city, e.state, e.pincode,
                 e.emergency_contact_name, e.emergency_contact_phone, e.emergency_contact_relation,
                 e.aadhar_number, e.pan_number,
                 e.bank_name, e.bank_account, e.bank_ifsc, e.uan_number,
                 s.name, sc.salary_per_day, e.about_me
    """, (emp_id,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        db.close()
        flash("Employee not found.", "error")
        return redirect(tpath("/employees"))

    # Decrypt PII fields: [12]=gender [14]=blood_group [17]=address [18]=city
    # [19]=state [20]=pincode [21]=ec_name [22]=ec_phone [23]=ec_relation
    # [24]=aadhar_number [25]=pan_number [26]=bank_name [27]=bank_account
    # [28]=bank_ifsc [29]=uan_number. [13]=dob handled separately (see
    # decrypt_pii_date). NOTE: this replaces an existing off-by-one bug that
    # decrypted the wrong indices (23,24,26,27,28) and left pan_number/
    # uan_number displayed as raw ciphertext on this page.
    row = list(row)
    for _pii_idx in (12, 14, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29):
        if _pii_idx < len(row):
            row[_pii_idx] = decrypt_pii(row[_pii_idx])
    row[13] = decrypt_pii_date(row[13])

    # DLP: aadhar/pan/bank_account/uan (indices 24,25,27,29) and salary
    # (index 36) are only shown unmasked to the finance/HR-clearance tier
    # (admin_role=="admin") -- mirrors the restriction payroll.py's
    # view_payslip already enforces for payslips. manager/soc_analyst still
    # get the rest of the record.
    salary_hidden = False
    if not has_pii_clearance():
        row[24] = mask_tail(row[24])
        row[25] = mask_tail(row[25])
        row[27] = mask_tail(row[27])
        row[29] = mask_tail(row[29])
        if row[36]:
            salary_hidden = True
            row[36] = None
    else:
        log_security_event("data.reveal", "Admin viewed unmasked PII on employee detail",
                           level="WARNING", identifier=session.get("admin_username"),
                           resource_type="employee_detail", resource_id=emp_id)

    cursor.execute("SELECT COUNT(*) FROM resignation_requests WHERE employee_id=%s AND status='Accepted'", (emp_id,))
    is_resigned = cursor.fetchone()[0] > 0
    cursor.execute(
        "SELECT COUNT(*) FROM leave_requests WHERE employee_id=%s AND status='Approved' AND leave_date=CURRENT_DATE", (emp_id,))
    is_on_leave = cursor.fetchone()[0] > 0

    if is_resigned:
        emp_status = "Resigned"
    elif is_on_leave:
        emp_status = "On Leave"
    else:
        emp_status = "Active"

    # Recent attendance (last 30 records)
    cursor.execute("""
        SELECT date, login_time, logout_time, attendance_type, status
        FROM attendance WHERE employee_id=%s
        ORDER BY date DESC LIMIT 30
    """, (emp_id,))
    raw_att = cursor.fetchall()

    def _fmt_time(t):
        if t is None:
            return None
        if isinstance(t, datetime.timedelta):
            total = int(t.total_seconds())
            h, rem = divmod(total, 3600)
            m = rem // 60
            suffix = "AM" if h < 12 else "PM"
            h12 = h % 12 or 12
            return f"{h12:02d}:{m:02d} {suffix}"
        if hasattr(t, 'strftime'):
            return t.strftime('%I:%M %p')
        return str(t)

    recent_attendance = [
        (date, _fmt_time(lt), _fmt_time(lot), att_type, status)
        for date, lt, lot, att_type, status in raw_att
    ]

    # Work experience
    cursor.execute("""
        SELECT company, designation, from_year, to_year, is_current, description
        FROM employee_experience WHERE employee_id=%s ORDER BY from_year DESC
    """, (emp_id,))
    experience = cursor.fetchall()

    # Education
    cursor.execute("""
        SELECT degree, institution, year_of_passing, percentage
        FROM employee_education WHERE employee_id=%s ORDER BY year_of_passing DESC
    """, (emp_id,))
    education = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM leave_requests WHERE status='Pending'")
    pending_leaves = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM resignation_requests WHERE status='Pending'")
    pending_resignations = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('Open','In Progress')")
    pending_tickets = cursor.fetchone()[0]

    # Documents for this employee
    cursor.execute(
        "SELECT id, doc_type, original_name, uploaded_by, uploaded_at FROM employee_documents WHERE employee_id=%s ORDER BY uploaded_at DESC",
        (emp_id,)
    )
    emp_docs = cursor.fetchall()

    cursor.close()
    db.close()
    return render_template("employee_detail.html",
                           emp=row,
                           emp_id=row[0], name=row[1], role=row[2], email=row[3],
                           doj=row[4], work_mode=row[5], work_lat=row[6], work_lon=row[7],
                           face_image=row[8], qr_code=row[9], department=row[10], phone=row[11],
                           gender=row[12], dob=row[13], blood_group=row[14], shift_id=row[15],
                           manager_name=row[16], address=row[17], city=row[18], state=row[19],
                           pincode=row[20], ec_name=row[21], ec_phone=row[22], ec_rel=row[23],
                           aadhar=row[24], pan=row[25], bank_name=row[26], bank_account=row[27],
                           bank_ifsc=row[28], uan=row[29], shift_name=row[30], total_days=row[31],
                           last_seen=row[32], full_days=row[33], half_days=row[34], late_days=row[35],
                           salary_pd=row[36], about_me=row[37],
                           emp_status=emp_status,
                           recent_attendance=recent_attendance,
                           experience=experience,
                           education=education,
                           pending_leaves=pending_leaves,
                           pending_resignations=pending_resignations,
                           pending_tickets=pending_tickets,
                           emp_docs=emp_docs,
                           salary_hidden=salary_hidden,
                           active_nav="employees",
                           )


@employees_bp.route("/add_employee_page", methods=["POST"])
@admin_required
def add_employee_page():
    name = request.form.get("name", "").strip()
    emp_id = request.form.get("emp_id", "").strip()
    email = request.form.get("email", "").strip() or None
    role = request.form.get("role", "").strip() or None
    date_of_joining = request.form.get("date_of_joining", "").strip() or None
    work_mode = request.form.get("work_mode", "office").strip() or "office"
    work_lat_raw = request.form.get("work_lat", "").strip()
    work_lon_raw = request.form.get("work_lon", "").strip()
    work_lat = float(work_lat_raw) if work_lat_raw else None
    work_lon = float(work_lon_raw) if work_lon_raw else None
    company_id_raw = request.form.get("company_id", "").strip()
    company_id = int(company_id_raw) if company_id_raw.isdigit() else None

    gender = encrypt_pii(request.form.get("gender", "").strip() or None)
    dob_raw = request.form.get("dob", "").strip()
    dob = encrypt_pii(dob_raw) if dob_raw else None
    blood_group = encrypt_pii(request.form.get("blood_group", "").strip() or None)
    address = encrypt_pii(request.form.get("address", "").strip() or None)
    city = encrypt_pii(request.form.get("city", "").strip() or None)
    state = encrypt_pii(request.form.get("state", "").strip() or None)
    pincode = encrypt_pii(request.form.get("pincode", "").strip() or None)
    ec_name = encrypt_pii(request.form.get("emergency_contact_name", "").strip() or None)
    ec_phone = encrypt_pii(request.form.get("emergency_contact_phone", "").strip() or None)
    ec_relation = encrypt_pii(request.form.get("emergency_contact_relation", "").strip() or None)
    aadhar = encrypt_pii(request.form.get("aadhar_number", "").strip() or None)
    pan = encrypt_pii(request.form.get("pan_number", "").strip().upper() or None)
    bank_name = encrypt_pii(request.form.get("bank_name", "").strip() or None)
    bank_account = encrypt_pii(request.form.get("bank_account", "").strip() or None)
    bank_ifsc = encrypt_pii(request.form.get("bank_ifsc", "").strip().upper() or None)
    uan = encrypt_pii(request.form.get("uan_number", "").strip() or None)
    edu_degrees = request.form.getlist("degree[]")
    edu_institutions = request.form.getlist("institution[]")
    edu_years = request.form.getlist("year_of_passing[]")
    edu_pcts = request.form.getlist("percentage[]")
    salary_per_day_raw = request.form.get("salary_per_day", "").strip()
    salary_per_day = float(salary_per_day_raw) if salary_per_day_raw else None

    if not name or not emp_id:
        flash("Name and Employee ID are required.", "error")
        return redirect(tpath("/employees"))
    if not validate_emp_id(emp_id):
        flash("Employee ID may only contain letters, digits, hyphens and underscores.", "error")
        return redirect(tpath("/employees"))
    _domain_error = validate_employee_email_domain(email)
    if _domain_error:
        flash(_domain_error, "error")
        return redirect(tpath("/employees"))

    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    # Auto-increment emp_id if already taken
    cursor.execute("SELECT employee_id FROM employees WHERE employee_id=%s", (emp_id,))
    if cursor.fetchone():
        prefix = ''.join(c for c in emp_id if not c.isdigit())
        if prefix:
            cursor.execute(
                "SELECT employee_id FROM employees WHERE employee_id LIKE %s",
                (prefix + "%",)
            )
            max_seq = 0
            for (eid,) in cursor.fetchall():
                sfx = eid[len(prefix):]
                if sfx.isdigit():
                    max_seq = max(max_seq, int(sfx))
            emp_id = f"{prefix}{max_seq + 1:03d}"

    file = request.files.get("face")
    if not file or not file.filename:
        flash("A face photo is required.", "error")
        cursor.close()
        db.close()
        return redirect(tpath("/employees"))

    _img_ok, _img_err = _validate_image_file(file)
    if not _img_ok:
        flash(_img_err, "error")
        cursor.close()
        db.close()
        return redirect(tpath("/employees"))

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], emp_id + ".jpg")
    file.save(filepath)

    if _face_recognition_available:
        test_img = face_recognition.load_image_file(filepath)
        if not face_recognition.face_encodings(test_img):
            os.remove(filepath)
            flash("No face detected in the uploaded photo. Please upload a clear, well-lit front-facing photo.", "error")
            cursor.close()
            db.close()
            return redirect(tpath("/employees"))

    auto_pass = secrets.token_urlsafe(8)
    hashed_pwd = generate_password_hash(auto_pass)

    # Retry up to 5 times in case of duplicate ID collision
    prefix = ''.join(c for c in emp_id if not c.isdigit())
    if not prefix:
        prefix = emp_id
    original_filepath = filepath  # photo was already saved under initial emp_id
    registered = False
    for _attempt in range(5):
        # Keep photo file in sync with the current emp_id on each retry attempt
        new_filepath = os.path.join(app.config["UPLOAD_FOLDER"], emp_id + ".jpg")
        if new_filepath != original_filepath and os.path.exists(original_filepath):
            try:
                os.rename(original_filepath, new_filepath)
                original_filepath = new_filepath
            except OSError:
                pass
        filepath = new_filepath
        qr_path = generate_qr(emp_id)
        try:
            _mgr_id = request.form.get("manager_id", "").strip() or None
            _mgr_name = request.form.get("manager_name", "").strip() or None
            _dept = request.form.get("department", "").strip() or None
            cursor.execute(
                "INSERT INTO employees (name, employee_id, email, role, face_image, qr_code, password, "
                "date_of_joining, work_mode, work_lat, work_lon, company_id, manager_id, manager_name, department, "
                "gender, dob, blood_group, address, city, state, pincode, "
                "emergency_contact_name, emergency_contact_phone, emergency_contact_relation, "
                "aadhar_number, pan_number, bank_name, bank_account, bank_ifsc, uan_number, "
                "force_pin_change) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
                "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)",
                (name, emp_id, email, role, filepath, qr_path, hashed_pwd,
                 date_of_joining, work_mode, work_lat, work_lon, company_id,
                 _mgr_id, _mgr_name, _dept,
                 gender, dob, blood_group, address, city, state, pincode,
                 ec_name, ec_phone, ec_relation,
                 aadhar, pan, bank_name, bank_account, bank_ifsc, uan)
            )
            db.commit()
            _enroll_fingerprint_from_form(emp_id, cursor, db)
            assign_leave_balances_for_employee(cursor, emp_id)
            for _deg, _inst, _yr, _pct in zip(edu_degrees, edu_institutions, edu_years, edu_pcts):
                _deg, _inst = _deg.strip(), _inst.strip()
                if _deg and _inst:
                    cursor.execute(
                        "INSERT INTO employee_education (employee_id, degree, institution, year_of_passing, percentage) "
                        "VALUES (%s,%s,%s,%s,%s)",
                        (emp_id, _deg, _inst, _yr.strip() or None, _pct.strip() or None)
                    )
            if salary_per_day is not None:
                cursor.execute(
                    "INSERT INTO salary_config (employee_id, salary_per_day) VALUES (%s,%s) "
                    "ON CONFLICT (employee_id) DO UPDATE SET salary_per_day=%s",
                    (emp_id, salary_per_day, salary_per_day)
                )
            db.commit()
            registered = True
            break
        except psycopg2.IntegrityError:
            db.rollback()
            # Find next available ID and retry
            cursor.execute(
                "SELECT employee_id FROM employees WHERE employee_id LIKE %s",
                (prefix + "%",)
            )
            max_seq = 0
            for (eid,) in cursor.fetchall():
                sfx = eid[len(prefix):]
                if sfx.isdigit():
                    max_seq = max(max_seq, int(sfx))
            emp_id = f"{prefix}{max_seq + 1:03d}"

    if registered:
        flash(f"Employee '{name}' registered! ID: {emp_id} | Password: {auto_pass}", "success")
        # Auto-assign default onboarding template if configured
        cursor.execute("SELECT default_onboarding_template_id FROM company_settings LIMIT 1")
        _cs = cursor.fetchone()
        _default_tpl = _cs[0] if _cs and _cs[0] else None
        if _default_tpl:
            cursor.execute("SELECT id FROM onboarding_templates WHERE id=%s AND is_active=1", (_default_tpl,))
            if cursor.fetchone():
                cursor.execute("""
                    SELECT id FROM employee_onboarding
                    WHERE employee_id=%s AND template_id=%s
                """, (emp_id, _default_tpl))
                if not cursor.fetchone():
                    _due = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
                    cursor.execute("""
                        INSERT INTO employee_onboarding (employee_id, template_id, assigned_date, due_date, status)
                        VALUES (%s, %s, %s, %s, 'In Progress') RETURNING id
                    """, (emp_id, _default_tpl, datetime.date.today().isoformat(), _due))
                    _ob_id = cursor.fetchone()[0]
                    db.commit()
                    cursor.execute("""
                        SELECT id, task_title, task_description, requires_document, due_days, sort_order
                        FROM onboarding_template_tasks WHERE template_id=%s ORDER BY sort_order, id
                    """, (_default_tpl,))
                    for _tt in cursor.fetchall():
                        cursor.execute("""
                            INSERT INTO employee_onboarding_tasks
                            (onboarding_id, template_task_id, employee_id, task_title,
                             task_description, requires_document, due_days, status)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,'Pending')
                        """, (_ob_id, _tt[0], emp_id, _tt[1], _tt[2], _tt[3], _tt[4]))
                    db.commit()
                    flash("Onboarding checklist auto-assigned.", "success")
        if email:
            _ecfg = get_email_config()
            if _ecfg:
                _login_url = employee_login_url()
                _html = (f"<p>Hi <strong>{name}</strong>, your account is ready.</p>"
                         f"<p>Employee ID: <strong>{emp_id}</strong><br>"
                         f"Password: <strong>{auto_pass}</strong></p>"
                         f"<p><a href=\"{_login_url}\">{_login_url}</a></p>")
                try:
                    send_email_smtp(email, f"Welcome {name} -- Your Login Credentials", _html, _ecfg)
                    flash(f"Credentials email sent to {email}", "success")
                except Exception:
                    pass
    else:
        if os.path.exists(filepath):
            os.remove(filepath)
        flash("Registration failed. Please try again.", "error")
    cursor.close()
    db.close()
    return redirect(tpath("/employees"))


@employees_bp.route("/update_employee_photo/<emp_id>", methods=["POST"])
@admin_required
def update_employee_photo(emp_id):
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT employee_id FROM employees WHERE employee_id=%s", (emp_id,))
    if not cursor.fetchone():
        flash("Employee not found.", "error")
        cursor.close()
        db.close()
        return redirect(tpath("/employees"))

    file = request.files.get("face")
    if not file or not file.filename:
        flash("No photo file provided.", "error")
        cursor.close()
        db.close()
        return redirect(tpath("/employees"))

    _img_ok, _img_err = _validate_image_file(file)
    if not _img_ok:
        flash(_img_err, "error")
        cursor.close()
        db.close()
        return redirect(tpath("/employees"))

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], emp_id + ".jpg")
    file.save(filepath)

    if _face_recognition_available:
        test_img = face_recognition.load_image_file(filepath)
        if not face_recognition.face_encodings(test_img):
            os.remove(filepath)
            flash("No face detected in the uploaded photo. Please upload a clear front-facing photo.", "error")
            cursor.close()
            db.close()
            return redirect(tpath("/employees"))

    cursor.execute("UPDATE employees SET face_image=%s WHERE employee_id=%s", (filepath, emp_id))
    db.commit()
    flash(f"Photo updated for employee '{emp_id}'.", "success")
    cursor.close()
    db.close()
    return redirect(tpath("/employees"))


@employees_bp.route("/regenerate_qr/<emp_id>", methods=["POST"])
@admin_required
def regenerate_qr(emp_id):
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT employee_id FROM employees WHERE employee_id=%s", (emp_id,))
    if not cursor.fetchone():
        flash("Employee not found.", "error")
        cursor.close()
        db.close()
        return redirect(tpath("/employees"))
    qr_path = generate_qr(emp_id)
    cursor.execute("UPDATE employees SET qr_code=%s WHERE employee_id=%s", (qr_path, emp_id))
    db.commit()
    flash(f"QR code regenerated for '{emp_id}'.", "success")
    cursor.close()
    db.close()
    return redirect(tpath("/employees"))


@employees_bp.route("/view_qrcodes")
@admin_required
def view_qrcodes():
    return redirect(tpath("/view_photos"))


@employees_bp.route("/dataset/<path:filename>")
@admin_required
def serve_dataset(filename):
    from flask import send_from_directory
    return send_from_directory(UPLOAD_FOLDER, filename)


@employees_bp.route("/my_photo")
def my_photo():
    from flask import send_from_directory
    emp_id = session.get("employee_id")
    if not emp_id:
        return "", 403
    photo_path = os.path.join(UPLOAD_FOLDER, emp_id + ".jpg")
    if not os.path.exists(photo_path):
        return "", 404
    return send_from_directory(UPLOAD_FOLDER, emp_id + ".jpg")


@employees_bp.route("/view_photos")
@admin_required
def view_photos():
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT employee_id, name, role, email, face_image, qr_code FROM employees ORDER BY name")
    employees = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template("employee_photos.html", employees=employees, active_nav="employees")


@employees_bp.route("/update_photo/<emp_id>", methods=["POST"])
@admin_required
def update_photo(emp_id):
    file = request.files.get("photo")
    ok, err = _validate_image_file(file)
    if not ok:
        return jsonify({"ok": False, "msg": err}), 400
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], emp_id + ".jpg")
    file.save(save_path)
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("UPDATE employees SET face_image=%s WHERE employee_id=%s", (emp_id + ".jpg", emp_id))
    db.commit()
    cursor.close()
    db.close()
    return jsonify({"ok": True})


@employees_bp.route("/api/generate_emp_id")
def generate_emp_id():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "not logged in"}), 401
    company_id_raw = request.args.get("company_id", "").strip()
    db = get_db_connection()
    cursor = db.cursor(buffered=True)

    if company_id_raw.isdigit():
        company_id = int(company_id_raw)
        cursor.execute("SELECT COALESCE(code,''), name FROM companies WHERE id=%s", (company_id,))
        row = cursor.fetchone()
        code = (row[0] or "").strip().upper() if row else ""
        company_name = row[1] if row else ""
        cursor.execute("SELECT employee_id FROM employees WHERE company_id=%s", (company_id,))
    else:
        cursor.execute("SELECT COALESCE(company_code,'') FROM company_settings LIMIT 1")
        row = cursor.fetchone()
        code = (row[0] or "").strip().upper() if row else ""
        company_name = ""
        cursor.execute("SELECT employee_id FROM employees WHERE company_id IS NULL")

    # Find max existing sequence number to avoid collisions on deletions
    prefix = code if code else "EMP"
    max_seq = 0
    for (eid,) in cursor.fetchall():
        if eid and eid.upper().startswith(prefix):
            suffix = eid[len(prefix):]
            if suffix.isdigit():
                max_seq = max(max_seq, int(suffix))

    # Also check all employees globally in case company_id mismatch
    cursor.execute("SELECT employee_id FROM employees WHERE employee_id LIKE %s", (f"{prefix}%",))
    for (eid,) in cursor.fetchall():
        if eid and eid.upper().startswith(prefix):
            suffix = eid[len(prefix):]
            if suffix.isdigit():
                max_seq = max(max_seq, int(suffix))

    cursor.close()
    db.close()
    seq = max_seq + 1
    emp_id = f"{prefix}{seq:03d}"
    return jsonify({"emp_id": emp_id, "code": code, "seq": seq, "company_name": company_name})


_IDC_DARK = (15, 40, 100)
_IDC_BLUE = (30, 58, 138)
_IDC_MID = (37, 99, 235)
_IDC_PALE = (219, 234, 254)
_IDC_WHITE = (255, 255, 255)
_IDC_LGRAY = (241, 245, 249)
_IDC_MGRAY = (100, 116, 139)
_IDC_DGRAY = (15, 23, 42)
_IDC_GOLD = (251, 191, 36)
_IDC_RED = (220, 38, 38)


def _idc_blood_drop(draw, x, y, w, h, color):
    """Draw a small blood-drop (teardrop) icon inside box (x, y, w, h) --
    vector-drawn rather than an emoji glyph, since the PIL fonts available
    in this environment can't render color emoji (they'd just show as a
    missing-glyph box)."""
    r = w / 2.0
    cx = x + r
    circle_bottom = y + h
    circle_top = circle_bottom - 2 * r
    draw.polygon([(cx, y), (x, circle_top + r * 0.2), (x + w, circle_top + r * 0.2)], fill=color)
    draw.ellipse([(cx - r, circle_top), (cx + r, circle_bottom)], fill=color)


def _idc_font(size, bold=False):
    from PIL import ImageFont
    candidates = (
        ["C:/Windows/Fonts/segoeuib.ttf",
         "C:/Windows/Fonts/arialbd.ttf",
         "C:/Windows/Fonts/calibrib.ttf",
         "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
        if bold else
        ["C:/Windows/Fonts/segoeui.ttf",
         "C:/Windows/Fonts/arial.ttf",
         "C:/Windows/Fonts/calibri.ttf",
         "/System/Library/Fonts/Supplemental/Arial.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    )
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _idc_safe_text(text):
    try:
        text.encode('latin-1')
        return text
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text.encode('ascii', 'replace').decode('ascii')


def _idc_text_width(draw, text, font):
    bb = draw.textbbox((0, 0), _idc_safe_text(text), font=font)
    return bb[2] - bb[0]


_IDC_WORK_MODE_LABELS = {"office": "Office", "wfh": "Work From Home"}


def _idc_fmt_shift_time(t):
    t = _td_to_time(t)
    return t.strftime("%I:%M %p") if t else None


def _idc_shift_timing_text(shift_start, shift_end):
    s, e = _idc_fmt_shift_time(shift_start), _idc_fmt_shift_time(shift_end)
    return f"{s} - {e}" if s and e else "-"


def _idc_work_mode_text(work_mode):
    return _IDC_WORK_MODE_LABELS.get(work_mode, work_mode or "-")


def _idc_center_text(draw, text, font, card_w, y, color):
    t = _idc_safe_text(text)
    draw.text(((card_w - _idc_text_width(draw, t, font)) // 2, y), t, font=font, fill=color)


def _idc_wrap_text(draw, text, font, max_width, max_lines=2):
    """Greedy word-wrap `text` to fit within `max_width` px, capped at
    `max_lines` lines -- used for the default card's company address, which
    is free-form text unlike the other fixed single-line fields. Anything
    past `max_lines` is dropped, with the last line ellipsized."""
    words = _idc_safe_text(text).split()
    lines, current = [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if not current or _idc_text_width(draw, candidate, font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)

    if len(lines) <= max_lines:
        return lines

    kept = lines[:max_lines]
    last = kept[-1]
    while len(last) > 1 and _idc_text_width(draw, last + "…", font) > max_width:
        last = last[:-1]
    kept[-1] = last + "…"
    return kept


def _idc_header_logo_and_name(draw, img, bar_h, company_name, logo_path, fallback_title, fallback_subtitle):
    """Draw the default card's header as a logo+company-name lockup when the
    employee's company has branding on file, or the generic fixed title
    otherwise -- shared by both the front and back default layouts so they
    stay visually identical instead of drifting apart."""
    from PIL import Image

    CW = img.width
    if not company_name and not logo_path:
        _idc_center_text(draw, fallback_title, _idc_font(18, bold=True), CW, 18, _IDC_WHITE)
        _idc_center_text(draw, fallback_subtitle, _idc_font(11), CW, 52, _IDC_PALE)
        return

    logo_img = None
    if logo_path:
        try:
            logo_img = Image.open(_idc_static_path(logo_path)).convert("RGBA").resize((56, 56), Image.LANCZOS)
        except Exception:
            logo_img = None

    circle_margin = 120  # leave room for the decorative circle at top-right
    font = _idc_font(22, bold=True)
    name = _idc_safe_text(company_name) if company_name else ""
    logo_block_w = 60 + 14 if logo_img else 0
    if name:
        max_name_w = max(20, CW - circle_margin - 14 - logo_block_w)
        while len(name) > 1 and _idc_text_width(draw, name, font) > max_name_w:
            name = name[:-1]
    name_w = _idc_text_width(draw, name, font) if name else 0
    total_w = logo_block_w + name_w
    start_x = max(14, (CW - circle_margin - total_w) // 2)

    if logo_img:
        box_y = (bar_h - 60) // 2
        draw.rounded_rectangle([(start_x, box_y), (start_x + 60, box_y + 60)], radius=8, fill=_IDC_WHITE)
        img.paste(logo_img, (start_x + 2, box_y + 2), logo_img)
        text_x = start_x + 60 + 14
    else:
        text_x = start_x

    if name:
        text_y = (bar_h - 26) // 2
        draw.text((text_x, text_y), name, font=font, fill=_IDC_WHITE)


def _idc_footer_contact(draw, cw, ch, company_name, company_website, company_phone):
    """Draw the company's identity (name, then website/toll-free) as up to
    two compact lines centered in the card's bottom footer bar -- the same
    spot where a generic disclaimer used to sit -- shared by front and back
    so they stay in sync. Draws nothing when the company has none of these
    on file, preserving today's look for uncustomized companies."""
    contact_parts = [p for p in (
        company_website, f"Toll-Free: {company_phone}" if company_phone else None,
    ) if p]
    if not company_name and not contact_parts:
        return

    def _fit(text, font, max_w):
        t = text
        while len(t) > 1 and _idc_text_width(draw, t, font) > max_w:
            t = t[:-1]
        return t

    max_w = cw - 40
    if company_name and contact_parts:
        _idc_center_text(draw, _fit(company_name, _idc_font(11, bold=True), max_w),
                         _idc_font(11, bold=True), cw, ch - 44, _IDC_WHITE)
        line2 = "  |  ".join(contact_parts)
        _idc_center_text(draw, _fit(line2, _idc_font(9), max_w), _idc_font(9), cw, ch - 26, (200, 210, 225))
    elif company_name:
        _idc_center_text(draw, _fit(company_name, _idc_font(12, bold=True), max_w),
                         _idc_font(12, bold=True), cw, ch - 34, _IDC_WHITE)
    else:
        line = "  |  ".join(contact_parts)
        _idc_center_text(draw, _fit(line, _idc_font(10), max_w), _idc_font(10), cw, ch - 34, _IDC_WHITE)


def _idc_box_text(draw, text, box, color, font_size=14, bold=False, align="center"):
    """Draw text truncated to fit inside a pixel box (x, y, w, h) -- used by
    custom-template rendering, where fields sit at admin-chosen positions
    rather than the fixed default layout's hardcoded coordinates."""
    font = _idc_font(font_size, bold=bold)
    x, y, w, h = box
    t = _idc_safe_text(str(text))
    while len(t) > 1 and _idc_text_width(draw, t, font) > w:
        t = t[:-1]
    tw_ = _idc_text_width(draw, t, font)
    tx = x + max(0, (w - tw_) // 2) if align == "center" else x
    ty = y + max(0, (h - font_size) // 2)
    draw.text((tx, ty), t, font=font, fill=color)


def _idc_static_path(rel_path):
    return os.path.join(app.root_path, "static", rel_path)


def _idc_box_bg_color(img, box):
    """Best-guess background fill color for a text field's box, sampled from
    the (unmodified) template image at each edge's midpoint. Custom templates
    often have their own placeholder wording baked into the pixels ("YOUR
    NAME", "JOB POSITION") on a pill/rounded-rect background -- the box's
    actual corners usually land outside a *rounded* pill (in whatever
    surrounds it), while edge midpoints reliably land on the pill's fill and
    rarely on a glyph stroke (text is centered with padding from the edges).
    Filling with this color before drawing the real value covers the
    placeholder text instead of drawing over it."""
    x, y, w, h = box
    inset = max(2, min(w, h) // 8)
    points = [
        (x + inset, y + h // 2),
        (x + w - inset, y + h // 2),
        (x + w // 2, y + inset),
        (x + w // 2, y + h - inset),
    ]
    samples = []
    for px, py in points:
        px = min(max(0, px), img.width - 1)
        py = min(max(0, py), img.height - 1)
        samples.append(img.getpixel((px, py)))
    counts = {}
    for s in samples:
        counts[s] = counts.get(s, 0) + 1
    best = max(counts.items(), key=lambda kv: kv[1])
    if best[1] > 1:
        return best[0]
    return tuple(sum(c[i] for c in samples) // len(samples) for i in range(3))


def _idc_contrast_color(bg_rgb):
    """Pick white or dark-navy text, whichever reads better against `bg_rgb`,
    using perceptual (WCAG-style) relative luminance. This is the fallback
    used whenever a custom-template field doesn't pin an explicit text
    color -- so a field placed over a dark pill (navy header, photo overlay)
    or a light one (white card body) is legible by default instead of always
    rendering the same fixed gray regardless of what's underneath."""
    def _chan(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = bg_rgb
    luminance = 0.2126 * _chan(r) + 0.7152 * _chan(g) + 0.0722 * _chan(b)
    return _IDC_WHITE if luminance < 0.5 else _IDC_DGRAY


def _idc_parse_color(hex_str, default):
    """Parse a '#rrggbb' string (from a custom template field's saved color)
    into an (r,g,b) tuple, falling back to `default` for anything invalid --
    an admin-placed field over a dark pill background needs light text, so
    this can't be a single hardcoded color for every template."""
    if not hex_str or not isinstance(hex_str, str):
        return default
    h = hex_str.lstrip("#")
    if len(h) != 6:
        return default
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return default


def _idc_combine(front_img, back_img):
    from PIL import Image, ImageDraw
    gap, lbl_h = 40, 24
    bgcol = (215, 225, 240)
    total_w = front_img.width + gap + back_img.width
    total_h = max(front_img.height, back_img.height) + lbl_h
    total = Image.new("RGB", (total_w, total_h), bgcol)
    td = ImageDraw.Draw(total)
    td.text((10, 4), "FRONT", font=_idc_font(13, bold=True), fill=_IDC_BLUE)
    td.text((front_img.width + gap + 10, 4), "BACK", font=_idc_font(13, bold=True), fill=_IDC_BLUE)
    total.paste(front_img, (0, lbl_h))
    total.paste(back_img, (front_img.width + gap, lbl_h))
    return total


def _render_default_front(emp_id, row, company_name=None, logo_path=None, company_address=None, department=None,
                          company_website=None, company_phone=None):
    """Today's fixed ID-card front layout, now showing the employee's company
    name/logo in the header when set (falls back to the generic subtitle for
    companies with no branding on file -- no visual change for those)."""
    from PIL import Image, ImageDraw

    CW, CH = 500, 820
    front = Image.new("RGB", (CW, CH), _IDC_WHITE)
    fd = ImageDraw.Draw(front)

    fd.rectangle([(0, 0), (CW, 110)], fill=_IDC_BLUE)
    fd.ellipse([(CW - 100, -60), (CW + 60, 100)], fill=_IDC_MID)
    _idc_header_logo_and_name(fd, front, 110, company_name, logo_path,
                              "EMPLOYEE ID CARD", "Attendance Management System")
    fd.rectangle([(0, 108), (CW, 113)], fill=_IDC_GOLD)

    fd.rectangle([(0, 113), (CW, 370)], fill=_IDC_LGRAY)
    PH_W, PH_H = 160, 190
    PH_X = CW // 2 - PH_W // 2
    PH_Y = 128
    fd.rounded_rectangle([(PH_X - 5, PH_Y - 5), (PH_X + PH_W + 5, PH_Y + PH_H + 5)], radius=8, fill=_IDC_GOLD)
    fd.rounded_rectangle([(PH_X - 2, PH_Y - 2), (PH_X + PH_W + 2, PH_Y + PH_H + 2)], radius=6, fill=_IDC_WHITE)
    photo_path = os.path.join("dataset", emp_id + ".jpg")
    try:
        ph = Image.open(photo_path).convert("RGB").resize((PH_W, PH_H), Image.LANCZOS)
        front.paste(ph, (PH_X, PH_Y))
    except Exception:
        fd.rounded_rectangle([(PH_X, PH_Y), (PH_X + PH_W, PH_Y + PH_H)], radius=4, fill=_IDC_MID)
        ini = row[1][0].upper() if row and row[1] else "?"
        _idc_center_text(fd, ini, _idc_font(56, bold=True), CW, PH_Y + PH_H // 2 - 38, _IDC_WHITE)

    _idc_center_text(fd, (row[1] or "Unknown")[:24], _idc_font(18, bold=True), CW, 328, _IDC_DGRAY)
    _idc_center_text(fd, (row[2] or "Employee")[:28], _idc_font(12), CW, 352, _IDC_MGRAY)
    fd.rectangle([(40, 372), (CW - 40, 374)], fill=_IDC_PALE)

    info_rows = [
        ("Employee ID", row[0] if row else "-"),
        ("Department", department or "-"),
        ("Email", row[3] if row and row[3] else "-"),
        ("Phone", row[8] if row and row[8] else "-"),
        ("Blood Group", row[7] if row and row[7] else "-"),
    ]
    y = 390
    for i, (lbl, val) in enumerate(info_rows):
        if i % 2 == 0:
            fd.rectangle([(0, y - 4), (CW, y + 38)], fill=_IDC_LGRAY)
        _idc_center_text(fd, lbl, _idc_font(10), CW, y + 2, _IDC_MGRAY)
        _idc_center_text(fd, str(val)[:34], _idc_font(13, bold=True), CW, y + 17, _IDC_DGRAY)
        y += 44

    bg_val = row[7] if row and row[7] else None
    addr_y = y + 8
    if bg_val:
        font_bg = _idc_font(13, bold=True)
        text_w = _idc_text_width(fd, bg_val, font_bg)
        icon_w, icon_h, gap = 13, 18, 6
        bw = 14 + icon_w + gap + text_w + 14
        bx = (CW - bw) // 2
        by = addr_y
        fd.rounded_rectangle([(bx, by), (bx + bw, by + 32)], radius=16, fill=_IDC_RED)
        icon_x, icon_y = bx + 14, by + (32 - icon_h) // 2
        _idc_blood_drop(fd, icon_x, icon_y, icon_w, icon_h, _IDC_WHITE)
        fd.text((icon_x + icon_w + gap, by + 8), _idc_safe_text(bg_val), font=font_bg, fill=_IDC_WHITE)
        addr_y = by + 48

    if company_address:
        addr_font = _idc_font(11)
        addr_y += 12
        fd.rectangle([(60, addr_y), (CW - 60, addr_y + 2)], fill=_IDC_PALE)
        addr_y += 14
        _idc_center_text(fd, "OFFICE ADDRESS", _idc_font(9, bold=True), CW, addr_y, _IDC_MGRAY)
        addr_y += 18
        for line in _idc_wrap_text(fd, company_address, addr_font, CW - 80, max_lines=2):
            _idc_center_text(fd, line, addr_font, CW, addr_y, _IDC_DGRAY)
            addr_y += 18

    fd.rectangle([(0, CH - 60), (CW, CH)], fill=_IDC_BLUE)
    fd.rectangle([(0, CH - 62), (CW, CH - 60)], fill=_IDC_GOLD)
    _idc_footer_contact(fd, CW, CH, company_name, company_website, company_phone)
    return front


def _render_default_back(emp_id, row, logo_path=None, emergency_name=None, emergency_phone=None,
                         emergency_relation=None, company_name=None, manager_name=None,
                         shift_start=None, shift_end=None, work_mode=None,
                         company_website=None, company_phone=None):
    """Today's fixed ID-card back layout, now also showing the company logo
    and name in the header (matching the front) and the employee's emergency
    contact in place of the generic "return to HR" line when one is on file."""
    from PIL import Image, ImageDraw

    CW, CH = 500, 820
    back = Image.new("RGB", (CW, CH), _IDC_LGRAY)
    bd = ImageDraw.Draw(back)

    bd.rectangle([(0, 0), (CW, 110)], fill=_IDC_BLUE)
    bd.ellipse([(CW - 100, -60), (CW + 60, 100)], fill=_IDC_MID)
    _idc_header_logo_and_name(bd, back, 110, company_name, logo_path,
                              "ATTENDANCE MANAGEMENT SYSTEM", "Employee Attendance Card")
    bd.rectangle([(0, 108), (CW, 113)], fill=_IDC_GOLD)

    qr_path = os.path.join("static", "qrcodes", emp_id + ".png")
    if not os.path.exists(qr_path):
        qr_path = generate_qr(emp_id)
    QS = 200
    qr_x = (CW - QS) // 2
    qr_y = 148
    bd.rounded_rectangle([(qr_x - 16, qr_y - 16), (qr_x + QS + 16, qr_y + QS + 16)], radius=14, fill=_IDC_WHITE)
    try:
        qr_img = Image.open(qr_path).convert("RGB").resize((QS, QS), Image.LANCZOS)
        back.paste(qr_img, (qr_x, qr_y))
    except Exception:
        _idc_center_text(bd, "QR NOT AVAILABLE", _idc_font(13), CW, qr_y + QS // 2, _IDC_MGRAY)

    _idc_center_text(bd, "Scan to Mark Attendance", _idc_font(14, bold=True), CW, qr_y + QS + 28, _IDC_BLUE)
    _idc_center_text(bd, row[0] if row else "", _idc_font(12), CW, qr_y + QS + 52, _IDC_MGRAY)
    bd.rectangle([(40, qr_y + QS + 78), (CW - 40, qr_y + QS + 80)], fill=(203, 213, 225))

    sub_info = [
        ("Name", (row[1] or "-")[:26] if row else "-"),
        ("Designation", (row[2] or "-")[:26] if row else "-"),
        ("Shift", (row[6] or "-")[:26] if row and len(row) > 6 else "-"),
        ("Shift Timing", _idc_shift_timing_text(shift_start, shift_end)),
        ("Work Mode", _idc_work_mode_text(work_mode)),
        ("Reporting Manager", (manager_name or "-")[:26]),
        ("Blood Group", (row[7] or "-") if row else "-"),
    ]
    sy = qr_y + QS + 90
    for lbl2, val2 in sub_info:
        _idc_center_text(bd, lbl2, _idc_font(10), CW, sy, _IDC_MGRAY)
        if lbl2 == "Blood Group" and val2 and val2 != "-":
            font_bg = _idc_font(12, bold=True)
            text_w = _idc_text_width(bd, val2, font_bg)
            icon_w, icon_h, gap = 11, 15, 5
            start_x = (CW - (icon_w + gap + text_w)) // 2
            _idc_blood_drop(bd, start_x, sy + 15, icon_w, icon_h, _IDC_RED)
            bd.text((start_x + icon_w + gap, sy + 14), _idc_safe_text(val2), font=font_bg, fill=_IDC_DGRAY)
        else:
            _idc_center_text(bd, val2, _idc_font(12, bold=True), CW, sy + 14, _IDC_DGRAY)
        sy += 30

    bd.rectangle([(36, sy + 8), (CW - 36, sy + 10)], fill=(203, 213, 225))
    if emergency_name:
        rel_suffix = f" ({emergency_relation})" if emergency_relation else ""
        _idc_center_text(bd, "Emergency Contact:", _idc_font(10), CW, sy + 18, _IDC_MGRAY)
        _idc_center_text(bd, (emergency_name + rel_suffix)[:34], _idc_font(12, bold=True), CW, sy + 34, _IDC_BLUE)
        if emergency_phone:
            _idc_center_text(bd, emergency_phone[:34], _idc_font(10), CW, sy + 54, _IDC_MGRAY)
    else:
        _idc_center_text(bd, "If found, please return to:", _idc_font(10), CW, sy + 18, _IDC_MGRAY)
        _idc_center_text(bd, "HR Department", _idc_font(12, bold=True), CW, sy + 34, _IDC_BLUE)
        if row and row[3]:
            _idc_center_text(bd, row[3][:34], _idc_font(10), CW, sy + 54, _IDC_MGRAY)

    bd.rectangle([(0, CH - 100), (CW, CH - 68)], fill=_IDC_DARK)
    bd.rectangle([(0, CH - 60), (CW, CH)], fill=_IDC_BLUE)
    bd.rectangle([(0, CH - 62), (CW, CH - 60)], fill=_IDC_GOLD)
    _idc_footer_contact(bd, CW, CH, company_name, company_website, company_phone)
    return back


_ID_CARD_TEXT_FIELDS = {
    "name", "employee_id", "designation", "email", "phone", "blood_group",
    "date_of_joining", "company_address", "website",
    "emergency_contact_name", "emergency_contact_phone", "emergency_contact_relation",
    "department", "shift", "reporting_manager", "shift_timing", "work_mode", "company_phone",
}


def _render_custom_side(image_path, fields, side, emp_id, row, logo_path, company_address=None,
                        company_website=None, company_phone=None):
    """Render one side of an admin-uploaded custom ID card template: opens
    the template image at its own native size and pastes/draws each
    admin-placed field (photo/logo/qr/text) at its saved normalized (0-1)
    position, converted to that image's actual pixel dimensions."""
    from PIL import Image, ImageDraw

    img = Image.open(_idc_static_path(image_path)).convert("RGB")
    original = img.copy()
    draw = ImageDraw.Draw(img)
    W, H = img.size
    joined = row[5]

    def _at(idx):
        return row[idx] if len(row) > idx else None

    values = {
        "name": row[1] or "-",
        "employee_id": row[0] or "-",
        "designation": row[2] or "-",
        "email": row[3] or "-",
        "phone": row[8] or "-",
        "blood_group": row[7] or "-",
        "date_of_joining": joined.strftime("%d-%m-%Y") if joined else "-",
        "company_address": company_address or "-",
        "website": company_website or "-",
        "company_phone": company_phone or "-",
        "department": _at(9) or "-",
        "reporting_manager": _at(10) or "-",
        "emergency_contact_name": _at(11) or "-",
        "emergency_contact_phone": _at(12) or "-",
        "emergency_contact_relation": _at(13) or "-",
        "shift": _at(6) or "-",
        "shift_timing": _idc_shift_timing_text(_at(14), _at(15)),
        "work_mode": _idc_work_mode_text(_at(16)),
    }

    for key, box in fields.items():
        if (box.get("side") or "front") != side:
            continue
        try:
            x = int(round(box["x"] * W))
            y = int(round(box["y"] * H))
            w = int(round(box["w"] * W))
            h = int(round(box["h"] * H))
        except (KeyError, TypeError, ValueError):
            continue
        if w <= 0 or h <= 0:
            continue

        if key == "photo":
            photo_path = os.path.join("dataset", emp_id + ".jpg")
            try:
                ph = Image.open(photo_path).convert("RGB").resize((w, h), Image.LANCZOS)
                img.paste(ph, (x, y))
            except Exception:
                draw.rectangle([(x, y), (x + w, y + h)], fill=_IDC_MID)
                ini = row[1][0].upper() if row and row[1] else "?"
                _idc_box_text(draw, ini, (x, y, w, h), _IDC_WHITE, font_size=max(10, min(w, h) // 2), bold=True)
        elif key == "logo":
            if logo_path:
                try:
                    from PIL import ImageOps
                    logo_img = Image.open(_idc_static_path(logo_path)).convert("RGBA")
                    fitted = ImageOps.contain(logo_img, (w, h), Image.LANCZOS)
                    bg = _idc_parse_color(box.get("bg_color"), None) or _idc_box_bg_color(original, (x, y, w, h))
                    off_x = (w - fitted.width) // 2
                    off_y = (h - fitted.height) // 2
                    if box.get("round"):
                        mask = Image.new("L", (w, h), 0)
                        ImageDraw.Draw(mask).ellipse([(0, 0), (w, h)], fill=255)
                        canvas = Image.new("RGBA", (w, h), bg + (255,))
                        canvas.paste(fitted, (off_x, off_y), fitted)
                        canvas.putalpha(mask)
                        img.paste(canvas, (x, y), canvas)
                    else:
                        draw.rectangle([(x, y), (x + w, y + h)], fill=bg)
                        img.paste(fitted, (x + off_x, y + off_y), fitted)
                except Exception:
                    pass
        elif key == "qr":
            qr_path = os.path.join("static", "qrcodes", emp_id + ".png")
            if not os.path.exists(qr_path):
                qr_path = generate_qr(emp_id)
            try:
                qr_img = Image.open(qr_path).convert("RGB").resize((w, h), Image.LANCZOS)
                img.paste(qr_img, (x, y))
            except Exception:
                pass
        elif key in _ID_CARD_TEXT_FIELDS:
            font_size = box.get("font_size", 14)
            bg = _idc_parse_color(box.get("bg_color"), None) or _idc_box_bg_color(original, (x, y, w, h))
            color = _idc_parse_color(box.get("color"), None) or _idc_contrast_color(bg)
            if box.get("square"):
                draw.rectangle([(x, y), (x + w, y + h)], fill=bg)
            else:
                radius = max(0, min(w, h) // 2 - 1)
                try:
                    draw.rounded_rectangle([(x, y), (x + w, y + h)], radius=radius, fill=bg)
                except ValueError:
                    draw.rectangle([(x, y), (x + w, y + h)], fill=bg)
            _idc_box_text(draw, values.get(key, "-"), (x, y, w, h), color,
                          font_size=font_size, bold=bool(box.get("bold")))
    return img


def _build_id_card_buf(emp_id):
    """Generate the front+back ID card PNG and return a BytesIO buffer, or
    None if not found. Renders the employee's company's custom template when
    one is configured, else the default generated design (company-branded
    when the company has a logo/name on file)."""
    import io as _io2

    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("""
        SELECT e.employee_id, e.name, e.role, e.email, e.face_image, e.date_of_joining,
               sh.name AS shift_name, e.blood_group, e.phone,
               COALESCE(e.department,''), COALESCE(e.manager_name,''),
               e.emergency_contact_name, e.emergency_contact_phone, e.emergency_contact_relation,
               sh.start_time, sh.end_time, e.work_mode,
               c.name, COALESCE(c.logo_path,''), t.front_image, t.back_image, t.fields,
               COALESCE(c.address,''), COALESCE(c.website,''), COALESCE(c.phone,'')
        FROM employees e
        LEFT JOIN shifts sh ON e.shift_id = sh.id
        LEFT JOIN companies c ON e.company_id = c.id
        LEFT JOIN id_card_templates t ON t.company_id = c.id
        WHERE e.employee_id = %s
    """, (emp_id,))
    full_row = cursor.fetchone()
    if not full_row:
        cursor.execute("""
            SELECT e.employee_id, e.name, e.role, e.email, e.face_image, e.date_of_joining,
                   NULL, e.blood_group, e.phone,
                   COALESCE(e.department,''), COALESCE(e.manager_name,''),
                   e.emergency_contact_name, e.emergency_contact_phone, e.emergency_contact_relation,
                   NULL, NULL, e.work_mode,
                   c.name, COALESCE(c.logo_path,''), t.front_image, t.back_image, t.fields,
                   COALESCE(c.address,''), COALESCE(c.website,''), COALESCE(c.phone,'')
            FROM employees e
            LEFT JOIN companies c ON e.company_id = c.id
            LEFT JOIN id_card_templates t ON t.company_id = c.id
            WHERE e.employee_id=%s
        """, (emp_id,))
        full_row = cursor.fetchone()
    cursor.close()
    db.close()

    if not full_row:
        return None

    row = full_row[:17]
    row = (row[:7] + (decrypt_pii(row[7]),) + row[8:11]
           + tuple(decrypt_pii(v) for v in row[11:14]) + row[14:17])
    # [7]=blood_group, [11:14]=emergency contact, [14:17]=shift_start,shift_end,work_mode
    (company_name, logo_path_raw, front_image, back_image, fields_raw,
     company_address_raw, company_website_raw, company_phone_raw) = full_row[17:25]
    logo_path = logo_path_raw or None
    company_address = company_address_raw or None
    company_website = company_website_raw or None
    company_phone = company_phone_raw or None
    department, manager_name = row[9], row[10]
    emergency_name, emergency_phone, emergency_relation = row[11], row[12], row[13]
    shift_start, shift_end, work_mode = row[14], row[15], row[16]

    try:
        fields = json.loads(fields_raw) if fields_raw else {}
    except (ValueError, TypeError):
        fields = {}

    if front_image:
        front = _render_custom_side(front_image, fields, "front", emp_id, row, logo_path, company_address,
                                    company_website, company_phone)
    else:
        front = _render_default_front(emp_id, row, company_name, logo_path, company_address, department,
                                      company_website, company_phone)

    if back_image:
        back = _render_custom_side(back_image, fields, "back", emp_id, row, logo_path, company_address,
                                   company_website, company_phone)
    else:
        back = _render_default_back(emp_id, row, logo_path, emergency_name, emergency_phone,
                                    emergency_relation, company_name, manager_name,
                                    shift_start, shift_end, work_mode, company_website, company_phone)

    total = _idc_combine(front, back)
    buf = _io2.BytesIO()
    total.save(buf, format="PNG", dpi=(200, 200))
    buf.seek(0)
    return buf


@employees_bp.route("/admin_id_card/<emp_id>")
@admin_required
def admin_id_card(emp_id):
    from flask import send_file
    buf = _build_id_card_buf(emp_id)
    if buf is None:
        return "Employee not found", 404
    return send_file(buf, as_attachment=True,
                     download_name=f"IDCard_{emp_id}.png",
                     mimetype="image/png")


@employees_bp.route("/admin_view_id_card/<emp_id>")
@admin_required
def admin_view_id_card(emp_id):
    from flask import send_file
    buf = _build_id_card_buf(emp_id)
    if buf is None:
        return "Employee not found", 404
    return send_file(buf, as_attachment=False,
                     download_name=f"IDCard_{emp_id}.png",
                     mimetype="image/png")


@employees_bp.route("/api/employees", methods=["GET"])
@api_required
@api_role_required("admin")
@limiter.limit("10 per minute")
def api_employees():
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(100, max(1, int(request.args.get("per_page", 50))))
    offset = (page - 1) * per_page
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT COUNT(*) FROM employees")
    total = cursor.fetchone()[0]
    cursor.execute("""
        SELECT e.employee_id, e.name, e.email, COALESCE(s.salary_per_day, 0)
        FROM employees e
        LEFT JOIN salary_config s ON e.employee_id = s.employee_id
        ORDER BY e.name
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    rows = cursor.fetchall()
    cursor.close()
    db.close()
    return jsonify({"ok": True, "total": total, "page": page, "per_page": per_page,
                    "employees": [
                        {"employee_id": r[0], "name": r[1], "email": r[2], "salary_per_day": float(r[3])}
                        for r in rows
                    ]})


@employees_bp.route("/api/employees", methods=["POST"])
@api_required
def api_register_employee():
    name = request.form.get("name", "").strip()
    emp_id = request.form.get("emp_id", "").strip()
    email = request.form.get("email", "").strip() or None
    file = request.files.get("face")
    if not name or not emp_id or not file:
        return jsonify({"ok": False, "msg": "name, emp_id and face image required"}), 400
    if not validate_emp_id(emp_id):
        return jsonify({"ok": False, "msg": "emp_id may only contain letters, digits, hyphens and underscores"}), 400
    _domain_error = validate_employee_email_domain(email)
    if _domain_error:
        return jsonify({"ok": False, "msg": _domain_error}), 400
    # Validate extension, MIME type, magic bytes and size before writing to disk.
    ok, err = _validate_image_file(file)
    if not ok:
        return jsonify({"ok": False, "msg": err}), 400
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], emp_id + ".jpg")
    file.save(filepath)
    if _face_recognition_available:
        test_img = face_recognition.load_image_file(filepath)
        if not face_recognition.face_encodings(test_img):
            os.remove(filepath)
            return jsonify({"ok": False, "msg": "No face detected in uploaded photo."}), 400
    qr_path = generate_qr(emp_id)
    init_pass = request.form.get("password", "").strip() or emp_id
    hashed_pwd = generate_password_hash(init_pass)
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    try:
        cursor.execute(
            "INSERT INTO employees (name, employee_id, email, face_image, qr_code, password, force_pin_change) "
            "VALUES (%s,%s,%s,%s,%s,%s,1)",
            (name, emp_id, email, filepath, qr_path, hashed_pwd)
        )
        db.commit()
    except Exception:
        app_log.error("API employee register failed", exc_info=True)
        db.rollback()
        cursor.close()
        db.close()
        return jsonify({"ok": False, "msg": "Failed to create employee. Check for duplicate ID."}), 400
    cursor.close()
    db.close()
    if email:
        _ecfg = get_email_config()
        if _ecfg:
            _login_url = employee_login_url()
            _html = (f"<p>Hi <strong>{name}</strong>, your account is ready.</p>"
                     f"<p>Employee ID: <strong>{emp_id}</strong><br>"
                     f"Password: <strong>{init_pass}</strong></p>"
                     f"<p><a href=\"{_login_url}\">{_login_url}</a></p>")
            try:
                send_email_smtp(email, f"Welcome {name} -- Your Login Credentials", _html, _ecfg)
            except Exception:
                app_log.error("api_register_employee: welcome email failed", exc_info=True)
    return jsonify({"ok": True, "msg": f"Employee {name} registered."})


@employees_bp.route("/api/employees/<emp_id>", methods=["GET"])
@api_required
@api_role_required("admin")
@limiter.limit("30 per minute")
def api_employee_detail(emp_id):
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("""
        SELECT e.employee_id, e.name, e.email, e.role, e.date_of_joining,
               COALESCE(s.salary_per_day, 0)
        FROM employees e
        LEFT JOIN salary_config s ON e.employee_id = s.employee_id
        WHERE e.employee_id = %s
    """, (emp_id,))
    row = cursor.fetchone()
    cursor.close()
    db.close()
    if not row:
        return jsonify({"ok": False, "msg": "Employee not found"}), 404
    return jsonify({"ok": True, "employee": {
        "employee_id": row[0], "name": row[1], "email": row[2],
        "role": row[3], "date_of_joining": str(row[4]) if row[4] else None,
        "salary_per_day": float(row[5])
    }})


@employees_bp.route("/api/employees/<emp_id>", methods=["PUT"])
@api_required
def api_edit_employee(emp_id):
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip() or None
    role = data.get("role", "").strip() or None
    date_of_joining = data.get("date_of_joining", "").strip() or None
    if not name:
        return jsonify({"ok": False, "msg": "name required"}), 400
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute(
        "UPDATE employees SET name=%s, email=%s, role=%s, date_of_joining=%s WHERE employee_id=%s",
        (name, email, role, date_of_joining, emp_id)
    )
    db.commit()
    cursor.close()
    db.close()
    return jsonify({"ok": True, "msg": "Employee updated."})


@employees_bp.route("/api/employees/<emp_id>", methods=["DELETE"])
@api_required
def api_delete_employee(emp_id):
    db = get_db_connection()
    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT face_image, qr_code FROM employees WHERE employee_id=%s", (emp_id,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        db.close()
        return jsonify({"ok": False, "msg": "Employee not found"}), 404
    for path in row:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception as _e:
                app_log.warning("Could not delete file %s: %s", path, _e)
    cursor.execute("DELETE FROM attendance WHERE employee_id=%s", (emp_id,))
    cursor.execute("DELETE FROM salary_config WHERE employee_id=%s", (emp_id,))
    cursor.execute("DELETE FROM leave_requests WHERE employee_id=%s", (emp_id,))
    cursor.execute("DELETE FROM resignation_requests WHERE employee_id=%s", (emp_id,))
    cursor.execute("DELETE FROM tickets WHERE employee_id=%s", (emp_id,))
    cursor.execute("DELETE FROM employees WHERE employee_id=%s", (emp_id,))
    db.commit()
    cursor.close()
    db.close()
    return jsonify({"ok": True, "msg": f"Employee '{emp_id}' deleted."})
