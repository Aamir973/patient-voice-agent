from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.responses import envelope
from app.logging_config import api_logger

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("")
def list_patients(
    last_name: Optional[str] = Query(None),
    date_of_birth: Optional[str] = Query(None),
    phone_number: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    patients = crud.list_patients(db, last_name, date_of_birth, phone_number)
    data = [schemas.PatientOut.model_validate(p).model_dump(mode="json") for p in patients]
    return envelope(data=data)


@router.get("/{patient_id}")
def get_patient(patient_id: str, db: Session = Depends(get_db)):
    patient = crud.get_patient(db, patient_id)
    if not patient:
        return envelope(error=f"Patient {patient_id} not found", status_code=404)
    return envelope(data=schemas.PatientOut.model_validate(patient).model_dump(mode="json"))


@router.post("", status_code=201)
def create_patient(payload: dict, db: Session = Depends(get_db)):
    # Validate manually (rather than via the endpoint signature) so we control the
    # error envelope shape/status code (422) instead of FastAPI's default shape.
    try:
        patient_in = schemas.PatientCreate(**payload)
    except ValidationError as e:
        return envelope(error=_format_validation_error(e), status_code=422)

    patient = crud.create_patient(db, patient_in)
    api_logger.info("Created patient %s (%s %s)", patient.patient_id, patient.first_name, patient.last_name)
    return envelope(data=schemas.PatientOut.model_validate(patient).model_dump(mode="json"), status_code=201)


@router.put("/{patient_id}")
def update_patient(patient_id: str, payload: dict, db: Session = Depends(get_db)):
    try:
        patient_in = schemas.PatientUpdate(**payload)
    except ValidationError as e:
        return envelope(error=_format_validation_error(e), status_code=422)

    patient = crud.update_patient(db, patient_id, patient_in)
    if not patient:
        return envelope(error=f"Patient {patient_id} not found", status_code=404)
    api_logger.info("Updated patient %s", patient_id)
    return envelope(data=schemas.PatientOut.model_validate(patient).model_dump(mode="json"))


@router.delete("/{patient_id}")
def delete_patient(patient_id: str, db: Session = Depends(get_db)):
    patient = crud.soft_delete_patient(db, patient_id)
    if not patient:
        return envelope(error=f"Patient {patient_id} not found", status_code=404)
    api_logger.info("Soft-deleted patient %s", patient_id)
    return envelope(data={"patient_id": patient_id, "deleted_at": patient.deleted_at.isoformat()})


def _format_validation_error(e: ValidationError) -> str:
    messages = []
    for err in e.errors():
        field = ".".join(str(x) for x in err["loc"])
        messages.append(f"{field}: {err['msg']}")
    return "; ".join(messages)
