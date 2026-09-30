"""Homepage discovery endpoint and serializers."""

from __future__ import annotations

from mayabu.api.serializers import serialize_product, serialize_search_result
from mayabu.search.homepage_discovery import HOMEPAGE_CACHE_KEY, get_homepage_discovery


def test_normalize_image_url_protocol_relative():
    row = {
        "product_id": "11111111-1111-1111-1111-111111111111",
        "canonical_title": "Test",
        "brand": "ASUS",
        "category": "laptop",
        "specs": {},
        "best_price": 1000,
        "best_platform": "amazon",
        "platform_count": 1,
        "image_url": "//cdn.example.com/a.jpg",
        "last_seen_at": None,
    }
    assert serialize_search_result(row)["image_url"] == "https://cdn.example.com/a.jpg"
    assert serialize_product({**row, "id": row["product_id"]})["image_url"] == "https://cdn.example.com/a.jpg"


def test_normalize_image_url_rejects_javascript():
    row = {
        "product_id": "11111111-1111-1111-1111-111111111111",
        "canonical_title": "Test",
        "category": "laptop",
        "specs": {},
        "image_url": "javascript:alert(1)",
    }
    assert serialize_search_result(row)["image_url"] is None


def test_homepage_discovery_shape_with_empty_db(monkeypatch):
    class FakeCache:
        def get_json(self, key):
            return None

        def set_json(self, key, value, ttl):
            self.key = key
            self.value = value
            self.ttl = ttl

    import mayabu.search.homepage_discovery as mod

    monkeypatch.setattr(mod, "_fetch_recently_checked", lambda limit: [])
    monkeypatch.setattr(mod, "_fetch_price_drops", lambda limit: [])
    monkeypatch.setattr(mod, "_fetch_biggest_discounts", lambda limit: [])
    monkeypatch.setattr(mod, "_fetch_lowest_since_tracking", lambda limit: [])
    monkeypatch.setattr(mod, "_fetch_multi_store", lambda limit: [])
    monkeypatch.setattr(mod, "_fetch_near_tracked_low", lambda limit: [])
    monkeypatch.setattr(mod, "_fetch_explore_by_category", lambda: [])
    monkeypatch.setattr(mod, "_fetch_category_spotlights", lambda **kwargs: [])
    monkeypatch.setattr(mod, "trending_product_ids", lambda limit=12: [])
    monkeypatch.setattr(mod, "popular_product_ids", lambda limit=12: [])
    monkeypatch.setattr(mod, "get_cache", lambda: FakeCache())

    payload = get_homepage_discovery(limit=4, use_cache=True)
    assert payload["trending"] == []
    assert payload["popular"] == []
    assert payload["recently_checked"] == []
    assert payload["price_drops"] == []
    assert payload["biggest_discounts"] == []
    assert payload["lowest_since_tracking"] == []
    assert payload.get("near_tracked_low") == []
    assert payload.get("explore_by_category") == []
    assert payload.get("category_spotlights") == []
    assert payload["featured"] == []
    assert payload.get("multi_store") == []
    assert "categories" in payload
    assert payload["semantics"]["trending"] is None
    assert HOMEPAGE_CACHE_KEY.startswith("homepage:")
    assert HOMEPAGE_CACHE_KEY.endswith(":v5")


def test_homepage_dedupe_priority(monkeypatch):
    import mayabu.search.homepage_discovery as mod

    shared = {
        "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "title": "Shared",
        "brand": "X",
        "category": "laptop",
        "specs": {},
        "best_price": 100,
        "best_platform": "amazon",
        "platform_count": 1,
        "image_url": None,
    }

    monkeypatch.setattr(mod, "trending_product_ids", lambda limit=12: [])
    monkeypatch.setattr(mod, "popular_product_ids", lambda limit=12: [])
    monkeypatch.setattr(mod, "_ordered_products_from_ids", lambda *_a, **_k: [])
    monkeypatch.setattr(mod, "_fetch_biggest_discounts", lambda limit: [{**shared, "discount_percent": 20}])
    monkeypatch.setattr(mod, "_fetch_lowest_since_tracking", lambda limit: [{**shared}])
    monkeypatch.setattr(mod, "_fetch_price_drops", lambda limit: [{**shared, "drop_percent": 10}])
    monkeypatch.setattr(mod, "_fetch_recently_checked", lambda limit: [{**shared}])
    monkeypatch.setattr(mod, "_fetch_multi_store", lambda limit: [])
    monkeypatch.setattr(mod, "_fetch_near_tracked_low", lambda limit: [])
    monkeypatch.setattr(mod, "_fetch_explore_by_category", lambda: [])
    monkeypatch.setattr(mod, "_fetch_category_spotlights", lambda **kwargs: [])
    monkeypatch.setattr(
        mod,
        "get_cache",
        lambda: type("C", (), {"get_json": lambda self, k: None, "set_json": lambda *a, **k: None})(),
    )

    payload = get_homepage_discovery(limit=4, use_cache=False)
    assert len(payload["biggest_discounts"]) == 1
    # Soft dedupe may reuse a product into a later thin section rather than emptying it.
    assert len(payload["lowest_since_tracking"]) <= 1
    assert len(payload["price_drops"]) <= 1
    assert "multi_store" in payload
    assert payload["semantics"].get("multi_store")


def test_homepage_soft_dedupe_reuses_when_section_would_be_empty():
    from mayabu.search.homepage_discovery import _dedupe_priority

    shared = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "title": "Shared"}
    unique_trend = {"id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "title": "Trend"}
    cleaned = _dedupe_priority(
        [
            ("trending", [unique_trend, shared]),
            ("lowest_since_tracking", [shared]),
        ],
        soft_min=1,
    )
    assert cleaned["trending"][0]["id"] == unique_trend["id"]
    assert cleaned["lowest_since_tracking"][0]["id"] == shared["id"]


def test_diverse_pick_caps_category_dominance():
    from mayabu.search.homepage_discovery import _diverse_pick

    rows = []
    for i in range(10):
        rows.append({"product_id": f"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa{i:02d}", "category": "laptop", "canonical_title": f"L{i}", "best_price": 1000})
    for i in range(3):
        rows.append({"product_id": f"bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb{i:02d}", "category": "smartphone", "canonical_title": f"P{i}", "best_price": 2000})
    for i in range(2):
        rows.append({"product_id": f"cccccccc-cccc-cccc-cccc-cccccccccc{i:02d}", "category": "television", "canonical_title": f"T{i}", "best_price": 3000})
    picked = _diverse_pick(rows, 8, max_per_category=3)
    cats = [p["category"] for p in picked]
    assert cats.count("laptop") <= 3
    assert "smartphone" in cats
    assert "television" in cats
