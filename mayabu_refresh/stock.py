"""Evidence-based stock classification for refresh/verify adapters.

UNKNOWN must never become OUT_OF_STOCK.
Challenge / incomplete pages must preserve prior trusted stock.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

StockState = Literal[
    "in_stock",
    "out_of_stock",
    "unavailable",
    "unknown",
    "challenge",
    "login_required",
    "delivery_location_required",
    "variant_unselected",
    "parser_uncertain",
]

# Public DB / listing stock uses a narrower enum.
PublicStock = Literal["in_stock", "out_of_stock", "unknown", "unavailable"]

_EXPLICIT_OOS = (
    "currently unavailable",
    "out of stock",
    "outofstock",
    "sold out",
    "this item is no longer available",
    "we don't know when or if this item will be back in stock",
    "item cannot be shipped to your selected delivery location",
)

# Phrases that appear all over retail HTML and must NOT alone imply OOS.
_WEAK_OOS_NOISE = (
    "not available",  # too broad: "not available in your area" for other SKUs, etc.
    "unavailable",
)

_EXPLICIT_IN_STOCK = (
    "in stock",
    "instock",
    "only \\d+ left",  # handled separately via regex-ish substring checks
    "available to order",
    "ships from",
)

_PURCHASE_CTA = (
    "add to cart",
    "add to basket",
    "buy now",
    "buy with",
)

_CHALLENGE = (
    "robot check",
    "captcha",
    "verify you are human",
    "unusual traffic",
    "enter the characters you see",
    "access denied",
)

_LOCATION = (
    "enter pincode",
    "enter pin code",
    "select your location",
    "choose your location",
    "delivery location",
    "check delivery",
)

_LOGIN = (
    "sign in to see",
    "login to continue",
    "log in to buy",
)


@dataclass(frozen=True, slots=True)
class StockClassification:
    state: StockState
    reason: str
    confidence: str  # high | medium | low
    evidence: tuple[str, ...] = ()

    @property
    def public_stock(self) -> PublicStock:
        if self.state == "in_stock":
            return "in_stock"
        if self.state == "out_of_stock":
            return "out_of_stock"
        if self.state == "unavailable":
            return "unavailable"
        return "unknown"


def classify_stock_text(
    text: str | None,
    *,
    page_status: str | None = None,
    scoped: bool = False,
) -> StockClassification:
    """Classify stock from page text.

    Prefer calling with *scoped* availability/purchase region text.
    Full HTML is accepted but treated conservatively (OOS needs explicit phrases;
    weak tokens ignored; purchase CTAs can corroborate in-stock).
    """
    value = (text or "").lower()
    page = (page_status or "").lower()

    if page in {"blocked", "captcha"} or any(t in value for t in _CHALLENGE):
        return StockClassification("challenge", "challenge_or_captcha", "high", ("challenge",))

    if not value.strip():
        return StockClassification("unknown", "empty_text", "low")

    if any(t in value for t in _LOGIN):
        return StockClassification("login_required", "login_wall", "medium", ("login",))

    if any(t in value for t in _LOCATION) and "add to cart" not in value and "buy now" not in value:
        # Location modal without purchase CTA → uncertain, not OOS.
        return StockClassification(
            "delivery_location_required",
            "location_required",
            "medium",
            ("location",),
        )

    explicit_oos = [t for t in _EXPLICIT_OOS if t in value]
    has_cta = any(t in value for t in _PURCHASE_CTA)
    has_instock_phrase = "in stock" in value or "instock" in value or "available to order" in value
    left_in_stock = "left in stock" in value or "left" in value and "stock" in value

    # Purchase CTA / explicit in-stock beats incidental OOS phrases elsewhere on page
    # when analyzing full HTML (scoped=False).
    if has_cta or has_instock_phrase or left_in_stock:
        if explicit_oos and scoped:
            # In a tight availability box, explicit OOS wins over stray CTA elsewhere.
            return StockClassification(
                "out_of_stock",
                "explicit_oos_text",
                "high",
                tuple(explicit_oos),
            )
        return StockClassification(
            "in_stock",
            "purchase_cta" if has_cta else "explicit_in_stock_text",
            "high" if has_cta or has_instock_phrase else "medium",
            ("add_to_cart_or_buy_now",) if has_cta else ("in_stock_phrase",),
        )

    if explicit_oos:
        return StockClassification(
            "out_of_stock",
            "explicit_oos_text",
            "high" if scoped else "medium",
            tuple(explicit_oos),
        )

    # Weak noise alone → unknown (never OOS).
    if any(t in value for t in _WEAK_OOS_NOISE):
        return StockClassification("parser_uncertain", "weak_availability_phrase", "low", ("weak_oos_noise",))

    if "coming soon" in value or "notify me" in value:
        return StockClassification("unavailable", "coming_soon_or_notify", "medium", ("coming_soon",))

    return StockClassification("unknown", "no_stock_evidence", "low")


def detect_stock_status(text: str | None) -> str:
    """Backward-compatible wrapper returning public stock string."""
    return classify_stock_text(text, scoped=False).public_stock


def resolve_stock_for_ingest(
    *,
    detected: str | None,
    previous: str | None,
    page_status: str | None,
    update_stock: bool,
    reason: str | None = None,
    confidence: str | None = None,
) -> tuple[str, str]:
    """Decide listing stock for persistence.

    Returns (stock_status, decision_reason).
    Surprising in_stock → out_of_stock without strong evidence preserves previous.
    """
    det = (detected or "unknown").strip().lower()
    prev = (previous or "unknown").strip().lower()
    page = (page_status or "").strip().lower()
    why = (reason or "").strip().lower()
    conf = (confidence or "").strip().lower()

    if page in {"blocked", "captcha", "failed"}:
        return (prev if prev in {"in_stock", "out_of_stock", "unavailable"} else "unknown"), "preserve_on_page_failure"

    if det in {"challenge", "login_required", "delivery_location_required", "variant_unselected", "parser_uncertain"}:
        return (prev if prev in {"in_stock", "out_of_stock", "unavailable"} else "unknown"), f"preserve_on_{det}"

    if det == "unknown":
        return (prev if prev in {"in_stock", "out_of_stock", "unavailable"} else "unknown"), "preserve_on_unknown"

    if det == "out_of_stock":
        # Explicit OOS text with high confidence only for surprising transitions.
        strong = why == "explicit_oos_text" and conf == "high"
        if prev == "in_stock" and not strong:
            return "unknown", "ambiguous_oos_not_published"
        if strong or (prev != "in_stock" and why == "explicit_oos_text" and page == "success"):
            return "out_of_stock", "accept_oos"
        if update_stock and why == "explicit_oos_text" and conf in {"high", "medium"} and prev in {"unknown", "out_of_stock", "unavailable"}:
            return "out_of_stock", "accept_oos"
        return prev if prev != "unknown" else "unknown", "oos_insufficient_evidence"

    if det == "in_stock":
        if page == "success" or update_stock:
            return "in_stock", "accept_in_stock"
        return prev if prev in {"in_stock", "out_of_stock"} else "in_stock", "soft_in_stock"

    if det == "unavailable":
        return "unavailable", "accept_unavailable"

    return "unknown", "fallback_unknown"


__all__ = [
    "StockClassification",
    "StockState",
    "classify_stock_text",
    "detect_stock_status",
    "resolve_stock_for_ingest",
]
