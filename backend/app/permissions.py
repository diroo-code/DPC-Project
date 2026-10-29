"""Permission checks shared by the API.

Every check here is a SQL call, using the same function the RLS policies use, with the user id passed
explicitly. That is deliberate: the backend holds a privileged connection, so if a permission were
re-implemented in Python the two definitions could drift, and drift in a visibility rule is a
security bug.
"""

from __future__ import annotations

from uuid import UUID

from . import db


def can_view_photo(user_id: UUID, photo_id: UUID) -> bool:
    row = db.fetch_one(
        "select public.user_can_view_photo(%s, %s) as allowed",
        (str(user_id), str(photo_id)),
    )
    return bool(row and row["allowed"])


def are_friends(a: UUID, b: UUID) -> bool:
    row = db.fetch_one("select public.are_friends(%s, %s) as friends", (str(a), str(b)))
    return bool(row and row["friends"])


def photo_owner(photo_id: UUID) -> UUID | None:
    row = db.fetch_one("select owner_id from public.photos where id = %s", (str(photo_id),))
    return row["owner_id"] if row else None
