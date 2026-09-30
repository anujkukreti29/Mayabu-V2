"""Drop Flipkart capacity slots left by killed workers and unstick deferred tasks."""
from mayabu.search.cache import get_cache
from mayabu.core.distributed_limit import _slot_key
from mayabu_db.connection import db_connection

key = _slot_key("scrape-platform", "flipkart")
client = get_cache().coordination_client()
if client is None:
    raise SystemExit("no redis")
before = client.zcard(key)
client.delete(key)
print("cleared", key, "members", before)
with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        update scrape_tasks
        set scheduled_at = now(), updated_at = now()
        where created_by = 'catalog_depth'
          and platform = 'flipkart'
          and status = 'pending'
        returning query
        """
    )
    print("unstuck", [r["query"] for r in cur.fetchall()])
