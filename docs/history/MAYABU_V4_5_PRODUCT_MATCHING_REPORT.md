# Mayabu v4.5 Product Matching + Efficiency Build Report

Generated: 2026-07-05

## Purpose

v4.5 implements the product-matching audit recommendations on top of the v4.4 audit-enhanced backend. The goal is to make Mayabu behave more like a real buying assistant: one clean product cluster with platform offers underneath it, instead of duplicate cards for the same physical product.

## What changed

### 1. Candidate lookup no longer uses waterfall blocking

File: `mayabu_db/repository.py`

`list_candidate_products()` was redesigned. v4.4 stopped at the first non-empty candidate tier. v4.5 now builds a unioned candidate pool from:

- exact `variant_key`
- model-code overlap
- brand + family
- `pg_trgm` product-title similarity
- `pg_trgm` matched-listing-title similarity
- small recency fallback only as a final bounded safety net

This directly fixes the audit finding that the true product match could exist but never be considered.

### 2. Trigram similarity is now used for matching

File: `mayabu_db/repository.py`

v4.5 uses PostgreSQL `similarity()` and `%` against `product_clusters.title_norm` and `platform_listings.title_norm`. The existing trigram indexes are now useful for product matching, not only search.

### 3. No-model-code guardrail is safer and less duplicate-prone

File: `mayabu_catalog.py`

The old guardrail capped no-model-code matches below review too often. v4.5 still prevents automatic unsafe merges, but if a pair has strong title similarity and at least two exact specs, it now enters the manual-review band instead of becoming a new duplicate cluster.

### 4. Product merge operation added

File: `mayabu_db/repository.py`

Added `merge_products(primary_product_id, duplicate_product_id)`.

It:

- reassigns `platform_listings.product_id`
- reassigns `price_observations.product_id`
- reassigns `daily_listing_prices.product_id`
- rebuilds affected `daily_product_prices`
- merges specs conservatively
- keeps the more complete title
- marks the duplicate cluster as `status='duplicate'`
- writes to `product_merge_log`
- invalidates relevant product/search caches

### 5. Duplicate candidate finder added

Files:

- `mayabu_db/repository.py`
- `mayabu/scheduler/maintenance.py`
- `run_maintenance_scheduler.py`

Added `find_duplicate_product_candidates()`. It finds likely duplicate active product clusters using same category, same brand, trigram title similarity, and existing scoring logic. It queues product-level review items into `review_queue`.

The maintenance scheduler now runs this nightly.

### 6. Review queue now supports product-vs-product reviews

Files:

- `mayabu_db/schema.sql`
- `mayabu/monitoring/reports.py`
- `mayabu/api/admin_routes.py`
- `admin_review.py`
- `mayabu/admin/review_cli.py`

Schema additions:

- `review_queue.review_type`
- `review_queue.source_product_id`
- duplicate-product review index
- `product_merge_log`

Admin API additions:

- `GET /api/admin/review-queue?review_type=duplicate_product`
- `POST /api/admin/review-queue/{review_id}/approve`
- `POST /api/admin/review-queue/{review_id}/reject`
- `POST /api/admin/products/merge`
- `POST /api/admin/products/find-duplicates`

CLI additions:

- `python admin_review.py find-duplicates`
- `python admin_review.py list --type duplicate_product`
- `python admin_review.py approve <review_id>`
- `python admin_review.py reject <review_id>`
- `python admin_review.py merge-products <primary_id> <duplicate_id>`

### 7. Search cache invalidation is less destructive

Files:

- `mayabu_db/repository.py`
- `mayabu_db/refresh_ingestion.py`
- `mayabu/api/search_routes.py`

v4.4 invalidated the whole `search:` namespace even on unchanged price ticks. v4.5:

- skips invalidation on `event_type='unchanged'`
- uses category-scoped search keys like `search:laptop:<hash>`
- invalidates only the affected category namespace when category is known
- still invalidates product detail and price-history cache for affected product IDs

### 8. Search analytics moved off the response path

File: `mayabu/api/search_routes.py`

`log_search_query()` and `upsert_demand_cluster()` now run through FastAPI `BackgroundTasks` so uncached search responses do not wait for analytics writes.

### 9. Matching sanity checks added

File: `tests/matching_eval_v45.py`

This is a small starter eval, not the final 200-500 pair labeled dataset. It checks:

- strong no-model-code same-product candidates enter review band
- similar but conflicting storage variants still reject

## Verification run during build

```cmd
python -m compileall .
python tests\smoke_backend.py
python tests\smoke_v43_scrapers.py
python tests\matching_eval_v45.py
```

Result:

```text
Mayabu backend smoke test passed
Mayabu v4.3 scraper contract smoke test passed
Mayabu v4.5 matching sanity checks passed
```

## What still remains after v4.5

v4.5 fixes the root matching/duplicate-cleanup layer. Still recommended next:

1. Build a real labeled matching eval set with 200-500 pairs.
2. Add category-specific extractors/scorers for mobiles, tablets, cameras, earbuds, smartwatches, TVs.
3. Add frontend product cards that clearly show merged platform offers.
4. Add seller trust and product detail enrichment later.
5. Add AI embeddings only for uncertain cases after deterministic matching is measured.

## Recommended local verification

```cmd
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
docker compose up -d
python -m mayabu_db.migrate
python tests\smoke_backend.py
python tests\smoke_v43_scrapers.py
python tests\matching_eval_v45.py
python run_mayabu_db.py "laptop" --platforms flipkart amazon reliancedigital croma --max-pages 1 --max-products 10
python -m mayabu_db.health
python admin_review.py find-duplicates --limit 50
python admin_review.py list --type duplicate_product
python run_api.py
```

API checks:

```cmd
curl "http://127.0.0.1:8000/api/search?q=laptop"
curl -X POST "http://127.0.0.1:8000/api/admin/products/find-duplicates?limit=50" -H "X-Mayabu-Admin-Token: YOUR_ADMIN_TOKEN"
```
