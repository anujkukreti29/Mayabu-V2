"""Product activity aggregate tests."""

from __future__ import annotations

from mayabu.search import product_activity as mod


def test_record_rejects_invalid_event(monkeypatch):
    monkeypatch.setattr(mod, "product_exists", lambda _pid: True)
    result = mod.record_product_activity(
        product_id="11111111-1111-1111-1111-111111111111",
        event_type="impression",
        client_id="client-a",
    )
    assert result["accepted"] is False
    assert result["reason"] == "invalid_event"


def test_record_rejects_unknown_product(monkeypatch):
    monkeypatch.setattr(mod, "product_exists", lambda _pid: False)
    result = mod.record_product_activity(
        product_id="11111111-1111-1111-1111-111111111111",
        event_type="product_view",
        client_id="client-a",
    )
    assert result["accepted"] is False
    assert result["reason"] == "unknown_product"


def test_trending_requires_momentum(monkeypatch):
    monkeypatch.setattr(
        mod,
        "_fetch_activity_scores",
        lambda **_kwargs: [
            {
                "product_id": "11111111-1111-1111-1111-111111111111",
                "recent_count": 5,
                "baseline_count": 8,
                "momentum": 0.6,
            },
            {
                "product_id": "22222222-2222-2222-2222-222222222222",
                "recent_count": 6,
                "baseline_count": 1,
                "momentum": 6.0,
            },
        ],
    )
    assert mod.trending_product_ids(limit=5) == ["22222222-2222-2222-2222-222222222222"]


def test_popular_uses_window_totals(monkeypatch):
    monkeypatch.setattr(
        mod,
        "_fetch_activity_scores",
        lambda **_kwargs: [
            {"product_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "recent_count": 9},
            {"product_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "recent_count": 7},
        ],
    )
    assert mod.popular_product_ids(limit=5) == [
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    ]
