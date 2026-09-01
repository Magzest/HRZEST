# -*- coding: utf-8 -*-
"""
Application factory entry point for the refactored blueprint structure.

Usage:
  gunicorn wsgi:application          # production
  python wsgi.py                     # local dev (SSL-aware)

Migration status
----------------
The blueprint split (app.py's routes moved into blueprints/) is complete --
see the "Register blueprints" section below for the full list. app.py now
holds only shared setup: init_db, error handlers, before/after_request
hooks, and template filters.
"""
import os
import sys

# ── Encoding fix for Windows ──────────────────────────────────────────────────
# Runs before `from extensions import app_log` below, so there's no logger
# available yet to report a failure here to -- harmless either way (fails
# only on a stream that doesn't support .reconfigure(), e.g. Python <3.7 or
# a fully redirected/piped stdout that's already fixed-encoding).
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import os as _os
from dotenv import load_dotenv
from utils.secrets_loader import load_aws_secrets
# In production, AWS_SECRET_ID must be set as a plain instance env var
# (not a secret itself -- just its name/ARN). Runs before load_dotenv() so
# Secrets Manager values win in prod; local dev with no AWS_SECRET_ID falls
# straight through to .env unaffected.
load_aws_secrets()
load_dotenv()

# ── Import shared extensions FIRST (no side-effects) ─────────────────────────
from extensions import app, app_log  # noqa: F401
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Path-based multi-tenancy (www.hrzest.com/<company-slug>/...) -- strips a
# recognized tenant slug into SCRIPT_NAME before Flask ever routes the
# request. See utils/tenant_routing.py for why this has to be WSGI-level
# rather than a route parameter on every blueprint.
from utils.tenant_routing import TenantPrefixMiddleware
app.wsgi_app = TenantPrefixMiddleware(app.wsgi_app)

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

# ── Start the email queue worker ──────────────────────────────────────────────
import threading
from utils.email_utils import _email_queue_worker
threading.Thread(target=_email_queue_worker, daemon=True, name="email-queue-worker").start()

# ── Register blueprints (uncomment as routes are migrated from app.py) ────────
#
# Migration status:
#   ✅ health.py          -- /healthz, /favicon.ico
#   ✅ notifications.py   -- /api/notifications/*, /web/notifications/*
#   ✅ payroll.py         -- salary, payslips, reports, export (25 routes)
#   ✅ leave.py           -- leave, holidays, resignation, overtime, comp-off (35 routes)
#   ✅ admin_views.py     -- admin dashboard, settings, companies, analytics, audit (28 routes)
#   ✅ auth.py            -- login, logout, password reset, WebAuthn (24 routes)
#   ✅ employees.py       -- employee CRUD, photos, QR, ID cards (24 routes)
#   ✅ attendance.py      -- check-in/out, shifts, breaks, reports (34 routes)
#   ✅ tickets.py         -- support tickets (7 routes)
#   ✅ performance.py     -- KPIs, reviews (10 routes; hike/bonus in payroll.py)
#   ✅ onboarding.py      -- templates, tasks, offer letters (22 routes)
#   ✅ documents.py       -- employee document management (7 routes)
#   ✅ org.py             -- multi-tenant org self-registration (2 routes)
#   ✅ employee_portal.py -- employee self-service, check-in APIs (20 routes)
#   ✅ core.py            -- home, CSP reporting, session-risk stream,
#                            security lockout, token-based REST API (10 routes)
#
# All 15 blueprints migrated. app.py now holds zero route handlers -- only
# shared setup (init_db, error handlers, before/after_request hooks,
# template filters).

# ── Register blueprints & shared app setup ────────────────────────────────────
import app as _app_module  # noqa: F401

# ── Nightly daily report scheduler ───────────────────────────────────────────
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from blueprints.daily_report import generate_and_send_daily_report
    from blueprints.auto_debit import sync_and_bill_auto_debit
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        func=generate_and_send_daily_report,
        trigger="cron",
        hour=23, minute=59,
        id="daily_attendance_report",
        replace_existing=True,
    )
    _scheduler.add_job(
        func=sync_and_bill_auto_debit,
        trigger="cron",
        hour=2, minute=0,
        id="auto_debit_sync_and_bill",
        replace_existing=True,
    )
    _scheduler.start()
    app_log.info("Daily report scheduler started -- fires at 23:59 every night")
    app_log.info("Auto-debit sync/billing scheduler started -- fires at 02:00 every night")
except ImportError:
    app_log.warning("APScheduler not installed -- daily email reports disabled. Run: pip install apscheduler")
except Exception as _sch_err:
    app_log.warning("Scheduler failed to start: %s", _sch_err)

# ── WSGI export ───────────────────────────────────────────────────────────────
application = app   # gunicorn / uWSGI entry point

if __name__ == "__main__":
    _cert = _os.environ.get("SSL_CERT_PATH") or _os.path.join(_os.path.dirname(__file__), "cert.pem")
    _key = _os.environ.get("SSL_KEY_PATH") or _os.path.join(_os.path.dirname(__file__), "key.pem")
    # threaded=True: /api/session/risk-stream (blueprints/core.py) holds an
    # SSE connection open for ~20s, and Werkzeug's dev server is single-
    # threaded by default -- without this, one open stream blocks every
    # other request until it closes.
    if _os.path.exists(_cert) and _os.path.exists(_key):
        print("SSL cert found -- starting on https://0.0.0.0:5000")
        app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False, threaded=True,  # nosec B104
                ssl_context=(_cert, _key))
    else:
        print("No cert.pem / key.pem -- starting on http://0.0.0.0:5000")
        app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False, threaded=True)  # nosec B104
