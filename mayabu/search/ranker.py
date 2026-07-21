"""Deterministic, bounded product-search ranking."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

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
    if row_value is not None:
        try:
            return int(float(row_value)) == int(float(value))
        except (TypeError, ValueError):
            return str(row_value).lower() == str(value).lower()

    row_specs = row.get("specs")
    if isinstance(row_specs, dict) and row_specs.get(key) is not None:
        return str(row_specs[key]).lower() == str(value).lower()
    return _string_contains(text, value)


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

    if row.get("exact_model_match"):
        score += 95.0
        row["match_group"] = "exact_match"
    elif row.get("family_match"):
        score += 36.0
        if row.get("match_group") != "exact_match":
            row["match_group"] = "similar_variant"

    if brand and str(row.get("brand") or "").lower() == str(brand).lower():
        score += 30.0

    for key, weight in (("cpu", 28), ("gpu", 16), ("model_code", 52)):
        if _string_contains(text, specs.get(key)):
            score += weight

    if _spec_match(row, specs, "ram_gb", text=text):
        score += 18.0
    if _spec_match(row, specs, "storage_gb", text=text):
        score += 18.0

    for key in ("ram_gb", "storage_gb"):
        query_value = specs.get(key)
        row_value = row.get(key)
        if query_value is None or row_value is None:
            continue
        try:
            conflicts = int(float(query_value)) != int(float(row_value))
        except (TypeError, ValueError):
            conflicts = False
        if conflicts:
            score -= 14.0
            if row.get("match_group") == "exact_match":
                row["match_group"] = "similar_variant"

    score += min(32.0, _to_float(row.get("text_rank")) * 32.0)
    score += min(16.0, _to_float(row.get("listing_rank")) * 4.0)
    score += min(14.0, _to_float(row.get("trigram_rank")) * 14.0)

    if row.get("best_price") is not None:
        score += 8.0
    if row.get("platform_count"):
        score += min(20.0, int(row.get("platform_count") or 0) * 5.0)
    if row.get("image_url"):
        score += 2.0
    return round(score, 4)


def rank_products(
    rows: list[dict[str, Any]], specs: dict[str, Any]
) -> list[dict[str, Any]]:
    """Return a ranked copy; query parsing is performed once per result page."""
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
            item.get("last_seen_at") or "",
        ),
        reverse=True,
    )
    return ranked
