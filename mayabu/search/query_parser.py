"""Query normalization and deterministic laptop intent/spec extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from mayabu_common import FAMILY_PATTERNS, MODEL_CODE_RE, extract_specs, normalize_specs

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
    "avita",
    "infinix",
    "honor",
    "realme",
    "xiaomi",
    "microsoft",
    "razer",
    "gigabyte",
}
SERIES_ALIASES = {
    "vivbook": "vivobook",
    "vivo book": "vivobook",
    "mac book": "macbook",
    "think pad": "thinkpad",
    "idea pad": "ideapad",
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
}


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


def normalize_query(query: str) -> str:
    text = re.sub(r"\brom\b", " storage ", (query or "").lower())
    text = re.sub(r"[^a-z0-9.+\-_/\s]", " ", text)
    for wrong, right in SERIES_ALIASES.items():
        text = re.sub(rf"\b{re.escape(wrong)}\b", right, text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_brand(text: str) -> str | None:
    tokens = set(text.split())
    return next((brand for brand in sorted(BRANDS) if brand in tokens), None)


def _extract_family(text: str) -> str | None:
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
    # Capture hyphenated commercial SKUs such as X1407CA-LY1581WS.
    for token in re.findall(r"\b[a-z0-9]{3,12}(?:-[a-z0-9]{3,12})+\b", text, re.I):
        if any(ch.isdigit() for ch in token):
            found.add(token.upper())
    return tuple(sorted(found, key=lambda x: (-len(x), x)))


def parse_query(query: str) -> ParsedQuery:
    raw = query or ""
    norm = normalize_query(raw)
    brand = _extract_brand(norm)
    family = _extract_family(norm)
    extracted = normalize_specs(extract_specs(norm, "laptop"))
    model_codes = _extract_model_codes(norm)
    if model_codes:
        extracted["model_codes"] = list(model_codes)
        extracted["model_code"] = model_codes[0].lower()
    if brand:
        extracted["brand"] = brand
    if family:
        extracted["family"] = family

    tokens = [token for token in norm.split() if token not in _STOP_WORDS]
    explicit_laptop = any(
        term in norm for term in ("laptop", "notebook", "chromebook", "macbook")
    )
    signals = sum(
        bool(extracted.get(key))
        for key in (
            "brand",
            "family",
            "model_code",
            "cpu_series",
            "cpu_models",
            "ram_gb",
            "storage_gb",
            "gpu",
            "screen_inch",
        )
    )
    category = "laptop" if explicit_laptop or brand or family or signals >= 1 else None
    quality = min(
        100.0, len(tokens) * 3.0 + signals * 13.0 + (18.0 if model_codes else 0.0)
    )
    relevant = category == "laptop" and (explicit_laptop or quality >= 12)
    if model_codes:
        intent = "exact_product"
    elif family and signals >= 2:
        intent = "variant_search"
    elif category == "laptop":
        intent = "category_search"
    else:
        intent = "irrelevant"

    return ParsedQuery(
        raw_query=raw,
        normalized_query=norm,
        detected_category=category,
        detected_brand=brand,
        detected_specs={
            k: v for k, v in extracted.items() if v not in (None, "", [], {})
        },
        quality_score=quality,
        is_relevant=relevant,
        intent=intent,
        family=family,
        model_codes=model_codes,
    )
