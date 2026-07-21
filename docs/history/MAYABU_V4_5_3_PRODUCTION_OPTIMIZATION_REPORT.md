# Mayabu v4.5.3 Production Optimization Report

## Goal
This release focuses on production safety, fast retrieval, bounded resource usage, code reuse, and edge-case handling without changing the existing frontend contract.

## Key Improvements

### 1. Fast Retrieval Search Index
Added a read-optimized PostgreSQL materialized view: `product_search_index`.

It pre-joins and precomputes:
- product title and normalized title
- brand/category/family/model codes
- CPU/RAM/storage/screen extracted fields
- best price and best platform
- platform count and offer count
- image URL
- full-text `search_vector`
- trigram-ready `search_text`

New indexes:
- GIN full-text index for fast search
- GIN trigram index for fuzzy search
- category/brand/family indexes
- model-code trigram index
- price/platform-count indexes

### 2. Better Search Ranking
Search now ranks products by:
1. exact model/SKU match
2. same family as similar variant
3. spec match such as CPU/RAM/storage
4. text/full-text/fuzzy relevance
5. platform count and freshness

API still returns `results`, but now also includes:
- `sections.exact_matches`
- `sections.similar_variants`
- `sections.related_products`
- match-group counts

This keeps old frontend compatibility while enabling a better frontend later.

### 3. Search Index Refresh Tools
Added reusable search-index maintenance helpers:
- `mayabu/search/index_manager.py`
- `refresh_product_search_index()`
- `get_search_index_stats()`

New CLI commands:
```cmd
python admin_review.py refresh-search-index
python admin_review.py db-stats
python admin_review.py explain-matching "ASUS Vivobook 14 Ultra 5 225H"
```

### 4. Production-Safe Scraper CLI
`run_mayabu_db.py` now includes:
- bounded platform concurrency
- DB retry around run creation, ingestion, and auto-merge
- safe max-pages/max-products validation
- automatic search-index refresh after scraping
- structured status output

Recommended command:
```cmd
python run_mayabu_db.py "laptop" --platforms flipkart amazon croma reliancedigital --max-pages 20 --max-products 500 --platform-concurrency 2
```

### 5. Database Space/Time Hardening
Added hot-path indexes for:
- matched listings by product/platform/price
- platform URL hash lookup
- price observation lookup
- valid product price history
- recent scraper failures
- open anomaly events

The URL hash index is intentionally non-unique to avoid migration failure on legacy duplicate data. After cleanup, it can be promoted to a unique index.

### 6. Edge-Case Focus
The new code handles:
- missing search index by falling back to old live-table search
- stale/missing Redis cache
- DB pool timeouts with retries in CLI paths
- broad vs exact laptop queries
- exact match vs similar variant separation
- overly large scrape commands that could burst production resources
- existing old databases without immediate hard failure

## Required Upgrade Steps
From the backend folder:

```cmd
.venv\Scripts\activate.bat
set DATABASE_URL=postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu
python -m mayabu_db.migrate
python admin_review.py refresh-search-index
python admin_review.py db-stats
```

Then restart API:
```cmd
python run_api.py
```

## New Useful Commands

Explain why search results are ranking/appearing:
```cmd
python admin_review.py explain-matching "ASUS Vivobook 14 Ultra 5 225H"
```

Refresh fast search index manually:
```cmd
python admin_review.py refresh-search-index
```

Check indexed product count:
```cmd
python admin_review.py db-stats
```

Safe heavy scrape:
```cmd
python run_mayabu_db.py "laptop" --platforms flipkart amazon croma reliancedigital --max-pages 20 --max-products 500 --platform-concurrency 2
```

One-platform safer scrape:
```cmd
python run_mayabu_db.py "Apple MacBook Air M2 8GB 256GB" --platforms flipkart --max-pages 5 --max-products 100 --platform-concurrency 1
```

## Remaining Recommended Next Steps
- Add direct product URL ingestion for exact listing capture.
- Add detail-page enrichment for title/specs/image when search discovery misses products.
- Add background job queue instead of long-running scrape in one CLI process.
- Add historical raw price retention policy and archival.
- Add frontend display for `sections.exact_matches` and `sections.similar_variants`.
