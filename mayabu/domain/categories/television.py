"""Television category adapter."""

from __future__ import annotations

import re
from typing import Any

from mayabu.domain.categories.base import conflict_numeric, model_code_conflict
from mayabu_common import MODEL_CODE_RE, ascii_fold, resolve_brand

_SIZE_RE = re.compile(r"\b(\d{2}(?:\.\d)?)\s*(?:\"|''|inch|inches|in)\b", re.I)
_PANEL_RE = re.compile(r"\b(oled|qled|mini[\s-]?led|led|lcd|nanocell|neo\s*qled)\b", re.I)
_RES_RE = re.compile(r"\b(8k|4k|uhd|fhd|full\s*hd|hd|1080p|2160p|4320p)\b", re.I)
_REFRESH_RE = re.compile(r"\b(\d{2,3})\s*hz\b", re.I)
_SMART_RE = re.compile(r"\b(google\s*tv|android\s*tv|webos|tizen|fire\s*tv|vidaa|roku)\b", re.I)
_SERIES_RE = re.compile(r"\b([a-z]{1,3}\d{2,4}[a-z]{0,3})\b", re.I)
# Samsung Frame / Q-series full SKUs embed a short series (LS03H, QN90F, …).
_SAMSUNG_FULL_RE = re.compile(
    r"\b(QA\d{2}(LS\d{2}[A-Z]?)\w*|QN\d{2}[A-Z]\w*|UE\d{2}\w+|QA\d{2}[A-Z]\w+)\b",
    re.I,
)
_SHORT_SERIES_RE = re.compile(r"\b(LS\d{2}[A-Z]|QN\d{2}[A-Z]|Q\d[A-Z]\d[A-Z]?)\b", re.I)


class TelevisionAdapter:
    name = "television"

    def extract_specs(self, title: str, *, breadcrumbs: str = "", url: str = "") -> dict[str, Any]:
        text = ascii_fold(title or "")
        brand = resolve_brand(text)

        screen = None
        sm = _SIZE_RE.search(text)
        if sm:
            val = float(sm.group(1))
            if 24 <= val <= 120:
                screen = round(val, 1)

        panel = None
        pm = _PANEL_RE.search(text)
        if pm:
            panel = re.sub(r"\s+", "", pm.group(1).lower())

        resolution = None
        rm = _RES_RE.search(text)
        if rm:
            resolution = re.sub(r"\s+", "", rm.group(1).lower())
            if resolution in {"uhd", "2160p"}:
                resolution = "4k"
            elif resolution in {"fullhd", "1080p"}:
                resolution = "fhd"

        refresh = None
        hz = _REFRESH_RE.search(text)
        if hz:
            refresh = int(hz.group(1))

        smart = None
        sp = _SMART_RE.search(text)
        if sp:
            smart = re.sub(r"\s+", "_", sp.group(1).strip().lower())

        model_codes: set[str] = set()
        for m in MODEL_CODE_RE.finditer(text):
            val = next((g for g in m.groups() if g), "")
            val = val.upper().replace(" ", "")
            if len(val) >= 5:
                model_codes.add(val)
        for m in _SAMSUNG_FULL_RE.finditer(text):
            full = (m.group(1) or "").upper().replace(" ", "")
            if len(full) >= 6:
                model_codes.add(full)
            series = (m.group(2) or "").upper()
            if series and len(series) >= 4:
                model_codes.add(series)
        for m in _SHORT_SERIES_RE.finditer(text):
            token = m.group(1).upper()
            if len(token) >= 4:
                model_codes.add(token)
        from mayabu.catalog.tv_aliases import expand_tv_model_aliases

        model_codes = set(expand_tv_model_aliases(model_codes))

        series = None
        if brand and not model_codes:
            for m in _SERIES_RE.finditer(text):
                token = m.group(1).upper()
                if len(token) >= 4 and not token.isdigit():
                    series = token.lower()
                    break
        elif model_codes:
            # Prefer short series token as family for overlap queries.
            for code in sorted(model_codes, key=len):
                if re.fullmatch(r"LS\d{2}[A-Z]|QN\d{2}[A-Z]|Q\d[A-Z]\d[A-Z]?", code):
                    series = code.lower()
                    break
            if series is None:
                series = min(model_codes, key=len).lower()

        return {
            "brand": brand,
            "category": self.name,
            "family": series,
            "model_codes": sorted(model_codes),
            "screen_size_inch": screen,
            "panel_type": panel,
            "resolution": resolution,
            "refresh_rate_hz": refresh,
            "smart_platform": smart,
            "series": series,
        }

    def identity_keys(self) -> tuple[str, ...]:
        return ("brand", "model_codes", "screen_size_inch")

    def variant_keys(self) -> tuple[str, ...]:
        return ("screen_size_inch",)

    def supporting_keys(self) -> tuple[str, ...]:
        return ("panel_type", "resolution", "refresh_rate_hz", "smart_platform")

    def descriptive_keys(self) -> tuple[str, ...]:
        return ()

    def hard_conflicts(self, left: dict[str, Any], right: dict[str, Any]) -> list[str]:
        from mayabu.catalog.tv_aliases import expand_tv_model_aliases

        reasons: list[str] = []
        left_exp = {**left, "model_codes": expand_tv_model_aliases(left.get("model_codes") or [])}
        right_exp = {**right, "model_codes": expand_tv_model_aliases(right.get("model_codes") or [])}
        if model_code_conflict(left_exp, right_exp):
            reasons.append("model_code")
        if conflict_numeric(left.get("screen_size_inch"), right.get("screen_size_inch"), tolerance=0.5):
            reasons.append("screen_size_inch")
        return reasons

    def price_bounds(self) -> tuple[int, int]:
        return (5_000, 1_500_000)
