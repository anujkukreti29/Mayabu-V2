"""Headphones category adapter (over-ear / on-ear / wired / wireless — not TWS)."""

from __future__ import annotations

import re
from typing import Any

from mayabu.domain.categories.base import conflict_text, model_code_conflict
from mayabu_common import MODEL_CODE_RE, ascii_fold, resolve_brand

_FORM_RE = re.compile(r"\b(over[\s-]?ear|on[\s-]?ear|in[\s-]?ear|neckband)\b", re.I)
_CONN_RE = re.compile(r"\b(wireless|wired|bluetooth|3\.5\s*mm|usb[\s-]?c)\b", re.I)
_ANC_RE = re.compile(r"\b(anc|active\s*noise\s*cancell?ation|noise\s*cancell?ing)\b", re.I)
_CODEC_RE = re.compile(r"\b(ldac|aptx(?:\s*adaptive|\s*hd)?|aac|sbc)\b", re.I)
_BATT_RE = re.compile(r"\b(\d{1,2}(?:\.\d)?)\s*(?:hrs?|hours?)\b", re.I)
_FAMILY_RE = re.compile(
    r"\b("
    r"wh[\s-]?\d{3,4}\s*xm\d|"
    r"wh[\s-]?\d{3,4}|"
    r"sony\s*xm\d+|"
    r"quietcomfort(?:\s*\d+)?|"
    r"studio\s*pro|"
    r"momentum"
    r")\b",
    re.I,
)
_HEADPHONE_MODEL_RE = re.compile(r"\b(WH[\s-]?\d{3,4}(?:XM\d)?|MDR[\s-]?\w{2,8}|WI[\s-]?\w{2,8})\b", re.I)
_FALSE_MODEL_TOKENS = frozenset(
    {
        "WIRELESS",
        "WITH",
        "OVER",
        "EAR",
        "HEADPHONES",
        "HEADPHONE",
        "BLUETOOTH",
        "NOISE",
        "CANCELING",
        "CANCELLING",
        "ACTIVE",
        "SONY",
        "JBL",
        "BOSE",
    }
)


class HeadphonesAdapter:
    name = "headphones"

    def extract_specs(self, title: str, *, breadcrumbs: str = "", url: str = "") -> dict[str, Any]:
        text = ascii_fold(title or "")
        brand = resolve_brand(text)

        form = None
        fm = _FORM_RE.search(text)
        if fm:
            form = re.sub(r"[\s-]+", "_", fm.group(1).strip().lower())

        connectivity = None
        cm = _CONN_RE.search(text)
        if cm:
            connectivity = re.sub(r"[\s-]+", "_", cm.group(1).strip().lower())

        anc = bool(_ANC_RE.search(text))
        codec = None
        codec_m = _CODEC_RE.search(text)
        if codec_m:
            codec = re.sub(r"\s+", "", codec_m.group(1).lower())

        battery_hours = None
        hours = [float(m.group(1)) for m in _BATT_RE.finditer(text)]
        if hours:
            battery_hours = max(hours)

        family = None
        fam = _FAMILY_RE.search(text)
        if fam:
            family = re.sub(r"\s+", "_", fam.group(1).strip().lower())

        model_codes: set[str] = set()
        for m in MODEL_CODE_RE.finditer(text):
            val = next((g for g in m.groups() if g), "")
            val = val.upper().replace(" ", "")
            if len(val) >= 4 and val not in _FALSE_MODEL_TOKENS:
                model_codes.add(val)
        for m in _HEADPHONE_MODEL_RE.finditer(text):
            token = re.sub(r"[\s-]+", "", m.group(1).upper())
            if token not in _FALSE_MODEL_TOKENS:
                model_codes.add(token)

        return {
            "brand": brand,
            "category": self.name,
            "family": family,
            "model_codes": sorted(model_codes),
            "form_factor": form,
            "connectivity": connectivity,
            "anc": anc,
            "codec": codec,
            "battery_hours": battery_hours,
        }

    def identity_keys(self) -> tuple[str, ...]:
        return ("brand", "model_codes", "family", "form_factor", "connectivity")

    def variant_keys(self) -> tuple[str, ...]:
        return ("form_factor", "connectivity")

    def supporting_keys(self) -> tuple[str, ...]:
        return ("anc", "codec")

    def descriptive_keys(self) -> tuple[str, ...]:
        return ("battery_hours",)

    def hard_conflicts(self, left: dict[str, Any], right: dict[str, Any]) -> list[str]:
        reasons: list[str] = []
        if model_code_conflict(left, right):
            reasons.append("model_code")
        if conflict_text(left.get("form_factor"), right.get("form_factor")):
            reasons.append("form_factor")
        # Wired vs wireless (or bluetooth vs 3.5mm) are distinct commercial products.
        left_conn = str(left.get("connectivity") or "").lower()
        right_conn = str(right.get("connectivity") or "").lower()
        if left_conn and right_conn:
            left_wired = left_conn in {"wired", "3.5_mm", "3.5mm"}
            right_wired = right_conn in {"wired", "3.5_mm", "3.5mm"}
            left_wireless = left_conn in {"wireless", "bluetooth"}
            right_wireless = right_conn in {"wireless", "bluetooth"}
            if (left_wired and right_wireless) or (left_wireless and right_wired):
                reasons.append("connectivity")
            elif conflict_text(left.get("connectivity"), right.get("connectivity")):
                reasons.append("connectivity")
        return reasons

    def price_bounds(self) -> tuple[int, int]:
        return (500, 150_000)
