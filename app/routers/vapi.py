"""
Webhook endpoints that Vapi calls into.

Two things land here:

1. `POST /vapi/tool-calls` — fired whenever the assistant invokes one of its Function
   Tools (lookup_patient_by_phone, register_patient, update_patient). This is how the
   voice agent actually reads/writes the database: the LLM decides *when* to call a
   tool, this endpoint does the *real* work and returns a plain-string result the
   model reads back to the caller.

2. `POST /vapi/call-events` — Vapi's generic server-events webhook. We only care about
   `end-of-call-report`, which we use to satisfy the observability requirement (log
   the final collected data payload) and the transcript-linking bonus.

Request/response shapes follow Vapi's Custom (Function) Tools contract as documented
at https://docs.vapi.ai/tools/custom-tools (message.type == "tool-calls",
message.toolCallList[]) and the troubleshooting guide's hard rules: always return
HTTP 200, and every `result` must be a single-line string.
"""
import json
import os
from typing import Any, Optional

from fastapi import APIRouter, Header, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import SessionLocal
from app.logging_config import call_logger, api_logger

router = APIRouter(prefix="/vapi", tags=["vapi"])

WEBHOOK_SECRET = os.getenv("VAPI_WEBHOOK_SECRET", "")


def _authorized(authorization: Optional[str], x_vapi_secret: Optional[str]) -> bool:
    """
    Accepts either header shape Vapi can be configured to send:
      - Authorization: Bearer <secret>   (Bearer Token credential, default header)
      - X-Vapi-Secret: <secret>          (Bearer Token credential, legacy header name)
    If VAPI_WEBHOOK_SECRET is unset, auth is skipped (useful for local `vapi listen` testing).
    """
    if not WEBHOOK_SECRET:
        return True
    if x_vapi_secret == WEBHOOK_SECRET:
        return True
    if authorization and authorization.replace("Bearer ", "", 1) == WEBHOOK_SECRET:
        return True
    return False


def _single_line(s: str) -> str:
    """Vapi silently drops results containing line breaks — flatten to one line."""
    return " ".join(str(s).split())


@router.post("/tool-calls")
async def handle_tool_calls(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_vapi_secret: Optional[str] = Header(None, alias="x-vapi-secret"),
):
    body = await request.json()

    if not _authorized(authorization, x_vapi_secret):
        # Still return 200 with an error result per Vapi's contract — a non-200
        # response is ignored outright rather than surfaced to the assistant.
        return {"results": [{"toolCallId": "unknown", "result": "Unauthorized"}]}

    message = body.get("message", {})
    tool_calls = message.get("toolCallList", [])
    results = []

    db: Session = SessionLocal()
    try:
        for call in tool_calls:
            call_id = call.get("id")
            name = call.get("name")
            args = call.get("arguments") or {}
            try:
                result_text = _dispatch(db, name, args)
            except Exception as exc:  # noqa: BLE001 - last-resort guard so we always answer Vapi
                api_logger.exception("Tool call %s failed", name)
                result_text = f"Sorry, something went wrong saving that ({exc.__class__.__name__}). Please try again."
            results.append({"toolCallId": call_id, "result": _single_line(result_text)})
    finally:
        db.close()

    return {"results": results}


def _dispatch(db: Session, name: str, args: dict) -> str:
    if name == "lookup_patient_by_phone":
        return _lookup_patient_by_phone(db, args)
    if name == "register_patient":
        return _register_patient(db, args)
    if name == "update_patient":
        return _update_patient(db, args)
    return f"Unknown tool '{name}'."


def _lookup_patient_by_phone(db: Session, args: dict) -> str:
    phone = args.get("phone_number", "")
    patient = crud.get_patient_by_phone(db, _digits(phone))
    if not patient:
        return "No existing patient found with that phone number. Proceed with a new registration."
    return (
        f"FOUND_EXISTING patient_id={patient.patient_id} "
        f"first_name={patient.first_name} last_name={patient.last_name} "
        f"date_of_birth={patient.date_of_birth.isoformat()}. "
        "Ask the caller if they'd like to update this record instead of creating a new one."
    )


def _register_patient(db: Session, args: dict) -> str:
    try:
        patient_in = schemas.PatientCreate(**args)
    except ValidationError as e:
        # Fed straight back to the LLM so it knows exactly which field to re-prompt for.
        return f"VALIDATION_ERROR: {_format_validation_error(e)}"

    patient = crud.create_patient(db, patient_in)
    call_logger.info(
        "REGISTERED patient_id=%s payload=%s",
        patient.patient_id,
        json.dumps(args, default=str),
    )
    return (
        f"SUCCESS patient_id={patient.patient_id}. Registration complete for "
        f"{patient.first_name} {patient.last_name}."
    )


def _update_patient(db: Session, args: dict) -> str:
    patient_id = args.pop("patient_id", None)
    if not patient_id:
        return "VALIDATION_ERROR: patient_id is required to update an existing record."
    try:
        patient_in = schemas.PatientUpdate(**args)
    except ValidationError as e:
        return f"VALIDATION_ERROR: {_format_validation_error(e)}"

    patient = crud.update_patient(db, patient_id, patient_in)
    if not patient:
        return f"No patient found with id {patient_id}."
    call_logger.info("UPDATED patient_id=%s payload=%s", patient_id, json.dumps(args, default=str))
    return f"SUCCESS patient_id={patient.patient_id}. Record updated for {patient.first_name} {patient.last_name}."


def _digits(v: str) -> str:
    return "".join(ch for ch in (v or "") if ch.isdigit())[-10:]


def _format_validation_error(e: ValidationError) -> str:
    messages = []
    for err in e.errors():
        field = ".".join(str(x) for x in err["loc"])
        messages.append(f"{field}: {err['msg']}")
    return "; ".join(messages)


@router.post("/call-events")
async def handle_call_events(request: Request):
    """
    Generic Vapi server-events webhook. We only act on `end-of-call-report`:
    log the transcript/summary (observability requirement) and, if the call resulted
    in a registration, attach the summary to that patient record (bonus: call
    transcript linked to patient).
    """
    body = await request.json()
    message = body.get("message", {})

    if message.get("type") == "end-of-call-report":
        call_id = message.get("call", {}).get("id")
        summary = message.get("summary") or message.get("analysis", {}).get("summary")
        ended_reason = message.get("endedReason")
        call_logger.info(
            "CALL_ENDED call_id=%s ended_reason=%s summary=%s",
            call_id,
            ended_reason,
            (summary or "")[:500],
        )
        # Best-effort: if the summary mentions a patient_id we minted during the call,
        # attach it. (The LLM is asked to state the patient_id in its final tool result;
        # a production version would instead pass it back explicitly via a variable.)
        patient_id = _extract_patient_id(json.dumps(message, default=str))
        if patient_id and summary:
            db = SessionLocal()
            try:
                crud.attach_call_summary(db, patient_id, summary)
            finally:
                db.close()

    return {"received": True}


def _extract_patient_id(blob: str) -> Optional[str]:
    import re

    match = re.search(r"patient_id[=:]\s*([0-9a-fA-F-]{36})", blob)
    return match.group(1) if match else None
