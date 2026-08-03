"""Org blueprint — multi-tenant org self-registration."""
import os
import re
import secrets
from flask import Blueprint, request, redirect, render_template, flash
from extensions import app_log
from utils.auth import generate_password_hash

org_bp = Blueprint("org", __name__)

_SUBDOMAIN_RE = re.compile(r'^[a-z0-9\-]+$')

# Require a server-side secret token to prevent anonymous tenant creation.
# Empty/unset SIGNUP_SECRET disables /create_org entirely.
_SIGNUP_SECRET = os.environ.get("SIGNUP_SECRET", "").strip()


@org_bp.route("/create_org", methods=["GET"])
def create_org_page():
    if not _SIGNUP_SECRET:
        # Provisioning disabled: no SIGNUP_SECRET configured in .env
        return render_template("create_org.html", signup_disabled=True)
    return render_template("create_org.html", signup_disabled=False)


@org_bp.route("/create_org", methods=["POST"])
def create_org():
    # Require a server-side secret token to prevent anonymous tenant creation.
    if not _SIGNUP_SECRET:
        flash("Organisation self-registration is disabled on this server.", "error")
        return redirect("/create_org")
    submitted_secret = request.form.get("signup_secret", "").strip()
    if not secrets.compare_digest(_SIGNUP_SECRET, submitted_secret):
        flash("Invalid signup code. Contact your administrator.", "error")
        return redirect("/create_org")

    company_name = request.form.get("company_name", "").strip()
    subdomain = request.form.get("subdomain", "").strip().lower()
    admin_username = request.form.get("admin_username", "").strip()
    admin_password = request.form.get("admin_password", "").strip()
    admin_email = request.form.get("admin_email", "").strip() or None

    # Validate
    if not all([company_name, subdomain, admin_username, admin_password]):
        flash("All fields (company name, subdomain, admin username and password) are required.", "error")
        return redirect("/create_org")
    if not _SUBDOMAIN_RE.match(subdomain):
        flash("Subdomain may only contain lowercase letters, digits, and hyphens.", "error")
        return redirect("/create_org")
    if len(admin_password) < 8:
        flash("Admin password must be at least 8 characters.", "error")
        return redirect("/create_org")

    # Derive DB name
    db_name = "att_" + subdomain.replace("-", "_")

    # Check subdomain not taken — and, critically, that the derived schema
    # name doesn't already exist at all. Checking only the `tenants` registry
    # row (as before) missed two cases: (1) a subdomain like "master" derives
    # db_name "att_master", which IS the tenant-registry schema itself —
    # CREATE SCHEMA IF NOT EXISTS would then silently no-op and the rest of
    # this flow would run tenant-schema migrations and INSERT an
    # attacker-controlled admin account *inside the registry schema*; (2) a
    # schema left over from a previously failed provisioning attempt (schema
    # created, but the tenants-row insert further down failed) has no
    # `tenants` row, so it would look "available" and get silently reused —
    # and the old `ON CONFLICT ... DO UPDATE SET password=...` below would
    # have let a new signup overwrite an existing admin's password in it.
    try:
        from database import get_master_db
        mconn = get_master_db()
        mcur = mconn.cursor(buffered=True)
        mcur.execute("SELECT id FROM tenants WHERE subdomain=%s", (subdomain,))
        taken = mcur.fetchone() is not None
        if not taken:
            mcur.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name=%s", (db_name,))
            taken = mcur.fetchone() is not None
        mcur.close()
        mconn.close()
        if taken:
            flash(f"Subdomain '{subdomain}' is already taken. Choose another.", "error")
            return redirect("/create_org")
    except Exception as exc:
        app_log.error("create_org subdomain check failed: %s", exc)
        flash("Could not check subdomain availability. Please try again.", "error")
        return redirect("/create_org")

    try:
        from database import create_tenant_schema
        create_tenant_schema(db_name)
    except Exception as exc:
        app_log.error("create_org DB creation failed: %s", exc)
        flash("Failed to create organisation. Please contact support.", "error")
        return redirect("/create_org")

    try:
        from flask import g as _g
        _g.tenant_db = db_name
        from app import init_tenant_db
        init_tenant_db(db_name)
    except Exception as exc:
        app_log.error("create_org schema init failed: %s", exc)
        flash("Failed to initialise organisation schema. Please contact support.", "error")
        return redirect("/create_org")

    # Insert company settings and admin user into the new tenant DB
    try:
        from database import get_tenant_db
        tconn = get_tenant_db(db_name)
        tcur = tconn.cursor()
        tcur.execute(
            "UPDATE company_settings SET company_name=%s, setup_done=1 WHERE id=1",
            (company_name,)
        )
        # Plain INSERT, no ON CONFLICT: the schema-existence check above
        # guarantees this is a brand-new schema, so a conflict here means a
        # genuine race (two signups for the same subdomain at once) rather
        # than legitimate reuse — fail loudly via the except below instead of
        # silently overwriting whichever admin_users row won the race.
        plan = request.form.get("plan", "basic").strip().lower()
        if plan not in ("basic", "medium", "premium"):
            plan = "basic"

        tcur.execute(
            "INSERT INTO admin_users (username, password, email, plan) VALUES (%s, %s, %s, %s)",
            (admin_username, generate_password_hash(admin_password), admin_email, plan)
        )
        tconn.commit()
        tcur.close()
        tconn.close()
    except Exception as exc:
        flash(f"Failed to seed tenant data: {exc}", "error")
        return redirect("/create_org")

    # Register tenant in master DB
    try:
        from database import get_master_db
        mconn = get_master_db()
        mcur = mconn.cursor()
        mcur.execute(
            "INSERT INTO tenants (company_name, subdomain, db_name, admin_email, status) "
            "VALUES (%s, %s, %s, %s, 'active')",
            (company_name, subdomain, db_name, admin_email)
        )
        mconn.commit()
        mcur.close()
        mconn.close()
    except Exception as exc:
        flash(f"Tenant registered in DB but master registry failed: {exc}", "error")
        return redirect("/create_org")

    plan_label = plan.title()
    login_link = f"/admin_login?plan={plan}&subdomain={subdomain}"
    flash(f"🎉 Organisation '{company_name}' onboarded on {plan_label} Plan! Direct login link: {login_link}", "success")
    return redirect(login_link)
