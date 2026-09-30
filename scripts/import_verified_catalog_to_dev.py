#!/usr/bin/env python3
"""Import legitimate retailer-backed catalog rows into the development DB.

Source is typically mayabu_test (rich controlled-live catalog). Target is mayabu
(the local development application database).

Rules:
- Copy only products that have at least one platform_listing.
- Exclude synthetic hardening / fixture products.
- Never copy users, sessions, wishlist, watches, email tokens, or scrape queue.
- Idempotent replace of catalog tables on the target (truncate + insert).
- Dry-run by default; pass --apply to write.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Iterable, Sequence
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

# Auth / session / personalization — never promote.
EXCLUDED_TABLES = frozenset(
    {
        "users",
        "user_sessions",
        "email_verification_tokens",
        "password_reset_tokens",
        "user_wishlist",
        "watch_events",
        "price_alerts",
        "scrape_tasks",
        "scrape_runs",
        "raw_scrape_items",
        "scheduler_heartbeats",
        "scheduler_plans",
        "worker_heartbeats",
        "live_verification_events",
        "admin_audit_log",
        "schema_migrations",
        "search_queries",
        "query_demand_clusters",
        "product_activity_dedupe",
        "product_activity_hourly",
        "anomaly_events",
        "maintenance_runs",
        "scrape_budget",
        "scraper_diagnostics",
        "platform_health",
        "overlap_discovery_attempts",
        "retailer_category_ops_evidence",
        "review_queue",
        "product_merge_log",
        "search_document_dirty",
    }
)

# Catalog tables copied in FK-safe order (parents first).
CATALOG_COPY_ORDER: list[str] = [
    "product_clusters",
    "variant_groups",
    "platform_listings",
    "product_variant_links",
    "price_observations",
    "daily_listing_prices",
    "daily_product_prices",
    "daily_product_platform_prices",
    "product_images",
    "product_search_documents",
]

# Truncate children first.
TRUNCATE_ORDER: list[str] = list(reversed(CATALOG_COPY_ORDER)) + [
    "scrape_tasks",
    "review_queue",
    "search_document_dirty",
    "product_merge_log",
    "live_verification_events",
    "watch_events",
    "user_wishlist",
    "price_alerts",
]


def _eligible_product_sql() -> str:
    return """
    select pc.id
    from product_clusters pc
    where exists (
      select 1 from platform_listings pl where pl.product_id = pc.id
    )
    and not (
      lower(coalesce(pc.brand, '')) = 'mayabu'
      and coalesce(pc.canonical_title, '') ilike '%hardening%'
    )
    and not (
      coalesce(pc.canonical_title, '') ilike '%fixture%'
      or coalesce(pc.canonical_title, '') ilike '%synthetic seed%'
    )
    """


def _table_columns(conn: psycopg.Connection, table: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select column_name
            from information_schema.columns
            where table_schema = 'public'
              and table_name = %s
              and is_generated = 'NEVER'
            order by ordinal_position
            """,
            (table,),
        )
        return [r[0] for r in cur.fetchall()]


def _table_exists(conn: psycopg.Connection, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            select 1 from information_schema.tables
            where table_schema = 'public' and table_name = %s
            """,
            (table,),
        )
        return cur.fetchone() is not None


def _adapt(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return Jsonb(value)
    return value


def _fetch_ids(conn: psycopg.Connection) -> list[Any]:
    with conn.cursor() as cur:
        cur.execute(_eligible_product_sql())
        return [r[0] for r in cur.fetchall()]


def _classify(conn: psycopg.Connection) -> dict[str, Any]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("select count(*)::int as n from product_clusters")
        clusters_total = cur.fetchone()["n"]
        cur.execute(_eligible_product_sql())
        eligible = [r["id"] for r in cur.fetchall()]
        cur.execute(
            """
            select count(*)::int as n from product_clusters pc
            where not exists (select 1 from platform_listings pl where pl.product_id = pc.id)
            """
        )
        orphans = cur.fetchone()["n"]
        cur.execute(
            """
            select count(*)::int as n from product_clusters
            where lower(coalesce(brand,'')) = 'mayabu'
              and coalesce(canonical_title,'') ilike '%hardening%'
            """
        )
        synthetic = cur.fetchone()["n"]
        cur.execute(
            """
            select lower(coalesce(category,'')) as cat, count(*)::int as n
            from product_clusters
            where id = any(%s)
            group by 1 order by n desc
            """,
            (eligible,),
        )
        by_cat = {r["cat"]: r["n"] for r in cur.fetchall()}
        cur.execute(
            """
            select lower(coalesce(platform,'')) as p, count(*)::int as n
            from platform_listings
            where product_id = any(%s)
            group by 1 order by n desc
            """,
            (eligible,),
        )
        by_plat = {r["p"]: r["n"] for r in cur.fetchall()}
        cur.execute("select count(*)::int as n from users")
        users = cur.fetchone()["n"]
    return {
        "clusters_total": clusters_total,
        "eligible_products": len(eligible),
        "orphan_clusters_excluded": orphans,
        "synthetic_excluded": synthetic,
        "by_category": by_cat,
        "by_platform": by_plat,
        "users_not_copied": users,
        "eligible_ids": eligible,
    }


def _copy_filtered(
    src: psycopg.Connection,
    dst: psycopg.Connection,
    table: str,
    *,
    product_ids: Sequence[Any],
    listing_ids: Sequence[Any] | None = None,
) -> int:
    if not _table_exists(src, table) or not _table_exists(dst, table):
        return 0
    src_cols = _table_columns(src, table)
    dst_cols = _table_columns(dst, table)
    cols = [c for c in src_cols if c in dst_cols]
    if not cols:
        return 0

    where = ""
    params: tuple[Any, ...] = ()
    if table == "product_clusters":
        where = "id = any(%s)"
        params = (list(product_ids),)
    elif table == "variant_groups":
        # Keep groups referenced by eligible products via product_variant_links.
        where = """
        id in (
          select distinct group_id from product_variant_links
          where product_id = any(%s) and group_id is not null
        )
        """
        params = (list(product_ids),)
    elif table == "platform_listings":
        where = "product_id = any(%s)"
        params = (list(product_ids),)
    elif table == "product_variant_links":
        where = "product_id = any(%s)"
        params = (list(product_ids),)
    elif table in {"price_observations", "daily_listing_prices"}:
        if not listing_ids:
            return 0
        where = "listing_id = any(%s)"
        params = (list(listing_ids),)
    elif table in {
        "daily_product_prices",
        "daily_product_platform_prices",
        "product_images",
        "product_search_documents",
    }:
        where = "product_id = any(%s)"
        params = (list(product_ids),)
    else:
        return 0

    col_sql = ", ".join(cols)
    select_exprs = []
    for c in cols:
        # Drop ops FKs we intentionally do not copy (queue/runs/users).
        if table == "price_observations" and c in {"source_run_id", "source_task_id"}:
            select_exprs.append(f"null as {c}")
        elif table in {"price_observations", "daily_listing_prices"} and c == "product_id":
            # Prefer listing's product when row points at an excluded orphan cluster.
            select_exprs.append(
                f"""
                case
                  when {table}.product_id = any(%s) then {table}.product_id
                  else (select pl.product_id from platform_listings pl where pl.id = {table}.listing_id)
                end as product_id
                """
            )
        else:
            select_exprs.append(c)
    select_sql = ", ".join(select_exprs)
    exec_params: list[Any] = []
    if table in {"price_observations", "daily_listing_prices"} and "product_id" in cols:
        exec_params.append(list(product_ids))
    exec_params.extend(params)
    with src.cursor() as cur:
        cur.execute(f"select {select_sql} from {table} where {where}", exec_params)
        rows = cur.fetchall()
    if not rows:
        return 0

    placeholders = ", ".join(["%s"] * len(cols))
    insert_sql = f"insert into {table} ({col_sql}) values ({placeholders})"
    adapted: list[tuple[Any, ...]] = [tuple(_adapt(v) for v in row) for row in rows]
    with dst.cursor() as cur:
        cur.executemany(insert_sql, adapted)
    return len(rows)


def _listing_ids(conn: psycopg.Connection, product_ids: Sequence[Any]) -> list[Any]:
    with conn.cursor() as cur:
        cur.execute(
            "select id from platform_listings where product_id = any(%s)",
            (list(product_ids),),
        )
        return [r[0] for r in cur.fetchall()]


def _ensure_target_platform_check(dst: psycopg.Connection) -> None:
    """Widen platform_listings.platform check so Vijay Sales / Poorvika rows can import."""
    with dst.cursor() as cur:
        cur.execute(
            """
            alter table platform_listings drop constraint if exists platform_listings_platform_check;
            alter table platform_listings add constraint platform_listings_platform_check check (
              platform in (
                'amazon','flipkart','croma','reliancedigital',
                'vijaysales','jiomart','poorvika','bajajelectronics'
              )
            );
            """
        )
        for table, col in (
            ("price_observations", "platform"),
            ("daily_listing_prices", "platform"),
            ("daily_product_platform_prices", "platform"),
            ("scrape_tasks", "platform"),
        ):
            if not _table_exists(dst, table):
                continue
            cur.execute(
                f"""
                do $$
                begin
                  if exists (
                    select 1 from pg_constraint
                    where conrelid = '{table}'::regclass
                      and conname = '{table}_{col}_check'
                  ) then
                    execute 'alter table {table} drop constraint {table}_{col}_check';
                    execute 'alter table {table} add constraint {table}_{col}_check check (
                      {col} in (
                        ''amazon'',''flipkart'',''croma'',''reliancedigital'',
                        ''vijaysales'',''jiomart'',''poorvika'',''bajajelectronics''
                      )
                    )';
                  end if;
                end $$;
                """
            )


def _truncate_catalog(dst: psycopg.Connection) -> list[str]:
    cleared: list[str] = []
    with dst.cursor() as cur:
        for table in TRUNCATE_ORDER:
            if not _table_exists(dst, table):
                continue
            if table in EXCLUDED_TABLES and table not in {
                "scrape_tasks",
                "review_queue",
                "search_document_dirty",
                "product_merge_log",
                "live_verification_events",
                "watch_events",
                "user_wishlist",
                "price_alerts",
            }:
                continue
            try:
                cur.execute(f"truncate table {table} restart identity cascade")
                cleared.append(table)
            except Exception as exc:  # noqa: BLE001 — report and continue for optional ops tables
                print(f"truncate_skip table={table} err={exc}", file=sys.stderr)
    return cleared


def _target_counts(conn: psycopg.Connection) -> dict[str, Any]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select lower(coalesce(category,'')) as cat, count(*)::int as n
            from product_clusters group by 1 order by n desc
            """
        )
        by_cat = {r["cat"]: r["n"] for r in cur.fetchall()}
        cur.execute(
            """
            select lower(coalesce(platform,'')) as p, count(*)::int as n
            from platform_listings group by 1 order by n desc
            """
        )
        by_plat = {r["p"]: r["n"] for r in cur.fetchall()}
        cur.execute(
            """
            select lower(coalesce(category,'')) as cat, count(*)::int as n
            from product_search_documents where best_price > 0
            group by 1 order by n desc
            """
        )
        priced = {r["cat"]: r["n"] for r in cur.fetchall()}
        cur.execute("select count(*)::int as n from users")
        users = cur.fetchone()["n"]
    return {
        "clusters_by_category": by_cat,
        "listings_by_platform": by_plat,
        "priced_docs_by_category": priced,
        "users_unchanged": users,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-url",
        default=os.getenv(
            "MAYABU_CATALOG_SOURCE_URL",
            "postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu_test",
        ),
    )
    parser.add_argument(
        "--target-url",
        default=os.getenv(
            "MAYABU_CATALOG_TARGET_URL",
            "postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu",
        ),
    )
    parser.add_argument("--apply", action="store_true", help="Write to target (default: dry-run)")
    args = parser.parse_args(list(argv) if argv is not None else None)

    src_db = (urlparse(args.source_url).path or "").lstrip("/")
    dst_db = (urlparse(args.target_url).path or "").lstrip("/")
    if src_db == dst_db:
        print("source and target must differ", file=sys.stderr)
        return 2
    if dst_db == "mayabu_test":
        print("refusing to write into mayabu_test (test DB only)", file=sys.stderr)
        return 2

    with psycopg.connect(args.source_url) as src:
        classification = _classify(src)
        product_ids = classification.pop("eligible_ids")
        listing_ids = _listing_ids(src, product_ids)

        report = {
            "mode": "apply" if args.apply else "dry-run",
            "source": src_db,
            "target": dst_db,
            "classification": classification,
            "listing_ids": len(listing_ids),
        }

        if not args.apply:
            print(json.dumps(report, indent=2, default=str))
            print("dry-run only; re-run with --apply to import")
            return 0

        with psycopg.connect(args.target_url) as dst:
            dst.execute("select pg_advisory_lock(%s)", (872341,))
            try:
                try:
                    _ensure_target_platform_check(dst)
                    cleared = _truncate_catalog(dst)
                    copied: dict[str, int] = {}
                    for table in CATALOG_COPY_ORDER:
                        n = _copy_filtered(
                            src,
                            dst,
                            table,
                            product_ids=product_ids,
                            listing_ids=listing_ids,
                        )
                        copied[table] = n
                        print(f"copied {table}={n}")
                    dst.commit()
                except Exception:
                    dst.rollback()
                    raise
            finally:
                try:
                    dst.execute("select pg_advisory_unlock(%s)", (872341,))
                    dst.commit()
                except Exception:  # noqa: BLE001
                    dst.rollback()

            report["truncated"] = cleared
            report["copied"] = copied
            report["target_after"] = _target_counts(dst)

    print(json.dumps(report, indent=2, default=str))
    print("import_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
