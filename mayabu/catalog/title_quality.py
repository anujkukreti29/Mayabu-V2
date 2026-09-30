"""Title quality gates for discovery / enrichment identity."""

from __future__ import annotations

import re

# Marketing bullets / feature lists masquerading as product names.
_BULLET_MARKERS = (
    "mp camera",
    "mah battery",
    "amoled",
    "ips display",
    "free shipping",
    "warranty",
    "cash on delivery",
    "bank offer",
    "exchange offer",
    "emi from",
    "suitable for:",
    "slow motion",
    "oversampling",
    "frames per second",
    "dual pixel",
    "collaborative is",
)

_FEATURE_COMMA_RE = re.compile(
    r"^(?:[^,]{2,40},\s*){3,}[^,]{2,80}$",
    re.I,
)


_BRAND_ONLY = frozenset(
    {
        "apple",
        "samsung",
        "oneplus",
        "xiaomi",
        "redmi",
        "realme",
        "vivo",
        "oppo",
        "google",
        "pixel",
        "sony",
        "canon",
        "nikon",
        "lg",
        "dell",
        "hp",
        "lenovo",
        "asus",
        "acer",
        "msi",
        "nothing",
        "motorola",
        "moto",
        "jbl",
        "boat",
        "noise",
        "croma",
        "nokia",
        "honor",
        "iqoo",
        "poco",
    }
)


def is_marketing_bullet_title(title: str | None) -> bool:
    """True when text looks like Flipkart/feature bullets, not a product name."""
    text = " ".join(str(title or "").split()).strip()
    if not text:
        return True
    if len(text) < 8:
        return True
    # Brand-only PLP labels are not product identity (common Amazon failure).
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    if len(tokens) <= 2 and all(t in _BRAND_ONLY for t in tokens):
        return True
    lower = text.lower()
    # Too many commas → feature list
    if text.count(",") >= 3 and _FEATURE_COMMA_RE.match(text):
        return True
    if text.count(",") >= 4:
        return True
    # Starts with numeric feature specs without brand/model context
    if re.match(r"^\d+\s*(mp|mah|gb|tb|hz|fps)\b", lower):
        return True
    if sum(1 for m in _BULLET_MARKERS if m in lower) >= 2:
        return True
    # Whole title is a comma/ampersand feature chain with no obvious brand token
    if "," in text and not re.search(
        r"\b(samsung|apple|iphone|oneplus|xiaomi|redmi|realme|vivo|oppo|google|pixel|"
        r"sony|canon|nikon|lg|sony|dell|hp|lenovo|asus|acer|msi|nothing|motorola|moto|"
        r"jbl|boat|noise|croma)\b",
        lower,
    ):
        if text.count(",") >= 2 or "&" in text:
            return True
    return False


def pick_best_title(*candidates: str | None) -> str | None:
    for raw in candidates:
        text = sanitize_product_title(raw)
        if not text or is_marketing_bullet_title(text):
            continue
        if len(text) > 280:
            text = text[:280].rsplit(" ", 1)[0].strip()
        return text
    return None


_SEO_SUFFIX_RE = re.compile(
    r"(?:"
    r"\s*[\|\-–—:]\s*|"
    r"\s+"
    r")"
    r"(?:"
    r"online\s+at\s+best\s+price(?:\s+on\s+[\w.]+)?|"
    r"best\s+price\s+on\s+[\w.]+|"
    r"buy\s+online|"
    r"shop\s+online|"
    r"free\s+delivery|"
    r"with\s+offer(?:s)?|"
    r"emi\s+available|"
    r"exchange\s+available|"
    r"lowest\s+price|"
    r"flipkart\.com|"
    r"amazon\.in|"
    r"croma\.com"
    r")\.?\s*$",
    re.I,
)

_SEO_INLINE_RE = re.compile(
    r"\s*\((?:buy\s+online|best\s+price|with\s+offer[^)]*)\)\s*",
    re.I,
)


def sanitize_product_title(title: str | None) -> str | None:
    """Strip Flipkart/Amazon SEO filler while preserving brand + model + config."""
    text = " ".join(str(title or "").split()).strip()
    if not text:
        return None
    prev = None
    while prev != text:
        prev = text
        text = _SEO_SUFFIX_RE.sub("", text).strip(" -|–—:")
        text = _SEO_INLINE_RE.sub(" ", text)
        text = " ".join(text.split()).strip()
    return text or None


__all__ = [
    "is_marketing_bullet_title",
    "pick_best_title",
    "sanitize_product_title",
]
