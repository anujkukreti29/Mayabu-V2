"""CLI for ingesting or queueing one exact platform product URL."""

from __future__ import annotations

import argparse
import asyncio
import json

from mayabu.jobs.queue import enqueue_direct_ingest
from mayabu.scrapers.platforms import detect_platform
from mayabu.services.direct_ingestion import ingest_product_url


def _print(value) -> None:
    print(json.dumps(value, indent=2, default=str))


async def _run_now(args: argparse.Namespace, platform: str) -> None:
    result = await ingest_product_url(
        args.url,
        platform=platform,
        headless=not args.show_browser,
        debug=not args.no_debug,
    )
    _print(result)
    if not result.get("ok"):
        raise SystemExit(2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest an exact Amazon/Flipkart/Croma/Reliance product URL")
    parser.add_argument("--url", required=True)
    parser.add_argument("--platform", choices=["amazon", "flipkart", "croma", "reliancedigital"])
    parser.add_argument("--enqueue", action="store_true", help="Queue the URL for a background worker instead of scraping now")
    parser.add_argument("--force", action="store_true", help="Allow another active task for the same URL")
    parser.add_argument("--show-browser", action="store_true")
    parser.add_argument("--no-debug", action="store_true")
    args = parser.parse_args()

    platform = args.platform or detect_platform(args.url)
    if args.enqueue:
        _print(enqueue_direct_ingest(args.url, platform, force=args.force))
        return
    asyncio.run(_run_now(args, platform))


if __name__ == "__main__":
    main()
