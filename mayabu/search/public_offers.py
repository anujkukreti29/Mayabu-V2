"""Public offer selection: one authoritative listing per retailer.

Internal catalogs may retain multiple same-platform listings (color aliases,
rediscovery paths). Public PDP / cards / best-price must collapse to unique
retailers for an exact Mayabu product variant.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from mayabu.search.public_price import listing_is_public_priced

_OOS = frozenset({"out_of_stock", "unavailable"})

_COLOR_TOKEN_RE = re.compile(
    r"\b(black|white|silver|gold|blue|red|green|pink|purple|grey|gray|titanium|"
    r"natural|desert|ultramarine|teal|midnight|starlight|graphite|burgundy|"
    r"glacier|cosmic\s*orange|orange|yellow|violet|lavender|mint|cream|beige|"
    r"space\s*black|space\s*grey|space\s*gray|phantom\s*black|deep\s*purple)\b",
    re.I,
)


def _as_price(value: Any) -> Decimal | None:
    if value is None or value is False:
        return None
    try:
        price = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if price <= 0:
        return None
    return price


def _parse_ts(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, datetime):
        return value.timestamp()
    text = str(value).strip()
    if not text:
        return 0.0
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def extract_color_token(text: str | None) -> str | None:
    if not text:
        return None
    hit = _COLOR_TOKEN_RE.search(str(text))
    if not hit:
        return None
    return re.sub(r"\s+", " ", hit.group(1).lower()).strip()


def product_color_hint(
    *,
    title: str | None = None,
    specs: dict[str, Any] | None = None,
) -> str | None:
    specs = specs or {}
    raw = specs.get("color")
    if raw:
        token = extract_color_token(str(raw)) or str(raw).strip().lower()
        if token:
            return token
    return extract_color_token(title)


def _listing_color(listing: dict[str, Any]) -> str | None:
    specs = listing.get("specs") if isinstance(listing.get("specs"), dict) else {}
    if specs.get("color"):
        token = extract_color_token(str(specs["color"])) or str(specs["color"]).strip().lower()
        if token:
            return token
    return extract_color_token(listing.get("title") or listing.get("listing_url") or "")


def _is_oos(listing: dict[str, Any]) -> bool:
    return str(listing.get("stock_status") or "").strip().lower() in _OOS


def _selection_key(
    listing: dict[str, Any],
    *,
    preferred_color: str | None,
    category: str | None,
) -> tuple:
    """Lower tuple wins (sort ascending)."""
    color = _listing_color(listing)
    color_rank = 1
    if preferred_color:
        if color and color == preferred_color:
            color_rank = 0
        elif color and color != preferred_color:
            color_rank = 2
        else:
            color_rank = 1

    priced = listing_is_public_priced(listing, category)
    price = _as_price(listing.get("current_price"))
    oos = _is_oos(listing)
    freshness = max(
        _parse_ts(listing.get("last_verified_at")),
        _parse_ts(listing.get("last_successful_refresh_at")),
        _parse_ts(listing.get("last_seen_at")),
    )
    try:
        confidence = float(listing.get("match_confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    listing_id = str(listing.get("id") or listing.get("listing_id") or "")

    return (
        0 if priced else 1,
        color_rank,
        0 if (priced and not oos) else 1,
        price if price is not None else Decimal("999999999"),
        -freshness,
        -confidence,
        listing_id,
    )


def select_public_offers(
    listings: list[dict[str, Any]],
    *,
    category: str | None = None,
    product_title: str | None = None,
    product_specs: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return at most one public offer row per platform."""
    preferred = product_color_hint(title=product_title, specs=product_specs)
    by_platform: dict[str, list[dict[str, Any]]] = {}
    for listing in listings:
        platform = str(listing.get("platform") or "").strip().lower()
        if not platform:
            continue
        if str(listing.get("match_status") or "matched") != "matched":
            continue
        by_platform.setdefault(platform, []).append(listing)

    selected: list[dict[str, Any]] = []
    for platform in sorted(by_platform.keys()):
        candidates = by_platform[platform]
        candidates.sort(
            key=lambda row: _selection_key(
                row, preferred_color=preferred, category=category
            )
        )
        selected.append(candidates[0])

    selected.sort(
        key=lambda row: (
            0 if listing_is_public_priced(row, category) and not _is_oos(row) else 1,
            _as_price(row.get("current_price")) or Decimal("999999999"),
            str(row.get("platform") or ""),
        )
    )
    return selected


def unique_platform_count(listings: list[dict[str, Any]], category: str | None = None) -> int:
    """Count unique platforms among public-priced matched listings."""
    platforms: set[str] = set()
    for listing in listings:
        if not listing_is_public_priced(listing, category):
            continue
        platform = str(listing.get("platform") or "").strip().lower()
        if platform:
            platforms.add(platform)
    return len(platforms)


__all__ = [
    "extract_color_token",
    "product_color_hint",
    "select_public_offers",
    "unique_platform_count",
]
