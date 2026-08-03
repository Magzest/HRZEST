"""Tests for _resolve_tenant()'s (app.py) session-cache re-validation: a
platform admin suspending a tenant (blueprints/platform_admin.py) must
lock out an already-logged-in session within a bounded window, not never
-- cookie-based sessions have no server-side store to revoke from outside,
so the cached tenant_db is re-checked against tenants.status periodically
instead of being trusted for the life of the session.

Calls _resolve_tenant() directly inside a manually constructed request
context, pre-seeding flask.session, rather than round-tripping real HTTP
requests through the test client with a custom Host header -- Werkzeug's
test client cookie jar doesn't reliably resend a Set-Cookie issued under a
custom Host back to a second request with the same Host in this
environment, which made a real end-to-end version of this test flaky for
reasons unrelated to the behavior under test. This targets the same
production code path (_resolve_tenant is a plain importable function, not
just a before_request registration) with a deterministic, direct call.
"""
import pytest
from flask import session as flask_session


def _make_tenant_row(db_engine, subdomain, status="active"):
    from app import init_master_db
    init_master_db()
    schema_name = "att_" + subdomain.replace("-", "_")
    cur = db_engine.cursor()
    cur.execute("DELETE FROM att_master.tenants WHERE subdomain=%s", (subdomain,))
    cur.execute(
        "INSERT INTO att_master.tenants (company_name, subdomain, db_name, status) "
        "VALUES (%s,%s,%s,%s)",
        (f"{subdomain} Co", subdomain, schema_name, status),
    )
    cur.close()
    return schema_name


def _drop_tenant_row(db_engine, subdomain):
    cur = db_engine.cursor()
    cur.execute("DELETE FROM att_master.tenants WHERE subdomain=%s", (subdomain,))
    cur.close()


class TestTenantStatusRecheck:
    def test_active_tenant_cache_hit_within_window_skips_requery(self, client, db_engine):
        from app import _resolve_tenant
        subdomain = "recheck-active-org"
        schema_name = _make_tenant_row(db_engine, subdomain, "active")
        try:
            with client.application.test_request_context("/admin_login"):
                flask_session["tenant_db"] = schema_name
                flask_session["_tenant_status_checked_at"] = __import__("time").time()
                result = _resolve_tenant()
                assert result is None  # falls through to the route, no rejection
                from flask import g
                assert g.tenant_db == schema_name
                # Cache-hit path doesn't touch the recheck timestamp again.
        finally:
            _drop_tenant_row(db_engine, subdomain)

    def test_active_tenant_recheck_after_window_elapses_stays_reachable(self, client, db_engine):
        from app import _resolve_tenant
        subdomain = "recheck-active-org2"
        schema_name = _make_tenant_row(db_engine, subdomain, "active")
        try:
            with client.application.test_request_context("/admin_login"):
                flask_session["tenant_db"] = schema_name
                flask_session["_tenant_status_checked_at"] = 0  # force the recheck branch
                result = _resolve_tenant()
                assert result is None
                from flask import g
                assert g.tenant_db == schema_name
                assert flask_session["_tenant_status_checked_at"] > 0  # stamped by the recheck
        finally:
            _drop_tenant_row(db_engine, subdomain)

    def test_suspended_tenant_rejected_once_rechecked(self, client, db_engine):
        from app import _resolve_tenant
        subdomain = "recheck-suspended-org"
        schema_name = _make_tenant_row(db_engine, subdomain, "suspended")
        try:
            with client.application.test_request_context("/admin_login"):
                flask_session["tenant_db"] = schema_name
                flask_session["_tenant_status_checked_at"] = 0  # force the recheck branch
                result = _resolve_tenant()
                assert result is not None, "suspended tenant must be rejected, not silently passed through"
                body, status = result
                assert status == 403
                assert body.json["ok"] is False
                assert "tenant_db" not in flask_session, "session must be cleared on rejection"
        finally:
            _drop_tenant_row(db_engine, subdomain)

    def test_suspended_tenant_still_reachable_within_recheck_window(self, client, db_engine):
        # Documents the deliberate trade-off: suspension isn't an instant
        # kill-switch for already-cached sessions, only bounded (see
        # _TENANT_STATUS_RECHECK_SEC).
        from app import _resolve_tenant
        subdomain = "recheck-suspended-org2"
        schema_name = _make_tenant_row(db_engine, subdomain, "suspended")
        try:
            with client.application.test_request_context("/admin_login"):
                flask_session["tenant_db"] = schema_name
                flask_session["_tenant_status_checked_at"] = __import__("time").time()
                result = _resolve_tenant()
                assert result is None
                from flask import g
                assert g.tenant_db == schema_name
        finally:
            _drop_tenant_row(db_engine, subdomain)

    def test_master_db_error_during_recheck_does_not_lock_out_session(self, client, db_engine, monkeypatch):
        # A transient DB hiccup during the periodic recheck must not punish
        # an otherwise-valid session -- fail open on infrastructure errors
        # here (the check itself still runs correctly next time), not on
        # anything related to the tenant's own actual status.
        from app import _resolve_tenant
        subdomain = "recheck-dberror-org"
        schema_name = _make_tenant_row(db_engine, subdomain, "active")
        try:
            def _boom():
                raise RuntimeError("master db unreachable")
            monkeypatch.setattr("database.get_master_db", lambda: _boom())
            with client.application.test_request_context("/admin_login"):
                flask_session["tenant_db"] = schema_name
                flask_session["_tenant_status_checked_at"] = 0
                result = _resolve_tenant()
                assert result is None
                from flask import g
                assert g.tenant_db == schema_name
        finally:
            _drop_tenant_row(db_engine, subdomain)
