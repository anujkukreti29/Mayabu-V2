"""Product, offer, variant, and price-history routes."""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, HTTPException, Query

from mayabu.api.serializers import serialize_offer, serialize_price_point, serialize_product, serialize_search_result
from mayabu.core.config import get_app_settings
from mayabu.search.cache import get_cache
from mayabu.search.search_repository import (
    get_price_history, get_product, get_product_offers, get_similar_variants, product_exists,
)

router = APIRouter(prefix="/api/products", tags=["products"])
cache = get_cache()


def _key(prefix: str, product_id: str, extra: str = "") -> str:
    extra_hash = hashlib.sha256(str(extra).encode()).hexdigest()[:12] if extra else "default"
    return f"{prefix}:{product_id}:{extra_hash}"


@router.get("/{product_id}")
def product_detail(product_id: str) -> dict:
    settings = get_app_settings()
    key = _key("product", product_id)
    cached = cache.get_json(key)
    if cached is not None:
        return cached
    product = get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    offers = [serialize_offer(row) for row in get_product_offers(product_id)]
    variants = [serialize_search_result(row) for row in get_similar_variants(product_id, limit=8)]
    response = {
        "product": serialize_product(product),
        "offers": offers,
        "offer_count": len(offers),
        "similar_variants": variants,
        "similar_variant_count": len(variants),
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
def price_history(product_id: str, days: int = Query(180, ge=1, le=3650)) -> dict:
    settings = get_app_settings()
    key = _key("price-history", product_id, str(days))
    cached = cache.get_json(key)
    if cached is not None:
        return cached
    if not product_exists(product_id):
        raise HTTPException(status_code=404, detail="Product not found")
    history = [serialize_price_point(row) for row in get_price_history(product_id, days)]
    response = {"product_id": product_id, "days": days, "history": history}
    cache.set_json(key, response, settings.price_history_cache_ttl_seconds)
    return response
