"""Tests for the auth gate on POST /admin_action, blueprints/employees.py.

/admin_action used to have an action="register" branch that created new
employees; that branch was removed at some point (registration moved to
its own dedicated POST /add_employee_page, covered by
tests/test_employees_routes.py) but nothing here was updated to match --
every "register" test in this file was silently exercising a dead code
path (action="register" falls through to a no-op redirect: no employee
created, no validation, no flash message) rather than the real feature.
Removed rather than ported 1:1, since /add_employee_page's validation
model differs in real ways from what these tests assumed (e.g. duplicate
IDs are always auto-reassigned now, including purely numeric ones, never
outright rejected; there's no name-length rejection at all).

What's left is only the auth-gate coverage, which never depended on the
"register" branch existing -- @role_required("admin") rejects an
unauthenticated/wrong-role caller before the action dispatch is ever
reached.
"""


def test_anonymous_request_rejected(client):
    resp = client.post("/admin_action", data={"action": "register"}, follow_redirects=False)
    assert resp.status_code in (302, 401)
    assert "/admin-login" in resp.headers.get("Location", "")


def test_employee_session_rejected(client, seed_employee):
    with client.session_transaction() as sess:
        sess["employee_id"] = seed_employee["employee_id"]
    resp = client.post("/admin_action", data={"action": "register"}, follow_redirects=False)
    assert resp.status_code in (302, 401)
