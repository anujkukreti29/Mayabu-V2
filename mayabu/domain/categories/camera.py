"""Camera category adapter — body-only vs kit-lens must not blindly merge."""

from __future__ import annotations

import re
from typing import Any

from mayabu.domain.categories.base import model_code_conflict
from mayabu_common import MODEL_CODE_RE, ascii_fold, resolve_brand

_TYPE_RE = re.compile(
    r"\b(mirrorless|dslr|compact|action\s*camera|point[\s-]?and[\s-]?shoot)\b", re.I
)
_SENSOR_RE = re.compile(
    r"\b(full[\s-]?frame|aps[\s-]?c|m43|micro[\s-]?four[\s-]?thirds|1[\s-]?inch)\b", re.I
)
_MP_RE = re.compile(r"\b(\d{1,3}(?:\.\d)?)\s*mp\b", re.I)
_MOUNT_RE = re.compile(
    r"\b(sony\s*e|e[\s-]?mount|canon\s*rf|canon\s*ef|nikon\s*z|fuji\s*x|mft|l[\s-]?mount)\b",
    re.I,
)
_BODY_ONLY_RE = re.compile(r"\b(body\s*only|(?:^|[\s(])body(?:[\s)]|$))\b", re.I)
_KIT_RE = re.compile(
    r"\b(kit|with\s*(?:lens|\d{2,3}\s*-\s*\d{2,3}\s*mm)|\d{2,3}\s*-\s*\d{2,3}\s*mm\s*kit)\b",
    re.I,
)
_FAMILY_RE = re.compile(
    r"\b("
    r"eos\s*r?\s*\d+[a-z]?|"
    r"alpha\s*\d+\s*(?:iv|iii|ii|v|vi|vii)?|"
    r"a\s*7\s*(?:iv|iii|ii|r\s*v|r\s*iv|c\s*ii)?|"
    r"z\s*\d+[a-z]?|"
    r"x[\s-]?[a-z]?\d+[a-z]?|"
    r"ilce[\s-]?\d+[a-z]*|"
    r"d\d{3,4}"
    r")\b",
    re.I,
)
_CAMERA_SKU_RE = re.compile(
    r"\b(ILCE[\s-]?\d+[A-Z0-9]*|EOS\s*R?\d+[A-Z]*|DC[\s-]?\w+|ZV[\s-]?\w+)\b", re.I
)


class CameraAdapter:
    name = "camera"

    def extract_specs(self, title: str, *, breadcrumbs: str = "", url: str = "") -> dict[str, Any]:
        text = ascii_fold(title or "")
        brand = resolve_brand(text)

        camera_type = None
        tm = _TYPE_RE.search(text)
        if tm:
            camera_type = re.sub(r"[\s-]+", "_", tm.group(1).strip().lower())
        elif re.search(r"\b(ilce|eos\s*r|alpha|mirrorless)\b", text, re.I):
            camera_type = "mirrorless"
        elif re.search(r"\b(dslr|d\d{3,4})\b", text, re.I):
            camera_type = "dslr"

        sensor = None
        sm = _SENSOR_RE.search(text)
        if sm:
            sensor = re.sub(r"[\s-]+", "_", sm.group(1).strip().lower())

        megapixels = None
        mm = _MP_RE.search(text)
        if mm:
            megapixels = round(float(mm.group(1)), 1)

        mount = None
        mount_m = _MOUNT_RE.search(text)
        if mount_m:
            mount = re.sub(r"[\s-]+", "_", mount_m.group(1).strip().lower())

        kit_lens = None
        body_only = False
        if _KIT_RE.search(text) or re.search(
            r"\bwith\s+\d{2,3}\s*-?\s*\d{0,3}\s*mm\b", text, re.I
        ):
            kit_m = re.search(r"(\d{2,3}\s*-?\s*\d{0,3}\s*mm)", text, re.I)
            kit_lens = kit_m.group(1).lower().replace(" ", "") if kit_m else "kit"
            body_only = False
        elif _BODY_ONLY_RE.search(text):
            body_only = True

        model_codes: set[str] = set()
        for m in MODEL_CODE_RE.finditer(text):
            val = next((g for g in m.groups() if g), "")
            val = val.upper().replace(" ", "")
            if len(val) >= 3:
                model_codes.add(val)
        for m in _CAMERA_SKU_RE.finditer(text):
            model_codes.add(re.sub(r"[\s-]+", "", m.group(1).upper()))
        # Normalize common Sony Alpha marketing aliases into ILCE-style when present.
        a7 = re.search(r"\ba\s*7\s*(iv|iii|ii|r\s*v|r\s*iv)?\b", text, re.I)
        if a7:
            suffix = (a7.group(1) or "").lower().replace(" ", "")
            alias = "A7" + suffix.upper()
            model_codes.add(alias)

        family = None
        fam = _FAMILY_RE.search(text)
        if fam:
            family = re.sub(r"\s+", "_", fam.group(1).strip().lower())

        return {
            "brand": brand,
            "category": self.name,
            "family": family,
            "model_codes": sorted(model_codes),
            "camera_type": camera_type,
            "sensor_format": sensor,
            "megapixels": megapixels,
            "mount": mount,
            "body_only": body_only,
            "kit_lens": kit_lens,
        }

    def identity_keys(self) -> tuple[str, ...]:
        return ("brand", "model_codes", "body_only", "kit_lens")

    def variant_keys(self) -> tuple[str, ...]:
        return ("body_only", "kit_lens")

    def supporting_keys(self) -> tuple[str, ...]:
        return ("camera_type", "sensor_format", "mount", "megapixels")

    def descriptive_keys(self) -> tuple[str, ...]:
        return ("megapixels",)

    def hard_conflicts(self, left: dict[str, Any], right: dict[str, Any]) -> list[str]:
        reasons: list[str] = []
        if model_code_conflict(left, right):
            reasons.append("model_code")
        left_body = bool(left.get("body_only"))
        right_body = bool(right.get("body_only"))
        left_kit = left.get("kit_lens")
        right_kit = right.get("kit_lens")
        # Body-only vs kit bundle is a hard identity split.
        if (left_body and right_kit) or (right_body and left_kit):
            reasons.append("kit_vs_body")
        if left_kit and right_kit and str(left_kit).lower() != str(right_kit).lower():
            reasons.append("kit_lens")
        return reasons

    def price_bounds(self) -> tuple[int, int]:
        # Broad camera range: compact through professional bodies. Reject EMI/accessory.
        return (3_000, 2_000_000)
