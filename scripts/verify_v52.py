"""Verify a live Mayabu v5.2 database and API schema."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mayabu import __version__  # noqa: E402
from mayabu.api.main import app  # noqa: E402
from mayabu.db.connection import db_connection, pool_stats  # noqa: E402

REQUIRED_COLUMNS = (
    "last_verification_attempt_at",
    "last_verified_at",
    "verification_status",
    "verification_source",
    "next_allowed_verification_at",
    "consecutive_verification_failures",
)


def main() -> None:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select column_name from information_schema.columns
                where table_schema='public' and table_name='platform_listings'
                  and column_name = any(%s::text[])
                """,
                (list(REQUIRED_COLUMNS),),
            )
            columns = {row["column_name"] for row in cur.fetchall()}
            cur.execute("select to_regclass('public.live_verification_events') is not null as present")
            events_table = bool(cur.fetchone()["present"])
            cur.execute(
                """
                select indexname from pg_indexes
                where schemaname='public' and indexname in (
                  'idx_platform_listings_verification_due',
                  'idx_scrape_tasks_live_verification_active',
                  'idx_live_verification_events_created_at'
                )
                """
            )
            indexes = {row["indexname"] for row in cur.fetchall()}
    paths = app.openapi()["paths"]
    required_paths = {
        "/api/products/{product_id}/verify-price",
        "/api/verification-jobs/{task_id}",
        "/api/products/{product_id}/verification-status",
    }
    result = {
        "ok": set(REQUIRED_COLUMNS) == columns and events_table and len(indexes) == 3 and required_paths.issubset(paths),
        "version": __version__,
        "columns": sorted(columns),
        "events_table": events_table,
        "indexes": sorted(indexes),
        "verification_paths": sorted(required_paths.intersection(paths)),
        "pool": pool_stats(),
    }
    print(json.dumps(result, indent=2, default=str))
    if not result["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
