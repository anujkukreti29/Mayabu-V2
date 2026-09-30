"""Qualify multi-category search against a populated local/staging catalog."""

from __future__ import annotations

import json
import os
import time
from collections import Counter
from typing import Any

from mayabu.api.serializers import serialize_search_result
from mayabu.db.connection import db_connection
from mayabu.search.category_registry import public_search_categories
from mayabu.search.query_parser import parse_query
from mayabu.search.search_repository import (
    build_query_facets,
    reset_search_source_cache,
    search_products,
)


def _sample_model_codes(limit: int = 8) -> list[dict[str, Any]]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select category, brand, canonical_title,
                       coalesce(specs->'model_codes'->>0, '') as model_code,
                       best_price
                from product_search_documents
                where coalesce(specs->'model_codes'->>0, '') <> ''
                  and category = any(%s)
                order by platform_count desc nulls last, last_seen_at desc nulls last
                limit %s
                """,
                (list(public_search_categories()), limit),
            )
            return list(cur.fetchall())


def run_search(q: str, **kwargs: Any) -> dict[str, Any]:
    parsed = parse_query(q, **{k: v for k, v in kwargs.items() if k in {
        "explicit_category", "min_price", "max_price", "category_filters"
    }})
    t0 = time.perf_counter()
    rows = search_products(parsed, limit=kwargs.get("limit", 10), offset=0, sort=kwargs.get("sort", "relevance"))
    retrieve_ms = (time.perf_counter() - t0) * 1000
    t1 = time.perf_counter()
    facets, scope, sample = build_query_facets(parsed, sort=kwargs.get("sort", "relevance"))
    facet_ms = (time.perf_counter() - t1) * 1000
    t2 = time.perf_counter()
    payload = [serialize_search_result(r) for r in rows]
    ser_ms = (time.perf_counter() - t2) * 1000
    cats = Counter(str(r.get("category") or "") for r in rows)
    return {
        "query": q,
        "detected_category": parsed.detected_category,
        "search_mode": parsed.search_mode,
        "result_count": len(rows),
        "categories": dict(cats),
        "top_titles": [r.get("title") for r in payload[:3]],
        "top_categories": [r.get("category") for r in payload[:3]],
        "facet_scope": scope,
        "facet_keys": list(facets.keys()),
        "facet_sample_size": sample,
        "timing_ms": {
            "retrieve": round(retrieve_ms, 2),
            "facets": round(facet_ms, 2),
            "serialize": round(ser_ms, 2),
            "total": round(retrieve_ms + facet_ms + ser_ms, 2),
        },
    }


def identity_audit(limit: int = 40) -> dict[str, Any]:
    """Look for potential duplicate canonical titles within brand+family."""
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select category, brand, lower(coalesce(specs->>'family','')) as family,
                       count(*)::int as n,
                       array_agg(canonical_title order by canonical_title) as titles
                from product_clusters
                where status = 'active'
                  and category = any(%s)
                  and coalesce(specs->>'family','') <> ''
                group by 1,2,3
                having count(*) > 3
                order by n desc
                limit %s
                """,
                (list(public_search_categories()), limit),
            )
            heavy = list(cur.fetchall())
            cur.execute(
                """
                select count(*)::int as n from product_clusters
                where category in ('unknown','accessory')
                """
            )
            unknown_n = cur.fetchone()["n"]
            cur.execute(
                """
                select p.category,
                       avg(sub.c)::float as avg_offers,
                       count(*) filter (where sub.c >= 2)::int as multi_offer_products,
                       count(*)::int as products
                from product_clusters p
                join (
                  select product_id, count(*)::int as c
                  from platform_listings where match_status='matched'
                  group by product_id
                ) sub on sub.product_id = p.id
                where p.status='active' and p.category = any(%s)
                group by p.category
                order by p.category
                """,
                (list(public_search_categories()),),
            )
            offers = list(cur.fetchall())
    return {
        "heavy_family_groups": [
            {
                "category": r["category"],
                "brand": r["brand"],
                "family": r["family"],
                "count": r["n"],
                "sample_titles": (r["titles"] or [])[:4],
            }
            for r in heavy
        ],
        "unknown_or_accessory_products": unknown_n,
        "offer_stats": offers,
    }


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise SystemExit("DATABASE_URL required")
    reset_search_source_cache()
    models = _sample_model_codes()
    searches = [
        run_search("gaming laptop under 70000"),
        run_search("phone under 30000"),
        run_search("55 inch OLED TV"),
        run_search("LG refrigerator"),
        run_search("8kg front load washing machine"),
        run_search("ANC earbuds under 5000"),
        run_search("sony headphones"),
        run_search("Samsung"),
        run_search("Sony"),
        run_search("phone case for iphone"),
        run_search("TV stand"),
    ]
    for row in models[:5]:
        code = row["model_code"]
        if code:
            searches.append(run_search(code, explicit_category=row["category"]))

    # Sort / pagination smoke
    parsed = parse_query("samsung", explicit_category="smartphone")
    page1 = search_products(parsed, limit=5, offset=0, sort="price_asc")
    page2 = search_products(parsed, limit=5, offset=5, sort="price_asc")
    ids1 = {str(r["product_id"]) for r in page1}
    ids2 = {str(r["product_id"]) for r in page2}
    pagination = {
        "page1": len(page1),
        "page2": len(page2),
        "overlap": len(ids1 & ids2),
        "price_asc_monotonic": all(
            (page1[i].get("best_price") or 0) <= (page1[i + 1].get("best_price") or 10**12)
            for i in range(len(page1) - 1)
            if page1[i].get("best_price") is not None and page1[i + 1].get("best_price") is not None
        ),
    }

    report = {
        "model_code_samples": models,
        "searches": searches,
        "identity_audit": identity_audit(),
        "pagination": pagination,
        "public_categories": list(public_search_categories()),
    }
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
