"""Compare API contract tests (unit-level, no DB)."""

from __future__ import annotations

from mayabu.api.compare_routes import MAX_COMPARE_IDS, _parse_ids
from mayabu.search.search_repository import _valid_product_uuids


def test_parse_ids_dedupes_and_caps() -> None:
    assert _parse_ids("a, a, b, c, d, e") == ["a", "b", "c", "d"]
    assert len(_parse_ids("1,2,3,4,5")) == MAX_COMPARE_IDS
    assert _parse_ids("") == []
    assert _parse_ids("  , ,x, ") == ["x"]


def test_valid_product_uuids_skips_garbage() -> None:
    good = "1211b369-3b40-474c-b4f2-6847f1e6dfc8"
    assert _valid_product_uuids(["not-a-real-id", good, "also-fake", good]) == [good]
