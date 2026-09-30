"""Close empty continuation tasks that were retried instead of finished."""
from mayabu.scheduler.discovery_cursor import persist_plan_cursor
from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select id::text, query, metadata
        from scrape_tasks
        where created_by = 'catalog_depth'
          and platform = 'flipkart'
          and status = 'pending'
          and coalesce(last_error, '') = 'empty'
          and coalesce((metadata->>'start_page')::int, 1) > 1
        """
    )
    rows = list(cur.fetchall())

for row in rows:
    meta = row["metadata"] or {}
    plan_id = str(meta.get("scheduler_plan_id") or "")
    start = int(meta.get("start_page") or 1)
    if plan_id:
        persist_plan_cursor(
            plan_id,
            last_page=start,
            listings_found=0,
            stop_reason="empty_page",
            new_ids=0,
            duplicate_ids=0,
        )
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            update scrape_tasks
            set status = 'completed',
                last_error = null,
                locked_at = null,
                locked_by = null,
                lease_expires_at = null,
                updated_at = now()
            where id = %s and status = 'pending'
            """,
            (row["id"],),
        )
    print("closed", row["query"], "page", start)
