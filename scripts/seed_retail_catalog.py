"""Bounded retail catalog seed for local/staging PostgreSQL.

Uses existing discovery + ingestion paths. Never bypasses quality gates.
Never intended for production databases.

Examples:
  python scripts/seed_retail_catalog.py --dry-run
  python scripts/seed_retail_catalog.py --categories smartphone television --max-products 12
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlparse

from mayabu.platforms.coverage import PRODUCTION_PLATFORMS, get_coverage, ingestion_enabled
from mayabu.scrapers.capacity import scraper_capacity
from mayabu.search.index_manager import refresh_product_search_documents
from mayabu.search.search_repository import reset_search_source_cache
from mayabu.services.variant_groups import refresh_variant_groups
from mayabu_db.connection import db_connection
from mayabu_db.ingestion import ingest_records
from mayabu_db.scraper_runner import run_discovery_scraper
from mayabu_db.tasks import finish_run, start_run

# Category → seed queries (representative, not product logic).
SEED_QUERIES: dict[str, tuple[str, ...]] = {
    "laptop": (
        "gaming laptop",
        "student laptop",
        "asus laptop",
        "hp laptop",
        "lenovo laptop",
        "macbook",
    ),
    "smartphone": (
        "samsung galaxy",
        "iphone",
        "oneplus smartphone",
        "vivo smartphone",
        "nothing phone",
    ),
    "television": (
        "samsung 55 inch tv",
        "lg oled tv",
        "sony bravia",
        "55 inch tv",
    ),
    "refrigerator": (
        "lg refrigerator",
        "samsung double door refrigerator",
        "whirlpool refrigerator",
    ),
    "washing_machine": (
        "lg 8kg front load",
        "samsung top load washing machine",
        "front load washing machine",
    ),
    "tws": (
        "samsung galaxy buds",
        "oneplus buds",
        "boat tws",
        "sony tws",
    ),
    "headphones": (
        "sony headphones",
        "jbl headphones",
        "bose headphones",
    ),
}

# Trusted platform × category pairs for staging catalog (not experimental).
DEFAULT_TARGETS: list[tuple[str, str]] = [
    ("amazon", "laptop"),
    ("flipkart", "laptop"),
    ("croma", "laptop"),
    ("reliancedigital", "laptop"),
    ("flipkart", "smartphone"),
    ("croma", "smartphone"),
    ("reliancedigital", "smartphone"),
    ("amazon", "smartphone"),
    ("amazon", "television"),
    ("croma", "television"),
    ("reliancedigital", "television"),
    ("croma", "refrigerator"),
    ("reliancedigital", "refrigerator"),
    ("croma", "washing_machine"),
    ("reliancedigital", "washing_machine"),
    ("amazon", "tws"),
    ("croma", "tws"),
    ("croma", "headphones"),
]


@dataclass
class BatchSummary:
    platform: str
    category: str
    query: str
    discovered: int = 0
    valid: int = 0
    invalid: int = 0
    products_created: int = 0
    products_matched: int = 0
    listings_created: int = 0
    listings_updated: int = 0
    errors: list[str] = field(default_factory=list)
    status: str = "pending"
    latency_ms: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _assert_safe_database(url: str) -> None:
    name = urlparse(url).path.lstrip("/").lower()
    if not name:
        raise SystemExit("DATABASE_URL has no database name")
    blocked = {"mayabu_prod", "production", "prod"}
    if name in blocked or name.endswith("_prod"):
        raise SystemExit(f"Refusing to seed database named '{name}'")
    # Prefer test/staging; allow mayabu only with explicit --allow-dev-db
    return


def planned_jobs(
    *,
    categories: list[str] | None,
    platforms: list[str] | None,
    queries_per_category: int,
) -> list[tuple[str, str, str]]:
    cats = set(categories) if categories else None
    plats = set(platforms) if platforms else None
    jobs: list[tuple[str, str, str]] = []
    for platform, category in DEFAULT_TARGETS:
        if cats and category not in cats:
            continue
        if plats and platform not in plats:
            continue
        if platform not in PRODUCTION_PLATFORMS:
            continue
        cell = get_coverage(platform, category)
        if cell.status in {"disabled", "blocked", "unavailable"}:
            continue
        if not ingestion_enabled(platform, category) and cell.status == "partial":
            # Allow partial for staging population.
            pass
        elif not ingestion_enabled(platform, category) and cell.status not in {"supported", "partial"}:
            continue
        qlist = list(SEED_QUERIES.get(category, ()))[: max(1, queries_per_category)]
        for query in qlist:
            jobs.append((platform, category, query))
    return jobs


async def run_one(
    platform: str,
    category: str,
    query: str,
    *,
    max_pages: int,
    max_products: int,
    headless: bool,
) -> BatchSummary:
    summary = BatchSummary(platform=platform, category=category, query=query)
    started = time.perf_counter()
    try:
        pseudo_task = {
            "id": None,
            "platform": platform,
            "task_type": "discovery",
            "query": query,
            "url": None,
            "metadata": {"source": "seed_retail_catalog", "category": category},
        }
        with db_connection() as conn:
            run_id = start_run(conn, pseudo_task)
        async with scraper_capacity.acquire(platform):
            records = await run_discovery_scraper(
                platform,
                query,
                max_pages=max_pages,
                max_products=max_products,
                output=None,
                headless=headless,
                debug=False,
            )
        summary.discovered = len(records)
        with db_connection() as conn:
            stats = ingest_records(conn, records, platform, query, run_id=run_id)
            summary.valid = stats.valid
            summary.invalid = stats.invalid
            summary.products_created = stats.products_created
            summary.products_matched = stats.products_matched
            summary.listings_created = stats.listings_created
            summary.listings_updated = stats.listings_updated
            summary.errors = list(stats.errors[:5])
            status = "empty" if not records else ("completed" if stats.valid else "partial")
            finish_run(conn, run_id, status, stats.as_dict(), error=None)
            summary.status = status
            affected = list(stats.affected_product_ids)
        if affected:
            refresh_variant_groups(affected)
            refresh_product_search_documents(affected, strict=False)
    except Exception as exc:
        summary.status = "failed"
        summary.errors.append(str(exc)[:300])
    summary.latency_ms = int((time.perf_counter() - started) * 1000)
    return summary


def catalog_report() -> dict[str, Any]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select category, count(*)::int as products
                from product_clusters
                where status = 'active' and category not in ('unknown','accessory')
                group by category order by category
                """
            )
            products = {r["category"]: r["products"] for r in cur.fetchall()}
            cur.execute(
                """
                select p.category, count(l.id)::int as offers,
                       count(distinct l.product_id)::int as products_with_offers
                from platform_listings l
                join product_clusters p on p.id = l.product_id
                where l.match_status = 'matched'
                group by p.category order by p.category
                """
            )
            offers = {r["category"]: r for r in cur.fetchall()}
            cur.execute(
                """
                select category, count(*)::int as docs
                from product_search_documents
                where category not in ('unknown','accessory')
                group by category order by category
                """
            )
            docs = {r["category"]: r["docs"] for r in cur.fetchall()}
            cur.execute(
                """
                select
                  count(*) filter (where platform_count = 1)::int as one_offer,
                  count(*) filter (where platform_count >= 2)::int as multi_offer,
                  count(*) filter (where best_price is not null)::int as with_price
                from product_search_documents
                where category not in ('unknown','accessory')
                """
            )
            price_cov = cur.fetchone() or {}
    return {
        "products_by_category": products,
        "offers_by_category": {
            k: {"offers": v["offers"], "products_with_offers": v["products_with_offers"]}
            for k, v in offers.items()
        },
        "search_docs_by_category": docs,
        "one_offer_docs": price_cov.get("one_offer"),
        "multi_offer_docs": price_cov.get("multi_offer"),
        "docs_with_price": price_cov.get("with_price"),
    }


async def main_async(args: argparse.Namespace) -> int:
    db_url = os.getenv("DATABASE_URL") or ""
    if not db_url:
        raise SystemExit("DATABASE_URL is required")
    _assert_safe_database(db_url)
    if "test" not in urlparse(db_url).path.lower() and "staging" not in urlparse(db_url).path.lower():
        if not args.allow_dev_db:
            raise SystemExit(
                "Refuse to seed non-test/staging DB. Use mayabu_test or pass --allow-dev-db for local mayabu only."
            )

    jobs = planned_jobs(
        categories=args.categories,
        platforms=args.platforms,
        queries_per_category=args.queries_per_category,
    )
    plan = [
        {
            "platform": p,
            "category": c,
            "query": q,
            "max_pages": args.max_pages,
            "max_products": args.max_products,
        }
        for p, c, q in jobs
    ]
    if args.dry_run:
        print(json.dumps({"dry_run": True, "jobs": plan, "job_count": len(plan)}, indent=2))
        return 0

    reset_search_source_cache()
    summaries: list[BatchSummary] = []
    for platform, category, query in jobs:
        print(f"SEED {platform}/{category}: {query}", flush=True)
        summary = await run_one(
            platform,
            category,
            query,
            max_pages=args.max_pages,
            max_products=args.max_products,
            headless=not args.headed,
        )
        summaries.append(summary)
        print(
            json.dumps(
                {
                    "platform": summary.platform,
                    "category": summary.category,
                    "query": summary.query,
                    "status": summary.status,
                    "discovered": summary.discovered,
                    "valid": summary.valid,
                    "created": summary.products_created,
                    "matched": summary.products_matched,
                    "listings_created": summary.listings_created,
                    "listings_updated": summary.listings_updated,
                    "latency_ms": summary.latency_ms,
                    "errors": summary.errors[:2],
                },
                default=str,
            ),
            flush=True,
        )
        await asyncio.sleep(args.pace_seconds)

    totals: dict[str, Any] = defaultdict(int)
    for s in summaries:
        totals["jobs"] += 1
        totals["discovered"] += s.discovered
        totals["valid"] += s.valid
        totals["invalid"] += s.invalid
        totals["products_created"] += s.products_created
        totals["products_matched"] += s.products_matched
        totals["listings_created"] += s.listings_created
        totals["listings_updated"] += s.listings_updated
        if s.status == "failed":
            totals["failed_jobs"] += 1

    report = catalog_report()
    print(json.dumps({"totals": dict(totals), "catalog": report}, indent=2, default=str))
    return 0 if totals.get("failed_jobs", 0) == 0 or totals.get("valid", 0) > 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded Mayabu retail catalog seed")
    parser.add_argument("--categories", nargs="+")
    parser.add_argument("--platforms", nargs="+")
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--max-products", type=int, default=12)
    parser.add_argument("--queries-per-category", type=int, default=2)
    parser.add_argument("--pace-seconds", type=float, default=1.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument(
        "--allow-dev-db",
        action="store_true",
        help="Allow seeding local mayabu DB that is not named *test*/*staging*",
    )
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    if args.max_products > 40 or args.max_pages > 2:
        raise SystemExit("Refuse unsafe crawl size: max-products<=40, max-pages<=2")
    if args.report_only:
        print(json.dumps(catalog_report(), indent=2, default=str))
        return
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
