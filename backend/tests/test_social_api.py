"""Friend request and comment API tests."""

from __future__ import annotations

import uuid

import psycopg

from .conftest import create_user, make_friends, make_photo, token_for


def auth(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_for(user_id)}"}


def send(client, user_id: uuid.UUID, username: str):
    return client.post(
        "/api/v1/friends/requests", headers=auth(user_id), json={"username": username}
    )


def test_send_request(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    create_user(conn, "bob")

    response = send(client, alice, "bob")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["requester_username"] == "alice"
    assert body["addressee_username"] == "bob"


def test_cannot_befriend_yourself(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    assert send(client, alice, "alice").status_code == 400


def test_unknown_username_returns_404(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    assert send(client, alice, "nobody").status_code == 404


def test_duplicate_request_is_rejected(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    create_user(conn, "bob")
    assert send(client, alice, "bob").status_code == 201
    assert send(client, alice, "bob").status_code == 409
    # The reverse direction must also be refused while a request is pending.
    bob = conn.execute("select id from public.profiles where username = 'bob'").fetchone()[0]
    assert send(client, bob, "alice").status_code == 409


def test_only_the_addressee_can_accept(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    request_id = send(client, alice, "bob").json()["id"]

    assert (
        client.post(f"/api/v1/friends/requests/{request_id}/accept", headers=auth(alice)).status_code
        == 403
    )
    accepted = client.post(
        f"/api/v1/friends/requests/{request_id}/accept", headers=auth(bob)
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"


def test_reject_leaves_no_friendship(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    request_id = send(client, alice, "bob").json()["id"]

    rejected = client.post(
        f"/api/v1/friends/requests/{request_id}/reject", headers=auth(bob)
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert client.get("/api/v1/friends", headers=auth(alice)).json() == []


def test_requests_are_listed_by_direction(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    send(client, alice, "bob")

    bob_view = client.get("/api/v1/friends/requests", headers=auth(bob)).json()
    assert len(bob_view["incoming"]) == 1
    assert bob_view["outgoing"] == []

    alice_view = client.get("/api/v1/friends/requests", headers=auth(alice)).json()
    assert alice_view["incoming"] == []
    assert len(alice_view["outgoing"]) == 1


def test_friends_list_and_removal(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    request_id = send(client, alice, "bob").json()["id"]
    client.post(f"/api/v1/friends/requests/{request_id}/accept", headers=auth(bob))

    friends = client.get("/api/v1/friends", headers=auth(alice)).json()
    assert [f["username"] for f in friends] == ["bob"]

    assert client.delete(f"/api/v1/friends/{request_id}", headers=auth(bob)).status_code == 204
    assert client.get("/api/v1/friends", headers=auth(alice)).json() == []


def test_comment_on_a_shared_photo(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    make_friends(conn, alice, bob)
    photo = make_photo(conn, alice, visibility="friends")

    response = client.post(
        f"/api/v1/photos/{photo}/comments",
        headers=auth(bob),
        json={"body": "Nice shot"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["author_username"] == "bob"

    listed = client.get(f"/api/v1/photos/{photo}/comments", headers=auth(alice)).json()
    assert [c["body"] for c in listed] == ["Nice shot"]


def test_cannot_comment_on_an_owner_only_photo(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    make_friends(conn, alice, bob)
    photo = make_photo(conn, alice, visibility="owner")

    response = client.post(
        f"/api/v1/photos/{photo}/comments", headers=auth(bob), json={"body": "hello"}
    )
    assert response.status_code == 404


def test_comment_deletion_by_author_and_owner(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    carol = create_user(conn, "carol")
    make_friends(conn, alice, bob)
    make_friends(conn, alice, carol)
    photo = make_photo(conn, alice, visibility="friends")

    first = client.post(
        f"/api/v1/photos/{photo}/comments", headers=auth(bob), json={"body": "one"}
    ).json()
    second = client.post(
        f"/api/v1/photos/{photo}/comments", headers=auth(bob), json={"body": "two"}
    ).json()

    # A third party may not delete someone else's comment.
    assert (
        client.delete(f"/api/v1/comments/{first['id']}", headers=auth(carol)).status_code == 403
    )
    # The author may.
    assert (
        client.delete(f"/api/v1/comments/{first['id']}", headers=auth(bob)).status_code == 204
    )
    # The photo owner may delete a comment they did not write.
    assert (
        client.delete(f"/api/v1/comments/{second['id']}", headers=auth(alice)).status_code == 204
    )


def test_comment_requires_authentication(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    photo = make_photo(conn, alice)
    response = client.get(f"/api/v1/photos/{photo}/comments")
    assert response.status_code == 401
