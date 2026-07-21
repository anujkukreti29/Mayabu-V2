"""Compatibility wrapper for the shared scraper platform concurrency gate."""

from __future__ import annotations

from contextlib import asynccontextmanager

from mayabu.core.distributed_limit import DistributedCapacityError, distributed_slot

PlatformCapacityError = DistributedCapacityError


@asynccontextmanager
async def distributed_platform_slot(platform: str, limit: int, *, ttl_seconds: int = 90, wait_seconds: int = 30):
    """Acquire a slot from the same global budget used by every scraper task."""

    async with distributed_slot(
        "scrape-platform",
        platform,
        limit,
        ttl_seconds=ttl_seconds,
        wait_seconds=wait_seconds,
    ):
        yield
