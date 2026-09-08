"""Every API response uses the same envelope: {"data": ..., "error": null}."""
from typing import Any, Optional

from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder


def envelope(data: Any = None, error: Optional[str] = None, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"data": jsonable_encoder(data), "error": error},
    )
