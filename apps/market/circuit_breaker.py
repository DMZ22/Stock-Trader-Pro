"""
Circuit breaker for provider resilience.

Tracks per-provider failure rates. If a provider hits N consecutive failures
within a window, it's skipped for a cooldown period. This prevents wasting
time on broken/rate-limited providers during a scan.
"""
import time
import threading
from collections import defaultdict, deque
from typing import Dict


class ProviderCircuit:
    """Circuit state for a single provider."""

    def __init__(self, failure_threshold: int = 3, cooldown_sec: int = 60,
                 window_sec: int = 120):
        self.failure_threshold = failure_threshold
        self.cooldown_sec = cooldown_sec
        self.window_sec = window_sec
        self.failures = deque()  # timestamps of recent failures
        self.open_until = 0  # circuit open until this timestamp
        self.successes = 0
        self.total_calls = 0
        self._lock = threading.Lock()

    def is_open(self) -> bool:
        """Returns True if circuit is open (provider should be skipped)."""
        with self._lock:
            now = time.time()
            # Evict old failures
            while self.failures and now - self.failures[0] > self.window_sec:
                self.failures.popleft()
            return now < self.open_until

    def record_success(self):
        with self._lock:
            self.successes += 1
            self.total_calls += 1
            self.failures.clear()
            self.open_until = 0

    def record_failure(self):
        with self._lock:
            now = time.time()
            self.failures.append(now)
            self.total_calls += 1
            # Evict old
            while self.failures and now - self.failures[0] > self.window_sec:
                self.failures.popleft()
            if len(self.failures) >= self.failure_threshold:
                self.open_until = now + self.cooldown_sec

    def stats(self) -> dict:
        with self._lock:
            now = time.time()
            return {
                "recent_failures": len(self.failures),
                "total_calls": self.total_calls,
                "successes": self.successes,
                "circuit_open": now < self.open_until,
                "cooldown_remaining_sec": max(0, int(self.open_until - now)),
            }


class CircuitBreakerRegistry:
    def __init__(self):
        self._circuits: Dict[str, ProviderCircuit] = defaultdict(ProviderCircuit)
        self._lock = threading.Lock()

    def get(self, provider: str) -> ProviderCircuit:
        with self._lock:
            return self._circuits[provider]

    def all_stats(self) -> dict:
        return {name: c.stats() for name, c in self._circuits.items()}


REGISTRY = CircuitBreakerRegistry()
