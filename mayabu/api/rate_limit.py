"""Reusable bounded sliding-window rate limiter.

Redis provides cross-process enforcement. A bounded process-local fallback keeps
one API process safe when Redis is absent in development. Verification can add a
global limit so a burst of many different products cannot exhaust PostgreSQL.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from threading import Lock

from mayabu.search.cache import get_cache

_REDIS_SCRIPT = """
local now = tonumber(ARGV[1])
local cutoff = tonumber(ARGV[2])
local token = ARGV[3]
local client_limit = tonumber(ARGV[4])
local global_limit = tonumber(ARGV[5])
local ttl = tonumber(ARGV[6])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', cutoff)
if redis.call('ZCARD', KEYS[1]) >= client_limit then return 0 end
if global_limit > 0 then
  redis.call('ZREMRANGEBYSCORE', KEYS[2], '-inf', cutoff)
  if redis.call('ZCARD', KEYS[2]) >= global_limit then return -1 end
end
redis.call('ZADD', KEYS[1], now, token)
redis.call('EXPIRE', KEYS[1], ttl)
if global_limit > 0 then
  redis.call('ZADD', KEYS[2], now, token)
  redis.call('EXPIRE', KEYS[2], ttl)
end
return 1
"""


class SlidingWindowLimiter:
    def __init__(self, namespace: str, *, window_seconds: int = 60, max_memory_keys: int = 10_000) -> None:
        self.namespace = namespace
        self.window_seconds = max(1, int(window_seconds))
        self.max_memory_keys = max(100, int(max_memory_keys))
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._global_events: deque[float] = deque()
        self._lock = Lock()
        self._cache = get_cache()

    def allow(
        self,
        identifier: str,
        *,
        per_key_limit: int,
        global_limit: int | None = None,
        fail_closed_global: bool = False,
    ) -> str:
        """Return allowed, client_limited, or global_limited."""
        per_key_limit = max(1, int(per_key_limit))
        global_limit_value = max(0, int(global_limit or 0))
        client = self._cache.client if self._cache._available() else None  # noqa: SLF001
        if client is not None:
            now = time.time()
            token = f"{now}:{uuid.uuid4().hex}"
            client_key = f"rl:{self.namespace}:client:{identifier}"
            global_key = f"rl:{self.namespace}:global"
            try:
                result = int(
                    client.eval(
                        _REDIS_SCRIPT,
                        2,
                        client_key,
                        global_key,
                        now,
                        now - self.window_seconds,
                        token,
                        per_key_limit,
                        global_limit_value,
                        self.window_seconds * 2,
                    )
                )
                return "allowed" if result == 1 else ("global_limited" if result == -1 else "client_limited")
            except Exception as exc:
                self._cache._failed(exc)  # noqa: SLF001
                if fail_closed_global and global_limit_value:
                    return "global_limited"
        elif fail_closed_global and global_limit_value and self._cache.enabled:
            return "global_limited"
        return self._allow_memory(identifier, per_key_limit, global_limit_value)

    def _allow_memory(self, identifier: str, per_key_limit: int, global_limit: int) -> str:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            while self._global_events and self._global_events[0] <= cutoff:
                self._global_events.popleft()
            if len(self._events) > self.max_memory_keys:
                stale = [key for key, values in self._events.items() if not values or values[-1] <= cutoff]
                for key in stale[: max(1, self.max_memory_keys // 2)]:
                    self._events.pop(key, None)
            events = self._events[identifier]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= per_key_limit:
                return "client_limited"
            if global_limit and len(self._global_events) >= global_limit:
                return "global_limited"
            events.append(now)
            if global_limit:
                self._global_events.append(now)
            return "allowed"
