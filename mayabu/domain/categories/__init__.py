"""Category normalization package."""

from mayabu.domain.categories.registry import (
    CATEGORY_PREFIX,
    CategoryDetection,
    detect_category_from_evidence,
    detect_category_result,
    extract_category_specs,
    extract_generic_specs,
    get_adapter,
    hard_conflicts,
    normalize_category_name,
    price_bounds_for,
)

__all__ = [
    "CATEGORY_PREFIX",
    "CategoryDetection",
    "detect_category_from_evidence",
    "detect_category_result",
    "extract_category_specs",
    "extract_generic_specs",
    "get_adapter",
    "hard_conflicts",
    "normalize_category_name",
    "price_bounds_for",
]
