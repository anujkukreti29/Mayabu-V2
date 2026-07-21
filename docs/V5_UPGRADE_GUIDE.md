# Upgrade from Mayabu v4.5.x or v5.0 to v5.1

## Safe upgrade order

1. Back up PostgreSQL.
2. Replace/add the v5.1 files.
3. Keep the existing PostgreSQL volume.
4. Install updated dependencies.
5. Apply the idempotent schema migration.
6. Build variant links and search documents.
7. Verify the database.
8. Start API, worker, and frontend.

Windows CMD:

```cmd
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python -m playwright install chromium
set DATABASE_URL=postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu
docker compose up -d postgres redis
python -m mayabu_db.migrate
python admin_review.py refresh-variant-groups --limit 10000
python admin_review.py backfill-search-documents --batch-size 500
python scripts\verify_v51.py
```

Do not run `docker compose down -v` unless you intentionally want to delete the PostgreSQL data volume.

## Rollback

The migration adds tables, columns, indexes, functions, and triggers without deleting the v4 tables. To roll the application code back, stop v5 processes and restore the previous code. Keep a database backup because data written by v5 may not be understood by older code.


## v5.0 to v5.1 hardening notes

- Discovery and direct-URL ingestion now use the same deterministic identity engine.
- Search pagination is performed in PostgreSQL, so offsets beyond the old 300-row rerank window no longer silently return empty pages.
- Price refreshes invalidate product and price-history caches only; search cache entries expire through their short TTL.
- `MAYABU_SCRAPER_PLATFORM_CONCURRENCY` now affects worker semaphores within conservative platform caps.
- `MAYABU_API_WORKERS` controls production Uvicorn process count.
- Run `python -m pytest -q tests/test_v51_postgres_integration.py` with a dedicated `MAYABU_TEST_DATABASE_URL` before production deployment.
