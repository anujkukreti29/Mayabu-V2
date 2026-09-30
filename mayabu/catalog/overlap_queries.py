"""Exact-identity discovery queries for single-store products.

Model codes outrank family names. Retailers that already have a public offer
are not searched again.
"""

from __future__ import annotations

import re
from typing import Any

_CODE_RE = re.compile(r"\b(?=[A-Z0-9-]{5,}\b)(?=[A-Z0-9-]*\d)[A-Z0-9-]+\b")
_NOT_A_MODEL = {
    "HDR10", "HDR10+", "DOLBY", "HDMI", "USB", "WIFI", "QLED", "OLED",
    "UHD", "ANDROID", "GOOGLE", "SMART", "ULTRA", "1080P", "720P", "2160P",
}

_DEEP = ("reliancedigital", "flipkart")
_PHONE = ("reliancedigital", "flipkart", "poorvika")
_LAPTOP = ("reliancedigital", "flipkart", "poorvika")


def usable_retailers(category: str, *, healthy: set[str] | None = None) -> list[str]:
    cat = (category or "").lower()
    if cat in {"laptop", "smartphone"}:
        ordered = list(_LAPTOP if cat == "laptop" else _PHONE)
    else:
        ordered = list(_DEEP)
    if healthy is not None and "vijaysales" in healthy:
        ordered.append("vijaysales")
    if healthy is not None:
        ordered = [name for name in ordered if name in healthy]
    return ordered


def missing_retailers(category: str, attached: set[str], *, healthy: set[str] | None = None) -> list[str]:
    have = {str(name).lower() for name in attached}
    return [name for name in usable_retailers(category, healthy=healthy) if name not in have]


def _camera_body_code(token: str) -> bool:
    """Manufacturer body codes. Focal lengths and lens mounts are not bodies."""
    if re.search(r"\d+-\d+", token) or token.endswith("MM") or token.startswith(("RF", "EF", "XF")):
        return False
    return bool(
        re.search(
            r"(ILCE|ILME|EOS|ZVE|ZV-?E?\d|FZ\d|D\d{3,4}|Z\d|EM\d|A7|FX\d|X-?H\d)",
            token,
        )
    )


def _codes(specs: dict[str, Any] | None, title: str) -> list[str]:
    specs = specs or {}
    found: list[str] = []
    raw = specs.get("model_codes") or specs.get("model_code") or specs.get("manufacturer_model")
    if isinstance(raw, str):
        found.append(raw)
    elif isinstance(raw, (list, tuple)):
        found.extend(str(item) for item in raw if item)
    for match in _CODE_RE.findall((title or "").upper()):
        if match not in found:
            found.append(match)
    cleaned = []
    for code in found:
        token = re.sub(r"\s+", "", str(code).upper())
        if token in _NOT_A_MODEL or re.search(r"(HZ|YEAR|MONTH|WATT|MAH|BIT|CORE|HRS|HOURS|BUTTON|RPM)$", token):
            continue
        if re.fullmatch(r"\d+-IN-\d+", token):
            continue
        if token in {"SPACE1", "DRAWER2L", "1TURBO"}:
            continue
        if len(token) >= 5 and any(ch.isdigit() for ch in token) and token not in cleaned:
            cleaned.append(token)
    return cleaned[:6]


def _storage_token(token: str) -> bool:
    return bool(
        re.fullmatch(r"\d+GB", token)
        or re.fullmatch(r"\d+GB-\d+GB", token)
        or re.fullmatch(r"\d{4,5}", token)
    )


def _cpu_only(token: str) -> bool:
    """Bare processor SKUs are not a laptop product identity."""
    return bool(re.fullmatch(r"\d{4,5}[A-Z]{1,3}", token))


def overlap_query(category: str, brand: str | None, title: str, specs: dict[str, Any] | None) -> str | None:
    """Strongest identity string for a missing-retailer search. None if too weak."""
    specs = specs or {}
    codes = _codes(specs, title)
    cat = (category or "").lower()
    if codes:
        if cat == "smartphone":
            code = next((item for item in codes if not _storage_token(item)), None)
            if not code:
                return None
            storage = specs.get("storage_gb")
            color = str(specs.get("color") or "").strip()
            parts = [code]
            if storage:
                parts.append(f"{int(storage)}GB")
            if color and len(color) <= 24:
                parts.append(color)
            return " ".join(parts)
        if cat == "camera":
            body = next((code for code in codes if _camera_body_code(code)), None)
            if not body:
                return None
            kind = "body" if specs.get("body_only") else ("kit" if specs.get("kit_lens") else "")
            return " ".join(part for part in (body, kind) if part)
        if cat == "laptop":
            sku = next((code for code in codes if not _cpu_only(code)), None)
            if sku:
                return sku
        else:
            return codes[0]
    family = str(specs.get("family") or "").strip()
    brand_s = str(brand or specs.get("brand") or "").strip()
    if cat == "television":
        size = specs.get("screen_size_inch") or specs.get("screen_inch")
        if brand_s and family and size:
            return f"{brand_s} {family} {int(float(size))} inch tv"
        return None
    if cat == "refrigerator":
        capacity = specs.get("capacity_l")
        door = str(specs.get("door_type") or "").replace("_", " ").strip()
        if brand_s and capacity and door:
            return f"{brand_s} {capacity} L {door} refrigerator"
        return None
    if cat == "washing_machine":
        return None
    if cat == "laptop" and family and specs.get("cpu_models"):
        cpu = specs.get("cpu_models")
        cpu_s = cpu[-1] if isinstance(cpu, list) and cpu else str(cpu or "")
        if ":" in cpu_s:
            cpu_s = cpu_s.split(":")[-1]
        ram = specs.get("ram_gb")
        storage = specs.get("storage_gb")
        parts = [brand_s, family.replace("_", " "), cpu_s.replace("_", " ")]
        if ram:
            parts.append(f"{ram}GB")
        if storage:
            parts.append(f"{storage}GB")
        query = " ".join(part for part in parts if part).strip()
        return query or None
    return None
