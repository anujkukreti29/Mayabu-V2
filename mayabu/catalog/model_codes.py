"""Central model-code extraction / normalization (operator-facing, not a score)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from mayabu_common import MODEL_CODE_RE, ascii_fold

_JUNK_CODES = frozenset(
    {
        "WIRED",
        "WIRELESS",
        "BLUETOOTH",
        "BLACK",
        "WHITE",
        "CAMERA",
        "SMART",
        "ANDROID",
        "IPHONE",
        "GALAXY",
        "LAPTOP",
        "TABLET",
        "PHONE",
        "MOBILE",
        "HDMI",
        "USB",
        "TYPEC",
        "ANC",
        "ACTIVE",
        "NOISE",
        "CANCEL",
        "PRO",
        "MAX",
        "PLUS",
        "MINI",
        "LITE",
        "ULTRA",
        "KIT",
        "BODY",
        "ONLY",
        "5G",
        "4G",
        "LTE",
        "AMOLED",
        "OLED",
        "LED",
        "QLED",
        "FPS",
        "UHD",
        "FHD",
        "RAW",
        "HDMI",
    }
)

_PHONE_MODEL_RE = re.compile(
    r"\b("
    r"SM-[A-Z0-9]{4,10}|"
    r"CPH\d{4,5}|"
    r"RMX\d{4}|"
    r"MZB\d{4,}[A-Z0-9]*|"
    r"M\d{4}[A-Z0-9]{2,6}|"
    r"XQ-[A-Z0-9]{4,8}|"
    r"A\d{4}|"  # Apple/region-ish — kept only with digit+letter mix check below
    r"GE\d{4}|"
    r"LE\d{4}|"
    r"IN\d{4}"
    r")\b",
    re.I,
)


@dataclass(frozen=True, slots=True)
class ModelCodeHit:
    code: str
    source: str
    reason: str


def normalize_model_code(raw: str | None) -> str | None:
    text = str(raw or "").strip().upper()
    if not text:
        return None
    text = text.replace(" ", "")
    text = re.sub(r"[^A-Z0-9\-/]", "", text)
    text = text.strip("-/")
    if not text or text in _JUNK_CODES:
        return None
    if text.isalpha() and len(text) < 8:
        return None
    if text.isdigit() and len(text) < 6:
        return None
    if len(text) < 4:
        return None
    # Flipkart internal product ids look like MOBH… / MOBF… — not manufacturer codes.
    if re.fullmatch(r"MOB[A-Z0-9]{8,}", text):
        return None
    # Reject pure marketing tokens like 12FPS3-ish when too short prefix
    if re.fullmatch(r"\d{1,3}FPS\d?", text):
        return None
    return text


def extract_model_codes(
    *,
    title: str | None = None,
    specs: dict[str, Any] | None = None,
    structured: dict[str, Any] | None = None,
    category: str | None = None,
) -> list[ModelCodeHit]:
    hits: list[ModelCodeHit] = []
    seen: set[str] = set()

    def _add(raw: Any, source: str, reason: str) -> None:
        code = normalize_model_code(str(raw) if raw is not None else None)
        if not code or code in seen:
            return
        seen.add(code)
        hits.append(ModelCodeHit(code=code, source=source, reason=reason))

    specs = specs or {}
    for code in specs.get("model_codes") or []:
        _add(code, "specs.model_codes", "existing_spec")
    for key in ("model", "model_number", "mpn", "sku"):
        if specs.get(key):
            _add(specs[key], f"specs.{key}", "spec_field")

    structured = structured or {}
    for key in ("sku", "mpn", "model", "productID", "gtin13", "gtin"):
        if structured.get(key):
            _add(structured[key], f"structured.{key}", "structured_data")

    text = ascii_fold(title or "")
    if category == "smartphone":
        for m in _PHONE_MODEL_RE.finditer(text):
            _add(m.group(1), "title.phone_pattern", "phone_model_re")
    for m in MODEL_CODE_RE.finditer(text):
        val = next((g for g in m.groups() if g), "")
        _add(val, "title.model_re", "generic_model_re")

    return hits


def model_codes_list(**kwargs: Any) -> list[str]:
    return [h.code for h in extract_model_codes(**kwargs)]


__all__ = [
    "ModelCodeHit",
    "extract_model_codes",
    "model_codes_list",
    "normalize_model_code",
]
