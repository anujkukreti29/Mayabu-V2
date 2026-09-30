from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        update scheduler_plans
        set metadata = jsonb_set(
                metadata,
                '{cursor,stop_reason}',
                to_jsonb(metadata->>'stop_reason'),
                true
            ),
            updated_at = now()
        where platform = 'flipkart'
          and coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
          and coalesce(metadata->>'stop_reason','') <> ''
          and coalesce(metadata#>>'{cursor,stop_reason}','') = ''
        returning query, metadata->>'stop_reason'
        """
    )
    print("cursor", [dict(r) for r in cur.fetchall()])
    cur.execute(
        """
        update scrape_tasks t
        set status = 'completed', last_error = null, updated_at = now()
        where t.created_by = 'catalog_depth'
          and t.platform = 'flipkart'
          and t.status = 'pending'
          and coalesce(t.last_error, '') = 'empty'
          and exists (
            select 1 from scheduler_plans p
            where p.id::text = t.metadata->>'scheduler_plan_id'
              and coalesce(p.metadata->>'completion','') = 'saturated'
          )
        returning t.query
        """
    )
    print("closed", [r["query"] for r in cur.fetchall()])
