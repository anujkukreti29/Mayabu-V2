# Staging retail catalog (local / disposable PostgreSQL)

Use this only against **local**, **test**, or **disposable staging** databases.
Never point these scripts at production.

## PostgreSQL requirement

Public search and catalog qualification require PostgreSQL.

Local Docker Compose (repo default):

```text
postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu_test
```

Bootstrap:

```powershell
$env:MAYABU_TEST_DATABASE_URL = "postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu_test"
$env:DATABASE_URL = $env:MAYABU_TEST_DATABASE_URL
$env:PYTHONPATH = (Get-Location).Path
python scripts/bootstrap_test_db.py
```

`bootstrap_test_db.py` creates `mayabu_test` if missing, applies `mayabu_db/schema.sql`
twice (idempotency check), and verifies a marker row survives.

Integration test:

```powershell
$env:MAYABU_TEST_DATABASE_URL = "postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu_test"
python -m pytest -q tests/test_v51_postgres_integration.py
```

## Trusted platform × category combinations (staging seed)

| Category | Platforms |
|----------|-----------|
| laptop | amazon, flipkart, croma, reliancedigital |
| smartphone | flipkart, croma, reliancedigital, amazon |
| television | amazon, croma, reliancedigital |
| refrigerator | croma, reliancedigital |
| washing_machine | croma, reliancedigital |
| tws | amazon, croma |
| headphones | croma |

Do **not** rely on Vijay Sales, Poorvika, JioMart, or Bajaj Electronics for
staging correctness.

## Bounded seed

```powershell
python scripts/seed_retail_catalog.py --dry-run
python scripts/seed_retail_catalog.py --max-products 12 --max-pages 1 --queries-per-category 2
python scripts/seed_retail_catalog.py --categories smartphone television --max-products 10
python scripts/seed_retail_catalog.py --report-only
```

Safety:

- refuses databases named `*prod*` / `production`
- refuses non-test/staging DB names unless `--allow-dev-db`
- caps `--max-products` ≤ 40 and `--max-pages` ≤ 2
- uses existing discovery + ingestion (quality gates stay on)
- upserts listings on re-run (interrupt-safe; no one giant transaction)

Repair unknown listings after category-detection fixes:

```powershell
python scripts/repair_unknown_listings.py
```

## Search qualification

```powershell
python scripts/qualify_search.py
```

Checks category queries, exact model codes from the live catalog, accessory
rejection, pagination/sort smoke, and `facet_scope=query`.

## Facet semantics

`facet_scope` is **`query`**: counts come from a bounded matching candidate set
(cap 200), **not** the current page of 20 results, and **not** the full catalog.

Frontend must not present these as global catalog-wide totals.

## Public category readiness (evidence-based)

Classify after a real catalog seed + `qualify_search.py`, not from parser unit
tests alone. See the latest staging qualification report in the task notes.

Camera remains **experimental** and is not public-searchable via `category=`.

## Insufficient-identity cleanup

Brand-only / brand+generic titles are rejected at the quality gate with reason
`insufficient_identity`. Operators can inspect staging rows:

```powershell
python scripts/repair_insufficient_identity.py --inspect
python scripts/repair_insufficient_identity.py --remove-search-docs --limit 100
python scripts/repair_insufficient_identity.py --mark-needs-review --limit 100
```

Raw listings are retained; only public search visibility is changed.
