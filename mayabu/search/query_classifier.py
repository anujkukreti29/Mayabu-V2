"""Classifies search queries for Mayabu."""

from __future__ import annotations

from mayabu.search.query_parser import ParsedQuery, parse_query


def classify_query(query: str) -> ParsedQuery:
    """Return a parsed query with relevance and intent flags."""
    return parse_query(query)
