"""Coverage tests for blueprints/onboarding.py.
Targets: onboarding, template CRUD, task CRUD, assign, detail,
offer_letter routes, offer_letter_pdf/respond with invalid tokens.
"""
import pytest


def _admin_session(client, seed_admin):
    client.post("/login", data={
        "identifier": seed_admin["username"],
        "password":   seed_admin["password"],
    })
    return client


def _seed_template(db_engine, name="CI Onboard Template"):
    cur = db_engine.cursor()
    cur.execute(
        "INSERT INTO onboarding_templates (name, description, is_active) "
        "VALUES (%s,'CI test template',1) RETURNING id",
        (name,)
    )
    tid = cur.fetchone()[0]
    cur.close()
    return tid


def _seed_onboarding(db_engine, emp_id, template_id):
    import datetime
    cur = db_engine.cursor()
    cur.execute(
        "INSERT INTO employee_onboarding (employee_id, template_id, assigned_date, due_date, status) "
        "VALUES (%s,%s,%s,%s,'In Progress') RETURNING id",
        (emp_id, template_id, datetime.date.today(), datetime.date.today())
    )
    ob_id = cur.fetchone()[0]
    cur.close()
    return ob_id


# ── onboarding page ───────────────────────────────────────────────────────────

class TestOnboardingPage:

    def test_unauthenticated_redirects(self, client):
        rv = client.get("/onboarding")
        assert rv.status_code == 302

    def test_renders_for_admin(self, client, seed_admin):
        _admin_session(client, seed_admin)
        rv = client.get("/onboarding")
        assert rv.status_code == 200

    def test_active_tab(self, client, seed_admin):
        _admin_session(client, seed_admin)
        rv = client.get("/onboarding?tab=active")
        assert rv.status_code == 200

    def test_templates_tab(self, client, seed_admin):
        _admin_session(client, seed_admin)
        rv = client.get("/onboarding?tab=templates")
        assert rv.status_code == 200


# ── template CRUD ─────────────────────────────────────────────────────────────

class TestOnboardingTemplateSave:

    def test_unauthenticated_redirects(self, client):
        rv = client.post("/onboarding_template_save", data={"name": "x"})
        assert rv.status_code == 302

    def test_creates_new_template(self, client, seed_admin, db_engine):
        _admin_session(client, seed_admin)
        rv = client.post("/onboarding_template_save", data={
            "name":        "CI New Template",
            "description": "CI test",
            "role":        "",
            "is_active":   "1",
        })
        assert rv.status_code == 302
        cur = db_engine.cursor()
        cur.execute("SELECT id FROM onboarding_templates WHERE name='CI New Template'")
        row = cur.fetchone()
        if row:
            cur.execute("DELETE FROM onboarding_templates WHERE id=%s", (row[0],))
        cur.close()

    def test_updates_existing_template(self, client, seed_admin, db_engine):
        tid = _seed_template(db_engine, "CI Update Me")
        _admin_session(client, seed_admin)
        rv = client.post("/onboarding_template_save", data={
            "template_id": str(tid),
            "name":        "CI Updated Name",
            "description": "Updated desc",
            "is_active":   "1",
        })
        assert rv.status_code == 302
        cur = db_engine.cursor()
        cur.execute("DELETE FROM onboarding_templates WHERE id=%s", (tid,))
        cur.close()


class TestOnboardingTemplateDelete:

    def test_unauthenticated_redirects(self, client):
        rv = client.post("/onboarding_template_delete", data={"template_id": "1"})
        assert rv.status_code == 302

    def test_deletes_existing_template(self, client, seed_admin, db_engine):
        tid = _seed_template(db_engine, "CI Delete Me")
        _admin_session(client, seed_admin)
        rv = client.post("/onboarding_template_delete", data={"template_id": str(tid)})
        assert rv.status_code == 302

    def test_nonexistent_template_redirects(self, client, seed_admin):
        _admin_session(client, seed_admin)
        rv = client.post("/onboarding_template_delete", data={"template_id": "9999999"})
        assert rv.status_code == 302


class TestOnboardingTemplateDuplicate:

    def test_unauthenticated_redirects(self, client):
        rv = client.post("/onboarding_template_duplicate", data={"template_id": "1"})
        assert rv.status_code == 302

    def test_duplicates_template(self, client, seed_admin, db_engine):
        tid = _seed_template(db_engine, "CI To Duplicate")
        _admin_session(client, seed_admin)
        rv = client.post("/onboarding_template_duplicate", data={"template_id": str(tid)})
        assert rv.status_code == 302
        cur = db_engine.cursor()
        cur.execute("DELETE FROM onboarding_templates WHERE name LIKE 'CI To Duplicate%'")
        cur.close()


# ── task CRUD ─────────────────────────────────────────────────────────────────

class TestOnboardingTaskSave:

    def test_unauthenticated_redirects(self, client):
        rv = client.post("/onboarding_task_save", data={})
        assert rv.status_code == 302

    def test_creates_task(self, client, seed_admin, db_engine):
        tid = _seed_template(db_engine, "CI Task Template")
        _admin_session(client, seed_admin)
        rv = client.post("/onboarding_task_save", data={
            "template_id": str(tid),
            "title":       "CI Task 1",
            "description": "Do the thing",
            "due_days":    "3",
            "assigned_to": "HR",
        })
        assert rv.status_code == 302
        cur = db_engine.cursor()
        cur.execute("DELETE FROM onboarding_template_tasks WHERE template_id=%s", (tid,))
        cur.execute("DELETE FROM onboarding_templates WHERE id=%s", (tid,))
        cur.close()


class TestOnboardingTaskDelete:

    def test_unauthenticated_redirects(self, client):
        rv = client.post("/onboarding_task_delete", data={"task_id": "1"})
        assert rv.status_code == 302

    def test_nonexistent_task_redirects(self, client, seed_admin):
        _admin_session(client, seed_admin)
        rv = client.post("/onboarding_task_delete", data={"task_id": "9999999"})
        assert rv.status_code == 302


# ── template detail ───────────────────────────────────────────────────────────

class TestOnboardingTemplateDetail:

    def test_unauthenticated_redirects(self, client):
        rv = client.get("/onboarding_template_detail/1")
        assert rv.status_code == 302

    def test_renders_for_existing_template(self, client, seed_admin, db_engine):
        tid = _seed_template(db_engine, "CI Detail Template")
        _admin_session(client, seed_admin)
        rv = client.get(f"/onboarding_template_detail/{tid}")
        assert rv.status_code == 200
        cur = db_engine.cursor()
        cur.execute("DELETE FROM onboarding_templates WHERE id=%s", (tid,))
        cur.close()

    def test_nonexistent_returns_200_or_redirect(self, client, seed_admin):
        _admin_session(client, seed_admin)
        rv = client.get("/onboarding_template_detail/9999999")
        assert rv.status_code in (200, 302, 404)


# ── onboarding_assign ─────────────────────────────────────────────────────────

class TestOnboardingAssign:

    def test_unauthenticated_redirects(self, client):
        rv = client.post("/onboarding_assign", data={})
        assert rv.status_code == 302

    def test_assigns_template_to_employee(self, client, seed_admin, seed_employee, db_engine):
        tid = _seed_template(db_engine, "CI Assign Template")
        _admin_session(client, seed_admin)
        rv = client.post("/onboarding_assign", data={
            "employee_id": seed_employee["employee_id"],
            "template_id": str(tid),
            "due_days":    "30",
        })
        assert rv.status_code == 302
        cur = db_engine.cursor()
        cur.execute(
            "DELETE FROM employee_onboarding WHERE employee_id=%s AND template_id=%s",
            (seed_employee["employee_id"], tid)
        )
        cur.execute("DELETE FROM onboarding_templates WHERE id=%s", (tid,))
        cur.close()


# ── onboarding_detail ─────────────────────────────────────────────────────────

class TestOnboardingDetail:

    def test_unauthenticated_redirects(self, client):
        rv = client.get("/onboarding_detail/1")
        assert rv.status_code == 302

    def test_renders_for_existing(self, client, seed_admin, seed_employee, db_engine):
        tid = _seed_template(db_engine, "CI Detail Ob Template")
        ob_id = _seed_onboarding(db_engine, seed_employee["employee_id"], tid)
        _admin_session(client, seed_admin)
        rv = client.get(f"/onboarding_detail/{ob_id}")
        assert rv.status_code == 200
        cur = db_engine.cursor()
        cur.execute("DELETE FROM employee_onboarding WHERE id=%s", (ob_id,))
        cur.execute("DELETE FROM onboarding_templates WHERE id=%s", (tid,))
        cur.close()


# ── offer_letter_pdf / offer_letter_respond (invalid tokens) ──────────────────

class TestOfferLetterPublicRoutes:

    def test_offer_letter_pdf_invalid_token_returns_error(self, client):
        rv = client.get("/offer_letter_pdf/invalid_token_xyz")
        assert rv.status_code in (200, 302, 400, 404)

    def test_offer_letter_respond_invalid_token(self, client):
        rv = client.get("/offer_letter_respond/invalid_token_xyz/accept")
        assert rv.status_code in (200, 302, 400, 404)

    def test_offer_letter_respond_reject(self, client):
        rv = client.get("/offer_letter_respond/invalid_token_xyz/reject")
        assert rv.status_code in (200, 302, 400, 404)


# ── export_onboarding_csv ─────────────────────────────────────────────────────

class TestExportOnboardingCsv:

    def test_unauthenticated_redirects(self, client):
        rv = client.get("/export_onboarding_csv")
        assert rv.status_code == 302

    def test_returns_csv_for_admin(self, client, seed_admin):
        _admin_session(client, seed_admin)
        rv = client.get("/export_onboarding_csv")
        assert rv.status_code == 200
        assert b"employee" in rv.data.lower() or rv.content_type.startswith("text/csv")
