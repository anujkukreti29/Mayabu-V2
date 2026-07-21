from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

import psycopg
import pytest
from psycopg.rows import dict_row


TEST_DATABASE_URL = os.getenv("MAYABU_TEST_DATABASE_URL")


def _require_safe_test_database() -> str:
    if not TEST_DATABASE_URL:
        pytest.skip("Set MAYABU_TEST_DATABASE_URL to run PostgreSQL integration tests")
    database_name = urlparse(TEST_DATABASE_URL).path.lstrip("/").lower()
    if "test" not in database_name:
        pytest.fail("MAYABU_TEST_DATABASE_URL must point to a database whose name contains 'test'")
    return TEST_DATABASE_URL


@pytest.mark.integration
def test_v51_schema_search_document_and_queue_primitives() -> None:
    database_url = _require_safe_test_database()
    schema = Path("mayabu_db/schema.sql").read_text(encoding="utf-8")

    with psycopg.connect(database_url, autocommit=True, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(schema, prepare=False)

    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        try:
            with conn.cursor() as cur:
                specs = {
                    "brand": "apple",
                    "family": "macbook air",
                    "model_codes": ["MLY33HN/A"],
                    "cpu_models": ["apple m2"],
                    "ram_gb": 8,
                    "storage_gb": 256,
                    "screen_inch": 13.6,
                }
                cur.execute(
                    """
                    insert into product_clusters(category, brand, canonical_title, title_norm, specs)
                    values ('laptop','apple',%s,%s,%s::jsonb)
                    returning id
                    """,
                    (
                        "Apple MacBook Air M2 8GB 256GB MLY33HN/A",
                        "apple macbook air m2 8gb 256gb mly33hn a",
                        json.dumps(specs),
                    ),
                )
                product_id = cur.fetchone()["id"]
                cur.execute(
                    """
                    insert into platform_listings(
                      product_id, platform, listing_id, native_id, listing_url,
                      listing_url_hash, title, title_norm, category, specs,
                      current_price, current_mrp, stock_status, match_status,
                      match_confidence, match_method
                    ) values (
                      %s,'amazon',%s,%s,%s,%s,%s,%s,'laptop',%s::jsonb,
                      79990,99900,'in_stock','matched',1000,'integration_fixture'
                    )
                    """,
                    (
                        product_id,
                        f"amazon:test-{product_id}",
                        f"test-{product_id}",
                        f"https://www.amazon.in/dp/test-{product_id}",
                        f"hash-{product_id}",
                        "Apple MacBook Air M2 8GB 256GB MLY33HN/A",
                        "apple macbook air m2 8gb 256gb mly33hn a",
                        json.dumps(specs),
                    ),
                )
                cur.execute("select refresh_product_search_document(%s)", (product_id,))
                cur.execute(
                    """
                    select product_id, best_price, best_platform, platform_count,
                           model_codes_text, storage_gb
                    from product_search_documents where product_id = %s
                    """,
                    (product_id,),
                )
                document = cur.fetchone()
                assert document is not None
                assert document["best_price"] == 79990
                assert document["best_platform"] == "amazon"
                assert document["platform_count"] == 1
                assert "MLY33HN/A" in document["model_codes_text"]
                assert document["storage_gb"] == 256

                cur.execute(
                    """
                    insert into scrape_tasks(platform, task_type, query, idempotency_key, created_by)
                    values ('amazon','discovery_search','macbook air m2',%s,'integration_test')
                    returning id
                    """,
                    (f"integration-{product_id}",),
                )
                assert cur.fetchone() is not None
        finally:
            conn.rollback()
