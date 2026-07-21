from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mayabu_common import looks_like_real_product


@dataclass(frozen=True, slots=True)
class QualityFlag:
    code: str
    severity: str
    message: str
    evidence: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "evidence": self.evidence,
        }


def validate_listing(listing: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate normalized listing data before DB ingestion.

    Returns serializable flags. Medium/high flags should be visible in the
    anomaly table but should not always crash a run; Mayabu must preserve raw
    data even when a platform returns incomplete cards.
    """
    flags: list[QualityFlag] = []
    title = listing.get("title") or ""
    category = listing.get("category") or "unknown"
    platform = listing.get("platform") or "unknown"
    price = listing.get("price")
    mrp = listing.get("mrp")
    specs = listing.get("specs") or {}

    if not title:
        flags.append(QualityFlag("missing_title", "high", "Listing has no title", {"platform": platform}))
    elif not looks_like_real_product(title, category):
        flags.append(QualityFlag("weak_product_title", "medium", "Title does not look like the requested product category", {"title": title, "category": category}))

    if not listing.get("url"):
        flags.append(QualityFlag("missing_url", "high", "Listing has no URL", {"title": title}))

    if price is None:
        flags.append(QualityFlag("missing_price", "medium", "Price could not be parsed", {"title": title}))
    elif category == "laptop":
        if price < 5000:
            flags.append(QualityFlag("price_too_low", "high", "Laptop price is suspiciously low", {"price": price}))
        if price > 600000:
            flags.append(QualityFlag("price_too_high", "medium", "Laptop price is suspiciously high", {"price": price}))

    if mrp is not None and price is not None and mrp < price:
        flags.append(QualityFlag("mrp_below_price", "medium", "MRP is lower than current price", {"price": price, "mrp": mrp}))

    if category == "laptop":
        strong_specs = [specs.get("brand"), specs.get("cpu_series"), specs.get("ram_gb"), specs.get("storage_gb"), specs.get("model_codes")]
        if sum(1 for value in strong_specs if value) < 2:
            flags.append(QualityFlag("weak_laptop_specs", "low", "Few laptop identity specs were extracted", {"specs": specs}))

    return [f.as_dict() for f in flags]


def fatal_listing_flags(flags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [f for f in flags if f.get("severity") == "high" and f.get("code") in {"missing_title", "missing_url"}]


def classify_empty_scrape(platform: str, page_url: str | None, html_text: str | None = None) -> dict[str, Any]:
    html = (html_text or "").lower()
    if any(term in html for term in ["captcha", "robot check", "verify you are human", "unusual traffic"]):
        return {"severity": "critical", "event_type": "captcha_or_bot_check", "message": f"{platform} returned a bot/captcha page", "evidence": {"url": page_url}}
    if any(term in html for term in ["no results", "0 results", "did not match any products", "sorry, no results"]):
        return {"severity": "medium", "event_type": "empty_result_page", "message": f"{platform} returned an empty result page", "evidence": {"url": page_url}}
    return {"severity": "high", "event_type": "selector_or_content_failure", "message": f"{platform} scraper extracted zero products", "evidence": {"url": page_url}}
