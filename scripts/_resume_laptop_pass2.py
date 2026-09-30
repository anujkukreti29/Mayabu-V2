"""Resume laptop discovery after the interrupted first pass.

Re-queues Flipkart and Reliance plans that stopped on the shallow
product cap. Leaves Amazon and Croma unqueued: both are discovery-blocked
and this campaign does not clear circuits.
"""

from psycopg.types.json import Jsonb

from mayabu_db.connection import db_connection

SHALLOW = Jsonb({"completion": "pass2_after_shallow_cap", "pass": 2})
STOPPED = Jsonb(
    {
        "completion": "circuit_blocked",
        "error_state": "discovery_not_allowed",
    }
)

with db_connection() as conn, conn.cursor() as cur:
    cur.execute("select current_database() db")
    db = cur.fetchone()["db"]
    if db != "mayabu":
        raise SystemExit(f"refusing database {db}")

    cur.execute(
        """
        update scheduler_plans
        set last_materialized_at = now(),
            updated_at = now(),
            metadata = coalesce(metadata, '{}'::jsonb) || %s::jsonb
        where coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
          and coalesce(metadata->>'category','') = 'laptop'
          and platform in ('amazon', 'croma')
          and last_materialized_at is null
        """,
        (STOPPED,),
    )
    print("circuit_stopped", cur.rowcount)

    cur.execute(
        """
        update scheduler_plans sp
        set last_materialized_at = null,
            updated_at = now(),
            max_pages = case sp.platform when 'flipkart' then 8 else 8 end,
            max_products = case sp.platform when 'flipkart' then 160 else 96 end,
            metadata = jsonb_set(
                coalesce(sp.metadata, '{}'::jsonb) || %s::jsonb,
                '{cursor}',
                '{"last_page": 0, "mode": "page_offset"}'::jsonb,
                true
            )
        where coalesce(sp.metadata->>'purpose','') = 'catalog_expansion_v1'
          and coalesce(sp.metadata->>'category','') = 'laptop'
          and sp.platform in ('flipkart', 'reliancedigital')
          and exists (
            select 1 from scrape_tasks t
            where t.metadata->>'scheduler_plan_id' = sp.id::text
              and t.max_pages = 4
              and t.status in ('completed', 'dead')
              and t.created_by = 'catalog_expansion'
          )
          and not exists (
            select 1 from scrape_tasks t
            where t.metadata->>'scheduler_plan_id' = sp.id::text
              and t.max_pages >= 8
              and t.status = 'completed'
              and t.created_by = 'catalog_expansion'
          )
        """,
        (SHALLOW,),
    )
    print("requeued_shallow", cur.rowcount)

    cur.execute(
        """
        select platform,
               count(*) filter (where last_materialized_at is null)::int waiting,
               count(*) filter (where metadata->>'completion' = 'circuit_blocked')::int blocked
        from scheduler_plans
        where coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
          and coalesce(metadata->>'category','') = 'laptop'
        group by 1
        order by 1
        """
    )
    for row in cur.fetchall():
        print(dict(row))
