"""Data-quality cleanup: insufficient identity + audio accessory leakage + facets."""

from __future__ import annotations

from mayabu.domain.categories.registry import detect_category_result
from mayabu.domain.identity_quality import has_sufficient_product_identity
from mayabu.search.search_repository import _facet_is_useful, build_page_facets
from mayabu_db.quality import REASON_INSUFFICIENT_IDENTITY, evaluate_listing


def _listing(title: str, category: str, **extra) -> dict:
    base = {
        "platform": "croma",
        "title": title,
        "url": "https://www.croma.com/p/TEST123",
        "category": category,
        "category_confidence": "high",
        "price": 19999,
        "image": "https://www.croma.com/img.jpg",
    }
    base.update(extra)
    return base


def test_brand_only_titles_rejected() -> None:
    for title in ("Samsung", "Apple", "Sony", "LG", "HP", "Dell", "Lenovo", "OnePlus"):
        decision = evaluate_listing(_listing(title, "smartphone"))
        assert decision.decision == "rejected", title
        assert REASON_INSUFFICIENT_IDENTITY in decision.reasons


def test_brand_plus_generic_category_insufficient() -> None:
    for title, cat in (
        ("Samsung TV", "television"),
        ("Apple Laptop", "laptop"),
        ("OnePlus Phone", "smartphone"),
        ("Sony headphones", "headphones"),
    ):
        assert has_sufficient_product_identity(title, cat) is False
        decision = evaluate_listing(_listing(title, cat))
        assert decision.decision == "rejected"
        assert REASON_INSUFFICIENT_IDENTITY in decision.reasons


def test_real_short_models_accepted() -> None:
    for title, cat in (
        ("iPhone 16", "smartphone"),
        ("Galaxy S24", "smartphone"),
        ("LG OLED55C4", "television"),
        ("WH-1000XM5", "headphones"),
    ):
        assert has_sufficient_product_identity(title, cat) is True
        decision = evaluate_listing(_listing(title, cat, price=49990))
        assert decision.decision in {"accepted", "degraded"}
        assert REASON_INSUFFICIENT_IDENTITY not in decision.reasons


def test_model_code_structured_evidence_rescues_short_title() -> None:
    decision = evaluate_listing(
        _listing(
            "Samsung",
            "smartphone",
            specs={"model_codes": ["SM-S921B"], "family": "galaxy_s24"},
        )
    )
    assert REASON_INSUFFICIENT_IDENTITY not in decision.reasons
    assert decision.decision in {"accepted", "degraded"}


def test_tws_replacement_case_rejected() -> None:
    result = detect_category_result(title="Replacement charging case for Galaxy Buds 2")
    assert result.category == "accessory"


def test_ear_tips_rejected() -> None:
    result = detect_category_result(title="Silicone ear tips for TWS earbuds")
    assert result.category == "accessory"


def test_real_earbuds_with_charging_case_wording_accepted() -> None:
    title = "Samsung Galaxy Buds 2 Pro Wireless Earbuds with charging case included"
    result = detect_category_result(title=title)
    assert result.category == "tws"
    assert has_sufficient_product_identity(title, "tws") is True
    decision = evaluate_listing(_listing(title, "tws", price=14990))
    assert decision.decision in {"accepted", "degraded"}
    assert REASON_INSUFFICIENT_IDENTITY not in decision.reasons


def test_headphone_cable_rejected() -> None:
    result = detect_category_result(title="Sony headphone cable replacement cord")
    assert result.category == "accessory"


def test_sparse_facet_omitted() -> None:
    rows = [
        {"brand": "sony", "category": "headphones", "specs": {}} for _ in range(10)
    ]
    rows[0]["specs"] = {"connectivity": "wireless"}
    facets = build_page_facets(rows, "headphones")
    assert "connectivity" not in facets
    assert "brand" in facets


def test_well_populated_facet_retained() -> None:
    rows = [
        {
            "brand": "sony",
            "category": "headphones",
            "specs": {"connectivity": "wireless", "form_factor": "over_ear"},
        }
        for _ in range(10)
    ]
    facets = build_page_facets(rows, "headphones")
    assert "connectivity" in facets
    assert "form_factor" in facets
    assert _facet_is_useful({"wireless": 10}, 10, key="connectivity") is True
