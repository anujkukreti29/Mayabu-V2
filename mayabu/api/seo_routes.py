"""Public SEO sitemap feed endpoints (no private data)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from mayabu.search.seo_sitemap import (
    DEFAULT_PAGE_SIZE,
    get_sitemap_meta,
    list_indexable_products,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/seo", tags=["seo"])


@router.get("/sitemap/meta")
def sitemap_meta(page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=100, le=10_000)) -> dict:
    try:
        return get_sitemap_meta(page_size=page_size)
    except Exception:
        logger.exception("seo_sitemap_meta_failed", extra={"event": "seo_sitemap"})
        raise HTTPException(status_code=503, detail="Sitemap metadata unavailable.") from None


@router.get("/sitemap/products")
def sitemap_products(
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=100, le=10_000),
) -> dict:
    try:
        return list_indexable_products(page=page, page_size=page_size)
    except Exception:
        logger.exception("seo_sitemap_products_failed", extra={"event": "seo_sitemap"})
        raise HTTPException(status_code=503, detail="Sitemap products unavailable.") from None
