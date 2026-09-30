"""Deterministic retailer marketing-noise stripping for matching.

Strips promotional phrases only. Never removes product identity tokens.
"""

from __future__ import annotations

import re

MATCHING_VERSION = 2

_NOISE_PHRASES = (
    r"best\s+seller",
    r"bestseller",
    r"new\s+launch",
    r"newly\s+launched",
    r"no\s+cost\s+emi",
    r"zero\s+cost\s+emi",
    r"\bemi\b",
    r"bank\s+offer",
    r"bank\s+discount",
    r"instant\s+discount",
    r"exchange\s+offer",
    r"exchange\s+bonus",
    r"free\s+delivery",
    r"free\s+shipping",
    r"limited\s+offer",
    r"limited\s+time",
    r"special\s+price",
    r"deal\s+of\s+the\s+day",
    r"today'?s\s+deal",
    r"with\s+alexa",
    r"works?\s+with\s+alexa",
    r"google\s+assistant",
    r"smart\s+features?",
    r"inclusive\s+of\s+all\s+taxes",
    r"including\s+gst",
    r"\d+\s*%\s*off",
    r"upto\s+\d+\s*%",
    r"save\s+₹?\s*[\d,]+",
    r"emi\s+(?:starts?|from)\s+₹?\s*[\d,]+",
    r"₹?\s*[\d,]+\s*/\s*month",
    r"per\s+month",
)

_NOISE_RE = re.compile(r"(?:^|\s)(?:" + "|".join(_NOISE_PHRASES) + r")(?:\s|$)", re.I)
_MULTI_SPACE_RE = re.compile(r"\s+")


def strip_matching_noise(title: str | None) -> str:
    """Return title with common retailer promo noise removed."""
    text = str(title or "").strip()
    if not text:
        return ""
    cleaned = _NOISE_RE.sub(" ", text)
    return _MULTI_SPACE_RE.sub(" ", cleaned).strip()
