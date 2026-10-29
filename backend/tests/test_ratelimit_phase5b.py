"""Rate limiter tests: window behaviour, concurrency, and endpoint enforcement."""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest

from app import ratelimit

from .conftest import create_user, make_friends, make_photo, token_for

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 300


def auth(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_for(user_id)}"}


@pytest.fixture(autouse=True)
def clean_limiter(monkeypatch):
    ratelimit.limiter.reset()
    yield
    ratelimit.limiter.reset()


# ---------------------------------------------------------------- unit behaviour


def test_allows_the_budget_then_blocks() -> None:
    limiter = ratelimit.SlidingWindowLimiter()
    key = f"test:{uuid.uuid4()}"
    for _ in range(3):
        assert limiter.check(key, 3, 60)[0] is True
    allowed, retry_after = limiter.check(key, 3, 60)
    assert allowed is False
    assert retry_after >= 1


def test_window_expiry_releases_the_budget() -> None:
    limiter = ratelimit.SlidingWindowLimiter()
    key = f"test:{uuid.uuid4()}"
    assert limiter.check(key, 1, 1)[0] is True
    assert limiter.check(key, 1, 1)[0] is False
    time.sleep(1.1)
    assert limiter.check(key, 1, 1)[0] is True


def test_concurrent_requests_cannot_exceed_the_limit() -> None:
    """Thirty threads race for ten slots. Exactly ten must win."""
    limiter = ratelimit.SlidingWindowLimiter()
    key = f"test:{uuid.uuid4()}"
    barrier = threading.Barrier(30)
    outcomes: list[bool] = []
    lock = threading.Lock()

    def attempt() -> None:
        barrier.wait()
        allowed, _ = limiter.check(key, 10, 60)
        with lock:
            outcomes.append(allowed)

    with ThreadPoolExecutor(max_workers=30) as pool:
        list(pool.map(lambda _: attempt(), range(30)))

    assert outcomes.count(True) == 10
    assert outcomes.count(False) == 20


def test_identities_have_separate_budgets() -> None:
    limiter = ratelimit.SlidingWindowLimiter()
    a, b = f"a:{uuid.uuid4()}", f"b:{uuid.uuid4()}"
    assert limiter.check(a, 1, 60)[0] is True
    assert limiter.check(a, 1, 60)[0] is False
    assert limiter.check(b, 1, 60)[0] is True


# ---------------------------------------------------------------- endpoint enforcement


def test_comment_endpoint_returns_429_with_retry_after(
    client, conn: psycopg.Connection, monkeypatch
) -> None:
    monkeypatch.setitem(ratelimit.LIMITS, "comment", (2, 60))
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    make_friends(conn, alice, bob)
    photo = make_photo(conn, alice, visibility="friends")

    assert client.post(
        f"/api/v1/photos/{photo}/comments", headers=auth(bob), json={"body": "one"}
    ).status_code == 201
    assert client.post(
        f"/api/v1/photos/{photo}/comments", headers=auth(bob), json={"body": "two"}
    ).status_code == 201

    blocked = client.post(
        f"/api/v1/photos/{photo}/comments", headers=auth(bob), json={"body": "three"}
    )
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    assert int(blocked.headers["Retry-After"]) >= 1
    assert "rate limit" in blocked.json()["detail"]


def test_one_user_cannot_spend_another_users_budget(
    client, conn: psycopg.Connection, monkeypatch
) -> None:
    monkeypatch.setitem(ratelimit.LIMITS, "comment", (1, 60))
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    make_friends(conn, alice, bob)
    photo = make_photo(conn, alice, visibility="friends")

    assert client.post(
        f"/api/v1/photos/{photo}/comments", headers=auth(bob), json={"body": "bob"}
    ).status_code == 201
    assert client.post(
        f"/api/v1/photos/{photo}/comments", headers=auth(bob), json={"body": "again"}
    ).status_code == 429
    # Alice has her own budget and is unaffected.
    assert client.post(
        f"/api/v1/photos/{photo}/comments", headers=auth(alice), json={"body": "alice"}
    ).status_code == 201


def test_upload_endpoint_is_limited(client, conn: psycopg.Connection, monkeypatch) -> None:
    monkeypatch.setitem(ratelimit.LIMITS, "upload", (1, 60))
    alice = create_user(conn, "alice")

    first = client.post(
        "/api/v1/photos",
        headers=auth(alice),
        files={"file": ("a.jpg", JPEG, "image/jpeg")},
        data={"caption": "one", "visibility": "owner"},
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/photos",
        headers=auth(alice),
        files={"file": ("b.jpg", JPEG, "image/jpeg")},
        data={"caption": "two", "visibility": "owner"},
    )
    assert second.status_code == 429

    # The rejected request must not have stored an object or a row.
    assert conn.execute("select count(*) from public.photos").fetchone()[0] == 1


def test_rejected_request_is_not_counted(monkeypatch) -> None:
    """A blocked request must not extend the window, or a client could lock itself out forever."""
    limiter = ratelimit.SlidingWindowLimiter()
    key = f"test:{uuid.uuid4()}"
    assert limiter.check(key, 1, 60)[0] is True
    for _ in range(5):
        assert limiter.check(key, 1, 60)[0] is False
    # Still blocked, and the retry hint stays bounded by the original window.
    allowed, retry_after = limiter.check(key, 1, 60)
    assert allowed is False and retry_after <= 60
