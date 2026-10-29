"""Profile endpoints.

The brief requires GET /profiles/{user_id}. Profiles are readable by any authenticated user because
friend discovery needs to resolve a username, but the response is deliberately limited to public
fields. Email lives in auth.users and is never exposed here.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from .. import db
from ..deps import CurrentUser, get_current_user
from ..schemas import PublicProfileOut

router = APIRouter(tags=["profiles"])

PUBLIC_COLUMNS = "id, username, display_name, bio, avatar_path, created_at"


@router.get("/profiles/{user_id}", response_model=PublicProfileOut)
def get_profile(
    user_id: uuid.UUID, user: CurrentUser = Depends(get_current_user)
) -> PublicProfileOut:
    row = db.fetch_one(
        f"select {PUBLIC_COLUMNS} from public.profiles where id = %s", (str(user_id),)
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "profile not found")
    return PublicProfileOut(**row)
