"""Server-side rate limiting.

A sliding window per identity, held in memory. Trade-offs are deliberate and documented:

* In-memory means each worker process has its own counters. With one Uvicorn process that is exact;
  with several workers the effective limit is per worker. A shared store (Redis) would be needed for a
  cluster, and that is recorded as a deployment note rather than pretended away.
* Identity is the authenticated user id, so one account cannot exhaust another's budget and anonymous
  floods are still bounded by the per-IP fallback where it applies.
* A threading.Lock guards the window so concurrent requests cannot both slip past the last slot. That is
  tested with a real thread pool.
"""

from __future__ import annotations

import threading
import time
from collections import deque

from fastapi import Depends, HTTPException, Request, status

from .deps import CurrentUser, get_current_user

# bucket -> (limit, window seconds). Mutable so tests can tighten a single bucket without affecting
# the rest of the suite.
LIMITS: dict[str, tuple[int, int]] = {
    "upload": (10, 60),
    "comment": (20, 60),
    "friend_request": (10, 3600),
    "signed_url": (60, 60),
    "photo_delete": (20, 60),
}


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds). Counts the request only when it is allowed."""
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, int(events[0] + window_seconds - now) + 1)
                return False, retry_after
            events.append(now)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


limiter = SlidingWindowLimiter()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def rate_limit(bucket: str):
    """Dependency factory. Returns 429 with Retry-After when the budget is exhausted."""

    def dependency(request: Request, user: CurrentUser = Depends(get_current_user)) -> None:
        limit, window = LIMITS[bucket]
        allowed, retry_after = limiter.check(f"{bucket}:{user.id}", limit, window)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"rate limit exceeded for {bucket.replace('_', ' ')}",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
