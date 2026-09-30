"""Stamp saturated Flipkart plans that ended on an empty continuation page."""
from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        update scheduler_plans p
        set metadata = jsonb_set(
                jsonb_set(p.metadata, '{cursor,stop_reason}', '"empty_page"'),
                '{completion}', '"saturated"'
            ),
            updated_at = now()
        where p.platform = 'flipkart'
          and coalesce(p.metadata->>'purpose','') = 'catalog_expansion_v1'
          and coalesce(p.metadata#>>'{cursor,stop_reason}','') = ''
          and coalesce(p.metadata->>'completion','') = 'saturated'
          and coalesce((p.metadata#>>'{cursor,last_page}')::int, 0) < 40
          and exists (
              select 1 from scrape_tasks t
              where t.platform = 'flipkart'
                and t.created_by = 'catalog_depth'
                and t.query = p.query
                and t.status in ('dead', 'completed')
                and coalesce(t.last_error, '') in ('empty', '')
          )
        returning p.query
        """
    )
    print("stamped", [r["query"] for r in cur.fetchall()])
