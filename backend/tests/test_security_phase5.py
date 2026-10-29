"""Phase 5 security tests: CORS, token algorithms, injection, path traversal and error leakage."""

from __future__ import annotations

import base64
import json
import uuid
from pathlib import Path

import psycopg
import pytest

from .conftest import STORAGE_ROOT, create_user, make_photo, token_for

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 300
ALLOWED_ORIGIN = "http://localhost:5173"
EVIL_ORIGIN = "http://evil.example"


def auth(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_for(user_id)}"}


# ---------------------------------------------------------------- CORS


def test_cors_allows_the_configured_origin(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    response = client.get("/api/v1/photos", headers={**auth(alice), "Origin": ALLOWED_ORIGIN})
    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


def test_cors_does_not_allow_an_unknown_origin(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    response = client.get("/api/v1/photos", headers={**auth(alice), "Origin": EVIL_ORIGIN})
    assert "access-control-allow-origin" not in response.headers


def test_cors_preflight_allows_authorization_header(client) -> None:
    response = client.options(
        "/api/v1/photos",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code in (200, 204)
    assert "authorization" in response.headers.get("access-control-allow-headers", "").lower()


# ---------------------------------------------------------------- token handling


def test_unsigned_token_is_rejected(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")

    def b64(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")

    forged = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': str(alice), 'aud': 'authenticated'})}."
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_401_response_carries_a_challenge(client) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Bearer")


# ---------------------------------------------------------------- input handling


@pytest.mark.parametrize(
    "payload",
    ["' OR 1=1 --", "%' OR '1'='1", "'; drop table public.photos; --"],
)
def test_search_is_parameterised(client, conn: psycopg.Connection, payload: str) -> None:
    alice = create_user(conn, "alice")
    make_photo(conn, alice, caption="ordinary")
    response = client.get(
        "/api/v1/photos/search", params={"q": payload}, headers=auth(alice)
    )
    assert response.status_code == 200
    assert response.json()["total"] == 0
    # The table must still exist and hold the row.
    assert conn.execute("select count(*) from public.photos").fetchone()[0] == 1


def test_upload_filename_cannot_escape_the_storage_root(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    response = client.post(
        "/api/v1/photos",
        headers=auth(alice),
        files={"file": ("../../etc/passwd.jpg", JPEG, "image/jpeg")},
        data={"caption": "traversal", "visibility": "owner"},
    )
    assert response.status_code == 201, response.text
    row = conn.execute(
        "select storage_path from public.photos where id = %s", (response.json()["id"],)
    ).fetchone()
    stored = Path(STORAGE_ROOT) / row[0]
    assert stored.resolve().is_relative_to(Path(STORAGE_ROOT).resolve())
    assert stored.exists()
    # The generated name is the photo id, so the supplied filename is not used at all.
    assert "passwd" not in row[0] and ".." not in row[0]


def test_validation_errors_do_not_leak_internals(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    response = client.get("/api/v1/photos/not-a-uuid", headers=auth(alice))
    assert response.status_code == 422
    body = response.text
    for forbidden in ("Traceback", "psycopg", "site-packages", "select ", "INSERT INTO"):
        assert forbidden not in body


def test_upload_rejects_a_json_body_instead_of_a_file(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    response = client.post(
        "/api/v1/photos", headers={**auth(alice), "Content-Type": "application/json"}, json={}
    )
    assert response.status_code == 422
