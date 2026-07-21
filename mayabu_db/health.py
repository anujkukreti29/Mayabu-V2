from __future__ import annotations

import argparse
from decimal import Decimal
from typing import Any

from psycopg import sql

from mayabu_db.connection import db_connection

_HEALTH_COUNT_TABLES = (
    "product_clusters",
    "platform_listings",
    "price_observations",
    "scrape_tasks",
    "scrape_runs",
    "review_queue",
    "anomaly_events",
)


def _num(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def health_summary() -> dict[str, Any]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            result: dict[str, Any] = {}
            for table in _HEALTH_COUNT_TABLES:
                query = sql.SQL("select count(*) as count from {}").format(sql.Identifier(table))
                cur.execute(query)
                result[table] = cur.fetchone()["count"]
            cur.execute(
                """
                select platform, status, count(*) as count
                from scrape_tasks
                group by platform, status
                order by platform, status
                """
            )
            result["tasks_by_status"] = cur.fetchall()
            cur.execute(
                """
                select platform, status, count(*) as runs, max(started_at) as last_run
                from scrape_runs
                group by platform, status
                order by platform, status
                """
            )
            result["runs_by_status"] = cur.fetchall()
            cur.execute(
                """
                select severity, event_type, count(*) as count
                from anomaly_events
                where status = 'open'
                group by severity, event_type
                order by case severity when 'critical' then 1 when 'high' then 2 when 'medium' then 3 else 4 end, count(*) desc
                limit 20
                """
            )
            result["open_anomalies"] = cur.fetchall()
            return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Print Mayabu DB health summary")
    parser.parse_args()
    summary = health_summary()
    for key, value in summary.items():
        print(f"\n{key}:")
        if isinstance(value, list):
            for row in value:
                print("  ", {k: _num(v) for k, v in row.items()})
        else:
            print("  ", _num(value))


if __name__ == "__main__":
    main()
