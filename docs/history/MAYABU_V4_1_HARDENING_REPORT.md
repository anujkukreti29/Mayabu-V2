# Mayabu v4.1 Backend Hardening Report

This package is a focused hardening pass over the uploaded Mayabu v4 backend architecture. It keeps the modular monolith design and DB-backed queue, then fixes the correctness and reliability issues that matter before public MVP testing.

## What was fixed

### Data correctness

- Unified `observation_hash()` across discovery and refresh ingestion so the same listing/price/timestamp no longer gets different hashes depending on ingestion path.
- Added currency handling to listings and observations, with a currency-aware `current_product_best_prices` view that only compares INR prices.
- Hardened RAM and storage extraction:
  - prevents `512GB SSD` from becoming RAM
  - supports `2TB` and `1.5TB` storage
  - normalizes numeric specs before matching
- Added a guard against false product-family extraction from screen/RAM text such as `IdeaPad 16GB` and `Pavilion 15.6 inch`.

### Queue and worker reliability

- Added `requeue_stuck_tasks()` so crashed workers do not leave tasks permanently locked as `running`.
- Added exponential retry backoff instead of a flat 10-minute retry delay.
- Added `worker_heartbeats` schema and worker heartbeat writes.
- Moved scrape-budget consumption from task materialization to worker claim/execution time.
- Added maintenance CLI:
  - `python -m mayabu.scheduler.maintenance reap-stuck-tasks`
  - `python -m mayabu.scheduler.maintenance cleanup-raw`
  - `python -m mayabu.scheduler.maintenance refresh-demand-counters`
  - `python -m mayabu.scheduler.maintenance run-all`
- Replaced the old duplicate refresh materializer in `mayabu_db/scheduler.py` with a compatibility wrapper around the v4 materializer.

### Ingestion safety

- Added per-record transaction savepoints in `ingest_records()` so one bad raw listing cannot roll back an entire scrape batch.
- Added raw scrape cleanup support and an index on `raw_scrape_items.scraped_at`.

### Demand signal accuracy

- Fixed demand counters so `query_count_24h`, `query_count_7d`, and `unique_user_count_24h` are recalculated from `search_queries` instead of incrementing forever.
- Added `refresh_demand_counters()` for hourly or daily maintenance.

### Scraper reliability

- Flipkart discovery now targets product containers first and extracts links from inside the card, instead of treating anchors as cards.
- Reliance Digital now honors detected page count and caps the loop to the actual available pages.
- Croma now documents and treats `max_pages` as a backward-compatible View More click budget.
- `human_scroll()` now returns success/failure and re-raises browser/session-closed errors instead of silently swallowing dead-page failures.
- `polite_sleep()` now uses bounded variable pauses instead of a perfectly uniform delay.
- DOM fallback now cleans raw price text before passing it onward.

### API hardening

- Public search now supports `offset` pagination with `has_more`.
- Public search now has a small in-process rate limiter for MVP/local deployment.
- Public product/search/offer responses now use whitelisted serializers rather than returning raw DB rows.
- Product cache keys are now product-id-addressable for targeted invalidation.
- Refresh and discovery ingestion now perform best-effort cache invalidation after price observations.
- Admin token comparison now always uses constant-time comparison for provided vs expected token.

### Schema and indexes

- Added worker heartbeat table and heartbeat index.
- Added raw scrape retention index.
- Added stuck-task lookup index.
- Added search query window index for demand counter recalculation.
- Added `search_tsv` generated column and GIN index for future full-text search improvement.
- Rebuilt `current_product_best_prices` as currency-aware.

## What was intentionally not changed

- No proxy pool or stealth-browser bypass logic was added. The scraper base still follows the safer Mayabu principle: controlled, low-frequency, observable scraping rather than aggressive evasion.
- No migration to Graphile Worker/Celery was done. PostgreSQL `FOR UPDATE SKIP LOCKED` remains appropriate for the current MVP once the stuck-task reaper, backoff, and heartbeat are present.
- No full module-tree consolidation was done. That is a larger refactor and should happen after the DB-backed refresh flow is verified locally.
- No Alembic migration conversion was done yet. First verify this schema locally, then convert the stable schema into versioned Alembic migrations.
- No price-alert delivery system was added. The schema exists, but alert delivery should come after stable refresh, price history, and public API behavior are verified.

## Validation performed in this environment

- Python compile check passed with `python -m compileall -q .`
- Existing smoke backend test passed with `python tests/smoke_backend.py`
- Spec extraction was manually checked for:
  - `16GB RAM 512GB SSD`
  - `32GB SSD`
  - `32GB RAM 2TB SSD`
  - `16GB LPDDR5X 1.5TB SSD`
  - `Pavilion 15.6 inch`

## Not validated in this environment

The sandbox does not have a live PostgreSQL/Redis/Playwright runtime with Mayabu dependencies installed, so these still need local validation:

1. `python -m mayabu_db.migrate`
2. one `refresh_listing` task end to end
3. `worker_db.py --once`
4. public API health/search/products routes against a populated DB
5. real refresh scraper execution for Amazon, Flipkart, Croma, and Reliance Digital

## Recommended local validation order

```bash
cd mayabu_v4_1_hardened_backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
docker compose up -d postgres redis
python -m mayabu_db.migrate
python tests/smoke_backend.py
python -m mayabu.scheduler.maintenance run-all
python run_api.py
```

Then test one refresh flow:

```bash
python run_refresh_price.py --platform reliance --url "<known_reliance_laptop_url>" --debug
python run_refresh_price.py --platform flipkart --url "<known_flipkart_laptop_url>" --debug
python run_refresh_price.py --platform amazon --url "<known_amazon_laptop_url>" --debug
python run_refresh_price.py --platform croma --url "<known_croma_laptop_url>" --headed --debug
```

After that, insert or materialize a real `refresh_listing` task and run:

```bash
python -m mayabu.scheduler.task_materializer refresh --limit 5
python worker_db.py --once
```

Verify:

- `platform_listings.current_price`
- `price_observations`
- `daily_listing_prices`
- `daily_product_prices`
- `scraper_diagnostics`
- `anomaly_events`
- `worker_heartbeats`
