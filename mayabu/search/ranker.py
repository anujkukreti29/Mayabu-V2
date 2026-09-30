"""Category-aware scoring layered on the generic ranker core."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from mayabu.search.category_registry import get_search_category
from mayabu.search.intent_rank import intent_adjustment

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP_WORDS = {
    "with",
    "and",
    "the",
    "for",
    "best",
    "buy",
    "price",
    "online",
    "india",
    "laptop",
    "notebook",
    "phone",
    "smartphone",
    "television",
    "tv",
    "refrigerator",
    "fridge",
    "washing",
    "machine",
    "earbuds",
    "headphones",
    "windows",
    "home",
    "office",
    "inch",
    "cm",
    "kg",
}
_TEXT_FIELDS = (
    "canonical_title",
    "title",
    "title_norm",
    "brand",
    "search_text",
    "model_codes_text",
    "cpu_series",
    "family",
)


@dataclass(frozen=True, slots=True)
class _RankContext:
    query_normalized: str
    query_tokens: tuple[str, ...]


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in _TOKEN_RE.findall((text or "").lower())
        if len(token) >= 2 and token not in _STOP_WORDS
    )


def _row_text(row: dict[str, Any]) -> str:
    return " ".join(str(row.get(key) or "") for key in _TEXT_FIELDS).lower()


def _rank_context(specs: dict[str, Any]) -> _RankContext:
    query_tokens = _tokens(str(specs.get("_query") or ""))
    return _RankContext(" ".join(query_tokens), query_tokens)


def _string_contains(text: str, value: Any) -> bool:
    if value is None:
        return False
    candidate = str(value).lower().strip()
    return bool(candidate) and candidate in text


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return default


def _query_match_score(text: str, context: _RankContext) -> float:
    query_tokens = context.query_tokens
    if not query_tokens:
        return 0.0

    title_sequence = _tokens(text)
    title_tokens = set(title_sequence)
    score = 45.0 if context.query_normalized in text else 0.0

    covered = sum(token in title_tokens or token in text for token in query_tokens)
    score += covered / len(query_tokens) * 42.0

    title_text = " ".join(title_sequence)
    leading = 0
    for token in query_tokens[:8]:
        if token not in title_text:
            break
        leading += 1
    score += min(20.0, leading * 2.5)
    return score


def _spec_value(row: dict[str, Any], key: str) -> Any:
    if row.get(key) is not None:
        return row.get(key)
    specs = row.get("specs")
    if isinstance(specs, dict):
        return specs.get(key)
    return None


def _spec_match(
    row: dict[str, Any],
    specs: dict[str, Any],
    key: str,
    *,
    text: str,
    row_key: str | None = None,
) -> bool:
    value = specs.get(key)
    if value is None:
        return False

    row_value = row.get(row_key or key)
    if row_value is None:
        row_value = _spec_value(row, key)
    if row_value is not None:
        try:
            return int(float(row_value)) == int(float(value))
        except (TypeError, ValueError):
            return str(row_value).lower() == str(value).lower()
    return _string_contains(text, value)


def _spec_conflict(row: dict[str, Any], specs: dict[str, Any], key: str, *, tolerance: float = 0.0) -> bool:
    query_value = specs.get(key)
    row_value = _spec_value(row, key)
    if query_value is None or row_value is None:
        return False
    try:
        return abs(float(query_value) - float(row_value)) > tolerance
    except (TypeError, ValueError):
        return str(query_value).lower() != str(row_value).lower()


def score_product(
    row: dict[str, Any],
    specs: dict[str, Any],
    *,
    context: _RankContext | None = None,
) -> float:
    """Score one candidate without changing public search contracts."""
    context = context or _rank_context(specs)
    text = _row_text(row)
    score = _query_match_score(text, context)
    brand = specs.get("brand")
    category = str(row.get("category") or specs.get("_category") or "")

    if row.get("exact_model_match"):
        score += 95.0
        row["match_group"] = "exact_match"
    elif row.get("family_match"):
        score += 36.0
        if row.get("match_group") != "exact_match":
            row["match_group"] = "similar_variant"

    if brand and str(row.get("brand") or "").lower() == str(brand).lower():
        score += 30.0

    # Laptop-compatible text signals (preserve baseline).
    for key, weight in (("cpu", 28), ("gpu", 16), ("model_code", 52)):
        if _string_contains(text, specs.get(key)):
            score += weight

    if _spec_match(row, specs, "ram_gb", text=text):
        score += 18.0
    if _spec_match(row, specs, "storage_gb", text=text):
        score += 18.0

    for key in ("ram_gb", "storage_gb"):
        if _spec_conflict(row, specs, key):
            score -= 14.0
            if row.get("match_group") == "exact_match":
                row["match_group"] = "similar_variant"

    # Category-specific ranking signals from registry allowlists.
    info = get_search_category(category)
    if info:
        for key in info.ranking_keys:
            if key in {"model_codes", "family", "brand"}:
                continue
            if _spec_match(row, specs, key, text=text):
                score += 16.0
            elif _spec_conflict(row, specs, key, tolerance=0.5 if "inch" in key or key.endswith("_l") or key.endswith("_kg") else 0.0):
                score -= 12.0
                if row.get("match_group") == "exact_match":
                    row["match_group"] = "similar_variant"
        for key in info.supporting_rank_keys:
            if _spec_match(row, specs, key, text=text):
                score += 6.0

    # Screen-size intent for TVs (also laptop screen_inch via column).
    if _spec_match(row, specs, "screen_size_inch", text=text) or _spec_match(
        row, specs, "screen_inch", text=text, row_key="screen_inch"
    ):
        score += 20.0
    if _spec_match(row, specs, "panel_type", text=text):
        score += 10.0
    if _spec_match(row, specs, "capacity_l", text=text) or _spec_match(row, specs, "capacity_kg", text=text):
        score += 18.0
    if _spec_match(row, specs, "load_type", text=text) or _spec_match(row, specs, "automation_type", text=text):
        score += 12.0
    if specs.get("anc") and (_spec_value(row, "anc") is True or _string_contains(text, "anc")):
        score += 8.0

    score += min(32.0, _to_float(row.get("text_rank")) * 32.0)
    score += min(16.0, _to_float(row.get("listing_rank")) * 4.0)
    score += min(14.0, _to_float(row.get("trigram_rank")) * 14.0)

    if row.get("best_price") is not None:
        score += 8.0
    if row.get("platform_count"):
        score += min(20.0, int(row.get("platform_count") or 0) * 5.0)
    if row.get("image_url"):
        score += 2.0
    score += intent_adjustment(
        query=str(specs.get("_query") or ""),
        category=category,
        text=" ".join(
            [
                text,
                str(_spec_value(row, "gpu") or ""),
                str(_spec_value(row, "panel_type") or ""),
                str(row.get("family") or ""),
            ]
        ),
    )
    return round(score, 4)


def rank_products(
    rows: list[dict[str, Any]], specs: dict[str, Any]
) -> list[dict[str, Any]]:
    """Return a ranked copy; query parsing is performed once per result page."""
    import time

    from mayabu.monitoring import instrumentation as metrics

    started = time.perf_counter()
    context = _rank_context(specs)
    ranked: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["rank_score"] = score_product(item, specs, context=context)
        ranked.append(item)

    ranked.sort(
        key=lambda item: (
            item.get("match_group") == "exact_match",
            item.get("match_group") == "similar_variant",
            float(item.get("rank_score") or 0),
            int(item.get("platform_count") or 0),
            str(item.get("last_seen_at") or ""),
            str(item.get("product_id") or ""),
        ),
        reverse=True,
    )
    category = str(specs.get("_category") or "unknown")[:40]
    mode = str(specs.get("_search_mode") or "unknown")[:40]
    metrics.SEARCH_RANK.observe(
        (time.perf_counter() - started) * 1000, category=category, search_mode=mode
    )
    return ranked
