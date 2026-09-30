"""Public search API routes with category-aware retail search."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import time

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, status

from mayabu.api.client_identity import client_identifier
from mayabu.api.rate_limit import SlidingWindowLimiter
from mayabu.api.serializers import serialize_search_result
from mayabu.core.config import get_app_settings
from mayabu.core.security import hash_identifier, sanitize_query
from mayabu.monitoring import instrumentation as metrics
from mayabu.monitoring.singleflight import search_singleflight
from mayabu.search.cache import get_cache
from mayabu.search.category_registry import (
    SEARCH_CONTRACT_VERSION,
    public_search_categories,
    validate_public_category,
)
from mayabu.search.demand_signal import upsert_demand_cluster
from mayabu.search.query_classifier import classify_query
from mayabu.search.search_repository import (
    build_query_facets,
    category_counts,
    log_search_query,
    parse_filters_param,
    search_products,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["search"])
cache = get_cache()
_RATE_LIMITER = SlidingWindowLimiter("search")


def _encode_cursor(offset: int) -> str:
    payload = json.dumps({"offset": offset}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(cursor: str | None) -> int | None:
    if not cursor:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        offset = int(payload["offset"])
        if offset < 0 or offset > 5000:
            raise ValueError
        return offset
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid pagination cursor") from exc


def _cache_key(
    query: str,
    limit: int,
    offset: int,
    *,
    category: str | None,
    sort: str,
    min_price: int | None,
    max_price: int | None,
    filters: str | None,
) -> str:
    digest = hashlib.sha256(
        f"{SEARCH_CONTRACT_VERSION}|{query}|{limit}|{offset}|{category or 'all'}|"
        f"{sort}|{min_price}|{max_price}|{filters or ''}".encode()
    ).hexdigest()
    return f"search:{SEARCH_CONTRACT_VERSION}:{digest}"


_SECTION_BY_MATCH_GROUP = {
    "exact_match": "exact_matches",
    "similar_variant": "similar_variants",
    "related_product": "related_products",
}


def _result_sections(results: list[dict]) -> dict[str, list[dict]]:
    sections = {"exact_matches": [], "similar_variants": [], "related_products": []}
    for item in results:
        key = _SECTION_BY_MATCH_GROUP.get(
            item.get("match_group") or "related_product",
            "related_products",
        )
        sections[key].append(item)
    return sections


def _enforce_public_rate_limit(request: Request) -> None:
    settings = get_app_settings()
    if not settings.enable_redis_rate_limit:
        return
    decision = _RATE_LIMITER.allow(
        client_identifier(request),
        per_key_limit=settings.public_rate_limit_per_minute,
    )
    if decision != "allowed":
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many search requests. Please slow down.",
            headers={"Retry-After": "60"},
        )


def _record_search_analytics(
    parsed,
    result_count: int,
    top_id: str | None,
    confidence: float,
    ip_hash: str | None,
) -> None:
    try:
        log_search_query(parsed, result_count, top_id, confidence, ip_hash, None)
        upsert_demand_cluster(parsed, result_count, top_id)
    except Exception as exc:
        logger.warning(
            "search_analytics_failed",
            extra={"event": "search_analytics", "error": str(exc)[:500]},
        )


@router.get("/search")
def search(
    request: Request,
    background_tasks: BackgroundTasks,
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0, le=5000),
    cursor: str | None = Query(default=None),
    category: str | None = Query(default=None, max_length=40),
    sort: str = Query(default="relevance", max_length=20),
    min_price: int | None = Query(default=None, ge=0, le=10_000_000),
    max_price: int | None = Query(default=None, ge=0, le=10_000_000),
    filters: str | None = Query(default=None, max_length=1000),
) -> dict:
    _enforce_public_rate_limit(request)
    cursor_offset = _decode_cursor(cursor)
    effective_offset = cursor_offset if cursor_offset is not None else offset
    settings = get_app_settings()
    query = sanitize_query(q)

    if sort not in {"relevance", "price_asc", "price_desc", "recently_checked"}:
        raise HTTPException(
            status_code=400,
            detail="Invalid sort. Use relevance, price_asc, price_desc, or recently_checked.",
        )

    explicit_category = None
    if category:
        try:
            explicit_category = validate_public_category(category).slug
        except ValueError as exc:
            code = str(exc)
            if code == "invalid_category":
                raise HTTPException(status_code=400, detail="Invalid category.") from exc
            raise HTTPException(
                status_code=404,
                detail="Category is not available for public search.",
            ) from exc

    try:
        filter_map = parse_filters_param(filters, explicit_category)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid filters: {exc}") from exc

    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status_code=400, detail="min_price cannot exceed max_price.")

    total_started = time.perf_counter()
    with metrics.timer(metrics.SEARCH_PARSE, category=explicit_category or "auto", search_mode="pending"):
        parsed = classify_query(
            query,
            explicit_category=explicit_category,
            min_price=min_price,
            max_price=max_price,
            category_filters=filter_map,
        )
    category_label = parsed.detected_category or "cross"
    mode_label = parsed.search_mode or "unknown"
    ip_hash = hash_identifier(client_identifier(request))

    if not parsed.is_relevant:
        background_tasks.add_task(
            _record_search_analytics, parsed, 0, None, 0.0, ip_hash
        )
        message = "No searchable products for this query."
        if parsed.intent == "accessory":
            message = "That looks like an accessory search. Mayabu compares primary products."
        metrics.SEARCH_TOTAL.observe(
            (time.perf_counter() - total_started) * 1000,
            category=category_label,
            search_mode=mode_label,
            cache="skip",
        )
        return {
            "query": query,
            "normalized_query": parsed.normalized_query,
            "intent": parsed.intent,
            "detected_category": parsed.detected_category,
            "search_mode": parsed.search_mode,
            "public_categories": list(public_search_categories()),
            "search_contract_version": SEARCH_CONTRACT_VERSION,
            "result_count": 0,
            "limit": limit,
            "offset": effective_offset,
            "next_cursor": None,
            "has_more": False,
            "results": [],
            "sections": {
                "exact_matches": [],
                "similar_variants": [],
                "related_products": [],
            },
            "facets": {},
            "facet_scope": "query",
            "sort": sort,
            "message": message,
        }

    key = _cache_key(
        parsed.normalized_query,
        limit,
        effective_offset,
        category=parsed.detected_category,
        sort=sort,
        min_price=parsed.min_price,
        max_price=parsed.max_price,
        filters=filters,
    )
    try:
        cached = cache.get_json(key)
    except Exception:
        metrics.SEARCH_CACHE.inc(event="error")
        cached = None
    if cached is not None:
        metrics.SEARCH_CACHE.inc(event="hit")
        metrics.SEARCH_TOTAL.observe(
            (time.perf_counter() - total_started) * 1000,
            category=category_label,
            search_mode=mode_label,
            cache="hit",
        )
        return cached
    metrics.SEARCH_CACHE.inc(event="miss")

    def _build_response() -> dict:
        with metrics.timer(
            metrics.SEARCH_CANDIDATES, category=category_label, search_mode=mode_label
        ):
            raw_results = search_products(
                parsed, limit=limit + 1, offset=effective_offset, sort=sort
            )
        has_more = len(raw_results) > limit
        page_rows = raw_results[:limit]
        metrics.SEARCH_CANDIDATE_COUNT.observe(
            float(len(raw_results)), category=category_label, search_mode=mode_label
        )
        with metrics.timer(
            metrics.SEARCH_SERIALIZE, category=category_label, search_mode=mode_label
        ):
            public_results = [serialize_search_result(row) for row in page_rows]
            sections = _result_sections(public_results)
        with metrics.timer(
            metrics.SEARCH_FACETS, category=category_label, search_mode=mode_label
        ):
            facets, facet_scope, facet_sample_size = build_query_facets(parsed, sort=sort)
        counts = category_counts(page_rows)
        top_id = str(page_rows[0]["product_id"]) if page_rows else None
        confidence = float(page_rows[0].get("rank_score") or 0) if page_rows else 0.0
        background_tasks.add_task(
            _record_search_analytics,
            parsed,
            len(public_results),
            top_id,
            confidence,
            ip_hash,
        )
        metrics.SEARCH_RESULT_COUNT.observe(
            float(len(public_results)), category=category_label, search_mode=mode_label
        )
        return {
            "query": query,
            "normalized_query": parsed.normalized_query,
            "intent": parsed.intent,
            "detected_category": parsed.detected_category,
            "detected_brand": parsed.detected_brand,
            "detected_specs": parsed.detected_specs,
            "search_mode": parsed.search_mode,
            "category_confidence": parsed.category_confidence,
            "min_price": parsed.min_price,
            "max_price": parsed.max_price,
            "public_categories": list(public_search_categories()),
            "search_contract_version": SEARCH_CONTRACT_VERSION,
            "result_count": len(public_results),
            "limit": limit,
            "offset": effective_offset,
            "has_more": has_more,
            "next_cursor": _encode_cursor(effective_offset + limit) if has_more else None,
            "results": public_results,
            "sections": sections,
            "exact_match_count": len(sections["exact_matches"]),
            "similar_variant_count": len(sections["similar_variants"]),
            "related_product_count": len(sections["related_products"]),
            "facets": facets,
            "facet_scope": facet_scope,
            "facet_sample_size": facet_sample_size,
            "category_counts": counts,
            "sort": sort,
            "message": None if public_results else "No matching product is indexed yet.",
        }

    response = search_singleflight().do(key, _build_response)
    cache.set_json(key, response, settings.search_cache_ttl_seconds)
    metrics.SEARCH_TOTAL.observe(
        (time.perf_counter() - total_started) * 1000,
        category=category_label,
        search_mode=mode_label,
        cache="miss",
    )
    return response


def _serialize_suggestion(row: dict) -> dict:
    """Bounded product suggestion — same public universe as Search Results."""
    public = serialize_search_result(row)
    return {
        "id": public["id"],
        "title": public.get("title") or "",
        "brand": public.get("brand"),
        "category": public.get("category"),
        "image_url": public.get("image_url"),
        "best_price": public.get("best_price"),
        "best_platform": public.get("best_platform"),
        "platform_count": public.get("platform_count") or 0,
        "offer_count": public.get("offer_count") or public.get("platform_count") or 0,
        "display_specs": public.get("display_specs") or {},
        "specs": public.get("specs") or {},
        "model_codes": public.get("model_codes") or [],
    }


@router.get("/search/suggest")
def search_suggest(
    request: Request,
    q: str = Query(default="", max_length=160),
    limit: int = Query(default=6, ge=1, le=10),
) -> dict:
    """Bounded autocomplete suggestions from the public search index.

    Reuses classify_query + search_products. Does not create a second ranker.
    Popular queries are omitted when aggregate data is unavailable.
    """
    _enforce_public_rate_limit(request)
    settings = get_app_settings()
    query = sanitize_query(q or "")
    products: list[dict] = []
    categories: list[dict] = []
    popular_queries: list[dict] = []

    if len(query) >= 2:
        cache_key = (
            f"suggest:{SEARCH_CONTRACT_VERSION}:"
            f"{hashlib.sha256(f'{query}|{limit}'.encode()).hexdigest()}"
        )
        try:
            cached = cache.get_json(cache_key)
        except Exception:
            cached = None
        if cached is not None:
            return cached

        parsed = classify_query(query)
        if parsed.is_relevant:
            rows = search_products(parsed, limit=limit, offset=0, sort="relevance")
            products = [_serialize_suggestion(row) for row in rows[:limit]]

        needle = query.lower()
        for slug in public_search_categories():
            try:
                info = validate_public_category(slug)
            except ValueError:
                continue
            label = info.display_name
            hay = f"{slug} {label} {' '.join(info.aliases)}".lower()
            if needle in hay or any(token in hay for token in needle.split() if len(token) > 1):
                categories.append({"slug": slug, "label": label})
            if len(categories) >= 4:
                break

        payload = {
            "query": query,
            "products": products,
            "categories": categories,
            "popular_queries": popular_queries,
            "search_contract_version": SEARCH_CONTRACT_VERSION,
        }
        cache.set_json(cache_key, payload, min(30, settings.search_cache_ttl_seconds))
        # Documented bound: suggest prices may lag material refreshes by at most this TTL.
        return payload

    # Empty / short query: categories + optional popular aggregates only.
    from mayabu.search.search_repository import popular_search_queries

    for slug in public_search_categories():
        try:
            info = validate_public_category(slug)
        except ValueError:
            continue
        categories.append({"slug": slug, "label": info.display_name})
    popular_queries = popular_search_queries(limit=6)
    return {
        "query": query,
        "products": [],
        "categories": categories,
        "popular_queries": popular_queries,
        "search_contract_version": SEARCH_CONTRACT_VERSION,
    }


@router.get("/search/categories")
def list_search_categories() -> dict:
    """Public catalog of searchable categories (no experimental exposure as ready)."""
    from mayabu.search.category_registry import all_search_categories

    return {
        "search_contract_version": SEARCH_CONTRACT_VERSION,
        "categories": [
            {
                "slug": c.slug,
                "display_name": c.display_name,
                "public_search_enabled": c.public_search_enabled,
                "status": c.status,
                "aliases": list(c.aliases),
                "filterable_keys": list(c.filterable_keys),
                "facets": [{"key": f.key, "label": f.label} for f in c.facet_defs],
            }
            for c in all_search_categories()
            if c.public_search_enabled or c.status == "experimental"
        ],
    }
