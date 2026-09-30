"""Controlled automation E2E with a fixture retailer — no live websites."""

from __future__ import annotations

from mayabu.domain.price_intelligence import build_price_intelligence
from mayabu.jobs.worker import _refresh_product_state


def test_intelligence_updates_from_new_observation() -> None:
    history = [
        {"date": "2026-07-01", "best_price": 60000, "platform_prices": {"amazon": 60000}},
        {"date": "2026-07-15", "best_price": 58000, "platform_prices": {"amazon": 58000}},
        {"date": "2026-08-01", "best_price": 54000, "platform_prices": {"amazon": 54000, "flipkart": 54990}},
    ]
    # pad tracking depth
    history = [
        {"date": f"2026-06-{day:02d}", "best_price": 61000, "platform_prices": {"amazon": 61000}}
        for day in range(1, 20)
    ] + history
    before = build_price_intelligence(
        product_id="fixture",
        product={"best_price": 58000, "best_platform": "amazon"},
        offers=[
            {"platform": "amazon", "current_price": 58000, "stock_status": "in_stock"},
            {"platform": "flipkart", "current_price": 58500, "stock_status": "in_stock"},
        ],
        history=history[:-1],
        min_observation_days=7,
        min_tracking_days=14,
        stale_hours=24,
    )
    after = build_price_intelligence(
        product_id="fixture",
        product={"best_price": 54000, "best_platform": "amazon"},
        offers=[
            {"platform": "amazon", "current_price": 54000, "stock_status": "in_stock"},
            {"platform": "flipkart", "current_price": 54990, "stock_status": "in_stock"},
        ],
        history=history,
        min_observation_days=7,
        min_tracking_days=14,
        stale_hours=24,
    )
    assert after.tracked_low <= before.tracked_low
    assert after.current_price == 54000
    assert after.timing.state in {"CONSIDER_NOW", "WATCH"}


def test_unchanged_refresh_skips_homepage_invalidation(monkeypatch) -> None:
    calls: list[str] = []

    class _Cache:
        def invalidate_product(self, product_id: str) -> int:
            calls.append(f"product:{product_id}")
            return 1

        def delete(self, key: str) -> int:
            calls.append(f"delete:{key}")
            return 1

    monkeypatch.setattr("mayabu.jobs.worker._CACHE", _Cache())
    monkeypatch.setattr("mayabu.jobs.worker.refresh_product_search_documents", lambda ids: None)
    _refresh_product_state("abc", material_change=False)
    assert calls == ["product:abc"]
    _refresh_product_state("abc", material_change=True)
    assert any(item.startswith("delete:") for item in calls)
