"""Category landing API — one generic endpoint for all public categories."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from mayabu.search.category_landing import get_category_landing

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("/{category}/landing")
def category_landing(
    category: str,
    product_limit: int = Query(default=18, ge=6, le=24),
    section_limit: int = Query(default=6, ge=1, le=12),
) -> dict:
    """Bounded discovery payload for a public category landing page."""
    try:
        return get_category_landing(
            category,
            product_limit=product_limit,
            section_limit=section_limit,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "invalid_category":
            raise HTTPException(status_code=400, detail="Invalid category.") from exc
        raise HTTPException(
            status_code=404,
            detail="Category is not available for public landing pages.",
        ) from exc
    except Exception:
        logger.exception("category_landing_failed", extra={"event": "category_landing"})
        raise HTTPException(status_code=503, detail="Category landing temporarily unavailable.") from None
