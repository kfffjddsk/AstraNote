"""Sliding-window rate limiter keyed on ``account_id``.

Two backends are available:

* **In-process** (``AccountRateLimiter``) — stdlib-only, zero dependencies,
  deterministic for tests.  Resets on process restart; not suitable for
  multi-worker deployments where each worker maintains its own counter.
* **Redis-backed** (``RedisRateLimiter``) — requires the ``redis`` package and
  ``ASTRANOTES_REDIS_URL`` env var.  Stores a sorted set per account so the
  window is shared across all worker processes.

Use ``make_rate_limiter(per_minute, redis_url)`` to get the right
implementation at startup.  The Redis path falls back gracefully to the
in-process limiter when ``redis`` is not installed or the connection fails.

Refs: [BL B-95] [REQ R16.7]
"""
from __future__ import annotations

import collections
import logging
import math
import threading
import time
from typing import Deque, Dict, Union

logger = logging.getLogger(__name__)

try:
    import redis as _redis_mod

    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False


class RateLimitExceeded(Exception):
    """Raised by :meth:`AccountRateLimiter.check` when the window is full."""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(
            f"rate limit exceeded; retry after {retry_after_seconds}s"
        )
        self.retry_after_seconds = retry_after_seconds


class AccountRateLimiter:
    """Thread-safe sliding-window counter (``per_minute`` requests / 60 s)."""

    def __init__(self, per_minute: int) -> None:
        if per_minute < 1:
            raise ValueError("per_minute must be >= 1")
        self.per_minute = per_minute
        self._buckets: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, account_id: str) -> None:
        """Record a successful call for *account_id* or raise.

        Raises :class:`RateLimitExceeded` if the account already used up
        its quota inside the last 60 seconds.  ``retry_after_seconds`` on
        the exception is the ceiling of seconds until the oldest entry
        ages out of the window (always at least 1 so clients have a
        useful ``Retry-After`` value).
        """
        now = time.time()
        cutoff = now - 60.0
        with self._lock:
            bucket = self._buckets.get(account_id)
            if bucket is None:
                bucket = collections.deque()
                self._buckets[account_id] = bucket

            # Prune timestamps outside the rolling 60-second window.
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= self.per_minute:
                oldest = bucket[0]
                retry = max(1, math.ceil(60.0 - (now - oldest)))
                raise RateLimitExceeded(retry)

            bucket.append(now)


class RedisRateLimiter:
    """Sliding-window rate limiter backed by a Redis sorted set.

    Each account gets a key ``astranotes:rl:<account_id>`` whose members are
    request timestamps.  Because the set lives in Redis, the window is shared
    across all worker processes — correct under multi-worker deployments.

    Requires the ``redis`` package (``pip install redis``) and a reachable
    Redis server.

    Refs: [BL B-95] [REQ R16.7]
    """

    _WINDOW = 60  # seconds

    def __init__(self, redis_url: str, per_minute: int) -> None:
        if per_minute < 1:
            raise ValueError("per_minute must be >= 1")
        if not _REDIS_AVAILABLE:
            raise RuntimeError(
                "redis package is not installed; "
                "run 'pip install redis' to enable the Redis rate limiter"
            )
        self.per_minute = per_minute
        self._client = _redis_mod.from_url(redis_url, decode_responses=False)

    def check(self, account_id: str) -> None:
        """Record a call for *account_id* or raise :class:`RateLimitExceeded`.

        Two round-trips to Redis:
        1. Atomic prune+count (pipeline).
        2. Conditional zadd + expire only when the limit is not exceeded.
        """
        now = time.time()
        cutoff = now - self._WINDOW
        key = f"astranotes:rl:{account_id}"

        pipe = self._client.pipeline(transaction=True)
        pipe.zremrangebyscore(key, "-inf", cutoff)
        pipe.zcard(key)
        _, count = pipe.execute()

        if count >= self.per_minute:
            oldest_raw = self._client.zrange(key, 0, 0, withscores=True)
            if oldest_raw:
                oldest_ts = oldest_raw[0][1]
                retry = max(1, math.ceil(self._WINDOW - (now - oldest_ts)))
            else:
                retry = 1
            raise RateLimitExceeded(retry)

        pipe = self._client.pipeline(transaction=True)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, self._WINDOW + 10)
        pipe.execute()


def make_rate_limiter(
    per_minute: int, redis_url: str = ""
) -> "Union[AccountRateLimiter, RedisRateLimiter]":
    """Return the best available rate limiter.

    Uses :class:`RedisRateLimiter` when *redis_url* is non-empty **and** the
    ``redis`` package is installed **and** a ``PING`` to the server succeeds.
    Falls back to :class:`AccountRateLimiter` (in-process) otherwise.
    """
    if redis_url and _REDIS_AVAILABLE:
        try:
            limiter = RedisRateLimiter(redis_url, per_minute)
            limiter._client.ping()
            logger.info("Rate limiter: Redis backend at %s", redis_url)
            return limiter
        except Exception as exc:
            logger.warning(
                "Redis rate limiter unavailable (%s); "
                "falling back to in-process limiter.",
                exc,
            )
    return AccountRateLimiter(per_minute)
