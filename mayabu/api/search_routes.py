"""Public search API routes with bounded cursor pagination."""

from __future__ import annotations

import base64
import hashlib
import json
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, status

from mayabu.api.client_identity import client_identifier
from mayabu.api.rate_limit import SlidingWindowLimiter
from mayabu.api.serializers import serialize_search_result
from mayabu.core.config import get_app_settings
from mayabu.core.security import hash_identifier, sanitize_query
from mayabu.search.cache import get_cache
from mayabu.search.demand_signal import upsert_demand_cluster
from mayabu.search.query_classifier import classify_query
from mayabu.search.search_repository import log_search_query, search_products

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
        raise HTTPException(
            status_code=400, detail="Invalid pagination cursor"
        ) from exc


def _cache_key(query: str, limit: int, offset: int, category: str | None = None) -> str:
    digest = hashlib.sha256(
        f"{query}|{limit}|{offset}|{category or 'all'}".encode()
    ).hexdigest()
    return f"search:v5:{digest}"


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
) -> dict:
    _enforce_public_rate_limit(request)
    cursor_offset = _decode_cursor(cursor)
    effective_offset = cursor_offset if cursor_offset is not None else offset
    settings = get_app_settings()
    query = sanitize_query(q)
    parsed = classify_query(query)
    ip_hash = hash_identifier(client_identifier(request))

    if not parsed.is_relevant:
        background_tasks.add_task(
            _record_search_analytics, parsed, 0, None, 0.0, ip_hash
        )
        return {
            "query": query,
            "normalized_query": parsed.normalized_query,
            "intent": parsed.intent,
            "detected_category": parsed.detected_category,
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
            "message": "Mayabu currently supports laptop searches.",
        }

    key = _cache_key(
        parsed.normalized_query, limit, effective_offset, parsed.detected_category
    )
    cached = cache.get_json(key)
    if cached is not None:
        return cached

    raw_results = search_products(parsed, limit=limit + 1, offset=effective_offset)
    has_more = len(raw_results) > limit
    page_rows = raw_results[:limit]
    public_results = [serialize_search_result(row) for row in page_rows]
    sections = _result_sections(public_results)
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

    response = {
        "query": query,
        "normalized_query": parsed.normalized_query,
        "intent": parsed.intent,
        "detected_category": parsed.detected_category,
        "detected_brand": parsed.detected_brand,
        "detected_specs": parsed.detected_specs,
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
        "message": None if public_results else "No matching product is indexed yet.",
    }
    cache.set_json(key, response, settings.search_cache_ttl_seconds)
    return response
