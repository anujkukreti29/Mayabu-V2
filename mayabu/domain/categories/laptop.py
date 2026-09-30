"""Laptop category adapter — preserves production baseline identity rules."""

from __future__ import annotations

import re
from typing import Any

from mayabu_common import (
    CPU_PATTERNS,
    FAMILY_PATTERNS,
    GEN_RE,
    GPU_RE,
    MODEL_CODE_RE,
    RAM_RE,
    SCREEN_RE,
    STORAGE_RE,
    ascii_fold,
    resolve_brand,
)


def _to_storage_gb(value: str, unit: str) -> int:
    number = float(value)
    return int(number * 1024) if unit.lower() == "tb" else int(number)


def _family_conflict(left: Any, right: Any) -> bool:
    """Different laptop lines conflict. A shorter prefix may still be the same line."""
    left_family = str(left or "").strip().lower()
    right_family = str(right or "").strip().lower()
    if not left_family or not right_family or left_family == right_family:
        return False
    if left_family.startswith(right_family) or right_family.startswith(left_family):
        return False
    return True


class LaptopAdapter:
    name = "laptop"

    def extract_specs(self, title: str, *, breadcrumbs: str = "", url: str = "") -> dict[str, Any]:
        text = ascii_fold(title or "")
        tl = text.lower()
        brand = resolve_brand(text)

        ram_hits: list[int] = []
        storage_hits: list[int] = []
        for m in RAM_RE.finditer(text):
            value = int(m.group(1))
            if value in {2, 3, 4, 6, 8, 10, 12, 16, 18, 24, 32, 36, 48, 64, 96, 128}:
                ram_hits.append(value)
        ram = max(ram_hits) if ram_hits else None

        for m in STORAGE_RE.finditer(text):
            gb = _to_storage_gb(m.group(1), m.group(2))
            if gb >= 32 and gb != ram:
                storage_hits.append(gb)
        storage_gb = max(storage_hits) if storage_hits else None

        screen = None
        sm = SCREEN_RE.search(text)
        if sm:
            if sm.group(1):
                screen = round(float(sm.group(1)), 1)
            elif sm.group(2):
                screen = round(float(sm.group(2)) / 2.54, 1)

        gen = None
        gm = GEN_RE.search(text)
        if gm:
            try:
                gen = int(gm.group(1))
            except ValueError:
                gen = None

        cpu_series = None
        cpu_models: set[str] = set()
        for pattern, label in CPU_PATTERNS:
            m = pattern.search(text)
            if not m:
                continue
            groups = [g for g in m.groups() if g]
            normalized_groups = [re.sub(r"\s+", "", g.lower()) for g in groups]
            cpu_series = label
            if normalized_groups:
                cpu_series = label + ":" + ":".join(normalized_groups[:2])
                cpu_models.add(":".join([label] + normalized_groups))
            break
        # "Core i5 12th Gen 12450H" matches the series before the SKU. Attach a
        # single explicit SKU so 12450H and 13450HX are not treated as the same CPU.
        if cpu_series and not re.search(r"\d{4,5}[a-z]", cpu_series):
            sku_hits = []
            for num, suffix in re.findall(
                r"\b(\d{4,5})(hx|hk|hs|h|u|p|g[1-7]|y|e)\b",
                tl,
            ):
                token = f"{num}{suffix}".lower()
                if token not in sku_hits:
                    sku_hits.append(token)
            if len(sku_hits) == 1:
                cpu_series = f"{cpu_series}:{sku_hits[0]}"
                label = cpu_series.split(":", 1)[0]
                cpu_models = {f"{label}:{':'.join(cpu_series.split(':')[1:])}"}

        model_codes: set[str] = set()
        for m in MODEL_CODE_RE.finditer(text):
            val = next((g for g in m.groups() if g), "")
            val = val.upper().replace(" ", "")
            if len(val) < 5:
                continue
            if re.fullmatch(r"I[3579]\d{4,5}[A-Z]*", val):
                continue
            if val.lower() in {"windows11", "office2024"}:
                continue
            model_codes.add(val)

        gpu = None
        gm2 = GPU_RE.search(text)
        if gm2:
            gpu = re.sub(r"\s+", "", gm2.group(1).lower())
        gpu_memory_gb = None
        vram = re.search(r"\b(\d+)\s*gb\s*graphics\b", tl)
        if vram:
            gpu_memory_gb = int(vram.group(1))

        family = None
        for fp in FAMILY_PATTERNS:
            fm = re.search(fp, tl)
            if fm:
                tail = tl[fm.end(1) : fm.end(1) + 10]
                if re.match(r"\s*(?:\.\d+\s*)?(?:gb|tb|inch|inches|cm)\b", tail):
                    continue
                family = re.sub(r"\s+", "_", fm.group(1).strip().lower())
                break
        if family is None:
            for token in (
                "ideapad", "thinkpad", "thinkbook", "loq", "legion", "yoga",
                "vivobook", "zenbook", "tuf", "inspiron", "pavilion", "omen",
                "victus", "envy", "aspire", "nitro", "predator", "swift", "macbook",
            ):
                if re.search(rf"\b{token}\b", tl):
                    family = token
                    break

        return {
            "brand": brand,
            "category": self.name,
            "family": family,
            "model_codes": sorted(model_codes),
            "cpu_series": cpu_series,
            "cpu_models": sorted(cpu_models),
            "gpu": gpu,
            "gpu_memory_gb": gpu_memory_gb,
            "ram_gb": ram,
            "storage_gb": storage_gb,
            "screen_inch": screen,
            "generation": gen,
        }

    def identity_keys(self) -> tuple[str, ...]:
        return ("brand", "model_codes", "cpu_series", "cpu_models", "ram_gb", "storage_gb", "screen_inch", "gpu")

    def variant_keys(self) -> tuple[str, ...]:
        return ("ram_gb", "storage_gb", "screen_inch")

    def supporting_keys(self) -> tuple[str, ...]:
        return ("cpu_series", "gpu", "generation")

    def descriptive_keys(self) -> tuple[str, ...]:
        return ()

    def hard_conflicts(self, left: dict[str, Any], right: dict[str, Any]) -> list[str]:
        from mayabu.domain.categories.base import (
            conflict_numeric,
            cpu_models_compatible,
            discrete_gpu_conflict,
            model_code_conflict,
        )

        reasons: list[str] = []
        if model_code_conflict(left, right):
            reasons.append("model_code")
        if conflict_numeric(left.get("ram_gb"), right.get("ram_gb")):
            reasons.append("ram_gb")
        if conflict_numeric(left.get("storage_gb"), right.get("storage_gb")):
            reasons.append("storage_gb")
        if conflict_numeric(left.get("screen_inch"), right.get("screen_inch"), tolerance=0.25):
            reasons.append("screen_inch")
        if not cpu_models_compatible(left.get("cpu_models"), right.get("cpu_models")):
            reasons.append("cpu_models")
        if discrete_gpu_conflict(left.get("gpu"), right.get("gpu")):
            reasons.append("gpu")
        if conflict_numeric(left.get("gpu_memory_gb"), right.get("gpu_memory_gb")):
            reasons.append("gpu_memory_gb")
        if _family_conflict(left.get("family"), right.get("family")):
            reasons.append("family")
        return reasons

    def price_bounds(self) -> tuple[int, int]:
        return (5_000, 600_000)
