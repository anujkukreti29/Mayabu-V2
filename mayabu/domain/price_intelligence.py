"""Deterministic price intelligence for Mayabu.

Facts only: current public offers + recorded daily observations.
Does not predict future retailer prices. Does not invent missing days.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from statistics import pstdev
from typing import Any, Iterable, Literal, Mapping, Sequence

from mayabu.core.config import get_app_settings
from mayabu.monitoring import instrumentation as metrics
from mayabu.search.search_repository import get_price_history, get_product, get_product_offers

TimingState = Literal[
    "CONSIDER_NOW",
    "WATCH",
    "WAIT_FOR_BETTER_PRICE",
    "INSUFFICIENT_HISTORY",
    "UNAVAILABLE",
]

WINDOW_DAYS: dict[str, int] = {
    "30d": 30,
    "90d": 90,
    "180d": 180,
    "6m": 180,
    "1y": 365,
    "all": 3650,
}

DISCLOSURE = (
    "Mayabu compares the current public price with prices it has observed over time. "
    "It considers tracking depth, relative current price, recent movement, freshness, "
    "and store coverage. It does not predict future retailer prices."
)

_OOS_STOCK = frozenset({"out_of_stock", "unavailable", "oos"})


def resolve_history_days(window: str | None, days: int | None = None) -> tuple[str, int]:
    if window:
        key = str(window).strip().lower()
        if key in WINDOW_DAYS:
            return key if key != "6m" else "180d", WINDOW_DAYS[key]
        if key.endswith("d") and key[:-1].isdigit():
            value = max(1, min(int(key[:-1]), 3650))
            return f"{value}d", value
    if days is not None:
        value = max(1, min(int(days), 3650))
        inverse = {30: "30d", 90: "90d", 180: "180d", 365: "1y", 3650: "all"}
        return inverse.get(value, f"{value}d"), value
    return "90d", 90


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return number


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _age_hours(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    now = datetime.now(tz=value.tzinfo)
    return max(0.0, (now - value).total_seconds() / 3600.0)


@dataclass(frozen=True, slots=True)
class WindowStats:
    window: str
    observation_days: int
    tracking_days: int
    low: float | None
    high: float | None
    latest: float | None
    percentile: float | None
    volatility: float | None
    recent_change: float | None
    recent_change_pct: float | None


@dataclass(frozen=True, slots=True)
class TimingSignal:
    state: TimingState
    label: str
    reasons: tuple[str, ...]
    reason_codes: tuple[str, ...]
    window: str
    freshness_hours: float | None
    store_count: int
    in_stock_count: int
    purchasability: str


@dataclass(frozen=True, slots=True)
class OfferSnapshot:
    platform: str
    price: float | None
    in_stock: bool
    freshness_hours: float | None


@dataclass(frozen=True, slots=True)
class PriceIntelligence:
    product_id: str
    current_price: float | None
    current_platform: str | None
    freshness_hours: float | None
    store_count: int
    in_stock_count: int
    observation_count: int
    tracking_days: int
    tracked_low: float | None
    tracked_high: float | None
    windows: dict[str, WindowStats]
    timing: TimingSignal
    platform_summary: dict[str, dict[str, Any]]
    disclosure: str


def _label_for(state: TimingState) -> str:
    return {
        "CONSIDER_NOW": "Consider now",
        "WATCH": "Watch",
        "WAIT_FOR_BETTER_PRICE": "Wait for a better price",
        "INSUFFICIENT_HISTORY": "Not enough history yet",
        "UNAVAILABLE": "Price timing unavailable",
    }[state]


def _in_window(points: Sequence[tuple[date, float]], days: int, *, today: date) -> list[tuple[date, float]]:
    start = today - timedelta(days=days)
    return [(day, price) for day, price in points if day >= start]


def window_stats(
    points: Sequence[tuple[date, float]],
    *,
    window: str,
    days: int,
    today: date | None = None,
) -> WindowStats:
    today = today or date.today()
    subset = _in_window(points, days, today=today) if window != "tracked" else list(points)
    if not subset:
        return WindowStats(window, 0, 0, None, None, None, None, None, None, None)
    prices = [price for _, price in subset]
    low = min(prices)
    high = max(prices)
    latest = subset[-1][1]
    tracking_days = (subset[-1][0] - subset[0][0]).days + 1
    below_or_equal = sum(1 for price in prices if price <= latest)
    percentile = round(100.0 * below_or_equal / len(prices), 1)
    volatility = None
    if len(prices) >= 3 and (mean := sum(prices) / len(prices)) > 0:
        volatility = round(pstdev(prices) / mean, 4)
    recent_change = recent_pct = None
    if len(subset) >= 2:
        previous = subset[-2][1]
        recent_change = round(latest - previous, 2)
        if previous > 0:
            recent_pct = round(100.0 * (latest - previous) / previous, 2)
    return WindowStats(
        window=window,
        observation_days=len(subset),
        tracking_days=tracking_days,
        low=low,
        high=high,
        latest=latest,
        percentile=percentile,
        volatility=volatility,
        recent_change=recent_change,
        recent_change_pct=recent_pct,
    )


def _format_inr(value: float) -> str:
    return f"₹{value:,.0f}"


def decide_timing(
    *,
    current_price: float | None,
    offers: Sequence[OfferSnapshot],
    tracked: WindowStats,
    window_30: WindowStats,
    window_90: WindowStats,
    min_observation_days: int,
    min_tracking_days: int,
    stale_hours: int,
) -> TimingSignal:
    store_count = len(offers)
    in_stock = [offer for offer in offers if offer.in_stock and offer.price is not None]
    priced = [offer for offer in offers if offer.price is not None]
    freshness_values = [offer.freshness_hours for offer in offers if offer.freshness_hours is not None]
    freshness_hours = min(freshness_values) if freshness_values else None
    in_stock_count = len(in_stock)

    purchasability = "in_stock" if in_stock_count > 0 else ("out_of_stock" if priced else "unknown")

    def _signal(
        state: TimingState,
        reasons: Sequence[str],
        window: str,
        codes: Sequence[str],
    ) -> TimingSignal:
        return TimingSignal(
            state=state,
            label=_label_for(state),
            reasons=tuple(reasons[:3]),
            reason_codes=tuple(codes[:8]),
            window=window,
            freshness_hours=freshness_hours,
            store_count=store_count,
            in_stock_count=in_stock_count,
            purchasability=purchasability,
        )

    if not priced:
        return _signal(
            "UNAVAILABLE",
            ("No current public priced offers to evaluate.",),
            "tracked",
            ("NO_PRICED_OFFERS",),
        )
    if in_stock_count == 0:
        return _signal(
            "UNAVAILABLE",
            ("Currently out of stock at checked stores.", "Last-known prices remain in history."),
            "tracked",
            ("OOS_ONLY", "NO_POSITIVE_BUY_SIGNAL"),
        )
    if current_price is None:
        return _signal(
            "UNAVAILABLE",
            ("No in-stock public price is available.",),
            "tracked",
            ("NO_IN_STOCK_PRICE", "NO_POSITIVE_BUY_SIGNAL"),
        )

    evidence_window = window_90 if window_90.observation_days >= min_observation_days else tracked
    if (
        evidence_window.observation_days < min_observation_days
        or evidence_window.tracking_days < min_tracking_days
    ):
        days = evidence_window.tracking_days or evidence_window.observation_days
        return _signal(
            "INSUFFICIENT_HISTORY",
            (
                f"Mayabu has only {evidence_window.observation_days} tracked observation"
                f"{'' if evidence_window.observation_days == 1 else 's'} "
                f"over {days} day{'s' if days != 1 else ''}.",
                "More observations are needed before showing a price-timing signal.",
            ),
            evidence_window.window,
            ("INSUFFICIENT_HISTORY",),
        )

    stale = freshness_hours is not None and freshness_hours > stale_hours
    coverage_low = in_stock_count < 2
    compare_low = evidence_window.low
    if evidence_window.window == "90d" and evidence_window.tracking_days >= 90:
        window_name = "90 days"
    elif evidence_window.window == "30d" and evidence_window.tracking_days >= 30:
        window_name = "30 days"
    else:
        window_name = "the tracked period"
    gap = None
    gap_pct = None
    if compare_low and compare_low > 0:
        gap = current_price - compare_low
        gap_pct = (gap / compare_low) * 100.0

    recent_drop = (window_30.recent_change or 0) < 0 and abs(window_30.recent_change or 0) >= max(
        100.0, current_price * 0.02
    )

    if stale:
        return _signal(
            "WATCH",
            (
                "Current offers are older than Mayabu's freshness threshold.",
                "Use Check latest price before treating this as a buying moment.",
            ),
            evidence_window.window,
            ("STALE_OFFERS", "FRESHNESS_DOWNGRADED"),
        )

    if gap is not None and gap_pct is not None and gap_pct <= 3.0 and not coverage_low:
        return _signal(
            "CONSIDER_NOW",
            (
                f"{_format_inr(current_price)} is within {gap_pct:.1f}% of the lowest price Mayabu has tracked over {window_name}.",
                f"Checked across {in_stock_count} in-stock stores.",
            ),
            evidence_window.window,
            ("NEAR_RECENT_LOW", "MULTI_STORE", "FRESH"),
        )

    if gap is not None and gap_pct is not None and gap_pct >= 8.0:
        reasons = [
            f"Current price is {_format_inr(gap)} above the lowest price tracked over {window_name}.",
            "This is not a prediction that the lower price will return.",
        ]
        if recent_drop:
            reasons.insert(
                1,
                f"Price has fallen recently, but it remains above the lowest price tracked over {window_name}.",
            )
            return _signal(
                "WATCH",
                reasons,
                evidence_window.window,
                ("RECENT_DROP_ABOVE_LOW", "ABOVE_RECENT_LOW", "NOT_A_PREDICTION"),
            )
        return _signal(
            "WAIT_FOR_BETTER_PRICE",
            reasons,
            evidence_window.window,
            ("ABOVE_RECENT_LOW", "NOT_A_PREDICTION"),
        )

    reasons: list[str] = []
    codes: list[str] = ["MIXED_EVIDENCE"]
    if recent_drop:
        reasons.append("Price has fallen recently, but it remains above the lowest price tracked over {window_name}.".format(window_name=window_name))
        codes.append("RECENT_DROP_ABOVE_LOW")
    elif gap is not None and gap_pct is not None:
        reasons.append(
            f"{_format_inr(current_price)} is {gap_pct:.1f}% above the lowest price tracked over {window_name}."
        )
        codes.append("WITHIN_TRACKED_RANGE")
    else:
        reasons.append("Current price sits inside the recent tracked range.")
        codes.append("WITHIN_TRACKED_RANGE")
    if coverage_low:
        reasons.append("Only one eligible retailer currently has an in-stock public price.")
        codes.append("SINGLE_STORE")
    if not reasons:
        reasons.append("Evidence is mixed, so Mayabu is not issuing a buy or wait judgment.")
    return _signal("WATCH", reasons, evidence_window.window, codes)


def signal_contradictions(payload: PriceIntelligence) -> list[str]:
    """Return machine-readable contradiction codes; empty means consistent."""
    issues: list[str] = []
    timing = payload.timing
    text = " ".join(timing.reasons).lower()
    label = (timing.label or "").lower()
    codes = set(timing.reason_codes)
    if timing.state == "CONSIDER_NOW":
        if timing.purchasability != "in_stock":
            issues.append("consider_now_not_in_stock")
        if timing.in_stock_count < 2:
            issues.append("consider_now_single_store")
        if "out of stock" in text or "out of stock" in label:
            issues.append("consider_now_oos_wording")
        if "STALE_OFFERS" in codes or "stale" in text:
            issues.append("consider_now_stale")
        if "OOS_ONLY" in codes:
            issues.append("consider_now_oos_code")
        if payload.freshness_hours is not None and payload.freshness_hours > 24:
            issues.append("consider_now_stale_hours")
    if "90 days" in text and payload.tracking_days < 90:
        issues.append("90d_wording_without_90_tracked_days")
    if timing.state == "CONSIDER_NOW" and payload.current_price is None:
        issues.append("consider_now_without_price")
    return issues


def _observation_points(history: Iterable[Mapping[str, Any]]) -> list[tuple[date, float]]:
    points: list[tuple[date, float]] = []
    for row in history:
        day = _as_date(row.get("date") or row.get("observed_at"))
        price = _as_float(row.get("best_price"))
        if day is None or price is None:
            continue
        points.append((day, price))
    points.sort(key=lambda item: item[0])
    return points


def _platform_series(history: Iterable[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    series: dict[str, list[dict[str, Any]]] = {}
    for row in history:
        day = _as_date(row.get("date") or row.get("observed_at"))
        platforms = row.get("platform_prices") or {}
        if not isinstance(platforms, dict):
            continue
        for platform, raw in platforms.items():
            price = _as_float(raw)
            if day is None or price is None:
                continue
            series.setdefault(str(platform), []).append(
                {"date": day.isoformat(), "price": price, "observed": True}
            )
    for values in series.values():
        values.sort(key=lambda item: item["date"])
    return series


def _offer_snapshots(rows: Sequence[Mapping[str, Any]]) -> list[OfferSnapshot]:
    snapshots: list[OfferSnapshot] = []
    for row in rows:
        match_status = str(row.get("match_status") or "matched").strip().lower()
        if match_status not in {"", "matched"}:
            continue
        price = _as_float(row.get("current_price") or row.get("price") or row.get("current_effective_price"))
        checked = row.get("last_verified_at") or row.get("last_successful_refresh_at") or row.get("last_checked_at")
        snapshots.append(
            OfferSnapshot(
                platform=str(row.get("platform") or ""),
                price=price,
                in_stock=str(row.get("stock_status") or "").lower() not in _OOS_STOCK,
                freshness_hours=_age_hours(checked),
            )
        )
    return snapshots


def build_price_intelligence(
    *,
    product_id: str,
    product: Mapping[str, Any] | None,
    offers: Sequence[Mapping[str, Any]],
    history: Sequence[Mapping[str, Any]],
    min_observation_days: int,
    min_tracking_days: int,
    stale_hours: int,
) -> PriceIntelligence:
    snapshots = _offer_snapshots(offers)
    in_stock_priced = [item for item in snapshots if item.in_stock and item.price is not None]
    current_price = min((item.price for item in in_stock_priced if item.price is not None), default=None)
    current_platform = None
    if current_price is not None:
        match = next((item for item in in_stock_priced if item.price == current_price), None)
        current_platform = match.platform if match else None
    elif product:
        current_price = _as_float(product.get("best_price"))
        if product.get("best_platform"):
            current_platform = str(product.get("best_platform"))

    points = _observation_points(history)
    today = date.today()
    tracked = window_stats(points, window="tracked", days=3650, today=today)
    stats_30 = window_stats(points, window="30d", days=30, today=today)
    stats_90 = window_stats(points, window="90d", days=90, today=today)
    timing = decide_timing(
        current_price=current_price if in_stock_priced else None,
        offers=snapshots,
        tracked=tracked,
        window_30=stats_30,
        window_90=stats_90,
        min_observation_days=min_observation_days,
        min_tracking_days=min_tracking_days,
        stale_hours=stale_hours,
    )
    metrics.PRICE_SIGNAL.inc(signal=timing.state)

    platform_summary: dict[str, dict[str, Any]] = {}
    for platform, series in _platform_series(history).items():
        prices = [float(item["price"]) for item in series]
        platform_summary[platform] = {
            "observation_days": len(series),
            "low": min(prices) if prices else None,
            "high": max(prices) if prices else None,
            "latest": prices[-1] if prices else None,
        }

    freshness_values = [item.freshness_hours for item in snapshots if item.freshness_hours is not None]
    return PriceIntelligence(
        product_id=product_id,
        current_price=current_price,
        current_platform=current_platform,
        freshness_hours=min(freshness_values) if freshness_values else None,
        store_count=len(snapshots),
        in_stock_count=len(in_stock_priced),
        observation_count=tracked.observation_days,
        tracking_days=tracked.tracking_days,
        tracked_low=tracked.low,
        tracked_high=tracked.high,
        windows={"30d": stats_30, "90d": stats_90, "tracked": tracked},
        timing=timing,
        platform_summary=platform_summary,
        disclosure=DISCLOSURE,
    )


def serialize_intelligence(payload: PriceIntelligence) -> dict[str, Any]:
    windows = {
        name: asdict(stats)
        for name, stats in payload.windows.items()
    }
    timing = asdict(payload.timing)
    timing["reasons"] = list(payload.timing.reasons)
    timing["reason_codes"] = list(payload.timing.reason_codes)
    previous = payload.windows.get("30d")
    movement = {
        "absolute": previous.recent_change if previous else None,
        "percent": previous.recent_change_pct if previous else None,
        "previous_price": (
            None
            if not previous or previous.latest is None or previous.recent_change is None
            else round(previous.latest - previous.recent_change, 2)
        ),
    }
    return {
        "product_id": payload.product_id,
        "signal": payload.timing.state,
        "explanation": payload.timing.reasons[0] if payload.timing.reasons else None,
        "reason_codes": list(payload.timing.reason_codes),
        "current_price": payload.current_price,
        "retailer": payload.current_platform,
        "purchasability": payload.timing.purchasability,
        "current": {
            "price": payload.current_price,
            "platform": payload.current_platform,
            "purchasability": payload.timing.purchasability,
        },
        "freshness": {
            "hours": payload.freshness_hours,
        },
        "store_coverage": {
            "store_count": payload.store_count,
            "in_stock_count": payload.in_stock_count,
        },
        "history_summary": {
            "observation_count": payload.observation_count,
            "tracking_days": payload.tracking_days,
            "tracked_low": payload.tracked_low,
            "tracked_high": payload.tracked_high,
        },
        "windows": windows,
        "timing_signal": timing,
        "reasons": list(payload.timing.reasons),
        "movement": movement,
        "platform_summary": payload.platform_summary,
        "disclosure": payload.disclosure,
    }


def get_price_intelligence(product_id: str) -> PriceIntelligence | None:
    product = get_product(product_id)
    if not product:
        return None
    settings = get_app_settings()
    offers = get_product_offers(product_id)
    history = get_price_history(product_id, days=3650)
    return build_price_intelligence(
        product_id=product_id,
        product=product,
        offers=offers,
        history=history,
        min_observation_days=settings.intelligence_min_observation_days,
        min_tracking_days=settings.intelligence_min_tracking_days,
        stale_hours=settings.intelligence_stale_hours,
    )


def serialize_history_payload(
    product_id: str,
    history_rows: Sequence[Mapping[str, Any]],
    *,
    window: str,
    days: int,
) -> dict[str, Any]:
    best_series = []
    for row in history_rows:
        day = _as_date(row.get("date") or row.get("observed_at"))
        price = _as_float(row.get("best_price"))
        if day is None or price is None:
            continue
        best_series.append(
            {
                "date": day.isoformat(),
                "price": price,
                "observed": True,
                "platform_count": row.get("platform_count"),
                "observations_count": row.get("observations_count"),
                "in_stock_observations": row.get("in_stock_observations"),
                "stock_inferred_from_price": False,
            }
        )
    platforms = _platform_series(history_rows)
    return {
        "product_id": product_id,
        "window": window,
        "days": days,
        "best_price": best_series,
        "platforms": platforms,
        "history": [dict(row) for row in history_rows],
        "missing_days_are_unobserved": True,
        "stock_history_note": (
            "in_stock_observations is a listing-day count when recorded; "
            "a price without that count does not imply the product was in stock."
        ),
    }
