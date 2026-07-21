# Mayabu Scraper Design v4.3

Mayabu uses separate scraper types so the backend stays clean and maintainable.

## 1. Discovery scrapers

Discovery scrapers run on ecommerce search/category pages and extract only:

- `title`
- `current_price`
- `mrp`
- `discount_percent`
- `image_url`
- `product_url`

Discovery is responsible for finding new platform listings and collecting the minimum product data required for comparison.

## 2. Refresh scrapers

Refresh scrapers run on already-known product detail URLs and extract only:

- `current_price`
- `mrp`
- `discount_percent`

Refresh does not scrape title, image, stock, reviews, features, offers, delivery, seller, or description. Those belong to future enrichment modules.

## 3. Structural extraction strategy

Generated ecommerce frontend classes are brittle. Mayabu v4.3 avoids using them as the foundation.

The preferred extraction order is:

1. Stable semantic/platform selectors where available.
2. Structural selectors such as product URLs and images.
3. Visible text extraction using INR price patterns.
4. Parent-card grouping.
5. Line-through/nearby larger price detection for MRP.
6. Discount calculation from current price and MRP.
7. Health scoring and diagnostics.

Flipkart discovery specifically uses product links containing `/p/` or `pid=`, then climbs to the nearest visible card and extracts title, price, MRP, discount, image, and URL from that card.

## 4. Diagnostics

Normal product output must stay clean. Internal diagnostics are separate and may include:

- platform
- scraper type
- URL/query
- products found
- extraction rates
- error message
- screenshot path
- HTML path

Diagnostics are for admin/debugging only.

## 5. Health checks

Run health checks with:

```cmd
python scraper_health_check.py --platform flipkart --type discovery --query laptop --max-products 20 --max-pages 1 --headed --debug
python scraper_health_check.py --platform flipkart --type refresh --url "PRODUCT_URL" --headed --debug
```

Discovery health checks expect enough products and high rates for title, price, image, and URL extraction.

Refresh health checks expect a valid current price and sane MRP/discount when available.

## 6. Integrity rules

- Do not overwrite existing good prices with null.
- Validate laptop prices before saving.
- Keep price observations append-only.
- Keep debug artifacts private.
- One broken platform must not stop all scraping.
