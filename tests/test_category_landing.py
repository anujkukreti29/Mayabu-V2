"""Category landing API and discovery payload."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("psycopg")

DATABASE_URL = os.getenv("MAYABU_TEST_DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("MAYABU_TEST_DATABASE_URL not set", allow_module_level=True)


def test_category_landing_payload_shape_for_public_categories():
    from mayabu.search.category_landing import build_category_landing
    from mayabu.search.category_registry import public_search_categories

    for slug in public_search_categories():
        payload = build_category_landing(slug, product_limit=12, section_limit=4)
        assert payload["category"] == slug
        assert isinstance(payload["products"], list)
        assert isinstance(payload["featured"], list)
        assert isinstance(payload["facets"], dict)
        assert "price_drops" in payload
        assert "biggest_discounts" in payload
        assert "lowest_since_tracking" in payload
        assert "related_categories" in payload
        assert slug not in payload["related_categories"]
        for product in payload["products"]:
            assert product.get("category") == slug
            assert product.get("best_price")


def test_category_landing_rejects_unknown_category():
    from mayabu.search.category_landing import build_category_landing

    with pytest.raises(ValueError, match="invalid_category"):
        build_category_landing("not-a-real-category")


def test_category_landing_http_endpoint():
    from fastapi.testclient import TestClient

    from mayabu.api.main import app

    with TestClient(app) as client:
        response = client.get("/api/categories/laptop/landing?product_limit=12&section_limit=4")
        assert response.status_code == 200
        body = response.json()
        assert body["category"] == "laptop"
        assert "products" in body
        assert "facets" in body

        bad = client.get("/api/categories/notreal/landing")
        assert bad.status_code in {400, 404}
