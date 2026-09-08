from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app import models, schemas


def get_patient(db: Session, patient_id: str) -> Optional[models.Patient]:
    return (
        db.query(models.Patient)
        .filter(models.Patient.patient_id == patient_id, models.Patient.deleted_at.is_(None))
        .first()
    )


def get_patient_by_phone(db: Session, phone_number: str) -> Optional[models.Patient]:
    """Used for the bonus duplicate-caller-detection flow."""
    return (
        db.query(models.Patient)
        .filter(models.Patient.phone_number == phone_number, models.Patient.deleted_at.is_(None))
        .first()
    )


def list_patients(
    db: Session,
    last_name: Optional[str] = None,
    date_of_birth: Optional[str] = None,
    phone_number: Optional[str] = None,
):
    query = db.query(models.Patient).filter(models.Patient.deleted_at.is_(None))
    filters = []
    if last_name:
        filters.append(models.Patient.last_name.ilike(last_name))
    if date_of_birth:
        filters.append(models.Patient.date_of_birth == date_of_birth)
    if phone_number:
        filters.append(models.Patient.phone_number == phone_number)
    if filters:
        query = query.filter(and_(*filters))
    return query.order_by(models.Patient.created_at.desc()).all()


def create_patient(db: Session, patient: schemas.PatientCreate) -> models.Patient:
    db_patient = models.Patient(**patient.model_dump())
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    return db_patient


def update_patient(
    db: Session, patient_id: str, patient_update: schemas.PatientUpdate
) -> Optional[models.Patient]:
    db_patient = get_patient(db, patient_id)
    if not db_patient:
        return None
    update_data = patient_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_patient, field, value)
    db_patient.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_patient)
    return db_patient


def soft_delete_patient(db: Session, patient_id: str) -> Optional[models.Patient]:
    db_patient = get_patient(db, patient_id)
    if not db_patient:
        return None
    db_patient.deleted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_patient)
    return db_patient


def attach_call_summary(db: Session, patient_id: str, summary: str) -> Optional[models.Patient]:
    db_patient = get_patient(db, patient_id)
    if not db_patient:
        return None
    db_patient.last_call_summary = summary[:4000]
    db.commit()
    db.refresh(db_patient)
    return db_patient
