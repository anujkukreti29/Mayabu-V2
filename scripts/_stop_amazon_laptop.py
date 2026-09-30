"""Stop pending Amazon catalog-expansion tasks while the circuit is open."""
from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        update scrape_tasks
        set status = 'dead',
            last_error = 'circuit_blocked',
            locked_at = null,
            locked_by = null,
            lease_expires_at = null,
            updated_at = now()
        where created_by = 'catalog_expansion'
          and platform = 'amazon'
          and status in ('pending', 'running')
        returning query
        """
    )
    rows = cur.fetchall()
    print("killed", [row["query"] for row in rows])
    cur.execute(
        """
        update scheduler_plans
        set metadata = coalesce(metadata, '{}'::jsonb) || '{"completion":"circuit_blocked","error_state":"discovery_not_allowed"}'::jsonb,
            updated_at = now()
        where coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
          and coalesce(metadata->>'category','') = 'laptop'
          and platform = 'amazon'
          and coalesce(metadata->>'completion','') not in ('saturated')
        """
    )
    print("plans_blocked", cur.rowcount)
