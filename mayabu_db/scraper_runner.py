from __future__ import annotations

from typing import Any

from amazon_scraper import scrape_amazon
from croma_scraper import scrape_croma
from flipkart_scraper import scrape_flipkart
from reliancedigital_scraper import scrape_reliancedigital
from mayabu_common import canonical_platform


async def run_discovery_scraper(
    platform: str,
    query: str,
    max_pages: int | None,
    max_products: int | None,
    output: str | None = None,
    headless: bool = True,
    debug: bool = False,
) -> list[dict[str, Any]]:
    platform = canonical_platform(platform)
    if platform == "amazon":
        return await scrape_amazon(query, max_products=max_products, max_pages=max_pages, output=output, headless=headless, debug=debug)
    if platform == "flipkart":
        return await scrape_flipkart(query, max_products=max_products, max_pages=max_pages, output=output, headless=headless, debug=debug)
    if platform == "croma":
        return await scrape_croma(query, max_products=max_products, max_pages=max_pages, output=output, headless=headless, debug=debug)
    if platform == "reliancedigital":
        return await scrape_reliancedigital(query, max_products=max_products, max_pages=max_pages, output=output, headless=headless, debug=debug)
    raise ValueError(f"Unsupported platform: {platform}")


# Re-export refresh runner for DB worker integration.
from mayabu_refresh.runner import run_refresh_scraper  # noqa: E402,F401
