# SEO Checklist

- Indexable pages render meaningful initial HTML through SSR or prerendering.
- Each indexable page has one title, description, canonical URL, robots directive, H1, and main content.
- Stable pages are prerendered: home, categories, platforms, how it works, about, contact, privacy, terms, and disclaimer.
- Product pages are server-rendered from FastAPI and use `/products/{id}/{slug}`.
- Old product slugs redirect permanently to the canonical slug.
- Missing products return 404 instead of a 200 application shell.
- Search is `noindex, follow`; compare is `noindex, follow`; account and admin are noindex.
- Sitemap contains only canonical static/indexable routes until a verified product-feed source is available.
- Search, filters, sort URLs, compare, account, admin, and verification jobs are excluded from sitemap output.
- Product and BreadcrumbList structured data use visible backend data only.
- Invalid or zero prices, fabricated ratings, reviews, GTINs, seller policies, and stale merchant claims are excluded.
- `robots.txt` permits required assets and does not hide noindex pages from crawlers.
- Social metadata uses relevant Mayabu copy and canonical URLs.
- Validate production output with Search Console, URL Inspection, Rich Results Test, and Core Web Vitals before public launch.
