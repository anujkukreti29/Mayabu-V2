"""Homepage discovery and lightweight product activity API."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel, Field

from mayabu.search.homepage_discovery import get_homepage_discovery
from mayabu.search.product_activity import record_product_activity

router = APIRouter(prefix="/api", tags=["homepage"])


class ActivityEventBody(BaseModel):
    product_id: str = Field(min_length=8, max_length=64)
    event_type: Literal["product_view", "search_click", "retailer_click"]


@router.get("/homepage")
def homepage_discovery(limit: int = Query(default=6, ge=1, le=12)) -> dict:
    """Return a single bounded payload for homepage product discovery sections."""
    return get_homepage_discovery(limit=limit)


@router.post("/activity")
def post_activity(
    body: ActivityEventBody,
    x_mayabu_client_id: str | None = Header(default=None, alias="X-Mayabu-Client-Id"),
) -> dict:
    """Record aggregate product engagement. Client-only; SSR must not call this."""
    return record_product_activity(
        product_id=body.product_id,
        event_type=body.event_type,
        client_id=x_mayabu_client_id,
    )
