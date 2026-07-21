"""Materialize safe scrape tasks from refresh policy and demand signals."""

from __future__ import annotations

import argparse

from mayabu.db.connection import db_connection
from mayabu.search.demand_signal import list_promotable_demand
from mayabu.scheduler.budget_policy import budget_available, ensure_today_budget
from mayabu.scheduler.platform_health_policy import platform_allows_task
from mayabu.scheduler.refresh_policy import due_refresh_candidates
from mayabu_db.tasks import create_task

PLATFORMS = ["amazon", "flipkart", "croma", "reliancedigital"]


def materialize_refresh(limit: int = 100, platform: str | None = None) -> int:
    rows = due_refresh_candidates(limit=limit, platform=platform)
    created = 0
    with db_connection() as conn:
        for row in rows:
            plat = row["platform"]
            ensure_today_budget(plat)
            if not platform_allows_task(plat, "refresh_listing") or not budget_available(plat, "refresh_listing"):
                continue
            create_task(
                conn,
                plat,
                "refresh_listing",
                url=row["listing_url"],
                native_id=row.get("native_id"),
                priority=int(row.get("refresh_priority") or 100),
                metadata={
                    "source": "refresh_policy_v4",
                    "platform_listing_id": str(row["id"]),
                    "listing_id": row["listing_id"],
                    "product_id": str(row["product_id"]) if row.get("product_id") else None,
                },
            )
            created += 1
    return created


def materialize_demand_discovery(limit: int = 25, min_score: float = 70.0) -> int:
    clusters = list_promotable_demand(limit=limit, min_score=min_score)
    created = 0
    with db_connection() as conn:
        for cluster in clusters:
            query = cluster["canonical_query"].replace("|", " ")
            for plat in PLATFORMS:
                ensure_today_budget(plat)
                if not platform_allows_task(plat, "discovery") or not budget_available(plat, "discovery"):
                    continue
                create_task(
                    conn,
                    plat,
                    "discovery",
                    query=query,
                    priority=max(10, 100 - int(cluster.get("priority_score") or 0)),
                    max_pages=1,
                    max_products=30,
                    metadata={"source": "demand_cluster", "demand_cluster_id": str(cluster["id"])},
                )
                created += 1
            with conn.cursor() as cur:
                cur.execute("update query_demand_clusters set last_promoted_at = now() where id = %s", (cluster["id"],))
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Mayabu v4 task materializer")
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("refresh")
    r.add_argument("--limit", type=int, default=100)
    r.add_argument("--platform")
    d = sub.add_parser("demand")
    d.add_argument("--limit", type=int, default=25)
    d.add_argument("--min-score", type=float, default=70.0)
    args = parser.parse_args()
    if args.command == "refresh":
        print(f"Created {materialize_refresh(limit=args.limit, platform=args.platform)} refresh tasks")
    else:
        print(f"Created {materialize_demand_discovery(limit=args.limit, min_score=args.min_score)} demand discovery tasks")


if __name__ == "__main__":
    main()
