"""Maintenance jobs for Mayabu background operations."""

from __future__ import annotations

import argparse

from mayabu.db.connection import db_connection
from mayabu.search.demand_signal import refresh_demand_counters
from mayabu_db.repository import find_duplicate_product_candidates, rebuild_daily_product_prices
from mayabu_db.tasks import cleanup_raw_scrape_items, requeue_stuck_tasks


def run_queue_reaper(max_age_minutes: int = 45) -> int:
    with db_connection() as conn:
        return requeue_stuck_tasks(conn, max_age_minutes=max_age_minutes)


def run_raw_cleanup(retention_days: int = 30) -> int:
    with db_connection() as conn:
        return cleanup_raw_scrape_items(conn, retention_days=retention_days)


def run_price_rollup_rebuild(product_id: str | None = None) -> int:
    with db_connection() as conn:
        return rebuild_daily_product_prices(conn, product_id=product_id)


def run_duplicate_candidate_finder(limit: int = 100, min_score: float = 70.0) -> int:
    with db_connection() as conn:
        return find_duplicate_product_candidates(conn, limit=limit, min_score=min_score)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mayabu maintenance jobs")
    sub = parser.add_subparsers(dest="command", required=True)
    reaper = sub.add_parser("reap-stuck-tasks")
    reaper.add_argument("--max-age-minutes", type=int, default=45)
    cleanup = sub.add_parser("cleanup-raw")
    cleanup.add_argument("--retention-days", type=int, default=30)
    sub.add_parser("refresh-demand-counters")
    rebuild = sub.add_parser("rebuild-price-rollups")
    rebuild.add_argument("--product-id")
    dupes = sub.add_parser("find-duplicate-products")
    dupes.add_argument("--limit", type=int, default=100)
    dupes.add_argument("--min-score", type=float, default=70.0)
    all_jobs = sub.add_parser("run-all")
    all_jobs.add_argument("--max-age-minutes", type=int, default=45)
    all_jobs.add_argument("--retention-days", type=int, default=30)
    args = parser.parse_args()

    if args.command == "reap-stuck-tasks":
        print(f"Reaped {run_queue_reaper(args.max_age_minutes)} stuck tasks")
    elif args.command == "cleanup-raw":
        print(f"Deleted {run_raw_cleanup(args.retention_days)} old raw scrape rows")
    elif args.command == "refresh-demand-counters":
        print(f"Refreshed {refresh_demand_counters()} demand clusters")
    elif args.command == "rebuild-price-rollups":
        print(f"Rebuilt {run_price_rollup_rebuild(args.product_id)} daily product price rows")
    elif args.command == "find-duplicate-products":
        print(f"Queued {run_duplicate_candidate_finder(args.limit, args.min_score)} duplicate product candidates")
    elif args.command == "run-all":
        print(f"Reaped {run_queue_reaper(args.max_age_minutes)} stuck tasks")
        print(f"Deleted {run_raw_cleanup(args.retention_days)} old raw scrape rows")
        print(f"Refreshed {refresh_demand_counters()} demand clusters")
        print(f"Queued {run_duplicate_candidate_finder()} duplicate product candidates")
        print(f"Rebuilt {run_price_rollup_rebuild()} daily product price rows")


if __name__ == "__main__":
    main()
