"""Deterministic query-intent adjustments. No model calls."""

from __future__ import annotations

import re

_GAMING_RE = re.compile(
    r"(\bgaming\s+(laptop|notebook)\b|\b(rog|tuf|legion|loq|victus|omen|nitro|predator|alienware|katana|cyborg|strix|rtx|gtx|geforce|radeon|helios|pulse)\b)",
    re.I,
)
_CAMERA_BODY_RE = re.compile(
    r"\b(mirrorless|dslr|camera body|eos|alpha|lumix|ilce|powershot)\b",
    re.I,
)
_CAMERA_DOWNRANK_RE = re.compile(
    r"\b(lens only|prime lens|zoom lens|telephoto|batis|kids?\s+camera|toy camera|tripod|camera bag|memory card|filter kit|designed for)\b",
    re.I,
)
_GENERIC_CAMERA_TITLE_RE = re.compile(
    r"^(dslr/?slr camera|digital camera|mirrorless camera|camera)$",
    re.I,
)


def intent_adjustment(*, query: str, category: str, text: str) -> float:
    q = (query or "").lower()
    cat = (category or "").lower()
    blob = (text or "").lower()
    score = 0.0
    if "gaming" in q and cat == "laptop":
        score += 48.0 if _GAMING_RE.search(blob) else -36.0
    if "oled" in q and "oled" in blob:
        score += 24.0
    if "qled" in q and "qled" in blob:
        score += 24.0
    if "front load" in q and cat == "washing_machine":
        score += 20.0 if "front" in blob else -12.0
    if "top load" in q and cat == "washing_machine":
        score += 20.0 if "top" in blob else -12.0
    if "noise" in q and "cancell" in q and ("anc" in blob or "noise" in blob):
        score += 16.0
    if "mirrorless" in q and "mirrorless" in blob:
        score += 20.0
    # Generic "camera" should surface bodies, not lenses, toys, or accessories.
    if cat == "camera" and re.search(r"\bcameras?\b", q) and "lens" not in q:
        if _GENERIC_CAMERA_TITLE_RE.match(blob.strip()) or _CAMERA_DOWNRANK_RE.search(blob):
            score -= 55.0 if _GENERIC_CAMERA_TITLE_RE.match(blob.strip()) or "designed for" in blob else 40.0
        elif _CAMERA_BODY_RE.search(blob) or "camera" in blob:
            score += 18.0
    return score
