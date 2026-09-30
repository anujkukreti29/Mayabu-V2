"""Per-category public product image gallery coverage report."""

from __future__ import annotations

import json
import sys

from mayabu.db.connection import db_connection

PUBLIC_CATEGORIES = (
    "smartphone",
    "laptop",
    "television",
    "refrigerator",
    "washing_machine",
    "tws",
    "headphones",
    "camera",
)


def report() -> dict:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                with public_docs as (
                  select d.product_id, d.category
                  from product_search_documents d
                  where d.category = any(%s)
                ),
                gallery as (
                  select pi.product_id, count(*)::int as n
                  from product_images pi
                  where pi.active
                  group by pi.product_id
                ),
                joined as (
                  select
                    p.category,
                    p.product_id,
                    greatest(coalesce(g.n, 0), case when d.image_url is not null and length(trim(d.image_url)) > 8 then 1 else 0 end) as img_n
                  from public_docs p
                  left join gallery g on g.product_id = p.product_id
                  left join product_search_documents d on d.product_id = p.product_id
                )
                select
                  category,
                  count(*)::int as total,
                  count(*) filter (where img_n >= 1)::int as ge1,
                  count(*) filter (where img_n >= 2)::int as ge2,
                  count(*) filter (where img_n >= 4)::int as ge4,
                  count(*) filter (where img_n >= 6)::int as ge6,
                  percentile_cont(0.5) within group (order by img_n)::float as median_gallery
                from joined
                group by category
                order by category
                """,
                (list(PUBLIC_CATEGORIES),),
            )
            rows = [dict(r) for r in cur.fetchall()]
    return {"categories": rows}


if __name__ == "__main__":
    out = report()
    json.dump(out, sys.stdout, indent=2)
    print()
