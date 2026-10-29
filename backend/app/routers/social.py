"""Friendships and comments.

Rules enforced here:

* A request may only be sent by the caller, to an existing user, and never to yourself.
* Only the addressee may accept or reject, and only while the request is pending.
* Either party may remove a friendship.
* Comments require permission to view the photo. Removing a comment is allowed for its author and
  for the photo owner, matching the RLS policy exactly.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status

from .. import db
from ..deps import CurrentUser, get_current_user
from ..permissions import can_view_photo
from ..ratelimit import rate_limit
from ..schemas import CommentCreate, CommentOut, FriendOut, FriendRequestCreate, FriendshipOut

router = APIRouter(tags=["social"])

FRIENDSHIP_SELECT = """
    select f.id, f.requester_id, r.username as requester_username,
           f.addressee_id, a.username as addressee_username,
           f.status, f.created_at, f.responded_at
    from public.friendships f
    join public.profiles r on r.id = f.requester_id
    join public.profiles a on a.id = f.addressee_id
"""

COMMENT_SELECT = """
    select c.id, c.photo_id, c.author_id, pr.username as author_username, c.body, c.created_at
    from public.comments c
    join public.profiles pr on pr.id = c.author_id
"""


# ---------------------------------------------------------------- friends


@router.post("/friends/requests", response_model=FriendshipOut, status_code=status.HTTP_201_CREATED)
def send_request(
    payload: FriendRequestCreate,
    user: CurrentUser = Depends(get_current_user),
    _: None = Depends(rate_limit("friend_request")),
) -> FriendshipOut:
    target = db.fetch_one(
        "select id, username from public.profiles where lower(username) = %s",
        (payload.username.strip().lower(),),
    )
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such user")
    if target["id"] == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "you cannot befriend yourself")

    existing = db.fetch_one(
        """
        select id from public.friendships
        where status in ('pending', 'accepted')
          and ((requester_id = %s and addressee_id = %s)
            or (requester_id = %s and addressee_id = %s))
        """,
        (str(user.id), str(target["id"]), str(target["id"]), str(user.id)),
    )
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "a request or friendship already exists with this user"
        )

    row = db.fetch_one(
        """
        insert into public.friendships (requester_id, addressee_id)
        values (%s, %s)
        returning id
        """,
        (str(user.id), str(target["id"])),
    )
    return FriendshipOut(
        **db.fetch_one(FRIENDSHIP_SELECT + " where f.id = %s", (str(row["id"]),))
    )


@router.get("/friends/requests", response_model=dict[str, list[FriendshipOut]])
def list_requests(user: CurrentUser = Depends(get_current_user)) -> dict[str, list[FriendshipOut]]:
    incoming = db.fetch_all(
        FRIENDSHIP_SELECT + " where f.addressee_id = %s and f.status = 'pending' order by f.created_at desc",
        (str(user.id),),
    )
    outgoing = db.fetch_all(
        FRIENDSHIP_SELECT + " where f.requester_id = %s and f.status = 'pending' order by f.created_at desc",
        (str(user.id),),
    )
    return {
        "incoming": [FriendshipOut(**r) for r in incoming],
        "outgoing": [FriendshipOut(**r) for r in outgoing],
    }


def _respond(
    friendship_id: uuid.UUID, user: CurrentUser, new_status: str
) -> FriendshipOut:
    row = db.fetch_one("select * from public.friendships where id = %s", (str(friendship_id),))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "request not found")
    if row["addressee_id"] != user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "only the recipient may respond to this request"
        )
    if row["status"] != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "request already answered")

    db.execute(
        """
        update public.friendships
           set status = %s, responded_at = now()
         where id = %s and addressee_id = %s and status = 'pending'
        """,
        (new_status, str(friendship_id), str(user.id)),
    )
    return FriendshipOut(
        **db.fetch_one(FRIENDSHIP_SELECT + " where f.id = %s", (str(friendship_id),))
    )


@router.post("/friends/requests/{friendship_id}/accept", response_model=FriendshipOut)
def accept_request(
    friendship_id: uuid.UUID, user: CurrentUser = Depends(get_current_user)
) -> FriendshipOut:
    return _respond(friendship_id, user, "accepted")


@router.post("/friends/requests/{friendship_id}/reject", response_model=FriendshipOut)
def reject_request(
    friendship_id: uuid.UUID, user: CurrentUser = Depends(get_current_user)
) -> FriendshipOut:
    return _respond(friendship_id, user, "rejected")


@router.get("/friends", response_model=list[FriendOut])
def list_friends(user: CurrentUser = Depends(get_current_user)) -> list[FriendOut]:
    rows = db.fetch_all(
        """
        select p.id, p.username, p.display_name
        from public.friendships f
        join public.profiles p
          on p.id = case when f.requester_id = %s then f.addressee_id else f.requester_id end
        where f.status = 'accepted'
          and (f.requester_id = %s or f.addressee_id = %s)
        order by p.username
        """,
        (str(user.id), str(user.id), str(user.id)),
    )
    return [FriendOut(**r) for r in rows]


@router.delete("/friends/{friendship_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_friend(
    friendship_id: uuid.UUID, user: CurrentUser = Depends(get_current_user)
) -> Response:
    row = db.fetch_one("select * from public.friendships where id = %s", (str(friendship_id),))
    if row is None or user.id not in (row["requester_id"], row["addressee_id"]):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "friendship not found")
    db.execute("delete from public.friendships where id = %s", (str(friendship_id),))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- comments


@router.get("/photos/{photo_id}/comments", response_model=list[CommentOut])
def list_comments(
    photo_id: uuid.UUID, user: CurrentUser = Depends(get_current_user)
) -> list[CommentOut]:
    if not can_view_photo(user.id, photo_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "photo not found")
    rows = db.fetch_all(
        COMMENT_SELECT + " where c.photo_id = %s order by c.created_at asc", (str(photo_id),)
    )
    return [CommentOut(**r) for r in rows]


@router.post(
    "/photos/{photo_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    photo_id: uuid.UUID,
    payload: CommentCreate,
    user: CurrentUser = Depends(get_current_user),
    _: None = Depends(rate_limit("comment")),
) -> CommentOut:
    if not can_view_photo(user.id, photo_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "photo not found")
    row = db.fetch_one(
        """
        insert into public.comments (photo_id, author_id, body)
        values (%s, %s, %s)
        returning id
        """,
        (str(photo_id), str(user.id), payload.body.strip()),
    )
    return CommentOut(**db.fetch_one(COMMENT_SELECT + " where c.id = %s", (str(row["id"]),)))


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    comment_id: uuid.UUID, user: CurrentUser = Depends(get_current_user)
) -> Response:
    row: dict[str, Any] | None = db.fetch_one(
        """
        select c.id, c.author_id, p.owner_id
        from public.comments c
        join public.photos p on p.id = c.photo_id
        where c.id = %s
        """,
        (str(comment_id),),
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "comment not found")
    if user.id not in (row["author_id"], row["owner_id"]):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "only the comment author or the photo owner may delete this comment",
        )
    db.execute("delete from public.comments where id = %s", (str(comment_id),))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
