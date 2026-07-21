"""Database-backed v4.5.1 product-matching integration checks.

These tests intentionally execute the real SQL paths that smoke tests cannot
catch: pg_trgm candidate recall, duplicate finder, rejected-pair suppression,
merge chain resolution, and price-alert reassignment.

Run locally with a disposable/dev database:

    set MAYABU_INTEGRATION_DATABASE_URL=postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu
    python tests\\integration_v451_matching_db.py

If MAYABU_INTEGRATION_DATABASE_URL is not set, the test exits cleanly so normal
fast smoke checks keep working without Docker/Postgres.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

Jsonb = None
close_connection_pool = None
db_connection = None
apply_schema = None
find_duplicate_product_candidates = None
list_candidate_products = None
merge_products = None
reject_review_item = None


def _load_db_symbols() -> None:
    global Jsonb, close_connection_pool, db_connection, apply_schema
    global find_duplicate_product_candidates, list_candidate_products, merge_products, reject_review_item

    dsn = os.getenv("MAYABU_INTEGRATION_DATABASE_URL")
    if not dsn:
        return
    os.environ["DATABASE_URL"] = dsn

    from psycopg.types.json import Jsonb as _Jsonb

    from mayabu_db.connection import close_connection_pool as _close_connection_pool, db_connection as _db_connection
    from mayabu_db.migrate import apply_schema as _apply_schema
    from mayabu_db.repository import (
        find_duplicate_product_candidates as _find_duplicate_product_candidates,
        list_candidate_products as _list_candidate_products,
        merge_products as _merge_products,
        reject_review_item as _reject_review_item,
    )

    Jsonb = _Jsonb
    close_connection_pool = _close_connection_pool
    db_connection = _db_connection
    apply_schema = _apply_schema
    find_duplicate_product_candidates = _find_duplicate_product_candidates
    list_candidate_products = _list_candidate_products
    merge_products = _merge_products
    reject_review_item = _reject_review_item


def _cleanup(conn, marker: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            select id from product_clusters
            where canonical_title like %s or title_norm like %s
            """,
            (f"%{marker}%", f"%{marker}%"),
        )
        ids = [row["id"] for row in cur.fetchall()]
        if not ids:
            return
        cur.execute("delete from review_queue where source_product_id = any(%s) or candidate_product_id = any(%s)", (ids, ids))
        cur.execute("delete from product_merge_log where primary_product_id = any(%s) or duplicate_product_id = any(%s)", (ids, ids))
        cur.execute("delete from price_alerts where product_id = any(%s)", (ids,))
        cur.execute("delete from price_observations where product_id = any(%s)", (ids,))
        cur.execute("delete from daily_listing_prices where product_id = any(%s)", (ids,))
        cur.execute("delete from daily_product_prices where product_id = any(%s)", (ids,))
        cur.execute("delete from platform_listings where product_id = any(%s)", (ids,))
        cur.execute("delete from product_clusters where id = any(%s)", (ids,))


def _insert_product(conn, marker: str, title: str, *, brand: str = "hp", specs: dict | None = None):
    title_norm = f"{title.lower()} {marker}"
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into product_clusters(category, brand, canonical_title, title_norm, specs, quality_score)
            values ('laptop', %s, %s, %s, %s, 80)
            returning id
            """,
            (brand, f"{title} {marker}", title_norm, Jsonb(specs or {"brand": brand, "ram_gb": 16, "storage_gb": 512})),
        )
        return cur.fetchone()["id"]


def test_trigram_candidate_pool_executes(conn) -> None:
    marker = f"__v451_trgm_{uuid4().hex[:8]}__"
    _cleanup(conn, marker)
    true_id = _insert_product(
        conn,
        marker,
        "HP Victus 15 Intel Core i5 13th Gen Gaming Laptop 16GB 512GB RTX 3050",
        specs={"brand": "hp", "ram_gb": 16, "storage_gb": 512},
    )
    # More recently updated same-brand products must not hide the true title match.
    for i in range(80):
        _insert_product(conn, marker, f"HP unrelated notebook filler {i} 8GB 256GB")

    listing = {
        "title": f"HP Victus 15 i5 13th Gen Laptop 16GB RAM 512GB SSD RTX 3050 {marker}",
        "title_norm": f"hp victus 15 i5 13th gen laptop 16gb ram 512gb ssd rtx 3050 {marker}",
        "category": "laptop",
        "specs": {"brand": "hp", "ram_gb": 16, "storage_gb": 512},
    }
    candidates = list_candidate_products(conn, listing, limit=50)
    ids = [str(row["id"]) for row in candidates]
    assert str(true_id) in ids, ids[:5]
    row = next(row for row in candidates if str(row["id"]) == str(true_id))
    assert any(src in row.get("candidate_sources", []) for src in ["title_trigram", "title_similarity_relaxed"]), row
    _cleanup(conn, marker)


def test_duplicate_finder_respects_rejected_pairs(conn) -> None:
    marker = f"__v451_reject_{uuid4().hex[:8]}__"
    _cleanup(conn, marker)
    p1 = _insert_product(conn, marker, "Lenovo IdeaPad Slim 3 Ryzen 3 8GB 512GB Laptop", brand="lenovo", specs={"brand": "lenovo", "family": "ideapad_slim_3", "ram_gb": 8, "storage_gb": 512})
    p2 = _insert_product(conn, marker, "Lenovo Ideapad Slim 3 AMD Ryzen 3 8 GB 512 GB Notebook", brand="lenovo", specs={"brand": "lenovo", "family": "ideapad_slim_3", "ram_gb": 8, "storage_gb": 512})
    queued = find_duplicate_product_candidates(conn, limit=10, min_score=70)
    assert queued >= 1
    with conn.cursor() as cur:
        cur.execute(
            """
            select id from review_queue
            where review_type='duplicate_product'
              and source_product_id in (%s,%s)
              and candidate_product_id in (%s,%s)
              and status='needs_review'
            limit 1
            """,
            (p1, p2, p1, p2),
        )
        review_id = cur.fetchone()["id"]
    reject_review_item(conn, str(review_id), note="integration test false positive")
    with conn.cursor() as cur:
        cur.execute(
            """
            select count(*) as c from review_queue
            where review_type='duplicate_product'
              and source_product_id in (%s,%s)
              and candidate_product_id in (%s,%s)
            """,
            (p1, p2, p1, p2),
        )
        before = cur.fetchone()["c"]
    find_duplicate_product_candidates(conn, limit=10, min_score=70)
    with conn.cursor() as cur:
        cur.execute(
            """
            select count(*) as c from review_queue
            where review_type='duplicate_product'
              and source_product_id in (%s,%s)
              and candidate_product_id in (%s,%s)
            """,
            (p1, p2, p1, p2),
        )
        after = cur.fetchone()["c"]
    assert after == before, (before, after)
    _cleanup(conn, marker)


def test_merge_resolves_primary_chain_and_moves_alerts(conn) -> None:
    marker = f"__v451_merge_{uuid4().hex[:8]}__"
    _cleanup(conn, marker)
    a = _insert_product(conn, marker, "Asus Vivobook 15 i5 16GB 512GB Laptop", brand="asus", specs={"brand": "asus", "family": "vivobook_15", "ram_gb": 16, "storage_gb": 512})
    b = _insert_product(conn, marker, "ASUS VivoBook 15 Intel i5 16 GB 512 GB Notebook", brand="asus", specs={"brand": "asus", "family": "vivobook_15", "ram_gb": 16, "storage_gb": 512})
    c = _insert_product(conn, marker, "Asus Vivobook 15 16GB 512GB i5 Laptop duplicate", brand="asus", specs={"brand": "asus", "family": "vivobook_15", "ram_gb": 16, "storage_gb": 512})
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into platform_listings(product_id, platform, listing_id, native_id, listing_url, listing_url_hash, title, title_norm, category, specs, current_price, match_status)
            values (%s, 'amazon', %s, %s, 'https://example.com/b', %s, %s, %s, 'laptop', %s, 50000, 'matched')
            """,
            (b, f"amazon:{marker}", marker, marker, f"Listing {marker}", f"listing {marker}", Jsonb({"brand": "asus"})),
        )
        cur.execute("insert into price_alerts(user_ref, product_id, target_price) values ('test-user', %s, 45000)", (b,))
    merge_products(conn, str(a), str(c), source="integration_test")
    result = merge_products(conn, str(c), str(b), source="integration_test_chain")
    assert result["merged"] is True
    assert result["primary_product_id"] == str(a)
    assert result["price_alerts_moved"] == 1
    with conn.cursor() as cur:
        cur.execute("select product_id from platform_listings where listing_id = %s", (f"amazon:{marker}",))
        assert str(cur.fetchone()["product_id"]) == str(a)
        cur.execute("select product_id from price_alerts where user_ref = 'test-user' and product_id = %s", (a,))
        assert cur.fetchone() is not None
    _cleanup(conn, marker)


def main() -> None:
    if not os.getenv("MAYABU_INTEGRATION_DATABASE_URL"):
        print("Skipped v4.5.1 DB integration tests: set MAYABU_INTEGRATION_DATABASE_URL to run them.")
        return
    _load_db_symbols()
    apply_schema()
    with db_connection() as conn:
        test_trigram_candidate_pool_executes(conn)
        test_duplicate_finder_respects_rejected_pairs(conn)
        test_merge_resolves_primary_chain_and_moves_alerts(conn)
    close_connection_pool()
    print("Mayabu v4.5.1 DB integration checks passed")


if __name__ == "__main__":
    main()
