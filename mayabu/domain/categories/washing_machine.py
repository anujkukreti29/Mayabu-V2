"""Washing machine category adapter."""

from __future__ import annotations

import re
from typing import Any

from mayabu.domain.categories.base import conflict_numeric, conflict_text, model_code_conflict
from mayabu_common import MODEL_CODE_RE, ascii_fold, resolve_brand

_CAP_RE = re.compile(r"\b(\d{1,2}(?:\.\d)?)\s*kg\b", re.I)
# Washer/dryer combos: "13-10 kg", "13 kg/10 kg", "13kg / 10kg" — wash capacity is first.
_DUAL_CAP_RE = re.compile(
    r"\b(\d{1,2}(?:\.\d)?)\s*(?:kg)?\s*[-/]\s*(\d{1,2}(?:\.\d)?)\s*kg\b",
    re.I,
)
_LOAD_RE = re.compile(r"\b(front[\s-]?load(?:ing)?|top[\s-]?load(?:ing)?)\b", re.I)
_AUTO_RE = re.compile(r"\b(fully\s*automatic|semi[\s-]?automatic|automatic)\b", re.I)
_STAR_RE = re.compile(r"\b([1-5])\s*star\b", re.I)
_RPM_RE = re.compile(r"\b(\d{3,4})\s*rpm\b", re.I)
_INV_RE = re.compile(r"\b(inverter|digital\s*inverter)\b", re.I)


class WashingMachineAdapter:
    name = "washing_machine"

    def extract_specs(self, title: str, *, breadcrumbs: str = "", url: str = "") -> dict[str, Any]:
        text = ascii_fold(title or "")
        brand = resolve_brand(text)

        capacity = None
        dry_capacity = None
        dual = _DUAL_CAP_RE.search(text)
        if dual:
            capacity = round(float(dual.group(1)), 1)
            dry_capacity = round(float(dual.group(2)), 1)
        else:
            cm = _CAP_RE.search(text)
            if cm:
                capacity = round(float(cm.group(1)), 1)

        load = None
        lm = _LOAD_RE.search(text)
        if lm:
            load = re.sub(r"[\s-]+", "_", lm.group(1).strip().lower())
            load = load.replace("front_loading", "front_load").replace("top_loading", "top_load")

        automation = None
        am = _AUTO_RE.search(text)
        if am:
            automation = re.sub(r"[\s-]+", "_", am.group(1).strip().lower())

        star = None
        sm = _STAR_RE.search(text)
        if sm:
            star = int(sm.group(1))

        rpm = None
        rm = _RPM_RE.search(text)
        if rm:
            rpm = int(rm.group(1))

        inverter = None
        im = _INV_RE.search(text)
        if im:
            inverter = re.sub(r"\s+", "_", im.group(1).strip().lower())

        model_codes: set[str] = set()
        for m in MODEL_CODE_RE.finditer(text):
            val = next((g for g in m.groups() if g), "")
            val = val.upper().replace(" ", "")
            if len(val) >= 5:
                model_codes.add(val)

        return {
            "brand": brand,
            "category": self.name,
            # Brand + load type forms a stable family so capacity differences
            # classify as variant (not conflict) when load type matches.
            "family": (
                f"{brand}_{load}"
                if brand and load
                else (f"{brand}_washer" if brand else None)
            ),
            "model_codes": sorted(model_codes),
            "capacity_kg": capacity,
            "dry_capacity_kg": dry_capacity,
            "load_type": load,
            "automation_type": automation,
            "star_rating": star,
            "rpm": rpm,
            "inverter": inverter,
        }

    def identity_keys(self) -> tuple[str, ...]:
        return ("brand", "model_codes", "capacity_kg", "load_type", "automation_type")

    def variant_keys(self) -> tuple[str, ...]:
        return ("capacity_kg", "load_type", "automation_type")

    def supporting_keys(self) -> tuple[str, ...]:
        return ("star_rating", "rpm", "inverter")

    def descriptive_keys(self) -> tuple[str, ...]:
        return ()

    def hard_conflicts(self, left: dict[str, Any], right: dict[str, Any]) -> list[str]:
        reasons: list[str] = []
        if model_code_conflict(left, right):
            reasons.append("model_code")
        if conflict_numeric(left.get("capacity_kg"), right.get("capacity_kg"), tolerance=0.25):
            reasons.append("capacity_kg")
        if conflict_text(left.get("load_type"), right.get("load_type")):
            reasons.append("load_type")
        if conflict_text(left.get("automation_type"), right.get("automation_type")):
            reasons.append("automation_type")
        return reasons

    def price_bounds(self) -> tuple[int, int]:
        return (5_000, 250_000)
