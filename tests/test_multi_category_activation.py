"""Multi-category catalog activation: matching, accessories, quality, health."""

from __future__ import annotations

from mayabu.domain.categories.registry import (
    detect_category_result,
    extract_category_specs,
    price_bounds_for,
)
from mayabu.domain.matching import assess_product_match
from mayabu.domain.product_identity import build_identity, classify_relation
from mayabu.monitoring.platform_category_health import score_platform_category_health
from mayabu.platforms.coverage import (
    PRODUCTION_PLATFORMS,
    coverage_matrix,
    get_coverage,
    ingestion_enabled,
    meets_coverage_thresholds,
    production_category_targets,
)
from mayabu.search.index_readiness import search_index_readiness_report
from mayabu_common import listing_id, normalize_raw_listing, normalize_url
from mayabu_db.quality import evaluate_listing
from mayabu_db.variant import build_variant_key


def test_production_coverage_matrix_seeded() -> None:
    cells = coverage_matrix()
    assert len(cells) == len(PRODUCTION_PLATFORMS) * 8
    assert get_coverage("amazon", "smartphone").status == "production"
    assert get_coverage("croma", "refrigerator").status == "production"
    assert get_coverage("jiomart", "laptop").ingestion_enabled is False
    assert get_coverage("bajajelectronics", "television").status == "blocked"
    assert ingestion_enabled("amazon", "laptop") is True
    assert ingestion_enabled("vijaysales", "headphones") is False
    assert ingestion_enabled("vijaysales", "laptop") is True
    targets = production_category_targets()
    assert "smartphone" in targets["amazon"]
    assert "refrigerator" in targets["croma"]
    assert "laptop" in targets.get("vijaysales", ())
    assert "smartphone" in targets.get("poorvika", ())


def test_accessory_rejection_expanded() -> None:
    cases = [
        "phone case for iPhone 15",
        "USB-C phone charger 20W",
        "screen protector tempered glass",
        "TV wall mount bracket 55 inch",
        "TV remote replacement",
        "TV stand wooden unit",
        "fridge cover waterproof",
        "refrigerator stand base",
        "washing-machine cover",
        "washing machine stand trolley",
        "camera lens 50mm prime",
        "camera bag DSLR",
        "tripod for mirrorless camera",
        "earbud case charging",
        "replacement ear tips for buds",
        "headphone cable 3.5mm",
    ]
    for title in cases:
        assert detect_category_result(title=title).category == "accessory", title


def test_cross_platform_smartphone_exact_match() -> None:
    amazon = build_identity(
        "Samsung Galaxy S24 5G (Marble Gray, 8GB RAM, 256GB Storage) SM-S921B",
        category="smartphone",
    )
    flipkart = build_identity(
        "SAMSUNG Galaxy S24 (SM-S921B) 256 GB (8 GB RAM)",
        category="smartphone",
    )
    croma = build_identity(
        "Samsung SM-S921B Galaxy S24 smartphone 8/256",
        category="smartphone",
    )
    reliance = build_identity(
        "Samsung Galaxy S24 SM-S921B 256GB 8GB RAM smartphone",
        category="smartphone",
    )
    assert amazon.ram_gb == 8 and amazon.storage_gb == 256
    assert classify_relation(amazon, flipkart) == "exact"
    assert classify_relation(amazon, croma) == "exact"
    assert classify_relation(flipkart, reliance) == "exact"


def test_false_merge_phone_storage() -> None:
    a = build_identity("Samsung Galaxy S24 8GB 128GB SM-S921B", category="smartphone")
    b = build_identity("Samsung Galaxy S24 8GB 256GB SM-S921B", category="smartphone")
    assert classify_relation(a, b) != "exact"
    assert a.exact_fingerprint != b.exact_fingerprint


def test_false_merge_tv_size() -> None:
    a = build_identity("Samsung 43 inch 4K Smart TV UA43CU8000", category="television")
    b = build_identity("Samsung 55 inch 4K Smart TV UA55CU8000", category="television")
    assert classify_relation(a, b) != "exact"


def test_false_merge_fridge_capacity() -> None:
    a = build_identity("LG 260L Frost Free Double Door Refrigerator GL-S292RDSX", category="refrigerator")
    b = build_identity("LG 340L Frost Free Double Door Refrigerator GL-T372MDSX", category="refrigerator")
    assert classify_relation(a, b) != "exact"


def test_false_merge_washer_capacity_and_load() -> None:
    a = build_identity("LG 7kg Front Load Fully Automatic Washing Machine FHV1207Z4M", category="washing_machine")
    b = build_identity("LG 9kg Front Load Fully Automatic Washing Machine FHV1409Z4M", category="washing_machine")
    c = build_identity("LG 7kg Top Load Fully Automatic Washing Machine T70SKSF1Z", category="washing_machine")
    assert classify_relation(a, b) != "exact"
    assert classify_relation(a, c) != "exact"


def test_false_merge_camera_body_vs_kit() -> None:
    body = build_identity("Sony Alpha ILCE-6400 body only mirrorless", category="camera")
    kit = build_identity("Sony Alpha ILCE-6400 kit 16-50mm mirrorless", category="camera")
    assert classify_relation(body, kit) != "exact"


def test_false_merge_tws_generation() -> None:
    gen2 = build_identity("Samsung Galaxy Buds 2 ANC wireless earbuds", category="tws")
    gen3 = build_identity("Samsung Galaxy Buds 3 ANC wireless earbuds", category="tws")
    assert classify_relation(gen2, gen3) != "exact"
    assert gen2.identity_specs != gen3.identity_specs or gen2.exact_fingerprint != gen3.exact_fingerprint


def test_tws_battery_claim_does_not_split_identical() -> None:
    a = build_identity("OnePlus Buds 3 ANC 30 hours total playback", category="tws")
    b = build_identity("OnePlus Buds 3 ANC up to 32 hours battery", category="tws")
    # Battery is descriptive; generation/family should align.
    assert classify_relation(a, b) in {"exact", "related", "variant"}
    assert classify_relation(a, b) != "conflict"


def test_headphones_wired_vs_wireless_not_exact() -> None:
    wired = build_identity("Sony over-ear wired headphones MDR-ZX110", category="headphones")
    wireless = build_identity("Sony over-ear wireless headphones WH-CH520", category="headphones")
    assert classify_relation(wired, wireless) != "exact"


def test_category_spec_extraction_real_titles() -> None:
    phone = extract_category_specs(
        "Apple iPhone 15 (Blue, 128GB Storage) A3090",
        category="smartphone",
    )
    assert phone["storage_gb"] == 128
    assert str(phone.get("brand") or "").lower() in {"apple", "iphone"} or phone.get("family")
    assert phone.get("spec_schema_version") == 1

    tv = extract_category_specs(
        "Sony Bravia 55 inch 4K OLED Google TV XR-55A80L",
        category="television",
    )
    assert tv["screen_size_inch"] == 55.0
    assert tv["panel_type"] == "oled"
    assert tv["smart_platform"] == "google_tv"

    fridge = extract_category_specs(
        "Samsung 253L Frost Free Double Door 3 Star Refrigerator RT28T3122S8",
        category="refrigerator",
    )
    assert fridge["capacity_l"] == 253.0
    assert fridge["door_type"] == "double_door"
    assert fridge["frost_type"] == "frost_free"

    washer = extract_category_specs(
        "LG 8 kg Front Load Fully Automatic Washing Machine with Inverter 1400 rpm",
        category="washing_machine",
    )
    assert washer["capacity_kg"] == 8.0
    assert washer["load_type"] == "front_load"
    assert washer["automation_type"] == "fully_automatic"
    assert washer["rpm"] == 1400


def test_category_price_bounds_not_laptop_shaped() -> None:
    assert price_bounds_for("tws")[0] <= 500
    assert price_bounds_for("headphones")[1] >= 100_000
    assert price_bounds_for("television")[1] >= 500_000
    assert price_bounds_for("camera")[1] >= 500_000
    assert price_bounds_for("refrigerator")[0] <= 10_000

    cheap_buds = evaluate_listing(
        {
            "platform": "amazon",
            "title": "boAt Airdopes 141 TWS Earbuds",
            "url": "https://www.amazon.in/dp/B0BUDS141X",
            "category": "tws",
            "category_confidence": "high",
            "price": 999,
            "image": "https://m.media-amazon.com/images/I/buds.jpg",
        }
    )
    assert cheap_buds.decision in {"accepted", "degraded"}
    assert cheap_buds.price_usable is True

    premium_tv = evaluate_listing(
        {
            "platform": "croma",
            "title": "Sony Bravia 65 inch OLED Google TV",
            "url": "https://www.croma.com/p/1234567",
            "category": "television",
            "category_confidence": "high",
            "price": 249990,
            "image": "https://www.croma.com/images/tv.jpg",
        }
    )
    assert premium_tv.decision in {"accepted", "degraded"}
    assert premium_tv.price_usable is True


def test_placeholder_image_rejected_softly() -> None:
    decision = evaluate_listing(
        {
            "platform": "flipkart",
            "title": "JBL Tune 760NC Wireless Over Ear Headphones",
            "url": "https://www.flipkart.com/x/p/itm123?pid=ACCF123",
            "category": "headphones",
            "category_confidence": "high",
            "price": 5999,
            "image": "https://cdn.example.com/wishlist-icon.png",
        }
    )
    assert "placeholder_image" in decision.reasons
    assert decision.decision in {"accepted", "degraded"}


def test_idempotent_listing_id_native_and_tracking_url() -> None:
    native = "B0ABCDE123"
    clean = listing_id("amazon", native, "https://www.amazon.in/dp/B0ABCDE123", "Phone")
    tracking = listing_id(
        "amazon",
        native,
        "https://www.amazon.in/dp/B0ABCDE123?tag=mayabu-21&ref=xyz",
        "Phone",
    )
    assert clean == tracking == "amazon:B0ABCDE123"
    # Same canonical URL without native still stable after normalize.
    u1 = normalize_url("https://www.amazon.in/dp/B0ABCDE123?tag=x")
    u2 = normalize_url("https://www.amazon.in/dp/B0ABCDE123")
    assert u1 == u2 or listing_id("amazon", None, u1 or "", "") == listing_id(
        "amazon", None, u2 or "", ""
    )


def test_match_confidence_states_clear() -> None:
    listing = {
        "title": "Samsung Galaxy S24 8GB 256GB SM-S921B",
        "category": "smartphone",
        "specs": extract_category_specs(
            "Samsung Galaxy S24 8GB 256GB SM-S921B", category="smartphone"
        ),
    }
    exact_product = {
        "canonical_title": "Samsung Galaxy S24 SM-S921B 256GB (8GB RAM)",
        "category": "smartphone",
        "specs": extract_category_specs(
            "Samsung Galaxy S24 SM-S921B 256GB (8GB RAM)", category="smartphone"
        ),
    }
    conflict_product = {
        "canonical_title": "Samsung Galaxy S24 8GB 128GB SM-S921B",
        "category": "smartphone",
        "specs": extract_category_specs(
            "Samsung Galaxy S24 8GB 128GB SM-S921B", category="smartphone"
        ),
    }
    exact = assess_product_match(listing, exact_product)
    assert exact.merge_allowed is True
    assert exact.relation == "exact"

    blocked = assess_product_match(listing, conflict_product)
    assert blocked.merge_allowed is False
    assert blocked.relation in {"variant", "conflict"}


def test_variant_key_category_aware() -> None:
    phone_specs = extract_category_specs(
        "Samsung Galaxy S24 8GB 256GB SM-S921B", category="smartphone"
    )
    key = build_variant_key(phone_specs)
    assert key is not None
    assert "smartphone" in key
    assert "ram_gb" in key or "256" in key

    laptop_specs = {
        "category": "laptop",
        "brand": "asus",
        "model_codes": ["X1407CA"],
        "cpu_series": "core_ultra_5",
        "cpu_models": ["225h"],
        "ram_gb": 16,
        "storage_gb": 512,
    }
    assert build_variant_key(laptop_specs) is not None


def test_normalize_multi_category_preserves_raw_evidence() -> None:
    listing = normalize_raw_listing(
        {
            "title": "LG 260L Double Door Refrigerator GL-S292RDSX",
            "link": "https://www.croma.com/p/9876543",
            "currentPrice": "28990",
            "image": "https://www.croma.com/images/fridge.jpg",
            "native_id": "9876543",
        },
        platform_hint="croma",
        query="lg refrigerator",
    )
    assert listing is not None
    assert listing["category"] == "refrigerator"
    assert listing["raw"]["title"].startswith("LG")
    assert listing["native_id"] == "9876543"
    assert listing["specs"]["capacity_l"] == 260.0


def test_platform_category_health_distinguishes_pairs() -> None:
    laptop = score_platform_category_health(
        platform="amazon",
        category="laptop",
        discovered=12,
        accepted=10,
        degraded=1,
        rejected=1,
        valid_price_rate=0.9,
        category_confidence_rate=0.85,
        duplicate_rate=0.05,
    )
    fridge_weak = score_platform_category_health(
        platform="amazon",
        category="refrigerator",
        discovered=2,
        accepted=1,
        degraded=1,
        rejected=0,
        valid_price_rate=0.5,
        category_confidence_rate=0.5,
        duplicate_rate=0.0,
    )
    assert laptop.status == "healthy"
    assert fridge_weak.status in {"partial", "degraded"}
    assert laptop.status != fridge_weak.status


def test_coverage_thresholds_require_more_than_one_hit() -> None:
    assert (
        meets_coverage_thresholds(
            discovered=1,
            accepted=1,
            valid_price_rate=1.0,
            category_confidence_rate=1.0,
            duplicate_rate=0.0,
        )
        is False
    )


def test_search_index_readiness_documents_blockers() -> None:
    report = search_index_readiness_report()
    assert report["can_store_non_laptop_documents"] is True
    assert report["public_search_exposes_non_laptop"] is True
    assert "smartphone" in report["public_categories"]


def test_offer_attachment_concept_via_matching() -> None:
    """Same exact variant from two platforms should merge; different URL is irrelevant."""
    amazon_listing = {
        "title": "Sony WH-1000XM5 Wireless Over-ear Headphones",
        "category": "headphones",
        "specs": extract_category_specs(
            "Sony WH-1000XM5 Wireless Over-ear Headphones", category="headphones"
        ),
    }
    croma_product = {
        "canonical_title": "Sony WH-1000XM5 Over Ear Wireless Headphones with ANC",
        "category": "headphones",
        "specs": extract_category_specs(
            "Sony WH-1000XM5 Over Ear Wireless Headphones with ANC",
            category="headphones",
        ),
    }
    assessment = assess_product_match(amazon_listing, croma_product)
    assert assessment.merge_allowed is True
    assert assessment.relation == "exact"
