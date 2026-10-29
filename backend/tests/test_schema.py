"""Schema tests: the constraints do the work, so test the constraints."""

from __future__ import annotations

import uuid

import psycopg
import pytest
from psycopg import errors

from .conftest import create_user, make_photo


def test_expected_tables_exist(conn: psycopg.Connection) -> None:
    rows = conn.execute(
        """
        select table_name from information_schema.tables
        where table_schema = 'public' and table_type = 'BASE TABLE'
        order by table_name
        """
    ).fetchall()
    names = {row[0] for row in rows}
    assert {"profiles", "friendships", "photos", "comments", "photo_tags"} <= names


def test_every_table_has_rls_enabled(conn: psycopg.Connection) -> None:
    rows = conn.execute(
        """
        select relname, relrowsecurity from pg_class
        where relnamespace = 'public'::regnamespace and relkind = 'r'
        """
    ).fetchall()
    flags = dict(rows)
    for table in ("profiles", "friendships", "photos", "comments", "photo_tags"):
        assert flags[table] is True, f"RLS is not enabled on {table}"


def test_trigger_creates_profile(conn: psycopg.Connection) -> None:
    user_id = create_user(conn, "alice", "Alice")
    row = conn.execute(
        "select username, display_name from public.profiles where id = %s", (user_id,)
    ).fetchone()
    assert row == ("alice", "Alice")


def test_duplicate_username_gets_a_suffix(conn: psycopg.Connection) -> None:
    create_user(conn, "alice")
    second = create_user(conn, "alice", email="alice.second@example.test")
    username = conn.execute(
        "select username from public.profiles where id = %s", (second,)
    ).fetchone()[0]
    assert username != "alice"
    assert username.startswith("alice")


def test_exact_duplicate_username_is_rejected(conn: psycopg.Connection) -> None:
    create_user(conn, "alice")
    other = create_user(conn, "bob")
    with pytest.raises(errors.UniqueViolation):
        conn.execute(
            "insert into public.profiles (id, username, display_name) values (%s, %s, %s)",
            (other, "alice", "Impostor"),
        )


def test_uppercase_username_is_rejected_before_the_unique_index(conn: psycopg.Connection) -> None:
    """The format check is lower case only, so "ALICE" is rejected on format rather than
    reaching the case-insensitive unique index. That is stricter than the index alone and is
    the behaviour the API must normalise against."""
    create_user(conn, "alice")
    other = create_user(conn, "bob")
    with pytest.raises(errors.CheckViolation):
        conn.execute(
            "insert into public.profiles (id, username, display_name) values (%s, %s, %s)",
            (other, "ALICE", "Impostor"),
        )


def test_username_format_is_enforced(conn: psycopg.Connection) -> None:
    user_id = create_user(conn, "charlie")
    with pytest.raises(errors.CheckViolation):
        conn.execute(
            "update public.profiles set username = %s where id = %s",
            ("Bad Name!", user_id),
        )


def test_self_friendship_is_rejected(conn: psycopg.Connection) -> None:
    user_id = create_user(conn, "dave")
    with pytest.raises(errors.CheckViolation):
        conn.execute(
            "insert into public.friendships (requester_id, addressee_id) values (%s, %s)",
            (user_id, user_id),
        )


def test_duplicate_active_friendship_is_rejected_in_either_direction(
    conn: psycopg.Connection,
) -> None:
    a = create_user(conn, "erin")
    b = create_user(conn, "frank")
    conn.execute(
        "insert into public.friendships (requester_id, addressee_id) values (%s, %s)", (a, b)
    )
    with pytest.raises(errors.UniqueViolation):
        conn.execute(
            "insert into public.friendships (requester_id, addressee_id) values (%s, %s)",
            (b, a),
        )


def test_rejected_request_does_not_block_a_new_one(conn: psycopg.Connection) -> None:
    a = create_user(conn, "gina")
    b = create_user(conn, "hugo")
    conn.execute(
        """
        insert into public.friendships (requester_id, addressee_id, status, responded_at)
        values (%s, %s, 'rejected', now())
        """,
        (a, b),
    )
    conn.execute(
        "insert into public.friendships (requester_id, addressee_id) values (%s, %s)", (b, a)
    )
    count = conn.execute(
        "select count(*) from public.friendships where status = 'pending'"
    ).fetchone()[0]
    assert count == 1


def test_pending_request_cannot_carry_a_response_time(conn: psycopg.Connection) -> None:
    a = create_user(conn, "ivan")
    b = create_user(conn, "judy")
    with pytest.raises(errors.CheckViolation):
        conn.execute(
            """
            insert into public.friendships (requester_id, addressee_id, status, responded_at)
            values (%s, %s, 'pending', now())
            """,
            (a, b),
        )


def test_photo_mime_type_is_restricted(conn: psycopg.Connection) -> None:
    owner = create_user(conn, "kara")
    photo_id = uuid.uuid4()
    with pytest.raises(errors.CheckViolation):
        conn.execute(
            """
            insert into public.photos (id, owner_id, storage_path, mime_type, size_bytes)
            values (%s, %s, %s, 'image/gif', 1024)
            """,
            (photo_id, owner, f"{owner}/{photo_id}.gif"),
        )


def test_photo_size_limit_is_5mb(conn: psycopg.Connection) -> None:
    owner = create_user(conn, "liam")
    photo_id = uuid.uuid4()
    with pytest.raises(errors.CheckViolation):
        conn.execute(
            """
            insert into public.photos (id, owner_id, storage_path, mime_type, size_bytes)
            values (%s, %s, %s, 'image/jpeg', 5242881)
            """,
            (photo_id, owner, f"{owner}/{photo_id}.jpg"),
        )


def test_photo_path_must_start_with_owner_folder(conn: psycopg.Connection) -> None:
    owner = create_user(conn, "mia")
    other = create_user(conn, "nina")
    photo_id = uuid.uuid4()
    with pytest.raises(errors.CheckViolation):
        conn.execute(
            """
            insert into public.photos (id, owner_id, storage_path, mime_type, size_bytes)
            values (%s, %s, %s, 'image/jpeg', 1024)
            """,
            (photo_id, owner, f"{other}/{photo_id}.jpg"),
        )


def test_daily_upload_quota_is_20(conn: psycopg.Connection) -> None:
    owner = create_user(conn, "owen")
    for _ in range(20):
        make_photo(conn, owner)
    with pytest.raises(errors.RaiseException):
        make_photo(conn, owner)


def test_comment_body_cannot_be_blank(conn: psycopg.Connection) -> None:
    owner = create_user(conn, "pia")
    photo = make_photo(conn, owner)
    with pytest.raises(errors.CheckViolation):
        conn.execute(
            "insert into public.comments (photo_id, author_id, body) values (%s, %s, %s)",
            (photo, owner, "   "),
        )


def test_tag_format_is_normalised(conn: psycopg.Connection) -> None:
    owner = create_user(conn, "quinn")
    photo = make_photo(conn, owner)
    with pytest.raises(errors.CheckViolation):
        conn.execute(
            "insert into public.photo_tags (photo_id, tag) values (%s, %s)",
            (photo, "Not A Tag"),
        )
    conn.execute(
        "insert into public.photo_tags (photo_id, tag) values (%s, %s)", (photo, "sunset_2026")
    )


def test_updated_at_changes_on_update(conn: psycopg.Connection) -> None:
    user_id = create_user(conn, "rosa")
    before = conn.execute(
        "select created_at, updated_at from public.profiles where id = %s", (user_id,)
    ).fetchone()
    conn.execute(
        "update public.profiles set display_name = 'Rosa B' where id = %s", (user_id,)
    )
    after = conn.execute(
        "select created_at, updated_at from public.profiles where id = %s", (user_id,)
    ).fetchone()
    assert after[1] > before[1]


def test_deleting_photo_cascades_comments_and_tags(conn: psycopg.Connection) -> None:
    owner = create_user(conn, "sam")
    photo = make_photo(conn, owner)
    conn.execute(
        "insert into public.comments (photo_id, author_id, body) values (%s, %s, 'nice')",
        (photo, owner),
    )
    conn.execute(
        "insert into public.photo_tags (photo_id, tag) values (%s, 'trip')", (photo,)
    )
    conn.execute("delete from public.photos where id = %s", (photo,))
    assert conn.execute("select count(*) from public.comments").fetchone()[0] == 0
    assert conn.execute("select count(*) from public.photo_tags").fetchone()[0] == 0
