# Listing URL-hash duplicate cleanup plan

PostgreSQL `platform_listings` identity is `(platform, listing_url_hash)`. A unique constraint is **not** applied because legacy duplicate rows exist. The non-unique index `idx_platform_listings_platform_urlhash_active` remains.

## Audit

```bash
python scripts/audit_listing_url_duplicates.py
python scripts/audit_listing_url_duplicates.py --json
```

The script does **not** delete or merge rows.

## Survivor rules (manual / future maintenance)

For each duplicate group:

1. Prefer the single `match_status=matched` row when exactly one exists and product_ids agree.
2. If two matched rows or two product_ids exist: **defer**. Ambiguous public offers must not be collapsed automatically.
3. Prefer the row with the latest successful observation / `last_successful_refresh_at`.
4. Check `price_observations`, `scrape_tasks.metadata`, and `daily_listing_prices` FKs before any delete.
5. Archive losers as `match_status=duplicate` with `specs.duplicate_of` rather than hard-deleting when references exist.

Do not promote the URL-hash index to UNIQUE until deferred groups are empty or explicitly waived.

## Local catalog snapshot

On the 7-listing local catalog used for runtime proof (Amazon laptops only after synthetic leftover rows were removed), `scripts/audit_listing_url_duplicates.py` reported **0 duplicate groups**. That does not prove other databases are unique. Keep the non-unique index until a full-catalog audit is empty or explicitly waived.
