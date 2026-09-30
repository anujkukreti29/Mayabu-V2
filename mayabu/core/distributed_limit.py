"""Renewable Redis-backed concurrency limits shared by worker replicas.

Each active operation owns a token in a Redis sorted set. Expired tokens are
removed atomically during acquisition, and a lightweight heartbeat renews the
lease until the operation finishes. Production fails closed if coordination is
lost so scraper replicas cannot silently exceed retailer budgets.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import time
import uuid
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from typing import AsyncIterator, Any

from mayabu.core.config import get_app_settings
from mayabu.search.cache import Cache, get_cache

logger = logging.getLogger(__name__)


class DistributedCapacityError(RuntimeError):
    """Raised when a distributed concurrency slot cannot be held safely."""


@dataclass(frozen=True, slots=True)
class SlotPolicy:
    """Validated limits for one distributed slot acquisition."""

    limit: int
    ttl_seconds: int
    wait_seconds: float

    @classmethod
    def normalized(
        cls, limit: int, ttl_seconds: int, wait_seconds: float
    ) -> "SlotPolicy":
        return cls(
            limit=max(1, int(limit)),
            ttl_seconds=max(15, int(ttl_seconds)),
            wait_seconds=max(0.1, float(wait_seconds)),
        )


_ACQUIRE_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local expires = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local token = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, '-inf', now)
if redis.call('ZCARD', key) >= limit then return 0 end
redis.call('ZADD', key, expires, token)
redis.call('EXPIRE', key, math.max(1, math.ceil((expires-now) * 2)))
return 1
"""

_RENEW_SCRIPT = """
local key = KEYS[1]
local token = ARGV[1]
local expires = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
if redis.call('ZSCORE', key, token) == false then return 0 end
redis.call('ZADD', key, expires, token)
redis.call('EXPIRE', key, math.max(1, math.ceil((expires-now) * 2)))
return 1
"""

_SAFE_KEY_PART = re.compile(r"[^a-z0-9_.-]+")


def _key_part(value: str) -> str:
    normalized = _SAFE_KEY_PART.sub("-", value.strip().lower()).strip("-")
    return normalized or "unknown"


def _redis_required() -> bool:
    settings = get_app_settings()
    return bool(
        settings.redis_url and settings.environment.lower() in {"production", "prod"}
    )


def _slot_key(namespace: str, resource: str) -> str:
    settings = get_app_settings()
    prefix = _key_part(
        getattr(settings, "redis_key_prefix", None)
        or getattr(settings, "environment", None)
        or "development"
    )
    return f"mayabu:{prefix}:slots:{_key_part(namespace)}:{_key_part(resource)}"



async def _redis_call(function: Any, *args: Any) -> Any:
    """Run synchronous redis-py operations without blocking the event loop."""

    return await asyncio.to_thread(function, *args)


async def _renew_lease(
    client: Any,
    cache: Cache,
    key: str,
    token: str,
    policy: SlotPolicy,
    stop: asyncio.Event,
    lost: asyncio.Event,
    owner: asyncio.Task[Any] | None,
) -> None:
    interval = max(1.0, min(policy.ttl_seconds / 3.0, 15.0))
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
            return
        except asyncio.TimeoutError:
            now = time.time()
            try:
                renewed = bool(
                    await _redis_call(
                        client.eval,
                        _RENEW_SCRIPT,
                        1,
                        key,
                        token,
                        now + policy.ttl_seconds,
                        now,
                    )
                )
            except Exception as exc:
                cache.note_failure(exc)
                logger.warning(
                    "distributed_slot_renewal_failed",
                    extra={
                        "event": "distributed_slot",
                        "slot_key": key,
                        "error": str(exc)[:300],
                    },
                )
                renewed = False

            if renewed:
                continue

            lost.set()
            logger.warning(
                "distributed_slot_lease_lost",
                extra={"event": "distributed_slot", "slot_key": key},
            )
            if owner and not owner.done():
                owner.cancel()
            return


async def _acquire(
    client: Any, cache: Cache, key: str, token: str, policy: SlotPolicy
) -> bool:
    deadline = time.monotonic() + policy.wait_seconds
    delay = 0.05
    while True:
        now = time.time()
        try:
            acquired = bool(
                await _redis_call(
                    client.eval,
                    _ACQUIRE_SCRIPT,
                    1,
                    key,
                    now,
                    now + policy.ttl_seconds,
                    policy.limit,
                    token,
                )
            )
        except Exception as exc:
            cache.note_failure(exc)
            if _redis_required():
                raise DistributedCapacityError(
                    "distributed scraper gate became unavailable"
                ) from exc
            return False

        if acquired:
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        await asyncio.sleep(min(remaining, delay + random.uniform(0, delay * 0.2)))
        delay = min(delay * 1.7, 0.5)


@asynccontextmanager
async def distributed_slot(
    namespace: str,
    resource: str,
    limit: int,
    *,
    ttl_seconds: int,
    wait_seconds: float,
    cache: Cache | None = None,
) -> AsyncIterator[None]:
    """Hold one renewable cross-process slot for the context lifetime.

    Development may continue with the caller's process-local semaphore when
    Redis is intentionally absent. Production never runs an uncoordinated
    scraper operation when Redis is configured but unavailable.
    """

    cache = cache or get_cache()
    client = cache.coordination_client()
    if client is None:
        if _redis_required():
            raise DistributedCapacityError("distributed scraper gate unavailable")
        yield
        return

    policy = SlotPolicy.normalized(limit, ttl_seconds, wait_seconds)
    key = _slot_key(namespace, resource)
    token = uuid.uuid4().hex
    acquired = await _acquire(client, cache, key, token, policy)
    if not acquired:
        if _redis_required() or client is not None:
            raise DistributedCapacityError(
                f"distributed capacity unavailable for {resource}"
            )
        yield
        return

    stop = asyncio.Event()
    lost = asyncio.Event()
    owner = asyncio.current_task()
    renewal = asyncio.create_task(
        _renew_lease(client, cache, key, token, policy, stop, lost, owner),
        name=f"renew-slot:{_key_part(resource)}",
    )
    try:
        yield
        if lost.is_set():
            raise DistributedCapacityError(
                f"distributed capacity lease lost for {resource}"
            )
    except asyncio.CancelledError as exc:
        if lost.is_set():
            raise DistributedCapacityError(
                f"distributed capacity lease lost for {resource}"
            ) from exc
        raise
    finally:
        stop.set()
        renewal.cancel()
        with suppress(asyncio.CancelledError):
            await renewal
        try:
            await _redis_call(client.zrem, key, token)
        except Exception as exc:
            cache.note_failure(exc)
            logger.warning(
                "distributed_slot_release_failed",
                extra={
                    "event": "distributed_slot",
                    "slot_key": key,
                    "error": str(exc)[:300],
                },
            )
