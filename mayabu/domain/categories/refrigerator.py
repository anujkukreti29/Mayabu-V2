"""Refrigerator category adapter."""

from __future__ import annotations

import re
from typing import Any

from mayabu.domain.categories.base import conflict_numeric, conflict_text, model_code_conflict
from mayabu_common import MODEL_CODE_RE, ascii_fold, resolve_brand

_CAP_RE = re.compile(r"\b(\d{2,4}(?:\.\d)?)\s*(?:l|ltr|litre|litres|liter|liters)\b", re.I)
_DOOR_RE = re.compile(r"\b(single[\s-]?door|double[\s-]?door|triple[\s-]?door|multi[\s-]?door|side[\s-]?by[\s-]?side|french[\s-]?door)\b", re.I)
_STAR_RE = re.compile(r"\b([1-5])\s*star\b", re.I)
_FROST_RE = re.compile(r"\b(frost[\s-]?free|direct[\s-]?cool)\b", re.I)
_COMP_RE = re.compile(r"\b(inverter|non[\s-]?inverter|digital\s*inverter)\b", re.I)


class RefrigeratorAdapter:
    name = "refrigerator"

    def extract_specs(self, title: str, *, breadcrumbs: str = "", url: str = "") -> dict[str, Any]:
        text = ascii_fold(title or "")
        brand = resolve_brand(text)

        capacity = None
        cm = _CAP_RE.search(text)
        if cm:
            capacity = round(float(cm.group(1)), 1)

        door = None
        dm = _DOOR_RE.search(text)
        if dm:
            door = re.sub(r"[\s-]+", "_", dm.group(1).strip().lower())

        star = None
        sm = _STAR_RE.search(text)
        if sm:
            star = int(sm.group(1))

        frost = None
        fm = _FROST_RE.search(text)
        if fm:
            frost = re.sub(r"[\s-]+", "_", fm.group(1).strip().lower())

        compressor = None
        pm = _COMP_RE.search(text)
        if pm:
            compressor = re.sub(r"[\s-]+", "_", pm.group(1).strip().lower())

        model_codes: set[str] = set()
        for m in MODEL_CODE_RE.finditer(text):
            val = next((g for g in m.groups() if g), "")
            val = val.upper().replace(" ", "")
            if len(val) >= 5:
                model_codes.add(val)

        return {
            "brand": brand,
            "category": self.name,
            "family": None,
            "model_codes": sorted(model_codes),
            "capacity_l": capacity,
            "door_type": door,
            "star_rating": star,
            "frost_type": frost,
            "compressor_type": compressor,
            "color": None,
        }

    def identity_keys(self) -> tuple[str, ...]:
        return ("brand", "model_codes", "capacity_l", "door_type")

    def variant_keys(self) -> tuple[str, ...]:
        return ("capacity_l", "door_type")

    def supporting_keys(self) -> tuple[str, ...]:
        return ("star_rating", "frost_type", "compressor_type")

    def descriptive_keys(self) -> tuple[str, ...]:
        return ("color",)

    def hard_conflicts(self, left: dict[str, Any], right: dict[str, Any]) -> list[str]:
        reasons: list[str] = []
        if model_code_conflict(left, right):
            reasons.append("model_code")
        if conflict_numeric(left.get("capacity_l"), right.get("capacity_l"), tolerance=5.0):
            reasons.append("capacity_l")
        if conflict_text(left.get("door_type"), right.get("door_type")):
            reasons.append("door_type")
        return reasons

    def price_bounds(self) -> tuple[int, int]:
        return (8_000, 500_000)
