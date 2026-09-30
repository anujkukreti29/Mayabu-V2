from __future__ import annotations

import inspect
from typing import Any, Awaitable, Callable

from amazon_scraper import scrape_amazon
from bajajelectronics_scraper import scrape_bajajelectronics
from croma_scraper import scrape_croma
from flipkart_scraper import scrape_flipkart
from jiomart_scraper import scrape_jiomart
from poorvika_scraper import scrape_poorvika
from reliancedigital_scraper import scrape_reliancedigital
from vijaysales_scraper import scrape_vijaysales
from mayabu_common import canonical_platform

DiscoveryFn = Callable[..., Awaitable[list[dict[str, Any]]]]

_DISCOVERY: dict[str, DiscoveryFn] = {
    "amazon": scrape_amazon,
    "flipkart": scrape_flipkart,
    "croma": scrape_croma,
    "reliancedigital": scrape_reliancedigital,
    "vijaysales": scrape_vijaysales,
    "jiomart": scrape_jiomart,
    "poorvika": scrape_poorvika,
    "bajajelectronics": scrape_bajajelectronics,
}


async def run_discovery_scraper(
    platform: str,
    query: str,
    max_pages: int | None,
    max_products: int | None,
    output: str | None = None,
    headless: bool = True,
    debug: bool = False,
    start_page: int = 1,
) -> list[dict[str, Any]]:
    platform = canonical_platform(platform)
    scraper = _DISCOVERY.get(platform)
    if scraper is None:
        raise ValueError(f"Unsupported platform: {platform}")
    kwargs: dict[str, Any] = {
        "max_products": max_products,
        "max_pages": max_pages,
        "output": output,
        "headless": headless,
        "debug": debug,
    }
    try:
        if "start_page" in inspect.signature(scraper).parameters:
            kwargs["start_page"] = max(1, int(start_page or 1))
    except (TypeError, ValueError):
        pass
    return await scraper(query, **kwargs)


# Re-export refresh runner for DB worker integration.
from mayabu_refresh.runner import run_refresh_scraper  # noqa: E402,F401
