"""Resilient process-wide PostgreSQL connection pool for Mayabu v5."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from threading import Lock
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout

from mayabu_db.config import get_settings

logger = logging.getLogger(__name__)
_pool_lock = Lock()
_pool: ConnectionPool | None = None
_pool_dsn: str | None = None


def _configure_connection(conn: psycopg.Connection) -> None:
    """Set per-session guardrails once when a pooled connection is created."""
    settings = get_settings()
    with conn.cursor() as cur:
        cur.execute("set application_name = 'mayabu-v5'")
        cur.execute("select set_config('statement_timeout', %s, false)", (f"{settings.db_statement_timeout_ms}ms",))
        cur.execute("select set_config('idle_in_transaction_session_timeout', '30s', false)")
        cur.execute("select set_config('lock_timeout', '5s', false)")
    conn.commit()


def get_connection_pool() -> ConnectionPool:
    global _pool, _pool_dsn
    settings = get_settings()
    dsn = settings.database_url

    with _pool_lock:
        if _pool is not None and _pool_dsn == dsn:
            return _pool
        if _pool is not None:
            try:
                _pool.close()
            except Exception:
                logger.exception("db_pool_close_failed")

        _pool = ConnectionPool(
            conninfo=dsn,
            min_size=settings.db_pool_min_size,
            max_size=settings.db_pool_max_size,
            timeout=settings.db_pool_timeout_seconds,
            max_waiting=settings.db_pool_max_waiting,
            max_lifetime=settings.db_pool_max_lifetime_seconds,
            max_idle=settings.db_pool_max_idle_seconds,
            reconnect_timeout=30,
            kwargs={
                "row_factory": dict_row,
                "connect_timeout": settings.db_connect_timeout_seconds,
            },
            configure=_configure_connection,
            check=ConnectionPool.check_connection,
            name="mayabu-postgres-pool-v5",
            open=True,
        )
        _pool_dsn = dsn
        return _pool


def pool_stats() -> dict[str, Any]:
    pool = get_connection_pool()
    try:
        return dict(pool.get_stats())
    except Exception:
        return {"pool_available": True}


def close_connection_pool() -> None:
    global _pool, _pool_dsn
    with _pool_lock:
        if _pool is not None:
            _pool.close()
        _pool = None
        _pool_dsn = None


@contextmanager
def db_connection(autocommit: bool = False) -> Iterator[psycopg.Connection]:
    """Borrow a healthy connection and return it in a clean transaction state.

    Pool exhaustion fails quickly with a clear message instead of letting every
    request hang for thirty seconds. Callers may retry at the job/CLI boundary.
    """
    pool = get_connection_pool()
    try:
        with pool.connection(timeout=get_settings().db_pool_timeout_seconds) as conn:
            previous_autocommit = conn.autocommit
            if previous_autocommit != autocommit:
                conn.autocommit = autocommit
            try:
                yield conn
                if not autocommit:
                    conn.commit()
            except Exception:
                if not autocommit:
                    conn.rollback()
                raise
            finally:
                if conn.autocommit != previous_autocommit:
                    conn.autocommit = previous_autocommit
    except PoolTimeout as exc:
        stats = pool_stats()
        raise RuntimeError(f"Mayabu database pool is exhausted or PostgreSQL is unavailable. pool={stats}") from exc
