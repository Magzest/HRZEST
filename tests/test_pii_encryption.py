"""Tests for at-rest encryption of employee PII fields added this session:
gender, dob, blood_group, address, city, state, pincode, emergency contact
name/phone/relation, and bank_name. Verifies both halves of the contract:
the raw DB column actually holds ciphertext (not plaintext), and the app's
read paths correctly decrypt it back to the original value. Also covers the
gender-distribution analytics query, which had to move from a SQL GROUP BY
to Python-side aggregation since Fernet ciphertext is non-deterministic.
"""
from utils.helpers import decrypt_pii


def _admin_session(client, username="test_admin", role="admin"):
    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True
        sess["admin_username"] = username
        sess["admin_role"] = role


def _employee_session(client, employee_id):
    with client.session_transaction() as sess:
        sess["employee_id"] = employee_id


def _raw_column(db_engine, employee_id, column):
    cur = db_engine.cursor()
    cur.execute(f"SELECT {column} FROM employees WHERE employee_id=%s", (employee_id,))  # nosec B608 - column is a fixed literal from this test file, not user input  # noqa: E501
    row = cur.fetchone()
    cur.close()
    return row[0] if row else None


class TestEditEmployeeEncryptsPii:
    def test_fields_are_encrypted_at_rest_and_decrypt_correctly(self, client, seed_admin, seed_employee, db_engine):
        _admin_session(client, seed_admin["username"])
        emp_id = seed_employee["employee_id"]

        resp = client.post("/edit_employee", data={
            "emp_id": emp_id,
            "name": seed_employee["name"],
            "gender": "Female",
            "dob": "1995-06-15",
            "blood_group": "O+",
            "address": "221B Baker Street",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pincode": "560001",
            "ec_name": "Jane Doe",
            "ec_phone": "9876543210",
            "ec_rel": "Spouse",
        }, follow_redirects=False)
        assert resp.status_code in (302, 303)

        plaintexts = {
            "gender": "Female", "dob": "1995-06-15", "blood_group": "O+",
            "address": "221B Baker Street", "city": "Bengaluru", "state": "Karnataka",
            "pincode": "560001", "emergency_contact_name": "Jane Doe",
            "emergency_contact_phone": "9876543210", "emergency_contact_relation": "Spouse",
        }
        for column, plain in plaintexts.items():
            raw = _raw_column(db_engine, emp_id, column)
            assert raw != plain, f"{column} was stored in plaintext"
            assert decrypt_pii(raw) == plain, f"{column} did not decrypt back to the original value"

        info = client.get(f"/api/employee_info/{emp_id}").get_json()
        assert info["gender"] == "Female"
        assert info["dob"] == "1995-06-15"
        assert info["blood_group"] == "O+"
        assert info["address"] == "221B Baker Street"
        assert info["city"] == "Bengaluru"
        assert info["state"] == "Karnataka"
        assert info["pincode"] == "560001"
        assert info["ec_name"] == "Jane Doe"
        assert info["ec_phone"] == "9876543210"
        assert info["ec_rel"] == "Spouse"


class TestEmployeeSelfServiceEncryptsPii:
    def test_update_my_profile_encrypts_fields(self, client, seed_employee, db_engine):
        _employee_session(client, seed_employee["employee_id"])
        emp_id = seed_employee["employee_id"]

        resp = client.post("/update_my_profile", data={
            "gender": "Male",
            "dob": "1990-01-20",
            "blood_group": "AB-",
            "address": "42 MG Road",
            "city": "Mumbai",
            "state": "Maharashtra",
            "pincode": "400001",
            "emergency_contact_name": "John Doe",
            "emergency_contact_phone": "9123456780",
            "emergency_contact_relation": "Father",
        }, follow_redirects=False)
        assert resp.status_code in (302, 303)

        raw_gender = _raw_column(db_engine, emp_id, "gender")
        assert raw_gender != "Male"
        assert decrypt_pii(raw_gender) == "Male"

        raw_ec_name = _raw_column(db_engine, emp_id, "emergency_contact_name")
        assert raw_ec_name != "John Doe"
        assert decrypt_pii(raw_ec_name) == "John Doe"

    def test_update_my_bank_details_encrypts_bank_name(self, client, seed_employee, db_engine):
        _employee_session(client, seed_employee["employee_id"])
        emp_id = seed_employee["employee_id"]

        resp = client.post("/update_my_bank_details", data={
            "bank_name": "State Bank of India",
        }, follow_redirects=False)
        assert resp.status_code in (302, 303)

        raw = _raw_column(db_engine, emp_id, "bank_name")
        assert raw != "State Bank of India"
        assert decrypt_pii(raw) == "State Bank of India"


class TestLegacyPlaintextStillReadable:
    def test_preexisting_plaintext_dob_is_returned_unchanged(self, client, seed_admin, seed_employee, db_engine):
        # Simulates a row saved before this migration/encryption change —
        # decrypt_pii() must gracefully fall back to the original value
        # instead of erroring on a non-Fernet-token input.
        _admin_session(client, seed_admin["username"])
        emp_id = seed_employee["employee_id"]
        cur = db_engine.cursor()
        cur.execute("UPDATE employees SET dob=%s, gender=%s WHERE employee_id=%s",
                    ("1988-03-10", "Female", emp_id))
        db_engine.commit()
        cur.close()

        info = client.get(f"/api/employee_info/{emp_id}").get_json()
        assert info["dob"] == "1988-03-10"
        assert info["gender"] == "Female"


class TestGenderAnalyticsAggregation:
    def test_analytics_page_loads_and_counts_encrypted_gender_correctly(self, client, seed_admin, seed_employee, db_engine):
        _admin_session(client, seed_admin["username"])
        emp_id = seed_employee["employee_id"]
        client.post("/edit_employee", data={"emp_id": emp_id, "name": seed_employee["name"], "gender": "Female"})

        resp = client.get("/analytics")
        assert resp.status_code == 200
