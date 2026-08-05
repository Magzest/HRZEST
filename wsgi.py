"""
Application factory entry point for the refactored blueprint structure.

Usage:
  gunicorn wsgi:application          # production
  python wsgi.py                     # local dev (SSL-aware)

Migration status
----------------
The blueprint split is in progress. Routes are being moved from app.py
(monolith) into blueprints/ incrementally. Each blueprint file documents
exactly which routes belong there and the imports each route needs.

Current state:
  ✅ extensions.py    — Flask app + limiter (shared by all blueprints)
  ✅ utils/config.py  — shift/salary runtime constants
  ✅ utils/helpers.py — audit, cache, encryption, validation, notifications
  ✅ utils/auth.py    — decorators, lockout, password hashing
  ✅ utils/email_utils.py     — SMTP + DB-backed queue worker
  ✅ utils/attendance_utils.py— attendance calculations
  🔄 blueprints/*.py  — route stubs with full migration instructions
  🔄 app.py           — still contains all routes (being drained into blueprints)

To migrate a route from app.py into its blueprint:
  1. Copy the route function from app.py to the blueprint file
  2. Change @app.route → @<name>_bp.route
  3. Update imports at top of blueprint file (see each file's Key imports section)
  4. Delete the route from app.py
  5. Run: python -m py_compile app.py && python -m py_compile blueprints/<file>.py
"""
import os
import sys

# ── Encoding fix for Windows ──────────────────────────────────────────────────
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import os as _os
from dotenv import load_dotenv
from utils.secrets_loader import load_aws_secrets
# In production, AWS_SECRET_ID must be set as a plain instance env var
# (not a secret itself — just its name/ARN). Runs before load_dotenv() so
# Secrets Manager values win in prod; local dev with no AWS_SECRET_ID falls
# straight through to .env unaffected.
load_aws_secrets()
load_dotenv()

# ── Import shared extensions FIRST (no side-effects) ─────────────────────────
from extensions import app, app_log  # noqa: F401
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# ── Start the email queue worker ──────────────────────────────────────────────
import threading
from utils.email_utils import _email_queue_worker
threading.Thread(target=_email_queue_worker, daemon=True, name="email-queue-worker").start()

# ── Register blueprints (uncomment as routes are migrated from app.py) ────────
#
# Migration status:
#   ✅ health.py          — /healthz, /favicon.ico
#   ✅ notifications.py   — /api/notifications/*, /web/notifications/*
#   ✅ payroll.py         — salary, payslips, reports, export (25 routes)
#   ✅ leave.py           — leave, holidays, resignation, overtime, comp-off (35 routes)
#   ✅ admin_views.py     — admin dashboard, settings, companies, analytics, audit (28 routes)
#   ✅ auth.py            — login, logout, password reset, WebAuthn (24 routes)
#   ✅ employees.py       — employee CRUD, photos, QR, ID cards (24 routes)
#   ✅ attendance.py      — check-in/out, shifts, breaks, reports (34 routes)
#   ✅ tickets.py         — support tickets (7 routes)
#   ✅ performance.py     — KPIs, reviews (10 routes; hike/bonus in payroll.py)
#   ✅ onboarding.py      — templates, tasks, offer letters (22 routes)
#   ✅ documents.py       — employee document management (7 routes)
#   ✅ org.py             — multi-tenant org self-registration (2 routes)
#   ✅ employee_portal.py — employee self-service, check-in APIs (20 routes)
#   ✅ core.py            — home, CSP reporting, session-risk stream,
#                            security lockout, token-based REST API (10 routes)
#
# All 15 blueprints migrated. app.py now holds zero route handlers — only
# shared setup (init_db, error handlers, before/after_request hooks,
# template filters).

# ✅ All routes migrated to blueprints — app.py now contains only helpers/init
from blueprints.health import health_bp
from blueprints.notifications import notifications_bp
from blueprints.payroll import payroll_bp
from blueprints.leave import leave_bp
from blueprints.admin_views import admin_views_bp
from blueprints.auth import auth_bp
from blueprints.employees import employees_bp
from blueprints.attendance import attendance_bp
from blueprints.tickets import tickets_bp
from blueprints.performance import performance_bp
from blueprints.documents import documents_bp
from blueprints.org import org_bp
from blueprints.onboarding import onboarding_bp
from blueprints.employee_portal import employee_portal_bp
from blueprints.core import core_bp
from blueprints.ai_hrms import ai_hrms_bp
from blueprints.secops import secops_bp
from blueprints.email_blast import email_blast_bp
from blueprints.compliance import compliance_bp
from blueprints.hr_portal import hr_bp
from blueprints.platform_admin import platform_admin_bp

app.register_blueprint(health_bp)
app.register_blueprint(notifications_bp)
app.register_blueprint(payroll_bp)
app.register_blueprint(leave_bp)
app.register_blueprint(admin_views_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(employees_bp)
app.register_blueprint(attendance_bp)
app.register_blueprint(tickets_bp)
app.register_blueprint(performance_bp)
app.register_blueprint(documents_bp)
app.register_blueprint(org_bp)
app.register_blueprint(onboarding_bp)
app.register_blueprint(employee_portal_bp)
app.register_blueprint(core_bp)
app.register_blueprint(ai_hrms_bp)
app.register_blueprint(secops_bp)
app.register_blueprint(email_blast_bp)
app.register_blueprint(compliance_bp)
app.register_blueprint(hr_bp)
app.register_blueprint(platform_admin_bp)

from blueprints.daily_report import daily_report_bp
app.register_blueprint(daily_report_bp)

# ── app.py: shared setup only (init_db, error handlers, before/after_request
#    hooks, template filters) — no route handlers remain, but it still needs
#    importing to run that setup code and register those hooks. ─────────────
import app as _app_module  # noqa: F401

# ── Startup DB init ───────────────────────────────────────────────────────────
with app.app_context():
    try:
        from app import init_master_db, init_db
        from utils.config import load_default_shift, load_salary_rules
        init_master_db()
        init_db()
        load_default_shift()
        load_salary_rules()
    except Exception as _e:
        app_log.warning("Startup init failed (non-fatal): %s", _e)

# ── Nightly daily report scheduler ───────────────────────────────────────────
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from blueprints.daily_report import generate_and_send_daily_report
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        func=generate_and_send_daily_report,
        trigger="cron",
        hour=23, minute=59,
        id="daily_attendance_report",
        replace_existing=True,
    )
    _scheduler.start()
    app_log.info("Daily report scheduler started — fires at 23:59 every night")
except ImportError:
    app_log.warning("APScheduler not installed — daily email reports disabled. Run: pip install apscheduler")
except Exception as _sch_err:
    app_log.warning("Scheduler failed to start: %s", _sch_err)

# ── WSGI export ───────────────────────────────────────────────────────────────
application = app   # gunicorn / uWSGI entry point

if __name__ == "__main__":
    _cert = _os.environ.get("SSL_CERT_PATH") or _os.path.join(_os.path.dirname(__file__), "cert.pem")
    _key = _os.environ.get("SSL_KEY_PATH") or _os.path.join(_os.path.dirname(__file__), "key.pem")
    if _os.path.exists(_cert) and _os.path.exists(_key):
        print("SSL cert found — starting on https://0.0.0.0:5000")
        app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False,  # nosec B104
                ssl_context=(_cert, _key))
    else:
        print("No cert.pem / key.pem — starting on http://0.0.0.0:5000")
        app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)  # nosec B104
