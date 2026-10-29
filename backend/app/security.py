"""Supabase JWT verification.

Two signing schemes are supported because Supabase projects differ:

* HS256 with the project's legacy JWT secret.
* ES256/RS256/EdDSA with the project's published JWKS, which is the current default for new
  projects. The signing key is selected by the token's `kid`, and PyJWT caches the key set.

Verification is local: no network call per request, and no reliance on the Supabase REST API,
so an expired Supabase outage does not lock the API out.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient

from .config import Settings, settings as default_settings

HS_ALGORITHMS = {"HS256", "HS384", "HS512"}
ASYM_ALGORITHMS = {"ES256", "ES384", "RS256", "RS384", "RS512", "EdDSA"}


class TokenError(Exception):
    """Raised when a bearer token is missing, malformed, expired, or signed with the wrong key."""


@lru_cache(maxsize=4)
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_keys=True, lifespan=300)


def decode_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or default_settings
    if not token or not token.strip():
        raise TokenError("empty token")

    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise TokenError("malformed token header") from exc

    algorithm = header.get("alg", "")

    if algorithm in HS_ALGORITHMS:
        if not settings.supabase_jwt_secret:
            raise TokenError("token uses a shared secret but SUPABASE_JWT_SECRET is not configured")
        key: Any = settings.supabase_jwt_secret
        allowed = [algorithm]
    elif algorithm in ASYM_ALGORITHMS:
        if not settings.supabase_jwks_url:
            raise TokenError("token uses asymmetric signing but no JWKS URL is configured")
        try:
            key = _jwks_client(settings.supabase_jwks_url).get_signing_key_from_jwt(token).key
        except jwt.PyJWTError as exc:
            raise TokenError("signing key not found for token") from exc
        allowed = [algorithm]
    else:
        raise TokenError(f"unsupported signing algorithm: {algorithm or 'none'}")

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=allowed,
            audience=settings.jwt_audience,
            options={"require": ["exp", "sub"], "verify_aud": True},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("token expired") from exc
    except jwt.InvalidAudienceError as exc:
        raise TokenError("token audience mismatch") from exc
    except jwt.PyJWTError as exc:
        raise TokenError("token verification failed") from exc

    if not claims.get("sub"):
        raise TokenError("token has no subject")
    return claims
