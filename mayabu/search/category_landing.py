"""Bounded category landing discovery payloads (public categories only)."""

from __future__ import annotations

import logging
from typing import Any

from mayabu.search.cache import get_cache
from mayabu.search.category_registry import (
    SEARCH_CONTRACT_VERSION,
    get_search_category,
    public_search_categories,
    validate_public_category,
)
from mayabu.search.homepage_discovery import (
    LOWEST_MIN_DISTINCT_DAYS,
    LOWEST_MIN_OBSERVATIONS,
    PRICE_DROP_WINDOW_DAYS,
    _fetch_biggest_discounts,
    _fetch_lowest_since_tracking,
    _fetch_multi_store,
    _fetch_price_drops,
    _fetch_recently_checked,
    _ordered_products_from_ids,
    fetch_category_documents,
)
from mayabu.search.product_activity import popular_product_ids, trending_product_ids
from mayabu.search.search_repository import build_page_facets
from mayabu.db.connection import db_connection

logger = logging.getLogger(__name__)

CATEGORY_LANDING_CONTRACT = "v1"
CATEGORY_LANDING_CACHE_TTL_SECONDS = 90
PRODUCT_LIMIT = 18
SECTION_LIMIT = 6
FACET_SAMPLE_LIMIT = 120
# Discovery facets: smaller than full Search V2 — top values only.
DISCOVERY_FACET_VALUES = 8


def _cache_key(category: str) -> str:
    return (
        f"category:landing:{CATEGORY_LANDING_CONTRACT}:"
        f"{SEARCH_CONTRACT_VERSION}:{category}"
    )


def _merge_unique(buckets: list[list[dict[str, Any]]], *, limit: int) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for bucket in buckets:
        for item in bucket:
            pid = str(item.get("id") or "")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            out.append(item)
            if len(out) >= limit:
                return out
    return out


def _trim_facets(facets: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    trimmed: dict[str, list[dict[str, Any]]] = {}
    for key, values in facets.items():
        if not values:
            continue
        ranked = sorted(values, key=lambda item: (-int(item.get("count") or 0), str(item.get("value"))))
        trimmed[key] = ranked[:DISCOVERY_FACET_VALUES]
    return trimmed


def _public_product_count(category: str) -> int:
    """Count priced public search docs for a category (not a sample size)."""
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select count(*)::int as n
            from product_search_documents
            where category = %s
              and best_price is not null
              and best_price > 0
            """,
            (category,),
        )
        row = cur.fetchone()
        return int(row["n"] if row else 0)


def build_category_landing(
    category: str,
    *,
    product_limit: int = PRODUCT_LIMIT,
    section_limit: int = SECTION_LIMIT,
) -> dict[str, Any]:
    info = validate_public_category(category)
    slug = info.slug
    product_limit = max(6, min(int(product_limit), 24))
    section_limit = max(1, min(int(section_limit), 12))
    cats = [slug]

    recently = _fetch_recently_checked(product_limit, categories=cats)
    multi_store = _fetch_multi_store(max(section_limit, 8), categories=cats)
    products = _merge_unique([recently, multi_store], limit=product_limit)

    trending_ids = trending_product_ids(limit=section_limit * 3)
    popular_ids = popular_product_ids(limit=section_limit * 3)
    trending = _ordered_products_from_ids(
        trending_ids, limit=section_limit, badge="Trending", categories=cats
    )
    popular = _ordered_products_from_ids(
        popular_ids, limit=section_limit, badge="Popular", categories=cats
    )
    if trending and popular:
        trend_set = {str(p.get("id")) for p in trending}
        pop_set = {str(p.get("id")) for p in popular}
        overlap = len(trend_set & pop_set) / max(1, min(len(trend_set), len(pop_set)))
        if overlap >= 0.75:
            if len(trending) <= len(popular):
                trending = []
            else:
                popular = []

    discounts = _fetch_biggest_discounts(section_limit, categories=cats)
    lowest = _fetch_lowest_since_tracking(section_limit, categories=cats)
    drops = _fetch_price_drops(section_limit, categories=cats)

    featured = _merge_unique(
        [trending, discounts, lowest, popular, drops, multi_store, recently],
        limit=max(5, min(6, section_limit)),
    )

    raw_docs = fetch_category_documents(slug, limit=FACET_SAMPLE_LIMIT)
    facets = _trim_facets(build_page_facets(raw_docs, slug))
    product_count = _public_product_count(slug)

    related = [
        c
        for c in public_search_categories()
        if c != slug
    ][:6]

    return {
        "category": slug,
        "display_name": info.display_name,
        "product_count": product_count,
        "product_count_sample": len(raw_docs),
        "featured": featured,
        "products": products,
        "facets": facets,
        "facet_keys": [f.key for f in info.facet_defs if f.key != "best_price"],
        "price_drops": drops[:section_limit],
        "biggest_discounts": discounts[:section_limit],
        "lowest_since_tracking": lowest[:section_limit],
        "trending": trending[:section_limit],
        "popular": popular[:section_limit],
        "related_categories": related,
        "semantics": {
            "biggest_discounts": "Validated public listing MRP above current selling price.",
            "lowest_since_tracking": (
                "Current best price at or below Mayabu's minimum tracked daily best price "
                f"with at least {LOWEST_MIN_OBSERVATIONS} observations across "
                f"{LOWEST_MIN_DISTINCT_DAYS}+ dates. Not a market all-time-low claim."
            ),
            "price_drops": (
                f"Current best price lower than a prior daily observation within "
                f"{PRICE_DROP_WINDOW_DAYS} days. Not an MRP comparison."
            ),
            "featured": "Recently verified and multi-offer products with strong identity coverage.",
            "trending": (
                "Rising Mayabu engagement in the last 48 hours relative to the prior 48 hours."
                if trending
                else None
            ),
            "popular": (
                "Higher aggregate Mayabu engagement over the last 7 days."
                if popular
                else None
            ),
            "product_count": "Priced public products currently eligible in this category.",
        },
        "contract_version": CATEGORY_LANDING_CONTRACT,
        "search_contract_version": SEARCH_CONTRACT_VERSION,
    }


def get_category_landing(
    category: str,
    *,
    product_limit: int = PRODUCT_LIMIT,
    section_limit: int = SECTION_LIMIT,
    use_cache: bool = True,
) -> dict[str, Any]:
    info = validate_public_category(category)
    key = _cache_key(info.slug)
    cache = get_cache()
    if use_cache:
        cached = cache.get_json(key)
        if isinstance(cached, dict) and cached.get("category") == info.slug:
            return cached
    payload = build_category_landing(
        info.slug, product_limit=product_limit, section_limit=section_limit
    )
    if use_cache:
        cache.set_json(key, payload, CATEGORY_LANDING_CACHE_TTL_SECONDS)
    return payload


__all__ = [
    "CATEGORY_LANDING_CONTRACT",
    "build_category_landing",
    "get_category_landing",
    "get_search_category",
]
