"""Category-aware query normalization and intent extraction.

Generic intent (brand, price, model codes) is shared.
Category adapters contribute only allowlisted category-specific fields.
Unknown does NOT default to laptop.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from mayabu.domain.categories.registry import (
    ACCESSORY_REJECT_RE,
    detect_category_result,
    extract_category_specs,
)
from mayabu.search.category_registry import (
    get_search_category,
    public_search_categories,
    resolve_category_alias,
    validate_public_category,
)
from mayabu_common import FAMILY_PATTERNS, MODEL_CODE_RE, normalize_specs, resolve_brand

BRANDS = {
    "asus",
    "lenovo",
    "hp",
    "dell",
    "acer",
    "apple",
    "msi",
    "samsung",
    "lg",
    "sony",
    "boat",
    "boAt",
    "jbl",
    "oneplus",
    "xiaomi",
    "realme",
    "vivo",
    "oppo",
    "google",
    "nothing",
    "canon",
    "nikon",
    "avita",
    "infinix",
    "honor",
    "microsoft",
    "razer",
    "gigabyte",
    "ifb",
    "whirlpool",
    "haier",
    "panasonic",
    "philips",
    "bose",
    "sennheiser",
}

SERIES_ALIASES = {
    "vivbook": "vivobook",
    "vivo book": "vivobook",
    "mac book": "macbook",
    "think pad": "thinkpad",
    "idea pad": "ideapad",
    "galaxy buds": "galaxy buds",
}

_STOP_WORDS = {
    "with",
    "and",
    "the",
    "for",
    "best",
    "buy",
    "price",
    "online",
    "india",
    "offer",
    "deals",
    "under",
    "below",
    "above",
    "between",
    "rs",
    "inr",
}

# Budget patterns require explicit budget language — never bare storage/size/SKU digits.
_UNDER_RE = re.compile(
    r"\b(?:under|below|upto|up\s*to|less\s*than|max(?:imum)?)\s*(?:rs\.?|₹|inr)?\s*"
    r"(\d{1,7}(?:\.\d+)?)\s*(k|lakh|lac|thousand)?\b",
    re.I,
)
_ABOVE_RE = re.compile(
    r"\b(?:above|over|more\s*than|min(?:imum)?|from)\s*(?:rs\.?|₹|inr)?\s*"
    r"(\d{1,7}(?:\.\d+)?)\s*(k|lakh|lac|thousand)?\b",
    re.I,
)
_BETWEEN_RE = re.compile(
    r"\bbetween\s*(?:rs\.?|₹|inr)?\s*(\d{1,7}(?:\.\d+)?)\s*(k|lakh|lac|thousand)?\s*"
    r"(?:and|to|-)\s*(?:rs\.?|₹|inr)?\s*(\d{1,7}(?:\.\d+)?)\s*(k|lakh|lac|thousand)?\b",
    re.I,
)
_BUDGET_K_RE = re.compile(
    r"\b(?:budget|price|cost)\s*(?:of|is|around|~)?\s*(?:rs\.?|₹|inr)?\s*"
    r"(\d{1,7}(?:\.\d+)?)\s*(k|lakh|lac)?\b",
    re.I,
)

# Strong product-identity hints when alias words are absent.
_STRONG_PHONE_RE = re.compile(
    r"\b(galaxy\s*s\d{1,2}|iphone\s*\d{1,2}|pixel\s*\d{1,2}|oneplus\s*\d+|redmi\s*(?:note\s*)?\d+)\b",
    re.I,
)
_STRONG_HEADPHONE_RE = re.compile(r"\b(wh[\s-]?\d{3,4}(?:xm\d)?|quietcomfort|sony\s*xm\d)\b", re.I)
_STRONG_TWS_RE = re.compile(r"\b(galaxy\s*buds|airdopes|airpods|oneplus\s*buds)\b", re.I)
_STRONG_TV_RE = re.compile(r"\b(\d{2}\s*(?:\"|inch)|oled|qled|bravia|smart\s*tv)\b", re.I)
_STRONG_FRIDGE_RE = re.compile(r"\b(\d{2,4}\s*l(?:itre|iter)?s?|double\s*door|frost\s*free)\b", re.I)
_STRONG_WASHER_RE = re.compile(r"\b(\d{1,2}(?:\.\d)?\s*kg|front\s*load|top\s*load|fully\s*automatic)\b", re.I)


@dataclass(slots=True)
class ParsedQuery:
    raw_query: str
    normalized_query: str
    detected_category: str | None
    detected_brand: str | None
    detected_specs: dict[str, object] = field(default_factory=dict)
    quality_score: float = 0.0
    is_relevant: bool = False
    intent: str = "unknown"
    family: str | None = None
    model_codes: tuple[str, ...] = ()
    min_price: int | None = None
    max_price: int | None = None
    explicit_category: str | None = None
    search_mode: str = "category"  # category | cross_category | accessory | empty
    category_filters: dict[str, Any] = field(default_factory=dict)
    category_confidence: str = "unknown"


def normalize_query(query: str) -> str:
    text = re.sub(r"\brom\b", " storage ", (query or "").lower())
    text = re.sub(r"[^a-z0-9.+\-_/\s]", " ", text)
    for wrong, right in SERIES_ALIASES.items():
        text = re.sub(rf"\b{re.escape(wrong)}\b", right, text)
    return re.sub(r"\s+", " ", text).strip()


def _money(value: str, unit: str | None) -> int:
    number = float(value)
    unit_l = (unit or "").lower()
    if unit_l in {"k", "thousand"}:
        number *= 1_000
    elif unit_l in {"lakh", "lac"}:
        number *= 100_000
    return int(round(number))


def extract_price_intent(text: str) -> tuple[int | None, int | None]:
    """Conservative budget extraction — never treat storage/size/SKU as prices."""
    min_price: int | None = None
    max_price: int | None = None

    between = _BETWEEN_RE.search(text)
    if between:
        low = _money(between.group(1), between.group(2))
        high = _money(between.group(3), between.group(4))
        return (min(low, high), max(low, high))

    under = _UNDER_RE.search(text)
    if under:
        max_price = _money(under.group(1), under.group(2))

    above = _ABOVE_RE.search(text)
    if above:
        min_price = _money(above.group(1), above.group(2))

    if max_price is None and min_price is None:
        budget = _BUDGET_K_RE.search(text)
        if budget:
            max_price = _money(budget.group(1), budget.group(2))

    return min_price, max_price


def _extract_brand(text: str) -> str | None:
    resolved = resolve_brand(text)
    if resolved:
        return str(resolved).lower()
    tokens = set(text.lower().split())
    for brand in sorted(BRANDS, key=len, reverse=True):
        if brand.lower() in tokens:
            return brand.lower()
    return None


def _extract_family_laptop(text: str) -> str | None:
    for pattern in FAMILY_PATTERNS:
        match = re.search(pattern, text, re.I)
        if match:
            return re.sub(r"\s+", " ", match.group(1).lower()).strip()
    for family in (
        "vivobook",
        "zenbook",
        "expertbook",
        "macbook air",
        "macbook pro",
        "macbook",
        "ideapad",
        "thinkpad",
        "inspiron",
        "pavilion",
        "aspire",
        "loq",
        "legion",
        "tuf",
        "rog",
        "victus",
    ):
        if family in text:
            return family
    return None


def _extract_model_codes(text: str) -> tuple[str, ...]:
    found: set[str] = set()
    for match in MODEL_CODE_RE.finditer(text):
        code = next((group for group in match.groups() if group), None)
        if code:
            found.add(code.upper())
    for token in re.findall(r"\b[a-z0-9]{3,12}(?:-[a-z0-9]{3,12})+\b", text, re.I):
        if any(ch.isdigit() for ch in token):
            found.add(token.upper())
    # Headphone-style commercial codes.
    for token in re.findall(r"\bWH[\s-]?\d{3,4}(?:XM\d)?\b", text, re.I):
        found.add(re.sub(r"[\s-]+", "", token.upper()))
    return tuple(sorted(found, key=lambda x: (-len(x), x)))


def _infer_category(norm: str, *, brand: str | None, model_codes: tuple[str, ...]) -> tuple[str | None, str]:
    if ACCESSORY_REJECT_RE.search(norm):
        return "accessory", "high"

    detection = detect_category_result(query=norm, title=norm)
    if detection.category == "accessory":
        return "accessory", detection.confidence

    alias = resolve_category_alias(norm)
    if alias and get_search_category(alias) and get_search_category(alias).public_search_enabled:
        return alias, "high"

    if detection.category in public_search_categories() and detection.confidence in {"high", "medium"}:
        return detection.category, detection.confidence

    if _STRONG_PHONE_RE.search(norm):
        return "smartphone", "medium"
    if _STRONG_HEADPHONE_RE.search(norm):
        return "headphones", "medium"
    if _STRONG_TWS_RE.search(norm):
        return "tws", "medium"
    if _STRONG_TV_RE.search(norm) and ("tv" in norm or "oled" in norm or "qled" in norm or "bravia" in norm):
        return "television", "medium"
    if _STRONG_FRIDGE_RE.search(norm) and ("fridge" in norm or "refrigerator" in norm):
        return "refrigerator", "medium"
    if _STRONG_WASHER_RE.search(norm) and ("wash" in norm or "washer" in norm):
        return "washing_machine", "medium"

    # Model-code-only queries: leave category open for cross-search unless alias exists.
    if model_codes and not alias:
        return None, "low"

    # Brand-only → cross-category.
    if brand and not alias:
        return None, "low"

    if detection.category in public_search_categories():
        return detection.category, detection.confidence or "low"

    return None, "unknown"


def _category_intent_specs(norm: str, category: str | None) -> dict[str, Any]:
    if not category or category in {"unknown", "accessory"}:
        return {}
    if category not in public_search_categories() and category != "laptop":
        # Still allow parsing for public categories only in search path.
        info = get_search_category(category)
        if info is None or not info.public_search_enabled:
            return {}
    specs = normalize_specs(extract_category_specs(norm, category))
    info = get_search_category(category)
    if info is None:
        return specs
    allowed = set(info.filterable_keys) | set(info.display_spec_keys) | {
        "brand",
        "family",
        "model_codes",
        "model_code",
    }
    return {k: v for k, v in specs.items() if k in allowed and v not in (None, "", [], {})}


def parse_query(
    query: str,
    *,
    explicit_category: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    category_filters: dict[str, Any] | None = None,
) -> ParsedQuery:
    raw = query or ""
    norm = normalize_query(raw)
    brand = _extract_brand(norm)
    model_codes = _extract_model_codes(norm)
    inferred_min, inferred_max = extract_price_intent(norm)
    # Explicit API price bounds override inferred budget.
    final_min = min_price if min_price is not None else inferred_min
    final_max = max_price if max_price is not None else inferred_max

    explicit: str | None = None
    if explicit_category:
        info = validate_public_category(explicit_category)
        explicit = info.slug

    inferred, confidence = _infer_category(norm, brand=brand, model_codes=model_codes)
    category = explicit or (None if inferred == "accessory" else inferred)

    if inferred == "accessory" and not explicit:
        return ParsedQuery(
            raw_query=raw,
            normalized_query=norm,
            detected_category="accessory",
            detected_brand=brand,
            quality_score=0.0,
            is_relevant=False,
            intent="accessory",
            search_mode="accessory",
            category_confidence="high",
            min_price=final_min,
            max_price=final_max,
        )

    family = None
    extracted: dict[str, Any] = {}
    if category:
        extracted = _category_intent_specs(norm, category)
        family = extracted.get("family")
        if category == "laptop" and not family:
            family = _extract_family_laptop(norm)
            if family:
                extracted["family"] = family
    elif brand:
        # Cross-category: keep generic brand/model only.
        family = _extract_family_laptop(norm)

    if model_codes:
        extracted["model_codes"] = list(model_codes)
        extracted["model_code"] = model_codes[0].lower()
    if brand:
        extracted["brand"] = brand
    if family:
        extracted["family"] = family

    # Merge validated structured filters (allowlisted per category).
    filters: dict[str, Any] = {}
    if category and category_filters:
        info = get_search_category(category)
        if info:
            for key, value in category_filters.items():
                if key in info.filterable_keys and value not in (None, "", [], {}):
                    filters[key] = value
                    extracted[key] = value

    tokens = [token for token in norm.split() if token not in _STOP_WORDS]
    signals = sum(1 for v in extracted.values() if v not in (None, "", [], {}))
    quality = min(
        100.0,
        len(tokens) * 3.0 + signals * 10.0 + (18.0 if model_codes else 0.0) + (8.0 if brand else 0.0),
    )

    if model_codes:
        intent = "exact_product"
        is_relevant = True
        search_mode = "category" if category else "cross_category"
    elif category:
        search_mode = "category"
        is_relevant = True
        if family and signals >= 2:
            intent = "variant_search"
        else:
            intent = "category_search"
    elif brand or tokens:
        search_mode = "cross_category"
        is_relevant = True
        intent = "cross_category_search" if brand else "broad_search"
        category = None
        confidence = "low"
    else:
        search_mode = "empty"
        is_relevant = False
        intent = "irrelevant"

    return ParsedQuery(
        raw_query=raw,
        normalized_query=norm,
        detected_category=category,
        detected_brand=brand,
        detected_specs={k: v for k, v in extracted.items() if v not in (None, "", [], {})},
        quality_score=quality,
        is_relevant=is_relevant,
        intent=intent,
        family=str(family).lower() if family else None,
        model_codes=model_codes,
        min_price=final_min,
        max_price=final_max,
        explicit_category=explicit,
        search_mode=search_mode,
        category_filters=filters,
        category_confidence=confidence if not explicit else "high",
    )
