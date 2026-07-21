"""Scrape budget policy helpers."""

from __future__ import annotations

from psycopg import sql

from mayabu.db.connection import db_connection
from mayabu_common import canonical_platform

DEFAULT_DAILY_BUDGETS = {
    "amazon": {"discovery": 100, "refresh": 500},
    "flipkart": {"discovery": 150, "refresh": 800},
    "croma": {"discovery": 100, "refresh": 300},
    "reliancedigital": {"discovery": 100, "refresh": 500},
}

_BUDGET_COLUMNS = {
    "discovery": ("discovery_used", "discovery_budget"),
    "refresh": ("refresh_used", "refresh_budget"),
}


def _budget_columns(task_type: str) -> tuple[str, str]:
    kind = "refresh" if str(task_type).startswith("refresh") else "discovery"
    return _BUDGET_COLUMNS[kind]


def ensure_today_budget(platform: str) -> None:
    platform = canonical_platform(platform)
    budget = DEFAULT_DAILY_BUDGETS[platform]
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into scrape_budget(platform, budget_date, discovery_budget, refresh_budget)
                values (%s, current_date, %s, %s)
                on conflict (platform, budget_date) do nothing
                """,
                (platform, budget["discovery"], budget["refresh"]),
            )


def budget_available(platform: str, task_type: str) -> bool:
    platform = canonical_platform(platform)
    ensure_today_budget(platform)
    field_used, field_budget = _budget_columns(task_type)
    query = sql.SQL(
        "select {used} < {budget} as ok "
        "from scrape_budget where platform = %s and budget_date = current_date"
    ).format(used=sql.Identifier(field_used), budget=sql.Identifier(field_budget))
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (platform,))
            row = cur.fetchone()
            return bool(row and row["ok"])


def consume_budget(conn, platform: str, task_type: str, amount: int = 1) -> None:
    platform = canonical_platform(platform)
    used_col, _ = _budget_columns(task_type)
    query = sql.SQL(
        "update scrape_budget set {used} = {used} + %s, updated_at = now() "
        "where platform = %s and budget_date = current_date"
    ).format(used=sql.Identifier(used_col))
    with conn.cursor() as cur:
        cur.execute(query, (amount, platform))


def try_consume_budget(conn, platform: str, task_type: str, amount: int = 1) -> bool:
    """Atomically consume budget for an execution attempt."""
    platform = canonical_platform(platform)
    used_col, budget_col = _budget_columns(task_type)
    query = sql.SQL(
        """
        update scrape_budget
        set {used} = {used} + %s, updated_at = now()
        where platform = %s
          and budget_date = current_date
          and {used} + %s <= {budget}
        returning id
        """
    ).format(used=sql.Identifier(used_col), budget=sql.Identifier(budget_col))
    with conn.cursor() as cur:
        cur.execute(query, (amount, platform, amount))
        return cur.fetchone() is not None
