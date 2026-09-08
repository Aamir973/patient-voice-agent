"""
Pydantic schemas. This is where server-side validation actually lives (the spec is
explicit that the API must validate independently of the voice agent — a caller's
speech-to-text transcript is not a trusted input).
"""
import re
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator, ConfigDict

VALID_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN",
    "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV",
    "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN",
    "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC", "PR", "GU", "VI",
}

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z'\-]{0,49}$")
ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")


def _clean_phone(v: str, field_name: str) -> str:
    digits = re.sub(r"\D", "", v or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise ValueError(f"{field_name} must be a valid 10-digit U.S. phone number")
    return digits


class PatientBase(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    sex: str
    phone_number: str
    address_line_1: str
    city: str
    state: str
    zip_code: str

    email: Optional[EmailStr] = None
    address_line_2: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: Optional[str] = "English"
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, v, info):
        if not v or not NAME_RE.match(v):
            raise ValueError(
                f"{info.field_name} must be 1-50 alphabetic characters "
                "(hyphens and apostrophes allowed)"
            )
        return v.strip()

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: date):
        if v > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        if v.year < 1900:
            raise ValueError("date_of_birth is not plausible")
        return v

    @field_validator("sex")
    @classmethod
    def validate_sex(cls, v: str):
        allowed = {"Male", "Female", "Other", "Decline to Answer"}
        if v not in allowed:
            raise ValueError(f"sex must be one of {sorted(allowed)}")
        return v

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str):
        return _clean_phone(v, "phone_number")

    @field_validator("emergency_contact_phone")
    @classmethod
    def validate_emergency_phone(cls, v):
        if v in (None, ""):
            return None
        return _clean_phone(v, "emergency_contact_phone")

    @field_validator("city")
    @classmethod
    def validate_city(cls, v: str):
        if not (1 <= len(v.strip()) <= 100):
            raise ValueError("city must be 1-100 characters")
        return v.strip()

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str):
        v = v.strip().upper()
        if v not in VALID_STATES:
            raise ValueError("state must be a valid 2-letter U.S. state/territory abbreviation")
        return v

    @field_validator("zip_code")
    @classmethod
    def validate_zip(cls, v: str):
        v = v.strip()
        if not ZIP_RE.match(v):
            raise ValueError("zip_code must be 5 digits or ZIP+4 (e.g. 12345 or 12345-6789)")
        return v

    @field_validator("address_line_1")
    @classmethod
    def validate_address(cls, v: str):
        if not v or not v.strip():
            raise ValueError("address_line_1 is required")
        return v.strip()


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    """All fields optional -> supports partial updates via PUT."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    sex: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, v, info):
        if v is None:
            return v
        if not NAME_RE.match(v):
            raise ValueError(
                f"{info.field_name} must be 1-50 alphabetic characters "
                "(hyphens and apostrophes allowed)"
            )
        return v.strip()

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v):
        if v is None:
            return v
        if v > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        return v

    @field_validator("sex")
    @classmethod
    def validate_sex(cls, v):
        if v is None:
            return v
        allowed = {"Male", "Female", "Other", "Decline to Answer"}
        if v not in allowed:
            raise ValueError(f"sex must be one of {sorted(allowed)}")
        return v

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v):
        if v is None:
            return v
        return _clean_phone(v, "phone_number")

    @field_validator("emergency_contact_phone")
    @classmethod
    def validate_emergency_phone(cls, v):
        if v in (None, ""):
            return v
        return _clean_phone(v, "emergency_contact_phone")

    @field_validator("state")
    @classmethod
    def validate_state(cls, v):
        if v is None:
            return v
        v = v.strip().upper()
        if v not in VALID_STATES:
            raise ValueError("state must be a valid 2-letter U.S. state/territory abbreviation")
        return v

    @field_validator("zip_code")
    @classmethod
    def validate_zip(cls, v):
        if v is None:
            return v
        if not ZIP_RE.match(v.strip()):
            raise ValueError("zip_code must be 5 digits or ZIP+4 (e.g. 12345 or 12345-6789)")
        return v.strip()


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: str
    first_name: str
    last_name: str
    date_of_birth: date
    sex: str
    phone_number: str
    email: Optional[str] = None
    address_line_1: str
    address_line_2: Optional[str] = None
    city: str
    state: str
    zip_code: str
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
