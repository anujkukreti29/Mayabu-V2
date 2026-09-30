"""Unit tests for public one-offer-per-retailer selection."""

from __future__ import annotations

from mayabu.search.public_offers import select_public_offers, unique_platform_count
from mayabu.search.public_price import compute_public_best_price


def _listing(**kwargs):
    base = {
        "id": "x",
        "platform": "croma",
        "match_status": "matched",
        "current_price": 100000,
        "currency": "INR",
        "stock_status": "in_stock",
        "title": "Phone",
    }
    base.update(kwargs)
    return base


def test_select_public_offers_collapses_same_retailer_duplicates():
    listings = [
        _listing(id="c1", platform="croma", title="iPhone Black", current_price=204900),
        _listing(id="c2", platform="croma", title="iPhone Silver", current_price=204900),
        _listing(id="c3", platform="croma", title="iPhone Burgundy", current_price=204900),
        _listing(id="c4", platform="croma", title="iPhone Glacier", current_price=204900),
        _listing(id="f1", platform="flipkart", title="iPhone Glacier", current_price=204900),
        _listing(id="f2", platform="flipkart", title="iPhone Black", current_price=204900),
        _listing(id="r1", platform="reliancedigital", title="iPhone Burgundy", current_price=204900),
        _listing(id="v1", platform="vijaysales", title="iPhone Burgundy", current_price=205000),
    ]
    selected = select_public_offers(
        listings,
        category="smartphone",
        product_title="Apple iPhone 18 Pro Max 512 GB, Burgundy",
        product_specs={"color": "burgundy", "storage_gb": 512},
    )
    platforms = [row["platform"] for row in selected]
    assert platforms == sorted(set(platforms))
    assert len(selected) == 4
    croma = next(row for row in selected if row["platform"] == "croma")
    assert "Burgundy" in croma["title"]


def test_platform_count_ignores_duplicate_retailer_rows():
    listings = [
        _listing(id="c1", platform="croma"),
        _listing(id="c2", platform="croma"),
        _listing(id="f1", platform="flipkart"),
        _listing(id="f2", platform="flipkart"),
        _listing(id="r1", platform="reliancedigital"),
        _listing(id="v1", platform="vijaysales"),
    ]
    assert unique_platform_count(listings, "smartphone") == 4
    best = compute_public_best_price(listings, "smartphone")
    assert best.platform_count == 4


def test_best_price_not_inflated_by_duplicate_same_retailer():
    listings = [
        _listing(id="c1", platform="croma", current_price=90000),
        _listing(id="c2", platform="croma", current_price=90000),
        _listing(id="c3", platform="croma", current_price=90000),
        _listing(id="f1", platform="flipkart", current_price=91000),
    ]
    best = compute_public_best_price(listings, "smartphone")
    assert best.best_price is not None
    assert int(best.best_price) == 90000
    assert best.best_platform == "croma"
    assert best.platform_count == 2


def test_smartphone_color_hard_conflict():
    from mayabu.domain.categories.smartphone import SmartphoneAdapter

    adapter = SmartphoneAdapter()
    conflicts = adapter.hard_conflicts(
        {"storage_gb": 512, "color": "burgundy"},
        {"storage_gb": 512, "color": "black"},
    )
    assert "color" in conflicts
