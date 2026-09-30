"""TWS / true-wireless earbuds category adapter."""

from __future__ import annotations

import re
from typing import Any

from mayabu.domain.categories.base import conflict_text, model_code_conflict
from mayabu_common import GEN_RE, MODEL_CODE_RE, ascii_fold, resolve_brand

_ANC_RE = re.compile(r"\b(anc|active\s*noise\s*cancell?ation|noise\s*cancell?ing)\b", re.I)
_CODEC_RE = re.compile(r"\b(ldac|aptx(?:\s*adaptive|\s*hd)?|aac|sbc)\b", re.I)
_BT_RE = re.compile(r"\bbluetooth\s*(?:v(?:ersion)?\s*)?(\d(?:\.\d)?)\b", re.I)
_BATT_RE = re.compile(r"\b(\d{1,2}(?:\.\d)?)\s*(?:hrs?|hours?)\b", re.I)
_SAMSUNG_BUD_MODEL_RE = re.compile(r"\b(SM[\s-]?R\d{3}[A-Z0-9]*)\b", re.I)
_ONEPLUS_BUD_MODEL_RE = re.compile(r"\b(E\d{3,4}[A-Z]?)\b", re.I)
_SONY_WF_RE = re.compile(r"\b(wf[\s-]?\d{3,4}[\s-]?xm\d)\b", re.I)


def _normalize_family(raw: str | None) -> str | None:
    if not raw:
        return None
    family = re.sub(r"[\s\-]+", "_", raw.strip().lower())
    family = re.sub(r"_+", "_", family).strip("_")
    # Sony WF-1000XM5 style → wf1000xm5
    family = re.sub(r"^wf_?", "wf", family)
    family = family.replace("wf-", "wf")
    return family or None


def _galaxy_buds_family(text: str) -> str | None:
    """Distinguish Buds / Buds2 / Buds3 / FE / Pro / Live as separate families."""
    m = re.search(
        r"\bgalaxy\s*buds\s*(?:(\d)\s*)?(pro|fe|live)?\b",
        text,
        re.I,
    )
    if not m:
        # Compact "Buds3" / "Buds3 FE" without space after Buds
        m = re.search(r"\bbuds\s*([23])\s*(pro|fe)?\b", text, re.I)
        if not m:
            return None
        gen, variant = m.group(1), (m.group(2) or "").lower()
        parts = ["galaxy_buds", gen]
        if variant:
            parts.append(variant)
        return "_".join(parts)
    gen = (m.group(1) or "").strip()
    variant = (m.group(2) or "").lower()
    parts = ["galaxy_buds"]
    if gen:
        parts.append(gen)
    if variant:
        parts.append(variant)
    return "_".join(parts) if len(parts) > 1 or re.search(r"\bgalaxy\s*buds\b", text, re.I) else None


def _oneplus_buds_family(text: str) -> str | None:
    m = re.search(
        r"\b(?:oneplus\s+)?(nord\s+)?buds\s*((?:pro|z|r)?\s*\d*(?:\s*pro)?|\d+\s*(?:pro|r)?)",
        text,
        re.I,
    )
    if not m and not re.search(r"\b(?:oneplus\s+)?(?:nord\s+)?buds\b", text, re.I):
        return None
    nord = bool(m and m.group(1)) or bool(re.search(r"\bnord\s+buds\b", text, re.I))
    suffix = ""
    if m:
        suffix = re.sub(r"\s+", "_", (m.group(2) or "").strip().lower()).strip("_")
    base = "nord_buds" if nord else "oneplus_buds"
    return f"{base}_{suffix}" if suffix else base


def _samsung_model_stem(code: str) -> str:
    """SMR530NZAAINU → SMR530 (chassis identity)."""
    c = re.sub(r"[^A-Z0-9]", "", (code or "").upper())
    m = re.match(r"(SMR\d{3})", c)
    return m.group(1) if m else c[:6]


class TwsAdapter:
    name = "tws"

    def extract_specs(self, title: str, *, breadcrumbs: str = "", url: str = "") -> dict[str, Any]:
        text = ascii_fold(title or "")
        brand = resolve_brand(text)

        anc = bool(_ANC_RE.search(text))
        codec = None
        cm = _CODEC_RE.search(text)
        if cm:
            codec = re.sub(r"\s+", "", cm.group(1).lower())

        bt = None
        bm = _BT_RE.search(text)
        if bm:
            bt = bm.group(1)

        battery_hours = None
        hours = [float(m.group(1)) for m in _BATT_RE.finditer(text)]
        if hours:
            battery_hours = max(hours)

        gen = None
        gm = GEN_RE.search(text)
        if gm:
            try:
                gen = int(gm.group(1))
            except ValueError:
                gen = None
        if gen is None:
            buds_gen = re.search(r"\bbuds\s*([23])\b", text, re.I)
            if buds_gen:
                gen = int(buds_gen.group(1))

        family = _galaxy_buds_family(text)
        if family is None:
            family = _oneplus_buds_family(text)
        if family is None:
            sm = _SONY_WF_RE.search(text)
            if sm:
                family = _normalize_family(sm.group(1))
        if family is None:
            ap = re.search(r"\b(airpods\s*(?:pro\s*)?(?:\d)?)\b", text, re.I)
            if ap:
                family = _normalize_family(ap.group(1))
        if family is None:
            ad = re.search(r"\b(airdopes\s*\d{2,4})\b", text, re.I)
            if ad:
                family = _normalize_family(ad.group(1))
        if family is None:
            ne = re.search(r"\b(nothing\s*ear(?:\s*\(?\s*a\s*\)?)?)\b", text, re.I)
            if ne:
                family = _normalize_family(ne.group(1))
        family = _normalize_family(family)

        model_codes: set[str] = set()
        for m in MODEL_CODE_RE.finditer(text):
            val = next((g for g in m.groups() if g), "")
            val = val.upper().replace(" ", "")
            if len(val) >= 4:
                model_codes.add(val)
        for m in _SAMSUNG_BUD_MODEL_RE.finditer(text):
            model_codes.add(re.sub(r"[\s-]+", "", m.group(1).upper()))
        for m in _ONEPLUS_BUD_MODEL_RE.finditer(text):
            token = m.group(1).upper()
            if len(token) >= 4:
                model_codes.add(token)

        return {
            "brand": brand,
            "category": self.name,
            "family": family,
            "model_codes": sorted(model_codes),
            "anc": anc,
            "codec": codec,
            "battery_hours": battery_hours,
            "bluetooth_version": bt,
            "generation": gen,
        }

    def identity_keys(self) -> tuple[str, ...]:
        return ("brand", "model_codes", "family", "generation")

    def variant_keys(self) -> tuple[str, ...]:
        # Family already encodes generation / FE / Pro; do not require separate gen.
        return ()

    def supporting_keys(self) -> tuple[str, ...]:
        return ("anc", "codec", "bluetooth_version")

    def descriptive_keys(self) -> tuple[str, ...]:
        return ("battery_hours",)

    def hard_conflicts(self, left: dict[str, Any], right: dict[str, Any]) -> list[str]:
        reasons: list[str] = []
        if model_code_conflict(left, right):
            reasons.append("model_code")
        # Distinct Samsung chassis stems never exact-merge (Buds3 vs FE vs Pro).
        left_stems = {
            _samsung_model_stem(c)
            for c in (left.get("model_codes") or [])
            if str(c).upper().startswith("SMR")
        }
        right_stems = {
            _samsung_model_stem(c)
            for c in (right.get("model_codes") or [])
            if str(c).upper().startswith("SMR")
        }
        if left_stems and right_stems and not (left_stems & right_stems):
            if "model_code" not in reasons:
                reasons.append("model_code")
        left_fam = _normalize_family(left.get("family"))
        right_fam = _normalize_family(right.get("family"))
        if left_fam and right_fam and left_fam != right_fam:
            reasons.append("family")
        left_gen, right_gen = left.get("generation"), right.get("generation")
        if left_gen is not None and right_gen is not None and left_gen != right_gen:
            reasons.append("generation")
        return reasons

    def price_bounds(self) -> tuple[int, int]:
        return (500, 80_000)
