"""Unknown-category products must never appear on public commerce surfaces."""

from __future__ import annotations

from mayabu.search.category_registry import public_search_categories
from mayabu.search.search_repository import _EXCLUDED_PUBLIC_CATEGORIES


def test_unknown_excluded_from_public_categories() -> None:
    assert "unknown" in _EXCLUDED_PUBLIC_CATEGORIES
    assert "accessory" in _EXCLUDED_PUBLIC_CATEGORIES
    public = set(public_search_categories())
    assert "unknown" not in public
    assert "accessory" not in public


def test_unknown_not_in_eight_commerce_categories() -> None:
    allowed = {
        "laptop",
        "smartphone",
        "television",
        "refrigerator",
        "washing_machine",
        "tws",
        "headphones",
        "camera",
    }
    public = set(public_search_categories())
    assert public <= allowed or public == allowed
    assert public & {"unknown", "accessory"} == set()
