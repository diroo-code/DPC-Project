"""Application configuration, read from the environment only.

Secrets never appear in code. `.env` is loaded for local development and is git-ignored.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _split_csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    app_name: str = "TEB3033 Photo Sharing API"
    version: str = "0.1.0"
    environment: str = "development"

    # PostgreSQL. Supabase provides this as the direct connection string.
    database_url: str | None = None

    # Supabase project settings. Used for Storage signing in later phases.
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None

    # Token verification. Supabase projects use either a legacy shared secret (HS256)
    # or asymmetric signing keys published as a JWKS (ES256/RS256). Support both.
    supabase_jwt_secret: str | None = None
    supabase_jwks_url: str | None = None
    jwt_audience: str = "authenticated"

    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")

    # Storage. "local" is a test and development driver; "supabase" is the real one.
    storage_backend: str = "local"
    storage_local_root: str = "var/storage"
    storage_signing_secret: str = "development-only-signing-secret"
    signed_url_ttl_seconds: int = 60

    @classmethod
    def from_env(cls) -> "Settings":
        project_url = os.environ.get("SUPABASE_URL", "").rstrip("/") or None
        jwks = os.environ.get("SUPABASE_JWKS_URL")
        if not jwks and project_url:
            jwks = f"{project_url}/auth/v1/.well-known/jwks.json"

        return cls(
            environment=os.environ.get("APP_ENV", "development"),
            database_url=os.environ.get("DATABASE_URL") or None,
            supabase_url=project_url,
            supabase_anon_key=os.environ.get("SUPABASE_ANON_KEY") or None,
            supabase_service_role_key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or None,
            supabase_jwt_secret=os.environ.get("SUPABASE_JWT_SECRET") or None,
            supabase_jwks_url=jwks or None,
            jwt_audience=os.environ.get("SUPABASE_JWT_AUDIENCE", "authenticated"),
            cors_origins=_split_csv(os.environ.get("CORS_ORIGINS"))
            or ("http://localhost:5173", "http://127.0.0.1:5173"),
            storage_backend=os.environ.get("STORAGE_BACKEND", "local"),
            storage_local_root=os.environ.get("STORAGE_LOCAL_ROOT", "var/storage"),
            storage_signing_secret=os.environ.get(
                "STORAGE_SIGNING_SECRET", "development-only-signing-secret"
            ),
            signed_url_ttl_seconds=int(os.environ.get("SIGNED_URL_TTL_SECONDS", "60")),
        )


settings = Settings.from_env()
