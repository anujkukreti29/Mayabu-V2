"""SEO sitemap product feed — bounded, keyset-paginated eligible public products."""

from __future__ import annotations

import logging
from typing import Any

from mayabu.db.connection import db_connection
from mayabu.search.cache import get_cache
from mayabu.search.category_registry import public_search_categories

logger = logging.getLogger(__name__)

SEO_SITEMAP_CONTRACT = "v1"
DEFAULT_PAGE_SIZE = 5_000
MAX_PAGE_SIZE = 10_000
MAX_URLS_PER_SITEMAP = 45_000
SITEMAP_META_CACHE_KEY = f"seo:sitemap:meta:{SEO_SITEMAP_CONTRACT}"
SITEMAP_META_TTL_SECONDS = 300
SITEMAP_PAGE_TTL_SECONDS = 300
# Minimum title length for a useful indexable PDP.
_MIN_TITLE_LEN = 8


def _page_cache_key(page: int, page_size: int) -> str:
    return f"seo:sitemap:products:{SEO_SITEMAP_CONTRACT}:p{page}:s{page_size}"


def count_indexable_products() -> int:
    categories = list(public_search_categories())
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select count(*)::int as n
            from product_search_documents
            where category = any(%s)
              and canonical_title is not null
              and length(btrim(canonical_title)) >= %s
            """,
            (categories, _MIN_TITLE_LEN),
        )
        row = cur.fetchone()
    return int((row or {}).get("n") or 0)


def get_sitemap_meta(*, page_size: int = DEFAULT_PAGE_SIZE, use_cache: bool = True) -> dict[str, Any]:
    page_size = max(1, min(int(page_size), MAX_PAGE_SIZE))
    # Cap effective page size to protocol-friendly chunks.
    page_size = min(page_size, MAX_URLS_PER_SITEMAP)
    cache = get_cache()
    cache_key = f"{SITEMAP_META_CACHE_KEY}:s{page_size}"
    if use_cache:
        cached = cache.get_json(cache_key)
        if isinstance(cached, dict) and "total" in cached:
            return cached
    total = count_indexable_products()
    pages = max(1, (total + page_size - 1) // page_size) if total else 0
    payload = {
        "contract_version": SEO_SITEMAP_CONTRACT,
        "total": total,
        "page_size": page_size,
        "pages": pages,
        "max_urls_per_sitemap": MAX_URLS_PER_SITEMAP,
    }
    if use_cache:
        cache.set_json(cache_key, payload, SITEMAP_META_TTL_SECONDS)
    return payload


def list_indexable_products(
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Return one sitemap page of indexable products (keyset via OFFSET on ordered UUID).

    Eligibility:
    - public search category
    - useful canonical title
    - present in product_search_documents (Mayabu public catalog surface)

    Products may appear without a current best_price (temporary retailer outage);
    they remain indexable while they stay in the public search document set.
    """
    page = max(1, int(page))
    page_size = max(1, min(int(page_size), MAX_PAGE_SIZE, MAX_URLS_PER_SITEMAP))
    cache = get_cache()
    key = _page_cache_key(page, page_size)
    if use_cache:
        cached = cache.get_json(key)
        if isinstance(cached, dict) and "items" in cached:
            return cached

    categories = list(public_search_categories())
    offset = (page - 1) * page_size
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select product_id::text as product_id,
                   canonical_title as title,
                   last_seen_at as lastmod
            from product_search_documents
            where category = any(%s)
              and canonical_title is not null
              and length(btrim(canonical_title)) >= %s
              and best_price is not null
              and best_price > 0
              and coalesce(platform_count, 0) >= 1
            order by product_id asc
            limit %s offset %s
            """,
            (categories, _MIN_TITLE_LEN, page_size, offset),
        )
        rows = [dict(r) for r in cur.fetchall()]

    items: list[dict[str, Any]] = []
    for row in rows:
        pid = str(row.get("product_id") or "")
        title = str(row.get("title") or "").strip()
        if not pid or len(title) < _MIN_TITLE_LEN:
            continue
        lastmod = row.get("lastmod")
        items.append(
            {
                "product_id": pid,
                "title": title,
                "lastmod": lastmod.isoformat() if hasattr(lastmod, "isoformat") else None,
            }
        )

    payload = {
        "page": page,
        "page_size": page_size,
        "count": len(items),
        "items": items,
        "contract_version": SEO_SITEMAP_CONTRACT,
    }
    if use_cache:
        cache.set_json(key, payload, SITEMAP_PAGE_TTL_SECONDS)
    return payload


def chunk_product_ids_for_sitemaps(
    product_ids: list[str],
    *,
    max_urls: int = MAX_URLS_PER_SITEMAP,
) -> list[list[str]]:
    """Pure helper for scale tests — split IDs into sitemap-sized pages."""
    max_urls = max(1, int(max_urls))
    if not product_ids:
        return []
    return [product_ids[i : i + max_urls] for i in range(0, len(product_ids), max_urls)]


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_URLS_PER_SITEMAP",
    "SEO_SITEMAP_CONTRACT",
    "chunk_product_ids_for_sitemaps",
    "count_indexable_products",
    "get_sitemap_meta",
    "list_indexable_products",
]
