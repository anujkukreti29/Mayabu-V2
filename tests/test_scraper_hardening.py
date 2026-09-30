"""Correctness / data-quality hardening regressions."""

from __future__ import annotations

from pathlib import Path

from mayabu.domain.categories.registry import (
    detect_category_result,
    extract_category_specs,
    extract_generic_specs,
)
from mayabu.domain.product_identity import build_identity, classify_relation
from mayabu.scrapers.retail_parse import (
    extract_jsonld_products,
    html_looks_blocked,
    jsonld_to_raw_record,
)
from mayabu_common import extract_specs, normalize_raw_listing
from mayabu_db.quality import (
    REASON_CATEGORY_UNKNOWN,
    REASON_SUSPICIOUS_PRICE,
    evaluate_listing,
)
from mayabu_scraper_base import discovery_health_report

FIXTURES = Path(__file__).parent / "fixtures" / "retail"


def test_unknown_does_not_become_laptop() -> None:
    specs = extract_specs("Generic Retail Widget Model XYZ-99", "unknown")
    assert specs.get("category") == "unknown"
    assert "ram_gb" not in specs or specs.get("ram_gb") is None
    assert "cpu_series" not in specs or specs.get("cpu_series") is None
    # Generic path may still capture model-like tokens, never laptop CPU families.
    generic = extract_generic_specs("Something with 16GB RAM and Core i7")
    assert generic["category"] == "unknown"
    assert "cpu_series" not in generic


def test_accessories_are_not_parent_categories() -> None:
    cases = [
        ("TV stand wooden unit", "accessory"),
        ("washing machine stand trolley", "accessory"),
        ("phone case for iPhone 15", "accessory"),
        ("Laptop bag for MacBook", "accessory"),
        ("camera lens 50mm", "accessory"),
        ("earbud case charging", "accessory"),
        ("screen protector tempered glass", "accessory"),
        ("refrigerator cover waterproof", "accessory"),
    ]
    for title, expected in cases:
        result = detect_category_result(title=title)
        assert result.category == expected, title


def test_tv_stand_not_laptop_or_television_product() -> None:
    result = detect_category_result(title="TV stand for living room")
    assert result.category == "accessory"
    listing = normalize_raw_listing(
        {"title": "TV stand for living room", "link": "https://www.amazon.in/dp/B0TVSTAND1", "currentPrice": "1999"},
        platform_hint="amazon",
        query="tv",
    )
    assert listing is None


def test_category_confidence_structured_beats_title() -> None:
    result = detect_category_result(
        title="Bundle pack accessories",
        structured_category="smartphone",
        breadcrumbs="Electronics > Mobiles",
    )
    assert result.category == "smartphone"
    assert result.confidence in {"high", "medium"}


def test_quality_gate_rejects_suspicious_laptop_emi_price() -> None:
    decision = evaluate_listing(
        {
            "platform": "amazon",
            "title": "ASUS Vivobook 16GB 512GB Laptop",
            "url": "https://www.amazon.in/dp/B0ABCDE123",
            "category": "laptop",
            "category_confidence": "high",
            "price": 499,
            "image": "https://www.amazon.in/img.jpg",
        },
        price_context="EMI from ₹499 per month",
    )
    assert decision.decision == "rejected"
    assert REASON_SUSPICIOUS_PRICE in decision.reasons or "emi_or_fee_context" in decision.reasons


def test_quality_gate_degrades_unknown_category() -> None:
    decision = evaluate_listing(
        {
            "platform": "croma",
            "title": "Mystery Gadget 2000",
            "url": "https://www.croma.com/p/123456",
            "category": "unknown",
            "category_confidence": "unknown",
            "price": 12999,
            "image": "https://www.croma.com/img.jpg",
        }
    )
    assert decision.decision == "degraded"
    assert REASON_CATEGORY_UNKNOWN in decision.reasons
    assert decision.record_usable is True


def test_health_status_blocked_vs_empty() -> None:
    blocked = discovery_health_report([], scrape_status="blocked")
    assert blocked["status"] == "blocked"
    empty = discovery_health_report([], scrape_status="empty")
    assert empty["status"] == "empty"
    failed = discovery_health_report([], scrape_status="failed")
    assert failed["status"] == "failed"


def test_vijaysales_fixture_jsonld_itemlist() -> None:
    html = (FIXTURES / "vijaysales_listing.html").read_text(encoding="utf-8")
    products = extract_jsonld_products(html)
    assert len(products) >= 2
    first = jsonld_to_raw_record(products[0], base_url="https://www.vijaysales.com")
    titles = [jsonld_to_raw_record(p, base_url="https://www.vijaysales.com")["title"] for p in products]
    assert first is not None
    assert any("HP" in t for t in titles)
    assert any("10020030" in (jsonld_to_raw_record(p, base_url="https://www.vijaysales.com") or {}).get("link", "") for p in products)


def test_poorvika_fixture_has_product_paths() -> None:
    html = (FIXTURES / "poorvika_listing.html").read_text(encoding="utf-8")
    assert html.count("/p") >= 2
    assert "selling-price" in html


def test_jiomart_shell_has_no_products() -> None:
    html = (FIXTURES / "jiomart_empty_shell.html").read_text(encoding="utf-8")
    assert extract_jsonld_products(html) == []
    assert not html_looks_blocked(html)


def test_bajaj_blocked_fixture() -> None:
    html = (FIXTURES / "bajaj_blocked_challenge.html").read_text(encoding="utf-8")
    assert html_looks_blocked(html, title="Attention Required")


def test_unknown_matching_is_conservative() -> None:
    a = build_identity("Mystery Device Alpha", category="unknown")
    b = build_identity("Mystery Device Beta", category="unknown")
    # Must not claim exact via laptop rules.
    assert classify_relation(a, b) in {"related", "conflict", "variant"}
    assert a.exact_fingerprint != b.exact_fingerprint or a.model_codes or b.model_codes


def test_smartphone_storage_conflict_still_holds() -> None:
    a = build_identity("Samsung Galaxy S24 8GB 128GB SM-S921B", category="smartphone")
    b = build_identity("Samsung Galaxy S24 8GB 256GB SM-S921B", category="smartphone")
    assert a.exact_fingerprint != b.exact_fingerprint
    assert classify_relation(a, b) in {"variant", "conflict"}
