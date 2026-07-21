from __future__ import annotations

import argparse
from typing import Iterable

from psycopg.types.json import Jsonb

from mayabu_common import canonical_platform
from mayabu_db.connection import db_connection
from mayabu_db.tasks import create_task

DEFAULT_DISCOVERY_QUERIES = [
    "laptop",
    "gaming laptop",
    "student laptop",
    "business laptop",
    "laptop under 30000",
    "laptop under 40000",
    "laptop under 50000",
    "laptop under 60000",
    "laptop under 80000",
    "laptop under 100000",
    "lenovo laptop",
    "hp laptop",
    "dell laptop",
    "asus laptop",
    "acer laptop",
    "apple macbook",
]

DEFAULT_PLATFORMS = ["amazon", "flipkart", "croma", "reliancedigital"]


def seed_discovery_tasks(platforms: Iterable[str], queries: Iterable[str], max_pages: int = 2, max_products: int | None = None) -> list[str]:
    task_ids: list[str] = []
    with db_connection() as conn:
        for platform in platforms:
            for query in queries:
                task_ids.append(create_task(conn, platform, "discovery", query=query, priority=100, max_pages=max_pages, max_products=max_products, metadata={"source": "manual_seed"}))
    return task_ids


def create_default_plans(max_pages: int = 2, max_products: int | None = None) -> None:
    with db_connection() as conn:
        with conn.cursor() as cur:
            for platform in DEFAULT_PLATFORMS:
                for query in DEFAULT_DISCOVERY_QUERIES:
                    name = f"{platform}:discovery:{query}"
                    cur.execute(
                        """
                        insert into scheduler_plans(name, platform, task_type, query, cadence_minutes, priority, max_pages, max_products, metadata)
                        values (%s,%s,'discovery',%s,1440,100,%s,%s,%s)
                        on conflict (name) do update set
                          max_pages = excluded.max_pages,
                          max_products = excluded.max_products,
                          enabled = true,
                          updated_at = now()
                        """,
                        (name, canonical_platform(platform), query, max_pages, max_products, Jsonb({"purpose": "broad_laptop_discovery"})),
                    )


def materialize_due_plans() -> int:
    created = 0
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select * from scheduler_plans
                where enabled = true
                  and (last_materialized_at is null or last_materialized_at + make_interval(mins => cadence_minutes) <= now())
                order by priority asc, name asc
                """
            )
            plans = cur.fetchall()
            for plan in plans:
                create_task(conn, plan["platform"], plan["task_type"], query=plan.get("query"), priority=plan.get("priority") or 100, max_pages=plan.get("max_pages"), max_products=plan.get("max_products"), metadata={"scheduler_plan_id": str(plan["id"]), "scheduler_plan_name": plan["name"]})
                cur.execute("update scheduler_plans set last_materialized_at = now(), updated_at = now() where id = %s", (plan["id"],))
                created += 1
    return created



def materialize_due_refresh_tasks(limit: int = 100, platforms: Iterable[str] | None = None) -> int:
    """Compatibility wrapper for the v4 task materializer.

    The canonical refresh materialization logic lives in
    mayabu.scheduler.task_materializer. Keeping this wrapper avoids two
    independent implementations creating duplicate refresh tasks.
    """
    from mayabu.scheduler.task_materializer import materialize_refresh

    if platforms:
        return sum(materialize_refresh(limit=limit, platform=canonical_platform(platform)) for platform in platforms)
    return materialize_refresh(limit=limit)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mayabu DB scheduler utilities")
    sub = parser.add_subparsers(dest="command", required=True)

    seed = sub.add_parser("seed-discovery")
    seed.add_argument("--platforms", nargs="+", default=DEFAULT_PLATFORMS)
    seed.add_argument("--query", action="append", dest="queries")
    seed.add_argument("--max-pages", type=int, default=2)
    seed.add_argument("--max-products", type=int)

    plans = sub.add_parser("create-default-plans")
    plans.add_argument("--max-pages", type=int, default=2)
    plans.add_argument("--max-products", type=int)

    sub.add_parser("materialize-due")

    refresh = sub.add_parser("materialize-refresh-due")
    refresh.add_argument("--limit", type=int, default=100)
    refresh.add_argument("--platforms", nargs="+")
    args = parser.parse_args()

    if args.command == "seed-discovery":
        ids = seed_discovery_tasks(args.platforms, args.queries or DEFAULT_DISCOVERY_QUERIES, args.max_pages, args.max_products)
        print(f"Created {len(ids)} discovery tasks")
    elif args.command == "create-default-plans":
        create_default_plans(args.max_pages, args.max_products)
        print("Default scheduler plans created/updated")
    elif args.command == "materialize-due":
        print(f"Created {materialize_due_plans()} due tasks")
    elif args.command == "materialize-refresh-due":
        print(f"Created {materialize_due_refresh_tasks(limit=args.limit, platforms=args.platforms)} refresh tasks")


if __name__ == "__main__":
    main()
