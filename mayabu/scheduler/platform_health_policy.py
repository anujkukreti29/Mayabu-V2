"""Platform health policy helpers."""

from __future__ import annotations

from mayabu.db.connection import db_connection
from mayabu_common import canonical_platform


def get_platform_status(platform: str) -> str:
    platform = canonical_platform(platform)
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select status from platform_health where platform = %s", (platform,))
            row = cur.fetchone()
            return str(row["status"]) if row else "healthy"


def platform_allows_task(platform: str, task_type: str) -> bool:
    status = get_platform_status(platform)
    if status == "paused":
        return False
    if status == "blocked":
        return False
    if status == "degraded" and task_type != "refresh_listing":
        return False
    return True
