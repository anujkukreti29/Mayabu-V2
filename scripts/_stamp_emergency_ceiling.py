"""Stamp emergency_ceiling on plans that already reached page 40 with a blank reason.

Does not change last_page and skips plans with a task still in flight.
"""

from psycopg.types.json import Jsonb

from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        update scheduler_plans p
        set metadata = jsonb_set(
              coalesce(metadata, '{}'::jsonb) || %s::jsonb,
              '{cursor,stop_reason}',
              '"emergency_ceiling"'::jsonb,
              true
            ),
            updated_at = now()
        where coalesce((metadata#>>'{cursor,last_page}')::int, 0) >= 40
          and coalesce(metadata#>>'{cursor,stop_reason}','') in ('', 'page_budget', 'product_budget')
          and not exists (
            select 1 from scrape_tasks t
            where t.idempotency_key = 'discovery:' || p.id::text
              and t.status in ('pending','running','paused')
          )
        returning name
        """,
        (Jsonb({"completion": "saturated", "stop_reason": "emergency_ceiling"}),),
    )
    rows = cur.fetchall()
    for row in rows:
        print(row["name"])
    print("stamped", len(rows))
