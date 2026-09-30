"""Poorvika discovery scraper — one platform implementation.

Public /search?q=... currently redirects to homepage. Category landing pages
load product groups via public /api/pim-v4/page/groups/group JSON, which we
capture during normal browser page use.
"""

from __future__ import annotations

import argparse
import asyncio
import urllib.parse
from typing import Any

from mayabu.scrapers.poorvika_parse import (
    parse_poorvika_embedded,
    records_from_pim_group_payload,
    resolve_poorvika_listing_path,
)
from mayabu.scrapers.retail_discovery import scrape_retail_discovery
from mayabu.scrapers.retail_parse import html_looks_blocked
from mayabu_common import utc_now
from mayabu_scraper_base import (
    BrowserSession,
    ScrapeConfig,
    close_common_popups,
    finalize_records,
    human_scroll,
    polite_sleep,
    save_or_print,
)

PLATFORM = "poorvika"


def build_search_url(query: str, page: int = 1) -> str:
    # Prefer category landing pages; free-text search currently redirects home.
    path = resolve_poorvika_listing_path(query)
    if path:
        base = f"https://www.poorvika.com{path}"
        if page > 1:
            sep = "&" if "?" in base else "?"
            return f"{base}{sep}page={page}"
        return base
    encoded = urllib.parse.quote_plus(query.strip())
    base = f"https://www.poorvika.com/search?q={encoded}"
    if page > 1:
        return f"{base}&page={page}"
    return base


async def scrape_poorvika(
    query: str,
    max_products: int | None = None,
    max_pages: int | None = 3,
    output: str | None = None,
    headless: bool = True,
    debug: bool = False,
    start_page: int = 1,
) -> list[dict[str, Any]]:
    # Category-mapped queries: capture public PIM group JSON during page load.
    if resolve_poorvika_listing_path(query):
        return await _scrape_poorvika_category(
            query,
            max_products=max_products,
            max_pages=max_pages,
            output=output,
            headless=headless,
            debug=debug,
        )
    return await scrape_retail_discovery(
        PLATFORM,
        query,
        max_products=max_products,
        max_pages=max_pages,
        output=output,
        headless=headless,
        debug=debug,
        link_substring="/p",
        build_url=build_search_url,
        parse_embedded=lambda html: parse_poorvika_embedded(html),
        card_selectors=[
            "[class*='product-card']",
            "[class*='ProductCard']",
            "[data-testid*='product']",
            "div[class*='product']",
            "a[href*='/p']",
        ],
        start_page=start_page,
    )


async def _scrape_poorvika_category(
    query: str,
    *,
    max_products: int | None,
    max_pages: int | None,
    output: str | None,
    headless: bool,
    debug: bool,
) -> list[dict[str, Any]]:
    config = ScrapeConfig(
        query=query,
        max_products=max_products,
        max_pages=max_pages,
        output=output,
        headless=headless,
        debug=debug,
    )
    observed_at = utc_now()
    raw_records: list[dict[str, Any]] = []
    scrape_status = "success"
    seen: set[str] = set()

    async with BrowserSession(headless=headless, timeout_ms=config.timeout_ms) as session:
        page = await session.new_page()
        payloads: list[str] = []

        async def on_response(resp: Any) -> None:
            url = resp.url
            if "/api/pim-v4/page/groups/group" not in url:
                return
            try:
                if resp.status != 200:
                    return
                text = await resp.text()
                if text:
                    payloads.append(text)
            except Exception:
                return

        page.on("response", on_response)
        total_pages = max(1, max_pages or 1)
        for page_no in range(1, total_pages + 1):
            if max_products and len(raw_records) >= max_products:
                break
            url = build_search_url(query, page_no)
            print(f"[{PLATFORM}] page {page_no}: {url}")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=config.timeout_ms)
            except Exception as exc:
                print(f"[{PLATFORM}] navigation failed on page {page_no}: {exc}")
                scrape_status = "failed"
                break
            await close_common_popups(page)
            await human_scroll(page)
            await polite_sleep(config, 0.8)
            html = await page.content()
            if html_looks_blocked(html, await page.title()):
                scrape_status = "blocked"
                break
            for payload in payloads:
                for raw in records_from_pim_group_payload(payload):
                    key = (raw.get("link") or raw.get("title") or "").lower()
                    if not key or key in seen:
                        continue
                    seen.add(key)
                    raw_records.append(raw)
                    if max_products and len(raw_records) >= max_products:
                        break
            # Also parse any JSON-LD / embedded product blobs on the page.
            for raw in parse_poorvika_embedded(html):
                key = (raw.get("link") or raw.get("title") or "").lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                raw_records.append(raw)
            payloads.clear()
            if page_no < total_pages:
                await polite_sleep(config, 0.5)

    records = finalize_records(PLATFORM, query, raw_records, observed_at)
    if max_products:
        records = records[:max_products]
    if scrape_status == "blocked":
        from mayabu.scrapers.retail_discovery import DiscoveryResult

        result = DiscoveryResult(records, scrape_status="blocked")
        result.blocked = True
        await save_or_print(config, PLATFORM, result, observed_at)
        return result
    await save_or_print(config, PLATFORM, records, observed_at)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Mayabu Poorvika scraper")
    parser.add_argument("query")
    parser.add_argument("--max-products", type=int)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--output")
    parser.add_argument("--show-browser", action="store_true")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    asyncio.run(
        scrape_poorvika(
            args.query,
            args.max_products,
            args.max_pages,
            args.output,
            not args.show_browser,
            args.debug,
        )
    )


if __name__ == "__main__":
    main()
