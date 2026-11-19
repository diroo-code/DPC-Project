"""Request and response models.

Input models forbid unknown fields, so a client cannot smuggle `id` or `username` through a
profile update and have it silently ignored in a way that later becomes a bug.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


class ReadyResponse(BaseModel):
    status: Literal["ready", "degraded"]
    database: Literal["ok", "unavailable"]


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    display_name: str
    bio: str | None = None
    avatar_path: str | None = None
    created_at: datetime
    updated_at: datetime


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    bio: str | None = Field(default=None, max_length=500)


class PublicProfileOut(BaseModel):
    """What another user may see. No email, no internal state."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    display_name: str
    bio: str | None = None
    avatar_path: str | None = None
    created_at: datetime


class ErrorResponse(BaseModel):
    detail: str


# ------------------------------------------------------------------ photos


class PhotoOut(BaseModel):
    id: UUID
    owner_id: UUID
    owner_username: str
    caption: str | None = None
    mime_type: str
    size_bytes: int
    visibility: Literal["friends", "owner"]
    created_at: datetime
    comment_count: int = 0
    tags: list[str] = Field(default_factory=list)


class PhotoPage(BaseModel):
    items: list[PhotoOut]
    total: int
    limit: int
    offset: int
    has_more: bool


class SignedUrlOut(BaseModel):
    url: str
    expires_in: int


class TagUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tags: list[str] = Field(default_factory=list, max_length=20)


# ------------------------------------------------------------------ social


class FriendshipOut(BaseModel):
    id: UUID
    requester_id: UUID
    requester_username: str
    addressee_id: UUID
    addressee_username: str
    status: Literal["pending", "accepted", "rejected"]
    created_at: datetime
    responded_at: datetime | None = None


class FriendRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=30)


class FriendOut(BaseModel):
    id: UUID
    friendship_id: UUID
    username: str
    display_name: str


class CommentOut(BaseModel):
    id: UUID
    photo_id: UUID
    author_id: UUID
    author_username: str
    body: str
    created_at: datetime


class CommentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=2000)
