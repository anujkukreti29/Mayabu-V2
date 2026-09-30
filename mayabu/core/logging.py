"""Small structured JSON logger with request correlation."""

from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("mayabu_request_id", default=None)


def set_request_id(value: str | None) -> contextvars.Token:
    return _request_id.set(value)


def reset_request_id(token: contextvars.Token) -> None:
    _request_id.reset(token)


def get_request_id() -> str | None:
    return _request_id.get()


class JsonFormatter(logging.Formatter):
    _SECRET_KEYS = (
        "password",
        "passwd",
        "secret",
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "token",
        "csrf",
        "database_url",
        "redis_url",
    )

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, dict):
            cleaned: dict[str, Any] = {}
            for key, item in value.items():
                if any(s in str(key).lower() for s in self._SECRET_KEYS):
                    cleaned[key] = "[redacted]"
                else:
                    cleaned[key] = self._sanitize(item)
            return cleaned
        if isinstance(value, str):
            lowered = value.lower()
            if "password=" in lowered or "api_key=" in lowered or "bearer " in lowered:
                return "[redacted]"
            return value
        return value

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = get_request_id()
        if request_id:
            payload["request_id"] = request_id
        for key in (
            "event",
            "duration_ms",
            "platform",
            "task_id",
            "task_type",
            "category",
            "product_id",
            "status_code",
            "status",
            "error",
            "route",
            "method",
            "operation",
            "search_mode",
            "search_relation",
            "api_workers",
            "api_threadpool_tokens",
            "db_pool_max_size",
            "environment",
            "redis_cache_enabled",
            "redis_rate_limit_enabled",
            "run_id",
            "release_version",
            "git_sha",
            "email_delivered",
            "kind",
            "result",
            "api_key",
            "token",
            "password",
        ):
            if hasattr(record, key):
                payload[key] = self._sanitize(getattr(record, key))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(self._sanitize(payload), ensure_ascii=False, default=str)


def configure_logging(level: str | None = None) -> None:
    root = logging.getLogger()
    if getattr(root, "_mayabu_configured", False):
        return
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(getattr(logging, (level or os.getenv("MAYABU_LOG_LEVEL", "INFO")).upper(), logging.INFO))
    root._mayabu_configured = True
