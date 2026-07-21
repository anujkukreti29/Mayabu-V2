# Mayabu v5.1 Independent Audit and Production Hardening Report

## Decision

The v5.0 architecture was a strong foundation, but several issues required correction before it should be treated as the production-hardening baseline. The changes in v5.1 are not cosmetic: they address product-identity correctness, deep-search correctness, cache effectiveness, worker configurability, database efficiency, deployment safety, and operational accountability.

This report distinguishes code paths that were statically verified and tested from behavior that still requires a live PostgreSQL, Redis, browser, and platform environment.

## Independently confirmed v5.0 issues

1. **Two matching systems were active.** Discovery ingestion used the older fuzzy scorer while direct-URL ingestion and variant grouping used deterministic fingerprints. The same listing could therefore receive different identity decisions depending on its ingestion path.
2. **Deep pages could silently disappear.** Search fetched a bounded candidate window, ranked it in Python, and then sliced using the requested offset. Offsets beyond the fetch window returned empty pages even when more database rows existed.
3. **Search caching was invalidated too broadly.** A single listing refresh cleared the complete search-cache namespace, making repeated search misses likely under continuous price refresh.
4. **The search source was resolved through PostgreSQL for every search request.** The v5 search table/materialized-view compatibility check added an avoidable round trip to the hottest route.
5. **Worker platform concurrency ignored configuration.** Documented environment settings did not actually control the runtime semaphore limits.
6. **Search-document backfill repeatedly checked out database connections.** Large batches used one pool checkout per product rather than one checkout per batch.
7. **API deployment was single-process by default.** The application was stateless enough to scale, but the supplied runner did not expose a production worker-count setting.
8. **Deployment hardening gaps existed.** Containers ran as root; local PostgreSQL/Redis ports were exposed on all interfaces; compose used fixed container names that made scaling awkward; and the development database password was embedded directly in compose configuration.
9. **Admin mutations had no durable audit trail.** Sensitive actions such as merges, review decisions, direct ingestion, and platform controls were authenticated but not recorded as immutable operational events.
10. **Existing fingerprint indexes were not fully used for discovery candidate retrieval.** Candidate lookup depended more heavily on JSON/model/title tiers than the deterministic identity columns already present in the schema.

## Corrections implemented in v5.1

### One authoritative matching engine

- Added `mayabu/domain/matching.py` as the single matching policy used by discovery ingestion and maintenance deduplication.
- Deterministic `build_identity()` and `classify_relation()` decisions are authoritative.
- Explicit model, RAM, storage, screen, CPU, and family conflicts block automatic merging.
- Fuzzy title scoring is retained only as a conservative fallback for incomplete identities.
- Production modules no longer import matching logic from the JSON-era `mayabu_catalog.py` tool.
- Product creation now persists exact and family fingerprints immediately.
- Candidate retrieval checks exact fingerprint, family fingerprint, variant key, model code, family, trigram title, and bounded fallback tiers.

### Correct SQL-ranked pagination

- The v5 search path now computes groups and ranking in PostgreSQL and applies `LIMIT/OFFSET` after ranking.
- The previous 300-row Python rerank ceiling no longer truncates deeper pages.
- The compatibility path for older schemas remains bounded.
- Search-source detection is memoized per process and warmed during API startup.
- Added lower-case trigram expression indexes matching the case-normalized query predicates.

### Cache behavior suitable for continuous refresh

- Product changes now invalidate only product-detail and price-history keys.
- Search results use their short TTL for eventual consistency instead of being globally deleted after every price update.
- Added an explicit bulk search invalidation method for migrations/manual rebuilds.
- API and workers reuse a process-local cache singleton rather than repeatedly constructing clients.

### Worker and index efficiency

- Platform concurrency now reads `MAYABU_SCRAPER_PLATFORM_CONCURRENCY` while preserving conservative per-platform safety caps.
- Search-document and variant-group batch refreshes reuse a database checkout across the batch and isolate per-item failures with transactions.
- Discovery workers no longer clear the full search cache after each batch.

### Deployment and operational hardening

- Added `MAYABU_API_WORKERS` for production Uvicorn process count.
- Development reload remains single-process; production can use multiple workers.
- API and browser-worker images run as a non-root `mayabu` user.
- PostgreSQL and Redis host ports bind to `127.0.0.1` in the local compose profile.
- PostgreSQL password is environment-interpolated.
- Fixed container names were removed so compose services can be replicated.
- Added persistent `admin_audit_log` storage and an admin audit-log endpoint.
- Admin merge, review, ingestion, maintenance, duplicate-scan, and platform-control actions write audit events.

## Test coverage added

- Deterministic exact-product match.
- Storage/SKU variant rejection despite near-identical titles.
- Discovery ingestion using the same identity policy as direct ingestion.
- Product cache invalidation not clearing search results.
- Config-driven worker limits with conservative caps.
- SQL-side pagination regression check.
- Memoized search-source resolution.
- No production dependency on the JSON catalog matcher.
- Non-root container and audit-schema checks.
- Optional real-PostgreSQL integration test covering schema application, fixture listing ingestion, search-document refresh, best-price output, and durable queue insertion.

## Validation completed in the build environment

- Python compilation: passed.
- Ruff static checks: passed.
- Unit/architecture tests: 21 passed.
- PostgreSQL integration test: 1 skipped because no dedicated live test database was available.
- Existing backend smoke test: passed.
- Existing scraper contract test: passed.
- Existing product-matching sanity test: passed.
- FastAPI OpenAPI generation: passed, version `5.1.0`, 23 paths.
- PostgreSQL schema parse using `pglast`: passed.
- ZIP integrity checks: performed after packaging.

## Still requires local/live verification

The artifact environment did not provide Docker, a live PostgreSQL/Redis instance, or authenticated/stable access to the four ecommerce sites. The following must therefore be validated locally before production deployment:

1. Apply the migration to a backup/restored copy of the real Mayabu database.
2. Run the dedicated PostgreSQL integration test against a database whose name contains `test`.
3. Run real discovery, detail, direct-URL, and refresh scrapes per platform.
4. Execute a search load test with realistic catalog volume and record p50/p95/p99 latency.
5. Confirm query plans with `EXPLAIN (ANALYZE, BUFFERS)` on exact-SKU, family, broad-category, and deep-page searches.
6. Exercise worker retries, leases, circuit breakers, and dead-letter recovery by intentionally failing a test platform job.
7. Confirm multi-worker API behavior behind the intended reverse proxy/load balancer.

## Final assessment

Mayabu v5.1 is the corrected production-hardening baseline, not a claim that software can never be improved again. The verified correctness and efficiency defects found in v5.0 have been addressed in code. Future changes should now be driven by live measurements, catalog growth, platform behavior, and actual traffic rather than another architecture rewrite.
