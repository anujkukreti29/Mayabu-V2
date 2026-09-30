"""Cap Amazon/Croma discovery to a tiny probe for one category."""
import sys

from psycopg.types.json import Jsonb

from mayabu_db.connection import db_connection

CATEGORY = sys.argv[1]
KEEP = {
    "amazon": {
        "laptop": {"macbook air", "gaming laptop", "dell g15"},
        "smartphone": {"iphone 16", "galaxy s24", "oneplus nord"},
        "television": {"samsung 55 inch tv", "lg oled tv", "sony bravia"},
        "refrigerator": {"samsung refrigerator", "lg refrigerator"},
        "washing_machine": {"front load washing machine", "lg washing machine"},
        "tws": {"apple airpods", "galaxy buds"},
        "headphones": {"sony headphones", "bose headphones"},
        "camera": {"sony alpha", "canon eos"},
    },
    "croma": {
        "laptop": {"macbook air", "hp victus", "lenovo loq"},
        "smartphone": {"iphone 16", "galaxy s24", "nothing phone"},
        "television": {"samsung 55 inch tv", "lg oled tv", "sony bravia"},
        "refrigerator": {"samsung refrigerator", "lg refrigerator"},
        "washing_machine": {"front load washing machine", "lg washing machine"},
        "tws": {"apple airpods", "galaxy buds"},
        "headphones": {"sony headphones", "bose headphones"},
        "camera": {"sony alpha", "canon eos"},
    },
}

with db_connection() as conn, conn.cursor() as cur:
    for platform in ("amazon", "croma"):
        queries = KEEP[platform].get(CATEGORY, set())
        cur.execute(
            """
            update scheduler_plans
            set last_materialized_at = now(),
                updated_at = now(),
                metadata = coalesce(metadata, '{}'::jsonb) || %s::jsonb
            where coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
              and coalesce(metadata->>'category','') = %s
              and platform = %s
              and last_materialized_at is null
              and lower(query) <> all(%s)
            """,
            (
                Jsonb({"completion": "limited_budget_held", "error_state": "amazon_croma_limited"}),
                CATEGORY,
                platform,
                list(queries) or ["__none__"],
            ),
        )
        print(platform, "held", cur.rowcount)
