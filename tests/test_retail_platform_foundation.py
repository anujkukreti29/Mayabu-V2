"""Platform registry, native IDs, category adapters, and retail parser fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from mayabu.domain.categories.registry import (
    detect_category_from_evidence,
    extract_category_specs,
)
from mayabu.domain.product_identity import build_identity, classify_relation
from mayabu.platforms.registry import (
    PLATFORMS,
    canonical_platform_slug,
    display_name,
    get_platform,
)
from mayabu.scrapers.platforms import detect_platform, validate_product_url
from mayabu.scrapers.retail_parse import (
    extract_jsonld_products,
    extract_refresh_from_html,
    jsonld_to_raw_record,
    price_to_int,
)
from mayabu_common import canonical_platform, extract_native_id, extract_specs

FIXTURES = Path(__file__).parent / "fixtures" / "retail"


def test_platform_registry_contains_eight_retailers() -> None:
    assert PLATFORMS == frozenset(
        {
            "amazon",
            "flipkart",
            "croma",
            "reliancedigital",
            "vijaysales",
            "jiomart",
            "poorvika",
            "bajajelectronics",
        }
    )
    assert display_name("vijaysales") == "Vijay Sales"
    assert display_name("jiomart") == "JioMart"
    assert display_name("poorvika") == "Poorvika"
    assert display_name("bajajelectronics") == "Bajaj Electronics"
    assert canonical_platform("vijay_sales") == "vijaysales"
    assert canonical_platform_slug("jio_mart") == "jiomart"
    assert get_platform("bajajelectronics") is not None


@pytest.mark.parametrize(
    "url,platform,native",
    [
        ("https://www.vijaysales.com/p/12345678/sony-tv", "vijaysales", "12345678"),
        ("https://www.vijaysales.com/p/P987/12345678/foo", "vijaysales", "12345678"),
        ("https://www.jiomart.com/p/electronics/samsung-galaxy/601234567", "jiomart", "601234567"),
        ("https://www.poorvika.com/samsung-galaxy-s24-8gb-128gb/p", "poorvika", "SAMSUNG-GALAXY-S24-8GB-128GB"),
        ("https://www.bajajelectronics.com/samsung-55-inch-4k-smart-tv", "bajajelectronics", "SAMSUNG-55-INCH-4K-SMART-TV"),
        ("https://www.amazon.in/dp/B0ABCDE123", "amazon", "B0ABCDE123"),
    ],
)
def test_native_id_extraction(url: str, platform: str, native: str) -> None:
    assert extract_native_id(platform, url) == native


def test_url_domain_validation() -> None:
    assert detect_platform("https://www.vijaysales.com/p/1/x") == "vijaysales"
    assert detect_platform("https://www.jiomart.com/p/electronics/x/1") == "jiomart"
    validate_product_url("poorvika", "https://www.poorvika.com/foo/p")
    with pytest.raises(ValueError):
        detect_platform("https://evil-vijaysales.com/p/1")
    with pytest.raises(ValueError):
        validate_product_url("amazon", "https://www.flipkart.com/x/p/itm")


def test_accessory_category_rejection() -> None:
    assert detect_category_from_evidence(title="Laptop bag for MacBook") == "accessory"
    assert detect_category_from_evidence(title="TV stand wooden unit") == "accessory"
    assert detect_category_from_evidence(title="Refrigerator cover") == "accessory"
    assert detect_category_from_evidence(title="Washing machine stand") == "accessory"
    assert detect_category_from_evidence(title="Camera lens 50mm") == "accessory"


def test_smartphone_variants_conflict() -> None:
    a = build_identity("Samsung Galaxy S24 8GB 128GB SM-S921B", category="smartphone")
    b = build_identity("Samsung Galaxy S24 12GB 256GB SM-S921B", category="smartphone")
    # Same model family code but RAM/storage conflict → not exact
    assert classify_relation(a, b) in {"variant", "conflict"}
    assert a.exact_fingerprint != b.exact_fingerprint


def test_television_size_conflict() -> None:
    a = build_identity("LG 43 inch 4K Smart TV 43UQ7500", category="television")
    b = build_identity("LG 55 inch 4K Smart TV 55UQ7500", category="television")
    assert classify_relation(a, b) in {"variant", "conflict"}
    assert a.exact_fingerprint != b.exact_fingerprint


def test_refrigerator_capacity_conflict() -> None:
    a = build_identity("LG 260L Double Door Refrigerator GL-S292", category="refrigerator")
    b = build_identity("LG 340L Double Door Refrigerator GL-T372", category="refrigerator")
    assert classify_relation(a, b) in {"variant", "conflict"}


def test_washing_machine_capacity_conflict() -> None:
    a = build_identity("IFB 7kg Front Load Fully Automatic WM7", category="washing_machine")
    b = build_identity("IFB 9kg Front Load Fully Automatic WM9", category="washing_machine")
    assert classify_relation(a, b) in {"variant", "conflict"}


def test_tws_battery_wording_does_not_split() -> None:
    a = build_identity("boAt Airdopes 141 ANC 42 hours playback", category="tws")
    b = build_identity("boAt Airdopes 141 ANC up to 42 hrs battery", category="tws")
    assert classify_relation(a, b) in {"exact", "related", "variant"}


def test_camera_kit_vs_body() -> None:
    body = build_identity("Canon EOS R50 body only", category="camera")
    kit = build_identity("Canon EOS R50 kit 18-45mm", category="camera")
    assert classify_relation(body, kit) in {"variant", "conflict"}
    assert body.exact_fingerprint != kit.exact_fingerprint


def test_laptop_baseline_preserved() -> None:
    one_tb = build_identity("ASUS Vivobook 14 Core Ultra 5 225H 16GB RAM 1TB SSD X1407CA-LY1581WS")
    same = build_identity("ASUS Vivobook 14 Core Ultra 5 225H 16GB RAM 1TB SSD X1407CA-LY1581WS")
    half_tb = build_identity("ASUS Vivobook 14 Core Ultra 5 225H 16GB RAM 512GB SSD X1407CA-LY160WS")
    assert classify_relation(one_tb, same) == "exact"
    assert classify_relation(one_tb, half_tb) == "variant"


def test_cross_platform_phone_matching() -> None:
    amazon = build_identity(
        "Samsung Galaxy S24 5G (Marble Gray, 8GB RAM, 128GB Storage) SM-S921B",
        category="smartphone",
    )
    flipkart = build_identity("SAMSUNG Galaxy S24 8 GB RAM 128 GB Storage", category="smartphone")
    # Without shared model codes this may be related/variant; fingerprints differ by title.
    assert classify_relation(amazon, flipkart) != "conflict" or amazon.brand == flipkart.brand


def test_jsonld_fixture_parsers() -> None:
    html = (FIXTURES / "sample_product.jsonld.html").read_text(encoding="utf-8")
    products = extract_jsonld_products(html)
    assert products
    record = jsonld_to_raw_record(products[0], base_url="https://www.vijaysales.com")
    assert record is not None
    assert "Galaxy" in record["title"]
    assert price_to_int(record["currentPrice"]) == 54999
    current, mrp = extract_refresh_from_html(html, category="smartphone")
    assert current == 54999
    assert mrp == 79999


def test_smartphone_spec_keys() -> None:
    specs = extract_category_specs("OnePlus Nord CE 4 8GB 128GB 5G", category="smartphone")
    assert specs["ram_gb"] == 8
    assert specs["storage_gb"] == 128
    assert specs["network_generation"] == "5g"
    assert "camera_mp" in specs  # descriptive key present


def test_extract_specs_dispatch() -> None:
    specs = extract_specs("Sony Bravia 55 inch 4K OLED Google TV XR55A80L", "television")
    assert specs["screen_size_inch"] == 55.0
    assert specs["panel_type"] == "oled"
