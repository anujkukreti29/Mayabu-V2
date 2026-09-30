"""Guards for titles recovered into the smartphone category.

Storage or 5G text alone is not enough. A tablet, watch, hotspot, or
accessory that mentions gigabytes stays out of the public phone catalog.
"""

from __future__ import annotations

import re

_NOT_PHONE = re.compile(
    r"\b("
    r"tablet|ipad|galaxy\s*tab\b|smart\s*watch|galaxy\s*watch|watch\d|"
    r"feature\s*phone|"
    r"dongle|hotspot|mifi|data\s*card|"
    r"case|cover|tempered|screen\s*guard|charger|cable|power\s*bank|"
    r"earbuds?|headphones?|buds\b|"
    r"monitor|laptop|notebook|"
    r"display\s+only|replacement\s+display"
    r")\b",
    re.I,
)
_PHONE_BRAND = re.compile(
    r"\b(apple|iphone|samsung|galaxy|oneplus|google|pixel|xiaomi|redmi|poco|realme|"
    r"motorola|moto|nothing|vivo|oppo|iqoo|infinix|tecno|lava|nokia)\b",
    re.I,
)
_PHONE_SHAPE = re.compile(r"\b(\d+\s*gb|5g)\b", re.I)
_FRAGMENT = re.compile(
    r"^(response time|exposure mode|refresh rate|\d+(\.\d+)?\s*cm\s*\(|\d+\s*gb ram\b|\d+\s*mah\b|battery)",
    re.I,
)


def phone_recovery_verdict(title: str) -> str:
    """Return correct_smartphone, wrong_category, fragment, or ambiguous."""
    text = (title or "").strip()
    if not text or _FRAGMENT.search(text):
        return "fragment"
    if _NOT_PHONE.search(text):
        return "wrong_category"
    if _PHONE_BRAND.search(text) and _PHONE_SHAPE.search(text):
        return "correct_smartphone"
    if re.search(r"\b(iphone|smartphone|mobile phone)\b", text, re.I):
        return "correct_smartphone"
    return "ambiguous"
