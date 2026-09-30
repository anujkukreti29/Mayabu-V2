"""Live multi-category discovery smoke matrix (tiny limits, production-first).

Does not write to the catalog DB. Prints JSON report for the activation task.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from typing import Any

from mayabu.monitoring.platform_category_health import score_platform_category_health
from mayabu.platforms.coverage import (
    EXPERIMENTAL_PLATFORMS,
    PRODUCTION_PLATFORMS,
    get_coverage,
    smoke_probe_queries,
)
from mayabu.scrapers.capacity import scraper_capacity
from mayabu.scrapers.retail_discovery import DiscoveryResult
from mayabu_common import normalize_raw_listing
from mayabu_db.quality import evaluate_listing
from mayabu_db.scraper_runner import run_discovery_scraper


def _rate(numer: int, denom: int) -> float:
    return float(numer) / float(denom) if denom else 0.0


async def run_probe(
    platform: str,
    category: str,
    query: str,
    *,
    max_products: int,
    headless: bool,
) -> dict[str, Any]:
    started = time.perf_counter()
    scrape_status = "failed"
    records: list[dict[str, Any]] = []
    error: str | None = None
    try:
        async with scraper_capacity.acquire(platform):
            result = await run_discovery_scraper(
                platform,
                query,
                max_pages=1,
                max_products=max_products,
                output=None,
                headless=headless,
                debug=False,
            )
        if isinstance(result, DiscoveryResult):
            records = list(result)
            scrape_status = str(result.scrape_status or getattr(result, "health", {}).get("status") or "ok")
            if result.health and result.health.get("status"):
                scrape_status = str(result.health.get("status"))
        else:
            records = list(result)
            scrape_status = "ok" if records else "empty"
    except Exception as exc:
        error = str(exc)[:300]
        scrape_status = "failed"

    accepted = degraded = rejected = 0
    valid_price = valid_image = unknown_cat = confident = 0
    seen_urls: set[str] = set()
    duplicates = 0
    category_hits = 0

    for raw in records:
        listing = normalize_raw_listing(raw, platform_hint=platform, query=query)
        if not listing:
            rejected += 1
            continue
        decision = evaluate_listing(listing, seen_urls=seen_urls)
        if "duplicate_url" in decision.reasons:
            duplicates += 1
        if decision.decision == "accepted":
            accepted += 1
        elif decision.decision == "degraded":
            degraded += 1
        else:
            rejected += 1
        if decision.price_usable:
            valid_price += 1
        image = str(listing.get("image") or "")
        if image and "placeholder" not in image.lower() and "logo" not in image.lower():
            valid_image += 1
        cat = str(listing.get("category") or "unknown")
        if cat == "unknown":
            unknown_cat += 1
        if cat == category:
            category_hits += 1
        conf = str(listing.get("category_confidence") or "unknown")
        if conf in {"high", "medium"}:
            confident += 1

    discovered = len(records)
    health = score_platform_category_health(
        platform=platform,
        category=category,
        discovered=discovered,
        accepted=accepted,
        degraded=degraded,
        rejected=rejected,
        valid_price_rate=_rate(valid_price, discovered),
        valid_image_rate=_rate(valid_image, discovered),
        unknown_category_rate=_rate(unknown_cat, discovered),
        category_confidence_rate=_rate(confident, discovered),
        duplicate_rate=_rate(duplicates, discovered),
        scrape_status=scrape_status if discovered == 0 else None,
    )

    return {
        "platform": platform,
        "category": category,
        "query": query,
        "coverage": get_coverage(platform, category).status,
        "status": health.status,
        "products_discovered": discovered,
        "accepted": accepted,
        "degraded": degraded,
        "rejected": rejected,
        "valid_price_rate": round(_rate(valid_price, discovered), 3),
        "valid_image_rate": round(_rate(valid_image, discovered), 3),
        "unknown_category_rate": round(_rate(unknown_cat, discovered), 3),
        "target_category_hit_rate": round(_rate(category_hits, discovered), 3),
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "scrape_status": scrape_status,
        "error": error,
        "health": health.as_dict(),
    }


async def main_async(args: argparse.Namespace) -> dict[str, Any]:
    probes = smoke_probe_queries()
    if args.platform:
        probes = [p for p in probes if p[0] == args.platform]
    if args.category:
        probes = [p for p in probes if p[1] == args.category]
    if args.include_experimental:
        for platform in EXPERIMENTAL_PLATFORMS:
            probes.append((platform, "smartphone", "smartphone"))
            probes.append((platform, "laptop", "laptop"))

    results = []
    for platform, category, query in probes:
        # Tiny pacing — do not hammer retailers.
        await asyncio.sleep(0.8)
        results.append(
            await run_probe(
                platform,
                category,
                query,
                max_products=args.max_products,
                headless=not args.headed,
            )
        )

    production = [r for r in results if r["platform"] in PRODUCTION_PLATFORMS]
    ready = [
        f"{r['platform']}/{r['category']}"
        for r in production
        if r["status"] == "healthy" and r["accepted"] >= 3
    ]
    experimental_obs = [r for r in results if r["platform"] in EXPERIMENTAL_PLATFORMS]

    return {
        "probes": results,
        "production_ready_pairs": ready,
        "experimental_observations": experimental_obs,
        "note": "One successful item is not sufficient for readiness; thresholds require >=3 accepted.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Mayabu multi-category live smoke matrix")
    parser.add_argument("--max-products", type=int, default=8)
    parser.add_argument("--platform")
    parser.add_argument("--category")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--include-experimental", action="store_true")
    args = parser.parse_args()
    report = asyncio.run(main_async(args))
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
