import time
from collections import defaultdict
from threading import Lock


class RateLimitExceeded(Exception):
    public_message = "Too many requests. Wait a moment and try again."


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        with self._lock:
            recent = [stamp for stamp in self._hits[key] if now - stamp < window_seconds]
            if len(recent) >= limit:
                self._hits[key] = recent
                raise RateLimitExceeded()
            recent.append(now)
            self._hits[key] = recent

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()
