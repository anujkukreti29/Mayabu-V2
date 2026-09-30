"""SEO sitemap feed tests."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("psycopg")

DATABASE_URL = os.getenv("MAYABU_TEST_DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("MAYABU_TEST_DATABASE_URL not set", allow_module_level=True)


def test_chunk_product_ids_for_sitemaps_scale():
    from mayabu.search.seo_sitemap import MAX_URLS_PER_SITEMAP, chunk_product_ids_for_sitemaps

    ids_1k = [f"id-{i:06d}" for i in range(1_000)]
    chunks_1k = chunk_product_ids_for_sitemaps(ids_1k, max_urls=500)
    assert len(chunks_1k) == 2
    assert sum(len(c) for c in chunks_1k) == 1_000

    ids_10k = [f"id-{i:06d}" for i in range(10_000)]
    chunks_10k = chunk_product_ids_for_sitemaps(ids_10k, max_urls=MAX_URLS_PER_SITEMAP)
    assert len(chunks_10k) == 1

    ids_50k = [f"id-{i:06d}" for i in range(50_000)]
    chunks_50k = chunk_product_ids_for_sitemaps(ids_50k, max_urls=MAX_URLS_PER_SITEMAP)
    assert len(chunks_50k) == 2
    assert all(len(chunk) <= MAX_URLS_PER_SITEMAP for chunk in chunks_50k)
    assert sum(len(c) for c in chunks_50k) == 50_000


def test_sitemap_meta_and_products_http():
    from fastapi.testclient import TestClient

    from mayabu.api.main import app

    with TestClient(app) as client:
        meta = client.get("/api/seo/sitemap/meta?page_size=5000")
        assert meta.status_code == 200
        body = meta.json()
        assert "total" in body
        assert "pages" in body
        assert body["page_size"] == 5000

        page = client.get("/api/seo/sitemap/products?page=1&page_size=100")
        assert page.status_code == 200
        products = page.json()
        assert "items" in products
        for item in products["items"]:
            assert item["product_id"]
            assert len(item["title"]) >= 8
