# Mayabu v4 full backend architecture build report

This build expands Mayabu from the v3.2 refresh-price backend into a fuller backend architecture aligned with the master Mayabu specification.

## Added

- FastAPI application under `mayabu/api/`.
- Public search endpoint: `GET /api/search?q=`.
- Product endpoints: product detail, offers, and price history.
- Admin endpoints protected by `X-Mayabu-Admin-Token`.
- Query parser and laptop-focused classifier.
- Search repository reading from PostgreSQL and `current_product_best_prices`.
- Search query logging and demand cluster upsert.
- Redis-capable cache abstraction with optional fallback.
- Task materializer for refresh and demand-driven discovery.
- Platform health policy and scrape budget policy.
- Monitoring and admin CLI helpers.
- Database schema extensions for `search_queries`, `query_demand_clusters`, `scrape_budget`, `platform_health`, search indexes, task type broadening, and product/listing metadata.
- Docs for schema, scraper design, security, deployment, and roadmap.

## Preserved

- Existing v3.2 refresh scrapers.
- DB-backed `refresh_listing` worker path.
- Append-only price observations.
- Daily listing/product price snapshots.
- Anomaly logging and validation behavior.

## Important limits

- Live ecommerce scraping was not run in this environment.
- PostgreSQL migration was syntax-checked by Python compile only, not applied against a live DB here.
- Redis is optional and disabled by default with `MAYABU_ENABLE_REDIS_CACHE=false`.
- Semantic search is still planned, not fully implemented.
- Frontend is intentionally not included.

## Run sequence

```bash
docker compose up -d postgres redis
python -m mayabu_db.migrate
python run_api.py
python -m mayabu.scheduler.task_materializer refresh --limit 10
python worker_db.py --once
```

## Admin examples

```bash
python -m mayabu.admin.task_cli pending --limit 20
python -m mayabu.admin.data_quality_cli --status open --limit 20
python -m mayabu.admin.review_cli --limit 20
python -m mayabu.admin.platform_cli pause croma
python -m mayabu.admin.platform_cli resume croma
```
