from __future__ import annotations

from mayabu.search import ranker
from mayabu_refresh.common import classify_visible_prices


def _price_candidate(
    text: str,
    price_text: str,
    *,
    y: int,
    struck: bool = False,
    context: str = "",
    font_size: int = 26,
) -> dict[str, object]:
    return {
        "text": text,
        "price_text": price_text,
        "context": context or text,
        "font_size": font_size,
        "font_weight": "700",
        "text_decoration": "line-through" if struck else "none",
        "y": y,
        "width": 150,
        "height": 36,
    }


def test_visible_price_classifier_prefers_main_price_and_nearby_struck_mrp() -> None:
    candidates = [
        _price_candidate("₹5,999 per month EMI", "₹5,999", y=240, font_size=30),
        _price_candidate("₹69,990", "₹69,990", y=300),
        _price_candidate("₹89,990", "₹89,990", y=305, struck=True),
    ]

    current, mrp, discount = classify_visible_prices(candidates)

    assert current == 69_990
    assert mrp == 89_990
    assert discount == 22.22


def test_visible_price_classifier_uses_discount_to_avoid_unrelated_high_mrp() -> None:
    candidates = [
        _price_candidate("₹69,990 22% off", "₹69,990", y=300),
        _price_candidate("₹89,689", "₹89,689", y=305, struck=True),
        _price_candidate("₹1,99,990", "₹1,99,990", y=900, struck=True),
    ]

    current, mrp, discount = classify_visible_prices(candidates, page_text="22% off")

    assert current == 69_990
    assert mrp == 89_689
    assert discount == 22.0


def test_rank_products_prepares_query_tokens_once_and_preserves_input(
    monkeypatch,
) -> None:
    rows = [
        {
            "product_id": "exact",
            "canonical_title": "ASUS Vivobook 14 Ultra 5 16GB 512GB",
            "exact_model_match": 1,
            "platform_count": 2,
            "match_group": "related_product",
        },
        {
            "product_id": "related",
            "canonical_title": "Lenovo IdeaPad 15 Ryzen 5 8GB 512GB",
            "platform_count": 1,
            "match_group": "related_product",
        },
    ]
    query = "asus vivobook ultra 5"
    token_calls: list[str] = []
    original_tokens = ranker._tokens

    def counted_tokens(text: str) -> tuple[str, ...]:
        token_calls.append(text)
        return original_tokens(text)

    monkeypatch.setattr(ranker, "_tokens", counted_tokens)
    ranked = ranker.rank_products(rows, {"_query": query, "brand": "asus"})

    assert ranked[0]["product_id"] == "exact"
    assert ranked[0]["match_group"] == "exact_match"
    assert "rank_score" not in rows[0]
    assert token_calls.count(query) == 1
