"""Authentication endpoints.

Registration, login and logout are handled by Supabase Auth on the client. The backend never
sees a password. Its job is to verify the resulting token and to expose the caller's profile.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, status

from .. import db
from ..deps import CurrentUser, get_current_user
from ..schemas import ProfileOut, ProfileUpdate

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

PROFILE_COLUMNS = """
    id, username, display_name, bio, avatar_path, created_at, updated_at
"""


def _fallback_username(email: str | None, user_id: str) -> str:
    base = (email or "user").split("@")[0].lower()
    base = re.sub(r"[^a-z0-9_]", "", base)[:20] or "user"
    if len(base) < 3:
        base = f"user{base}"
    return f"{base}_{user_id[:4]}"


def _fetch_profile(user_id: str) -> dict | None:
    return db.fetch_one(
        f"select {PROFILE_COLUMNS} from public.profiles where id = %s",
        (user_id,),
    )


def _ensure_profile(user: CurrentUser) -> dict:
    """Return the profile, creating it if the database trigger has not done so.

    The trigger is the normal path. This fallback matters for accounts that predate the
    trigger, and it keeps the endpoint useful when a project is provisioned before the
    migration is applied.
    """
    profile = _fetch_profile(str(user.id))
    if profile is not None:
        return profile

    username = _fallback_username(user.email, str(user.id))
    display_name = (user.email or "New user").split("@")[0]

    db.execute(
        """
        insert into public.profiles (id, username, display_name)
        values (%s, %s, %s)
        on conflict (id) do nothing
        """,
        (str(user.id), username, display_name),
    )
    profile = _fetch_profile(str(user.id))
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="profile could not be created",
        )
    return profile


@router.get("/me", response_model=ProfileOut)
def read_me(user: CurrentUser = Depends(get_current_user)) -> dict:
    return _ensure_profile(user)


# The brief names this route GET /me, while the versioned contract uses /api/v1/auth/me.
# Both are served from the same handler so there is no second implementation to drift.
brief_router = APIRouter(tags=["auth"])


@brief_router.get("/me", response_model=ProfileOut)
def read_me_short(user: CurrentUser = Depends(get_current_user)) -> dict:
    return _ensure_profile(user)


@router.patch("/me", response_model=ProfileOut)
def update_me(
    payload: ProfileUpdate,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    provided = payload.model_fields_set
    if not provided:
        return _ensure_profile(user)

    assignments: list[str] = []
    params: list[object] = []

    if "display_name" in provided:
        if payload.display_name is None:
            raise HTTPException(
                status_code=422,
                detail="display_name cannot be null",
            )
        assignments.append("display_name = %s")
        params.append(payload.display_name.strip())

    if "bio" in provided:
        assignments.append("bio = %s")
        params.append(payload.bio.strip() if payload.bio else None)

    _ensure_profile(user)
    params.append(str(user.id))

    row = db.fetch_one(
        f"""
        update public.profiles
           set {', '.join(assignments)}
         where id = %s
        returning {PROFILE_COLUMNS}
        """,
        tuple(params),
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="profile not found",
        )
    return row
