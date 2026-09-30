"""Public best-price semantics for matched, production-ready offers.

PostgreSQL `current_product_best_prices` is the production source of truth for
product, search, compare, and wishlist payloads. This module mirrors that view
so tests and Python offer filtering cannot drift from it.

Eligible public current price:
- match_status == matched
- public_offer_allowed(platform, category)
- numeric current_price > 0
- currency INR (missing currency treated as INR)

Best price:
- minimum in-stock eligible price when any in-stock priced offer exists
- otherwise the minimum eligible last-known price, including out_of_stock rows
  that still carry a trustworthy current_price (TWS / OOS-null-refresh semantics)
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from mayabu.platforms.coverage import public_offer_allowed

_OOS = frozenset({"out_of_stock", "unavailable"})


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


def listing_is_public_priced(listing: dict[str, Any], category: str | None = None) -> bool:
    """Whether a listing may contribute to public best price / public offers."""
    if str(listing.get("match_status") or "matched") != "matched":
        return False
    platform = str(listing.get("platform") or "")
    cat = str(category or listing.get("category") or "")
    if not public_offer_allowed(platform, cat):
        return False
    currency = str(listing.get("currency") or "INR").strip().upper()
    if currency != "INR":
        return False
    return _as_price(listing.get("current_price")) is not None


def _is_out_of_stock(listing: dict[str, Any]) -> bool:
    return str(listing.get("stock_status") or "").strip().lower() in _OOS


@dataclass(frozen=True, slots=True)
class PublicBestPrice:
    best_price: Decimal | None
    best_platform: str | None
    platform_count: int
    used_out_of_stock_fallback: bool


def compute_public_best_price(
    listings: list[dict[str, Any]],
    category: str | None = None,
) -> PublicBestPrice:
    """Minimum eligible public current price across unique retailers."""
    from mayabu.search.public_offers import select_public_offers

    # Collapse same-retailer duplicates before min-price so listing inflation
    # cannot distort best_platform / platform_count.
    unique = select_public_offers(listings, category=category)
    eligible: list[tuple[Decimal, dict[str, Any]]] = []
    for listing in unique:
        if not listing_is_public_priced(listing, category):
            continue
        price = _as_price(listing.get("current_price"))
        if price is None:
            continue
        eligible.append((price, listing))

    platforms = {str(row.get("platform") or "") for _, row in eligible if row.get("platform")}
    in_stock = [(price, row) for price, row in eligible if not _is_out_of_stock(row)]
    source = in_stock or eligible
    used_fallback = bool(eligible) and not in_stock
    if not source:
        return PublicBestPrice(None, None, 0, False)

    source.sort(
        key=lambda item: (
            item[0],
            str(item[1].get("platform") or ""),
        )
    )
    best_price, best_row = source[0]
    return PublicBestPrice(
        best_price=best_price,
        best_platform=str(best_row.get("platform") or "") or None,
        platform_count=len(platforms),
        used_out_of_stock_fallback=used_fallback,
    )


__all__ = [
    "PublicBestPrice",
    "compute_public_best_price",
    "listing_is_public_priced",
]
