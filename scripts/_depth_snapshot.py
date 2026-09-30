import json
from collections import Counter

from mayabu.domain.matching_golden import score_golden
from mayabu_db.connection import db_connection

CATS = ["laptop","smartphone","television","refrigerator","washing_machine","tws","headphones","camera"]
out = {"golden": score_golden()}
with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select d.category,
               count(*)::int products,
               count(*) filter (where d.best_price > 0)::int priced,
               count(*) filter (where coalesce(d.platform_count,0) = 1)::int one_store,
               count(*) filter (where coalesce(d.platform_count,0) >= 2)::int ge2,
               count(*) filter (where coalesce(d.platform_count,0) >= 3)::int ge3,
               count(*) filter (where coalesce(d.platform_count,0) >= 4)::int ge4,
               count(*) filter (where coalesce(d.platform_count,0) >= 5)::int ge5
        from product_search_documents d
        join product_clusters c on c.id = d.product_id and c.status = 'active'
        where d.category = any(%s)
        group by 1 order by 1
        """,
        (CATS,),
    )
    out["categories"] = [dict(r) for r in cur.fetchall()]
    cur.execute("select count(*)::int n from search_document_dirty")
    out["dirty"] = cur.fetchone()["n"]
    cur.execute(
        """
        select count(*)::int n from product_search_documents
        where offer_count is distinct from platform_count
        """
    )
    out["offer_mismatch"] = cur.fetchone()["n"]
    cur.execute(
        """
        select match_status, count(*)::int n
        from platform_listings
        where category = any(%s)
        group by 1 order by n desc
        """,
        (CATS,),
    )
    out["match"] = [dict(r) for r in cur.fetchall()]
    cur.execute("select count(*)::int n from platform_listings where category = 'unknown'")
    out["unknown"] = cur.fetchone()["n"]
    cur.execute("select count(*)::int n from platform_listings where category = 'accessory'")
    out["accessory"] = cur.fetchone()["n"]
    cur.execute(
        """
        select platform,
               count(*) filter (where coalesce(metadata->>'completion','') = 'saturated')::int saturated,
               count(*) filter (where coalesce((metadata#>>'{cursor,last_page}')::int,0) > 8)::int past_8,
               max(coalesce((metadata#>>'{cursor,last_page}')::int,0))::int max_page
        from scheduler_plans
        where coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
          and platform in ('flipkart','reliancedigital')
        group by 1
        """
    )
    out["depth"] = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        select status, count(*)::int n
        from scrape_tasks
        where coalesce(metadata->>'purpose','') in ('catalog_depth_v2','catalog_overlap_v2')
           or created_by in ('catalog_depth','catalog_overlap')
        group by 1
        """
    )
    out["depth_tasks"] = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        select coalesce(metadata#>>'{cursor,stop_reason}','') reason, count(*)::int n,
               coalesce(sum((metadata#>>'{cursor,new_ids}')::int),0)::int new_ids
        from scheduler_plans
        where platform = 'flipkart' and coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
        group by 1
        """
    )
    out["flipkart_stops"] = [dict(r) for r in cur.fetchall()]
print(json.dumps(out, default=str, indent=2))
