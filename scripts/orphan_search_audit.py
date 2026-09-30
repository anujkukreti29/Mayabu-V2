"""Orphan / synthetic search-document audit (dry-run by default)."""

from __future__ import annotations

import argparse
import json
from typing import Any

from mayabu.db.connection import db_connection


def orphan_search_documents(*, category: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
    params: list[Any] = []
    cat = ""
    if category:
        cat = "and d.category = %s"
        params.append(category)
    params.append(max(1, min(int(limit), 5_000)))
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select d.product_id, d.category, d.canonical_title as title, d.best_price, d.image_url, d.platform_count
                from product_search_documents d
                where not exists (
                  select 1 from platform_listings pl
                  where pl.product_id = d.product_id and pl.match_status = 'matched'
                )
                {cat}
                order by d.category, d.canonical_title
                limit %s
                """,
                tuple(params),
            )
            return [dict(r) for r in cur.fetchall()]


def orphan_summary() -> dict[str, Any]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select d.category, count(*)::int as orphan_docs
                from product_search_documents d
                where not exists (
                  select 1 from platform_listings pl
                  where pl.product_id = d.product_id and pl.match_status = 'matched'
                )
                group by 1
                order by 1
                """
            )
            by_cat = [dict(r) for r in cur.fetchall()]
            cur.execute(
                """
                select count(*)::int as public_matched_products
                from (
                  select product_id from platform_listings
                  where match_status = 'matched' and product_id is not null
                  group by product_id
                ) t
                """
            )
            public = cur.fetchone() or {}
    return {"orphans_by_category": by_cat, **dict(public)}


def deactivate_orphan_search_docs(*, dry_run: bool = True, limit: int = 5000) -> dict[str, Any]:
    """Soft cleanup: delete orphan search docs only (keeps clusters)."""
    rows = orphan_search_documents(limit=limit)
    if dry_run:
        return {
            "dry_run": True,
            "would_delete": len(rows),
            "by_category": _count_by_category(rows),
            "sample": rows[:10],
        }
    ids = [str(r["product_id"]) for r in rows]
    deleted = 0
    with db_connection() as conn:
        with conn.cursor() as cur:
            for pid in ids:
                cur.execute(
                    "delete from product_search_documents where product_id = %s::uuid",
                    (pid,),
                )
                deleted += cur.rowcount or 0
    return {
        "dry_run": False,
        "deleted": deleted,
        "by_category": _count_by_category(rows),
        "retained_canonical_clusters": True,
    }


def _count_by_category(rows: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        cat = str(row.get("category") or "unknown")
        out[cat] = out.get(cat, 0) + 1
    return out



def main() -> None:
    parser = argparse.ArgumentParser(description="Audit orphan search documents")
    parser.add_argument("--apply", action="store_true", help="Delete orphan search docs")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--category")
    args = parser.parse_args()
    print(json.dumps(orphan_summary(), indent=2, default=str))
    if args.apply:
        print(json.dumps(deactivate_orphan_search_docs(dry_run=False, limit=args.limit), indent=2))
    else:
        sample = orphan_search_documents(category=args.category, limit=min(20, args.limit))
        print(json.dumps({"sample": sample}, indent=2, default=str))


if __name__ == "__main__":
    main()
