"""Run once to populate a couple of demo patients: `python seed_data.py`"""
from datetime import date

from app import models, crud, schemas
from app.database import SessionLocal, engine

models.Base.metadata.create_all(bind=engine)

db = SessionLocal()

seed_patients = [
    schemas.PatientCreate(
        first_name="Jane",
        last_name="Doe",
        date_of_birth=date(1990, 4, 12),
        sex="Female",
        phone_number="5551234567",
        email="jane.doe@example.com",
        address_line_1="123 Main St",
        address_line_2="Apt 4B",
        city="Austin",
        state="TX",
        zip_code="78701",
        insurance_provider="BlueCross BlueShield",
        insurance_member_id="BCBS123456",
        preferred_language="English",
        emergency_contact_name="John Doe",
        emergency_contact_phone="5559876543",
    ),
    schemas.PatientCreate(
        first_name="Carlos",
        last_name="Martinez",
        date_of_birth=date(1985, 11, 2),
        sex="Male",
        phone_number="5552223333",
        address_line_1="456 Oak Ave",
        city="Phoenix",
        state="AZ",
        zip_code="85001",
        preferred_language="Spanish",
    ),
]

for p in seed_patients:
    existing = crud.get_patient_by_phone(db, p.phone_number)
    if existing:
        print(f"Skipping {p.first_name} {p.last_name} (already exists)")
        continue
    created = crud.create_patient(db, p)
    print(f"Seeded {created.first_name} {created.last_name} -> {created.patient_id}")

db.close()
