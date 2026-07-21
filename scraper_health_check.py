"""Run Mayabu scraper health checks without touching production data.

Discovery health checks run platform search scrapers and measure extraction
quality. Refresh health checks run one known product URL and validate only price
fields. Results are printed as JSON so they can be used by CI, cron or an admin
workflow.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from mayabu.scrapers.capacity import scraper_capacity
from mayabu_common import canonical_platform
from mayabu_db.scraper_runner import run_discovery_scraper
from mayabu_refresh.common import refresh_health_report
from mayabu_refresh.runner import run_refresh_scraper
from mayabu_scraper_base import discovery_health_report

DEFAULT_DISCOVERY_URL_QUERIES = {
    "amazon": "laptop",
    "flipkart": "laptop",
    "croma": "laptop",
    "reliancedigital": "laptop",
}


async def check_discovery(
    platform: str,
    query: str,
    *,
    max_products: int,
    max_pages: int,
    headless: bool,
    debug: bool,
) -> dict[str, Any]:
    async with scraper_capacity.acquire(platform):
        records = await run_discovery_scraper(
            platform,
            query,
            max_pages=max_pages,
            max_products=max_products,
            output=None,
            headless=headless,
            debug=debug,
        )
    report = discovery_health_report(records, min_products=min(10, max_products))
    return {
        "platform": canonical_platform(platform),
        "scraper_type": "discovery",
        "query": query,
        **report,
    }


async def check_refresh(
    platform: str, url: str, *, headless: bool, debug: bool
) -> dict[str, Any]:
    async with scraper_capacity.acquire(platform):
        result = await run_refresh_scraper(
            platform, url, headless=headless, debug=debug
        )
    report = refresh_health_report(result)
    return {
        "platform": canonical_platform(platform),
        "scraper_type": "refresh",
        "url": url,
        **report,
    }


async def main_async(args: argparse.Namespace) -> dict[str, Any]:
    platform = canonical_platform(args.platform)
    if args.type == "discovery":
        query = args.query or DEFAULT_DISCOVERY_URL_QUERIES.get(platform, "laptop")
        return await check_discovery(
            platform,
            query,
            max_products=args.max_products,
            max_pages=args.max_pages,
            headless=not args.headed,
            debug=args.debug,
        )
    if not args.url:
        raise SystemExit("--url is required for refresh health checks")
    return await check_refresh(
        platform, args.url, headless=not args.headed, debug=args.debug
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Mayabu scraper health check")
    parser.add_argument(
        "--platform",
        required=True,
        choices=["amazon", "flipkart", "croma", "reliancedigital"],
    )
    parser.add_argument("--type", required=True, choices=["discovery", "refresh"])
    parser.add_argument("--query", help="Discovery query. Defaults to laptop.")
    parser.add_argument("--url", help="Refresh product URL.")
    parser.add_argument("--max-products", type=int, default=20)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    result = asyncio.run(main_async(args))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
