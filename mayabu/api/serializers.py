"""Public API serialization helpers."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from mayabu.search.category_registry import display_specs_for, get_search_category


def _public_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


# Laptop fields kept for backward compatibility; category display specs are additive.
_LAPTOP_COMPAT_KEYS = {
    "family",
    "model_codes",
    "cpu_series",
    "cpu_models",
    "gpu",
    "ram_gb",
    "storage_gb",
    "screen_inch",
    "generation",
}


def serialize_specs(specs: Any, category: str | None = None) -> dict[str, Any]:
    if not isinstance(specs, dict):
        return {}
    allowed = set(_LAPTOP_COMPAT_KEYS)
    info = get_search_category(category)
    if info:
        allowed |= set(info.display_spec_keys) | set(info.filterable_keys) | {"family", "model_codes"}
    return {
        key: _public_value(value)
        for key, value in specs.items()
        if key in allowed and value not in (None, "", [])
    }


def _normalize_image_url(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "undefined", "n/a"}:
        return None
    if text.startswith("//"):
        text = f"https:{text}"
    lower = text.lower()
    if lower.startswith("javascript:") or lower.startswith("data:"):
        return None
    if not (lower.startswith("https://") or lower.startswith("http://")):
        return None
    # Reject obvious 1x1 tracker patterns when detectable from the URL alone.
    if any(token in lower for token in ("1x1", "pixel.gif", "tracking/pixel")):
        return None
    return text


def serialize_search_result(row: dict[str, Any]) -> dict[str, Any]:
    category = row.get("category")
    specs = serialize_specs(row.get("specs"), category)
    display = display_specs_for(
        category, row.get("specs") if isinstance(row.get("specs"), dict) else specs
    )
    return {
        "id": str(row.get("product_id")),
        "title": row.get("canonical_title") or row.get("title") or "",
        "brand": row.get("brand"),
        "category": category,
        "specs": specs,
        "display_specs": {k: _public_value(v) for k, v in display.items()},
        "family": row.get("family") or specs.get("family"),
        "model_codes": specs.get("model_codes") or [],
        "best_price": _public_value(row.get("best_price")),
        "best_platform": row.get("best_platform"),
        "platform_count": int(row.get("platform_count") or 0),
        "offer_count": int(row.get("offer_count") or row.get("platform_count") or 0),
        "image_url": _normalize_image_url(row.get("image_url")),
        "last_seen_at": _public_value(row.get("last_seen_at")),
        "match_group": row.get("match_group") or "related_product",
        "rank_score": _public_value(row.get("rank_score")),
        "variant_group_id": str(row.get("variant_group_id")) if row.get("variant_group_id") else None,
    }


def serialize_product(row: dict[str, Any]) -> dict[str, Any]:
    category = row.get("category")
    specs = serialize_specs(row.get("specs"), category)
    return {
        "id": str(row.get("id") or row.get("product_id")),
        "title": row.get("canonical_title") or "",
        "brand": row.get("brand"),
        "category": category,
        "specs": specs,
        "display_specs": {
            k: _public_value(v)
            for k, v in display_specs_for(
                category, row.get("specs") if isinstance(row.get("specs"), dict) else specs
            ).items()
        },
        "best_price": _public_value(row.get("best_price")),
        "best_platform": row.get("best_platform"),
        "platform_count": int(row.get("platform_count") or 0),
        "image_url": _normalize_image_url(row.get("image_url")),
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
        "image_url": _normalize_image_url(row.get("image_url")),
        "price": _public_value(row.get("current_price")),
        "mrp": _public_value(row.get("current_mrp")),
        "effective_price": _public_value(row.get("current_effective_price")),
        "discount_percent": _public_value(row.get("current_discount_pct")),
        "currency": row.get("currency") or "INR",
        "stock_status": row.get("stock_status"),
        "rating": _public_value(row.get("rating")),
        "review_count": row.get("review_count"),
        "last_checked_at": _public_value(
            row.get("last_verified_at") or row.get("last_successful_refresh_at") or row.get("last_seen_at")
        ),
        "last_verified_at": _public_value(row.get("last_verified_at")),
        "verification_status": row.get("verification_status") or "never",
        "verification_source": row.get("verification_source"),
        "next_allowed_verification_at": _public_value(row.get("next_allowed_verification_at")),
        "verification_failures": int(row.get("consecutive_verification_failures") or 0),
    }


def serialize_price_point(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _public_value(value) for key, value in row.items()}
