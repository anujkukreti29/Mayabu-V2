# Platform × Category Readiness

Mayabu no longer treats retailer readiness as one global boolean.

## Three distinct concepts

1. **Configured / enabled platform** — code + registry know the retailer (`mayabu.platforms.registry`).
2. **Platform × category readiness** — authoritative ingestion/search gate (`mayabu.platforms.coverage`).
3. **Temporary health** — circuit breaker / scrape outcomes (`platform_health`, category health scores). Do not rewrite readiness from one outage.

## Readiness states

| State | Scheduled discovery | Catalog ingestion | Public best-price / search offers |
|---|---|---|---|
| `production` | yes | yes (quality-gated) | yes |
| `experimental` | no (tests/smoke only) | no | no |
| `disabled` | no | no | no |
| `blocked` | no | no | no |
| `unsupported` | no | no | no |

## Promotion procedure for a category

1. Run bounded live probes (`scripts/category_promotion_smoke.py`) repeatedly.
2. Confirm price/image/URL/native-ID/category accuracy/dedupe thresholds.
3. Confirm worker/scheduler would only schedule that pair (`discovery_allowed` / `task_allowed`).
4. Set the cell to `production` with `ingestion_enabled=True` in `mayabu/platforms/coverage.py`.
5. Seed/update multi-category plans via `create_multi_category_plans` (uses `production_discovery_pairs()`).
6. Re-run pytest gating tests + PostgreSQL audit.

## Partial platform summary

A retailer may be **PARTIALLY PRODUCTION READY** when some categories are production and others remain experimental (e.g. Vijay Sales headphones experimental while laptop is production).
