"""Photo endpoints: upload, feed, retrieval, deletion and signed URL issuance.

Permission rules, all enforced here and mirrored by RLS:

* Upload is authenticated and always owned by the caller.
* Reading a photo requires ownership, or friendship when visibility is `friends`. A caller who may
  not read a photo receives 404, not 403, so the API does not confirm that an unreadable id exists.
* Deleting requires ownership. A non-owner who can see the photo receives 403; a caller who cannot
  see it receives 404.
* A signed URL is issued only after the same visibility check, and it expires in 60 seconds.
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status

from .. import db
from ..config import settings
from ..deps import CurrentUser, get_current_user
from ..permissions import can_view_photo, photo_owner
from ..ratelimit import rate_limit
from ..schemas import PhotoOut, PhotoPage, SignedUrlOut, TagUpdate
from ..storage import StorageError, storage

router = APIRouter(tags=["photos"])

ALLOWED = {
    "image/jpeg": ("jpg", lambda d: d[:3] == b"\xff\xd8\xff"),
    "image/png": ("png", lambda d: d[:8] == b"\x89PNG\r\n\x1a\n"),
    "image/webp": ("webp", lambda d: d[:4] == b"RIFF" and d[8:12] == b"WEBP"),
}
MAX_BYTES = 5 * 1024 * 1024
DAILY_QUOTA = 20
TAG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,29}$")

PHOTO_SELECT = """
    select p.id, p.owner_id, pr.username as owner_username, p.caption, p.mime_type, p.size_bytes,
           p.visibility, p.created_at,
           (select count(*) from public.comments c where c.photo_id = p.id) as comment_count,
           coalesce(
               (select array_agg(t.tag order by t.tag) from public.photo_tags t where t.photo_id = p.id),
               array[]::text[]
           ) as tags
    from public.photos p
    join public.profiles pr on pr.id = p.owner_id
"""


def _row_to_photo(row: dict[str, Any]) -> PhotoOut:
    return PhotoOut(**row)


def _visible_predicate() -> str:
    return "(p.owner_id = %(uid)s or (p.visibility = 'friends' and public.are_friends(p.owner_id, %(uid)s)))"


def _tags_for(photo_id: str) -> list[str]:
    rows = db.fetch_all(
        "select tag from public.photo_tags where photo_id = %s order by tag", (photo_id,)
    )
    return [r["tag"] for r in rows]


def _normalise_tags(raw: list[str]) -> list[str]:
    cleaned: list[str] = []
    for tag in raw:
        value = tag.strip().lower()
        if not value:
            continue
        if not TAG_RE.match(value):
            raise HTTPException(
                status_code=422,
                detail=f"invalid tag: {tag}",
            )
        if value not in cleaned:
            cleaned.append(value)
    if len(cleaned) > 20:
        raise HTTPException(
            status_code=422, detail="at most 20 tags"
        )
    return cleaned


@router.post("/photos", response_model=PhotoOut, status_code=status.HTTP_201_CREATED)
async def upload_photo(
    file: UploadFile = File(...),
    caption: str | None = Form(default=None),
    visibility: str = Form(default="friends"),
    tags: str | None = Form(default=None),
    user: CurrentUser = Depends(get_current_user),
    _: None = Depends(rate_limit("upload")),
) -> PhotoOut:
    if visibility not in ("friends", "owner"):
        raise HTTPException(422, "visibility must be 'friends' or 'owner'")

    mime = (file.content_type or "").lower()
    if mime not in ALLOWED:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "only JPEG, PNG and WebP are accepted",
        )

    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "maximum size is 5 MB")
    if not data:
        raise HTTPException(422, "empty file")

    extension, sniff = ALLOWED[mime]
    if not sniff(data):
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "file content does not match the declared image type",
        )

    used = db.fetch_one(
        """
        select count(*) as n from public.photos
        where owner_id = %s and created_at >= date_trunc('day', now() at time zone 'utc') at time zone 'utc'
        """,
        (str(user.id),),
    )["n"]
    if used >= DAILY_QUOTA:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "daily upload limit reached: 20 photos per day",
        )

    tag_list = _normalise_tags(tags.split(",") if tags else [])
    photo_id = uuid.uuid4()
    key = f"{user.id}/{photo_id}.{extension}"

    try:
        storage.save(key, data, mime)
    except StorageError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"storage write failed: {exc}") from exc

    try:
        db.execute(
            """
            insert into public.photos
                (id, owner_id, storage_path, caption, mime_type, size_bytes, visibility)
            values (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(photo_id),
                str(user.id),
                key,
                caption.strip() if caption else None,
                mime,
                len(data),
                visibility,
            ),
        )
        for tag in tag_list:
            db.execute(
                "insert into public.photo_tags (photo_id, tag) values (%s, %s)",
                (str(photo_id), tag),
            )
    except Exception as exc:
        # Compensating delete: a stored object with no metadata row would be invisible and would
        # count against storage forever, so it must not be left behind.
        try:
            storage.delete(key)
        except StorageError:
            pass
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "could not record photo") from exc

    row = db.fetch_one(PHOTO_SELECT + " where p.id = %s", (str(photo_id),))
    return _row_to_photo(row)


def _query_photos(
    user: CurrentUser,
    limit: int,
    offset: int,
    uploader: str | None,
    date_from: date | None,
    date_to: date | None,
    q: str | None,
    tag: str | None,
) -> PhotoPage:
    where = [_visible_predicate()]
    params: dict[str, Any] = {"uid": str(user.id), "limit": limit, "offset": offset}

    if uploader:
        where.append("pr.username = %(uploader)s")
        params["uploader"] = uploader.lower()
    if date_from:
        where.append("p.created_at >= %(date_from)s")
        params["date_from"] = date_from
    if date_to:
        # Inclusive of the whole end date.
        where.append("p.created_at < (%(date_to)s::date + interval '1 day')")
        params["date_to"] = date_to
    if q:
        where.append("p.caption ilike %(q)s")
        params["q"] = f"%{q}%"
    if tag:
        where.append(
            "exists (select 1 from public.photo_tags t where t.photo_id = p.id and t.tag = %(tag)s)"
        )
        params["tag"] = tag.lower()

    clause = " and ".join(where)
    total = db.fetch_one(
        f"select count(*) as n from public.photos p join public.profiles pr on pr.id = p.owner_id where {clause}",
        params,
    )["n"]

    rows = db.fetch_all(
        f"{PHOTO_SELECT} where {clause} order by p.created_at desc, p.id desc limit %(limit)s offset %(offset)s",
        params,
    )
    items = [_row_to_photo(r) for r in rows]
    return PhotoPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(items) < total,
    )


@router.get("/photos", response_model=PhotoPage)
def list_photos(
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    uploader: str | None = Query(default=None, max_length=30),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
    tag: str | None = Query(default=None, max_length=30),
    user: CurrentUser = Depends(get_current_user),
) -> PhotoPage:
    return _query_photos(user, limit, offset, uploader, date_from, date_to, q, tag)


# Declared before /photos/{photo_id}. FastAPI matches in declaration order, so a later declaration
# would make "search" be parsed as a UUID and return 422 instead of searching.
@router.get("/photos/search", response_model=PhotoPage)
def search_photos(
    q: str = Query(min_length=1, max_length=100),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    uploader: str | None = Query(default=None, max_length=30),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    tag: str | None = Query(default=None, max_length=30),
    user: CurrentUser = Depends(get_current_user),
) -> PhotoPage:
    return _query_photos(user, limit, offset, uploader, date_from, date_to, q, tag)


@router.get("/photos/{photo_id}", response_model=PhotoOut)
def get_photo(photo_id: uuid.UUID, user: CurrentUser = Depends(get_current_user)) -> PhotoOut:
    if not can_view_photo(user.id, photo_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "photo not found")
    row = db.fetch_one(PHOTO_SELECT + " where p.id = %s", (str(photo_id),))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "photo not found")
    return _row_to_photo(row)


@router.delete("/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_photo(
    photo_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    _: None = Depends(rate_limit("photo_delete")),
) -> Response:
    owner = photo_owner(photo_id)
    if owner is None or not can_view_photo(user.id, photo_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "photo not found")
    if owner != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "only the owner may delete this photo")

    row = db.fetch_one("select storage_path from public.photos where id = %s", (str(photo_id),))
    key = row["storage_path"]

    # Delete the object first. If this fails the metadata row stays, so the photo remains visible and
    # consistent, and the operation can be retried. Deleting the row first would leave an orphan
    # object that no endpoint can ever reach.
    try:
        storage.delete(key)
    except StorageError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"storage deletion failed, photo left unchanged: {exc}",
        ) from exc

    try:
        db.execute("delete from public.photos where id = %s", (str(photo_id),))
    except Exception as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "object deleted but metadata deletion failed; retry the delete to converge",
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/photos/{photo_id}/url", response_model=SignedUrlOut)
def photo_url(
    photo_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    _: None = Depends(rate_limit("signed_url")),
) -> SignedUrlOut:
    if not can_view_photo(user.id, photo_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "photo not found")

    row = db.fetch_one("select storage_path from public.photos where id = %s", (str(photo_id),))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "photo not found")

    try:
        url = storage.signed_url(row["storage_path"], settings.signed_url_ttl_seconds)
    except StorageError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"could not sign URL: {exc}") from exc

    return SignedUrlOut(url=url, expires_in=settings.signed_url_ttl_seconds)


@router.put("/photos/{photo_id}/tags", response_model=PhotoOut)
def replace_tags(
    photo_id: uuid.UUID,
    payload: TagUpdate,
    user: CurrentUser = Depends(get_current_user),
) -> PhotoOut:
    owner = photo_owner(photo_id)
    if owner is None or not can_view_photo(user.id, photo_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "photo not found")
    if owner != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "only the owner may tag this photo")

    tags = _normalise_tags(payload.tags)
    db.execute("delete from public.photo_tags where photo_id = %s", (str(photo_id),))
    for tag in tags:
        db.execute(
            "insert into public.photo_tags (photo_id, tag) values (%s, %s)", (str(photo_id), tag)
        )

    row = db.fetch_one(PHOTO_SELECT + " where p.id = %s", (str(photo_id),))
    return _row_to_photo(row)
