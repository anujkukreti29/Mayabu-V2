"""Thin wrapper keeping classify_query import path stable."""

from __future__ import annotations

from typing import Any

from mayabu.search.query_parser import ParsedQuery, parse_query


def classify_query(
    query: str,
    *,
    explicit_category: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    category_filters: dict[str, Any] | None = None,
) -> ParsedQuery:
    return parse_query(
        query,
        explicit_category=explicit_category,
        min_price=min_price,
        max_price=max_price,
        category_filters=category_filters,
    )
