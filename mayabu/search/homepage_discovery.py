"""Bounded homepage discovery queries for Mayabu public homepage."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from mayabu.api.serializers import serialize_search_result
from mayabu.db.connection import db_connection
from mayabu.platforms.coverage import public_offer_allowed
from mayabu.search.cache import get_cache
from mayabu.search.category_registry import public_search_categories
from mayabu.search.product_activity import popular_product_ids, trending_product_ids

# Nested db_connection/cursor with-blocks match the rest of the Mayabu data layer.
# ruff: noqa: SIM117

logger = logging.getLogger(__name__)

HOMEPAGE_CACHE_KEY = "homepage:discovery:v5"
HOMEPAGE_CACHE_TTL_SECONDS = 90
SECTION_LIMIT = 8
PRICE_DROP_WINDOW_DAYS = 30
PRICE_DROP_MIN_PERCENT = 2
PRICE_DROP_MIN_AMOUNT = 100.0
DISCOUNT_MIN_PERCENT = 5
MULTI_STORE_PREFERRED_MIN = 3
MULTI_STORE_FALLBACK_MIN = 2
DEDUPE_SOFT_MIN = 3
LOWEST_MIN_OBSERVATIONS = 2
LOWEST_MIN_DISTINCT_DAYS = 2
NEAR_LOW_PERCENT = 5.0
# Align with Price Intelligence evidence depth — hide section when supply is thin.
NEAR_LOW_MIN_OBS = 7
NEAR_LOW_MIN_DAYS = 14
EXPLORE_PER_CATEGORY = 4
SPOTLIGHT_PRODUCTS = 6
# Prefer non-laptop spotlights first; laptop allowed when supply is thin.
SPOTLIGHT_CATEGORY_ORDER = (
    "smartphone",
    "television",
    "headphones",
    "tws",
    "camera",
    "washing_machine",
    "refrigerator",
    "laptop",
)


def _resolve_categories(categories: Sequence[str] | None = None) -> list[str]:
    if categories:
        return [str(c) for c in categories if c]
    return list(public_search_categories())


def _row_as_product(row: dict[str, Any], *, extras: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = serialize_search_result(
        {
            "product_id": row.get("product_id") or row.get("id"),
            "canonical_title": row.get("canonical_title") or row.get("title"),
            "brand": row.get("brand"),
            "category": row.get("category"),
            "specs": row.get("specs") or {},
            "family": row.get("family"),
            "best_price": row.get("best_price") or row.get("current_price"),
            "best_platform": row.get("best_platform"),
            "platform_count": row.get("platform_count") or 0,
            "offer_count": row.get("offer_count") or row.get("platform_count") or 0,
            "image_url": row.get("image_url"),
            "last_seen_at": row.get("last_seen_at"),
            "match_group": "related_product",
            "rank_score": None,
            "variant_group_id": row.get("variant_group_id"),
        }
    )
    if extras:
        payload.update(extras)
    return payload


def _fetch_documents_by_ids(
    product_ids: list[str],
    *,
    categories: Sequence[str] | None = None,
) -> dict[str, dict[str, Any]]:
    if not product_ids:
        return {}
    categories = _resolve_categories(categories)
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                select product_id, brand, category, canonical_title, specs, family,
                       best_price, best_platform, platform_count, offer_count,
                       image_url, last_seen_at, variant_group_id
                from product_search_documents
                where product_id = any(%s::uuid[])
                  and category = any(%s)
                  and best_price is not null
                  and best_price > 0
                """,
            (product_ids, categories),
        )
        rows = [dict(r) for r in cur.fetchall()]
    return {str(row["product_id"]): row for row in rows}


def _ordered_products_from_ids(
    product_ids: list[str],
    *,
    limit: int,
    badge: str | None = None,
    categories: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    docs = _fetch_documents_by_ids(product_ids, categories=categories)
    out: list[dict[str, Any]] = []
    for pid in product_ids:
        row = docs.get(pid)
        if not row:
            continue
        extras = {"activity_badge": badge} if badge else None
        out.append(_row_as_product(row, extras=extras))
        if len(out) >= limit:
            break
    return out


def _fetch_recently_checked(
    limit: int,
    *,
    categories: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    categories = _resolve_categories(categories)
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select product_id, brand, category, canonical_title, specs, family,
                       best_price, best_platform, platform_count, offer_count,
                       image_url, last_seen_at, variant_group_id
                from product_search_documents
                where category = any(%s)
                  and best_price is not null
                  and best_price > 0
                  and last_seen_at is not null
                order by last_seen_at desc nulls last, platform_count desc, product_id asc
                limit %s
                """,
                (categories, limit * 3),
            )
            rows = [dict(r) for r in cur.fetchall()]
    return _diverse_pick(rows, limit)


def _fetch_multi_store(
    limit: int,
    *,
    categories: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Products with multiple public production offers (prefer ≥3 stores)."""
    categories = _resolve_categories(categories)
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select product_id, brand, category, canonical_title, specs, family,
                       best_price, best_platform, platform_count, offer_count,
                       image_url, last_seen_at, variant_group_id
                from product_search_documents
                where category = any(%s)
                  and best_price is not null
                  and best_price > 0
                  and coalesce(platform_count, 0) >= %s
                order by platform_count desc, last_seen_at desc nulls last, product_id asc
                limit %s
                """,
                (categories, MULTI_STORE_PREFERRED_MIN, limit * 4),
            )
            preferred = [dict(r) for r in cur.fetchall()]
            if len(preferred) < limit:
                cur.execute(
                    """
                    select product_id, brand, category, canonical_title, specs, family,
                           best_price, best_platform, platform_count, offer_count,
                           image_url, last_seen_at, variant_group_id
                    from product_search_documents
                    where category = any(%s)
                      and best_price is not null
                      and best_price > 0
                      and coalesce(platform_count, 0) >= %s
                    order by platform_count desc, last_seen_at desc nulls last, product_id asc
                    limit %s
                    """,
                    (categories, MULTI_STORE_FALLBACK_MIN, limit * 4),
                )
                preferred = [dict(r) for r in cur.fetchall()]
    return _diverse_pick(preferred, limit)


def _fetch_price_drops(
    limit: int,
    *,
    categories: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    categories = _resolve_categories(categories)
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select d.product_id, d.brand, d.category, d.canonical_title, d.specs, d.family,
                       d.best_platform, d.platform_count, d.offer_count, d.image_url,
                       d.last_seen_at, d.variant_group_id,
                       curr.best_price as current_price,
                       curr.date as current_date,
                       prev.best_price as previous_price,
                       prev.date as previous_date
                from product_search_documents d
                join lateral (
                  select best_price, date
                  from daily_product_prices
                  where product_id = d.product_id
                    and best_price is not null
                    and best_price > 0
                  order by date desc
                  limit 1
                ) curr on true
                join lateral (
                  select best_price, date
                  from daily_product_prices
                  where product_id = d.product_id
                    and best_price is not null
                    and best_price > 0
                    and date < curr.date
                    and date >= current_date - (%s::int * interval '1 day')
                  order by date desc
                  limit 1
                ) prev on true
                where d.category = any(%s)
                  and curr.best_price < prev.best_price
                order by ((prev.best_price - curr.best_price) / prev.best_price) desc,
                         (prev.best_price - curr.best_price) desc,
                         d.product_id asc
                limit %s
                """,
                (PRICE_DROP_WINDOW_DAYS, categories, limit * 2),
            )
            rows = [dict(r) for r in cur.fetchall()]

    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            current = float(row["current_price"])
            previous = float(row["previous_price"])
        except (TypeError, ValueError, KeyError):
            continue
        if previous <= 0 or current >= previous:
            continue
        drop_amount = previous - current
        drop_percent = round((drop_amount / previous) * 100)
        if drop_percent < PRICE_DROP_MIN_PERCENT and drop_amount < PRICE_DROP_MIN_AMOUNT:
            continue
        product = _row_as_product(
            {**row, "best_price": current},
            extras={
                "previous_price": previous,
                "drop_amount": drop_amount,
                "drop_percent": drop_percent,
                "drop_window_days": PRICE_DROP_WINDOW_DAYS,
            },
        )
        out.append(product)
        if len(out) >= limit * 3:
            break
    return _serialize_diverse(out, limit)


def _fetch_biggest_discounts(
    limit: int,
    *,
    categories: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    categories = _resolve_categories(categories)
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select d.product_id, d.brand, d.category, d.canonical_title, d.specs, d.family,
                       d.best_platform, d.platform_count, d.offer_count, d.image_url,
                       d.last_seen_at, d.variant_group_id,
                       l.platform, l.current_price, l.current_mrp, l.current_discount_pct
                from product_search_documents d
                join platform_listings l
                  on l.product_id = d.product_id
                 and l.match_status = 'matched'
                where d.category = any(%s)
                  and l.current_price is not null
                  and l.current_mrp is not null
                  and l.current_price > 0
                  and l.current_mrp > l.current_price
                order by ((l.current_mrp - l.current_price) / l.current_mrp) desc,
                         (l.current_mrp - l.current_price) desc,
                         d.product_id asc
                limit %s
                """,
                (categories, limit * 6),
            )
            rows = [dict(r) for r in cur.fetchall()]

    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        product_id = str(row.get("product_id") or "")
        if not product_id or product_id in seen:
            continue
        category = str(row.get("category") or "")
        platform = str(row.get("platform") or "")
        if not public_offer_allowed(platform, category):
            continue
        try:
            price = float(row["current_price"])
            mrp = float(row["current_mrp"])
        except (TypeError, ValueError, KeyError):
            continue
        if mrp <= price or price <= 0:
            continue
        discount_percent = round(((mrp - price) / mrp) * 100)
        if discount_percent < DISCOUNT_MIN_PERCENT or discount_percent >= 90:
            continue
        seen.add(product_id)
        out.append(
            _row_as_product(
                {**row, "best_price": price, "best_platform": platform},
                extras={
                    "mrp": mrp,
                    "discount_percent": discount_percent,
                    "discount_amount": mrp - price,
                },
            )
        )
        if len(out) >= limit * 3:
            break
    return _serialize_diverse(out, limit)


def _fetch_lowest_since_tracking(
    limit: int,
    *,
    categories: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Current best price at/below Mayabu's tracked historical minimum (not market all-time)."""
    categories = _resolve_categories(categories)
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select d.product_id, d.brand, d.category, d.canonical_title, d.specs, d.family,
                       d.best_platform, d.platform_count, d.offer_count, d.image_url,
                       d.last_seen_at, d.variant_group_id,
                       d.best_price as current_price,
                       hist.min_price as tracked_low,
                       hist.obs_count,
                       hist.day_count
                from product_search_documents d
                join lateral (
                  select min(best_price) as min_price,
                         count(*)::int as obs_count,
                         count(distinct date)::int as day_count
                  from daily_product_prices
                  where product_id = d.product_id
                    and best_price is not null
                    and best_price > 0
                ) hist on true
                where d.category = any(%s)
                  and d.best_price is not null
                  and d.best_price > 0
                  and hist.obs_count >= %s
                  and hist.day_count >= %s
                  and d.best_price <= hist.min_price
                order by hist.day_count desc, d.last_seen_at desc nulls last, d.product_id asc
                limit %s
                """,
                (categories, LOWEST_MIN_OBSERVATIONS, LOWEST_MIN_DISTINCT_DAYS, limit * 2),
            )
            rows = [dict(r) for r in cur.fetchall()]

    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            current = float(row["current_price"])
            tracked_low = float(row["tracked_low"])
        except (TypeError, ValueError, KeyError):
            continue
        if current <= 0 or current > tracked_low:
            continue
        out.append(
            _row_as_product(
                {**row, "best_price": current},
                extras={
                    "tracked_low_price": tracked_low,
                    "is_lowest_since_tracking": True,
                    "tracking_observation_count": int(row.get("obs_count") or 0),
                    "tracking_day_count": int(row.get("day_count") or 0),
                },
            )
        )
        if len(out) >= limit * 3:
            break
    return _serialize_diverse(out, limit)


def fetch_category_documents(category: str, *, limit: int = 120) -> list[dict[str, Any]]:
    """Bounded raw search documents for one public category (facets + browse)."""
    categories = _resolve_categories([category])
    limit = max(1, min(int(limit), 200))
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select product_id, brand, category, canonical_title, specs, family,
                   best_price, best_platform, platform_count, offer_count,
                   image_url, last_seen_at, variant_group_id
            from product_search_documents
            where category = any(%s)
              and best_price is not null
              and best_price > 0
            order by last_seen_at desc nulls last, platform_count desc, product_id asc
            limit %s
            """,
            (categories, limit),
        )
        return [dict(r) for r in cur.fetchall()]


def _fetch_near_tracked_low(
    limit: int,
    *,
    categories: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Current price within NEAR_LOW_PERCENT of tracked minimum (not at/below it)."""
    categories = _resolve_categories(categories)
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select d.product_id, d.brand, d.category, d.canonical_title, d.specs, d.family,
                       d.best_platform, d.platform_count, d.offer_count, d.image_url,
                       d.last_seen_at, d.variant_group_id,
                       d.best_price as current_price,
                       hist.min_price as tracked_low,
                       hist.obs_count,
                       hist.day_count
                from product_search_documents d
                join lateral (
                  select min(best_price) as min_price,
                         count(*)::int as obs_count,
                         count(distinct date)::int as day_count
                  from daily_product_prices
                  where product_id = d.product_id
                    and best_price is not null
                    and best_price > 0
                ) hist on true
                where d.category = any(%s)
                  and d.best_price is not null
                  and d.best_price > 0
                  and hist.obs_count >= %s
                  and hist.day_count >= %s
                  and hist.min_price > 0
                  and d.best_price > hist.min_price
                  and d.best_price <= hist.min_price * (1 + %s::numeric / 100.0)
                order by ((d.best_price - hist.min_price) / hist.min_price) asc,
                         d.last_seen_at desc nulls last, d.product_id asc
                limit %s
                """,
                (
                    categories,
                    NEAR_LOW_MIN_OBS,
                    NEAR_LOW_MIN_DAYS,
                    NEAR_LOW_PERCENT,
                    limit * 4,
                ),
            )
            rows = [dict(r) for r in cur.fetchall()]

    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            current = float(row["current_price"])
            tracked_low = float(row["tracked_low"])
        except (TypeError, ValueError, KeyError):
            continue
        if current <= 0 or tracked_low <= 0 or current <= tracked_low:
            continue
        gap_pct = round(((current - tracked_low) / tracked_low) * 100, 1)
        out.append(
            _row_as_product(
                {**row, "best_price": current},
                extras={
                    "tracked_low_price": tracked_low,
                    "near_tracked_low": True,
                    "near_low_gap_percent": gap_pct,
                    "tracking_observation_count": int(row.get("obs_count") or 0),
                    "tracking_day_count": int(row.get("day_count") or 0),
                },
            )
        )
        if len(out) >= limit * 3:
            break
    return _serialize_diverse(out, limit)


def _fetch_explore_by_category(
    *,
    per_category: int = EXPLORE_PER_CATEGORY,
    categories: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """One group per public category with a small real product sample."""
    categories = _resolve_categories(categories)
    from mayabu.search.category_registry import validate_public_category

    counts: dict[str, int] = {}
    if categories:
        with db_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select category, count(*)::int as n
                from product_search_documents
                where category = any(%s)
                  and best_price is not null
                  and best_price > 0
                group by category
                """,
                (list(categories),),
            )
            counts = {str(r["category"]): int(r["n"]) for r in cur.fetchall()}

    groups: list[dict[str, Any]] = []
    for slug in categories:
        rows = fetch_category_documents(slug, limit=max(per_category * 2, 8))
        products = [_row_as_product(r) for r in rows[:per_category]]
        if not products:
            continue
        try:
            label = validate_public_category(slug).display_name
        except ValueError:
            label = slug.replace("_", " ").title()
        groups.append(
            {
                "slug": slug,
                "label": label,
                "product_count": counts.get(slug, len(products)),
                "products": products,
            }
        )
    return groups


def _fetch_category_spotlights(
    *,
    count: int = 2,
    products_each: int = SPOTLIGHT_PRODUCTS,
    categories: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Deterministic non-laptop-first category spotlights when supply allows."""
    from datetime import date

    available = _resolve_categories(categories)
    # Day-stable rotation across preferred order.
    day_seed = date.today().toordinal()
    ordered = [c for c in SPOTLIGHT_CATEGORY_ORDER if c in available]
    ordered += [c for c in available if c not in ordered]
    if not ordered:
        return []

    start = day_seed % len(ordered)
    rotated = ordered[start:] + ordered[:start]
    spotlights: list[dict[str, Any]] = []
    for slug in rotated:
        if len(spotlights) >= count:
            break
        # Prefer skipping laptop unless we cannot fill spotlights.
        if slug == "laptop" and len(spotlights) < count and len(rotated) > count:
            continue
        rows = fetch_category_documents(slug, limit=products_each * 2)
        products = [_row_as_product(r) for r in rows[:products_each]]
        if len(products) < 3:
            continue
        titles = {
            "smartphone": ("Smartphone picks to compare", "Current public prices across phone variants."),
            "television": ("TVs worth tracking", "Screen sizes and panels with live Mayabu prices."),
            "headphones": ("Audio prices to watch", "Headphones with recent public store prices."),
            "tws": ("TWS picks to compare", "Earbuds with current matched store prices."),
            "camera": ("Cameras to compare", "Body and kit configurations with public prices."),
            "washing_machine": ("Washers to compare", "Capacity and load types with live prices."),
            "refrigerator": ("Refrigerators to compare", "Capacity and door types with live prices."),
            "laptop": ("Laptops to compare", "Configurations with current public store prices."),
        }
        title, desc = titles.get(
            slug,
            (f"{slug.replace('_', ' ').title()} to compare", "Products with current public prices."),
        )
        spotlights.append(
            {
                "slug": slug,
                "title": title,
                "description": desc,
                "products": products,
            }
        )

    # Fallback: allow laptop if still short.
    if len(spotlights) < count and "laptop" in available:
        if not any(s["slug"] == "laptop" for s in spotlights):
            rows = fetch_category_documents("laptop", limit=products_each * 2)
            products = [_row_as_product(r) for r in rows[:products_each]]
            if len(products) >= 3:
                spotlights.append(
                    {
                        "slug": "laptop",
                        "title": "Laptops to compare",
                        "description": "Configurations with current public store prices.",
                        "products": products,
                    }
                )
    return spotlights[:count]


def _diverse_pick(
    rows: list[dict[str, Any]],
    limit: int,
    *,
    max_per_category: int | None = None,
    already_serialized: bool = False,
) -> list[dict[str, Any]]:
    """Category-aware selection: round-robin with a soft per-category cap.

    Preserves relative order within each category (semantic ranking already applied).
    Relaxes the cap only when remaining supply cannot fill ``limit``.
    """
    if limit <= 0:
        return []
    if max_per_category is None:
        # ~2–3 per category for typical 8–12 rails.
        max_per_category = max(2, min(3, (limit + 2) // 3))

    by_category: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        cat = str(row.get("category") or "other")
        by_category.setdefault(cat, []).append(row)

    picked: list[dict[str, Any]] = []
    seen: set[str] = set()
    per_cat: dict[str, int] = {}

    def _pid(row: dict[str, Any]) -> str:
        return str(row.get("id") or row.get("product_id") or "")

    def _emit(row: dict[str, Any]) -> dict[str, Any]:
        return row if already_serialized else _row_as_product(row)

    # Pass 1: round-robin respecting cap.
    while len(picked) < limit:
        progressed = False
        for cat in sorted(by_category.keys()):
            if per_cat.get(cat, 0) >= max_per_category:
                continue
            bucket = by_category[cat]
            while bucket:
                row = bucket.pop(0)
                pid = _pid(row)
                if not pid or pid in seen:
                    continue
                seen.add(pid)
                per_cat[cat] = per_cat.get(cat, 0) + 1
                picked.append(_emit(row))
                progressed = True
                break
            if len(picked) >= limit:
                break
        if not progressed:
            break

    # Pass 2: fill remaining slots ignoring cap (insufficient supply fallback).
    if len(picked) < limit:
        leftovers: list[dict[str, Any]] = []
        for cat in sorted(by_category.keys()):
            leftovers.extend(by_category[cat])
        for row in leftovers:
            if len(picked) >= limit:
                break
            pid = _pid(row)
            if not pid or pid in seen:
                continue
            seen.add(pid)
            picked.append(_emit(row))
    return picked


def _serialize_diverse(products: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Apply diversity to already-serialized product payloads."""
    return _diverse_pick(products, limit, already_serialized=True)


def _dedupe_priority(
    sections: list[tuple[str, list[dict[str, Any]]]],
    *,
    soft_min: int = DEDUPE_SOFT_MIN,
) -> dict[str, list[dict[str, Any]]]:
    """Prefer unique products by section priority; soft-reuse when a section would go empty/thin."""
    used: set[str] = set()
    cleaned: dict[str, list[dict[str, Any]]] = {}
    for name, items in sections:
        unique: list[dict[str, Any]] = []
        reused: list[dict[str, Any]] = []
        for item in items:
            pid = str(item.get("id") or "")
            if not pid:
                continue
            if pid in used:
                reused.append(item)
                continue
            used.add(pid)
            unique.append(item)
        if len(unique) < soft_min and reused:
            needed = soft_min - len(unique)
            for item in reused[:needed]:
                unique.append(item)
        cleaned[name] = unique
    return cleaned


def build_homepage_discovery(*, limit: int = SECTION_LIMIT) -> dict[str, Any]:
    limit = max(1, min(int(limit), 12))

    trending_ids = trending_product_ids(limit=limit * 2)
    popular_ids = popular_product_ids(limit=limit * 2)
    trending = _ordered_products_from_ids(trending_ids, limit=limit, badge="Trending")
    popular = _ordered_products_from_ids(popular_ids, limit=limit, badge="Popular")

    # If both activity lists are thin or nearly identical, keep the stronger signal only.
    if trending and popular:
        trend_set = {str(p.get("id")) for p in trending}
        pop_set = {str(p.get("id")) for p in popular}
        overlap = len(trend_set & pop_set) / max(1, min(len(trend_set), len(pop_set)))
        if overlap >= 0.75 and len(trending) < 3:
            popular = []
        elif overlap >= 0.75 and len(popular) >= len(trending):
            # Prefer popular window when momentum cannot be separated cleanly.
            trending = []
            for item in popular:
                item["activity_badge"] = "Recently popular"

    discounts = _fetch_biggest_discounts(limit)
    lowest = _fetch_lowest_since_tracking(limit)
    drops = _fetch_price_drops(limit)
    recently = _fetch_recently_checked(limit)
    multi_store = _fetch_multi_store(limit)
    near_low = _fetch_near_tracked_low(limit)
    trending = _serialize_diverse(trending, limit)
    popular = _serialize_diverse(popular, limit)

    cleaned = _dedupe_priority(
        [
            ("trending", trending),
            ("near_tracked_low", near_low),
            ("lowest_since_tracking", lowest),
            ("biggest_discounts", discounts),
            ("multi_store", multi_store),
            ("popular", popular),
            ("price_drops", drops),
            ("recently_checked", recently),
        ]
    )

    trending = cleaned["trending"]
    near_low = cleaned["near_tracked_low"]
    lowest = cleaned["lowest_since_tracking"]
    discounts = cleaned["biggest_discounts"]
    multi_store = cleaned["multi_store"]
    popular = cleaned["popular"]
    drops = cleaned["price_drops"]
    recently = cleaned["recently_checked"]

    explore = _fetch_explore_by_category()
    spotlights = _fetch_category_spotlights(count=4)

    featured_pool: list[dict[str, Any]] = []
    featured_ids: set[str] = set()
    for bucket in (trending, near_low, lowest, discounts, multi_store, popular, drops, recently):
        for item in bucket:
            pid = str(item.get("id") or "")
            if not pid or pid in featured_ids:
                continue
            featured_ids.add(pid)
            featured_pool.append(item)
            if len(featured_pool) >= max(6, limit):
                break
        if len(featured_pool) >= max(6, limit):
            break

    featured = featured_pool[: max(5, min(6, limit))]

    trending_semantics: str | None = None
    trending_note: str | None = None
    if trending:
        trending_semantics = (
            "Products with rising Mayabu engagement in the last 48 hours "
            "relative to the prior 48 hours (minimum activity threshold)."
        )
    else:
        trending_note = (
            "Trending is hidden until enough recent product engagement is recorded. "
            "Mayabu does not fabricate popularity."
        )

    popular_semantics: str | None = None
    if popular:
        label = popular[0].get("activity_badge") or "Popular"
        if label == "Recently popular":
            popular_semantics = (
                "Higher aggregate Mayabu engagement over the last 7 days "
                "(shown when trending momentum cannot be separated cleanly)."
            )
        else:
            popular_semantics = (
                "Higher aggregate Mayabu engagement over the last 7 days "
                "(minimum activity threshold)."
            )

    return {
        "trending": trending[:limit],
        "popular": popular[:limit],
        "biggest_discounts": discounts[:limit],
        "lowest_since_tracking": lowest[:limit],
        "near_tracked_low": near_low[:limit],
        "price_drops": drops[:limit],
        "recently_checked": recently[:limit],
        "multi_store": multi_store[:limit],
        "explore_by_category": explore,
        "category_spotlights": spotlights,
        "featured": featured,
        "categories": list(public_search_categories()),
        "stores": [],
        "semantics": {
            "trending": trending_semantics,
            "trending_note": trending_note,
            "popular": popular_semantics,
            "biggest_discounts": (
                f"Validated public listing MRP above current selling price "
                f"(minimum {DISCOUNT_MIN_PERCENT}% off). Bank/coupon/exchange offers excluded."
            ),
            "lowest_since_tracking": (
                "Current best price at or below Mayabu's minimum tracked daily best price "
                f"with at least {LOWEST_MIN_OBSERVATIONS} observations across "
                f"{LOWEST_MIN_DISTINCT_DAYS}+ dates. Not a market all-time-low claim."
            ),
            "near_tracked_low": (
                f"Current best price within {NEAR_LOW_PERCENT:g}% above Mayabu's tracked "
                f"minimum, with at least {NEAR_LOW_MIN_OBS} observations across "
                f"{NEAR_LOW_MIN_DAYS}+ dates. Not a market low claim."
            ),
            "price_drops": (
                f"Current best price lower than a prior daily observation within "
                f"{PRICE_DROP_WINDOW_DAYS} days "
                f"(≥{PRICE_DROP_MIN_PERCENT}% or ≥₹{int(PRICE_DROP_MIN_AMOUNT)}). "
                "Not an MRP comparison."
            ),
            "recently_checked": (
                "Products with a trustworthy public price and the most recent "
                "successful verification/observation timestamps."
            ),
            "multi_store": (
                f"Public eligible products with at least {MULTI_STORE_FALLBACK_MIN} "
                f"production store offers (prefer ≥{MULTI_STORE_PREFERRED_MIN}), "
                "ranked by offer coverage then freshness."
            ),
            "explore_by_category": (
                "Bounded samples from each public Mayabu category with a current public price."
            ),
            "category_spotlights": (
                "Deterministic category spotlights when enough eligible products exist. "
                "Laptop is not preferred when other categories have supply."
            ),
            "most_wishlisted": None,
            "most_wishlisted_note": (
                "Most Wishlisted stays hidden until aggregate wishlist volume "
                "is large enough to rank privately and meaningfully."
            ),
            "newly_tracked": None,
            "newly_tracked_note": (
                "Newly Tracked stays hidden until Mayabu can prove a reliable "
                "first-tracked timestamp per product (not manufacturer launch date)."
            ),
        },
    }


def get_homepage_discovery(*, limit: int = SECTION_LIMIT, use_cache: bool = True) -> dict[str, Any]:
    cache = get_cache()
    if use_cache:
        cached = cache.get_json(HOMEPAGE_CACHE_KEY)
        if isinstance(cached, dict) and "featured" in cached:
            return cached
    payload = build_homepage_discovery(limit=limit)
    if use_cache:
        cache.set_json(HOMEPAGE_CACHE_KEY, payload, HOMEPAGE_CACHE_TTL_SECONDS)
    return payload
