import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Date, DateTime, Enum
import enum

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Sex(str, enum.Enum):
    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Other"
    DECLINE = "Decline to Answer"


class Patient(Base):
    """
    Standard minimum demographic dataset for patient registration.
    Column names/types map 1:1 to the spec in the assessment doc.
    """
    __tablename__ = "patients"

    patient_id = Column(String(36), primary_key=True, default=_uuid)

    # Required
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    sex = Column(Enum(Sex), nullable=False)
    phone_number = Column(String(10), nullable=False, index=True)  # stored as 10 raw digits
    address_line_1 = Column(String(200), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(2), nullable=False)
    zip_code = Column(String(10), nullable=False)  # 5 digits or ZIP+4 (XXXXX-XXXX)

    # Optional
    email = Column(String(254), nullable=True)
    address_line_2 = Column(String(200), nullable=True)
    insurance_provider = Column(String(150), nullable=True)
    insurance_member_id = Column(String(50), nullable=True)
    preferred_language = Column(String(50), nullable=True, default="English")
    emergency_contact_name = Column(String(150), nullable=True)
    emergency_contact_phone = Column(String(10), nullable=True)

    # Auto
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)  # soft delete marker

    # Bonus: last call transcript/summary, linked 1:1 to the patient it registered
    last_call_summary = Column(String(4000), nullable=True)
