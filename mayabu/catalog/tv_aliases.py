"""TV model alias helpers — deterministic manufacturer shorthand ↔ full SKU only."""

from __future__ import annotations

import re
from typing import Iterable

# Known deterministic Samsung Frame / Q series embeddings.
# Full SKUs embed the short series token (LS03H inside QA55LS03HEUL).
_EMBEDDED_SERIES_RE = re.compile(
    r"^(?:QA|QN|UE|QA?)(\d{2})?(LS\d{2}[A-Z]|QN\d{2}[A-Z]|Q\d[A-Z]\d[A-Z]?)",
    re.I,
)

# Retailer titles often prefix screen size onto the series: 55Q7F, 55U8400F, 65QN90F.
_SIZE_PREFIX_RE = re.compile(r"^(\d{2})([A-Z]{1,3}\d{1,4}[A-Z0-9]{0,6})$", re.I)


def expand_tv_model_aliases(codes: Iterable[str]) -> list[str]:
    """Return unique codes including verified embedded series / size-prefix aliases."""
    out: list[str] = []
    seen: set[str] = set()

    def _add(code: str) -> None:
        if not code or code in seen:
            return
        seen.add(code)
        out.append(code)

    for raw in codes:
        code = re.sub(r"[^A-Z0-9]", "", str(raw or "").upper())
        if not code:
            continue
        _add(code)
        m = _EMBEDDED_SERIES_RE.match(code)
        if m:
            series = (m.group(2) or "").upper()
            if series and len(series) >= 4:
                _add(series)
        sm = _SIZE_PREFIX_RE.match(code)
        if sm:
            size, series = sm.group(1), sm.group(2).upper()
            # Only strip when size looks like a TV inch class and series is identity-like.
            if 24 <= int(size) <= 98 and len(series) >= 3:
                _add(series)
                # Keep size-prefixed form when series already present elsewhere.
                _add(f"{size}{series}")
    return out


def primary_tv_model_key(codes: Iterable[str]) -> str:
    """Stable grouping key: prefer shortest non-size-prefixed alias."""
    expanded = expand_tv_model_aliases(codes)
    if not expanded:
        return ""
    # Prefer short series tokens without leading inch digits.
    bare = [c for c in expanded if not re.match(r"^\d{2}[A-Z]", c)]
    pool = bare or expanded
    return min(pool, key=lambda c: (len(c), c))


__all__ = ["expand_tv_model_aliases", "primary_tv_model_key"]
