"""Authoritative public-search category registry.

One place for: public enablement, aliases, facet/filter allowlists, display specs.
Camera stays experimental until ingestion/matching evidence is stronger.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

SearchStatus = Literal["public", "experimental", "disabled"]
SortOption = Literal["relevance", "price_asc", "price_desc"]

SEARCH_CONTRACT_VERSION = "v6"


@dataclass(frozen=True, slots=True)
class FacetDef:
    key: str
    label: str
    source: Literal["column", "specs", "price"] = "specs"


@dataclass(frozen=True, slots=True)
class CategorySearchInfo:
    slug: str
    display_name: str
    public_search_enabled: bool
    status: SearchStatus
    aliases: tuple[str, ...]
    # Spec keys clients may filter / facet (never arbitrary JSON paths).
    filterable_keys: tuple[str, ...]
    facet_defs: tuple[FacetDef, ...]
    identity_fields: tuple[str, ...]
    display_spec_keys: tuple[str, ...]
    ranking_keys: tuple[str, ...] = ()
    supporting_rank_keys: tuple[str, ...] = ()


_CATEGORIES: dict[str, CategorySearchInfo] = {}


def _register(info: CategorySearchInfo) -> None:
    _CATEGORIES[info.slug] = info


def _seed() -> None:
    if _CATEGORIES:
        return

    _register(
        CategorySearchInfo(
            slug="laptop",
            display_name="Laptops",
            public_search_enabled=True,
            status="public",
            aliases=("laptop", "laptops", "notebook", "notebooks", "gaming laptop", "chromebook", "macbook"),
            filterable_keys=("brand", "ram_gb", "storage_gb", "screen_inch", "cpu_series", "gpu"),
            facet_defs=(
                FacetDef("brand", "Brand", "column"),
                FacetDef("ram_gb", "RAM", "column"),
                FacetDef("storage_gb", "Storage", "column"),
                FacetDef("cpu_series", "CPU", "column"),
                FacetDef("gpu", "GPU", "column"),
                FacetDef("best_price", "Price", "price"),
            ),
            identity_fields=("brand", "model_codes", "family", "ram_gb", "storage_gb", "cpu_series"),
            display_spec_keys=("ram_gb", "storage_gb", "cpu_series", "gpu", "screen_inch"),
            ranking_keys=("model_codes", "family", "ram_gb", "storage_gb", "cpu_series", "gpu"),
        )
    )
    _register(
        CategorySearchInfo(
            slug="smartphone",
            display_name="Smartphones",
            public_search_enabled=True,
            status="public",
            aliases=("smartphone", "smartphones", "phone", "phones", "mobile", "mobiles", "mobile phone"),
            filterable_keys=("brand", "ram_gb", "storage_gb", "chipset", "network_generation"),
            facet_defs=(
                FacetDef("brand", "Brand", "column"),
                FacetDef("ram_gb", "RAM", "specs"),
                FacetDef("storage_gb", "Storage", "specs"),
                FacetDef("network_generation", "Network", "specs"),
                FacetDef("best_price", "Price", "price"),
            ),
            identity_fields=("brand", "model_codes", "family", "ram_gb", "storage_gb"),
            display_spec_keys=("ram_gb", "storage_gb", "chipset", "network_generation"),
            ranking_keys=("model_codes", "family", "ram_gb", "storage_gb"),
            supporting_rank_keys=("chipset", "network_generation"),
        )
    )
    _register(
        CategorySearchInfo(
            slug="television",
            display_name="Televisions",
            public_search_enabled=True,
            status="public",
            aliases=("television", "televisions", "tv", "tvs", "smart tv", "oled tv", "qled tv", "led tv"),
            filterable_keys=("brand", "screen_size_inch", "panel_type", "resolution", "refresh_rate_hz"),
            facet_defs=(
                FacetDef("brand", "Brand", "column"),
                FacetDef("screen_size_inch", "Screen size", "specs"),
                FacetDef("panel_type", "Panel", "specs"),
                FacetDef("resolution", "Resolution", "specs"),
                FacetDef("best_price", "Price", "price"),
            ),
            identity_fields=("brand", "model_codes", "screen_size_inch"),
            display_spec_keys=("screen_size_inch", "panel_type", "resolution", "refresh_rate_hz", "smart_platform"),
            ranking_keys=("model_codes", "family", "screen_size_inch"),
            supporting_rank_keys=("panel_type", "resolution", "refresh_rate_hz"),
        )
    )
    _register(
        CategorySearchInfo(
            slug="refrigerator",
            display_name="Refrigerators",
            public_search_enabled=True,
            status="public",
            aliases=("refrigerator", "refrigerators", "fridge", "fridges"),
            filterable_keys=("brand", "capacity_l", "door_type", "star_rating", "frost_type"),
            facet_defs=(
                FacetDef("brand", "Brand", "column"),
                FacetDef("capacity_l", "Capacity", "specs"),
                FacetDef("door_type", "Door type", "specs"),
                FacetDef("best_price", "Price", "price"),
            ),
            identity_fields=("brand", "model_codes", "capacity_l", "door_type"),
            display_spec_keys=("capacity_l", "door_type", "frost_type", "star_rating"),
            ranking_keys=("model_codes", "capacity_l", "door_type"),
            supporting_rank_keys=("frost_type", "star_rating"),
        )
    )
    _register(
        CategorySearchInfo(
            slug="washing_machine",
            display_name="Washing Machines",
            public_search_enabled=True,
            status="public",
            aliases=("washing machine", "washing machines", "washer", "washers"),
            filterable_keys=("brand", "capacity_kg", "load_type", "automation_type", "star_rating", "rpm"),
            facet_defs=(
                FacetDef("brand", "Brand", "column"),
                FacetDef("capacity_kg", "Capacity", "specs"),
                FacetDef("load_type", "Load type", "specs"),
                FacetDef("automation_type", "Automation", "specs"),
                FacetDef("best_price", "Price", "price"),
            ),
            identity_fields=("brand", "model_codes", "capacity_kg", "load_type", "automation_type"),
            display_spec_keys=("capacity_kg", "load_type", "automation_type", "rpm", "star_rating"),
            ranking_keys=("model_codes", "capacity_kg", "load_type", "automation_type"),
            supporting_rank_keys=("rpm", "star_rating"),
        )
    )
    _register(
        CategorySearchInfo(
            slug="tws",
            display_name="True Wireless Earbuds",
            public_search_enabled=True,
            status="public",
            aliases=("tws", "earbuds", "ear buds", "true wireless", "true wireless earbuds", "airpods"),
            filterable_keys=("brand", "anc", "connectivity", "generation", "codec"),
            facet_defs=(
                FacetDef("brand", "Brand", "column"),
                FacetDef("anc", "ANC", "specs"),
                FacetDef("connectivity", "Connectivity", "specs"),
                FacetDef("best_price", "Price", "price"),
            ),
            identity_fields=("brand", "model_codes", "family", "generation"),
            display_spec_keys=("anc", "generation", "codec", "bluetooth_version"),
            ranking_keys=("model_codes", "family", "generation"),
            supporting_rank_keys=("anc", "codec"),
        )
    )
    _register(
        CategorySearchInfo(
            slug="headphones",
            display_name="Headphones",
            public_search_enabled=True,
            status="public",
            aliases=("headphones", "headphone", "headset", "over ear", "on ear"),
            filterable_keys=("brand", "form_factor", "connectivity", "anc", "codec"),
            facet_defs=(
                FacetDef("brand", "Brand", "column"),
                FacetDef("form_factor", "Form factor", "specs"),
                FacetDef("connectivity", "Connectivity", "specs"),
                FacetDef("anc", "ANC", "specs"),
                FacetDef("best_price", "Price", "price"),
            ),
            identity_fields=("brand", "model_codes", "family", "form_factor", "connectivity"),
            display_spec_keys=("form_factor", "connectivity", "anc", "codec"),
            ranking_keys=("model_codes", "family", "form_factor", "connectivity"),
            supporting_rank_keys=("anc", "codec"),
        )
    )
    _register(
        CategorySearchInfo(
            slug="camera",
            display_name="Cameras",
            public_search_enabled=True,
            status="public",
            aliases=("camera", "cameras", "mirrorless", "dslr", "ilce", "eos"),
            filterable_keys=("camera_type", "body_only", "kit_lens", "sensor_format", "mount"),
            facet_defs=(
                FacetDef("brand", "Brand", "column"),
                FacetDef("camera_type", "Type", "specs"),
                FacetDef("sensor_format", "Sensor", "specs"),
                FacetDef("body_only", "Body only", "specs"),
                FacetDef("best_price", "Price", "price"),
            ),
            identity_fields=("brand", "model_codes", "body_only", "kit_lens"),
            display_spec_keys=("camera_type", "sensor_format", "megapixels", "body_only", "kit_lens"),
            ranking_keys=("model_codes", "family", "body_only", "kit_lens"),
        )
    )


def all_search_categories() -> tuple[CategorySearchInfo, ...]:
    _seed()
    return tuple(_CATEGORIES.values())


def get_search_category(slug: str | None) -> CategorySearchInfo | None:
    _seed()
    if not slug:
        return None
    key = slug.strip().lower().replace("-", "_").replace(" ", "_")
    if key == "audio":
        key = "headphones"
    return _CATEGORIES.get(key)


def public_search_categories() -> tuple[str, ...]:
    return tuple(c.slug for c in all_search_categories() if c.public_search_enabled)


def resolve_category_alias(text: str) -> str | None:
    """Match longest alias token phrase in normalized text."""
    _seed()
    norm = " ".join((text or "").lower().split())
    best: str | None = None
    best_len = 0
    for info in _CATEGORIES.values():
        for alias in info.aliases:
            if alias in norm and len(alias) > best_len:
                # Prefer public categories when alias length ties later.
                best = info.slug
                best_len = len(alias)
    return best


def validate_public_category(slug: str | None) -> CategorySearchInfo:
    """Raise ValueError for unknown/disabled/experimental explicit requests."""
    info = get_search_category(slug)
    if info is None:
        raise ValueError("invalid_category")
    if not info.public_search_enabled:
        raise ValueError("category_not_available")
    return info


def is_filterable_key(category: str | None, key: str) -> bool:
    info = get_search_category(category)
    if info is None:
        return False
    return key in info.filterable_keys


def display_specs_for(category: str | None, specs: dict[str, Any] | None) -> dict[str, Any]:
    info = get_search_category(category)
    raw = specs if isinstance(specs, dict) else {}
    if info is None:
        return {}
    out: dict[str, Any] = {}
    for key in info.display_spec_keys:
        value = raw.get(key)
        if value not in (None, "", [], {}):
            out[key] = value
    return out


__all__ = [
    "CategorySearchInfo",
    "FacetDef",
    "SEARCH_CONTRACT_VERSION",
    "SortOption",
    "SearchStatus",
    "all_search_categories",
    "display_specs_for",
    "get_search_category",
    "is_filterable_key",
    "public_search_categories",
    "resolve_category_alias",
    "validate_public_category",
]
