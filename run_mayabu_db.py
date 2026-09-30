"""Run scraper(s) and ingest directly into PostgreSQL without JSON catalogue storage.

v4.5.3 hardens this local/ops CLI for production-like use:
- bounded platform concurrency to avoid browser storms and DB pool exhaustion
- safe max-pages/max-products caps with explicit override values
- search-index refresh after successful ingestion so API reads stay fast
"""

from __future__ import annotations

import argparse
import asyncio
import os
import time
from typing import Callable, TypeVar

from mayabu_db.connection import db_connection
from mayabu_db.ingestion import ingest_records
from mayabu_db.repository import auto_merge_duplicate_products
from mayabu_db.scraper_runner import run_discovery_scraper
from mayabu_db.tasks import finish_run, start_run
from mayabu.scrapers.capacity import scraper_capacity
from mayabu.platforms.registry import iter_enabled_slugs
from mayabu.search.index_manager import (
    drain_dirty_search_documents,
    refresh_product_search_documents,
)
from mayabu.services.variant_groups import refresh_variant_groups

T = TypeVar("T")
_DEFAULT_PLATFORMS = list(iter_enabled_slugs())


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _bounded_positive(
    value: int | None, *, default: int, maximum: int, name: str
) -> int:
    if value is None:
        return default
    if value <= 0:
        raise SystemExit(
            f"{name} must be a positive integer. Mayabu does not support unlimited scraping from this CLI."
        )
    if value > maximum:
        raise SystemExit(
            f"{name}={value} is too high for safe production-style scraping. Max allowed here is {maximum}."
        )
    return value


def _with_db_retry(
    action: Callable[[], T], *, attempts: int = 3, label: str = "db"
) -> T:
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return action()
        except Exception as exc:
            last_exc = exc
            if attempt >= attempts:
                break
            wait = min(12, 2 * attempt)
            print(
                {
                    "event": "db_operation_retry",
                    "label": label,
                    "attempt": attempt,
                    "wait_seconds": wait,
                    "error": str(exc)[:300],
                }
            )
            time.sleep(wait)
    assert last_exc is not None
    raise last_exc


async def run_platform(
    platform: str,
    query: str,
    max_pages: int,
    max_products: int | None,
    headless: bool,
    debug: bool,
    sem: asyncio.Semaphore,
) -> dict:
    async with sem:
        pseudo_task = {
            "id": None,
            "platform": platform,
            "task_type": "discovery",
            "query": query,
            "url": None,
            "metadata": {"source": "run_mayabu_db"},
        }

        def _start() -> str:
            with db_connection() as conn:
                return start_run(conn, pseudo_task)

        run_id = _with_db_retry(_start, label=f"start_run:{platform}")
        try:
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

            def _ingest() -> tuple[str, dict]:
                with db_connection() as conn:
                    stats = ingest_records(
                        conn, records, platform, query, run_id=run_id, task_id=None
                    )
                    status = (
                        "empty"
                        if not records
                        else ("completed" if stats.valid else "partial")
                    )
                    stats_dict = stats.as_dict()
                    finish_run(
                        conn,
                        run_id,
                        status,
                        stats_dict,
                        error=None if records else "Scraper returned zero records",
                    )
                    print(platform, status, stats_dict)
                    return status, stats_dict, list(stats.affected_product_ids)

            status, stats_dict, affected_product_ids = _with_db_retry(
                _ingest, label=f"ingest:{platform}"
            )
            if affected_product_ids:
                refresh_variant_groups(affected_product_ids)
                refresh_product_search_documents(affected_product_ids, strict=False)
            return {
                "platform": platform,
                "ok": status in {"completed", "partial"}
                and int(stats_dict.get("valid") or 0) > 0,
                "status": status,
                "records": len(records),
                "valid": int(stats_dict.get("valid") or 0),
            }
        except Exception as exc:
            error_text = str(exc)

            def _finish_failed() -> None:
                with db_connection() as conn:
                    finish_run(
                        conn,
                        run_id,
                        "failed",
                        {"errors": [error_text]},
                        error=error_text,
                    )

            try:
                _with_db_retry(
                    _finish_failed, attempts=2, label=f"finish_failed:{platform}"
                )
            except Exception as finish_exc:
                print(
                    {
                        "event": "finish_run_failed",
                        "platform": platform,
                        "error": str(finish_exc)[:500],
                    }
                )
            return {"platform": platform, "ok": False, "error": error_text[:1000]}


async def main_async(args: argparse.Namespace) -> None:
    max_pages = _bounded_positive(
        args.max_pages, default=2, maximum=args.max_safe_pages, name="--max-pages"
    )
    max_products = _bounded_positive(
        args.max_products,
        default=50,
        maximum=args.max_safe_products,
        name="--max-products",
    )
    platform_concurrency = max(1, min(args.platform_concurrency, len(args.platforms)))
    sem = asyncio.Semaphore(platform_concurrency)

    print(
        {
            "event": "mayabu_scrape_started",
            "query": args.query,
            "platforms": args.platforms,
            "max_pages": max_pages,
            "max_products": max_products,
            "platform_concurrency": platform_concurrency,
        }
    )

    tasks = [
        run_platform(
            platform,
            args.query,
            max_pages,
            max_products,
            not args.show_browser,
            args.debug,
            sem,
        )
        for platform in args.platforms
    ]
    platform_results = await asyncio.gather(*tasks)
    failed = [result for result in platform_results if not result.get("ok")]
    print(
        {
            "event": "mayabu_scrape_finished",
            "results": platform_results,
            "failed_platforms": len(failed),
        }
    )

    if not args.skip_auto_merge and len(failed) < len(platform_results):

        def _merge() -> dict:
            with db_connection() as conn:
                return auto_merge_duplicate_products(
                    conn,
                    limit=args.auto_merge_limit,
                    min_score=args.auto_merge_min_score,
                )

        result = _with_db_retry(_merge, label="auto_merge")
        print("auto_merge", result)

    if not args.skip_search_index_refresh:
        index_result = drain_dirty_search_documents(limit=5000, strict=False)
        print({"event": "incremental_search_index_refresh", **index_result})

    if len(failed) == len(platform_results):
        raise SystemExit(
            "All requested platform scrapes failed. Review debug artifacts and platform health before retrying."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Mayabu DB-first scrape pipeline")
    parser.add_argument("query")
    parser.add_argument(
        "--platforms",
        nargs="+",
        default=_DEFAULT_PLATFORMS,
    )
    parser.add_argument("--max-pages", type=int, default=2)
    parser.add_argument("--max-products", type=int, default=50)
    parser.add_argument(
        "--max-safe-pages", type=int, default=_env_int("MAYABU_CLI_MAX_SAFE_PAGES", 50)
    )
    parser.add_argument(
        "--max-safe-products",
        type=int,
        default=_env_int("MAYABU_CLI_MAX_SAFE_PRODUCTS", 1000),
    )
    parser.add_argument(
        "--platform-concurrency",
        type=int,
        default=_env_int("MAYABU_SCRAPER_PLATFORM_CONCURRENCY", 2),
    )
    parser.add_argument("--show-browser", action="store_true")
    parser.add_argument(
        "--debug", action="store_true", help="Save scraper debug artifacts"
    )
    parser.add_argument(
        "--skip-auto-merge",
        action="store_true",
        help="Disable safe duplicate-product auto-merge after scraping",
    )
    parser.add_argument(
        "--skip-search-index-refresh",
        action="store_true",
        help="Disable incremental search-document refresh after scraping",
    )
    parser.add_argument("--auto-merge-limit", type=int, default=100)
    parser.add_argument("--auto-merge-min-score", type=float, default=92.0)
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
