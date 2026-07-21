# Mayabu v5.1 Upgrade Guide

## Which package to use

- **Patch-only package:** apply over an existing Mayabu v5.0 full project. It contains only new or changed v5.1 files.
- **Full package:** extract into a clean folder for the safest independent test or a fresh deployment.

Do not apply the v5.1 patch directly to v4.5.x. Upgrade to the v5.0/full structure first, or use the v5.1 full package.

## Safe Windows upgrade sequence

1. Back up the project folder.
2. Back up PostgreSQL.
3. Stop the API and workers.
4. Extract the patch into the v5.0 project and allow replacement.
5. Run the commands below from the backend root.

```cmd
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m playwright install chromium

set DATABASE_URL=postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu
set REDIS_URL=redis://127.0.0.1:6379/0

docker compose up -d postgres redis
python -m mayabu_db.migrate
python admin_review.py refresh-variant-groups --limit 10000
python admin_review.py backfill-search-documents --batch-size 500
python scripts\verify_v51.py
python -m pytest -q tests\test_v5_architecture.py tests\test_v51_hardening.py
```

## Dedicated PostgreSQL integration test

Use a separate disposable database. Its database name must contain `test` as a safety guard.

```cmd
set MAYABU_TEST_DATABASE_URL=postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu_test
python -m pytest -q -m integration tests\test_v51_postgres_integration.py
```

Do not point `MAYABU_TEST_DATABASE_URL` at the production or normal development database.

## Start locally

API:

```cmd
set MAYABU_ENV=development
set MAYABU_API_WORKERS=1
python run_api.py
```

Worker in a second terminal:

```cmd
.venv\Scripts\activate.bat
set DATABASE_URL=postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu
set REDIS_URL=redis://127.0.0.1:6379/0
python worker_db.py --loop --concurrency 2
```

## Production compose profile

Create a strong database password in `.env`:

```env
MAYABU_ENV=production
MAYABU_POSTGRES_PASSWORD=replace-with-a-long-random-password
MAYABU_API_WORKERS=2
MAYABU_SCRAPER_PLATFORM_CONCURRENCY=2
```

Then build and start:

```cmd
docker compose --profile app up -d --build
```

## Important behavior changes

- Discovery and direct-URL ingestion now share one deterministic identity engine.
- Explicit variants are not automatically merged by fuzzy title similarity.
- Deep search pages are ranked and paginated in PostgreSQL.
- Search cache is no longer globally cleared after every listing refresh.
- Worker platform limits now respond to the documented environment setting.
- API and worker containers run as non-root users.
- Admin mutations are written to `admin_audit_log`.

## Rollback

The schema changes are additive and idempotent. To roll application code back, stop v5.1 processes and restore the previous code folder. Preserve the database backup because older application code may not understand data written by v5.1. Never run `docker compose down -v` unless deleting the database volume is intentional.
