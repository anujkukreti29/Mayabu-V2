"""Run Mayabu scraper health checks without touching production data."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from typing import Any

from mayabu.platforms.registry import SUPPORTED_PLATFORMS
from mayabu.scheduler.platform_health_policy import record_health_observation
from mayabu.scrapers.capacity import scraper_capacity
from mayabu.scrapers.retail_discovery import DiscoveryResult
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
    "vijaysales": "laptop",
    "jiomart": "smartphone",
    "poorvika": "laptop",
    "bajajelectronics": "television",
}


async def check_discovery(
    platform: str,
    query: str,
    *,
    max_products: int,
    max_pages: int,
    headless: bool,
    debug: bool,
    persist_health: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
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
    scrape_status = getattr(records, "scrape_status", None)
    if isinstance(records, DiscoveryResult) and records.health:
        report = dict(records.health)
    else:
        report = discovery_health_report(
            list(records),
            min_products=min(10, max_products),
            scrape_status=scrape_status,
        )
    categories: dict[str, int] = {}
    accepted = rejected = degraded = 0
    valid_price = valid_image = unknown_cat = confident = 0
    try:
        from mayabu_db.quality import evaluate_listing
        from mayabu_common import normalize_raw_listing
        from mayabu.monitoring.platform_category_health import score_platform_category_health

        for row in records:
            listing = normalize_raw_listing(row, platform_hint=platform, query=query)
            if not listing:
                rejected += 1
                continue
            cat = str(listing.get("category") or "unknown").lower()
            categories[cat] = categories.get(cat, 0) + 1
            decision = evaluate_listing(listing).decision
            if decision == "accepted":
                accepted += 1
            elif decision == "degraded":
                degraded += 1
            else:
                rejected += 1
            if decision != "rejected" and listing.get("price") is not None:
                valid_price += 1
            image = str(listing.get("image") or "")
            if image and "logo" not in image.lower() and "placeholder" not in image.lower():
                valid_image += 1
            if cat == "unknown":
                unknown_cat += 1
            if str(listing.get("category_confidence") or "") in {"high", "medium"}:
                confident += 1
    except Exception:
        for row in records:
            cat = str((row.get("category") or "unknown")).lower()
            categories[cat] = categories.get(cat, 0) + 1

    latency_ms = int((time.perf_counter() - started) * 1000)
    discovered = accepted + degraded + rejected
    if not discovered:
        try:
            discovered = len(records)
        except TypeError:
            discovered = 0
    denom = max(discovered, 1)
    # Dominant detected category for platform×category health (bounded).
    dominant_category = max(categories, key=categories.get) if categories else "unknown"
    platform_category_health = None
    try:
        from mayabu.monitoring.platform_category_health import score_platform_category_health

        platform_category_health = score_platform_category_health(
            platform=canonical_platform(platform),
            category=dominant_category if dominant_category != "unknown" else "laptop",
            discovered=discovered,
            accepted=accepted,
            degraded=degraded,
            rejected=rejected,
            valid_price_rate=valid_price / denom,
            valid_image_rate=valid_image / denom,
            unknown_category_rate=unknown_cat / denom,
            category_confidence_rate=confident / denom,
            scrape_status=str(report.get("status") or scrape_status or ""),
        ).as_dict()
    except Exception:
        platform_category_health = None

    payload = {
        "platform": canonical_platform(platform),
        "scraper_type": "discovery",
        "query": query,
        "category_detection": categories,
        "accepted_records": accepted,
        "degraded_records": degraded,
        "rejected_records": rejected,
        "latency_ms": latency_ms,
        "blocked": report.get("status") == "blocked",
        "platform_category_health": platform_category_health,
        **report,
    }
    if persist_health:
        try:
            record_health_observation(
                platform,
                str(report.get("status") or "failed"),
                reason=",".join(report.get("reasons") or []) or None,
            )
        except Exception as exc:
            payload["health_persist_error"] = str(exc)[:200]
    return payload


async def check_refresh(
    platform: str, url: str, *, headless: bool, debug: bool
) -> dict[str, Any]:
    async with scraper_capacity.acquire(platform):
        result = await run_refresh_scraper(
            platform, url, headless=headless, debug=debug
        )
    report = refresh_health_report(result)
    status = getattr(result, "page_status", None) or report.get("status")
    return {
        "platform": canonical_platform(platform),
        "scraper_type": "refresh",
        "url": url,
        "blocked": status == "blocked",
        "page_status": status,
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
            persist_health=args.persist_health,
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
        choices=sorted(SUPPORTED_PLATFORMS),
    )
    parser.add_argument("--type", required=True, choices=["discovery", "refresh"])
    parser.add_argument("--query")
    parser.add_argument("--url")
    parser.add_argument("--max-products", type=int, default=20)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--persist-health",
        action="store_true",
        help="Write observed status into platform_health (does not change enabled config)",
    )
    args = parser.parse_args()
    result = asyncio.run(main_async(args))
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
