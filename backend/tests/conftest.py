"""Shared test fixtures.

The suite runs against a real PostgreSQL instance. It creates a dedicated database, applies a
minimal Supabase stub (auth schema, auth.uid(), storage schema, roles) and then applies the
production migration. Nothing touches an existing database, and no cloud account is required.

RLS is exercised by switching to the `authenticated` role, which is subject to the same policies
a browser client would be. Running as the table owner would silently bypass RLS and prove nothing.
"""

from __future__ import annotations

import os
import secrets
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

import psycopg
import pytest
from psycopg.types.json import Jsonb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_DIR = PROJECT_ROOT / "database"

TEST_DB = os.environ.get("ITP_TEST_DB", "itp_photo_test")
DB_USER = os.environ.get("ITP_TEST_USER", "itp_app")
DB_PASS = os.environ.get("ITP_TEST_PASSWORD", "itp_local_only")
DB_HOST = os.environ.get("ITP_TEST_HOST", "127.0.0.1")
DB_PORT = os.environ.get("ITP_TEST_PORT", "5432")

ADMIN_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/postgres"
TEST_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{TEST_DB}"

JWT_SECRET = "test-secret-not-used-anywhere-else-0123456789"
STORAGE_ROOT = tempfile.mkdtemp(prefix="itp-storage-")
STORAGE_SIGNING_SECRET = secrets.token_hex(16)
os.environ["DATABASE_URL"] = TEST_URL
os.environ["SUPABASE_JWT_SECRET"] = JWT_SECRET
os.environ["APP_ENV"] = "test"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["STORAGE_LOCAL_ROOT"] = STORAGE_ROOT
os.environ["STORAGE_SIGNING_SECRET"] = STORAGE_SIGNING_SECRET

TABLES = ("photo_tags", "comments", "photos", "friendships", "profiles")


def _read(name: str) -> str:
    return (DB_DIR / name).read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def prepared_database() -> Iterator[str]:
    try:
        admin = psycopg.connect(ADMIN_URL, autocommit=True)
    except psycopg.OperationalError as exc:  # pragma: no cover - environment guard
        pytest.exit(
            "Cannot reach PostgreSQL as the test role. Run "
            "'bash database/testing/setup_local_role.sh' as root first.\n"
            f"Original error: {exc}",
            returncode=2,
        )

    with admin:
        admin.execute(f'drop database if exists "{TEST_DB}" with (force)')
        # Create explicitly as UTF8 from template0. This cluster's templates are SQL_ASCII, and a
        # SQL_ASCII database makes psycopg return every text column as bytes. Supabase is UTF8, so
        # the test database must be too, or the tests would exercise a different encoding.
        admin.execute(
            f'create database "{TEST_DB}" with encoding \'UTF8\' template template0'
        )

    conn = psycopg.connect(TEST_URL, autocommit=True)
    with conn:
        conn.execute(_read("testing/000_local_supabase_stub.sql"))
        # Apply every migration in order, so the harness reflects the real schema evolution.
        for migration in sorted((DB_DIR / "migrations").glob("*.sql")):
            conn.execute(migration.read_text(encoding="utf-8"))
    conn.close()

    yield TEST_URL

    with psycopg.connect(ADMIN_URL, autocommit=True) as admin2:
        admin2.execute(f'drop database if exists "{TEST_DB}" with (force)')


@pytest.fixture()
def conn(prepared_database: str) -> Iterator[psycopg.Connection]:
    connection = psycopg.connect(prepared_database, autocommit=True)
    connection.execute(
        "truncate table public.photo_tags, public.comments, public.photos, "
        "public.friendships, public.profiles, auth.users, storage.objects "
        "restart identity cascade"
    )
    # Storage is a directory, not a table, so it is cleared separately.
    for child in Path(STORAGE_ROOT).glob("*"):
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)
    yield connection
    connection.close()


def create_user(
    conn: psycopg.Connection,
    username: str,
    display_name: str | None = None,
    email: str | None = None,
) -> uuid.UUID:
    """Insert an auth user, which fires the profile trigger, and return the id."""
    user_id = uuid.uuid4()
    conn.execute(
        """
        insert into auth.users (id, email, raw_user_meta_data)
        values (%s, %s, %s)
        """,
        (
            user_id,
            email or f"{username}@example.test",
            Jsonb({"username": username, "display_name": display_name or username.title()}),
        ),
    )
    return user_id


@contextmanager
def acting_as(conn: psycopg.Connection, user_id: uuid.UUID | None) -> Iterator[psycopg.Connection]:
    """Run subsequent statements as an authenticated user, subject to RLS."""
    conn.execute("set role authenticated")
    conn.execute("select set_config('request.jwt.claim.sub', %s, false)", (str(user_id or ""),))
    try:
        yield conn
    finally:
        conn.execute("reset role")
        conn.execute("select set_config('request.jwt.claim.sub', '', false)")


def make_photo(
    conn: psycopg.Connection,
    owner_id: uuid.UUID,
    visibility: str = "friends",
    caption: str = "photo",
    mime_type: str = "image/jpeg",
    size_bytes: int = 1024,
) -> uuid.UUID:
    photo_id = uuid.uuid4()
    conn.execute(
        """
        insert into public.photos
            (id, owner_id, storage_path, caption, mime_type, size_bytes, visibility)
        values (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            photo_id,
            owner_id,
            f"{owner_id}/{photo_id}.jpg",
            caption,
            mime_type,
            size_bytes,
            visibility,
        ),
    )
    return photo_id


def make_friends(conn: psycopg.Connection, a: uuid.UUID, b: uuid.UUID) -> None:
    conn.execute(
        """
        insert into public.friendships (requester_id, addressee_id, status, responded_at)
        values (%s, %s, 'accepted', now())
        """,
        (a, b),
    )


def token_for(
    user_id: uuid.UUID,
    email: str = "user@example.test",
    expires_in: int = 3600,
    audience: str = "authenticated",
    secret: str = JWT_SECRET,
) -> str:
    import jwt

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "aud": audience,
        "role": "authenticated",
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture()
def client(prepared_database: str):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
