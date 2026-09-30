"""Multi-category public search + P0 family-only exact-match safety."""

from __future__ import annotations

import pytest

from mayabu.domain.product_identity import build_identity, classify_relation
from mayabu.search.category_registry import (
    public_search_categories,
    validate_public_category,
)
from mayabu.search.query_parser import extract_price_intent, parse_query
from mayabu.search.search_repository import parse_filters_param


def test_p0_phone_family_missing_storage_not_exact() -> None:
    complete = build_identity("Samsung Galaxy S24 8GB 128GB", category="smartphone")
    incomplete = build_identity("Samsung Galaxy S24", category="smartphone")
    assert classify_relation(complete, incomplete) != "exact"


def test_p0_tv_family_missing_size_not_exact() -> None:
    a = build_identity("Sony Bravia OLED Google TV", category="television")
    b = build_identity("Sony Bravia OLED", category="television")
    assert classify_relation(a, b) != "exact"


def test_p0_washer_missing_capacity_not_exact() -> None:
    a = build_identity("LG Front Load Fully Automatic Washing Machine", category="washing_machine")
    b = build_identity("LG 8kg Front Load Fully Automatic Washing Machine", category="washing_machine")
    assert classify_relation(a, b) != "exact"


def test_p0_shared_model_code_still_exact() -> None:
    a = build_identity("Samsung Galaxy S24 SM-S921B 8GB 256GB", category="smartphone")
    b = build_identity("Samsung Galaxy S24 SM-S921B smartphone", category="smartphone")
    assert classify_relation(a, b) == "exact"


def test_laptop_exact_matching_preserved() -> None:
    one = build_identity("ASUS Vivobook 14 Core Ultra 5 225H 16GB RAM 1TB SSD X1407CA-LY1581WS")
    same = build_identity("ASUS Vivobook 14 Core Ultra 5 225H 16GB RAM 1TB SSD X1407CA-LY1581WS")
    assert classify_relation(one, same) == "exact"


def test_public_categories_include_camera() -> None:
    cats = public_search_categories()
    assert "laptop" in cats
    assert "smartphone" in cats
    assert "camera" in cats
    info = validate_public_category("camera")
    assert info.display_name == "Cameras"
    with pytest.raises(ValueError):
        validate_public_category("not-a-real-category")


@pytest.mark.parametrize(
    "query,category,checks",
    [
        ("gaming laptop under 70000", "laptop", {"max_price": 70000}),
        ("Galaxy S24 256GB", "smartphone", {"storage_gb": 256}),
        ("phone under 30000", "smartphone", {"max_price": 30000}),
        ("55 inch OLED TV", "television", {"screen_size_inch": 55.0}),
        ("LG 260L refrigerator", "refrigerator", {"capacity_l": 260.0}),
        ("8kg front load washing machine", "washing_machine", {"capacity_kg": 8.0}),
        ("ANC earbuds under 5000", "tws", {"max_price": 5000}),
        ("WH-1000XM5", "headphones", {}),
    ],
)
def test_query_parser_category_intents(query: str, category: str, checks: dict) -> None:
    parsed = parse_query(query)
    assert parsed.is_relevant is True
    assert parsed.detected_category == category
    assert parsed.search_mode != "accessory"
    for key, expected in checks.items():
        if key == "max_price":
            assert parsed.max_price == expected
        elif key == "min_price":
            assert parsed.min_price == expected
        else:
            assert parsed.detected_specs.get(key) == expected


def test_price_not_confused_with_specs() -> None:
    assert extract_price_intent("rtx 4060 gaming laptop") == (None, None)
    assert extract_price_intent("256GB storage phone") == (None, None)
    assert extract_price_intent("55 inch OLED TV") == (None, None)
    assert extract_price_intent("8kg front load") == (None, None)
    assert extract_price_intent("120Hz refresh rate TV") == (None, None)
    assert extract_price_intent("phone under 30k")[1] == 30000
    assert extract_price_intent("between 20000 and 40000") == (20000, 40000)


def test_explicit_category_overrides_inference() -> None:
    parsed = parse_query("samsung", explicit_category="television")
    assert parsed.detected_category == "television"
    assert parsed.explicit_category == "television"


def test_accessory_query_not_parent_category() -> None:
    parsed = parse_query("phone case for iphone")
    assert parsed.is_relevant is False
    assert parsed.detected_category == "accessory"


def test_no_laptop_fallback_for_unknown() -> None:
    parsed = parse_query("mystery gadget xyz")
    assert parsed.detected_category != "laptop"
    # Broad/cross or irrelevant — never forced laptop.
    assert parsed.search_mode in {"cross_category", "empty", "category"}


def test_brand_only_is_cross_category() -> None:
    parsed = parse_query("Samsung")
    assert parsed.is_relevant is True
    assert parsed.search_mode == "cross_category"
    assert parsed.detected_category is None


def test_filters_allowlist() -> None:
    ok = parse_filters_param('{"ram_gb": 8, "storage_gb": 256}', "smartphone")
    assert ok == {"ram_gb": 8, "storage_gb": 256}
    with pytest.raises(ValueError):
        parse_filters_param('{"camera_mp": 108}', "smartphone")
    with pytest.raises(ValueError):
        parse_filters_param('{"ram_gb": 8}', None)


def test_api_price_overrides_inferred() -> None:
    parsed = parse_query("phone under 30000", min_price=10000, max_price=25000)
    assert parsed.min_price == 10000
    assert parsed.max_price == 25000


def test_multi_value_filter_sql_or_within_facet() -> None:
    from mayabu.search.search_repository import _specs_filter_sql

    sql, params = _specs_filter_sql({"storage_gb": [128, 256], "brand": ["samsung", "lg"]})
    assert "in (" in sql
    assert params == [128.0, 256.0, "samsung", "lg"]


def test_fair_cross_category_interleave() -> None:
    from mayabu.search.search_repository import _fair_cross_category_page

    ranked = []
    for i in range(8):
        ranked.append({"product_id": f"tws-{i}", "category": "tws", "rank_score": 100 - i})
    for i in range(3):
        ranked.append({"product_id": f"phone-{i}", "category": "smartphone", "rank_score": 90 - i})
    for i in range(2):
        ranked.append({"product_id": f"tv-{i}", "category": "television", "rank_score": 80 - i})
    page = _fair_cross_category_page(ranked, limit=6, offset=0)
    cats = [r["category"] for r in page]
    assert cats.count("tws") <= 2  # not 6 tws dominating
    assert "smartphone" in cats
    assert "television" in cats
    # Within category, higher rank first
    tws_ids = [r["product_id"] for r in page if r["category"] == "tws"]
    assert tws_ids == sorted(tws_ids, key=lambda x: int(x.split("-")[1]))
