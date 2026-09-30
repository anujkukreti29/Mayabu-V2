# Mayabu Scraper Design

Mayabu uses **one scraper implementation per retail platform**, not one scraper per category.

```
PLATFORM SCRAPER (Amazon / Flipkart / Croma / …)
    ↓
raw standardized listing
    ↓
CATEGORY DETECTION
    ↓
CATEGORY NORMALIZER  (mayabu/domain/categories/)
    ↓
CATEGORY IDENTITY + MATCHER
    ↓
canonical product / variant + platform offers
```

Food delivery, cabs, and quick commerce are **out of scope** for this ecommerce product model.

## Supported platforms

Canonical slugs (authoritative registry: `mayabu/platforms/registry.py`):

| Slug | Display |
|------|---------|
| amazon | Amazon India |
| flipkart | Flipkart |
| croma | Croma |
| reliancedigital | Reliance Digital |
| vijaysales | Vijay Sales |
| jiomart | JioMart |
| poorvika | Poorvika |
| bajajelectronics | Bajaj Electronics |

### Adding a new platform

1. Add one entry to `mayabu/platforms/registry.py` (slug, hosts, base URL, caps).
2. Add `*_scraper.py` discovery module with `scrape_<slug>(...)`.
3. Add `mayabu_refresh/<slug>.py` with `scrape_<slug>_refresh(...)`.
4. Register both in `mayabu_db/scraper_runner.py` and `mayabu_refresh/runner.py` dispatch maps.
5. Extend schema platform allowlists / `platform_registry` seed (idempotent).
6. Add fixtures + health-check default query.
7. Do **not** create per-category scrapers for that retailer.

### Adding a new category

1. Add `mayabu/domain/categories/<name>.py` adapter (extract_specs, identity/variant/descriptive keys, hard_conflicts, price_bounds).
2. Register in `mayabu/domain/categories/registry.py`.
3. Add detection rules (avoid accessory collisions).
4. Add deterministic matching tests.
5. Do **not** fork platform scrapers.

## Discovery scrapers

Lightweight search/listing extraction only:

- title, current price, MRP, valid discount, image URL, product URL, native ID, timestamp

Prefer JSON-LD / embedded state / semantic attributes over generated CSS classes.

## Refresh scrapers

Known product URLs → current_price, MRP, discount. Failed scrapes must not null out good prices at ingestion.

## Detail enrichment

`mayabu/scrapers/detail/registry.py` prefers JSON-LD/OpenGraph, then platform selectors. Category is detected before category-specific spec extraction (laptop remains the safe fallback).

## Category adapters

Identity fields decide exact variants. Supporting fields are evidence. Descriptive fields (e.g. TWS battery hours, phone camera MP) must not force merges/splits.

Legacy `audio` rows stay compatible; new data prefers `tws` / `headphones`.

## Price history

Source of truth: `daily_product_platform_prices` `(product_id, date, platform)`.

`daily_product_prices` keeps aggregates (`best_price`, `best_platform`, …) plus legacy amazon/flipkart/croma/reliancedigital columns as API compatibility surfaces.

Best price is computed by ordering platform rows — not a hard-coded COALESCE chain.

## Capacity

New platforms default to 1 concurrent slot (`PlatformInfo.discovery_cap`). Flipkart remains at 2.

## Health checks

```cmd
python scraper_health_check.py --platform vijaysales --type discovery --query laptop --max-products 20 --max-pages 1
python scraper_health_check.py --platform jiomart --type discovery --query smartphone --max-products 20 --max-pages 1
```

Report `blocked` honestly when CAPTCHA/anti-bot challenges appear. Do not bypass protections.

### Health status model

| Status | Meaning |
|--------|---------|
| healthy | quality thresholds satisfied |
| degraded | usable output below expected quality/count |
| partial | some extraction dimensions missing |
| empty | page accessible but zero usable products |
| blocked | challenge/access restriction detected |
| failed | unexpected scraper/runtime error |

Configured/enabled ≠ currently healthy. Scheduler backs off blocked/circuit-open platforms.

### Category safety

UNKNOWN stays UNKNOWN — never fall back to laptop adapters.
Accessories classify as `accessory` and are rejected from primary-product ingestion.
`evaluate_listing` returns accepted/degraded/rejected with stable reason codes; bad prices are not persisted.

## Integrity rules

- Do not overwrite existing good prices with null.
- Use category-aware price sanity bounds.
- Keep price observations append-only.
- One broken platform must not stop others.
- Public search index remains laptop-oriented for now (follow-up for multi-category search).
