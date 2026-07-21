# Mayabu v3.2 Refresh-Price Backend Build Report

This build adds the first production-style refresh-price path for Mayabu. Discovery/search scraping remains separate. Refresh scraping now opens known product-detail URLs from `platform_listings` and updates current price plus append-only price history.

## What changed

### New refresh scraper package

Added `mayabu_refresh/`:

- `models.py`: common `RefreshResult` dataclass.
- `common.py`: shared price parsing, discount calculation, URL validation, stock inference, debug artifact helper.
- `amazon.py`: Amazon product-detail price refresh scraper.
- `flipkart.py`: Flipkart product-detail price refresh scraper with full-title fallback.
- `croma.py`: Croma product-detail price refresh scraper with headed/headless support through caller.
- `reliancedigital.py`: Reliance Digital product-detail price refresh scraper using aria-label price extraction where available.
- `runner.py`: dispatches the right platform refresh scraper.

All refresh scrapers return the same schema:

```json
{
  "title": "...",
  "current_price": 58990,
  "mrp": 74990,
  "effective_price": null,
  "discount_percent": 21.34,
  "currency": "INR",
  "stock_status": "in_stock",
  "stock_text": null,
  "page_status": "success",
  "warnings": [],
  "raw_price_text": "₹58,990",
  "raw_mrp_text": "₹74,990",
  "raw_effective_price_text": null,
  "scraped_at": "..."
}
```

### New direct refresh test command

Added:

```bash
python run_refresh_price.py --platform flipkart --url "https://www.flipkart.com/..." --debug
python run_refresh_price.py --platform croma --url "https://www.croma.com/..." --headed --debug
```

Use `--headed` for Croma if headless extraction fails locally or on a server with Xvfb.

### Database schema extensions

Added idempotent schema extensions:

- `platform_listings.current_effective_price`
- `platform_listings.last_successful_refresh_at`
- `platform_listings.last_refresh_error`
- `platform_listings.refresh_priority`
- `platform_listings.refresh_interval_minutes`
- `price_observations.effective_price`
- `price_observations.raw_price_text`
- `price_observations.raw_mrp_text`
- `price_observations.validation_status`
- refresh-due index on `platform_listings`

Run migration again safely:

```bash
python -m mayabu_db.migrate
```

### Refresh ingestion

Added `mayabu_db/refresh_ingestion.py`.

It:

1. Resolves the target `platform_listings` row from the refresh task.
2. Validates URL domain and refresh result.
3. Prevents bad data from overwriting good data.
4. Updates `platform_listings` current price fields only on valid refresh.
5. Appends `price_observations`.
6. Refreshes `daily_listing_prices`.
7. Refreshes `daily_product_prices` when listing is attached to a product.
8. Logs anomalies for missing price, invalid platform URL, suspicious drops, MRP below price, blocked/captcha pages, and impossible laptop prices.

### Worker now supports refresh_listing

`worker_db.py` now supports:

- `discovery`
- `refresh_listing`

Refresh flow:

```txt
scrape_tasks.refresh_listing
  -> worker resolves platform_listings row
  -> opens known product-detail URL
  -> extracts latest price/MRP/status
  -> validates result
  -> updates platform_listings
  -> appends price_observations
  -> refreshes daily price history
```

### Scheduler can materialize due refresh tasks

Added scheduler command:

```bash
python -m mayabu_db.scheduler materialize-refresh-due --limit 100
python -m mayabu_db.scheduler materialize-refresh-due --platforms flipkart croma --limit 50
```

This creates `refresh_listing` tasks for listings whose `last_successful_refresh_at` is missing or older than `refresh_interval_minutes`. It avoids duplicate pending/running refresh tasks for the same listing.

### Croma handling

Croma is supported, but still marked as the platform most likely to need headed/debug mode.

Use:

```bash
MAYABU_CROMA_HEADLESS=false python worker_db.py --once
```

or for direct debugging:

```bash
python run_refresh_price.py --platform croma --url "..." --headed --debug
```

## How to run the new refresh path

1. Apply migration:

```bash
python -m mayabu_db.migrate
```

2. Make sure `platform_listings` has known product URLs from discovery.

3. Create due refresh tasks:

```bash
python -m mayabu_db.scheduler materialize-refresh-due --limit 20
```

4. Run one worker task:

```bash
python worker_db.py --once
```

5. Check updated data:

```sql
select platform, title, current_price, current_mrp, current_discount_pct, last_successful_refresh_at
from platform_listings
order by last_successful_refresh_at desc nulls last
limit 20;

select platform, price, mrp, discount_pct, observed_at
from price_observations
order by observed_at desc
limit 20;
```

## Validation protections

The refresh ingestion layer will not update current price when:

- URL domain does not match the expected platform.
- Refresh result has no price.
- Laptop price is below ₹5,000.
- Price drops by more than 70% compared with last known price.
- Page appears blocked or captcha protected.

In those cases it records `anomaly_events`, keeps the old price, and marks the task failed or retryable.

## What was tested here

- Python syntax compilation for the new package and updated worker/scheduler.
- Static integration of worker, scheduler, schema, and refresh modules.

Live ecommerce scraping and PostgreSQL migration were not run in this environment. Run the migration and small refresh tasks locally before scaling.

## Known limitations

- Croma headless behavior still needs your local/server verification.
- Amazon and Flipkart selectors may need more fallbacks after testing multiple product URLs.
- Refresh path assumes discovery has already populated `platform_listings` with valid URLs.
- No scrape budget table enforcement yet. The scheduler has due-refresh dedupe, but budget enforcement should be added next.

## Next recommended build step

1. Run refresh path locally with 5 to 10 known listings per platform.
2. Inspect `anomaly_events` and debug artifacts.
3. Add platform-specific selector fallbacks based on failures.
4. Add scrape budget enforcement and platform health throttling.
5. Add Search API after refresh pipeline is stable.
