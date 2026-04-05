"""Thread-safe token bucket rate limiter with per-provider tracking."""
import time
import threading
from collections import deque
from typing import Dict


class TokenBucket:
    """Sliding window rate limiter."""

    def __init__(self, requests_per_minute: int):
        self.max_requests = max(1, requests_per_minute)
        self.window = 60.0
        self._timestamps = deque()
        self._lock = threading.Lock()

    def acquire(self, blocking: bool = True, timeout: float = 30.0) -> bool:
        start = time.time()
        while True:
            with self._lock:
                now = time.time()
                # Evict old timestamps
                while self._timestamps and now - self._timestamps[0] > self.window:
                    self._timestamps.popleft()
                if len(self._timestamps) < self.max_requests:
                    self._timestamps.append(now)
                    return True
                wait = self.window - (now - self._timestamps[0]) + 0.05
            if not blocking or (time.time() - start) > timeout:
                return False
            time.sleep(min(wait, 1.0))

    def reset(self):
        with self._lock:
            self._timestamps.clear()


class RateLimiterRegistry:
    """Global per-provider rate limiter registry."""

    def __init__(self):
        self._buckets: Dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

    def get(self, provider: str, rpm: int) -> TokenBucket:
        with self._lock:
            if provider not in self._buckets:
                self._buckets[provider] = TokenBucket(rpm)
            return self._buckets[provider]


REGISTRY = RateLimiterRegistry()
