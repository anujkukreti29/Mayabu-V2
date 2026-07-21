"""Compatibility settings facade for database-first modules.

New code should use :mod:`mayabu.core.config`. Existing modules keep importing
``mayabu_db.config.get_settings`` without needing a rewrite.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from mayabu.core.config import get_app_settings


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_or_none(name: str) -> int | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None
    return int(value)


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    db_schema: str
    worker_id: str
    raw_artifact_dir: Path
    debug_artifact_dir: Path
    headless: bool
    max_pages: int
    max_products: int | None
    croma_headless: bool | None
    db_pool_min_size: int
    db_pool_max_size: int
    db_pool_timeout_seconds: float
    db_pool_max_waiting: int
    db_pool_max_lifetime_seconds: int
    db_pool_max_idle_seconds: int
    db_connect_timeout_seconds: int
    db_statement_timeout_ms: int

    def validate(self) -> None:
        get_app_settings().validate()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    app = get_app_settings()
    settings = Settings(
        database_url=app.database_url,
        db_schema=os.getenv("MAYABU_DB_SCHEMA", "public"),
        worker_id=app.worker_id,
        raw_artifact_dir=Path(os.getenv("MAYABU_RAW_ARTIFACT_DIR", "artifacts/raw")),
        debug_artifact_dir=Path(os.getenv("MAYABU_DEBUG_ARTIFACT_DIR", "artifacts/debug")),
        headless=_bool("MAYABU_HEADLESS", True),
        max_pages=int(os.getenv("MAYABU_MAX_PAGES", "2")),
        max_products=_int_or_none("MAYABU_MAX_PRODUCTS"),
        croma_headless=None if os.getenv("MAYABU_CROMA_HEADLESS") is None else _bool("MAYABU_CROMA_HEADLESS", True),
        db_pool_min_size=app.db_pool_min_size,
        db_pool_max_size=app.db_pool_max_size,
        db_pool_timeout_seconds=app.db_pool_timeout_seconds,
        db_pool_max_waiting=app.db_pool_max_waiting,
        db_pool_max_lifetime_seconds=app.db_pool_max_lifetime_seconds,
        db_pool_max_idle_seconds=app.db_pool_max_idle_seconds,
        db_connect_timeout_seconds=app.db_connect_timeout_seconds,
        db_statement_timeout_ms=app.db_statement_timeout_ms,
    )
    settings.validate()
    settings.raw_artifact_dir.mkdir(parents=True, exist_ok=True)
    settings.debug_artifact_dir.mkdir(parents=True, exist_ok=True)
    return settings
