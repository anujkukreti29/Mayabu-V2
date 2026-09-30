"""Public isolation, signal consistency, and health semantics — no live retailers."""

from __future__ import annotations

from datetime import date, timedelta

from mayabu.domain.price_intelligence import (
    OfferSnapshot,
    build_price_intelligence,
    decide_timing,
    signal_contradictions,
    window_stats,
)
from mayabu.search.public_price import compute_public_best_price, listing_is_public_priced
from mayabu.scheduler.error_classes import classify_exception, classify_refresh_failure
from mayabu.scheduler.lease import SchedulerHeartbeat, scheduler_is_functioning
from mayabu_refresh.models import RefreshResult


def _stats(prices: list[float]):
    today = date.today()
    points = [(today - timedelta(days=len(prices) - 1 - i), p) for i, p in enumerate(prices)]
    return window_stats(points, window="90d", days=90, today=today)


def _history(prices: list[float]) -> list[dict]:
    end = date.today()
    rows = []
    for index, price in enumerate(reversed(prices)):
        day = end - timedelta(days=index)
        rows.append({"date": day.isoformat(), "best_price": price, "platform_prices": {"amazon": price}})
    rows.reverse()
    return rows


def test_unmatched_and_needs_review_never_public_priced() -> None:
    unmatched = {
        "platform": "amazon",
        "current_price": 1000,
        "stock_status": "in_stock",
        "category": "laptop",
        "match_status": "unmatched",
        "currency": "INR",
    }
    review = {**unmatched, "match_status": "needs_review", "current_price": 1100}
    matched = {
        "platform": "flipkart",
        "current_price": 54990,
        "stock_status": "in_stock",
        "category": "laptop",
        "match_status": "matched",
        "currency": "INR",
    }
    assert listing_is_public_priced(unmatched, "laptop") is False
    assert listing_is_public_priced(review, "laptop") is False
    result = compute_public_best_price([unmatched, review, matched], "laptop")
    assert result.best_price is not None
    assert float(result.best_price) == 54990
    assert result.best_platform == "flipkart"


def test_unmatched_offer_cannot_drive_intelligence() -> None:
    history = _history([60000] * 20)
    payload = build_price_intelligence(
        product_id="iso",
        product={"best_price": 54990, "best_platform": "amazon"},
        offers=[
            {"platform": "amazon", "current_price": 54990, "stock_status": "in_stock", "match_status": "matched"},
            {"platform": "flipkart", "current_price": 999, "stock_status": "in_stock", "match_status": "unmatched"},
            {"platform": "croma", "current_price": 1000, "stock_status": "in_stock", "match_status": "needs_review"},
        ],
        history=history,
        min_observation_days=7,
        min_tracking_days=14,
        stale_hours=24,
    )
    assert payload.current_price == 54990
    assert payload.store_count == 1
    assert payload.timing.state != "CONSIDER_NOW"


def test_consider_now_contradicts_oos_and_stale() -> None:
    prices = [54100] * 20
    tracked = _stats(prices)
    oos = decide_timing(
        current_price=None,
        offers=[OfferSnapshot("amazon", 54100, False, 1.0)],
        tracked=tracked,
        window_30=tracked,
        window_90=tracked,
        min_observation_days=7,
        min_tracking_days=14,
        stale_hours=24,
    )
    assert oos.state != "CONSIDER_NOW"
    assert oos.purchasability == "out_of_stock"
    stale = decide_timing(
        current_price=54100,
        offers=[OfferSnapshot("amazon", 54100, True, 80.0), OfferSnapshot("flipkart", 54100, True, 80.0)],
        tracked=tracked,
        window_30=tracked,
        window_90=tracked,
        min_observation_days=7,
        min_tracking_days=14,
        stale_hours=24,
    )
    assert stale.state != "CONSIDER_NOW"
    payload = build_price_intelligence(
        product_id="oos",
        product={"best_price": 54100, "best_platform": "amazon"},
        offers=[{"platform": "amazon", "current_price": 54100, "stock_status": "out_of_stock"}],
        history=_history(prices),
        min_observation_days=7,
        min_tracking_days=14,
        stale_hours=24,
    )
    assert payload.timing.state != "CONSIDER_NOW"
    assert not signal_contradictions(payload)


def test_short_history_does_not_claim_90_days() -> None:
    prices = [50000 + i for i in range(16)]
    payload = build_price_intelligence(
        product_id="short",
        product={"best_price": prices[-1], "best_platform": "amazon"},
        offers=[
            {"platform": "amazon", "current_price": prices[-1], "stock_status": "in_stock"},
            {"platform": "flipkart", "current_price": prices[-1] + 100, "stock_status": "in_stock"},
        ],
        history=_history(prices),
        min_observation_days=7,
        min_tracking_days=14,
        stale_hours=24,
    )
    text = " ".join(payload.timing.reasons).lower()
    assert "90 days" not in text
    assert "90d_wording_without_90_tracked_days" not in signal_contradictions(payload)


def test_two_store_rule_keeps_single_store_on_watch() -> None:
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
    assert signal.state == "WATCH"
    assert "SINGLE_STORE" in signal.reason_codes


def test_scheduler_error_tick_is_not_functioning() -> None:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    ok = SchedulerHeartbeat(
        domain="automation",
        holder_id="a",
        leased_until=now,
        heartbeat_at=now,
        last_successful_tick_at=now,
        jobs_scheduled_total=1,
        last_error=None,
        last_tick_result="ok",
        last_tick_duration_ms=10,
        last_tick_jobs=1,
        age_seconds=1,
        alive=True,
    )
    failing = SchedulerHeartbeat(
        domain="automation",
        holder_id="a",
        leased_until=now,
        heartbeat_at=now,
        last_successful_tick_at=None,
        jobs_scheduled_total=0,
        last_error="boom",
        last_tick_result="error",
        last_tick_duration_ms=10,
        last_tick_jobs=0,
        age_seconds=1,
        alive=True,
    )
    assert scheduler_is_functioning(ok) is True
    assert scheduler_is_functioning(failing) is False


def test_scheduled_oos_without_price_is_valid() -> None:
    listing = {
        "platform": "amazon",
        "listing_url": "https://www.amazon.in/dp/B0ABCDEFGHI",
        "category": "laptop",
        "current_price": 70000,
        "stock_status": "in_stock",
    }
    from mayabu_db.refresh_ingestion import validate_refresh_result

    result = RefreshResult(current_price=None, stock_status="out_of_stock", page_status="success")
    ok, flags = validate_refresh_result(listing, result, allow_out_of_stock_without_price=False)
    assert ok is True
    assert not any(flag["code"] == "missing_price" for flag in flags)


def test_error_classes_distinguish_challenge_from_parser() -> None:
    assert classify_refresh_failure(RefreshResult.failed("captcha", page_status="captcha")) == "challenge"
    assert classify_refresh_failure(RefreshResult(page_status="success", current_price=None, warnings=["selector miss"])) == "parsing"
    assert classify_exception(TimeoutError("timed out")) == "timeout"


def test_due_refresh_sql_keeps_quarantine_and_fairness() -> None:
    from mayabu.scheduler import refresh_policy
    import inspect

    source = inspect.getsource(refresh_policy)
    assert "unmatched" in source
    assert "needs_review" in source
    assert "platform_rank" in source
    assert "partition by ranked.platform" in source
    assert "refresh_tier" in source


def test_materializer_records_task_source() -> None:
    from mayabu.scheduler import task_materializer
    import inspect

    source = inspect.getsource(task_materializer.materialize_refresh)
    assert "task_source" in source
    assert "scheduler_refresh" in source


def test_circuit_open_only_while_future() -> None:
    from datetime import datetime, timedelta, timezone

    from mayabu.scheduler.platform_health_policy import _circuit_is_open

    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    assert _circuit_is_open(None) is False
    assert _circuit_is_open(past) is False
    assert _circuit_is_open(future) is True


def test_discovery_cursor_persists_across_restart_semantics() -> None:
    from mayabu.scheduler.discovery_cursor import (
        MAX_ROTATION_PAGE,
        start_page_from_metadata,
        supports_page_cursor,
    )

    assert supports_page_cursor("amazon") is True
    assert supports_page_cursor("croma") is False
    assert start_page_from_metadata({"cursor": {"last_page": 2, "mode": "page_offset"}}) == 3
    restarted = start_page_from_metadata({"cursor": {"last_page": 2}})
    assert restarted == 3
    assert start_page_from_metadata({"cursor": {"last_page": MAX_ROTATION_PAGE}}) == 1
