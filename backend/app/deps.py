"""FastAPI dependencies for authentication and authorisation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import Header, HTTPException, status

from .security import TokenError, decode_token


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    email: str | None
    role: str | None
    claims: dict[str, Any]


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authorization header must be 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token.strip()


def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    """Resolve the caller from the bearer token, rejecting anything unverified."""
    token = _extract_bearer(authorization)
    try:
        claims = decode_token(token)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    try:
        user_id = UUID(str(claims["sub"]))
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token subject is not a valid user id",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return CurrentUser(
        id=user_id,
        email=claims.get("email"),
        role=claims.get("role"),
        claims=claims,
    )
