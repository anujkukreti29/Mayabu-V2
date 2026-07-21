# Mayabu v5.4 Optimization and Refinement Report

**Baseline:** Mayabu v5.3 scale-safe full-stack package  
**Result:** Mayabu v5.4 optimized baseline  
**Date:** 2026-07-20

## Purpose

This release is intended to become the stable base that can be maintained by
replacing or adding individual files. It deliberately avoids another framework,
database, or API redesign. The work concentrates on reusable code, bounded hot
paths, edge-case safety, reduced frontend weight, and clearer operational
ownership.

## Backend refinements

### Shared scraper capacity

`mayabu/scrapers/capacity.py` is now the single entry point for local and
cross-process retailer concurrency. The durable worker, discovery CLI, refresh
CLI, and scraper health checks use the same capacity policy instead of carrying
parallel semaphore logic.

The Redis lease is renewable. If renewal is lost in production, the owner task
is cancelled and fails closed instead of continuing to scrape without a valid
platform slot.

### Durable task ownership

Worker task lease duration and renewal frequency are configurable. A worker
stops processing immediately when PostgreSQL reports that it no longer owns the
task lease. It does not complete or fail a task row that another worker may have
already reclaimed.

Task dispatch now uses a typed handler registry. Compatible task aliases remain
explicit and test-covered.

### Matching and query edge cases

- `ROM` is normalized only as a standalone storage term. Product names such as
  `Chromebook` are no longer corrupted.
- Fuzzy title comparison is bounded to 2,048 characters. This prevents
  pathological retailer titles from creating unbounded `SequenceMatcher` and
  token-set work.
- RAM, storage, and screen values are compared through defensive numeric
  helpers. Malformed values reject conservatively instead of raising
  `ValueError` during ingestion or duplicate review.
- Numeric strings and numeric values now compare consistently.

The fuzzy fallback remains secondary to deterministic product identity and
cannot override a material specification conflict.

### Configuration and operational cleanup

Added safe defaults for:

```env
MAYABU_WORKER_TASK_LEASE_MINUTES=20
MAYABU_WORKER_LEASE_REFRESH_SECONDS=120
MAYABU_SCRAPER_HEADLESS=true
MAYABU_SCRAPER_DEBUG=false
```

Debug HTML and screenshots are now opt-in instead of being generated on every
blocked or failed refresh. Search-analytics and repository-tier failures use
structured logging rather than ad-hoc stdout output.

## Frontend refinements

### Reusable application definitions

Navigation routes, category links, indexable static routes, supported-platform
copy, seller disclosure, price disclaimer, and trademark copy are centralized.
Navbar, footer, sitemap, and product pages consume those definitions, reducing
copy drift and making future edits file-scoped.

### API request lifecycle

The typed API client now:

- validates that adapters pass relative API paths;
- combines caller cancellation with an internal timeout without leaking event
  listeners or timers;
- preserves caller `AbortError` during navigation cancellation;
- reports internal timeout, network, HTTP, unreadable JSON, and Zod validation
  failures separately;
- normalizes nested FastAPI validation details safely.

### Verification state isolation

Active task IDs and polling state are reset when the product changes. Invalid or
expired session data is removed. Polling pauses in the background, uses bounded
retry behavior, and maps job-read failures to an unavailable state rather than
showing an indefinitely queued request.

### Pricing utilities and chart weight

Price statistics use an iterable one-pass reducer with **O(n)** time and
**O(1)** additional aggregation space. Buying-insight decisions are pure and
unit-tested.

The Recharts runtime was removed and replaced by an SSR-safe accessible SVG
line chart. In this build:

| Metric | v5.3 reference | v5.4 result |
|---|---:|---:|
| Price-history client chunk | 394.40 kB | 3.21 kB |
| Price-history gzip chunk | 108.60 kB | 1.66 kB |
| Client modules transformed | 2,731 | 2,114 |
| Installed npm packages removed | - | 35 |

The chart still provides a text summary, useful y-axis labels, date labels, and
point titles for bounded data sets. No prediction or fabricated trend is added.

## Compatibility

- No PostgreSQL migration is required.
- No existing public FastAPI route was removed or renamed.
- No request or response contract was intentionally changed.
- Existing environment files continue to work because new settings have safe
  defaults.
- Existing React Router URLs and SEO policies remain intact.
- Unsupported auth, tracker, assistant, deals, and admin features remain
  feature-gated.

## Validation performed

### Backend

- Python compilation: passed
- Ruff: passed with zero findings
- Pytest: **47 passed, 1 skipped**
- The skipped test requires a live PostgreSQL integration database

### Frontend

- `npm ci`: passed after the package proxy became available
- Strict TypeScript: passed
- ESLint: passed with zero warnings
- Prettier check: passed
- Vitest/Testing Library: **41 passed across 13 files**
- Client production build: passed
- SSR server build: passed
- Ten stable routes prerendered: passed
- Client/server artifact checks: passed
- SEO verification: passed

### Not claimed as passed

- Playwright scenarios were executed with the host Chromium, but every local URL
  was rejected by the host policy with `net::ERR_BLOCKED_BY_ADMINISTRATOR`.
  Application assertions never ran, so E2E is not marked as passed.
- The npm audit endpoint returned HTTP 502 during final validation. No new
  dependency was added; Recharts and 35 transitive packages were removed, but a
  fresh vulnerability result is not claimed.
- No live PostgreSQL/Redis migration, real retailer scrape, distributed load
  test, or p50/p95/p99 production benchmark was available in this environment.

## Final assessment

v5.4 is a cleaner baseline for incremental maintenance. The largest practical
wins are the shared capacity/lease ownership model, bounded matching fallback,
removal of automatic debug artifacts, reusable frontend definitions, reliable
request cancellation, and the approximately 99% reduction in the dedicated
price-history chart chunk.
