"""Listing data-quality gate for production ingestion.

Separates record usability from price usability.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from mayabu.domain.categories.registry import price_bounds_for
from mayabu.domain.identity_quality import has_sufficient_product_identity
from mayabu.platforms.registry import PLATFORMS
from mayabu_common import looks_like_real_product

Decision = Literal["accepted", "degraded", "rejected"]

# Stable reason codes — do not invent free-form strings at call sites.
REASON_MISSING_TITLE = "missing_title"
REASON_INVALID_URL = "invalid_url"
REASON_MISSING_PRICE = "missing_price"
REASON_INVALID_PRICE = "invalid_price"
REASON_SUSPICIOUS_PRICE = "suspicious_price"
REASON_PLACEHOLDER_IMAGE = "placeholder_image"
REASON_CATEGORY_UNKNOWN = "category_unknown"
REASON_CATEGORY_ACCESSORY = "category_accessory"
REASON_CATEGORY_LOW_CONFIDENCE = "category_low_confidence"
REASON_DUPLICATE_URL = "duplicate_url"
REASON_WEAK_TITLE = "weak_product_title"
REASON_INSUFFICIENT_IDENTITY = "insufficient_identity"
REASON_MRP_BELOW_PRICE = "mrp_below_price"
REASON_UNSUPPORTED_PLATFORM = "unsupported_platform"
REASON_EMI_OR_FEE_CONTEXT = "emi_or_fee_context"

PLACEHOLDER_IMAGE_MARKERS = (
    "1x1",
    "pixel.gif",
    "spacer",
    "placeholder",
    "blank.gif",
    "data:image/gif;base64,r0lgodlh",
    "logo",
    "wishlist",
    "badge",
)

BAD_PRICE_CONTEXT_RE = re.compile(
    r"\b(emi|per\s*month|/mo|month|bank|cashback|coupon|exchange|delivery|fee|"
    r"warranty|protect|assured|no\s*cost|upto|up\s*to)\b",
    re.I,
)


@dataclass(frozen=True, slots=True)
class QualityFlag:
    code: str
    severity: str
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "evidence": self.evidence,
        }


@dataclass(frozen=True, slots=True)
class QualityDecision:
    decision: Decision
    reasons: tuple[str, ...]
    flags: tuple[QualityFlag, ...]
    price_usable: bool
    record_usable: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reasons": list(self.reasons),
            "flags": [f.as_dict() for f in self.flags],
            "price_usable": self.price_usable,
            "record_usable": self.record_usable,
        }


def _is_placeholder_image(url: str | None) -> bool:
    text = (url or "").strip().lower()
    if not text:
        return False
    return any(marker in text for marker in PLACEHOLDER_IMAGE_MARKERS)


def validate_listing(listing: dict[str, Any]) -> list[dict[str, Any]]:
    """Backward-compatible flag list used by existing ingestion."""
    return [f.as_dict() for f in evaluate_listing(listing).flags]


def evaluate_listing(
    listing: dict[str, Any],
    *,
    seen_urls: set[str] | None = None,
    price_context: str | None = None,
) -> QualityDecision:
    """Evaluate a normalized listing for production ingestion."""
    flags: list[QualityFlag] = []
    reasons: list[str] = []
    title = str(listing.get("title") or "")
    category = str(listing.get("category") or "unknown")
    confidence = str(listing.get("category_confidence") or "unknown")
    platform = str(listing.get("platform") or "unknown")
    url = str(listing.get("url") or listing.get("link") or "")
    price = listing.get("price")
    mrp = listing.get("mrp")
    image = str(listing.get("image") or listing.get("image_url") or "")

    if platform not in PLATFORMS and platform != "unknown":
        flags.append(
            QualityFlag(
                REASON_UNSUPPORTED_PLATFORM,
                "high",
                "Platform is not in the Mayabu registry",
                {"platform": platform},
            )
        )
        reasons.append(REASON_UNSUPPORTED_PLATFORM)

    if not title.strip():
        flags.append(QualityFlag(REASON_MISSING_TITLE, "high", "Listing has no title", {"platform": platform}))
        reasons.append(REASON_MISSING_TITLE)
    else:
        specs = listing.get("specs") if isinstance(listing.get("specs"), dict) else {}
        native_id = listing.get("native_id") or listing.get("sku")
        if not has_sufficient_product_identity(
            title,
            category,
            specs=specs,
            native_id=str(native_id) if native_id else None,
        ):
            flags.append(
                QualityFlag(
                    REASON_INSUFFICIENT_IDENTITY,
                    "high",
                    "Title/brand alone lacks product identity",
                    {"title": title, "category": category},
                )
            )
            reasons.append(REASON_INSUFFICIENT_IDENTITY)
        elif not looks_like_real_product(title, category):
            flags.append(
                QualityFlag(
                    REASON_WEAK_TITLE,
                    "medium",
                    "Title does not look like a sellable primary product",
                    {"title": title, "category": category},
                )
            )
            reasons.append(REASON_WEAK_TITLE)

    if not url or not url.startswith("http"):
        flags.append(QualityFlag(REASON_INVALID_URL, "high", "Listing URL is missing or invalid", {"url": url}))
        reasons.append(REASON_INVALID_URL)
    elif seen_urls is not None:
        key = url.rstrip("/").lower()
        if key in seen_urls:
            flags.append(QualityFlag(REASON_DUPLICATE_URL, "medium", "Duplicate product URL in batch", {"url": url}))
            reasons.append(REASON_DUPLICATE_URL)
        else:
            seen_urls.add(key)

    price_usable = True
    if price is None:
        flags.append(QualityFlag(REASON_MISSING_PRICE, "medium", "Price could not be parsed", {"title": title}))
        reasons.append(REASON_MISSING_PRICE)
        price_usable = False
    else:
        try:
            price_f = float(price)
        except (TypeError, ValueError):
            flags.append(QualityFlag(REASON_INVALID_PRICE, "high", "Price is not numeric", {"price": price}))
            reasons.append(REASON_INVALID_PRICE)
            price_usable = False
            price_f = None
        if price_f is not None:
            if price_f <= 0:
                flags.append(QualityFlag(REASON_INVALID_PRICE, "high", "Price must be positive", {"price": price_f}))
                reasons.append(REASON_INVALID_PRICE)
                price_usable = False
            else:
                lo, hi = price_bounds_for(category if category not in {"unknown", "accessory"} else None)
                if price_f < lo or price_f > hi:
                    flags.append(
                        QualityFlag(
                            REASON_SUSPICIOUS_PRICE,
                            "high",
                            "Price outside category sanity bounds",
                            {"price": price_f, "min": lo, "max": hi, "category": category},
                        )
                    )
                    reasons.append(REASON_SUSPICIOUS_PRICE)
                    price_usable = False
            if price_context and BAD_PRICE_CONTEXT_RE.search(price_context):
                flags.append(
                    QualityFlag(
                        REASON_EMI_OR_FEE_CONTEXT,
                        "high",
                        "Price text looks like EMI/fee/coupon rather than product price",
                        {"context": price_context[:200]},
                    )
                )
                reasons.append(REASON_EMI_OR_FEE_CONTEXT)
                price_usable = False

    if mrp is not None and price is not None:
        try:
            if float(mrp) < float(price):
                flags.append(
                    QualityFlag(
                        REASON_MRP_BELOW_PRICE,
                        "medium",
                        "MRP is lower than current price",
                        {"price": price, "mrp": mrp},
                    )
                )
                reasons.append(REASON_MRP_BELOW_PRICE)
        except (TypeError, ValueError):
            pass

    if _is_placeholder_image(image):
        flags.append(
            QualityFlag(
                REASON_PLACEHOLDER_IMAGE,
                "low",
                "Image URL looks like a placeholder/logo",
                {"image": image[:200]},
            )
        )
        reasons.append(REASON_PLACEHOLDER_IMAGE)

    if category == "accessory":
        flags.append(
            QualityFlag(
                REASON_CATEGORY_ACCESSORY,
                "high",
                "Listing classified as accessory, not a primary product",
                {"title": title},
            )
        )
        reasons.append(REASON_CATEGORY_ACCESSORY)
    elif category == "unknown":
        flags.append(
            QualityFlag(
                REASON_CATEGORY_UNKNOWN,
                "medium",
                "Category could not be determined",
                {"title": title},
            )
        )
        reasons.append(REASON_CATEGORY_UNKNOWN)
    elif confidence in {"low", "unknown"}:
        flags.append(
            QualityFlag(
                REASON_CATEGORY_LOW_CONFIDENCE,
                "low",
                "Category confidence is low",
                {"category": category, "confidence": confidence},
            )
        )
        reasons.append(REASON_CATEGORY_LOW_CONFIDENCE)

    fatal_codes = {
        REASON_MISSING_TITLE,
        REASON_INVALID_URL,
        REASON_UNSUPPORTED_PLATFORM,
        REASON_CATEGORY_ACCESSORY,
        REASON_INSUFFICIENT_IDENTITY,
        REASON_INVALID_PRICE,
        REASON_SUSPICIOUS_PRICE,
        REASON_EMI_OR_FEE_CONTEXT,
    }
    has_fatal = any(f.code in fatal_codes and f.severity == "high" for f in flags)

    # Record can be usable without price (title+url) as degraded metadata-only.
    record_usable = bool(title.strip()) and bool(url.startswith("http")) and category != "accessory"
    reject_codes = {
        REASON_MISSING_TITLE,
        REASON_INVALID_URL,
        REASON_UNSUPPORTED_PLATFORM,
        REASON_CATEGORY_ACCESSORY,
        REASON_INSUFFICIENT_IDENTITY,
        REASON_INVALID_PRICE,
        REASON_SUSPICIOUS_PRICE,
        REASON_EMI_OR_FEE_CONTEXT,
    }
    if has_fatal and any(code in reasons for code in reject_codes):
        decision: Decision = "rejected"
        record_usable = False
    elif not price_usable or REASON_CATEGORY_UNKNOWN in reasons or REASON_DUPLICATE_URL in reasons:
        decision = "degraded" if record_usable else "rejected"
    elif any(f.severity in {"medium", "high"} for f in flags):
        decision = "degraded"
    else:
        decision = "accepted"

    return QualityDecision(
        decision=decision,
        reasons=tuple(dict.fromkeys(reasons)),
        flags=tuple(flags),
        price_usable=price_usable and decision != "rejected",
        record_usable=record_usable and decision != "rejected",
    )


def fatal_listing_flags(flags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fatal_codes = {
        REASON_MISSING_TITLE,
        REASON_INVALID_URL,
        REASON_UNSUPPORTED_PLATFORM,
        REASON_CATEGORY_ACCESSORY,
        REASON_INSUFFICIENT_IDENTITY,
        "missing_url",  # legacy alias
    }
    return [f for f in flags if f.get("severity") == "high" and f.get("code") in fatal_codes]


def should_persist_price(flags: list[dict[str, Any]] | QualityDecision) -> bool:
    if isinstance(flags, QualityDecision):
        return flags.price_usable and flags.decision != "rejected"
    bad = {
        REASON_MISSING_PRICE,
        REASON_INVALID_PRICE,
        REASON_SUSPICIOUS_PRICE,
        REASON_EMI_OR_FEE_CONTEXT,
        "price_too_low",
        "price_too_high",
    }
    return not any(f.get("code") in bad for f in flags)


def classify_empty_scrape(platform: str, page_url: str | None, html_text: str | None = None) -> dict[str, Any]:
    html = (html_text or "").lower()
    if any(
        term in html
        for term in ["captcha", "robot check", "verify you are human", "unusual traffic", "access denied", "cf-challenge"]
    ):
        return {
            "severity": "critical",
            "event_type": "captcha_or_bot_check",
            "status": "blocked",
            "message": f"{platform} returned a bot/captcha page",
            "evidence": {"url": page_url},
        }
    if any(term in html for term in ["no results", "0 results", "did not match any products", "sorry, no results"]):
        return {
            "severity": "medium",
            "event_type": "empty_result_page",
            "status": "empty",
            "message": f"{platform} returned an empty result page",
            "evidence": {"url": page_url},
        }
    return {
        "severity": "high",
        "event_type": "selector_or_content_failure",
        "status": "failed",
        "message": f"{platform} scraper extracted zero products",
        "evidence": {"url": page_url},
    }
