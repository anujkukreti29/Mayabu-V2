"""Tests for /api/search/suggest — same public search universe, bounded payload."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from mayabu.api.main import app


def test_search_suggest_empty_query_returns_categories_without_fake_popular():
    with patch("mayabu.search.search_repository.popular_search_queries", return_value=[]):
        with TestClient(app) as client:
            response = client.get("/api/search/suggest", params={"q": ""})
    assert response.status_code == 200
    payload = response.json()
    assert payload["products"] == []
    assert isinstance(payload["categories"], list)
    assert payload["popular_queries"] == []
    assert "search_contract_version" in payload


def test_search_suggest_reuses_search_products_and_bounds_fields():
    fake_row = {
        "id": "prod-1",
        "title": "Samsung Galaxy S24 8GB 256GB",
        "brand": "Samsung",
        "category": "smartphone",
        "image_url": "https://cdn.example.com/p.jpg",
        "best_price": 54999,
        "best_platform": "flipkart",
        "offer_count": 3,
        "platform_count": 3,
        "display_specs": {"ram_gb": 8, "storage_gb": 256},
        "specs": {"ram_gb": 8, "storage_gb": 256},
        "model_codes": ["SM-S921B"],
        "match_group": "exact_match",
    }
    with (
        patch("mayabu.api.search_routes.classify_query") as classify,
        patch("mayabu.api.search_routes.search_products", return_value=[fake_row]) as search,
        patch("mayabu.api.search_routes.cache") as cache_mock,
    ):
        classify.return_value.is_relevant = True
        cache_mock.get_json.return_value = None
        with TestClient(app) as client:
            response = client.get("/api/search/suggest", params={"q": "galaxy", "limit": 6})
    assert response.status_code == 200
    payload = response.json()
    assert search.called
    assert len(payload["products"]) == 1
    product = payload["products"][0]
    assert set(product.keys()) >= {
        "id",
        "title",
        "brand",
        "category",
        "image_url",
        "best_price",
        "best_platform",
        "offer_count",
        "display_specs",
        "specs",
        "model_codes",
    }
    assert "rank_score" not in product
    assert product["best_price"] == 54999


def test_search_suggest_short_query_skips_product_search():
    with patch("mayabu.api.search_routes.search_products") as search:
        with TestClient(app) as client:
            response = client.get("/api/search/suggest", params={"q": "a"})
    assert response.status_code == 200
    assert response.json()["products"] == []
    search.assert_not_called()
