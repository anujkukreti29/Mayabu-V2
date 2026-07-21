"""Run one product-detail refresh scraper directly.

Refresh output is price-only by design:
  current_price, mrp, discount_percent

Examples:
  python run_refresh_price.py --platform flipkart --url "https://www.flipkart.com/..." --debug
  python run_refresh_price.py --platform croma --url "https://www.croma.com/..." --headed --debug
"""

from __future__ import annotations

import argparse
import asyncio
import json

from mayabu.scrapers.capacity import scraper_capacity
from mayabu_refresh.runner import run_refresh_scraper


async def _run(platform: str, url: str, *, headless: bool, debug: bool):
    async with scraper_capacity.acquire(platform):
        return await run_refresh_scraper(platform, url, headless=headless, debug=debug)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one Mayabu refresh-price scraper")
    parser.add_argument(
        "--platform",
        required=True,
        choices=["amazon", "flipkart", "croma", "reliancedigital"],
    )
    parser.add_argument("--url", required=True)
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser visibly. Useful for Croma debugging.",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Save debug screenshot/HTML."
    )
    parser.add_argument("--output")
    args = parser.parse_args()

    result = asyncio.run(
        _run(
            args.platform,
            args.url,
            headless=not args.headed,
            debug=args.debug,
        )
    )
    data = result.as_dict()
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    else:
        print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
