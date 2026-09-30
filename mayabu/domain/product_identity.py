"""Deterministic product identity and variant grouping rules.

These functions are intentionally pure and side-effect free so matching logic is
reusable from ingestion, search ranking, admin diagnostics, and tests.

Category-specific exact/variant/conflict rules live in mayabu.domain.categories.
Laptop behavior is preserved as the production baseline.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from mayabu.domain.categories.registry import get_adapter, hard_conflicts
from mayabu.domain.categories.base import (
    cpu_models_compatible,
    discrete_gpu_conflict,
    is_weak_series_model_code,
    strong_model_codes,
)
from mayabu_common import extract_specs, normalise_title, normalize_specs, resolve_brand

Relation = Literal["exact", "variant", "related", "conflict"]

_COMPATIBLE_AUDIO = frozenset({"audio", "headphones"})


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
    # Category-specific identity/variant evidence as JSON-serialized pairs.
    identity_specs: tuple[tuple[str, str], ...] = ()


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


def _serialize_specs(specs: dict[str, Any], keys: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for key in keys:
        if key not in specs:
            continue
        value = specs.get(key)
        if value in (None, "", [], {}):
            continue
        pairs.append((key, json.dumps(value, sort_keys=True, default=str)))
    return tuple(sorted(pairs))


def _deserialize_specs(pairs: tuple[tuple[str, str], ...]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, raw in pairs:
        try:
            out[key] = json.loads(raw)
        except Exception:
            out[key] = raw
    return out


def _categories_compatible(left: str, right: str) -> bool:
    if left == right:
        return True
    if left in _COMPATIBLE_AUDIO and right in _COMPATIBLE_AUDIO:
        return True
    return False


def build_identity(title: str, specs: dict[str, Any] | None = None, category: str = "laptop") -> ProductIdentity:
    merged = extract_specs(title or "", category=category)
    merged.update({k: v for k, v in (specs or {}).items() if v not in (None, "", [], {})})
    merged = normalize_specs(merged)
    brand = _clean(merged.get("brand") or resolve_brand(title))
    family = _clean(merged.get("family"))
    model_codes = _model_codes(merged)
    if category == "television" and model_codes:
        from mayabu.catalog.tv_aliases import expand_tv_model_aliases

        model_codes = tuple(sorted(expand_tv_model_aliases(model_codes)))
        merged["model_codes"] = list(model_codes)
    cpu_models = _cpu_models(merged)
    cpu_series = _clean(merged.get("cpu_series"))
    gpu = _clean(merged.get("gpu"))
    ram_gb = merged.get("ram_gb")
    storage_gb = merged.get("storage_gb")
    screen_inch = merged.get("screen_inch")
    if screen_inch is None:
        screen_inch = merged.get("screen_size_inch") or merged.get("display_size_inch")

    adapter = get_adapter(category)
    if adapter is not None and category not in {"laptop"}:
        keys = tuple(dict.fromkeys(adapter.identity_keys() + adapter.variant_keys()))
        exact_payload = {
            "category": category if category != "audio" else "headphones",
            "brand": brand,
        }
        for key in keys:
            exact_payload[key] = merged.get(key)
        if not model_codes and not family:
            exact_payload["title_norm"] = normalise_title(title)[:240]
        identity_specs = _serialize_specs(merged, keys)
    else:
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
        if not model_codes:
            exact_payload["title_norm"] = normalise_title(title)[:240]
        identity_specs = _serialize_specs(
            merged,
            ("brand", "model_codes", "cpu_series", "cpu_models", "ram_gb", "storage_gb", "screen_inch", "gpu"),
        )

    family_payload = None
    if brand and family:
        family_payload = {"category": category, "brand": brand, "family": family}
    elif brand and model_codes:
        prefix = re.split(r"[-_/]", model_codes[0], maxsplit=1)[0].lower()
        family_payload = {"category": category, "brand": brand, "family": prefix}

    return ProductIdentity(
        brand=brand,
        category=category,
        family=family,
        model_codes=model_codes,
        cpu_series=cpu_series,
        cpu_models=cpu_models,
        ram_gb=ram_gb if isinstance(ram_gb, int) else None,
        storage_gb=storage_gb if isinstance(storage_gb, int) else None,
        screen_inch=float(screen_inch) if screen_inch is not None else None,
        gpu=gpu,
        exact_fingerprint=_hash(exact_payload),
        family_fingerprint=_hash(family_payload) if family_payload else None,
        identity_specs=identity_specs,
    )


def _conflict(left: Any, right: Any, tolerance: float = 0.0) -> bool:
    if left is None or right is None:
        return False
    try:
        return abs(float(left) - float(right)) > tolerance
    except (TypeError, ValueError):
        return str(left).lower() != str(right).lower()


def _value_present(value: Any) -> bool:
    return value not in (None, "", [], {})


def _variant_keys_complete(category: str, specs: dict[str, Any]) -> bool:
    """True when required variant-defining fields are present for exact identity."""
    adapter = get_adapter(category if category != "audio" else "headphones")
    if adapter is None:
        return False
    keys = adapter.variant_keys()
    if not keys:
        # No variant dimensions — model/family evidence alone may be enough.
        return True
    return all(_value_present(specs.get(key)) for key in keys)


def _has_strong_exact_evidence(
    *,
    model_codes: tuple[str, ...],
    family: str | None,
    category: str,
    specs: dict[str, Any],
) -> bool:
    """Exact merge requires positive identity evidence, not merely 'no conflict'."""
    if strong_model_codes(model_codes):
        return True
    # Weak series codes alone are not strong exact evidence.
    if model_codes and not any(is_weak_series_model_code(c) for c in model_codes):
        return True
    if family and _variant_keys_complete(category, specs):
        return True
    return False


def _classify_laptop(left: ProductIdentity, right: ProductIdentity) -> Relation:
    shared_models = set(left.model_codes) & set(right.model_codes)
    strong_shared = strong_model_codes(shared_models)
    weak_shared = {m for m in shared_models if is_weak_series_model_code(m)}
    model_conflict = bool(left.model_codes and right.model_codes and not shared_models)
    spec_conflict = any(
        (
            _conflict(left.ram_gb, right.ram_gb),
            _conflict(left.storage_gb, right.storage_gb),
            _conflict(left.screen_inch, right.screen_inch, tolerance=0.25),
        )
    )
    cpu_conflict = not cpu_models_compatible(left.cpu_models, right.cpu_models)
    gpu_conflict = discrete_gpu_conflict(left.gpu, right.gpu)

    if strong_shared and not spec_conflict and not cpu_conflict and not gpu_conflict:
        return "exact"
    # Weak chassis codes need agreeing discrete GPU (when present) to exact-merge.
    if (
        weak_shared
        and not strong_shared
        and not spec_conflict
        and not cpu_conflict
        and not gpu_conflict
        and (not left.gpu or not right.gpu or left.gpu == right.gpu)
    ):
        if left.gpu and right.gpu and left.gpu == right.gpu:
            return "exact"
        # Both missing GPU with only a weak series code → related, not exact.
        return "related"
    if left.exact_fingerprint == right.exact_fingerprint:
        return "exact"
    if left.family_fingerprint and left.family_fingerprint == right.family_fingerprint:
        return "variant" if (model_conflict or spec_conflict or cpu_conflict or gpu_conflict) else "exact"
    if left.brand and left.brand == right.brand and (left.family == right.family or left.cpu_series == right.cpu_series):
        return "related"
    return "conflict" if model_conflict and cpu_conflict else "related"


def classify_relation(left: ProductIdentity, right: ProductIdentity) -> Relation:
    if not _categories_compatible(left.category, right.category):
        return "conflict"
    if left.brand and right.brand and left.brand != right.brand:
        return "conflict"

    if left.category == "laptop" and right.category == "laptop":
        return _classify_laptop(left, right)

    left_specs = _deserialize_specs(left.identity_specs)
    right_specs = _deserialize_specs(right.identity_specs)
    left_specs.setdefault("model_codes", list(left.model_codes))
    right_specs.setdefault("model_codes", list(right.model_codes))
    left_specs.setdefault("family", left.family)
    right_specs.setdefault("family", right.family)
    left_specs.setdefault("brand", left.brand)
    right_specs.setdefault("brand", right.brand)

    category = left.category if left.category != "audio" else "headphones"
    conflicts = hard_conflicts(category, left_specs, right_specs)
    shared_models = set(left.model_codes) & set(right.model_codes)

    if conflicts:
        # Variant fields that conflict → do not exact-merge; prefer variant when family matches.
        if left.family_fingerprint and left.family_fingerprint == right.family_fingerprint:
            return "variant"
        if shared_models:
            return "variant"
        return "conflict"

    # Shared reliable model/SKU codes remain strong exact evidence.
    if shared_models:
        return "exact"

    left_strong = _has_strong_exact_evidence(
        model_codes=left.model_codes,
        family=left.family,
        category=category,
        specs=left_specs,
    )
    right_strong = _has_strong_exact_evidence(
        model_codes=right.model_codes,
        family=right.family,
        category=category,
        specs=right_specs,
    )

    if left.exact_fingerprint == right.exact_fingerprint and left_strong and right_strong:
        return "exact"

    # Family match alone is never enough when variant-defining fields are missing.
    if left.family_fingerprint and left.family_fingerprint == right.family_fingerprint:
        if left_strong and right_strong:
            return "exact"
        return "related"

    if left.brand and left.brand == right.brand and left.family and left.family == right.family:
        return "related"
    return "related"
