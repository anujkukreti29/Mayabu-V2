"""Data reliability V1 — discovery plans, anomaly, browser pool, watch priority."""

from __future__ import annotations

from dataclasses import replace

from mayabu_refresh.models import RefreshResult


def test_ensure_discovery_plans_idempotent(monkeypatch) -> None:
    from mayabu_db import scheduler

    calls = {"n": 0}
    monkeypatch.setattr(
        scheduler,
        "create_multi_category_plans",
        lambda *a, **k: calls.__setitem__("n", calls["n"] + 1) or 5,
    )

    # Simulate existing plans so ensure does not seed.
    class _Cur:
        def execute(self, *a, **k):  # noqa: ANN001, ARG002
            return None

        def fetchone(self):
            return {"n": 3}

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):  # noqa: ANN001
            return False

        def cursor(self):
            return _Ctx()

    class _Ctx:
        def __enter__(self):
            return _Cur()

        def __exit__(self, *a):  # noqa: ANN001
            return False

    monkeypatch.setattr(scheduler, "db_connection", lambda: _Conn())
    result = scheduler.ensure_production_discovery_plans()
    assert result["existing"] == 3
    assert result["upserted"] == 0
    assert calls["n"] == 0


def test_category_discovery_priority_prefers_weak_verticals() -> None:
    from mayabu_db.scheduler import _CATEGORY_DISCOVERY_PRIORITY

    assert _CATEGORY_DISCOVERY_PRIORITY["camera"] < _CATEGORY_DISCOVERY_PRIORITY["laptop"]
    assert _CATEGORY_DISCOVERY_PRIORITY["headphones"] < _CATEGORY_DISCOVERY_PRIORITY["smartphone"]


def test_near_tracked_low_requires_pi_depth() -> None:
    from mayabu.search import homepage_discovery as hd

    assert hd.NEAR_LOW_MIN_OBS >= 7
    assert hd.NEAR_LOW_MIN_DAYS >= 14


def test_suspicious_spike_is_fatal() -> None:
    from mayabu_db.refresh_ingestion import validate_refresh_result

    listing = {
        "platform": "amazon",
        "listing_url": "https://www.amazon.in/dp/B0TEST",
        "category": "laptop",
        "current_price": 50_000,
    }
    result = RefreshResult(
        current_price=180_000,
        mrp=180_000,
        page_status="success",
        stock_status="in_stock",
    )
    ok, flags = validate_refresh_result(listing, result)
    codes = {f["code"] for f in flags}
    assert "suspicious_price_spike" in codes
    assert ok is False


def test_absurd_low_still_fatal() -> None:
    from mayabu_db.refresh_ingestion import validate_refresh_result

    listing = {
        "platform": "amazon",
        "listing_url": "https://www.amazon.in/dp/B0TEST",
        "category": "laptop",
        "current_price": 70_000,
    }
    result = RefreshResult(
        current_price=499,
        mrp=70_000,
        page_status="success",
        stock_status="in_stock",
    )
    ok, flags = validate_refresh_result(listing, result)
    assert ok is False
    assert any(f["code"] in {"price_too_low", "suspicious_price_drop"} for f in flags)


def test_browser_pool_module_exports() -> None:
    from mayabu_refresh.browser_pool import (
        get_refresh_browser_pool,
        wait_for_price_or_stock,
    )

    pool = get_refresh_browser_pool()
    assert pool.stats["browser_alive"] in {0, 1}
    assert callable(wait_for_price_or_stock)


def test_refresh_policy_source_has_watch_intent() -> None:
    import inspect

    from mayabu.scheduler import refresh_policy

    source = inspect.getsource(refresh_policy)
    assert "watch_intent_count" in source
    assert "notify_on_drop" in source


def test_new_tracked_low_event_constant() -> None:
    from mayabu.domain.watch_events import EVENT_NEW_TRACKED_LOW, evaluate_watches
    import inspect

    assert EVENT_NEW_TRACKED_LOW == "new_tracked_low"
    assert "new_tracked_low" in inspect.getsource(evaluate_watches)


def test_amazon_refresh_uses_browser_pool() -> None:
    import inspect

    from mayabu_refresh import amazon

    source = inspect.getsource(amazon.scrape_amazon_refresh)
    assert "get_refresh_browser_pool" in source
    assert "wait_for_price_or_stock" in source
    assert "async_playwright" not in source


def test_scheduler_tick_ensures_plans() -> None:
    import inspect

    from mayabu.scheduler import engine

    source = inspect.getsource(engine.tick)
    assert "ensure_production_discovery_plans" in source
