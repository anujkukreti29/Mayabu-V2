from __future__ import annotations

import argparse
import asyncio
import urllib.parse
from typing import Any

from mayabu_common import utc_now
from mayabu_scraper_base import (
    BrowserSession,
    ScrapeConfig,
    close_common_popups,
    discovery_health_report,
    extract_structural_discovery_records,
    finalize_records,
    human_scroll,
    polite_sleep,
    save_or_print,
)

PLATFORM = "flipkart"


async def scrape_flipkart(
    query: str,
    max_products: int | None = None,
    max_pages: int | None = 3,
    output: str | None = None,
    headless: bool = True,
    debug: bool = False,
) -> list[dict[str, Any]]:
    """Discover Flipkart products without relying on generated CSS classes.

    Discovery output intentionally contains only MVP product fields after
    finalization: title, current price, MRP, discount, image URL and product URL.
    The extractor finds product anchors (/p/ or pid), groups the nearest visible
    product card, then reads visible text/images from that card.
    """
    config = ScrapeConfig(query=query, max_products=max_products, max_pages=max_pages, output=output, headless=headless, debug=debug)
    observed_at = utc_now()
    raw_records: list[dict[str, Any]] = []

    async with BrowserSession(headless=headless, timeout_ms=config.timeout_ms) as session:
        page = await session.new_page()
        encoded = urllib.parse.quote_plus(query)
        total_pages = max_pages or 1
        for page_no in range(1, total_pages + 1):
            if max_products and len(raw_records) >= max_products:
                break
            url = f"https://www.flipkart.com/search?q={encoded}&marketplace=FLIPKART&page={page_no}"
            print(f"[flipkart] page {page_no}: {url}")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=config.timeout_ms)
                await page.wait_for_timeout(1800)
            except Exception as exc:
                print(f"[flipkart] navigation failed on page {page_no}: {exc}")
                break
            await close_common_popups(page)
            await human_scroll(page, steps=6)
            page_records = await extract_structural_discovery_records(
                page,
                PLATFORM,
                query,
                max_items=(max_products or 120),
            )
            if max_products:
                remaining = max_products - len(raw_records)
                page_records = page_records[:max(0, remaining)]
            raw_records.extend(page_records)
            print(f"[flipkart] page {page_no}: +{len(page_records)} structural cards")
            if not page_records:
                # Do not chase generated classes here. Capture state when debug is on.
                if debug:
                    from mayabu_scraper_base import capture_debug_artifacts
                    artifacts = await capture_debug_artifacts(page, PLATFORM, query, f"zero_structural_page_{page_no}")
                    print(f"[flipkart] debug artifacts: {artifacts}")
                break
            await polite_sleep(config)

    records = finalize_records(PLATFORM, query, raw_records, observed_at)
    health = discovery_health_report(records, min_products=min(10, max_products or 10))
    if debug:
        print(f"[flipkart] health: {health}")
    return await save_or_print(config, PLATFORM, records, observed_at)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mayabu Flipkart discovery scraper")
    parser.add_argument("query")
    parser.add_argument("--max-products", type=int)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--output")
    parser.add_argument("--show-browser", action="store_true")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    asyncio.run(scrape_flipkart(args.query, args.max_products, args.max_pages, args.output, not args.show_browser, args.debug))


if __name__ == "__main__":
    main()
