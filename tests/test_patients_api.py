"""
Integration tests for the /patients REST API. Uses a throwaway SQLite file so
these never touch the real data/patients.db.

Run with: pytest -v
"""
import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='.db')}"

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

VALID_PATIENT = {
    "first_name": "Alice",
    "last_name": "Nguyen",
    "date_of_birth": "1992-06-15",
    "sex": "Female",
    "phone_number": "512-555-0100",
    "email": "alice@example.com",
    "address_line_1": "789 Elm St",
    "city": "Austin",
    "state": "tx",
    "zip_code": "78701",
}


def test_create_patient_success():
    res = client.post("/patients", json=VALID_PATIENT)
    assert res.status_code == 201
    body = res.json()
    assert body["error"] is None
    assert body["data"]["first_name"] == "Alice"
    assert body["data"]["phone_number"] == "5125550100"  # normalized to digits
    assert body["data"]["state"] == "TX"  # normalized to uppercase
    assert "patient_id" in body["data"]


def test_create_patient_future_dob_rejected():
    bad = {**VALID_PATIENT, "date_of_birth": "2999-01-01", "phone_number": "5125550101"}
    res = client.post("/patients", json=bad)
    assert res.status_code == 422
    assert "date_of_birth" in res.json()["error"]


def test_create_patient_bad_phone_rejected():
    bad = {**VALID_PATIENT, "phone_number": "123", "email": "x2@example.com"}
    res = client.post("/patients", json=bad)
    assert res.status_code == 422
    assert "phone_number" in res.json()["error"]


def test_create_patient_bad_state_rejected():
    bad = {**VALID_PATIENT, "state": "ZZ", "phone_number": "5125550102"}
    res = client.post("/patients", json=bad)
    assert res.status_code == 422


def test_get_patient_by_id():
    created = client.post("/patients", json={**VALID_PATIENT, "phone_number": "5125550103"}).json()["data"]
    res = client.get(f"/patients/{created['patient_id']}")
    assert res.status_code == 200
    assert res.json()["data"]["patient_id"] == created["patient_id"]


def test_get_patient_not_found():
    res = client.get("/patients/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404
    assert res.json()["data"] is None


def test_list_patients_filter_by_last_name():
    client.post("/patients", json={**VALID_PATIENT, "last_name": "Zephyr", "phone_number": "5125550104"})
    res = client.get("/patients", params={"last_name": "Zephyr"})
    assert res.status_code == 200
    assert all(p["last_name"] == "Zephyr" for p in res.json()["data"])


def test_update_patient_partial():
    created = client.post("/patients", json={**VALID_PATIENT, "phone_number": "5125550105"}).json()["data"]
    res = client.put(f"/patients/{created['patient_id']}", json={"city": "Dallas"})
    assert res.status_code == 200
    assert res.json()["data"]["city"] == "Dallas"
    assert res.json()["data"]["first_name"] == "Alice"  # untouched fields survive


def test_soft_delete_then_hidden_from_list_and_get():
    created = client.post("/patients", json={**VALID_PATIENT, "phone_number": "5125550106"}).json()["data"]
    del_res = client.delete(f"/patients/{created['patient_id']}")
    assert del_res.status_code == 200

    get_res = client.get(f"/patients/{created['patient_id']}")
    assert get_res.status_code == 404

    list_res = client.get("/patients")
    ids = [p["patient_id"] for p in list_res.json()["data"]]
    assert created["patient_id"] not in ids


def test_duplicate_phone_lookup_used_by_voice_agent():
    from app.crud import get_patient_by_phone
    from app.database import SessionLocal

    client.post("/patients", json={**VALID_PATIENT, "phone_number": "5125550199"})
    db = SessionLocal()
    found = get_patient_by_phone(db, "5125550199")
    db.close()
    assert found is not None
    assert found.first_name == "Alice"
