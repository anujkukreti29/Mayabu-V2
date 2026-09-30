"""JioMart discovery scraper — one platform implementation."""

from __future__ import annotations

import argparse
import asyncio
import urllib.parse
from typing import Any

from mayabu.scrapers.jiomart_parse import parse_jiomart_embedded
from mayabu.scrapers.retail_discovery import scrape_retail_discovery

PLATFORM = "jiomart"


# JioMart often uses query-string search in addition to path search.
def build_search_url(query: str, page: int = 1) -> str:
    encoded = urllib.parse.quote(query.strip())
    base = f"https://www.jiomart.com/search/{encoded}"
    if page > 1:
        return f"{base}?page={page}"
    return base


async def scrape_jiomart(
    query: str,
    max_products: int | None = None,
    max_pages: int | None = 3,
    output: str | None = None,
    headless: bool = True,
    debug: bool = False,
) -> list[dict[str, Any]]:
    return await scrape_retail_discovery(
        PLATFORM,
        query,
        max_products=max_products,
        max_pages=max_pages,
        output=output,
        headless=headless,
        debug=debug,
        link_substring="/p/",
        build_url=build_search_url,
        parse_embedded=lambda html: parse_jiomart_embedded(html),
        card_selectors=[
            "[class*='plp-card']",
            "[class*='product-card']",
            "[data-testid*='product']",
            "div[class*='product']",
            "a[href*='/p/']",
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Mayabu JioMart scraper")
    parser.add_argument("query")
    parser.add_argument("--max-products", type=int)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--output")
    parser.add_argument("--show-browser", action="store_true")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    asyncio.run(
        scrape_jiomart(
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
