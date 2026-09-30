"""Tests for enrichment, overlap discovery, and gallery helpers."""

from __future__ import annotations

from mayabu.catalog.enrichment import completeness_flags, listing_needs_enrichment
from mayabu.catalog.overlap import build_overlap_query
from mayabu.scrapers.detail.models import DetailProduct
from mayabu.scrapers.detail.registry import _images


def test_build_overlap_query_requires_strong_model() -> None:
    assert build_overlap_query(brand="Sony", model_codes=["A"], category="camera") is None
    q = build_overlap_query(
        brand="Sony",
        model_codes=["ILCE-7M4"],
        category="camera",
        specs={},
    )
    assert q is not None
    assert "ILCE-7M4" in q
    assert "Sony" in q


def test_build_overlap_query_adds_phone_variant() -> None:
    q = build_overlap_query(
        brand="Samsung",
        model_codes=["SM-S921B"],
        category="smartphone",
        specs={"ram_gb": 8, "storage_gb": 128},
    )
    assert q is not None
    assert "128GB" in q
    assert "8GB" in q


def test_tv_size_in_query() -> None:
    q = build_overlap_query(
        brand="LG",
        model_codes=["OLED55C3PSA"],
        category="television",
        specs={"screen_size_inch": 55},
    )
    assert q is not None
    assert "55" in q


def test_completeness_flags() -> None:
    flags = completeness_flags(
        specs={"model_codes": ["X1"], "ram_gb": 16, "storage_gb": 512},
        image_count=3,
        store_count=2,
        has_price=True,
    )
    assert flags["has_model_number"]
    assert flags["has_gallery"]
    assert flags["has_multi_store"]
    assert flags["has_key_specs"]


def test_listing_needs_enrichment_when_no_gallery() -> None:
    assert listing_needs_enrichment(
        {"specs": {"model_codes": ["X"], "ram_gb": 8, "storage_gb": 128}, "current_price": 100, "store_count": 1},
        image_count=1,
    )


def test_jsonld_images_extract_list() -> None:
    urls = _images(
        {
            "image": [
                "https://cdn.example/a.jpg",
                {"url": "https://cdn.example/b.jpg"},
                "https://cdn.example/logo-badge.png",
            ]
        }
    )
    assert "https://cdn.example/a.jpg" in urls
    assert "https://cdn.example/b.jpg" in urls
    assert all("logo" not in u for u in urls)


def test_detail_product_gallery_urls_dedupe() -> None:
    detail = DetailProduct(
        platform="amazon",
        url="https://www.amazon.in/dp/X",
        canonical_url="https://www.amazon.in/dp/X",
        image_url="https://cdn.example/a.jpg",
        image_urls=["https://cdn.example/a.jpg", "https://cdn.example/b.jpg", "https://cdn.example/b.jpg"],
    )
    assert detail.gallery_urls() == ["https://cdn.example/a.jpg", "https://cdn.example/b.jpg"]


def test_enrich_listing_handler_registered() -> None:
    from mayabu.jobs import worker

    assert "enrich_listing" in worker._TASK_HANDLERS
    assert "targeted_discovery" in worker._TASK_HANDLERS


def test_task_type_constraint_includes_new_types() -> None:
    from pathlib import Path

    schema = Path("mayabu_db/schema.sql").read_text(encoding="utf-8")
    assert "enrich_listing" in schema
    assert "targeted_discovery" in schema
