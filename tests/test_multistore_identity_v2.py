"""Multi-store V2: identity, orphans, Flipkart titles, accessory gates."""

from __future__ import annotations

from mayabu.catalog.model_codes import extract_model_codes, normalize_model_code
from mayabu.catalog.title_quality import is_marketing_bullet_title, pick_best_title
from mayabu.domain.matching import assess_product_match
from mayabu.domain.product_type import classify_product_type, product_types_compatible


def test_flipkart_bullet_title_rejected() -> None:
    bad = "50MP Camera, 5000mAh Battery, AMOLED Display, 8GB RAM"
    assert is_marketing_bullet_title(bad)
    assert pick_best_title(bad, "Samsung Galaxy S24 8GB 128GB") == "Samsung Galaxy S24 8GB 128GB"


def test_camera_accessory_never_exact_matches_body() -> None:
    listing = {
        "title": "PICO Silicon Cover Protective Camera case Cover Compatible for Canon EOS R10 -RED",
        "category": "camera",
        "specs": {"brand": "canon", "model_codes": ["EOSR10"], "category": "camera"},
    }
    product = {
        "canonical_title": "Canon EOS R10 24.2MP Mirrorless Camera (18-150 mm Lens)",
        "category": "camera",
        "brand": "canon",
        "specs": {"brand": "canon", "model_codes": ["EOSR10"], "category": "camera"},
    }
    assert classify_product_type(listing["title"], category="camera") == "camera_accessory"
    assessment = assess_product_match(listing, product)
    assert not assessment.merge_allowed
    assert assessment.relation == "conflict"
    assert "product_type" in (assessment.evidence.get("reject") or [])


def test_soundbar_is_not_a_headphone() -> None:
    assert classify_product_type(
        "Samsung HW-Q990H 11.1.4ch Wireless Atmos Soundbar",
        category="headphones",
    ) == "audio_accessory"
    assert classify_product_type(
        "Sony WH-1000XM5 Wireless Headphones",
        category="headphones",
    ) == "product"


def test_product_types_compatible_body_kit_not_accessory() -> None:
    assert not product_types_compatible("camera_accessory", "camera_body")
    assert product_types_compatible("camera_body", "camera_body")


def test_normalize_rejects_junk_model_codes() -> None:
    assert normalize_model_code("WIRED") is None
    assert normalize_model_code("5G") is None
    assert normalize_model_code("BLACK") is None
    assert normalize_model_code("SM-S921B") == "SM-S921B"


def test_smartphone_storage_conflict_blocks_exact() -> None:
    listing = {
        "title": "Samsung Galaxy S24 8GB 256GB SM-S921B",
        "category": "smartphone",
        "specs": {
            "brand": "samsung",
            "model_codes": ["SM-S921B"],
            "ram_gb": 8,
            "storage_gb": 256,
            "category": "smartphone",
        },
    }
    product = {
        "canonical_title": "Samsung Galaxy S24 8GB 128GB",
        "category": "smartphone",
        "brand": "samsung",
        "specs": {
            "brand": "samsung",
            "model_codes": ["SM-S921B"],
            "ram_gb": 8,
            "storage_gb": 128,
            "category": "smartphone",
        },
    }
    assessment = assess_product_match(listing, product)
    assert not assessment.merge_allowed


def test_tv_size_conflict() -> None:
    listing = {
        "title": "LG OLED55C3PSA 55 inch",
        "category": "television",
        "specs": {
            "brand": "lg",
            "model_codes": ["OLED55C3PSA"],
            "screen_size_inch": 55,
            "category": "television",
        },
    }
    product = {
        "canonical_title": "LG OLED65C3PSA 65 inch",
        "category": "television",
        "brand": "lg",
        "specs": {
            "brand": "lg",
            "model_codes": ["OLED65C3PSA"],
            "screen_size_inch": 65,
            "category": "television",
        },
    }
    assessment = assess_product_match(listing, product)
    assert not assessment.merge_allowed


def test_tv_frame_model_aliases_match() -> None:
    from mayabu.domain.categories.television import TelevisionAdapter

    adapter = TelevisionAdapter()
    full = adapter.extract_specs(
        "Samsung 138 cm (55 inches), The Frame 4K Vision AI Smart TV, Black, QA55LS03HEUL"
    )
    short = adapter.extract_specs("SAMSUNG LS03H 140 cm (55 inch) QLED Smart TV")
    assert "LS03H" in full["model_codes"]
    assert "LS03H" in short["model_codes"]
    assessment = assess_product_match(
        {
            "title": "Samsung QA55LS03HEUL 55 inch",
            "category": "television",
            "specs": full,
        },
        {
            "canonical_title": "SAMSUNG LS03H 55 inch",
            "category": "television",
            "brand": "samsung",
            "specs": short,
        },
    )
    assert assessment.merge_allowed


def test_extract_phone_model_from_title() -> None:
    hits = extract_model_codes(
        title="Samsung Galaxy S24 SM-S921B 8GB 128GB",
        category="smartphone",
    )
    codes = {h.code for h in hits}
    assert "SM-S921B" in codes


def test_brand_only_title_rejected() -> None:
    assert is_marketing_bullet_title("Apple")
    assert is_marketing_bullet_title("Samsung")
    assert not is_marketing_bullet_title("Apple iPhone 16 128GB")


def test_smartphone_family_storage_exact_without_ram() -> None:
    """Indian retail titles often omit RAM; family + storage must still exact-merge."""
    listing = {
        "title": "Apple iPhone 16 (Black, 128 GB)",
        "category": "smartphone",
        "specs": {
            "brand": "apple",
            "family": "iphone_16",
            "storage_gb": 128,
            "category": "smartphone",
        },
    }
    product = {
        "canonical_title": "Apple iPhone 16 128 GB, Black",
        "category": "smartphone",
        "brand": "apple",
        "specs": {
            "brand": "apple",
            "family": "iphone_16",
            "storage_gb": 128,
            "category": "smartphone",
        },
    }
    assessment = assess_product_match(listing, product)
    assert assessment.merge_allowed
    assert assessment.relation == "exact"


def test_smartphone_four_store_same_sku() -> None:
    base_specs = {
        "brand": "samsung",
        "family": "galaxy_s24",
        "model_codes": ["SM-S921B"],
        "ram_gb": 8,
        "storage_gb": 128,
        "category": "smartphone",
    }
    product = {
        "canonical_title": "Samsung Galaxy S24 8GB 128GB",
        "category": "smartphone",
        "brand": "samsung",
        "specs": dict(base_specs),
    }
    for title in (
        "Samsung Galaxy S24 SM-S921B 8GB 128GB",
        "SAMSUNG Galaxy S24 (8GB RAM, 128GB, Onyx Black)",
        "Samsung Galaxy S24 5G 128 GB, 8 GB RAM",
        "Samsung Galaxy S24 8GB/128GB Black",
    ):
        listing = {
            "title": title,
            "category": "smartphone",
            "specs": dict(base_specs),
        }
        assessment = assess_product_match(listing, product)
        assert assessment.merge_allowed, title


def test_smartphone_ram_conflict_not_silent_merge() -> None:
    listing = {
        "title": "Samsung Galaxy A36 8GB 256GB",
        "category": "smartphone",
        "specs": {
            "brand": "samsung",
            "family": "galaxy_a36_5g",
            "ram_gb": 8,
            "storage_gb": 256,
            "category": "smartphone",
        },
    }
    product = {
        "canonical_title": "Samsung Galaxy A36 12GB 256GB",
        "category": "smartphone",
        "brand": "samsung",
        "specs": {
            "brand": "samsung",
            "family": "galaxy_a36_5g",
            "ram_gb": 12,
            "storage_gb": 256,
            "category": "smartphone",
        },
    }
    assessment = assess_product_match(listing, product)
    assert not assessment.merge_allowed


def test_public_search_requires_priced_platform() -> None:
    from pathlib import Path

    src = Path("mayabu/search/search_repository.py").read_text(encoding="utf-8")
    assert "psi.best_price is not null" in src
    assert "platform_count" in src


def test_orphan_docs_not_in_public_eligibility_sql() -> None:
    """Orphan synthetic search docs must not satisfy public Search gates."""
    from pathlib import Path

    src = Path("mayabu/search/search_repository.py").read_text(encoding="utf-8")
    assert "psi.best_price is not null" in src and "psi.best_price > 0" in src
    assert "coalesce(psi.platform_count, 0) >= 1" in src
    homepage = Path("mayabu/search/homepage_discovery.py").read_text(encoding="utf-8")
    assert "platform_count" in homepage
    seo = Path("mayabu/search/seo_sitemap.py").read_text(encoding="utf-8")
    assert "platform_count" in seo


def test_flipkart_mob_sku_rejected_as_model_code() -> None:
    assert normalize_model_code("MOBHFN6Y3HST3PZQ") is None
    assert normalize_model_code("SM-S921B") == "SM-S921B"
