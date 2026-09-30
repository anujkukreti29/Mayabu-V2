"""Resumable multi-category discovery campaign.

Seeds scheduler_plans and materializes discovery tasks through the existing
PostgreSQL queue. Does not reimplement scrapers. Refuses any database other
than the development catalog named mayabu.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.parse import urlparse

from psycopg.types.json import Jsonb

from mayabu.platforms.coverage import discovery_allowed
from mayabu_common import canonical_platform
from mayabu_db.connection import db_connection
from mayabu_db.tasks import create_task

PURPOSE = "catalog_expansion_v1"
CATEGORIES = (
    "laptop",
    "smartphone",
    "television",
    "refrigerator",
    "washing_machine",
    "tws",
    "headphones",
    "camera",
)

# One task paginates until a natural stop (empty / last page / no-new) or this
# ceiling. Flipkart and Reliance use the emergency page ceiling; Amazon and
# Croma stay intentionally shallow and stop on challenge.
PAGE_BUDGET = {
    "flipkart": 40,
    "reliancedigital": 40,
    "vijaysales": 8,
    "poorvika": 12,
    "amazon": 1,
    "croma": 1,
}
PRODUCT_BUDGET = {
    "flipkart": 400,
    "reliancedigital": 240,
    "vijaysales": 96,
    "poorvika": 120,
    "amazon": 12,
    "croma": 10,
}

_QUERIES: dict[str, list[str]] = {
    "laptop": [
        "laptop", "notebook", "gaming laptop", "thin laptop", "business laptop",
        "student laptop", "creator laptop", "2 in 1 laptop",
        "apple macbook", "hp laptop", "dell laptop", "lenovo laptop", "asus laptop",
        "acer laptop", "msi laptop", "samsung laptop", "infinix laptop", "honor laptop",
        "macbook air", "macbook pro",
        "hp pavilion", "hp victus", "hp omen", "hp envy", "hp 15", "hp 14",
        "dell inspiron", "dell vostro", "dell g15", "dell alienware",
        "lenovo ideapad", "lenovo loq", "lenovo legion", "lenovo thinkpad", "lenovo yoga",
        "asus vivobook", "asus zenbook", "asus tuf", "asus rog",
        "acer aspire", "acer alg", "acer nitro", "acer predator", "acer swift",
        "msi modern", "msi thin", "msi katana", "msi cyborg",
        "core i3 laptop", "core i5 laptop", "core i7 laptop",
        "core ultra 5 laptop", "core ultra 7 laptop",
        "ryzen 3 laptop", "ryzen 5 laptop", "ryzen 7 laptop",
        "rtx 3050 laptop", "rtx 4050 laptop", "rtx 4060 laptop",
    ],
    "smartphone": [
        "smartphone", "mobile phone", "5g phone",
        "apple iphone", "samsung galaxy", "oneplus", "google pixel", "xiaomi",
        "redmi", "poco", "realme", "motorola", "nothing phone", "vivo", "oppo", "iqoo",
        "iphone 16", "iphone 15", "galaxy s24", "galaxy s25", "galaxy a",
        "oneplus nord", "redmi note", "poco x", "realme narzo", "vivo v", "oppo reno",
        "smartphone 128gb", "smartphone 256gb", "smartphone 512gb", "iphone 256gb",
        "galaxy 256gb", "iphone 512gb", "iphone 1tb",
    ],
    "television": [
        "television", "smart tv", "4k tv", "oled tv", "qled tv", "mini led tv", "led tv",
        "samsung tv", "lg tv", "sony tv", "tcl tv", "hisense tv", "xiaomi tv",
        "vu tv", "panasonic tv",
        "32 inch tv", "43 inch tv", "50 inch tv", "55 inch tv", "65 inch tv", "75 inch tv",
        "samsung 55 inch tv", "lg oled tv", "sony bravia",
    ],
    "refrigerator": [
        "refrigerator", "fridge", "double door refrigerator", "single door refrigerator",
        "side by side refrigerator", "french door refrigerator",
        "samsung refrigerator", "lg refrigerator", "whirlpool refrigerator",
        "godrej refrigerator", "haier refrigerator", "panasonic refrigerator",
        "190 l refrigerator", "240 l refrigerator", "260 l refrigerator", "300 l refrigerator",
    ],
    "washing_machine": [
        "washing machine", "front load washing machine", "top load washing machine",
        "semi automatic washing machine", "fully automatic washing machine",
        "lg washing machine", "samsung washing machine", "whirlpool washing machine",
        "bosch washing machine", "ifb washing machine", "haier washing machine",
        "godrej washing machine",
        "6 kg washing machine", "7 kg washing machine", "8 kg washing machine",
        "9 kg washing machine", "10 kg washing machine",
    ],
    "tws": [
        "tws", "true wireless earbuds", "wireless earbuds",
        "apple airpods", "samsung galaxy buds", "sony wf", "oneplus buds",
        "nothing ear", "realme buds", "oppo enco", "boat earbuds", "jbl earbuds",
        "bose earbuds", "sennheiser earbuds",
    ],
    "headphones": [
        "headphones", "wireless headphones", "over ear headphones",
        "noise cancelling headphones", "gaming headphones",
        "sony headphones", "bose headphones", "jbl headphones", "boat headphones",
        "sennheiser headphones", "marshall headphones", "audio technica headphones",
    ],
    "camera": [
        "camera", "mirrorless camera", "dslr camera", "digital camera",
        "sony alpha", "canon eos", "nikon camera", "fujifilm camera",
        "panasonic lumix", "camera body", "camera kit",
    ],
}


def normalize_query(value: str) -> str:
    return " ".join(value.lower().split())


def queries_for(category: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in _QUERIES.get(category, []):
        query = normalize_query(raw)
        if query and query not in seen:
            seen.add(query)
            out.append(query)
    return out


def database_identity(url: str) -> dict[str, str]:
    parsed = urlparse(url)
    name = (parsed.path or "").lstrip("/").split("?")[0]
    return {
        "host": parsed.hostname or "",
        "name": name,
        "environment": os.getenv("MAYABU_ENV", "development"),
    }


def assert_dev_database(url: str) -> dict[str, str]:
    ident = database_identity(url)
    if ident["name"] != "mayabu":
        raise SystemExit(f"refusing database {ident['name']!r}; campaign targets mayabu only")
    if ident["host"] not in {"127.0.0.1", "localhost"}:
        raise SystemExit(f"refusing non-local host {ident['host']!r}")
    return ident


def retailers_for(category: str, requested: list[str] | None) -> list[str]:
    from mayabu.platforms.coverage import production_discovery_pairs

    allowed = [platform for platform, cat in production_discovery_pairs() if cat == category]
    if requested:
        wanted = {canonical_platform(item) for item in requested}
        allowed = [platform for platform in allowed if platform in wanted]
    # Stable budget order: deep sources first, limited sources last.
    order = ["flipkart", "reliancedigital", "vijaysales", "poorvika", "amazon", "croma"]
    return sorted(allowed, key=lambda name: order.index(name) if name in order else 99)


def seed_plans(category: str, platforms: list[str] | None) -> dict:
    targets = retailers_for(category, platforms)
    queries = queries_for(category)
    upserted = 0
    with db_connection() as conn, conn.cursor() as cur:
        for platform in targets:
            if not discovery_allowed(platform, category):
                continue
            for query in queries:
                name = f"catalog-expansion:{platform}:{category}:{query}"
                cur.execute(
                    """
                    insert into scheduler_plans(
                      name, platform, task_type, query, cadence_minutes, priority,
                      max_pages, max_products, metadata, enabled
                    )
                    values (%s,%s,'discovery',%s,10080,%s,%s,%s,%s,true)
                    on conflict (name) do update set
                      max_pages = greatest(scheduler_plans.max_pages, excluded.max_pages),
                      max_products = greatest(scheduler_plans.max_products, excluded.max_products),
                      metadata = scheduler_plans.metadata || excluded.metadata,
                      enabled = true,
                      updated_at = now()
                    """,
                    (
                        name,
                        platform,
                        query,
                        80,
                        PAGE_BUDGET.get(platform, 2),
                        PRODUCT_BUDGET.get(platform, 20),
                        Jsonb(
                            {
                                "purpose": PURPOSE,
                                "category": category,
                                "campaign": "catalog_expansion_v1",
                            }
                        ),
                    ),
                )
                upserted += 1
    return {"category": category, "retailers": targets, "queries": len(queries), "plans": upserted}


def resume_incomplete(category: str) -> int:
    """Allow unfinished plans to rematerialize without waiting for cadence.

    Saturated plans stay closed. Circuit-blocked plans reopen only when the
    retailer currently allows discovery (do not clear platform_health circuits).
    """
    from mayabu.scheduler.platform_health_policy import platform_allows_task

    reopened = 0
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            update scheduler_plans
            set last_materialized_at = null, updated_at = now()
            where enabled = true
              and task_type = 'discovery'
              and coalesce(metadata->>'purpose','') = %s
              and coalesce(metadata->>'category','') = %s
              and coalesce(metadata->>'completion','') not in ('saturated', 'circuit_blocked')
            """,
            (PURPOSE, category),
        )
        cleared = int(cur.rowcount or 0)
        cur.execute(
            """
            select id, platform from scheduler_plans
            where enabled = true
              and task_type = 'discovery'
              and coalesce(metadata->>'purpose','') = %s
              and coalesce(metadata->>'category','') = %s
              and coalesce(metadata->>'completion','') = 'circuit_blocked'
              and platform in ('amazon', 'croma')
            """,
            (PURPOSE, category),
        )
        for row in cur.fetchall():
            if not platform_allows_task(row["platform"], "discovery"):
                continue
            cur.execute(
                """
                update scheduler_plans
                set last_materialized_at = null,
                    updated_at = now(),
                    metadata = (coalesce(metadata, '{}'::jsonb) - 'completion' - 'error_state')
                where id = %s
                """,
                (row["id"],),
            )
            reopened += 1
    return cleared + reopened


def pending_discovery() -> int:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select count(*)::int as n
            from scrape_tasks
            where task_type = 'discovery'
              and status in ('pending','running','paused')
              and coalesce(metadata->>'purpose','') = %s
            """,
            (PURPOSE,),
        )
        # metadata on tasks may store purpose only after materialize copies it.
        # Also count by plan name prefix via scheduler_plan_name.
        by_purpose = int(cur.fetchone()["n"] or 0)
        cur.execute(
            """
            select count(*)::int as n
            from scrape_tasks
            where task_type = 'discovery'
              and status in ('pending','running','paused')
              and coalesce(metadata->>'scheduler_plan_name','') like 'catalog-expansion:%'
            """
        )
        return max(by_purpose, int(cur.fetchone()["n"] or 0))


def materialize(category: str, *, limit: int) -> int:
    from mayabu.scheduler.discovery_cursor import start_page_from_metadata, supports_page_cursor
    from mayabu.scheduler.platform_health_policy import platform_allows_task

    created = 0
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select * from scheduler_plans
            where enabled = true
              and task_type = 'discovery'
              and coalesce(metadata->>'purpose','') = %s
              and coalesce(metadata->>'category','') = %s
              and coalesce(metadata->>'completion','') not in ('saturated', 'circuit_blocked', 'limited_budget_held')
              and (
                last_materialized_at is null
                or last_materialized_at + make_interval(mins => cadence_minutes) <= now()
              )
            order by
              case platform
                when 'flipkart' then 0
                when 'reliancedigital' then 1
                when 'vijaysales' then 2
                when 'poorvika' then 3
                when 'amazon' then 4
                when 'croma' then 5
                else 9
              end,
              name
            """,
            (PURPOSE, category),
        )
        plans = cur.fetchall()
        for plan in plans:
            if created >= limit:
                break
            platform = plan["platform"]
            if not discovery_allowed(platform, category):
                continue
            if not platform_allows_task(platform, "discovery"):
                # Record the stop. Do not clear a circuit or retry discovery.
                cur.execute(
                    """
                    update scheduler_plans
                    set last_materialized_at = now(),
                        updated_at = now(),
                        metadata = coalesce(metadata, '{}'::jsonb) || %s::jsonb
                    where id = %s
                      and last_materialized_at is null
                    """,
                    (
                        Jsonb(
                            {
                                "completion": "circuit_blocked",
                                "error_state": "discovery_not_allowed",
                            }
                        ),
                        plan["id"],
                    ),
                )
                continue
            metadata = plan.get("metadata") or {}
            start_page = start_page_from_metadata(metadata) if supports_page_cursor(platform) else 1
            create_task(
                conn,
                platform,
                "discovery",
                query=plan.get("query"),
                priority=plan.get("priority") or 80,
                max_pages=plan.get("max_pages"),
                max_products=plan.get("max_products"),
                metadata={
                    "scheduler_plan_id": str(plan["id"]),
                    "scheduler_plan_name": plan["name"],
                    "category": category,
                    "purpose": PURPOSE,
                    "source": "catalog_expansion_v1",
                    "task_source": "catalog_expansion",
                    "start_page": start_page,
                    "page_cursor": supports_page_cursor(platform),
                },
                idempotency_key=f"discovery:{plan['id']}",
                created_by="catalog_expansion",
            )
            cur.execute(
                "update scheduler_plans set last_materialized_at = now(), updated_at = now() where id = %s",
                (plan["id"],),
            )
            created += 1
    return created


def queue_snapshot() -> dict:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select status, count(*)::int as n
            from scrape_tasks
            where coalesce(metadata->>'scheduler_plan_name','') like 'catalog-expansion:%'
               or created_by = 'catalog_expansion'
            group by status
            """
        )
        return {row["status"]: row["n"] for row in cur.fetchall()}


def write_checkpoint(category: str, report_dir: str, payload: dict) -> None:
    os.makedirs(report_dir, exist_ok=True)
    path = os.path.join(report_dir, f"{category}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", choices=CATEGORIES)
    parser.add_argument("--all-categories", action="store_true")
    parser.add_argument("--retailer", action="append")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--materialize", type=int, default=0, help="Enqueue up to N due plans")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Clear last_materialized_at on incomplete (non-saturated) plans",
    )
    parser.add_argument("--report-dir", default="artifacts/catalog_campaign")
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        print("DATABASE_URL required", file=sys.stderr)
        return 2
    ident = assert_dev_database(url)
    categories = list(CATEGORIES) if args.all_categories else [args.category or "laptop"]
    report = {"database": ident, "categories": []}
    for category in categories:
        seeded = seed_plans(category, args.retailer)
        resumed = 0
        if args.resume and not args.dry_run:
            resumed = resume_incomplete(category)
        created = 0
        if args.materialize and not args.dry_run:
            room = max(0, args.materialize)
            created = materialize(category, limit=room)
        entry = {
            **seeded,
            "resumed": resumed,
            "materialized": created,
            "dry_run": args.dry_run,
        }
        report["categories"].append(entry)
        if not args.dry_run:
            entry["queue"] = queue_snapshot()
            write_checkpoint(category, args.report_dir, entry)
    json.dump(report, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
