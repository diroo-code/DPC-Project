"""Database access.

The backend connects directly to PostgreSQL. Queries are explicit, parameterised, and every
permission decision is made in application code as well as in RLS, because the backend role
is privileged.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import settings

_pool: ConnectionPool | None = None


class DatabaseNotConfigured(RuntimeError):
    pass


def get_pool() -> ConnectionPool:
    """Create the pool on first use, so the app can start and serve /health without a database."""
    global _pool
    if _pool is None:
        if not settings.database_url:
            raise DatabaseNotConfigured("DATABASE_URL is not set")
        _pool = ConnectionPool(
            conninfo=settings.database_url,
            min_size=1,
            max_size=10,
            timeout=10,
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    pool = get_pool()
    with pool.connection() as conn:
        yield conn


def fetch_one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


def execute(query: str, params: tuple[Any, ...] = ()) -> int:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.rowcount


def ping() -> bool:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select 1 as ok")
            row = cur.fetchone()
            return bool(row and row["ok"] == 1)
