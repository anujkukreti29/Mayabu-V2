"""Public API serialization helpers."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any


def _public_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def serialize_specs(specs: Any) -> dict[str, Any]:
    if not isinstance(specs, dict):
        return {}
    allowed = {"family", "model_codes", "cpu_series", "cpu_models", "gpu", "ram_gb", "storage_gb", "screen_inch", "generation"}
    return {key: _public_value(value) for key, value in specs.items() if key in allowed and value not in (None, "", [])}


def serialize_search_result(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("product_id")),
        "title": row.get("canonical_title") or row.get("title") or "",
        "brand": row.get("brand"),
        "category": row.get("category"),
        "specs": serialize_specs(row.get("specs")),
        "best_price": _public_value(row.get("best_price")),
        "best_platform": row.get("best_platform"),
        "platform_count": int(row.get("platform_count") or 0),
        "offer_count": int(row.get("offer_count") or row.get("platform_count") or 0),
        "image_url": row.get("image_url"),
        "last_seen_at": _public_value(row.get("last_seen_at")),
        "match_group": row.get("match_group") or "related_product",
        "rank_score": _public_value(row.get("rank_score")),
        "variant_group_id": str(row.get("variant_group_id")) if row.get("variant_group_id") else None,
    }


def serialize_product(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id") or row.get("product_id")),
        "title": row.get("canonical_title") or "",
        "brand": row.get("brand"),
        "category": row.get("category"),
        "specs": serialize_specs(row.get("specs")),
        "best_price": _public_value(row.get("best_price")),
        "best_platform": row.get("best_platform"),
        "platform_count": int(row.get("platform_count") or 0),
        "image_url": row.get("image_url"),
        "last_seen_at": _public_value(row.get("last_seen_at")),
        "variant_group_id": str(row.get("variant_group_id")) if row.get("variant_group_id") else None,
    }


def serialize_offer(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id")),
        "platform": row.get("platform"),
        "listing_id": row.get("listing_id"),
        "native_id": row.get("native_id"),
        "url": row.get("listing_url"),
        "title": row.get("title") or "",
        "image_url": row.get("image_url"),
        "price": _public_value(row.get("current_price")),
        "mrp": _public_value(row.get("current_mrp")),
        "effective_price": _public_value(row.get("current_effective_price")),
        "discount_percent": _public_value(row.get("current_discount_pct")),
        "currency": row.get("currency") or "INR",
        "stock_status": row.get("stock_status"),
        "rating": _public_value(row.get("rating")),
        "review_count": row.get("review_count"),
        "last_checked_at": _public_value(row.get("last_verified_at") or row.get("last_successful_refresh_at") or row.get("last_seen_at")),
        "last_verified_at": _public_value(row.get("last_verified_at")),
        "verification_status": row.get("verification_status") or "never",
        "verification_source": row.get("verification_source"),
        "next_allowed_verification_at": _public_value(row.get("next_allowed_verification_at")),
        "verification_failures": int(row.get("consecutive_verification_failures") or 0),
    }


def serialize_price_point(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _public_value(value) for key, value in row.items()}
