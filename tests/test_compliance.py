"""Compliance & Security Center tests — certification attestations,
regulatory deadlines, and the audit log explorer.

Run with:
    python -m pytest tests/test_compliance.py -v
"""


def _admin_session(client, seed_admin):
    resp = client.post("/admin_login", data={
        "identifier": seed_admin["username"],
        "password": seed_admin["password"],
    }, follow_redirects=True)
    assert resp.status_code == 200
    return resp


def _cleanup_deadlines(db_engine, title):
    cur = db_engine.cursor()
    cur.execute("DELETE FROM compliance_deadlines WHERE title=%s", (title,))
    cur.close()


def _reset_certification(db_engine, framework):
    cur = db_engine.cursor()
    cur.execute(
        "UPDATE compliance_certifications SET status='Not Started', owner=NULL, "
        "last_reviewed=NULL, next_review=NULL, notes=NULL WHERE framework=%s",
        (framework,)
    )
    cur.close()


# ===========================================================================
# Dashboard
# ===========================================================================

class TestComplianceDashboard:
    def test_requires_admin(self, client):
        resp = client.get("/compliance", follow_redirects=False)
        assert resp.status_code in (302, 401, 403)

    def test_renders_for_admin(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.get("/compliance")
        assert resp.status_code == 200

    def test_seeded_frameworks_present(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.get("/compliance")
        body = resp.data.decode()
        for fw in ("GDPR", "SOC 2 Type II", "ISO 27001", "ISO 9001"):
            assert fw in body

    def test_access_matrix_present(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.get("/compliance")
        body = resp.data.decode()
        assert "Access Control Matrix" in body
        assert "SOC Security Dashboard" in body

    def test_data_residency_present(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.get("/compliance")
        body = resp.data.decode()
        assert "Data Residency" in body


# ===========================================================================
# Certification updates
# ===========================================================================

class TestCertificationUpdate:
    def test_update_certification_status(self, client, seed_admin, db_engine):
        _admin_session(client, seed_admin)
        try:
            resp = client.post("/compliance/certifications/update", data={
                "framework": "GDPR",
                "status": "In Progress",
                "owner": "Test Owner",
                "last_reviewed": "",
                "next_review": "",
                "notes": "Kickoff review scheduled.",
            }, follow_redirects=True)
            assert resp.status_code == 200

            cur = db_engine.cursor()
            cur.execute("SELECT status, owner, notes FROM compliance_certifications WHERE framework='GDPR'")
            row = cur.fetchone()
            cur.close()
            assert row[0] == "In Progress"
            assert row[1] == "Test Owner"
            assert row[2] == "Kickoff review scheduled."
        finally:
            _reset_certification(db_engine, "GDPR")

    def test_update_rejects_invalid_status(self, client, seed_admin, db_engine):
        _admin_session(client, seed_admin)
        try:
            resp = client.post("/compliance/certifications/update", data={
                "framework": "GDPR",
                "status": "Definitely Certified",
            }, follow_redirects=True)
            assert resp.status_code == 200

            cur = db_engine.cursor()
            cur.execute("SELECT status FROM compliance_certifications WHERE framework='GDPR'")
            row = cur.fetchone()
            cur.close()
            assert row[0] == "Not Started"
        finally:
            _reset_certification(db_engine, "GDPR")

    def test_requires_admin(self, client):
        resp = client.post("/compliance/certifications/update", data={
            "framework": "GDPR", "status": "Compliant",
        }, follow_redirects=False)
        assert resp.status_code in (302, 401, 403)


# ===========================================================================
# Regulatory deadlines
# ===========================================================================

class TestDeadlines:
    def test_add_deadline_appears_in_upcoming(self, client, seed_admin, db_engine):
        _admin_session(client, seed_admin)
        try:
            resp = client.post("/compliance/deadlines/add", data={
                "title": "Test GST Filing",
                "jurisdiction": "India",
                "category": "Tax Filing",
                "due_date": "2099-01-01",
            }, follow_redirects=True)
            assert resp.status_code == 200
            assert "Test GST Filing" in resp.data.decode()
        finally:
            _cleanup_deadlines(db_engine, "Test GST Filing")

    def test_add_deadline_requires_title_and_date(self, client, seed_admin, db_engine):
        _admin_session(client, seed_admin)
        resp = client.post("/compliance/deadlines/add", data={
            "title": "",
            "category": "Tax Filing",
            "due_date": "",
        }, follow_redirects=True)
        assert resp.status_code == 200
        cur = db_engine.cursor()
        cur.execute("SELECT COUNT(*) FROM compliance_deadlines WHERE title=''")
        assert cur.fetchone()[0] == 0
        cur.close()

    def test_mark_deadline_completed_moves_out_of_upcoming(self, client, seed_admin, db_engine):
        _admin_session(client, seed_admin)
        try:
            client.post("/compliance/deadlines/add", data={
                "title": "Test Labour Audit",
                "category": "Audit",
                "due_date": "2099-01-01",
            }, follow_redirects=True)

            cur = db_engine.cursor()
            cur.execute("SELECT id FROM compliance_deadlines WHERE title='Test Labour Audit'")
            deadline_id = cur.fetchone()[0]
            cur.close()

            resp = client.post(f"/compliance/deadlines/{deadline_id}/status", data={
                "status": "Completed",
            }, follow_redirects=True)
            assert resp.status_code == 200

            cur = db_engine.cursor()
            cur.execute("SELECT status FROM compliance_deadlines WHERE id=%s", (deadline_id,))
            assert cur.fetchone()[0] == "Completed"
            cur.close()
        finally:
            _cleanup_deadlines(db_engine, "Test Labour Audit")


# ===========================================================================
# Audit log explorer
# ===========================================================================

class TestAuditLogExplorer:
    def test_requires_admin(self, client):
        resp = client.get("/compliance/audit-logs", follow_redirects=False)
        assert resp.status_code in (302, 401, 403)

    def test_renders_for_admin(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.get("/compliance/audit-logs")
        assert resp.status_code == 200

    def test_certification_update_is_audited(self, client, seed_admin, db_engine):
        _admin_session(client, seed_admin)
        try:
            client.post("/compliance/certifications/update", data={
                "framework": "GDPR",
                "status": "In Progress",
            }, follow_redirects=True)

            resp = client.get("/compliance/audit-logs?action=compliance")
            body = resp.data.decode()
            assert "compliance.certification_updated" in body
        finally:
            _reset_certification(db_engine, "GDPR")

    def test_pagination_params_do_not_error(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.get("/compliance/audit-logs?page=9999")
        assert resp.status_code == 200

    def test_actor_filter(self, client, seed_admin):
        _admin_session(client, seed_admin)
        resp = client.get("/compliance/audit-logs?actor=test_admin")
        assert resp.status_code == 200
