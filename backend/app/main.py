"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .config import settings
from .routers import auth, health, photos, profiles, social
from .storage import storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    db.close_pool()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["X-Request-Id"],
        max_age=600,
    )

    # Versioned contract used by the frontend and the tests.
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(photos.router, prefix="/api/v1")
    app.include_router(social.router, prefix="/api/v1")
    app.include_router(profiles.router, prefix="/api/v1")

    # The brief's literal paths. Same handlers, no second implementation, hidden from the schema so
    # the published contract stays single and unambiguous.
    app.include_router(auth.brief_router, include_in_schema=False)
    app.include_router(photos.router, include_in_schema=False)
    app.include_router(social.router, include_in_schema=False)
    app.include_router(profiles.router, include_in_schema=False)

    @app.get("/media/{key:path}", tags=["media"])
    def serve_media(key: str, exp: int, sig: str):
        """Local storage driver only. Serves an object if the signed URL is valid and unexpired.

        This mirrors Supabase signed URL semantics: the URL is the capability, so authorisation
        happens before signing, not here. The Supabase driver never routes through this endpoint.
        """
        from fastapi import HTTPException
        from fastapi.responses import Response as RawResponse

        verifier = getattr(storage, "verify", None)
        if verifier is None:
            raise HTTPException(404, "not found")
        verifier(key, exp, sig)
        try:
            data = storage.read(key)
        except Exception:
            raise HTTPException(404, "object not found")
        media_type = "image/jpeg"
        if key.endswith(".png"):
            media_type = "image/png"
        elif key.endswith(".webp"):
            media_type = "image/webp"
        return RawResponse(content=data, media_type=media_type)

    @app.get("/", tags=["health"])
    def root() -> dict[str, str]:
        return {"service": settings.app_name, "version": settings.version, "docs": "/docs"}

    return app


app = create_app()
