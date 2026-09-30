"""Compatibility wrapper around Mayabu's resilient database pool."""

from mayabu_db.connection import (
    close_connection_pool,
    db_connection,
    get_connection_pool,
    open_session_connection,
    pool_stats,
)

__all__ = [
    "db_connection",
    "get_connection_pool",
    "close_connection_pool",
    "open_session_connection",
    "pool_stats",
]
