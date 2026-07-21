# Mayabu v3.1 backend build report

## Goal

Convert Mayabu from JSON-first scraper/merger into a PostgreSQL-first backend suitable for a startup-grade laptop price comparison and buying assistant platform.

## Built

### Database foundation

Added `mayabu_db/schema.sql` with industrial source-of-truth tables:

- `product_clusters`
- `platform_listings`
- `price_observations`
- `daily_listing_prices`
- `daily_product_prices`
- `scrape_tasks`
- `scrape_runs`
- `raw_scrape_items`
- `review_queue`
- `anomaly_events`
- `scraper_diagnostics`
- `scheduler_plans`
- `price_alerts`
- `current_product_best_prices` view

### DB migration

Added:

```bash
python -m mayabu_db.migrate
```

### DB-backed ingestion

Added:

- `mayabu_db/ingestion.py`
- `mayabu_db/repository.py`
- `mayabu_db/matching.py`
- `mayabu_db/variant.py`
- `mayabu_db/quality.py`

The ingestion layer now:

1. preserves raw scrape items;
2. normalizes listings;
3. validates quality;
4. matches or creates product clusters;
5. sends uncertain matches to review queue;
6. upserts platform listings;
7. inserts append-only price observations;
8. refreshes daily listing and product price rollups;
9. writes anomalies.

### Worker and scheduler

Added:

- `worker_db.py`
- `run_mayabu_db.py`
- `mayabu_db/tasks.py`
- `mayabu_db/scheduler.py`

The worker claims jobs with PostgreSQL row locking and supports multiple workers later.

### Price history

Added platform-wise daily history:

- listing-level daily OHLC prices in `daily_listing_prices`;
- product-level platform-wise prices in `daily_product_prices`;
- default best-market-price history;
- advanced Amazon/Flipkart/Croma/Reliance Digital lines.

### Error detection and debugging

Added:

- `anomaly_events` table;
- `scraper_diagnostics` table;
- quality flags per listing/observation;
- empty scrape detection;
- fatal/non-fatal validation logic;
- debug artifacts for scraper failures;
- DOM fallback extraction when CSS selectors return zero cards.

### Scraper robustness improvements

Updated:

- `mayabu_scraper_base.py`
- `amazon_scraper.py`
- `flipkart_scraper.py`
- `croma_scraper.py`
- `reliancedigital_scraper.py`

If normal selectors fail, scrapers now try DOM fallback extraction and capture diagnostics instead of silently returning empty results.

### Admin and exports

Added:

- `admin_review.py`
- `export_frontend_json.py`
- `mayabu_db/health.py`

## What is intentionally not built yet

- Platform-specific detail-page refresh scrapers.
- Public frontend API.
- User auth.
- Notification delivery for price alerts.
- AI buying assistant layer.

The schema supports these, but the correct startup order is to first stabilize discovery ingestion and match quality.

## Recommended next execution

```bash
cp .env.example .env
docker compose up -d postgres
python -m mayabu_db.migrate
python run_mayabu_db.py "laptop" --platforms flipkart croma --max-pages 1 --max-products 50
python -m mayabu_db.health
python admin_review.py list --limit 20
```

## Engineering caution

Do not start with 5000+ products per platform immediately. First stabilize data quality with 500-1000 listings total, then scale platform-by-platform.
