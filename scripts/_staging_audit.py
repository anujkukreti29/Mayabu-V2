"""Local/staging DB audits: price history, EXPLAIN, cache keys, filters, idempotency sample."""
from __future__ import annotations

import json
import os
import time
from collections import Counter

from mayabu.api.search_routes import _cache_key
from mayabu.search.query_parser import parse_query
from mayabu.search.search_repository import (
    build_query_facets,
    search_products,
)
from mayabu_db.connection import db_connection


def price_history_audit() -> dict:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select count(*)::int as n from daily_product_platform_prices
                """
            )
            dppp = cur.fetchone()["n"]
            cur.execute("select count(*)::int as n from daily_product_prices")
            dpp = cur.fetchone()["n"]
            cur.execute(
                """
                select product_id, date, platform, min_price
                from daily_product_platform_prices
                order by date desc, platform
                limit 8
                """
            )
            samples = list(cur.fetchall())
            cur.execute(
                """
                select product_id, date, best_price, best_platform, platform_count
                from daily_product_prices
                order by date desc
                limit 5
                """
            )
            agg = list(cur.fetchall())
    return {
        "daily_product_platform_prices": dppp,
        "daily_product_prices": dpp,
        "platform_price_samples": samples,
        "aggregate_samples": agg,
    }


def explain_search() -> list[dict]:
    patterns = [
        ("laptop gaming", "laptop"),
        ("samsung galaxy", "smartphone"),
        ("55 inch tv", "television"),
        ("lg refrigerator", "refrigerator"),
        ("samsung", None),
    ]
    out = []
    with db_connection() as conn:
        with conn.cursor() as cur:
            for q, cat in patterns:
                # Approximate main document retrieval path
                sql = """
                explain (analyze, buffers, format json)
                select d.product_id, d.canonical_title, d.best_price, d.category
                from product_search_documents d
                where (%s::text is null or d.category = %s)
                  and (
                    d.search_text ilike '%%' || %s || '%%'
                    or d.canonical_title ilike '%%' || %s || '%%'
                    or d.brand ilike '%%' || %s || '%%'
                  )
                order by d.best_price asc nulls last
                limit 40
                """
                t0 = time.perf_counter()
                cur.execute(sql, (cat, cat, q, q, q))
                row = cur.fetchone()
                plan = row["QUERY PLAN"] if isinstance(row, dict) else row[0]
                ms = (time.perf_counter() - t0) * 1000
                node = plan[0]["Plan"] if isinstance(plan, list) else plan
                out.append(
                    {
                        "query": q,
                        "category": cat,
                        "elapsed_ms": round(ms, 2),
                        "node_type": node.get("Node Type"),
                        "total_cost": node.get("Total Cost"),
                        "actual_rows": node.get("Actual Rows"),
                        "shared_hit": node.get("Shared Hit Blocks"),
                        "shared_read": node.get("Shared Read Blocks"),
                        "plan_summary": _summarize_plan(node),
                    }
                )
    return out


def _summarize_plan(node: dict, depth: int = 0) -> list[str]:
    lines = [
        f"{'  '*depth}{node.get('Node Type')} rows={node.get('Actual Rows')} "
        f"cost={node.get('Total Cost')} "
        f"{node.get('Index Name') or node.get('Relation Name') or ''}"
    ]
    for child in node.get("Plans") or []:
        lines.extend(_summarize_plan(child, depth + 1))
    return lines[:12]


def filter_facet_audit() -> dict:
    cases = [
        ("smartphone", {"storage_gb": 256}, "samsung"),
        ("smartphone", {"storage_gb": [128, 256], "ram_gb": 8}, "phone"),
        ("television", {"screen_size_inch": 55}, "tv"),
        ("television", {"screen_size_inch": [55, 65], "brand": ["samsung", "lg"]}, "tv"),
        ("refrigerator", {"door_type": "double_door"}, "refrigerator"),
        ("washing_machine", {"load_type": "front_load"}, "washing machine"),
        ("tws", {"anc": True}, "earbuds"),
        ("headphones", {"connectivity": "wireless"}, "headphones"),
    ]
    results = []
    for cat, filters, q in cases:
        parsed = parse_query(q, explicit_category=cat, category_filters=filters)
        rows = search_products(parsed, limit=10, offset=0, sort="relevance")
        facets, scope, sample = build_query_facets(parsed)
        results.append(
            {
                "category": cat,
                "filters": filters,
                "result_count": len(rows),
                "facet_scope": scope,
                "facet_keys": list(facets.keys()),
                "facet_sample": sample,
                "top": [r.get("canonical_title") for r in rows[:2]],
            }
        )
    return {"cases": results}


def cache_key_audit() -> dict:
    keys = [
        _cache_key("samsung", 20, 0, category=None, sort="relevance", min_price=None, max_price=None, filters=None),
        _cache_key("samsung", 20, 0, category="smartphone", sort="relevance", min_price=None, max_price=None, filters=None),
        _cache_key("samsung", 20, 0, category="smartphone", sort="price_asc", min_price=None, max_price=None, filters=None),
        _cache_key("samsung", 20, 20, category="smartphone", sort="relevance", min_price=None, max_price=None, filters=None),
        _cache_key(
            "samsung",
            20,
            0,
            category="smartphone",
            sort="relevance",
            min_price=None,
            max_price=None,
            filters='{"storage_gb":["256"]}',
        ),
    ]
    return {
        "keys": keys,
        "unique": len(set(keys)),
        "all_v6": all(":v6:" in str(k) or str(k).startswith("search:v6:") for k in keys),
    }


def cross_category_balance() -> dict:
    out = {}
    for brand in ("Samsung", "Sony", "LG"):
        rows = search_products(parse_query(brand), limit=20, offset=0, sort="relevance")
        out[brand] = dict(Counter(str(r.get("category") or "") for r in rows))
    return out


def identity_samples() -> dict:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select category, brand, canonical_title,
                       specs->>'family' as family,
                       specs->>'ram_gb' as ram,
                       specs->>'storage_gb' as storage,
                       specs->>'screen_size_inches' as size,
                       specs->>'capacity_liters' as liters,
                       specs->>'capacity_kg' as kg
                from product_clusters
                where status='active' and category = any(%s)
                order by category, brand, canonical_title
                """,
                (
                    [
                        "smartphone",
                        "television",
                        "refrigerator",
                        "washing_machine",
                        "tws",
                        "headphones",
                    ],
                ),
            )
            rows = list(cur.fetchall())
    by_cat: dict[str, list] = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)
    samples = {k: v[:8] for k, v in by_cat.items()}
    # storage variant check for smartphones
    phone_keys = Counter()
    for r in by_cat.get("smartphone", []):
        phone_keys[(r.get("family") or "", r.get("storage") or "", r.get("ram") or "")] += 1
    return {
        "samples": samples,
        "smartphone_family_variant_keys": len(phone_keys),
        "smartphone_duplicate_variant_keys": sum(1 for v in phone_keys.values() if v > 1),
    }


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise SystemExit("DATABASE_URL required")
    report = {
        "price_history": price_history_audit(),
        "explain": explain_search(),
        "filters_facets": filter_facet_audit(),
        "cache_keys": cache_key_audit(),
        "cross_category": cross_category_balance(),
        "identity": identity_samples(),
    }
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
