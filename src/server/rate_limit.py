"""In-process sliding-window rate limiter keyed on ``account_id``.

Sprint 5A.2 deliberately ships a tiny stdlib-only limiter rather than
adding ``slowapi`` / Redis to the dependency tree:

* zero new third-party dependencies (B-95 mandate),
* deterministic, monkeypatch-friendly tests (no clock skew with Redis),
* fits the existing ``RateLimitError`` pattern from ``src.core.auth``.

The implementation keeps one ``deque`` of unix-timestamp floats per
account, prunes entries older than 60 seconds on every check, and raises
``RateLimitExceeded`` once the window is full.  All mutations happen
inside a single ``threading.Lock`` so concurrent FastAPI worker threads
cannot tear the deque.

Refs: [BL B-95] [REQ R16.7]
"""
from __future__ import annotations

import collections
import math
import threading
import time
from typing import Deque, Dict


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
