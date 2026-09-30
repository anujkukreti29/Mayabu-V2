from __future__ import annotations

import argparse
from typing import Iterable

from psycopg.types.json import Jsonb

from mayabu.platforms.registry import iter_enabled_slugs
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

# Bounded multi-category probes for production catalog activation.
# Kept separate from laptop defaults so laptop discovery cadence stays unchanged.
MULTI_CATEGORY_DISCOVERY_QUERIES = [
    "samsung galaxy smartphone",
    "iphone",
    "oneplus smartphone",
    "samsung 55 inch tv",
    "lg oled tv",
    "sony bravia",
    "lg 260l refrigerator",
    "samsung double door refrigerator",
    "lg 8kg front load washing machine",
    "samsung top load washing machine",
    "samsung galaxy buds",
    "oneplus buds",
    "boat tws",
    "sony headphones",
    "jbl headphones",
    "canon mirrorless camera",
    "sony alpha camera",
]


DEFAULT_PLATFORMS = list(iter_enabled_slugs())


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


# Temporary catalog-balancing weight: lower number = higher scheduler priority.
# Laptop already dominates inventory; deprioritize while other verticals catch up.
_CATEGORY_DISCOVERY_PRIORITY: dict[str, int] = {
    "camera": 70,
    "headphones": 75,
    "tws": 80,
    "television": 85,
    "washing_machine": 90,
    "refrigerator": 95,
    "smartphone": 100,
    "laptop": 160,
}


def create_multi_category_plans(
    max_pages: int = 1,
    max_products: int | None = 20,
    platforms: Iterable[str] | None = None,
) -> int:
    """Seed bounded multi-category discovery plans for production-enabled pairs only.

    Idempotent via unique plan name. Returns number of plans upserted.
    """
    from mayabu.domain.categories.registry import detect_category_result
    from mayabu.platforms.coverage import discovery_allowed, production_discovery_pairs

    pairs = production_discovery_pairs()
    if platforms:
        allowed = {canonical_platform(p) for p in platforms}
        pairs = [(p, c) for p, c in pairs if p in allowed]

    # Map category → representative queries from the multi-category list.
    by_category: dict[str, list[str]] = {}
    for query in MULTI_CATEGORY_DISCOVERY_QUERIES:
        det = detect_category_result(title=query, query=query)
        cat = det.category if det.category not in {"unknown", "accessory"} else None
        if not cat:
            continue
        by_category.setdefault(cat, []).append(query)

    upserted = 0
    with db_connection() as conn:
        with conn.cursor() as cur:
            for platform, category in pairs:
                if not discovery_allowed(platform, category):
                    continue
                queries = by_category.get(category) or [category.replace("_", " ")]
                priority = _CATEGORY_DISCOVERY_PRIORITY.get(category, 120)
                # Slightly slower cadence for laptops during rebalance.
                cadence = 4320 if category == "laptop" else 2880
                for query in queries:
                    name = f"{platform}:discovery:mc:{category}:{query}"
                    cur.execute(
                        """
                        insert into scheduler_plans(name, platform, task_type, query, cadence_minutes, priority, max_pages, max_products, metadata)
                        values (%s,%s,'discovery',%s,%s,%s,%s,%s,%s)
                        on conflict (name) do update set
                          max_pages = excluded.max_pages,
                          max_products = excluded.max_products,
                          priority = excluded.priority,
                          cadence_minutes = excluded.cadence_minutes,
                          enabled = true,
                          updated_at = now()
                        """,
                        (
                            name,
                            canonical_platform(platform),
                            query,
                            cadence,
                            priority,
                            max_pages,
                            max_products,
                            Jsonb(
                                {
                                    "purpose": "multi_category_catalog_activation",
                                    "category": category,
                                    "readiness": "production",
                                    "catalog_balance": True,
                                }
                            ),
                        ),
                    )
                    upserted += 1
    return upserted


def ensure_production_discovery_plans(
    *,
    max_pages: int = 1,
    max_products: int | None = 20,
    force: bool = False,
) -> dict[str, int]:
    """Idempotent bootstrap: seed production multi-category plans when missing.

    Does not enqueue tasks. Does not enable the scheduler. Safe for API/worker boot
    and for CLI operators.
    """
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select count(*)::int as n
                from scheduler_plans
                where enabled = true
                  and task_type = 'discovery'
                  and coalesce(metadata->>'purpose', '') = 'multi_category_catalog_activation'
                """
            )
            existing = int(cur.fetchone()["n"] or 0)
    if existing > 0 and not force:
        return {"existing": existing, "upserted": 0, "seeded": 0}
    upserted = create_multi_category_plans(max_pages=max_pages, max_products=max_products)
    return {"existing": existing, "upserted": upserted, "seeded": upserted}


def materialize_due_plans(limit: int | None = None) -> int:
    from mayabu.domain.categories.registry import detect_category_result
    from mayabu.platforms.coverage import discovery_allowed, task_allowed
    from mayabu.scheduler.platform_health_policy import platform_allows_task

    created = 0
    max_plans = None if limit is None else max(0, int(limit))
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
                if max_plans is not None and created >= max_plans:
                    break
                platform = plan["platform"]
                metadata = plan.get("metadata") or {}
                if isinstance(metadata, str):
                    metadata = {}
                category = metadata.get("category") if isinstance(metadata, dict) else None
                if not category and plan.get("query"):
                    det = detect_category_result(title=plan["query"], query=plan["query"])
                    if det.category not in {"unknown", "accessory"}:
                        category = det.category
                if category and not discovery_allowed(platform, category):
                    continue
                if category and not task_allowed(platform, category, plan["task_type"]):
                    continue
                if not platform_allows_task(platform, plan["task_type"]):
                    continue
                from mayabu.scheduler.discovery_cursor import start_page_from_metadata, supports_page_cursor

                start_page = start_page_from_metadata(metadata) if supports_page_cursor(platform) else 1
                create_task(
                    conn,
                    platform,
                    plan["task_type"],
                    query=plan.get("query"),
                    priority=plan.get("priority") or 100,
                    max_pages=plan.get("max_pages"),
                    max_products=plan.get("max_products"),
                    metadata={
                        "scheduler_plan_id": str(plan["id"]),
                        "scheduler_plan_name": plan["name"],
                        "category": category,
                        "source": "scheduler_plan",
                        "task_source": "scheduler_discovery",
                        "start_page": start_page,
                        "page_cursor": supports_page_cursor(platform),
                    },
                    idempotency_key=f"discovery:{plan['id']}",
                    created_by="scheduler",
                )
                cur.execute(
                    "update scheduler_plans set last_materialized_at = now(), updated_at = now() where id = %s",
                    (plan["id"],),
                )
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

    mc_plans = sub.add_parser("create-multi-category-plans")
    mc_plans.add_argument("--max-pages", type=int, default=1)
    mc_plans.add_argument("--max-products", type=int, default=20)
    mc_plans.add_argument("--platforms", nargs="+")

    ensure = sub.add_parser("ensure-discovery-plans")
    ensure.add_argument("--max-pages", type=int, default=1)
    ensure.add_argument("--max-products", type=int, default=20)
    ensure.add_argument("--force", action="store_true")

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
    elif args.command == "create-multi-category-plans":
        n = create_multi_category_plans(args.max_pages, args.max_products, args.platforms)
        print(f"Multi-category scheduler plans created/updated: {n}")
    elif args.command == "ensure-discovery-plans":
        result = ensure_production_discovery_plans(
            max_pages=getattr(args, "max_pages", 1),
            max_products=getattr(args, "max_products", 20),
            force=bool(getattr(args, "force", False)),
        )
        print(result)
    elif args.command == "materialize-due":
        print(f"Created {materialize_due_plans()} due tasks")
    elif args.command == "materialize-refresh-due":
        print(f"Created {materialize_due_refresh_tasks(limit=args.limit, platforms=args.platforms)} refresh tasks")


if __name__ == "__main__":
    main()
