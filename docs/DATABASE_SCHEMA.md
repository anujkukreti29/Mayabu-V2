# Mayabu database schema

PostgreSQL is the source of truth. JSON files are only allowed for import, export, and debugging. The schema is idempotent and is applied with:

```bash
python -m mayabu_db.migrate
```

## Core entities

- `product_clusters`: real laptop products or variants.
- `platform_listings`: ecommerce listings from Amazon, Flipkart, Croma, and Reliance Digital.
- `price_observations`: append-only price events.
- `daily_listing_prices`: listing-level daily OHLC price summary.
- `daily_product_prices`: product-level platform-wise daily price summary.
- `scrape_tasks`: controlled background queue.
- `scrape_runs`: execution status for every task.
- `search_queries`: user searches stored as demand signals.
- `query_demand_clusters`: deduplicated demand signals that may become controlled discovery tasks.
- `scrape_budget`: daily platform/task budgets.
- `platform_health`: platform pause/degraded/blocked state.

## Integrity rules

- Never overwrite current price with missing or invalid data.
- Every valid refresh appends `price_observations`.
- Product matching must remain conservative.
- Suspicious data writes to `anomaly_events`.
- API reads should use indexed tables and snapshots, not live scraping.
