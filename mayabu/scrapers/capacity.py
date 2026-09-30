"""Shared local and distributed limits for every scraper entry point."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from mayabu.core.config import AppSettings, get_app_settings
from mayabu.platforms.registry import all_platforms
from mayabu.verification.platform_gate import distributed_platform_slot
from mayabu_common import canonical_platform

# Conservative retailer limits remain explicit and easy to review.
# New platforms start at 1 concurrent discovery/refresh slot.
_PLATFORM_CAPS: dict[str, int] = {p.slug: p.discovery_cap for p in all_platforms(enabled_only=False)}
_DEFAULT_PLATFORM_CAP = 1


def platform_limit(platform: str, configured: int | None = None) -> int:
    """Return the effective per-platform ceiling for one deployment."""

    normalized = canonical_platform(platform)
    requested = max(1, configured or get_app_settings().platform_concurrency)
    return min(requested, _PLATFORM_CAPS.get(normalized, _DEFAULT_PLATFORM_CAP))


def platform_slot_ttl(settings: AppSettings | None = None) -> int:
    settings = settings or get_app_settings()
    navigation_budget = (
        settings.scraper_timeout_ms * settings.scraper_navigation_attempts
    ) // 1000
    return max(settings.scraper_distributed_slot_ttl_seconds, navigation_budget + 30)


class ScraperCapacity:
    """Own process-local semaphores and the shared Redis budget."""

    def __init__(self) -> None:
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    def reset(self) -> None:
        self._semaphores.clear()

    def _semaphore(self, platform: str) -> asyncio.Semaphore:
        normalized = canonical_platform(platform)
        semaphore = self._semaphores.get(normalized)
        if semaphore is None:
            semaphore = asyncio.Semaphore(platform_limit(normalized))
            self._semaphores[normalized] = semaphore
        return semaphore

    @asynccontextmanager
    async def acquire(self, platform: str) -> AsyncIterator[None]:
        settings = get_app_settings()
        normalized = canonical_platform(platform)
        async with self._semaphore(normalized):
            async with distributed_platform_slot(
                normalized,
                platform_limit(normalized, settings.platform_concurrency),
                ttl_seconds=platform_slot_ttl(settings),
                wait_seconds=settings.scraper_distributed_slot_wait_seconds,
            ):
                yield


scraper_capacity = ScraperCapacity()
