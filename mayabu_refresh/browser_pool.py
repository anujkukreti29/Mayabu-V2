"""Process-local Playwright browser reuse for refresh/verify adapters.

One Chromium browser per worker process; each scrape gets an isolated context.
No cookies/storage persist across tasks. Browser restarts after crashes.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from mayabu_refresh.common import DEFAULT_USER_AGENT

logger = logging.getLogger(__name__)

# Safe defaults: block analytics/ads/media that do not affect price extraction.
_BLOCKED_RESOURCE_TYPES = frozenset({"media", "font", "websocket", "manifest", "other"})
_BLOCKED_URL_SUBSTR = (
    "google-analytics",
    "googletagmanager",
    "doubleclick",
    "facebook.net",
    "hotjar",
    "scorecardresearch",
    "newrelic",
    "nr-data.net",
    "optimizely",
    "segment.io",
    "mixpanel",
    "clarity.ms",
    "adservice",
    "amazon-adsystem",
    "fls-na.amazon",
)


class RefreshBrowserPool:
    """Shared Chromium for refresh adapters within one process."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._headless: bool | None = None
        self._launches = 0
        self._contexts_opened = 0
        self._contexts_closed = 0

    @property
    def stats(self) -> dict[str, int]:
        return {
            "launches": self._launches,
            "contexts_opened": self._contexts_opened,
            "contexts_closed": self._contexts_closed,
            "browser_alive": 1 if self._browser and self._browser.is_connected() else 0,
        }

    async def _ensure_browser(self, *, headless: bool) -> Browser:
        async with self._lock:
            if (
                self._browser is not None
                and self._browser.is_connected()
                and self._headless == headless
            ):
                return self._browser
            await self._close_unlocked()
            self._playwright = await async_playwright().start()
            from mayabu.core.config import get_app_settings

            settings = get_app_settings()
            args: list[str] = []
            if settings.scraper_chromium_no_sandbox:
                args.append("--no-sandbox")
            if settings.scraper_chromium_disable_dev_shm:
                args.append("--disable-dev-shm-usage")
            self._browser = await self._playwright.chromium.launch(
                headless=headless,
                args=args or None,
            )
            self._headless = headless
            self._launches += 1
            logger.info(
                "refresh_browser_launched",
                extra={"event": "browser_pool", "launches": self._launches},
            )
            return self._browser

    async def _close_unlocked(self) -> None:
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                logger.debug("browser_close_failed", exc_info=True)
            self._browser = None
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                logger.debug("playwright_stop_failed", exc_info=True)
            self._playwright = None
        self._headless = None

    async def close(self) -> None:
        async with self._lock:
            await self._close_unlocked()

    @asynccontextmanager
    async def page(
        self,
        *,
        headless: bool = True,
        block_heavy_resources: bool = True,
        default_timeout_ms: int = 14_000,
    ) -> AsyncIterator[Page]:
        browser = await self._ensure_browser(headless=headless)
        context: BrowserContext | None = None
        try:
            context = await browser.new_context(
                user_agent=DEFAULT_USER_AGENT,
                viewport={"width": 1366, "height": 768},
                locale="en-IN",
                timezone_id="Asia/Kolkata",
                extra_http_headers={"Accept-Language": "en-IN,en;q=0.9"},
            )
            self._contexts_opened += 1
            if block_heavy_resources and _resource_blocking_enabled():
                await context.route("**/*", _route_filter)
            page = await context.new_page()
            page.set_default_timeout(default_timeout_ms)
            yield page
        except Exception:
            # Restart browser on next call if launch/context failed.
            async with self._lock:
                await self._close_unlocked()
            raise
        finally:
            if context is not None:
                try:
                    await context.close()
                except Exception:
                    logger.debug("context_close_failed", exc_info=True)
                self._contexts_closed += 1


_POOL: RefreshBrowserPool | None = None


def get_refresh_browser_pool() -> RefreshBrowserPool:
    global _POOL
    if _POOL is None:
        _POOL = RefreshBrowserPool()
    return _POOL


async def close_refresh_browser_pool() -> None:
    global _POOL
    if _POOL is not None:
        await _POOL.close()
        _POOL = None


def _resource_blocking_enabled() -> bool:
    raw = (os.getenv("MAYABU_REFRESH_BLOCK_HEAVY_RESOURCES") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


async def _route_filter(route: Any) -> None:
    request = route.request
    rtype = (request.resource_type or "").lower()
    url = (request.url or "").lower()
    if rtype in _BLOCKED_RESOURCE_TYPES:
        await route.abort()
        return
    if any(token in url for token in _BLOCKED_URL_SUBSTR):
        await route.abort()
        return
    await route.continue_()


async def wait_for_price_or_stock(
    page: Page,
    *,
    price_selectors: list[str],
    stock_selectors: list[str] | None = None,
    timeout_ms: int = 8_000,
) -> None:
    """Stop waiting once a price or stock signal is determinable."""
    selectors = list(price_selectors)
    if stock_selectors:
        selectors.extend(stock_selectors)
    if not selectors:
        await page.wait_for_timeout(400)
        return
    # Playwright accepts comma-joined CSS for any-of wait.
    joined = ", ".join(selectors)
    try:
        await page.wait_for_selector(joined, timeout=timeout_ms, state="attached")
    except Exception:
        # Fall through — caller still attempts extraction / challenge detection.
        pass


__all__ = [
    "RefreshBrowserPool",
    "close_refresh_browser_pool",
    "get_refresh_browser_pool",
    "wait_for_price_or_stock",
]
