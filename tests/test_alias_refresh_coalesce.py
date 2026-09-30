"""Same-retailer alias listings should not independently refresh."""

from __future__ import annotations

from mayabu.search.public_offers import select_public_offers, unique_platform_count


def test_alias_group_collapses_to_one_public_offer() -> None:
    rows = [
        {
            "id": "primary",
            "platform": "flipkart",
            "native_id": "FKCORE5",
            "listing_url": "https://www.flipkart.com/acer-alg/p/itmcore5",
            "title": "Acer ALG Core5-210H",
            "current_price": 55_000,
            "stock_status": "in_stock",
            "match_status": "matched",
            "match_confidence": 0.95,
            "last_verified_at": "2026-09-20T10:00:00+00:00",
            "match_evidence": {"listing_role": "primary"},
        },
        {
            "id": "alias",
            "platform": "flipkart",
            "native_id": "FKCORE5",
            "listing_url": "https://www.flipkart.com/acer-alg/p/itmcore5?pid=alias",
            "title": "Acer ALG Core5-210H",
            "current_price": 55_100,
            "stock_status": "in_stock",
            "match_status": "matched",
            "match_confidence": 0.9,
            "last_verified_at": "2026-09-19T10:00:00+00:00",
            "match_evidence": {
                "listing_role": "alias",
                "primary_listing_id": "primary",
            },
        },
    ]
    selected = select_public_offers(rows, category="laptop")
    assert len(selected) == 1
    assert selected[0]["id"] == "primary"
    assert unique_platform_count(selected, category="laptop") == 1
