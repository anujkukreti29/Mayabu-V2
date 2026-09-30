"""Keep Amazon/Croma laptop discovery to a tiny exact probe set."""
from psycopg.types.json import Jsonb

from mayabu_db.connection import db_connection

KEEP = {
    "amazon": {"macbook air", "gaming laptop", "dell g15"},
    "croma": {"macbook air", "hp victus", "lenovo loq"},
}

with db_connection() as conn, conn.cursor() as cur:
    for platform, queries in KEEP.items():
        cur.execute(
            """
            update scheduler_plans
            set last_materialized_at = now(),
                updated_at = now(),
                metadata = coalesce(metadata, '{}'::jsonb) || %s::jsonb
            where coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
              and coalesce(metadata->>'category','') = 'laptop'
              and platform = %s
              and last_materialized_at is null
              and lower(query) <> all(%s)
            """,
            (
                Jsonb({"completion": "limited_budget_held", "error_state": "amazon_croma_limited"}),
                platform,
                list(queries),
            ),
        )
        print(platform, "held", cur.rowcount)
    cur.execute(
        """
        update scrape_tasks
        set status = 'dead', last_error = 'limited_budget_held', updated_at = now()
        where created_by = 'catalog_expansion'
          and platform in ('amazon','croma')
          and status in ('pending','running')
          and lower(query) <> all(%s)
        """,
        (list(KEEP["amazon"] | KEEP["croma"]),),
    )
    print("cancelled_tasks", cur.rowcount)
