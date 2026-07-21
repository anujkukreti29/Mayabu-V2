"""Deterministic product identity and variant grouping rules.

These functions are intentionally pure and side-effect free so matching logic is
reusable from ingestion, search ranking, admin diagnostics, and tests.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from mayabu_common import extract_specs, normalise_title, normalize_specs, resolve_brand

Relation = Literal["exact", "variant", "related", "conflict"]


@dataclass(frozen=True, slots=True)
class ProductIdentity:
    brand: str | None
    category: str
    family: str | None
    model_codes: tuple[str, ...]
    cpu_series: str | None
    cpu_models: tuple[str, ...]
    ram_gb: int | None
    storage_gb: int | None
    screen_inch: float | None
    gpu: str | None
    exact_fingerprint: str
    family_fingerprint: str | None


def _clean(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "").strip().lower())
    return text or None


def _hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def _model_codes(specs: dict[str, Any]) -> tuple[str, ...]:
    values = specs.get("model_codes") or []
    if isinstance(values, str):
        values = [values]
    return tuple(sorted({str(v).strip().upper() for v in values if str(v).strip()}))


def _cpu_models(specs: dict[str, Any]) -> tuple[str, ...]:
    values = specs.get("cpu_models") or []
    if isinstance(values, str):
        values = [values]
    return tuple(sorted({_clean(v) for v in values if _clean(v)}))


def build_identity(title: str, specs: dict[str, Any] | None = None, category: str = "laptop") -> ProductIdentity:
    merged = extract_specs(title or "", category=category)
    merged.update({k: v for k, v in (specs or {}).items() if v not in (None, "", [], {})})
    merged = normalize_specs(merged)
    brand = _clean(merged.get("brand") or resolve_brand(title))
    family = _clean(merged.get("family"))
    model_codes = _model_codes(merged)
    cpu_models = _cpu_models(merged)
    cpu_series = _clean(merged.get("cpu_series"))
    gpu = _clean(merged.get("gpu"))
    ram_gb = merged.get("ram_gb")
    storage_gb = merged.get("storage_gb")
    screen_inch = merged.get("screen_inch")

    exact_payload = {
        "category": category,
        "brand": brand,
        "model_codes": model_codes,
        "cpu_series": cpu_series,
        "cpu_models": cpu_models,
        "ram_gb": ram_gb,
        "storage_gb": storage_gb,
        "screen_inch": screen_inch,
        "gpu": gpu,
    }
    # When no model code exists, retain stable normalized title evidence so two
    # unrelated generic products do not collapse into the same fingerprint.
    if not model_codes:
        exact_payload["title_norm"] = normalise_title(title)[:240]

    family_payload = None
    if brand and family:
        family_payload = {"category": category, "brand": brand, "family": family}
    elif brand and model_codes:
        # Prefix before the first dash is often the chassis family (e.g. X1407CA).
        prefix = re.split(r"[-_/]", model_codes[0], maxsplit=1)[0].lower()
        family_payload = {"category": category, "brand": brand, "family": prefix}

    return ProductIdentity(
        brand=brand,
        category=category,
        family=family,
        model_codes=model_codes,
        cpu_series=cpu_series,
        cpu_models=cpu_models,
        ram_gb=ram_gb,
        storage_gb=storage_gb,
        screen_inch=screen_inch,
        gpu=gpu,
        exact_fingerprint=_hash(exact_payload),
        family_fingerprint=_hash(family_payload) if family_payload else None,
    )


def _conflict(left: Any, right: Any, tolerance: float = 0.0) -> bool:
    if left is None or right is None:
        return False
    try:
        return abs(float(left) - float(right)) > tolerance
    except (TypeError, ValueError):
        return str(left).lower() != str(right).lower()


def classify_relation(left: ProductIdentity, right: ProductIdentity) -> Relation:
    if left.category != right.category:
        return "conflict"
    if left.brand and right.brand and left.brand != right.brand:
        return "conflict"

    shared_models = set(left.model_codes) & set(right.model_codes)
    model_conflict = bool(left.model_codes and right.model_codes and not shared_models)
    spec_conflict = any(
        (
            _conflict(left.ram_gb, right.ram_gb),
            _conflict(left.storage_gb, right.storage_gb),
            _conflict(left.screen_inch, right.screen_inch, tolerance=0.25),
        )
    )
    cpu_conflict = bool(left.cpu_models and right.cpu_models and not (set(left.cpu_models) & set(right.cpu_models)))

    if shared_models and not spec_conflict and not cpu_conflict:
        return "exact"
    if left.exact_fingerprint == right.exact_fingerprint:
        return "exact"
    if left.family_fingerprint and left.family_fingerprint == right.family_fingerprint:
        return "variant" if (model_conflict or spec_conflict or cpu_conflict) else "exact"
    if left.brand and left.brand == right.brand and (left.family == right.family or left.cpu_series == right.cpu_series):
        return "related"
    return "conflict" if model_conflict and cpu_conflict else "related"
