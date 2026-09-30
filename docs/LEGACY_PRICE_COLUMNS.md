# Legacy Four-Platform Daily Price Columns

## Columns

`daily_product_prices` still materializes:

- `amazon_price`
- `flipkart_price`
- `croma_price`
- `reliancedigital_price`

alongside normalized `best_price` / `best_platform` / `platform_count`.

## Source of truth

`daily_product_platform_prices` (platform-dynamic) is the operational source of truth for multi-retailer history. Public best-price uses `current_product_best_prices` + `mayabu_listing_is_public_offer`.

## Current readers/writers

| Location | Role | Classification |
|----------|------|----------------|
| `mayabu_db/repository.py` daily rollup | Writes legacy columns from platform mins | **required compatibility** |
| `mayabu/search/search_repository.py` `get_price_history` | Selects legacy columns; prefers `daily_product_platform_prices` when present; falls back to legacy on error | **compatibility + fallback** |
| `export_frontend_json.py` | Export selects legacy columns | **migration candidate** |

## Do not remove yet

Frontend/history consumers may still expect the four named fields in older payloads. Removing columns requires a coordinated API/version bump.

## Safe near-term path

1. Keep writing legacy columns during rollup (cheap).
2. Prefer `platform_prices` map from `daily_product_platform_prices` in API responses (already).
3. Stop *new* internal feature code from reading the four columns.
4. Future task: deprecate response fields → remove SQL columns after one release of dual-read.

No destructive migration in this task.
