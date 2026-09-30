"""Search-index readiness for multi-category catalog (foundational only).

Public search remains laptop-first by design until a dedicated search task.
This module documents what already works and what must change next — without
redesigning the public search endpoint.
"""

from __future__ import annotations

from typing import Any

from mayabu.platforms.coverage import CATALOG_CATEGORIES


# Columns on product_search_documents that are laptop-shaped projections of specs JSONB.
LAPTOP_SHAPED_INDEX_COLUMNS: tuple[str, ...] = (
    "cpu_series",
    "cpu_models_text",
    "gpu",
    "ram_gb",
    "storage_gb",
    "screen_inch",
)

# Generic columns already usable for any category.
GENERIC_INDEX_COLUMNS: tuple[str, ...] = (
    "product_id",
    "brand",
    "category",
    "canonical_title",
    "title_norm",
    "specs",  # JSONB — category-specific fields live here
    "family",
    "model_codes_text",
    "best_price",
    "best_platform",
    "platform_count",
    "offer_count",
    "search_text",
    "search_vector",
)


def search_index_blockers() -> list[dict[str, str]]:
    """What currently prevents non-laptop categories from being publicly searchable."""
    return [
        {
            "area": "query_parser",
            "blocker": "mayabu/search/query_parser.py forces detected_category=laptop and marks non-laptop queries irrelevant",
            "safe_next": "Detect catalog categories from query tokens; keep public exposure gated until ranking is ready",
        },
        {
            "area": "public_search_api",
            "blocker": "Search endpoint / ranking still assumes laptop facet filters (cpu/ram/storage/screen)",
            "safe_next": "Add category filter + generic facets; keep laptop facets as category-specific overlays",
        },
        {
            "area": "index_projections",
            "blocker": "product_search_documents projects laptop-shaped columns; other categories leave them null",
            "safe_next": "Keep specs JSONB as source of truth; optionally project a few category-agnostic helper columns later",
        },
        {
            "area": "demand_signal",
            "blocker": "Demand scoring treats non-laptop queries as low relevance",
            "safe_next": "Score by detected catalog category once public search supports them",
        },
    ]


def search_index_readiness_report() -> dict[str, Any]:
    """Public multi-category search is enabled for ready categories.

    Camera remains experimental. Unknown/accessory stay excluded from public search.
    """
    from mayabu.search.category_registry import public_search_categories

    return {
        "can_store_non_laptop_documents": True,
        "public_search_exposes_non_laptop": True,
        "public_categories": list(public_search_categories()),
        "generic_columns": list(GENERIC_INDEX_COLUMNS),
        "laptop_shaped_optional_columns": list(LAPTOP_SHAPED_INDEX_COLUMNS),
        "catalog_categories": list(CATALOG_CATEGORIES),
        "blockers": [
            b
            for b in search_index_blockers()
            if b["area"] not in {"query_parser", "public_search_api"}
        ],
        "recommended_next_task": (
            "Category landing pages + SEO surfaces; deepen camera readiness; "
            "optional contextual facet counts if measured cheaply"
        ),
    }


__all__ = [
    "GENERIC_INDEX_COLUMNS",
    "LAPTOP_SHAPED_INDEX_COLUMNS",
    "search_index_blockers",
    "search_index_readiness_report",
]
