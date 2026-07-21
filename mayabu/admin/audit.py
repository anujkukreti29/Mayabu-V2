"""Immutable audit trail for privileged Mayabu mutations."""

from __future__ import annotations

from typing import Any

from psycopg import Connection
from psycopg.types.json import Jsonb

from mayabu.core.config import get_app_settings
from mayabu.core.logging import get_request_id
from mayabu.core.security import hash_identifier
from mayabu.db.connection import db_connection


def _insert(conn: Connection, action: str, target_type: str | None, target_id: str | None, details: dict[str, Any]) -> None:
    actor_hash = hash_identifier(get_app_settings().admin_token, salt="mayabu-admin")
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into admin_audit_log(action, actor_hash, target_type, target_id, request_id, details)
            values (%s,%s,%s,%s,%s,%s)
            """,
            (action, actor_hash, target_type, target_id, get_request_id(), Jsonb(details or {})),
        )


def record_admin_action(
    action: str,
    *,
    target_type: str | None = None,
    target_id: str | None = None,
    details: dict[str, Any] | None = None,
    conn: Connection | None = None,
) -> None:
    if conn is not None:
        _insert(conn, action, target_type, target_id, details or {})
        return
    with db_connection() as owned:
        _insert(owned, action, target_type, target_id, details or {})


def list_admin_actions(limit: int = 100) -> list[dict[str, Any]]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, action, actor_hash, target_type, target_id, request_id, details, created_at
                from admin_audit_log
                order by created_at desc
                limit %s
                """,
                (max(1, min(int(limit), 1000)),),
            )
            return cur.fetchall()
