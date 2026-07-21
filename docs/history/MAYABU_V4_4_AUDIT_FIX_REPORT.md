# Mayabu v4.4 Audit Fix Report

This package starts from the verified v4.3 working backend and applies the highest-impact audit recommendations without rebuilding the architecture from scratch.

## Fixed from the v4.3 audit

### P1: PostgreSQL connection pooling

Files changed:

- `mayabu_db/connection.py`
- `mayabu/db/connection.py`
- `requirements.txt`
- `.env.example`
- `mayabu/api/main.py`

What changed:

- Replaced per-request `psycopg.connect()` calls with a process-wide `psycopg_pool.ConnectionPool`.
- Kept the old `with db_connection() as conn:` API so existing API, worker, scheduler, scraper ingestion, and admin code continues to work.
- Added pool controls:
  - `MAYABU_DB_POOL_MIN_SIZE=1`
  - `MAYABU_DB_POOL_MAX_SIZE=10`
- Added graceful API shutdown pool close.

Expected impact:

- Lower API latency.
- Lower PostgreSQL connection churn.
- Better readiness for frontend traffic.

### P1: Wire `search_tsv` full-text search

Files changed:

- `mayabu/search/search_repository.py`

What changed:

- `search_products()` now uses `product_clusters.search_tsv @@ plainto_tsquery('english', query)`.
- Search ranking now uses `ts_rank_cd()` as a primary SQL relevance signal.
- Existing `ilike`/trigram fallback remains for noisy or partial queries.
- Generic `q=laptop` category fallback still works.

Expected impact:

- Better search relevance.
- Uses the GIN index that was already present in the schema.
- Faster text matching as the product catalogue grows.

### P2: Cap deep pagination over-fetch

Files changed:

- `mayabu/search/search_repository.py`
- `mayabu/api/search_routes.py`

What changed:

- Search fetch over-read is capped to `MAX_SEARCH_FETCH_LIMIT = 400`.
- API `offset` is capped to `400` to avoid expensive deep offset pagination.

Expected impact:

- Lower DB CPU on deep pages.
- Prevents expensive `offset=5000` style calls.

### P2: Startup settings validation

Files changed:

- `mayabu/core/config.py`
- `mayabu_db/config.py`

What changed:

- Added explicit validation for `DATABASE_URL` format.
- Added validation for API port, rate-limit value, and DB pool sizes.
- In production, `MAYABU_ADMIN_TOKEN` is required.
- Settings are cached with `lru_cache()` to avoid repeated parsing.

Expected impact:

- Cleaner startup failures.
- Easier debugging when `.env` is wrong or missing.

### P2: Maintenance scheduler

Files changed:

- `run_maintenance_scheduler.py`
- `docker-compose.yml`
- `requirements.txt`

What changed:

- Added APScheduler-based maintenance daemon.
- Added Docker Compose `maintenance` profile.
- Scheduled jobs:
  - Reap stuck tasks every 15 minutes.
  - Refresh demand counters every hour.
  - Cleanup raw scrape rows nightly.
  - Rebuild daily price rollups nightly.

Run locally:

```bash
python run_maintenance_scheduler.py
```

Run with Docker Compose:

```bash
docker compose --profile maintenance up -d maintenance
```

### P3: Optional scraper proxy support

Files changed:

- `mayabu_scraper_base.py`
- `.env.example`

What changed:

- `BrowserSession` now accepts `proxy: str | None`.
- Also reads `MAYABU_SCRAPER_PROXY` from environment.

Example:

```env
MAYABU_SCRAPER_PROXY=http://user:pass@host:port
```

### P3: Remove lightweight N+1 product existence checks

Files changed:

- `mayabu/search/search_repository.py`
- `mayabu/api/product_routes.py`

What changed:

- Added `product_exists(product_id)`.
- `/offers` and `/price-history` now use the lightweight existence check instead of loading the full product row.

## Verification performed

Commands run successfully in this package:

```bash
python -m compileall .
python tests/smoke_backend.py
python tests/smoke_v43_scrapers.py
```

## Still intentionally deferred

These remain future work and were not forced into this patch to avoid destabilizing the verified backend:

- CategoryParser plugin architecture for mobiles/TVs.
- Full `mayabu_db/` to `mayabu/db/` consolidation.
- Seller name extraction and seller trust scoring.
- Price alert delivery infrastructure.
- Full DB integration test suite with a test PostgreSQL fixture.
- Croma common utility extraction.

## Recommended next step

Run these locally after replacing your backend folder:

```cmd
docker compose up -d
python -m pip install -r requirements.txt
python -m mayabu_db.migrate
python tests\smoke_backend.py
python tests\smoke_v43_scrapers.py
python run_mayabu_db.py "laptop" --platforms flipkart amazon reliancedigital croma --max-pages 1 --max-products 10
python -m mayabu_db.health
python run_api.py
```

Then in a second terminal:

```cmd
curl "http://127.0.0.1:8000/api/search?q=laptop"
```
