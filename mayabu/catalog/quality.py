"""Operator-only catalog quality reporting (not a consumer score)."""

from __future__ import annotations

from typing import Any

from mayabu.db.connection import db_connection
from mayabu.platforms.coverage import CATALOG_CATEGORIES


def catalog_quality_report(*, include_orphans: bool = True) -> dict[str, Any]:
    """Public-matched product KPIs vs raw search-doc inflation."""
    categories: dict[str, Any] = {}
    with db_connection() as conn:
        with conn.cursor() as cur:
            for category in CATALOG_CATEGORIES:
                cur.execute(
                    """
                    with matched as (
                      select pl.product_id,
                             count(distinct pl.platform) as stores,
                             bool_or(pl.current_price is not null) as has_price,
                             bool_or(pl.last_successful_refresh_at > now() - interval '24 hours') as fresh_24h,
                             max(pl.image_url) as listing_image
                      from platform_listings pl
                      where pl.match_status = 'matched'
                        and pl.category = %s
                        and pl.product_id is not null
                      group by pl.product_id
                    ),
                    gallery as (
                      select product_id, count(*)::int as imgs
                      from product_images
                      where active
                      group by product_id
                    )
                    select
                      count(*)::int as public_products,
                      count(*) filter (where stores = 1)::int as stores_1,
                      count(*) filter (where stores >= 2)::int as stores_gte2,
                      count(*) filter (where stores >= 3)::int as stores_gte3,
                      count(*) filter (where stores >= 4)::int as stores_gte4,
                      count(*) filter (where has_price)::int as with_price,
                      count(*) filter (where fresh_24h)::int as fresh_24h,
                      count(*) filter (where coalesce(g.imgs, 0) >= 1 or listing_image is not null)::int as with_image,
                      count(*) filter (where coalesce(g.imgs, 0) >= 2)::int as gallery_gte2,
                      count(*) filter (where coalesce(g.imgs, 0) >= 4)::int as gallery_gte4
                    from matched m
                    left join gallery g on g.product_id = m.product_id
                    """,
                    (category,),
                )
                public = dict(cur.fetchone() or {})
                cur.execute(
                    """
                    select
                      count(*) filter (where match_status = 'matched')::int as matched_listings,
                      count(*) filter (where match_status = 'unmatched')::int as unmatched_listings,
                      count(*) filter (where match_status = 'needs_review')::int as needs_review_listings
                    from platform_listings
                    where category = %s
                    """,
                    (category,),
                )
                listings = dict(cur.fetchone() or {})
                cur.execute(
                    """
                    select count(*)::int as search_docs,
                           count(*) filter (where not exists (
                             select 1 from platform_listings pl
                             where pl.product_id = d.product_id and pl.match_status = 'matched'
                           ))::int as orphan_docs
                    from product_search_documents d
                    where d.category = %s
                    """,
                    (category,),
                )
                docs = dict(cur.fetchone() or {})
                cur.execute(
                    """
                    select count(*)::int as with_model
                    from product_clusters pc
                    where exists (
                      select 1 from platform_listings pl
                      where pl.product_id = pc.id and pl.match_status = 'matched' and pl.category = %s
                    )
                      and jsonb_typeof(pc.specs->'model_codes') = 'array'
                      and jsonb_array_length(pc.specs->'model_codes') > 0
                    """,
                    (category,),
                )
                model = dict(cur.fetchone() or {})
                categories[category] = {
                    **public,
                    **listings,
                    **docs,
                    **model,
                    "note": "public_* metrics exclude orphan search documents",
                }

            cur.execute(
                """
                with m as (
                  select product_id, array_agg(distinct platform order by platform) as plats
                  from platform_listings
                  where match_status = 'matched' and product_id is not null
                  group by product_id
                  having count(distinct platform) >= 2
                )
                select plats::text as pair, count(*)::int as n
                from m
                group by 1
                order by n desc
                limit 20
                """
            )
            pairs = [dict(r) for r in cur.fetchall()]

    return {
        "categories": categories,
        "retailer_pairs": pairs,
        "include_orphans_documented": include_orphans,
    }


__all__ = ["catalog_quality_report"]
