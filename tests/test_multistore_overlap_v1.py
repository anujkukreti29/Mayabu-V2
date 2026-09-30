"""Integration-style multi-store overlap + enrichment without live retailers."""

from __future__ import annotations

from mayabu.catalog.overlap import build_overlap_query, missing_platforms
from mayabu.catalog.enrichment import _merge_specs_conservative
from mayabu.domain.matching import assess_product_match


def test_missing_platforms_skips_source() -> None:
    missing = missing_platforms("amazon", "smartphone")
    assert "amazon" not in missing
    assert "flipkart" in missing or "croma" in missing


def test_spec_merge_preserves_identity_conflict() -> None:
    merged, conflicts = _merge_specs_conservative(
        {"ram_gb": 8, "storage_gb": 128, "model_codes": ["SM-A"]},
        {"ram_gb": 12, "storage_gb": 128, "model_codes": ["SM-B"]},
    )
    assert "ram_gb" in conflicts
    assert merged["ram_gb"] == 8
    assert set(merged["model_codes"]) == {"SM-A", "SM-B"}


def test_exact_model_match_allows_merge() -> None:
    listing = {
        "title": "Samsung Galaxy S24 8GB 128GB",
        "category": "smartphone",
        "specs": {
            "brand": "samsung",
            "model_codes": ["SM-S921B"],
            "ram_gb": 8,
            "storage_gb": 128,
        },
    }
    product = {
        "canonical_title": "Samsung Galaxy S24",
        "category": "smartphone",
        "brand": "samsung",
        "specs": {
            "brand": "samsung",
            "model_codes": ["SM-S921B"],
            "ram_gb": 8,
            "storage_gb": 128,
        },
    }
    assessment = assess_product_match(listing, product)
    assert assessment.merge_allowed
    assert assessment.relation in {"exact", "exact_match", "same_product", "variant"} or assessment.score >= 82


def test_storage_conflict_blocks_exact() -> None:
    listing = {
        "title": "Samsung Galaxy S24 8GB 256GB",
        "category": "smartphone",
        "specs": {
            "brand": "samsung",
            "model_codes": ["SM-S921B"],
            "ram_gb": 8,
            "storage_gb": 256,
        },
    }
    product = {
        "canonical_title": "Samsung Galaxy S24",
        "category": "smartphone",
        "brand": "samsung",
        "specs": {
            "brand": "samsung",
            "model_codes": ["SM-S921B"],
            "ram_gb": 8,
            "storage_gb": 128,
        },
    }
    assessment = assess_product_match(listing, product)
    assert not assessment.merge_allowed or assessment.relation in {
        "conflict",
        "variant",
        "similar_variant",
        "needs_review",
    }


def test_overlap_query_not_vague_title() -> None:
    q = build_overlap_query(
        brand="Apple",
        model_codes=["MQD83HN/A"],
        category="headphones",
        specs={},
    )
    assert q is not None
    assert "best bluetooth" not in q.lower()
