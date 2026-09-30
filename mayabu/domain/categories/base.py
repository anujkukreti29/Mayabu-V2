"""Category normalization adapters — separate from platform scrapers.

Identity fields drive exact/variant matching.
Supporting fields provide evidence.
Descriptive fields are shown to users but must not force merges/splits.
"""

from __future__ import annotations

import re
from typing import Any, Literal, Protocol

Relation = Literal["exact", "variant", "related", "conflict"]

# Chassis / series tokens like Lenovo "15IRX9" that are shared across GPU SKUs.
# Manufacturer MPNs with hyphens (15-FA2197TX) or letter-led codes (FWT1310BG) stay strong.
_WEAK_SERIES_MODEL_RE = re.compile(r"^\d{2}[A-Z]{2,5}\d{1,2}[A-Z]?$", re.I)


class CategoryAdapter(Protocol):
    name: str

    def extract_specs(self, title: str, *, breadcrumbs: str = "", url: str = "") -> dict[str, Any]:
        """Return normalized specs for this category."""

    def identity_keys(self) -> tuple[str, ...]:
        """Spec keys included in exact identity fingerprints."""

    def variant_keys(self) -> tuple[str, ...]:
        """Keys that distinguish sellable variants when they conflict."""

    def supporting_keys(self) -> tuple[str, ...]:
        """Useful evidence that should not alone force a conflict."""

    def descriptive_keys(self) -> tuple[str, ...]:
        """Marketing / soft fields — never exact-match requirements."""

    def hard_conflicts(self, left: dict[str, Any], right: dict[str, Any]) -> list[str]:
        """Return human-readable conflict reasons, empty if compatible."""

    def price_bounds(self) -> tuple[int, int]:
        """Conservative (min, max) INR sanity bounds for extraction mistakes."""


def _num(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _str(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    return text or None


def _codes(value: Any) -> set[str]:
    if isinstance(value, (list, tuple, set)):
        return {str(v).strip().upper() for v in value if str(v).strip()}
    if value not in (None, ""):
        return {str(value).strip().upper()}
    return set()


def conflict_numeric(left: Any, right: Any, *, tolerance: float = 0.0) -> bool:
    a, b = _num(left), _num(right)
    if a is None or b is None:
        return False
    return abs(a - b) > tolerance


def conflict_text(left: Any, right: Any) -> bool:
    a, b = _str(left), _str(right)
    if not a or not b:
        return False
    return a != b


def model_code_conflict(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_codes = _codes(left.get("model_codes"))
    right_codes = _codes(right.get("model_codes"))
    if left_codes and right_codes and not (left_codes & right_codes):
        return True
    return False


def is_weak_series_model_code(code: str | None) -> bool:
    """True for short digit-led chassis/series codes that are not unique SKUs."""
    text = str(code or "").strip().upper()
    if not text or "-" in text or "_" in text:
        return False
    return bool(_WEAK_SERIES_MODEL_RE.fullmatch(text))


def strong_model_codes(codes: Any) -> set[str]:
    return {c for c in _codes(codes) if not is_weak_series_model_code(c)}


def _normalize_cpu_token(token: str) -> str:
    """Align retail Core-N labels with classic Core iN series for compatibility checks."""
    text = str(token or "").strip().lower()
    if text.startswith("intel_core_i:"):
        return "intel_core:" + text[len("intel_core_i:") :]
    if text.startswith("intel_core_new:"):
        return "intel_core:" + text[len("intel_core_new:") :]
    if text in {"intel_core_i", "intel_core_new"}:
        return "intel_core"
    return text


def cpu_models_compatible(left: Any, right: Any) -> bool:
    """Series-only CPU evidence is compatible with a more specific same-prefix model.

    Example: intel_core_i:5  ≈  intel_core_i:5:13420h
    Distinct full models (…:13420h vs …:13450hx) still conflict.
    Retail Core 5 / Core 7 (`intel_core_new`) aligns with Core i5 / i7 (`intel_core_i`).
    """
    left_set = {
        _normalize_cpu_token(v)
        for v in (left if isinstance(left, (list, tuple, set)) else ([left] if left else []))
        if str(v).strip()
    }
    right_set = {
        _normalize_cpu_token(v)
        for v in (right if isinstance(right, (list, tuple, set)) else ([right] if right else []))
        if str(v).strip()
    }
    left_set.discard("")
    right_set.discard("")
    if not left_set or not right_set:
        return True
    if left_set & right_set:
        return True
    for a in left_set:
        for b in right_set:
            if _chip_tier(a) != _chip_tier(b):
                continue
            if a.startswith(b + ":") or b.startswith(a + ":"):
                return True
    return False


def _chip_tier(token: str) -> str | None:
    """M4 Pro is not a more specific form of M4. Numeric SKUs are."""
    tail = str(token or "").rsplit(":", 1)[-1]
    if tail in {"pro", "max", "ultra"}:
        return tail
    return None


def discrete_gpu_conflict(left_gpu: Any, right_gpu: Any) -> bool:
    """Conflict only when both sides name a discrete GPU family and they differ."""
    left = _str(left_gpu)
    right = _str(right_gpu)
    if not left or not right or left == right:
        return False
    combined = f"{left} {right}"
    if any(token in combined for token in ("rtx", "gtx", "radeon", "arc a", "arc_a")):
        return True
    return left != right


def classify_from_conflicts(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    conflicts: list[str],
    shared_models: bool,
) -> Relation:
    if conflicts:
        return "conflict"
    if shared_models:
        return "exact"
    left_family = _str(left.get("family"))
    right_family = _str(right.get("family"))
    if left_family and right_family and left_family == right_family:
        return "variant"
    return "related"
