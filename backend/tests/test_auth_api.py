"""API tests for health and authentication wiring."""

from __future__ import annotations

import psycopg
import pytest

from .conftest import create_user, token_for


def test_health_returns_expected_shape(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"]
    assert body["version"]


def test_ready_reports_database_ok(client, conn: psycopg.Connection) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


def test_me_rejects_missing_token(client) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_rejects_wrong_scheme(client) -> None:
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Token abc"})
    assert response.status_code == 401


def test_me_rejects_garbage_token(client) -> None:
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


def test_me_rejects_expired_token(client, conn: psycopg.Connection) -> None:
    user_id = create_user(conn, "alice")
    token = token_for(user_id, expires_in=-60)
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "expired" in response.json()["detail"]


def test_me_rejects_wrong_audience(client, conn: psycopg.Connection) -> None:
    user_id = create_user(conn, "alice")
    token = token_for(user_id, audience="anon")
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_me_rejects_token_signed_with_another_secret(client, conn: psycopg.Connection) -> None:
    user_id = create_user(conn, "alice")
    token = token_for(user_id, secret="a-different-secret-that-is-long-enough-to-avoid-warnings")
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_me_returns_the_callers_profile(client, conn: psycopg.Connection) -> None:
    user_id = create_user(conn, "alice", "Alice")
    token = token_for(user_id, email="alice@example.test")
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(user_id)
    assert body["username"] == "alice"
    assert body["display_name"] == "Alice"


def test_me_does_not_duplicate_the_profile(client, conn: psycopg.Connection) -> None:
    user_id = create_user(conn, "alice")
    token = token_for(user_id)
    for _ in range(3):
        assert client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        ).status_code == 200
    count = conn.execute(
        "select count(*) from public.profiles where id = %s", (user_id,)
    ).fetchone()[0]
    assert count == 1


def test_me_recovers_when_the_profile_row_is_missing(
    client, conn: psycopg.Connection
) -> None:
    user_id = create_user(conn, "alice")
    conn.execute("delete from public.profiles where id = %s", (user_id,))
    token = token_for(user_id, email="alice@example.test")
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["username"].startswith("alice")


def test_patch_updates_display_name_and_bio(client, conn: psycopg.Connection) -> None:
    user_id = create_user(conn, "alice")
    token = token_for(user_id)
    response = client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"display_name": "Alice B", "bio": "Third year student."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Alice B"
    assert body["bio"] == "Third year student."


def test_patch_can_clear_the_bio(client, conn: psycopg.Connection) -> None:
    user_id = create_user(conn, "alice")
    token = token_for(user_id)
    client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"bio": "temporary"},
    )
    response = client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"bio": None},
    )
    assert response.status_code == 200
    assert response.json()["bio"] is None


def test_patch_forbids_unknown_fields(client, conn: psycopg.Connection) -> None:
    user_id = create_user(conn, "alice")
    token = token_for(user_id)
    response = client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"id": str(create_user(conn, "bob"))},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {"display_name": ""},
        {"display_name": "x" * 81},
        {"bio": "x" * 501},
    ],
)
def test_patch_validates_lengths(client, conn: psycopg.Connection, payload: dict) -> None:
    user_id = create_user(conn, "alice")
    token = token_for(user_id)
    response = client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert response.status_code == 422


def test_patch_cannot_change_another_user(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    token = token_for(alice)

    response = client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"display_name": "Alice Changed"},
    )
    assert response.status_code == 200

    bob_name = conn.execute(
        "select display_name from public.profiles where id = %s", (bob,)
    ).fetchone()[0]
    assert bob_name == "Bob"
