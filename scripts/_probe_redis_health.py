"""One-off Redis-down + schema probe for staging readiness evidence."""

from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu",
)
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")

from mayabu.core.config import get_app_settings
from mayabu.db.connection import close_connection_pool, db_connection
from mayabu.monitoring import health as health_mod
from mayabu.search import cache as cache_mod

get_app_settings.cache_clear()
close_connection_pool()

with db_connection() as conn, conn.cursor() as cur:
    cur.execute("select current_database() as d")
    print("database", dict(cur.fetchone() or {}))
    cur.execute(
        """
        select table_name
        from information_schema.tables
        where table_schema = 'public'
          and table_name = any(%s)
        order by 1
        """,
        (["user_wishlist", "watch_events", "product_images"],),
    )
    print("required_tables", [r["table_name"] for r in cur.fetchall()])

schema = health_mod._schema_integrity()
print("schema", schema.get("status"), schema.get("missing"))


class DeadCache:
    enabled = True

    def ping(self) -> bool:
        return False


orig = cache_mod.get_cache
health_mod.get_cache = lambda: DeadCache()  # type: ignore[assignment]
cache_mod.get_cache = lambda: DeadCache()  # type: ignore[assignment]
try:
    data = health_mod.collect_health()
    ready = health_mod.readiness()
    print("redis", data.get("redis"))
    print("status", data.get("status"))
    print("degraded", data.get("degraded_reasons"))
    print("ready", ready.get("ready"), ready.get("status"), ready.get("not_ready_reason"))
finally:
    cache_mod.get_cache = orig
    health_mod.get_cache = orig  # type: ignore[assignment]
