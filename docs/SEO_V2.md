# Mayabu SEO V2

## Indexable routes

| Surface | Robots | Sitemap |
|---------|--------|---------|
| Homepage `/` | `index,follow` | static |
| Category landings (8) | `index,follow` | categories |
| Eligible Product Detail | `index,follow` | products-* |
| Platforms / How it works / About / Contact / Legal | `index,follow` | static |

## Noindex routes

Search (all query permutations), Compare, Sign-in / Sign-up / Account / Wishlist,
forgot/reset/verify password flows, Admin, Assistant, Tracker, API.

Meta robots is authoritative. `robots.txt` Disallow is advisory only.

## Canonical policy

- Public base URL: `VITE_SITE_URL` or `VITE_CANONICAL_HOST`
- Production **requires** `https://` base URL
- Paths: no trailing slash (except `/`); query/hash stripped from canonicals
- Categories: plural landing routes (`/laptops`, …) — never `/search?category=`
- Legacy: `/mobile-phones` → 301 `/smartphones`
- Products: `/products/{id}/{slug}` — retailer URLs are never canonical
- Variants (storage, size, body/kit) keep separate product URLs

## Product eligibility (sitemap + indexing)

Included when present in `product_search_documents` for a public category with a
useful title (≥ 8 chars). Temporary missing offers do **not** auto-noindex.
Permanently non-public / absent from search documents are omitted from sitemap
and return 404 on PDP.

## Sitemap architecture

```
/sitemap.xml                 → sitemap index
/sitemaps/static.xml
/sitemaps/categories.xml
/sitemaps/products/{n}.xml   → chunked eligible products
```

Backend feed:

- `GET /api/seo/sitemap/meta`
- `GET /api/seo/sitemap/products?page=&page_size=`

`lastmod` uses product `last_seen_at` (not request time). Redis cache ~5 minutes.
Chunk size default 5000 (protocol max treated as 45000).

## Robots

**Production:** Allow public surfaces; Disallow auth/search/compare/admin/api;
`Sitemap: https://…/sitemap.xml`

**Non-production:** `Disallow: /` plus `X-Robots-Tag: noindex, nofollow` on HTML
responses (and robots.txt). Staging meta forces `noindex,nofollow`.

## Structured data

- Homepage: Organization + WebSite (+ SearchAction → `/search?q={search_term_string}`)
- Category: BreadcrumbList (Home → Category)
- Product: Product + Offer (single) or AggregateOffer (multi); INR numeric prices;
  no availability / ratings / reviews

## Social metadata

`pageMeta` emits og:* and twitter:* with safe image URLs (normalized product image
or brand fallback).

## Pre-launch checklist (do not run in this task)

1. Set production `VITE_SITE_URL` / `VITE_CANONICAL_HOST` to https public host
2. Set `VITE_APP_ENV=production`
3. Verify robots.txt Allow + Sitemap host
4. Verify sitemap locs use production host
5. Crawl sample PDPs / categories
6. Validate structured data
7. Submit sitemap to search engines after go-live

## Local tools

- `node scripts/seo-crawl.mjs` — bounded local crawl of status/canonical/robots
- `node scripts/visual-qa-categories.mjs` — category screenshots (prior task)
