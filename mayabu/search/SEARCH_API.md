"""Backend search API notes (multi-category retail).

Public search contract version: v6

GET /api/search
  q (required)
  category (optional, public-enabled only)
  sort: relevance | price_asc | price_desc
  min_price / max_price (optional INR integers; override inferred budget)
  filters (optional JSON object; keys allowlisted per category)
  limit / offset / cursor

GET /api/search/categories
  Lists public + experimental category metadata.
  Experimental categories are not accepted as `category=` on /search.

Public-enabled categories:
  laptop, smartphone, television, refrigerator, washing_machine, tws, headphones

Experimental (not public-searchable via category=):
  camera

Pagination:
  result_count = length of current page (not catalog total)
  has_more / next_cursor for continuation
  facet_scope = query (facet counts from bounded matching set, cap 200; not page-only)
  facet_sample_size = number of matching candidates used for facets

Unknown/accessory products are never returned from public search.

Filters:
  JSON object; keys allowlisted per category (includes `brand` where applicable).
  List values = OR within one facet; multiple keys = AND.
  Example: filters={"brand":["samsung","lg"],"screen_size_inch":55}

Staging catalog seed:
  See docs/STAGING_CATALOG.md
  set DATABASE_URL=postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu_test
  python scripts/bootstrap_test_db.py
  python scripts/seed_retail_catalog.py --dry-run
  python scripts/seed_retail_catalog.py --max-products 12 --queries-per-category 2
  python scripts/qualify_search.py
"""
