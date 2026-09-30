"""Vijay Sales discovery scraper — one platform implementation.

Prefer public /c/{category} listing pages when the query maps to a known
category (far denser and more relevant than /search?q=). Fall back to
/search?q= for free-text queries. Path /search/{query} redirects to brand
pages and must not be used.
"""

from __future__ import annotations

import argparse
import asyncio
import urllib.parse
from typing import Any

from mayabu.scrapers.retail_discovery import scrape_retail_discovery
from mayabu.scrapers.vijaysales_parse import (
    parse_vijaysales_embedded,
    resolve_vijaysales_listing_path,
)

PLATFORM = "vijaysales"


def build_search_url(query: str, page: int = 1) -> str:
    path = resolve_vijaysales_listing_path(query)
    if path:
        base = f"https://www.vijaysales.com{path}"
        if page > 1:
            return f"{base}?page={page}"
        return base
    encoded = urllib.parse.quote_plus(query.strip())
    base = f"https://www.vijaysales.com/search?q={encoded}"
    if page > 1:
        return f"{base}&page={page}"
    return base


async def scrape_vijaysales(
    query: str,
    max_products: int | None = None,
    max_pages: int | None = 3,
    output: str | None = None,
    headless: bool = True,
    debug: bool = False,
) -> list[dict[str, Any]]:
    from mayabu.domain.categories.registry import detect_category_result

    path = resolve_vijaysales_listing_path(query)
    path_to_cat = {
        "/c/laptops": "laptop",
        "/c/mobiles": "smartphone",
        "/c/televisions": "television",
        "/c/refrigerators": "refrigerator",
        "/c/washing-machines": "washing_machine",
        "/c/headphones": "headphones",
        "/c/earphones": "headphones",
        "/c/neckbands": "headphones",
        "/c/camera": "camera",
    }
    expected = path_to_cat.get(path or "")
    # Pull extra cards when PLP filtering is required (featured cross-sell pollution).
    fetch_cap = max_products
    if expected in {"headphones", "tws"} and max_products:
        fetch_cap = max(max_products * 4, 24)

    records = await scrape_retail_discovery(
        PLATFORM,
        query,
        max_products=fetch_cap,
        max_pages=max_pages,
        output=None,
        headless=headless,
        debug=debug,
        link_substring="/p/",
        build_url=build_search_url,
        parse_embedded=lambda html: parse_vijaysales_embedded(html),
        card_selectors=[
            "[class*='product-card']",
            "[class*='ProductCard']",
            "li.product-item",
            "[data-testid*='product']",
            "div[class*='product']",
            "a[href*='/p/']",
        ],
    )
    # Drop cross-category recommendation cards on audio PLPs (phones featured on
    # /c/headphones). Category evidence comes from listing classification, not
    # naive title keyword bans.
    if expected in {"headphones", "tws"}:
        filtered: list[dict[str, Any]] = []
        for row in records:
            cat = row.get("category")
            if not cat or cat in {"unknown", "accessory"}:
                det = detect_category_result(
                    title=row.get("title") or "", url=row.get("link") or ""
                )
                cat = det.category
            if cat in {"headphones", "tws", "audio"}:
                filtered.append(row)
        records = filtered
    if max_products:
        records = records[:max_products]
    if output:
        from mayabu_common import utc_now
        from mayabu_scraper_base import ScrapeConfig, save_or_print

        await save_or_print(
            ScrapeConfig(
                query=query,
                max_products=max_products,
                max_pages=max_pages,
                output=output,
                headless=headless,
                debug=debug,
            ),
            PLATFORM,
            records,
            utc_now(),
        )
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Mayabu Vijay Sales scraper")
    parser.add_argument("query")
    parser.add_argument("--max-products", type=int)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--output")
    parser.add_argument("--show-browser", action="store_true")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    asyncio.run(
        scrape_vijaysales(
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
