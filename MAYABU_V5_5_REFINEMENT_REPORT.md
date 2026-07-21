# Mayabu v5.5 Refinement Report

**Baseline:** Mayabu v5.4 optimized baseline  
**Purpose:** stable file-by-file maintenance baseline

## Significant changes

### Search ranking

The legacy in-process ranker now prepares query tokens once per result page instead of once per candidate. Candidate text is assembled once and reused for query, brand, model, RAM, and storage scoring. Ranking remains deterministic and does not mutate source rows.

A local synthetic benchmark over 2,000 candidates improved median rank time from about 26.7 ms to 12.4 ms. This is a microbenchmark, not a production latency claim.

### Visible-price extraction

The visible-price classifier was split into small pure helpers. Parsed candidates use slot-based immutable records, current-price selection is one bounded pass, MRP candidates are deduplicated while collected, and page text is no longer copied into a second combined string solely to extract a discount.

Behavior remains conservative: EMI, coupon, fee, warranty, delivery, and unrelated offer text do not become the current price; struck and nearby values remain MRP signals.

### Comparison persistence

The comparison provider no longer overwrites restored session data during hydration. Persisted products are validated before use, corrupt data is removed, storage failures degrade to in-memory comparison, duplicate products are ignored, and the four-product limit is enforced without unnecessary array copies.

### Verification persistence

Stored verification task IDs are trimmed, deduplicated, length-bounded, and capped at four. Invalid admission states and corrupt session data are ignored. Browser storage failures no longer interrupt verification.

### Frontend dependency and test efficiency

`date-fns` and the unused Radix Tabs package were removed. Freshness labels now use the native `Intl.RelativeTimeFormat` API. The lockfile contains two fewer package entries, and the production client build transformed 1,810 modules instead of the prior 2,114. Vitest worker count is bounded to four to avoid excessive process and memory use on high-core CI hosts.

## Compatibility

- No PostgreSQL migration.
- No public endpoint rename or response-contract change.
- No matching ownership change.
- No queue, cache, or scraper architecture change.
- Existing v5.4 environment files remain valid.

## Validation

- Backend compile: passed
- Ruff: passed
- Backend tests: 50 passed, 1 PostgreSQL integration test skipped
- Frontend typecheck: passed
- ESLint: passed
- Prettier: passed
- Frontend tests: 44 passed
- Client and SSR build: passed
- Ten prerendered routes: passed
- SEO verification: passed
- npm audit, including development dependencies: 0 vulnerabilities

Live PostgreSQL/Redis, real retailer scraping, browser E2E, and production load measurements still require the user's local or staging environment.
