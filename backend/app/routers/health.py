"""Liveness and readiness.

`/health` proves the process is up and never touches the database. `/ready` proves the
database is reachable, which is what a deployment platform needs to decide whether traffic
should be sent to this instance.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from .. import db
from ..config import settings
from ..schemas import HealthResponse, ReadyResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service=settings.app_name, version=settings.version)


@router.get("/ready", response_model=ReadyResponse)
def ready(response: Response) -> ReadyResponse:
    try:
        db.ping()
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadyResponse(status="degraded", database="unavailable")
    return ReadyResponse(status="ready", database="ok")
