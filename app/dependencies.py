"""Shared dependency providers (DB session, rate limiter, etc.)."""
from __future__ import annotations
import time
import threading
from collections import defaultdict
from app.config import settings


class RateLimiter:
    """Token-bucket rate limiter, per user_id."""

    def __init__(self, max_per_minute: int = settings.rate_limit_per_minute):
        self.max_per_minute = max_per_minute
        self._lock = threading.Lock()
        self._counts: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, user_id: str) -> bool:
        now = time.time()
        window_start = now - 60.0
        with self._lock:
            self._counts[user_id] = [t for t in self._counts[user_id] if t > window_start]
            if len(self._counts[user_id]) >= self.max_per_minute:
                return False
            self._counts[user_id].append(now)
        return True


rate_limiter = RateLimiter()
