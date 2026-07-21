# Mayabu v4.3 Scraper-Hardened Backend Report

This build updates the Mayabu v4.2 backend into a scraper-hardened v4.3 architecture focused on the laptop MVP.

## Final scraper contract

### Discovery scraper output
Discovery scrapers are used for search/category pages and return only:

```json
{
  "title": "...",
  "current_price": 69990,
  "mrp": 89689,
  "discount_percent": 21.96,
  "image_url": "https://...",
  "product_url": "https://..."
}
```

Internally the legacy ingestion format still maps these to `title`, `currentPrice`, `maxRetailPrice`, `discount`, `image`, and `link`, so the existing DB pipeline remains compatible.

### Refresh scraper output
Refresh scrapers are used for already-known product detail URLs and return only:

```json
{
  "current_price": 69990,
  "mrp": 89689,
  "discount_percent": 21.96
}
```

Refresh scrapers no longer expose product title, image, stock status, stock text, raw price text, page status, or warnings in normal output. Extra diagnostics stay internal.

## Main changes

1. Replaced Flipkart discovery with a structural/text extractor that does not rely on Flipkart generated CSS classes.
2. Added a shared structural discovery fallback layer for Amazon, Croma, and Reliance Digital.
3. Added visible-price extraction for refresh scrapers across all platforms.
4. Made refresh scrapers price-only: current price, MRP, and discount percent.
5. Added health report logic for discovery and refresh scraper checks.
6. Added `scraper_health_check.py` CLI for platform-level health checks.
7. Added v4.3 smoke tests in `tests/smoke_v43_scrapers.py`.
8. Updated refresh ingestion so price-only refresh does not require a scraped title and does not update stock/effective-price fields.
9. Preserved DB compatibility while keeping public/dev scraper output clean.

## Flipkart anti-brittleness fix

The old approach depended on selectors like generated frontend classes. The v4.3 approach uses:

- `a[href]` product links containing `/p/` or `pid=`
- nearest visible parent product card
- visible `₹` price text
- plain nearby MRP numbers such as `89,689`
- line-through visual style when available
- largest image inside the card
- title-like card text with laptop/brand/spec hints
- sanity checks for laptop price ranges

Generated CSS classes are no longer the primary extraction method.

## Health checks

Discovery health checks measure:

- products found
- title success rate
- current price success rate
- image success rate
- URL success rate
- duplicate rate

Refresh health checks measure:

- current price exists
- current price is in laptop-safe range
- MRP is not below current price
- discount is between 0 and 95

Example commands:

```cmd
python scraper_health_check.py --platform flipkart --type discovery --query laptop --max-products 20 --max-pages 1 --headed --debug
python scraper_health_check.py --platform croma --type refresh --url "https://www.croma.com/.../p/322282" --headed --debug
```

## Data integrity rules

- Never overwrite a good existing price with null.
- Discovery requires title, product URL, and current price before ingestion.
- Refresh requires only valid price fields.
- Price observations remain append-only.
- Diagnostics/debug artifacts are kept separate from product output.
- One platform failure should not stop the other platform workers.

## Validation performed

Static Python compilation passed:

```cmd
python -m compileall -q .
```

v4.3 scraper contract smoke test passed:

```cmd
python tests\smoke_v43_scrapers.py
```

