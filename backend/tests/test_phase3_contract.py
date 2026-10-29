"""Phase 3 contract tests.

These verify the endpoint list named in the brief at its literal paths, including the ones that did
not exist before this phase: GET /me, GET /profiles/{user_id} and GET /photos/search. They also cover
the negative cases the brief requires: unauthorized access, invalid input, ownership, pagination and
error handling.
"""

from __future__ import annotations

import uuid

import psycopg
import pytest

from .conftest import create_user, make_friends, make_photo, token_for

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 400


def auth(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_for(user_id)}"}


def upload(client, user_id, caption, visibility="friends", tags=None):
    data = {"caption": caption, "visibility": visibility}
    if tags:
        data["tags"] = tags
    return client.post(
        "/api/v1/photos",
        headers=auth(user_id),
        files={"file": ("p.jpg", JPEG, "image/jpeg")},
        data=data,
    )


# ---------------------------------------------------------------- health and me


def test_health_at_root(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_me_requires_a_token(client) -> None:
    assert client.get("/me").status_code == 401


def test_me_returns_the_caller_profile(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice", "Alice")
    response = client.get("/me", headers=auth(alice))
    assert response.status_code == 200
    assert response.json()["username"] == "alice"


def test_me_and_versioned_route_agree(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    short = client.get("/me", headers=auth(alice)).json()
    versioned = client.get("/api/v1/auth/me", headers=auth(alice)).json()
    assert short == versioned


# ---------------------------------------------------------------- profiles


def test_profile_returns_public_fields_only(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice", "Alice")
    bob = create_user(conn, "bob")
    response = client.get(f"/profiles/{alice}", headers=auth(bob))
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "alice"
    assert body["display_name"] == "Alice"
    assert "email" not in body
    assert "updated_at" not in body


def test_profile_requires_authentication(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    assert client.get(f"/profiles/{alice}").status_code == 401


def test_profile_unknown_id_is_404(client, conn: psycopg.Connection) -> None:
    bob = create_user(conn, "bob")
    assert client.get(f"/profiles/{uuid.uuid4()}", headers=auth(bob)).status_code == 404


def test_profile_malformed_id_is_422(client, conn: psycopg.Connection) -> None:
    bob = create_user(conn, "bob")
    assert client.get("/profiles/not-a-uuid", headers=auth(bob)).status_code == 422


# ---------------------------------------------------------------- photos at brief paths


def test_photos_path_mirrors_the_versioned_contract(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    upload(client, alice, "one")
    brief = client.get("/photos", headers=auth(alice))
    versioned = client.get("/api/v1/photos", headers=auth(alice))
    assert brief.status_code == 200
    assert brief.json() == versioned.json()


def test_single_photo_and_delete_at_brief_paths(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    photo_id = upload(client, alice, "one").json()["id"]

    assert client.get(f"/photos/{photo_id}", headers=auth(alice)).status_code == 200
    assert client.delete(f"/photos/{photo_id}", headers=auth(alice)).status_code == 204
    assert client.get(f"/photos/{photo_id}", headers=auth(alice)).status_code == 404


def test_unknown_photo_is_404_and_malformed_is_422(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    assert client.get(f"/photos/{uuid.uuid4()}", headers=auth(alice)).status_code == 404
    assert client.get("/photos/not-a-uuid", headers=auth(alice)).status_code == 422


# ---------------------------------------------------------------- search


def test_search_requires_a_query(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    assert client.get("/photos/search", headers=auth(alice)).status_code == 422
    assert client.get("/photos/search?q=", headers=auth(alice)).status_code == 422


def test_search_matches_caption(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    upload(client, alice, "Sunset over the lake")
    upload(client, alice, "Mountain trail")

    response = client.get("/photos/search?q=sunset", headers=auth(alice))
    assert response.status_code == 200
    assert [i["caption"] for i in response.json()["items"]] == ["Sunset over the lake"]


def test_search_does_not_leak_invisible_photos(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    upload(client, alice, "Alice private", visibility="owner")
    upload(client, alice, "Alice shared", visibility="friends")

    before = client.get("/photos/search?q=alice", headers=auth(bob)).json()
    assert before["total"] == 0

    make_friends(conn, alice, bob)
    after = client.get("/photos/search?q=alice", headers=auth(bob)).json()
    assert [i["caption"] for i in after["items"]] == ["Alice shared"]


def test_search_filters_by_tag_and_uploader(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    make_friends(conn, alice, bob)
    upload(client, alice, "Trail run", tags="hiking")
    upload(client, alice, "Trail map")
    upload(client, bob, "Trail from bob", tags="hiking")

    tagged = client.get("/photos/search?q=trail&tag=hiking", headers=auth(alice)).json()
    assert {i["owner_username"] for i in tagged["items"]} == {"alice", "bob"}

    mine = client.get(
        "/photos/search?q=trail&tag=hiking&uploader=alice", headers=auth(alice)
    ).json()
    assert [i["caption"] for i in mine["items"]] == ["Trail run"]


def test_search_pagination(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    for i in range(5):
        upload(client, alice, f"snow day {i}")

    page = client.get("/photos/search?q=snow&limit=2", headers=auth(alice)).json()
    assert len(page["items"]) == 2
    assert page["total"] == 5
    assert page["has_more"] is True

    last = client.get("/photos/search?q=snow&limit=2&offset=4", headers=auth(alice)).json()
    assert len(last["items"]) == 1
    assert last["has_more"] is False


# ---------------------------------------------------------------- invalid input and errors


@pytest.mark.parametrize(
    "query",
    ["limit=0", "limit=51", "offset=-1", "q=" + ("x" * 101)],
)
def test_invalid_feed_parameters_are_rejected(client, conn: psycopg.Connection, query: str) -> None:
    alice = create_user(conn, "alice")
    response = client.get(f"/api/v1/photos?{query}", headers=auth(alice))
    assert response.status_code == 422


def test_search_rejects_overlong_query(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    assert client.get("/photos/search?q=" + "x" * 101, headers=auth(alice)).status_code == 422


def test_unknown_route_and_wrong_method(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    assert client.get("/api/v1/nonexistent", headers=auth(alice)).status_code == 404
    # A route that exists but does not accept this method.
    assert client.put("/photos", headers=auth(alice)).status_code == 405


# ---------------------------------------------------------------- friends and comments at brief paths


def test_friends_at_brief_path(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    request_id = client.post(
        "/friends/requests", headers=auth(alice), json={"username": "bob"}
    ).json()["id"]
    client.post(f"/friends/requests/{request_id}/accept", headers=auth(bob))

    friends = client.get("/friends", headers=auth(alice)).json()
    assert [f["username"] for f in friends] == ["bob"]


def test_comments_at_brief_paths(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    make_friends(conn, alice, bob)
    photo = make_photo(conn, alice, visibility="friends")

    created = client.post(
        f"/photos/{photo}/comments", headers=auth(bob), json={"body": "Hello"}
    )
    assert created.status_code == 201

    listed = client.get(f"/photos/{photo}/comments", headers=auth(alice)).json()
    assert [c["body"] for c in listed] == ["Hello"]

    deleted = client.delete(f"/comments/{created.json()['id']}", headers=auth(bob))
    assert deleted.status_code == 204


def test_ownership_still_enforced_on_brief_paths(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    make_friends(conn, alice, bob)
    photo = make_photo(conn, alice, visibility="friends")

    assert client.delete(f"/photos/{photo}", headers=auth(bob)).status_code == 403
    assert client.put(
        f"/photos/{photo}/tags", headers=auth(bob), json={"tags": ["x"]}
    ).status_code == 403
