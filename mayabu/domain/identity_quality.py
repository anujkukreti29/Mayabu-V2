"""Deterministic identity-sufficiency checks for catalog quality.

Reject brand-only / brand+generic titles without inventing free-form reasons.
Structured model evidence can rescue a short retailer display title.
"""

from __future__ import annotations

import re
from typing import Any

from mayabu_common import BRAND_ALIASES, BRANDS, resolve_brand

# Tokens that add no product identity when paired only with a brand.
_GENERIC_CATEGORY_TOKENS = frozenset(
    {
        "phone",
        "phones",
        "smartphone",
        "smartphones",
        "mobile",
        "mobiles",
        "laptop",
        "laptops",
        "notebook",
        "notebooks",
        "ultrabook",
        "chromebook",
        "macbook",
        "tv",
        "tvs",
        "television",
        "televisions",
        "refrigerator",
        "refrigerators",
        "fridge",
        "fridges",
        "washing",
        "washer",
        "washers",
        "machine",
        "machines",
        "headphone",
        "headphones",
        "headset",
        "earphone",
        "earphones",
        "earbud",
        "earbuds",
        "tws",
        "camera",
        "cameras",
        "tablet",
        "tablets",
        "watch",
        "watches",
        "audio",
        "electronics",
        "appliance",
        "appliances",
        "device",
        "devices",
        "product",
        "products",
        "model",
        "series",
        "edition",
        "version",
        "new",
        "latest",
        "best",
        "buy",
        "sale",
        "offer",
        "offers",
        "deal",
        "deals",
        "official",
        "original",
        "genuine",
        "smart",
        "wireless",
        "bluetooth",
        "android",
        "led",
        "oled",
        "qled",
        "uhd",
        "fhd",
        "hd",
        "4k",
        "5g",
        "lte",
        "wifi",
        "wi",
        "fi",
        "in",
        "the",
        "and",
        "with",
        "for",
        "by",
        "from",
        "india",
        "black",
        "white",
        "blue",
        "red",
        "grey",
        "gray",
        "silver",
        "gold",
    }
)

# Strong visible model / family signals (not brand alone).
_MODEL_SIGNAL_RE = re.compile(
    r"("
    r"\biphone\s*\d{1,2}\b|"
    r"\bgalaxy\s+[a-z]?\d{1,2}\b|"
    r"\bgalaxy\s+z\b|"
    r"\bgalaxy\s+buds\b|"
    r"\bpixel\s*\d{1,2}\b|"
    r"\bredmi\s*(?:note\s*)?\d{1,2}\b|"
    r"\bpoco\s*[a-z]?\d{1,2}\b|"
    r"\boneplus\s*(?:nord\s*)?\d|"
    r"\bnothing\s*phone\s*\d|"
    r"\bmacbook\b|"
    r"\bairpods?\b|"
    r"\bbuds\s*[a-z0-9]*\d|"
    r"\bwh-?[a-z0-9]{3,}\b|"
    r"\bwf-?[a-z0-9]{3,}\b|"
    r"\boled\s*\d{2,}|"
    r"\bqled\s*\d{2,}|"
    r"\bua\d{2,}|"
    r"\b[a-z]{1,5}\d{2,}[a-z0-9-]{0,12}\b|"  # GLT2526WWDS, FA506NCQ, SM-S921B
    r"\b\d{2,3}\s*(?:inch|in|\"|''|cm)\b|"
    r"\b\d{1,2}\s*kg\b|"
    r"\b\d{2,4}\s*l(?:itre|iter)?s?\b|"
    r"\b\d{1,2}\s*gb\b|"
    r"\b\d{3,4}\s*gb\b|"
    r"\b\d\s*tb\b"
    r")",
    re.I,
)

_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)


def _model_codes(specs: dict[str, Any] | None) -> list[str]:
    if not specs:
        return []
    raw = specs.get("model_codes") or specs.get("model_code")
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        return []
    return [str(v).strip() for v in raw if str(v).strip()]


def _has_structured_identity(specs: dict[str, Any] | None, native_id: str | None) -> bool:
    """Strong structured rescue — not native_id alone on a brand-only title."""
    specs = specs or {}
    if _model_codes(specs):
        return True
    family = str(specs.get("family") or "").strip()
    if family and re.search(r"\d", family):
        return True
    # Category variant fields only count with an additional model-ish signal already checked.
    # Native SKU alone is insufficient without title/model evidence.
    _ = native_id
    return False


def _residual_identity_tokens(title: str) -> list[str]:
    text = _PUNCT_RE.sub(" ", (title or "").lower())
    tokens = [tok for tok in text.split() if tok]
    brand = resolve_brand(title)
    drop = set(_GENERIC_CATEGORY_TOKENS)
    drop.update(b.lower() for b in BRANDS)
    drop.update(a.lower() for a in BRAND_ALIASES)
    if brand:
        drop.add(brand.lower())
        for alias, canonical in BRAND_ALIASES.items():
            if canonical == brand:
                drop.add(alias.lower())
    residual: list[str] = []
    for tok in tokens:
        if tok in drop:
            continue
        if tok.isdigit() and len(tok) <= 1:
            continue
        residual.append(tok)
    return residual


def has_sufficient_product_identity(
    title: str,
    category: str | None = None,
    *,
    specs: dict[str, Any] | None = None,
    native_id: str | None = None,
) -> bool:
    """Return True when title/structured evidence identifies a sellable primary product."""
    title = (title or "").strip()
    if not title:
        return False
    if (category or "").lower() == "accessory":
        return False
    if _has_structured_identity(specs, native_id):
        return True
    if _MODEL_SIGNAL_RE.search(title):
        return True

    residual = _residual_identity_tokens(title)
    if not residual:
        return False
    # Any residual token with a digit is identity (S24, 16, 55, XM5...).
    if any(re.search(r"\d", tok) for tok in residual):
        return True
    # Multi-token non-generic residue (e.g. "victus gaming") is enough.
    if len(residual) >= 2:
        return True
    # Single long token that looks like a model family word (bravia, vivobook).
    only = residual[0]
    if len(only) >= 5 and only.isalpha():
        return True
    return False
