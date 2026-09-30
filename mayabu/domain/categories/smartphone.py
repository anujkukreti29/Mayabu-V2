"""Smartphone category adapter."""

from __future__ import annotations

import re
from typing import Any

from mayabu.domain.categories.base import conflict_numeric, model_code_conflict
from mayabu_common import MODEL_CODE_RE, RAM_RE, STORAGE_RE, ascii_fold, resolve_brand

_DISPLAY_RE = re.compile(r"\b(\d{1,2}(?:\.\d)?)\s*(?:\"|''|inch|inches|in)\b", re.I)
_CHIPSET_RE = re.compile(
    r"\b("
    r"snapdragon\s*\d{3,4}[a-z]?|"
    r"dimensity\s*\d{3,4}|"
    r"helio\s*[a-z]?\d{2,4}|"
    r"exynos\s*\d{4}|"
    r"tensor\s*[a-z]?\d?|"
    r"a1[5-9]\s*bionic|a1[5-9]|"
    r"bionic|"
    r"kirin\s*\d{3,4}"
    r")\b",
    re.I,
)
_NETWORK_RE = re.compile(r"\b(5g|4g|lte)\b", re.I)
_FAMILY_RE = re.compile(
    r"\b("
    r"galaxy\s+[a-z]\d{1,2}(?:\s*(?:fe|plus|\+|ultra|5g))?|"
    r"iphone\s*(?:\d{1,2}|se|x[rs]?)(?:\s*(?:pro(?:\s*max)?|plus|mini))?|"
    r"pixel\s*\d{1,2}(?:\s*(?:pro|a|xl))?|"
    r"redmi\s*(?:note\s*)?\d{1,2}(?:\s*(?:pro|plus|\+|5g))?|"
    r"poco\s*[a-z]?\d{1,2}(?:\s*(?:pro|5g))?|"
    r"oneplus\s*(?:nord\s*(?:ce\s*)?)?\d*(?:\s*(?:lite|pro|5g))?|"
    r"nord\s*(?:ce\s*)?\d*(?:\s*(?:lite|5g))?|"
    r"nothing\s*phone\s*\(?\d\)?|"
    r"moto\s*[a-z]?\d+"
    r")\b",
    re.I,
)
# Keep aligned with mayabu.search.public_offers.extract_color_token — titles/PDPs
# routinely expose retailer color names (Burgundy, Glacier, Ultramarine, …).
_COLOR_RE = re.compile(
    r"\b(black|white|silver|gold|blue|red|green|pink|purple|grey|gray|titanium|"
    r"natural|desert|ultramarine|teal|midnight|starlight|graphite|burgundy|"
    r"glacier|cosmic\s*orange|orange|yellow|violet|lavender|mint|cream|beige|"
    r"space\s*black|space\s*grey|space\s*gray|phantom\s*black|deep\s*purple)\b",
    re.I,
)


def _to_storage_gb(value: str, unit: str) -> int:
    number = float(value)
    return int(number * 1024) if unit.lower() == "tb" else int(number)


class SmartphoneAdapter:
    name = "smartphone"

    def extract_specs(self, title: str, *, breadcrumbs: str = "", url: str = "") -> dict[str, Any]:
        text = ascii_fold(title or "")
        brand = resolve_brand(text)

        ram_hits = [int(m.group(1)) for m in RAM_RE.finditer(text) if int(m.group(1)) in {2, 3, 4, 6, 8, 12, 16, 18, 24}]
        ram = max(ram_hits) if ram_hits else None

        storage_hits: list[int] = []
        for m in STORAGE_RE.finditer(text):
            gb = _to_storage_gb(m.group(1), m.group(2))
            if gb >= 32 and gb != ram:
                storage_hits.append(gb)
        storage_gb = max(storage_hits) if storage_hits else None

        display = None
        dm = _DISPLAY_RE.search(text)
        if dm:
            display = round(float(dm.group(1)), 1)

        chipset = None
        cm = _CHIPSET_RE.search(text)
        if cm:
            chipset = re.sub(r"\s+", " ", cm.group(1).strip().lower())

        network = None
        nm = _NETWORK_RE.search(text)
        if nm:
            network = nm.group(1).lower()

        family = None
        fm = _FAMILY_RE.search(text)
        if fm:
            family = re.sub(r"\s+", "_", fm.group(1).strip().lower())

        model_codes: set[str] = set()
        from mayabu.catalog.model_codes import extract_model_codes

        for hit in extract_model_codes(title=text, category=self.name):
            model_codes.add(hit.code)
        for m in MODEL_CODE_RE.finditer(text):
            val = next((g for g in m.groups() if g), "")
            val = val.upper().replace(" ", "")
            if len(val) >= 5:
                model_codes.add(val)

        color = None
        col = _COLOR_RE.search(text) or _COLOR_RE.search(ascii_fold(url or ""))
        if col:
            color = re.sub(r"\s+", " ", col.group(1).lower()).strip()

        return {
            "brand": brand,
            "category": self.name,
            "family": family,
            "model_codes": sorted(model_codes),
            "ram_gb": ram,
            "storage_gb": storage_gb,
            "chipset": chipset,
            "display_size_inch": display,
            "network_generation": network,
            "color": color,
            # Soft / descriptive — not identity keys
            "camera_mp": None,
            "battery_mah": None,
            "spec_schema_version": 1,
        }

    def identity_keys(self) -> tuple[str, ...]:
        return ("brand", "model_codes", "family", "ram_gb", "storage_gb")

    def variant_keys(self) -> tuple[str, ...]:
        # Storage is the primary SKU axis on Indian retail titles.
        # Color is enforced via hard_conflicts when both sides expose it.
        return ("storage_gb",)

    def supporting_keys(self) -> tuple[str, ...]:
        return ("chipset", "network_generation", "display_size_inch")

    def descriptive_keys(self) -> tuple[str, ...]:
        return ("camera_mp", "battery_mah")

    def hard_conflicts(self, left: dict[str, Any], right: dict[str, Any]) -> list[str]:
        reasons: list[str] = []
        if model_code_conflict(left, right):
            reasons.append("model_code")
        if conflict_numeric(left.get("ram_gb"), right.get("ram_gb")):
            reasons.append("ram_gb")
        if conflict_numeric(left.get("storage_gb"), right.get("storage_gb")):
            reasons.append("storage_gb")
        left_color = str(left.get("color") or "").strip().lower() or None
        right_color = str(right.get("color") or "").strip().lower() or None
        if left_color and right_color and left_color != right_color:
            reasons.append("color")
        return reasons

    def price_bounds(self) -> tuple[int, int]:
        return (2_000, 250_000)
