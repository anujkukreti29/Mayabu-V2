"""Multi-category multi-store scale V3 tests."""

from __future__ import annotations

from mayabu.catalog.product_images import image_dedupe_key, normalize_image_url
from mayabu.catalog.title_quality import is_marketing_bullet_title, sanitize_product_title
from mayabu.catalog.tv_aliases import expand_tv_model_aliases
from mayabu.domain.categories.tws import TwsAdapter
from mayabu.domain.matching import assess_product_match
from mayabu.domain.product_type import classify_product_type


def test_sanitize_flipkart_seo_suffix() -> None:
    dirty = "Apple iPhone 18 Pro (256 GB Storage) Online at Best Price On Flipkart."
    clean = sanitize_product_title(dirty)
    assert clean is not None
    assert "best price" not in clean.lower()
    assert "iphone 18 pro" in clean.lower()
    assert is_marketing_bullet_title("50MP Camera, 5000mAh Battery, AMOLED Display")


def test_amazon_brand_only_never_exact_before_detail() -> None:
    listing = {
        "title": "Samsung",
        "category": "smartphone",
        "specs": {"brand": "samsung", "category": "smartphone"},
    }
    product = {
        "canonical_title": "Samsung Galaxy S25 8GB 256GB",
        "category": "smartphone",
        "brand": "samsung",
        "specs": {
            "brand": "samsung",
            "family": "galaxy_s25",
            "storage_gb": 256,
            "ram_gb": 8,
            "category": "smartphone",
        },
    }
    # Brand-only should not exact-merge even if brand matches.
    assessment = assess_product_match(listing, product)
    assert not assessment.merge_allowed


def test_tv_aliases_and_size_gate() -> None:
    codes = expand_tv_model_aliases(["QA55LS03HEUL", "LS03H"])
    assert "LS03H" in codes
    assert "QA55LS03HEUL" in codes
    size_prefixed = expand_tv_model_aliases(["55Q7F", "55U8400F"])
    assert "Q7F" in size_prefixed
    assert "U8400F" in size_prefixed
    listing = {
        "title": "Samsung QA55LS03HEUL 55 inch",
        "category": "television",
        "specs": {
            "brand": "samsung",
            "model_codes": codes,
            "screen_size_inch": 55,
            "category": "television",
        },
    }
    product55 = {
        "canonical_title": "SAMSUNG LS03H 55 inch",
        "category": "television",
        "brand": "samsung",
        "specs": {
            "brand": "samsung",
            "model_codes": ["LS03H"],
            "screen_size_inch": 55,
            "category": "television",
        },
    }
    product65 = {
        **product55,
        "canonical_title": "SAMSUNG LS03H 65 inch",
        "specs": {**product55["specs"], "screen_size_inch": 65},
    }
    assert assess_product_match(listing, product55).merge_allowed
    assert not assess_product_match(listing, product65).merge_allowed
    # Size-prefixed retailer code must merge with bare series at same size.
    croma = {
        "title": "SAMSUNG U8400F 55 inch",
        "category": "television",
        "specs": {
            "brand": "samsung",
            "model_codes": expand_tv_model_aliases(["U8400F"]),
            "screen_size_inch": 55,
            "category": "television",
        },
    }
    reliance = {
        "canonical_title": "Samsung 55U8400F 55 inch",
        "category": "television",
        "brand": "samsung",
        "specs": {
            "brand": "samsung",
            "model_codes": expand_tv_model_aliases(["55U8400F"]),
            "screen_size_inch": 55,
            "category": "television",
        },
    }
    assert assess_product_match(croma, reliance).merge_allowed


def test_tws_generation_and_accessory() -> None:
    adapter = TwsAdapter()
    buds3 = adapter.extract_specs("SAMSUNG Galaxy Buds 3 SMR530NZWAINU ANC")
    buds2 = adapter.extract_specs("Samsung Galaxy Buds 2 Pro Wireless")
    buds3_fe = adapter.extract_specs("SAMSUNG Galaxy Buds3 FE SM-R420NZAAINU")
    buds3_pro = adapter.extract_specs("SAMSUNG Galaxy Buds3 Pro SM-R630NZWAINU")
    assert buds3.get("family")
    assert buds2.get("family")
    assert buds3.get("family") != buds2.get("family")
    assert buds3_fe.get("family") != buds3_pro.get("family")
    listing = {
        "title": "Samsung Galaxy Buds 3 ANC",
        "category": "tws",
        "specs": buds3,
    }
    product = {
        "canonical_title": "Samsung Galaxy Buds 2 Pro",
        "category": "tws",
        "brand": "samsung",
        "specs": buds2,
    }
    assert not assess_product_match(listing, product).merge_allowed
    assert not assess_product_match(
        {"title": buds3_fe and "FE", "category": "tws", "specs": buds3_fe},
        {
            "canonical_title": "Buds3 Pro",
            "category": "tws",
            "brand": "samsung",
            "specs": buds3_pro,
        },
    ).merge_allowed
    # Sony family normalization enables exact across hyphen variants.
    s1 = adapter.extract_specs("Sony WF-1000XM5 Wireless Noise Cancelling")
    s2 = adapter.extract_specs("Sony WF1000XM5 Headphones")
    assert s1.get("family") == s2.get("family")
    assert classify_product_type(
        "Silicone Case Cover for Galaxy Buds 3", category="tws"
    ).endswith("accessory") or "accessory" in classify_product_type(
        "Silicone Case Cover for Galaxy Buds 3", category="tws"
    )


def test_appliance_capacity_alone_does_not_merge() -> None:
    listing = {
        "title": "LG 260L Frost Free Refrigerator GL-I292RPZL",
        "category": "refrigerator",
        "specs": {
            "brand": "lg",
            "model_codes": ["GL-I292RPZL"],
            "capacity_l": 260,
            "category": "refrigerator",
        },
    }
    product = {
        "canonical_title": "Samsung 260L Frost Free Refrigerator RT28A3022S8",
        "category": "refrigerator",
        "brand": "samsung",
        "specs": {
            "brand": "samsung",
            "model_codes": ["RT28A3022S8"],
            "capacity_l": 260,
            "category": "refrigerator",
        },
    }
    assert not assess_product_match(listing, product).merge_allowed


def test_image_cdn_dedupe() -> None:
    a = "https://rukminim2.flixcart.com/image/312/312/foo.jpeg?q=70"
    b = "https://rukminim2.flixcart.com/image/832/832/foo.jpeg?q=90"
    na = normalize_image_url(a)
    nb = normalize_image_url(b)
    assert na and nb
    assert image_dedupe_key(a) == image_dedupe_key(b)


def test_review_noise_classifier() -> None:
    from mayabu.catalog.review_hygiene import _is_deterministic_noise

    assert _is_deterministic_noise("Samsung", "smartphone") is not None
    assert _is_deterministic_noise("50MP Camera, 5000mAh Battery, AMOLED Display", "smartphone")
    assert (
        _is_deterministic_noise("Apple iPhone 16 128GB", "smartphone", {"storage_gb": 128})
        is None
    )
