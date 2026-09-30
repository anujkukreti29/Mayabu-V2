"""Archive the one recovered Galaxy Tab that was stored as a smartphone."""

from psycopg.types.json import Jsonb

from mayabu.domain.phone_recovery import phone_recovery_verdict
from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select c.id, c.canonical_title, l.id as listing_uuid
        from platform_listings l
        join product_clusters c on c.id = l.product_id
        where coalesce(l.match_evidence->>'auto_resolution','') = 'unknown_recovered'
          and c.category = 'smartphone'
          and c.status = 'active'
        """
    )
    rows = list(cur.fetchall())

ids = []
for row in rows:
    if phone_recovery_verdict(row["canonical_title"] or "") != "wrong_category":
        continue
    ids.append(str(row["id"]))
    print("unpublish", row["canonical_title"][:80])

if ids:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            update product_clusters
            set status = 'archived', updated_at = now()
            where id = any(%s::uuid[])
            """,
            (ids,),
        )
        cur.execute(
            """
            update platform_listings
            set match_status = 'rejected',
                product_id = null,
                match_evidence = coalesce(match_evidence, '{}'::jsonb) || %s::jsonb,
                updated_at = now()
            where product_id = any(%s::uuid[])
            """,
            (Jsonb({"auto_resolution": "recovered_not_smartphone"}), ids),
        )
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "delete from product_search_documents where product_id = any(%s::uuid[])",
            (ids,),
        )
print("count", len(ids))
