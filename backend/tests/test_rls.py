"""Row level security tests.

Each test switches to the `authenticated` role with a specific subject, which is the same
mechanism a browser client uses. The table owner bypasses RLS, so testing as the owner would
prove nothing about the policies.
"""

from __future__ import annotations

import psycopg
import pytest
from psycopg import errors

from .conftest import acting_as, create_user, make_friends, make_photo


def test_user_sees_only_visible_photos(conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    carol = create_user(conn, "carol")

    shared = make_photo(conn, alice, visibility="friends", caption="shared")
    private = make_photo(conn, alice, visibility="owner", caption="private")

    make_friends(conn, alice, bob)

    with acting_as(conn, bob):
        visible = conn.execute("select id from public.photos order by id").fetchall()
    visible_ids = {row[0] for row in visible}
    assert shared in visible_ids
    assert private not in visible_ids

    with acting_as(conn, carol):
        stranger_view = conn.execute("select id from public.photos").fetchall()
    assert stranger_view == []

    with acting_as(conn, alice):
        own = conn.execute("select id from public.photos").fetchall()
    assert {row[0] for row in own} == {shared, private}


def test_cannot_insert_an_already_accepted_friendship(conn: psycopg.Connection) -> None:
    """A user must not be able to create a friendship by inserting a row with status accepted."""
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")

    with acting_as(conn, alice):
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute(
                """
                insert into public.friendships (requester_id, addressee_id, status, responded_at)
                values (%s, %s, 'accepted', now())
                """,
                (alice, bob),
            )


def test_cannot_comment_as_another_user(conn: psycopg.Connection) -> None:
    """A friend may comment, but must not be able to attribute it to somebody else."""
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    make_friends(conn, alice, bob)
    photo = make_photo(conn, alice, visibility="friends")

    with acting_as(conn, bob):
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute(
                "insert into public.comments (photo_id, author_id, body) values (%s, %s, 'forged')",
                (photo, alice),
            )


def test_anonymous_role_cannot_read_photos(conn: psycopg.Connection) -> None:
    """Anonymous callers are denied at the privilege layer as well as by RLS: no grants on the
    table at all, which is stricter than an empty result set."""
    alice = create_user(conn, "alice")
    make_photo(conn, alice, visibility="friends")
    conn.execute("set role anon")
    try:
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute("select id from public.photos").fetchall()
    finally:
        conn.execute("reset role")


def test_friendship_insert_must_be_self_requested(conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    carol = create_user(conn, "carol")

    with acting_as(conn, alice):
        conn.execute(
            "insert into public.friendships (requester_id, addressee_id) values (%s, %s)",
            (alice, bob),
        )

    with acting_as(conn, carol):
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute(
                "insert into public.friendships (requester_id, addressee_id) values (%s, %s)",
                (alice, bob),
            )


def test_only_the_addressee_can_accept(conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    conn.execute(
        "insert into public.friendships (requester_id, addressee_id) values (%s, %s)",
        (alice, bob),
    )

    with acting_as(conn, alice):
        changed = conn.execute(
            "update public.friendships set status = 'accepted', responded_at = now()"
        ).rowcount
    assert changed == 0

    with acting_as(conn, bob):
        changed = conn.execute(
            "update public.friendships set status = 'accepted', responded_at = now()"
        ).rowcount
    assert changed == 1


def test_friendship_is_invisible_to_third_parties(conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    carol = create_user(conn, "carol")
    make_friends(conn, alice, bob)

    with acting_as(conn, carol):
        rows = conn.execute("select id from public.friendships").fetchall()
    assert rows == []


def test_profile_update_is_self_only(conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")

    with acting_as(conn, bob):
        changed = conn.execute(
            "update public.profiles set display_name = 'Hacked' where id = %s", (alice,)
        ).rowcount
    assert changed == 0

    with acting_as(conn, bob):
        changed = conn.execute(
            "update public.profiles set display_name = 'Bob B' where id = %s", (bob,)
        ).rowcount
    assert changed == 1


def test_non_friend_cannot_comment(conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    carol = create_user(conn, "carol")
    photo = make_photo(conn, alice, visibility="friends")

    with acting_as(conn, carol):
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute(
                "insert into public.comments (photo_id, author_id, body) values (%s, %s, 'hi')",
                (photo, carol),
            )


def test_friend_can_comment_on_shared_photo(conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    make_friends(conn, alice, bob)
    photo = make_photo(conn, alice, visibility="friends")

    with acting_as(conn, bob):
        conn.execute(
            "insert into public.comments (photo_id, author_id, body) values (%s, %s, 'nice')",
            (photo, bob),
        )
        rows = conn.execute("select body from public.comments").fetchall()
    assert rows == [("nice",)]


def test_friend_cannot_see_comments_on_owner_only_photo(conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    make_friends(conn, alice, bob)
    photo = make_photo(conn, alice, visibility="owner")
    conn.execute(
        "insert into public.comments (photo_id, author_id, body) values (%s, %s, 'secret')",
        (photo, alice),
    )

    with acting_as(conn, bob):
        rows = conn.execute("select body from public.comments").fetchall()
    assert rows == []


def test_comment_deletion_rights(conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    carol = create_user(conn, "carol")
    make_friends(conn, alice, bob)
    photo = make_photo(conn, alice, visibility="friends")
    conn.execute(
        "insert into public.comments (photo_id, author_id, body) values (%s, %s, 'hello')",
        (photo, bob),
    )

    # a stranger may not delete it
    make_friends(conn, alice, carol)
    with acting_as(conn, carol):
        assert conn.execute("delete from public.comments").rowcount == 0

    # the author may delete their own
    with acting_as(conn, bob):
        assert conn.execute("delete from public.comments").rowcount == 1

    # the photo owner may delete someone else's comment on their photo
    conn.execute(
        "insert into public.comments (photo_id, author_id, body) values (%s, %s, 'again')",
        (photo, bob),
    )
    with acting_as(conn, alice):
        assert conn.execute("delete from public.comments").rowcount == 1


def test_only_the_owner_can_tag(conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    make_friends(conn, alice, bob)
    photo = make_photo(conn, alice, visibility="friends")

    with acting_as(conn, bob):
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute(
                "insert into public.photo_tags (photo_id, tag) values (%s, 'beach')", (photo,)
            )

    with acting_as(conn, alice):
        conn.execute(
            "insert into public.photo_tags (photo_id, tag) values (%s, 'beach')", (photo,)
        )

    with acting_as(conn, bob):
        rows = conn.execute("select tag from public.photo_tags").fetchall()
    assert rows == [("beach",)]


def test_friend_cannot_update_photo_metadata(conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    make_friends(conn, alice, bob)
    photo = make_photo(conn, alice, visibility="friends")

    with acting_as(conn, bob):
        changed = conn.execute(
            "update public.photos set caption = 'edited' where id = %s", (photo,)
        ).rowcount
    assert changed == 0


def test_can_view_photo_function_matches_policies(conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    shared = make_photo(conn, alice, visibility="friends")
    private = make_photo(conn, alice, visibility="owner")

    with acting_as(conn, bob):
        assert conn.execute("select public.can_view_photo(%s)", (shared,)).fetchone()[0] is False
    make_friends(conn, alice, bob)
    with acting_as(conn, bob):
        assert conn.execute("select public.can_view_photo(%s)", (shared,)).fetchone()[0] is True
        assert conn.execute("select public.can_view_photo(%s)", (private,)).fetchone()[0] is False
    with acting_as(conn, alice):
        assert conn.execute("select public.can_view_photo(%s)", (private,)).fetchone()[0] is True
