# Mayabu v4.5.1 Product Matching Hardening Report

## Purpose

Mayabu v4.5 added the right product-matching design, but the independent verification audit found that the core trigram SQL was not actually executing because PostgreSQL's `pg_trgm` `%` operator was not escaped for psycopg parameter substitution. This v4.5.1 patch fixes that release blocker and hardens the merge/review edge cases found in live-DB testing.

## Fixed issues

### 1. Critical trigram SQL escaping bug

Changed psycopg SQL strings from:

```sql
coalesce(title_norm, '') % %s
```

to:

```sql
coalesce(title_norm, '') %% %s
```

Applied to:

- product-cluster title trigram candidate query
- matched-listing title trigram candidate query
- duplicate-product self-join finder query

### 2. No more silent trigram failure

`list_candidate_products()` now logs `trigram_candidate_query_failed` with category, brand, and a short error string instead of swallowing all exceptions silently. Ingestion still continues, but the operator/query failure becomes visible.

### 3. Duplicate finder no longer crashes scheduler

`find_duplicate_product_candidates()` now wraps the optional trigram query, logs `duplicate_product_finder_query_failed`, and returns `0` queued items instead of crashing the nightly maintenance job.

### 4. Merge chains are resolved safely

`merge_products()` now resolves a requested primary product through `specs.duplicate_of` until it reaches an active root product. This prevents data from being moved onto a hidden duplicate cluster when an admin merges into an already-merged product.

### 5. Price alerts move during product merge

`merge_products()` now runs:

```sql
update price_alerts set product_id = primary where product_id = duplicate
```

This prevents user alerts from silently pointing at hidden duplicate products.

### 6. Rejected duplicate suggestions stay rejected

The duplicate finder now excludes prior `needs_review`, `rejected`, and `ignored` duplicate-product pairs in either product order. This prevents the same false positive from being re-suggested every night.

### 7. Exact candidates are pinned ahead of fuzzy candidates

Candidate-pool truncation now prioritizes exact `variant_key`, model-code, and brand-family candidates before trigram/fallback candidates. This removes a low-probability edge case where a strong exact match could be sorted behind many fuzzy candidates.

### 8. Integration test added

Added:

```text
tests/integration_v451_matching_db.py
```

It exercises the actual SQL and DB paths for:

- trigram candidate recall
- duplicate finder query
- rejected-pair suppression
- merge chain resolution
- price-alert reassignment

It is opt-in and runs only when `MAYABU_INTEGRATION_DATABASE_URL` is set.

## Verification run in this environment

Passed:

```cmd
python -m compileall .
python tests\smoke_backend.py
python tests\smoke_v43_scrapers.py
python tests\matching_eval_v45.py
python tests\integration_v451_matching_db.py
```

The DB integration test was also checked for clean skip behavior when no integration database URL is available.

## Local DB verification to run after extraction

```cmd
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
docker compose up -d
python -m mayabu_db.migrate
set MAYABU_INTEGRATION_DATABASE_URL=postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu
python tests\integration_v451_matching_db.py
python admin_review.py find-duplicates --limit 50
python admin_review.py list --type duplicate_product
```

## Status

Mayabu v4.5.1 should replace v4.5 as the working product-matching baseline. It preserves the v4.5 matching architecture but fixes the critical SQL execution blocker and hardens the highest-risk merge/review edge cases.
