"""Product, offer, variant, price-history, and price-intelligence routes."""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, HTTPException, Query

from mayabu.api.serializers import serialize_offer, serialize_price_point, serialize_product, serialize_search_result
from mayabu.core.config import get_app_settings
from mayabu.domain.price_intelligence import (
    get_price_intelligence,
    resolve_history_days,
    serialize_history_payload,
    serialize_intelligence,
)
from mayabu.search.cache import get_cache
from mayabu.search.search_repository import (
    get_price_history, get_product, get_product_offers, get_similar_products, get_similar_variants, product_exists,
)

router = APIRouter(prefix="/api/products", tags=["products"])
cache = get_cache()
# Bump when product payload price contract changes so stale Redis rows cannot
# keep a null best_price next to priced public offers.
PRODUCT_CACHE_CONTRACT = "bp-oos-gallery-similar-v1"
HISTORY_CACHE_CONTRACT = "hist-platforms-v1"
INTELLIGENCE_CACHE_CONTRACT = "intel-v2"


def _key(prefix: str, product_id: str, extra: str = "") -> str:
    extra_hash = hashlib.sha256(str(extra).encode()).hexdigest()[:12] if extra else "default"
    return f"{prefix}:{product_id}:{extra_hash}"


@router.get("/{product_id}")
def product_detail(product_id: str) -> dict:
    settings = get_app_settings()
    key = _key("product", product_id, PRODUCT_CACHE_CONTRACT)
    cached = cache.get_json(key)
    if cached is not None:
        return cached
    product = get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    offers = [serialize_offer(row) for row in get_product_offers(product_id)]
    variants = [serialize_search_result(row) for row in get_similar_variants(product_id, limit=8)]
    similar = [serialize_search_result(row) for row in get_similar_products(product_id, limit=8)]
    from mayabu.catalog.product_images import list_product_images

    gallery = list_product_images(product_id, limit=10)
    images = [
        {
            "url": row["image_url"],
            "is_primary": bool(row.get("is_primary")),
            "source": row.get("source_platform"),
        }
        for row in gallery
        if row.get("image_url")
    ]
    if not images and product.get("image_url"):
        images = [{"url": product["image_url"], "is_primary": True, "source": None}]
    response = {
        "product": serialize_product(product),
        "offers": offers,
        "offer_count": len(offers),
        "similar_variants": variants,
        "similar_variant_count": len(variants),
        "similar_products": similar,
        "similar_product_count": len(similar),
        "images": images,
        "image_count": len(images),
    }
    cache.set_json(key, response, settings.product_cache_ttl_seconds)
    return response


@router.get("/{product_id}/offers")
def offers(product_id: str) -> dict:
    if not product_exists(product_id):
        raise HTTPException(status_code=404, detail="Product not found")
    rows = [serialize_offer(row) for row in get_product_offers(product_id)]
    return {"product_id": product_id, "offers": rows, "offer_count": len(rows)}


@router.get("/{product_id}/similar-variants")
def similar_variants(product_id: str, limit: int = Query(12, ge=1, le=50)) -> dict:
    if not product_exists(product_id):
        raise HTTPException(status_code=404, detail="Product not found")
    rows = [serialize_search_result(row) for row in get_similar_variants(product_id, limit=limit)]
    return {"product_id": product_id, "similar_variants": rows, "count": len(rows)}


@router.get("/{product_id}/price-history")
def price_history(
    product_id: str,
    days: int | None = Query(default=None, ge=1, le=3650),
    window: str | None = Query(default=None, max_length=16),
) -> dict:
    settings = get_app_settings()
    resolved_window, resolved_days = resolve_history_days(window, days if days is not None else 180)
    key = _key("price-history", product_id, f"{HISTORY_CACHE_CONTRACT}:{resolved_window}:{resolved_days}")
    cached = cache.get_json(key)
    if cached is not None:
        return cached
    if not product_exists(product_id):
        raise HTTPException(status_code=404, detail="Product not found")
    rows = get_price_history(product_id, resolved_days)
    history = [serialize_price_point(row) for row in rows]
    payload = serialize_history_payload(product_id, history, window=resolved_window, days=resolved_days)
    cache.set_json(key, payload, settings.price_history_cache_ttl_seconds)
    return payload


@router.get("/{product_id}/price-intelligence")
def price_intelligence(product_id: str) -> dict:
    settings = get_app_settings()
    key = _key("price-intelligence", product_id, INTELLIGENCE_CACHE_CONTRACT)
    cached = cache.get_json(key)
    if cached is not None:
        return cached
    payload = get_price_intelligence(product_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Product not found")
    response = serialize_intelligence(payload)
    ttl = min(settings.product_cache_ttl_seconds, settings.price_history_cache_ttl_seconds)
    cache.set_json(key, response, ttl)
    return response
