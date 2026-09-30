from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from mayabu.search.public_price import compute_public_best_price, listing_is_public_priced
from mayabu_db.repository import invalidate_price_caches


def _listing(
    platform: str,
    price: float | None,
    *,
    stock: str = "in_stock",
    category: str = "laptop",
    match_status: str = "matched",
    currency: str = "INR",
) -> dict:
    return {
        "platform": platform,
        "current_price": price,
        "stock_status": stock,
        "category": category,
        "match_status": match_status,
        "currency": currency,
    }


def test_one_eligible_priced_offer_sets_best_price() -> None:
    result = compute_public_best_price([_listing("amazon", 54990)], "laptop")
    assert result.best_price == Decimal("54990")
    assert result.best_platform == "amazon"
    assert result.platform_count == 1
    assert result.used_out_of_stock_fallback is False


def test_multiple_priced_offers_use_minimum() -> None:
    result = compute_public_best_price(
        [_listing("croma", 56990), _listing("amazon", 54990), _listing("flipkart", 55990)],
        "laptop",
    )
    assert result.best_price == Decimal("54990")
    assert result.best_platform == "amazon"


def test_experimental_offer_only_is_excluded() -> None:
    result = compute_public_best_price([_listing("vijaysales", 1999, category="tws")], "tws")
    assert result.best_price is None
    assert result.platform_count == 0
    assert listing_is_public_priced(_listing("vijaysales", 1999, category="tws"), "tws") is False


def test_disabled_or_blocked_retailer_is_excluded() -> None:
    disabled = compute_public_best_price([_listing("jiomart", 49990)], "laptop")
    blocked = compute_public_best_price(
        [_listing("bajajelectronics", 49990)],
        "laptop",
    )
    assert disabled.best_price is None
    assert blocked.best_price is None


def test_valid_public_plus_invalid_offer_keeps_valid_price() -> None:
    result = compute_public_best_price(
        [
            _listing("amazon", 54990),
            _listing("flipkart", 0),
            _listing("croma", -10),
            _listing("reliancedigital", None),
            _listing("jiomart", 1),
        ],
        "laptop",
    )
    assert result.best_price == Decimal("54990")
    assert result.best_platform == "amazon"
    assert result.platform_count == 1


def test_out_of_stock_null_refresh_preserves_prior_price_as_best() -> None:
    result = compute_public_best_price(
        [_listing("croma", 1999, stock="out_of_stock", category="tws")],
        "tws",
    )
    assert result.best_price == Decimal("1999")
    assert result.best_platform == "croma"
    assert result.used_out_of_stock_fallback is True


def test_in_stock_wins_over_cheaper_out_of_stock() -> None:
    result = compute_public_best_price(
        [
            _listing("amazon", 50000, stock="out_of_stock"),
            _listing("croma", 55000, stock="in_stock"),
        ],
        "laptop",
    )
    assert result.best_price == Decimal("55000")
    assert result.best_platform == "croma"
    assert result.used_out_of_stock_fallback is False


def test_unmatched_listing_cannot_become_public_best_price() -> None:
    result = compute_public_best_price(
        [
            _listing("amazon", 1000, match_status="unmatched"),
            _listing("flipkart", 1100, match_status="needs_review"),
            _listing("croma", 54990, match_status="matched"),
        ],
        "laptop",
    )
    assert result.best_price == Decimal("54990")
    assert result.best_platform == "croma"
    result = compute_public_best_price(
        [
            _listing("amazon", None),
            _listing("flipkart", 0),
            _listing("croma", 12990, match_status="candidate"),
        ],
        "laptop",
    )
    assert result.best_price is None
    assert result.best_platform is None
    assert result.platform_count == 0


def test_non_inr_currency_is_excluded() -> None:
    result = compute_public_best_price(
        [_listing("amazon", 54990, currency="USD")],
        "laptop",
    )
    assert result.best_price is None


def test_sql_view_falls_back_to_priced_out_of_stock() -> None:
    schema = Path("mayabu_db/schema.sql").read_text(encoding="utf-8")
    migration = Path(
        "mayabu_db/migrations/2026_09_20_public_best_price_oos_fallback.sql"
    ).read_text(encoding="utf-8")
    for source in (schema, migration):
        assert "mayabu_listing_is_public_priced" in source
        assert "used_out_of_stock_fallback" not in source
        assert "coalesce(" in source
        assert "stock_status <> 'out_of_stock'" in source


def test_verification_unchanged_does_not_invalidate_product_cache() -> None:
    calls: list[str] = []

    def fake_invalidate(product_id: str) -> int:
        calls.append(product_id)
        return 1

    import mayabu.search.cache as cache_mod

    original = cache_mod.get_cache

    class _Cache:
        def invalidate_product(self, product_id: str) -> int:
            return fake_invalidate(product_id)

    cache_mod.get_cache = lambda: _Cache()  # type: ignore[assignment]
    try:
        invalidate_price_caches("abc", event_type="unchanged")
        assert calls == []
        invalidate_price_caches("abc", event_type="price_changed")
        assert calls == ["abc"]
    finally:
        cache_mod.get_cache = original


def test_product_cache_contract_busts_stale_null_best_price() -> None:
    from mayabu.api.product_routes import PRODUCT_CACHE_CONTRACT, _key

    assert PRODUCT_CACHE_CONTRACT
    assert "bp-oos" in PRODUCT_CACHE_CONTRACT
    assert _key("product", "abc", PRODUCT_CACHE_CONTRACT) != _key("product", "abc")
