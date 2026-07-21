# Mayabu v5.0 Production Architecture Build Report

## Delivered

- Incremental indexed search read model and dirty-document queue.
- Exact/similar/related search sections with stronger model-token matching.
- Deterministic product and family fingerprints.
- Variant groups that preserve distinct storage/RAM/SKU variants.
- Direct product URL scraper and ingestion pipeline.
- Durable idempotent PostgreSQL jobs, leases, retries, dead tasks, and heartbeats.
- Bounded worker concurrency, per-platform semaphores, and persistent circuit breakers.
- Partial-platform failure isolation in the local scrape runner.
- Redis cache/rate-limit fallback and affected-product invalidation.
- Retention-aware maintenance and scheduler.
- Structured request logs, request IDs, liveness, readiness, and DB pool stats.
- Separate API and worker dependency/images to reduce API image size.
- Windows upgrade/start scripts and a bounded search load-test utility.

## Corrections made during validation

- Fixed parameterized PostgreSQL session timeout setup using `set_config`.
- Fixed JSONB array aliases in the incremental search-document SQL function.
- Added final v5 task-status constraint including paused jobs.
- Fixed direct-ingestion handling when the inserted listing cannot be reloaded.
- Removed event-loop binding risk from the worker shutdown event.
- Corrected worker Docker commands to match supported CLI flags.
- Corrected API container health endpoint.
- Fixed detail-page MRP extraction precedence.
- Added safe final-redirect platform validation.
- Made active-job idempotency race-safe with `ON CONFLICT`.
- Treated useful partial scrapes as terminal success rather than retrying forever.
- Bounded in-memory rate-limit fallback storage.

## Validation completed in the build environment

- Python compile check: passed.
- Import sweep across `mayabu`, `mayabu_db`, and `mayabu_refresh`: passed after dependencies were installed.
- New v5 unit tests: 12 passed.
- Existing backend smoke test: passed.
- Existing scraper-contract smoke test: passed.
- Existing v4.5 matching sanity test: passed.
- PostgreSQL schema parsed successfully as 176 statements using `pglast`.

## Not executed in the build environment

A live PostgreSQL/Docker instance and external ecommerce sites were not available in the artifact build environment. Therefore, migration execution against the user's existing database, live browser scraping, and real load measurements must be run locally using the included verification and benchmark commands. This is called out explicitly rather than being represented as already verified.
