#!/usr/bin/env python3
"""Audit probable duplicate / suspect-merge canonical products (read-only by default).

Uses product_clusters (Mayabu canonical products) on PostgreSQL.

Usage:
  set MAYABU_TEST_DATABASE_URL=postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu_test
  python scripts/audit_product_matching.py --dry-run
  python scripts/audit_product_matching.py --category smartphone --dry-run

Never rematches production unless --apply is passed AND MAYABU_ALLOW_REMATCH=1.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from typing import Any

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _connect():
    import psycopg
    from psycopg.rows import dict_row

    url = os.getenv("MAYABU_TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("Set MAYABU_TEST_DATABASE_URL or DATABASE_URL")
    return psycopg.connect(url, row_factory=dict_row)


def catalog_stats(conn) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute("select count(*) as n from product_clusters where status = 'active'")
        products = cur.fetchone()["n"]
        cur.execute("select count(*) as n from platform_listings")
        listings = cur.fetchone()["n"]
        cur.execute(
            """
            select count(*) as n from (
              select product_id from platform_listings
               where product_id is not null
               group by product_id having count(*) > 1
            ) t
            """
        )
        multi = cur.fetchone()["n"]
        cur.execute(
            "select count(*) as n from product_clusters where status = 'needs_review'"
        )
        needs_review = cur.fetchone()["n"]
    return {
        "active_products": products,
        "platform_listings": listings,
        "multi_offer_products": multi,
        "needs_review_products": needs_review,
    }


def find_model_code_duplicates(conn, *, category: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    sql = """
      select p.category,
             p.brand,
             p.specs->'model_codes' as model_codes,
             array_agg(p.id order by p.id) as product_ids,
             array_agg(p.canonical_title order by p.id) as titles,
             array_agg(p.specs order by p.id) as specs_list,
             count(*) as n
        from product_clusters p
       where p.status = 'active'
         and p.specs ? 'model_codes'
         and jsonb_typeof(p.specs->'model_codes') = 'array'
         and jsonb_array_length(p.specs->'model_codes') > 0
    """
    params: list[Any] = []
    if category:
        sql += " and p.category = %s"
        params.append(category)
    sql += """
       group by p.category, p.brand, p.specs->'model_codes'
      having count(*) > 1
       order by count(*) desc
       limit %s
    """
    params.append(limit)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    from mayabu.domain.categories.base import is_weak_series_model_code
    from mayabu.domain.matching import assess_product_match

    out: list[dict[str, Any]] = []
    for row in rows:
        product_ids = list(row["product_ids"] or [])
        titles = list(row["titles"] or [])
        specs_list = list(row["specs_list"] or [])
        codes = row["model_codes"] or []
        only_weak = bool(codes) and all(is_weak_series_model_code(str(c)) for c in codes)

        # Assess first pair: true duplicates vs legitimate variants under current matcher.
        classification = "duplicate_model_code"
        relation = None
        if len(product_ids) >= 2:
            left = {
                "title": titles[0],
                "category": row["category"],
                "specs": {**(specs_list[0] or {}), "category": row["category"]},
            }
            right = {
                "title": titles[1],
                "category": row["category"],
                "specs": {**(specs_list[1] or {}), "category": row["category"]},
            }
            assessment = assess_product_match(left, right)
            relation = assessment.relation
            if assessment.relation in {"variant", "conflict", "related"} and not assessment.merge_allowed:
                classification = "model_code_variant_or_collision"
            elif assessment.relation == "exact" and assessment.merge_allowed:
                classification = "true_duplicate_candidate"

        if only_weak and classification != "true_duplicate_candidate":
            classification = "weak_series_model_code_collision"

        out.append(
            {
                "kind": classification,
                "category": row["category"],
                "brand": row["brand"],
                "model_codes": row["model_codes"],
                "product_ids": [str(x) for x in product_ids],
                "count": int(row["n"]),
                "relation": relation,
            }
        )
    return out


def find_suspect_variant_merges(conn, *, category: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    sql = """
      select p.id, p.category, p.brand, p.canonical_title, p.specs
        from product_clusters p
       where p.status = 'active'
    """
    params: list[Any] = []
    if category:
        sql += " and p.category = %s"
        params.append(category)
    sql += " order by p.updated_at desc nulls last limit %s"
    params.append(limit * 5)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        products = cur.fetchall()
        suspects = []
        for row in products:
            pid = row["id"]
            cur.execute(
                """
                select specs, title
                  from platform_listings
                 where product_id = %s
                 limit 40
                """,
                (pid,),
            )
            listing_rows = cur.fetchall()
            if len(listing_rows) < 2:
                continue
            listing_specs = [r["specs"] or {} for r in listing_rows]
            conflicts: dict[str, set[str]] = defaultdict(set)
            for key in (
                "storage_gb",
                "ram_gb",
                "screen_size_inch",
                "screen_inch",
                "capacity_l",
                "capacity_kg",
                "body_only",
                "kit_lens",
                "load_type",
            ):
                values = {
                    str(s.get(key)).lower()
                    for s in listing_specs
                    if isinstance(s, dict) and s.get(key) not in (None, "")
                }
                if len(values) > 1:
                    conflicts[key] = values
            if conflicts:
                suspects.append(
                    {
                        "kind": "suspect_merge",
                        "product_id": str(pid),
                        "category": row["category"],
                        "brand": row["brand"],
                        "title": row["canonical_title"],
                        "conflicts": {k: sorted(v) for k, v in conflicts.items()},
                    }
                )
            if len(suspects) >= limit:
                break
    return suspects


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Mayabu matching duplicates/suspect merges")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", action="store_true", help="Reserved; requires MAYABU_ALLOW_REMATCH=1")
    parser.add_argument("--category")
    parser.add_argument("--product-id")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--json-out")
    args = parser.parse_args()

    if args.apply and os.environ.get("MAYABU_ALLOW_REMATCH") != "1":
        print("Refusing --apply without MAYABU_ALLOW_REMATCH=1", file=sys.stderr)
        return 2

    report: dict[str, Any] = {
        "matching_version": 2,
        "dry_run": not args.apply,
        "category": args.category,
        "catalog": {},
        "duplicates": [],
        "suspect_merges": [],
        "repairs": [],
    }
    try:
        conn = _connect()
    except Exception as exc:
        print(json.dumps({"error": f"db_unavailable: {exc}"}))
        return 1

    try:
        report["catalog"] = catalog_stats(conn)
        report["duplicates"] = find_model_code_duplicates(
            conn, category=args.category, limit=args.limit
        )
        report["suspect_merges"] = find_suspect_variant_merges(
            conn, category=args.category, limit=args.limit
        )
        if args.product_id:
            report["suspect_merges"] = [
                s for s in report["suspect_merges"] if str(s.get("product_id")) == str(args.product_id)
            ]
            report["duplicates"] = [
                d
                for d in report["duplicates"]
                if str(args.product_id) in [str(x) for x in d.get("product_ids", [])]
            ]
        if args.apply:
            report["message"] = (
                "Apply reserved: review duplicates/suspects manually; "
                "use scripts/rematch_catalog.py with MAYABU_ALLOW_REMATCH=1"
            )
    finally:
        conn.close()

    text = json.dumps(report, indent=2, default=str)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(text)
    print(
        f"summary: products={report['catalog'].get('active_products')} "
        f"listings={report['catalog'].get('platform_listings')} "
        f"duplicates={len(report['duplicates'])} "
        f"suspect_merges={len(report['suspect_merges'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
