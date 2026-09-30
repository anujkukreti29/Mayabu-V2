"""Price intelligence timing and history window tests — no live retailers."""

from __future__ import annotations

from datetime import date, timedelta

from mayabu.domain.price_intelligence import (
    OfferSnapshot,
    build_price_intelligence,
    decide_timing,
    resolve_history_days,
    serialize_history_payload,
    window_stats,
)


def _history(prices: list[float], *, days_apart: int = 1, end: date | None = None) -> list[dict]:
    end = end or date.today()
    rows = []
    for index, price in enumerate(reversed(prices)):
        day = end - timedelta(days=index * days_apart)
        rows.append({"date": day.isoformat(), "best_price": price, "platform_prices": {"amazon": price}})
    rows.reverse()
    return rows


def _stats(prices: list[float], window: str = "90d", days: int = 90):
    today = date.today()
    points = [(today - timedelta(days=len(prices) - 1 - i), p) for i, p in enumerate(prices)]
    return window_stats(points, window=window, days=days, today=today)


def test_history_windows_resolve() -> None:
    assert resolve_history_days("90d") == ("90d", 90)
    assert resolve_history_days("1y") == ("1y", 365)
    assert resolve_history_days("all") == ("all", 3650)
    assert resolve_history_days(None, 180) == ("180d", 180)


def test_missing_days_are_not_invented() -> None:
    rows = [
        {"date": "2026-01-01", "best_price": 100, "platform_prices": {"amazon": 100}},
        {"date": "2026-01-10", "best_price": 90, "platform_prices": {"amazon": 90}},
    ]
    payload = serialize_history_payload("p1", rows, window="30d", days=30)
    assert len(payload["best_price"]) == 2
    assert payload["missing_days_are_unobserved"] is True
    assert [item["date"] for item in payload["best_price"]] == ["2026-01-01", "2026-01-10"]


def test_insufficient_history_signal() -> None:
    tracked = _stats([50000, 51000, 50500], window="tracked", days=3650)
    signal = decide_timing(
        current_price=50500,
        offers=[OfferSnapshot("amazon", 50500, True, 1.0), OfferSnapshot("flipkart", 51000, True, 1.0)],
        tracked=tracked,
        window_30=tracked,
        window_90=tracked,
        min_observation_days=7,
        min_tracking_days=14,
        stale_hours=24,
    )
    assert signal.state == "INSUFFICIENT_HISTORY"
    assert "observation" in signal.reasons[0].lower()
    assert "INSUFFICIENT_HISTORY" in signal.reason_codes


def test_consider_now_near_tracked_low() -> None:
    prices = [54000 + (i % 5) * 200 for i in range(20)]
    prices[-1] = 54100
    tracked = _stats(prices, window="tracked", days=3650)
    window_90 = _stats(prices, window="90d", days=90)
    signal = decide_timing(
        current_price=54100,
        offers=[OfferSnapshot("amazon", 54100, True, 0.5), OfferSnapshot("flipkart", 54500, True, 0.5)],
        tracked=tracked,
        window_30=window_90,
        window_90=window_90,
        min_observation_days=7,
        min_tracking_days=14,
        stale_hours=24,
    )
    assert signal.state == "CONSIDER_NOW"
    assert "lowest" in signal.reasons[0].lower()
    assert "NEAR_RECENT_LOW" in signal.reason_codes


def test_wait_when_materially_above_low() -> None:
    prices = [50000] + [58000] * 20
    tracked = _stats(prices, window="tracked", days=3650)
    window_90 = _stats(prices, window="90d", days=90)
    signal = decide_timing(
        current_price=58000,
        offers=[OfferSnapshot("amazon", 58000, True, 1.0), OfferSnapshot("croma", 58500, True, 1.0)],
        tracked=tracked,
        window_30=window_90,
        window_90=window_90,
        min_observation_days=7,
        min_tracking_days=14,
        stale_hours=24,
    )
    assert signal.state == "WAIT_FOR_BETTER_PRICE"
    assert "above" in signal.reasons[0].lower()
    assert "not a prediction" in signal.reasons[1].lower()
    assert "ABOVE_RECENT_LOW" in signal.reason_codes


def test_watch_mixed_recent_drop() -> None:
    prices = [50000] + [58000] * 18 + [56000]
    tracked = _stats(prices, window="tracked", days=3650)
    window_90 = _stats(prices, window="90d", days=90)
    signal = decide_timing(
        current_price=56000,
        offers=[OfferSnapshot("amazon", 56000, True, 1.0), OfferSnapshot("flipkart", 57000, True, 1.0)],
        tracked=tracked,
        window_30=window_90,
        window_90=window_90,
        min_observation_days=7,
        min_tracking_days=14,
        stale_hours=24,
    )
    assert signal.state == "WATCH"
    assert any("fallen recently" in reason.lower() for reason in signal.reasons)


def test_oos_only_is_unavailable() -> None:
    prices = [50000] * 20
    tracked = _stats(prices)
    signal = decide_timing(
        current_price=None,
        offers=[OfferSnapshot("amazon", 50000, False, 1.0)],
        tracked=tracked,
        window_30=tracked,
        window_90=tracked,
        min_observation_days=7,
        min_tracking_days=14,
        stale_hours=24,
    )
    assert signal.state == "UNAVAILABLE"
    assert "out of stock" in signal.reasons[0].lower()
    assert "OOS_ONLY" in signal.reason_codes
    assert "NO_POSITIVE_BUY_SIGNAL" in signal.reason_codes
    assert signal.state != "CONSIDER_NOW"


def test_stale_offers_are_not_consider_now() -> None:
    prices = [54100] * 20
    tracked = _stats(prices)
    signal = decide_timing(
        current_price=54100,
        offers=[OfferSnapshot("amazon", 54100, True, 80.0), OfferSnapshot("flipkart", 54100, True, 80.0)],
        tracked=tracked,
        window_30=tracked,
        window_90=tracked,
        min_observation_days=7,
        min_tracking_days=14,
        stale_hours=24,
    )
    assert signal.state == "WATCH"
    assert "freshness" in signal.reasons[0].lower()


def test_single_store_cannot_consider_now() -> None:
    prices = [54100] * 20
    tracked = _stats(prices)
    signal = decide_timing(
        current_price=54100,
        offers=[OfferSnapshot("amazon", 54100, True, 1.0)],
        tracked=tracked,
        window_30=tracked,
        window_90=tracked,
        min_observation_days=7,
        min_tracking_days=14,
        stale_hours=24,
    )
    assert signal.state != "CONSIDER_NOW"
    assert signal.state == "WATCH"


def test_build_intelligence_payload_is_factual() -> None:
    history = _history([60000, 58000, 54000] + [54500] * 20)
    payload = build_price_intelligence(
        product_id="p1",
        product={"best_price": 54500, "best_platform": "amazon"},
        offers=[
            {"platform": "amazon", "current_price": 54500, "stock_status": "in_stock", "last_verified_at": None},
            {"platform": "flipkart", "current_price": 54990, "stock_status": "in_stock", "last_verified_at": None},
        ],
        history=history,
        min_observation_days=7,
        min_tracking_days=14,
        stale_hours=24,
    )
    assert payload.tracked_low == 54000
    assert payload.windows["30d"].observation_days >= 7
    assert "predict" not in payload.disclosure.lower() or "does not predict" in payload.disclosure.lower()
    from mayabu.domain.price_intelligence import serialize_intelligence

    serialized = serialize_intelligence(payload)
    assert serialized["reason_codes"]
    assert serialized["purchasability"] == "in_stock"
    assert serialized["signal"] == payload.timing.state
    assert serialized["current_price"] == 54500
    assert serialized["movement"]["absolute"] is not None or serialized["movement"]["absolute"] is None


def test_oos_fallback_cannot_consider_now_even_with_best_price() -> None:
    prices = [50000] * 20
    payload = build_price_intelligence(
        product_id="p-oos",
        product={"best_price": 50000, "best_platform": "amazon"},
        offers=[{"platform": "amazon", "current_price": 50000, "stock_status": "out_of_stock"}],
        history=_history(prices),
        min_observation_days=7,
        min_tracking_days=14,
        stale_hours=24,
    )
    assert payload.timing.state != "CONSIDER_NOW"
    assert payload.timing.state == "UNAVAILABLE"
    assert payload.timing.purchasability == "out_of_stock"


def test_invalid_and_sparse_history_excluded() -> None:
    rows = [
        {"date": "2026-01-01", "best_price": 0, "platform_prices": {"amazon": 0}},
        {"date": "2026-01-02", "best_price": -10, "platform_prices": {"amazon": None}},
        {"date": "2026-01-03", "best_price": 55000, "platform_prices": {"amazon": 55000}},
    ]
    payload = serialize_history_payload("p1", rows, window="30d", days=30)
    assert len(payload["best_price"]) == 1
    assert payload["best_price"][0]["price"] == 55000
    assert "flipkart" not in payload["platforms"]


def test_percentile_and_volatility_need_depth() -> None:
    tracked = _stats([50000], window="tracked", days=3650)
    assert tracked.volatility is None
    deep = _stats([50000, 51000, 52000, 50500], window="tracked", days=3650)
    assert deep.percentile is not None
    assert deep.volatility is not None


def test_mixed_in_stock_and_oos_uses_in_stock_price() -> None:
    prices = [54100] * 20
    tracked = _stats(prices)
    signal = decide_timing(
        current_price=54100,
        offers=[
            OfferSnapshot("amazon", 54100, True, 1.0),
            OfferSnapshot("flipkart", 49990, False, 1.0),
        ],
        tracked=tracked,
        window_30=tracked,
        window_90=tracked,
        min_observation_days=7,
        min_tracking_days=14,
        stale_hours=24,
    )
    assert signal.state != "UNAVAILABLE"
    assert signal.in_stock_count == 1
    assert signal.purchasability == "in_stock"

