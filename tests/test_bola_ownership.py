"""Tests for the object-level authorization guard (utils/auth.py:enforce_ownership)
and its use in the two employee-owned-resource routes that take a raw ID from the
URL/path: payroll.py's view_payslip and documents.py's download_document. These
are the BOLA/IDOR-shaped endpoints in this codebase — a valid session trying to
reach a DIFFERENT employee's payslip or uploaded document by editing an ID."""
import pytest
import utils.auth as auth_module


class TestEnforceOwnership:
    def test_admin_bypasses_ownership_check(self, client):
        with client.application.test_request_context():
            from flask import session
            session["admin_logged_in"] = True
            assert auth_module.enforce_ownership("SOMEONE_ELSE", "payslip") is True

    def test_own_resource_allowed(self, client):
        with client.application.test_request_context():
            from flask import session
            session["employee_id"] = "TST001"
            assert auth_module.enforce_ownership("TST001", "payslip") is True

    def test_cross_employee_denied(self, client):
        with client.application.test_request_context():
            from flask import session
            session["employee_id"] = "TST001"
            assert auth_module.enforce_ownership("OTHER_EMP", "payslip") is False

    def test_anonymous_denied(self, client):
        with client.application.test_request_context():
            assert auth_module.enforce_ownership("TST001", "payslip") is False

    def test_denial_logs_at_error_severity(self, client, monkeypatch):
        calls = []
        monkeypatch.setattr(
            auth_module, "log_security_event",
            lambda event_type, message, level="WARNING", **fields: calls.append((event_type, level, fields)),
        )
        with client.application.test_request_context():
            from flask import session
            session["employee_id"] = "TST001"
            auth_module.enforce_ownership("OTHER_EMP", "document", resource_id=42)
        assert len(calls) == 1
        event_type, level, fields = calls[0]
        assert event_type == "access.denied"
        assert level == "ERROR"
        assert fields["identifier"] == "TST001"
        assert fields["requested_owner"] == "OTHER_EMP"
        assert fields["resource_id"] == 42

    def test_allowed_access_does_not_log(self, client, monkeypatch):
        calls = []
        monkeypatch.setattr(
            auth_module, "log_security_event",
            lambda *a, **kw: calls.append((a, kw)),
        )
        with client.application.test_request_context():
            from flask import session
            session["employee_id"] = "TST001"
            auth_module.enforce_ownership("TST001", "payslip")
        assert calls == []


class TestPayslipOwnershipGate:
    def test_own_payslip_accessible(self, client, seed_employee):
        with client.session_transaction() as sess:
            sess["employee_id"] = seed_employee["employee_id"]
        resp = client.get(f"/view_payslip/{seed_employee['employee_id']}/2026/1")
        assert resp.status_code == 200

    def test_other_employees_payslip_rejected(self, client, seed_employee):
        with client.session_transaction() as sess:
            sess["employee_id"] = seed_employee["employee_id"]
        resp = client.get("/view_payslip/SOMEONE_ELSE/2026/1", follow_redirects=False)
        assert resp.status_code == 302
        assert "/login" in resp.headers.get("Location", "")

    def test_admin_can_view_any_payslip(self, client, seed_employee):
        with client.session_transaction() as sess:
            sess["admin_logged_in"] = True
        resp = client.get(f"/view_payslip/{seed_employee['employee_id']}/2026/1")
        assert resp.status_code == 200


class TestDocumentOwnershipGate:
    @pytest.fixture
    def seed_document(self, db_engine, seed_employee):
        cur = db_engine.cursor()
        cur.execute(
            "INSERT INTO employee_documents (employee_id, doc_type, original_name, stored_name) "
            "VALUES (%s,%s,%s,%s) RETURNING id",
            (seed_employee["employee_id"], "ID Proof", "id.pdf", "id.pdf"),
        )
        doc_id = cur.fetchone()[0]
        yield doc_id
        cur.execute("DELETE FROM employee_documents WHERE id=%s", (doc_id,))
        cur.close()

    def test_other_employees_document_rejected(self, client, seed_employee, seed_document):
        with client.session_transaction() as sess:
            sess["employee_id"] = "SOME_OTHER_EMP"
        resp = client.get(f"/download_document/{seed_document}", follow_redirects=False)
        assert resp.status_code == 302
        assert "/employee_portal" in resp.headers.get("Location", "")

    def test_owning_employee_not_rejected_by_ownership_check(self, client, seed_employee, seed_document):
        # The file doesn't exist on disk in this test environment, so the
        # route 500s/errors trying to send it — what matters here is that it
        # gets PAST the ownership check (i.e. doesn't redirect to /employee_portal
        # with "Access denied"), proving the gate doesn't block the real owner.
        with client.session_transaction() as sess:
            sess["employee_id"] = seed_employee["employee_id"]
        resp = client.get(f"/download_document/{seed_document}", follow_redirects=False)
        assert resp.status_code != 302 or "/employee_portal" not in resp.headers.get("Location", "")
