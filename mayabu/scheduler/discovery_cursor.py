"""Incremental discovery page checkpoints.

Adapters that accept ``start_page`` continue from persisted
``scheduler_plans.metadata.cursor.last_page``. Checkpoints survive process
restart because they live in PostgreSQL, not Redis.

Adapters without a page cursor (Croma click-budget, some PIM landings) keep
bounded page-1/click discovery. Those limitations are recorded on the cursor
rather than faked as incrementality.
"""

from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from mayabu.db.connection import db_connection
from mayabu.scrapers.page_saturation import EMERGENCY_PAGE, natural_stop

# Healthy Flipkart and Reliance discovery may continue until saturation.
# This value is the emergency ceiling, not the expected stop.
MAX_ROTATION_PAGE = EMERGENCY_PAGE
PAGE_CURSOR_ADAPTERS = frozenset({"amazon", "flipkart", "reliancedigital", "poorvika", "vijaysales"})


def start_page_from_metadata(metadata: Any) -> int:
    cursor = metadata.get("cursor") if isinstance(metadata, dict) else None
    if not isinstance(cursor, dict):
        return 1
    try:
        last_page = int(cursor.get("last_page") or 0)
    except (TypeError, ValueError):
        last_page = 0
    nxt = last_page + 1
    if nxt > MAX_ROTATION_PAGE:
        return 1
    return max(1, nxt)


def supports_page_cursor(platform: str) -> bool:
    return str(platform or "").strip().lower() in PAGE_CURSOR_ADAPTERS


def persist_plan_cursor(
    plan_id: str,
    *,
    last_page: int,
    listings_found: int | None = None,
    mode: str = "page_offset",
    stop_reason: str = "",
    new_ids: int | None = None,
    duplicate_ids: int | None = None,
    consecutive_no_new: int | None = None,
) -> None:
    payload = {
        "last_page": max(1, int(last_page)),
        "listings_found": listings_found,
        "mode": mode,
        "stop_reason": stop_reason or "",
        "new_ids": new_ids,
        "duplicate_ids": duplicate_ids,
        "consecutive_no_new": consecutive_no_new,
    }
    completion = {}
    if natural_stop(stop_reason):
        completion = {"completion": "saturated", "stop_reason": stop_reason}
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update scheduler_plans
                set metadata = jsonb_set(
                      coalesce(metadata, '{}'::jsonb) || %s::jsonb,
                      '{cursor}',
                      %s::jsonb,
                      true
                    ),
                    updated_at = now()
                where id = %s
                """,
                (Jsonb(completion), Jsonb(payload), plan_id),
            )
