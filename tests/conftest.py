"""
Pytest configuration and fixtures.

Tests run against a real test PostgreSQL database (att_test) to avoid
mock/prod divergence. Requires DB_* env vars pointing to a local PostgreSQL
instance. Set them in .env.test or export before running:

    DB_HOST=localhost DB_USER=postgres DB_PASS=secret pytest tests/
"""
import os
import pytest

# Override BEFORE dotenv loads (setdefault wins only if var not already in env).
# Force-set here so they take priority over any .env file values.
os.environ["DB_NAME"] = "att_test"
os.environ["DB_HOST"] = "localhost"
os.environ["APP_ENV"] = "development"   # avoids HTTPS-only cookies
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
# utils/helpers.py's PII-encryption bootstrap hard-fails at import time if
# this is missing, in every environment including tests — no dev/test
# exception, by design (see utils/helpers.py). Fixed test-only key, not a
# real secret.
os.environ["ENCRYPTION_KEY"] = "_jboJL8OrI9muPNyf0xCNrakSo_Iz5EbJSQ1KpDcAgY="

# wsgi.py (the real production entrypoint) registers the migrated
# blueprints on the shared `app` instance from extensions.py BEFORE
# importing app.py — mirror that exact order here. app.py's
# _register_api_v1_aliases() runs at import time and mirrors whatever
# routes are already in app.url_map, so blueprints registered AFTER
# `import app` would silently lose their /api/v1/* aliases (a real gap
# this order previously had: /api/v1/employees 404'd in tests while
# working in production, because wsgi.py's order is already correct).
from extensions import app as flask_app
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
flask_app.register_blueprint(health_bp)
flask_app.register_blueprint(notifications_bp)
flask_app.register_blueprint(payroll_bp)
flask_app.register_blueprint(leave_bp)
flask_app.register_blueprint(admin_views_bp)
flask_app.register_blueprint(auth_bp)
flask_app.register_blueprint(employees_bp)
flask_app.register_blueprint(attendance_bp)
flask_app.register_blueprint(tickets_bp)
flask_app.register_blueprint(performance_bp)
flask_app.register_blueprint(documents_bp)
flask_app.register_blueprint(org_bp)
flask_app.register_blueprint(onboarding_bp)
flask_app.register_blueprint(employee_portal_bp)
flask_app.register_blueprint(core_bp)
flask_app.register_blueprint(ai_hrms_bp)
flask_app.register_blueprint(secops_bp)
flask_app.register_blueprint(email_blast_bp)
flask_app.register_blueprint(compliance_bp)
flask_app.register_blueprint(hr_bp)

# Import app AFTER blueprints are registered so all module-level reads pick
# up test values AND _register_api_v1_aliases() sees the full route set.
import app as _app_module  # noqa: F401 — triggers route registration + init_db

# Fall back to typical local-Postgres defaults ONLY if .env (already loaded
# by database.py's load_dotenv() above) didn't provide them — setting these
# before the imports would permanently lock out the real .env values, since
# load_dotenv() never overrides an already-set env var.
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_USER", os.getenv("DB_USER", "postgres"))
os.environ.setdefault("DB_PASS", os.getenv("DB_PASS", ""))

# Disable Flask-Limiter for all tests — its .enabled attribute is set at init
# time (not dynamically from config), so we patch the instance directly.
_app_module.limiter.enabled = False

# Disable the mandatory-admin-MFA-enrollment gate (app.py's
# _enforce_admin_mfa_enrollment) for the suite by default — most tests log in
# admin sessions directly via session_transaction without an enrolled TOTP
# secret, same reasoning as disabling the rate limiter above. Tests for the
# gate itself (tests/test_mandatory_admin_mfa.py) re-enable it locally.
flask_app.config["MANDATORY_ADMIN_MFA"] = False

# Disable the mandatory-emailed-OTP-at-login gate (blueprints/auth.py's
# MANDATORY_LOGIN_MFA, blueprints/hr_portal.py's hr_login()) for the same
# reason: nearly the entire suite uses a plain POST /admin_login or
# /hr_login as its "get an authenticated session" setup and expects it to
# complete immediately. Tests for the gate itself (tests/test_login_mfa.py)
# re-enable it locally.
flask_app.config["MANDATORY_LOGIN_MFA"] = False


@pytest.fixture(scope="session")
def db_engine():
    """Return a raw psycopg2 connection to the test database for fixture setup."""
    import psycopg2
    conn = psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "5432")),
        user=os.environ["DB_USER"],
        password=os.environ.get("DB_PASS", ""),
        dbname=os.environ["DB_NAME"],
    )
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="session", autouse=True)
def _init_test_db(db_engine):
    """Run init_db() once per test session to set up schema in att_test."""
    with flask_app.app_context():
        from app import init_db
        init_db()
    # Clear transient state tables so stale data from prior runs doesn't bleed in
    cur = db_engine.cursor()
    cur.execute("DELETE FROM login_attempts WHERE 1=1")
    # init_db() only marks setup_done=1 when ADMIN_PASSWORD is set in the
    # environment (it seeds an admin from env, then marks setup complete
    # since one now exists) -- CI's pytest job doesn't set that var, so on
    # a fresh database setup_done stays 0 and every test that logs in via
    # the real /admin_login POST route (rather than the session_transaction
    # bypass some test files use) gets redirected to /setup before its
    # credentials are even checked. Tests assume setup is already done
    # (see test_auth_blueprint.py's test_get_when_setup_done_redirects_to_login),
    # so make that true directly instead of depending on env-var seeding.
    cur.execute("UPDATE company_settings SET setup_done=1 WHERE setup_done=0")
    cur.close()


@pytest.fixture(scope="session", autouse=True)
def _reset_login_attempts(db_engine, _init_test_db):
    """Clear login_attempts before the session starts.

    att_test is a persistent database, not recreated per run — tests that
    intentionally trigger failed logins (wrong password, unknown user)
    accumulate failed_count across every past run. Once a hardcoded test
    identifier crosses _LOGIN_MAX_ATTEMPTS, locked_until gets set and never
    clears (only a *successful* login clears it, which these tests never
    do), so a run days later can spuriously fail on an unrelated assertion
    because the login page renders "Account locked" instead of "Invalid
    credentials". Depends on _init_test_db so the table already exists.
    """
    cur = db_engine.cursor()
    cur.execute("DELETE FROM login_attempts")
    cur.close()


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True   # disables CSRF check + rate limits
    flask_app.config["WTF_CSRF_ENABLED"] = False
    flask_app.config["SESSION_COOKIE_SECURE"] = False
    flask_app.config["RATELIMIT_ENABLED"] = False  # Flask-Limiter 3.x flag
    with flask_app.test_client() as c:
        yield c


@pytest.fixture
def seed_admin(db_engine):
    """Insert a test admin user; clean up after the test."""
    from utils.auth import generate_password_hash
    cur = db_engine.cursor()
    cur.execute(
        "INSERT INTO admin_users (username, password, email) VALUES (%s,%s,%s) "
        "ON CONFLICT (username) DO NOTHING",
        ("test_admin", generate_password_hash("Test@1234"), "admin@test.local"),
    )
    yield {"username": "test_admin", "password": "Test@1234"}
    cur.execute("DELETE FROM admin_users WHERE username='test_admin'")
    cur.close()


@pytest.fixture
def seed_employee(db_engine):
    """Insert a test employee; clean up after the test."""
    from utils.auth import generate_password_hash
    cur = db_engine.cursor()
    cur.execute(
        "INSERT INTO employees (employee_id, name, email, password, force_pin_change) "
        "VALUES (%s,%s,%s,%s,0) ON CONFLICT (employee_id) DO NOTHING",
        ("TST001", "Test Employee", "emp@test.local", generate_password_hash("EmpPass@1")),
    )
    yield {"employee_id": "TST001", "password": "EmpPass@1", "name": "Test Employee"}
    cur.execute("DELETE FROM employees WHERE employee_id='TST001'")
    cur.execute("DELETE FROM api_tokens WHERE identity='TST001'")
    cur.close()
