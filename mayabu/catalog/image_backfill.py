"""Backfill search-document / cluster images from matched listing images.

Only uses images already attached to confidently matched listings.
Does not crawl external image search.
"""

from __future__ import annotations

from typing import Any

from mayabu.db.connection import db_connection


def backfill_product_images(*, limit: int = 500, category: str | None = None) -> dict[str, Any]:
    """Copy best matched listing image onto search docs / clusters missing images."""
    params: list[Any] = []
    cat_clause = ""
    if category:
        cat_clause = "and d.category = %s"
        params.append(category)
    params.append(max(1, min(int(limit), 5_000)))

    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                with candidates as (
                  select d.product_id,
                         (
                           select pl.image_url
                           from platform_listings pl
                           where pl.product_id = d.product_id
                             and pl.match_status = 'matched'
                             and pl.image_url is not null
                             and length(trim(pl.image_url)) > 8
                             and pl.image_url !~* '(1x1|pixel|spacer|logo|banner|placeholder|tracking)'
                           order by
                             case when pl.stock_status = 'in_stock' then 0 else 1 end,
                             pl.last_successful_refresh_at desc nulls last,
                             pl.updated_at desc
                           limit 1
                         ) as image_url
                  from product_search_documents d
                  where (d.image_url is null or length(trim(d.image_url)) <= 8)
                    {cat_clause}
                  limit %s
                ), picked as (
                  select product_id, image_url
                  from candidates
                  where image_url is not null
                ), upd_docs as (
                  update product_search_documents d
                  set image_url = p.image_url,
                      indexed_at = now()
                  from picked p
                  where d.product_id = p.product_id
                  returning d.product_id
                )
                select count(*)::int as updated from upd_docs
                """,
                tuple(params),
            )
            updated = int((cur.fetchone() or {}).get("updated") or 0)
            # Best-effort cluster title image is not stored; search docs drive UI.
    return {"updated": updated, "category": category, "limit": limit}


__all__ = ["backfill_product_images"]
