"""Resilient Redis cache abstraction with safe no-cache fallback."""

from __future__ import annotations

import json
import logging
import time
from functools import lru_cache
from typing import Any

from mayabu.core.config import get_app_settings

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None

logger = logging.getLogger(__name__)

# Keep in sync with mayabu.search.category_registry.SEARCH_CONTRACT_VERSION
_SEARCH_CACHE_PREFIX = "search:v6:"


class Cache:
    def __init__(self) -> None:
        settings = get_app_settings()
        self.enabled = bool(settings.enable_redis_cache and settings.redis_url and redis)
        self.client = None
        self._disabled_until = 0.0
        if self.enabled:
            self.client = redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=1.5,
                socket_timeout=1.5,
                health_check_interval=30,
                retry_on_timeout=True,
            )

    def _available(self) -> bool:
        return bool(self.client and time.monotonic() >= self._disabled_until)

    def _failed(self, exc: Exception) -> None:
        self._disabled_until = time.monotonic() + 15
        logger.warning("redis_temporarily_disabled", extra={"error": str(exc)[:300]})

    def note_failure(self, exc: Exception) -> None:
        """Expose the shared Redis backoff to coordination helpers."""
        self._failed(exc)

    def coordination_client(self):
        """Return the raw client only while Redis is considered healthy."""
        return self.client if self._available() else None

    def get_json(self, key: str) -> Any | None:
        if not self._available():
            return None
        try:
            value = self.client.get(key)
            return json.loads(value) if value is not None else None
        except Exception as exc:
            self._failed(exc)
            return None

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        if not self._available():
            return
        try:
            self.client.setex(key, max(1, int(ttl_seconds)), json.dumps(value, default=str, separators=(",", ":")))
        except Exception as exc:
            self._failed(exc)

    def set_if_absent(self, key: str, value: Any, ttl_seconds: int) -> bool | None:
        """Set a short-lived coordination key. None means Redis unavailable."""
        if not self._available():
            return None
        try:
            encoded = json.dumps(value, default=str, separators=(",", ":"))
            return bool(self.client.set(key, encoded, ex=max(1, int(ttl_seconds)), nx=True))
        except Exception as exc:
            self._failed(exc)
            return None

    def delete(self, key: str) -> None:
        if not self._available():
            return
        try:
            self.client.delete(key)
        except Exception as exc:
            self._failed(exc)

    def delete_prefix(self, prefix: str, batch_size: int = 500) -> int:
        if not self._available():
            return 0
        deleted = 0
        try:
            keys: list[str] = []
            for key in self.client.scan_iter(match=f"{prefix}*", count=batch_size):
                keys.append(key)
                if len(keys) >= batch_size:
                    deleted += int(self.client.delete(*keys) or 0)
                    keys.clear()
            if keys:
                deleted += int(self.client.delete(*keys) or 0)
            return deleted
        except Exception as exc:
            self._failed(exc)
            return deleted

    def ping(self) -> bool:
        if not self._available():
            return False
        try:
            return bool(self.client.ping())
        except Exception as exc:
            self._failed(exc)
            return False

    def invalidate_product(self, product_id: str) -> int:
        """Invalidate only strongly product-scoped data.

        Search and suggest responses are intentionally eventually consistent and
        expire via short TTL (suggest ≤30s). Clearing every search/suggest key for
        every price refresh turns Redis into a permanent miss cache under normal
        worker load. Maximum documented suggest staleness after a material price
        change is therefore the suggest TTL.
        """
        total = self.delete_prefix(f"product:{product_id}:")
        total += self.delete_prefix(f"price-history:{product_id}:")
        total += self.delete_prefix(f"price-intelligence:{product_id}:")
        return total

    def invalidate_search(self) -> int:
        """Explicit bulk invalidation for migrations or manual catalog rebuilds."""
        total = self.delete_prefix(_SEARCH_CACHE_PREFIX)
        total += self.delete_prefix("suggest:")
        return total


@lru_cache(maxsize=1)
def get_cache() -> Cache:
    """Return one process-local cache client shared by API and worker code."""
    return Cache()
