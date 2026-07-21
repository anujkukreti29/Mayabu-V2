"""Central application configuration for Mayabu v5.

The module intentionally keeps configuration parsing in one place so API,
workers, scrapers, maintenance jobs, and CLIs use the same production limits.
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

if load_dotenv:
    load_dotenv()


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


def _float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be numeric") from exc


def _database_url() -> str:
    return os.getenv(
        "DATABASE_URL", "postgresql://mayabu:mayabu_dev_password@localhost:5432/mayabu"
    )


def _worker_id() -> str:
    configured = os.getenv("MAYABU_WORKER_ID")
    if configured and configured.strip():
        return configured.strip()
    return f"worker-{socket.gethostname()}"


@dataclass(frozen=True, slots=True)
class AppSettings:
    database_url: str = _database_url()
    redis_url: str | None = os.getenv("REDIS_URL") or None
    environment: str = os.getenv("MAYABU_ENV", "development")
    api_host: str = os.getenv("MAYABU_API_HOST", "127.0.0.1")
    api_port: int = _int("MAYABU_API_PORT", 8000)
    api_workers: int = _int("MAYABU_API_WORKERS", 1)
    api_threadpool_tokens: int = _int("MAYABU_API_THREADPOOL_TOKENS", 40)
    admin_token: str | None = os.getenv("MAYABU_ADMIN_TOKEN") or None
    cors_origins: tuple[str, ...] = tuple(
        x.strip()
        for x in os.getenv(
            "MAYABU_CORS_ORIGINS",
            "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if x.strip()
    )

    # API/search safety.
    search_cache_ttl_seconds: int = _int("MAYABU_SEARCH_CACHE_TTL_SECONDS", 600)
    product_cache_ttl_seconds: int = _int("MAYABU_PRODUCT_CACHE_TTL_SECONDS", 900)
    price_history_cache_ttl_seconds: int = _int(
        "MAYABU_PRICE_HISTORY_CACHE_TTL_SECONDS", 1800
    )
    max_query_length: int = _int("MAYABU_MAX_QUERY_LENGTH", 180)
    public_rate_limit_per_minute: int = _int("MAYABU_PUBLIC_RATE_LIMIT_PER_MINUTE", 60)
    enable_redis_cache: bool = _bool("MAYABU_ENABLE_REDIS_CACHE", True)
    enable_redis_rate_limit: bool = _bool("MAYABU_ENABLE_REDIS_RATE_LIMIT", True)
    trust_proxy_headers: bool = _bool("MAYABU_TRUST_PROXY_HEADERS", False)
    search_fetch_limit: int = _int("MAYABU_SEARCH_FETCH_LIMIT", 300)

    # PostgreSQL pool protection. These values are deliberately conservative.
    db_pool_min_size: int = _int("MAYABU_DB_POOL_MIN_SIZE", 1)
    db_pool_max_size: int = _int("MAYABU_DB_POOL_MAX_SIZE", 10)
    db_pool_timeout_seconds: float = _float("MAYABU_DB_POOL_TIMEOUT_SECONDS", 10.0)
    db_pool_max_waiting: int = _int("MAYABU_DB_POOL_MAX_WAITING", 30)
    db_pool_max_lifetime_seconds: int = _int(
        "MAYABU_DB_POOL_MAX_LIFETIME_SECONDS", 1800
    )
    db_pool_max_idle_seconds: int = _int("MAYABU_DB_POOL_MAX_IDLE_SECONDS", 300)
    db_connect_timeout_seconds: int = _int("MAYABU_DB_CONNECT_TIMEOUT_SECONDS", 8)
    db_statement_timeout_ms: int = _int("MAYABU_DB_STATEMENT_TIMEOUT_MS", 15000)

    # Worker/scraper protection.
    worker_id: str = _worker_id()
    worker_concurrency: int = _int("MAYABU_WORKER_CONCURRENCY", 2)
    worker_poll_seconds: float = _float("MAYABU_WORKER_POLL_SECONDS", 5.0)
    worker_shutdown_grace_seconds: int = _int(
        "MAYABU_WORKER_SHUTDOWN_GRACE_SECONDS", 30
    )
    worker_task_lease_minutes: int = _int("MAYABU_WORKER_TASK_LEASE_MINUTES", 20)
    worker_lease_refresh_seconds: int = _int("MAYABU_WORKER_LEASE_REFRESH_SECONDS", 120)
    platform_concurrency: int = _int("MAYABU_SCRAPER_PLATFORM_CONCURRENCY", 2)
    scraper_distributed_slot_ttl_seconds: int = _int(
        "MAYABU_SCRAPER_DISTRIBUTED_SLOT_TTL_SECONDS",
        _int("MAYABU_LIVE_VERIFY_DISTRIBUTED_SLOT_TTL_SECONDS", 180),
    )
    scraper_distributed_slot_wait_seconds: int = _int(
        "MAYABU_SCRAPER_DISTRIBUTED_SLOT_WAIT_SECONDS",
        _int("MAYABU_LIVE_VERIFY_DISTRIBUTED_SLOT_WAIT_SECONDS", 5),
    )
    scraper_headless: bool = _bool("MAYABU_SCRAPER_HEADLESS", True)
    scraper_debug: bool = _bool("MAYABU_SCRAPER_DEBUG", False)
    scraper_navigation_attempts: int = _int("MAYABU_SCRAPER_NAVIGATION_ATTEMPTS", 3)
    scraper_timeout_ms: int = _int("MAYABU_SCRAPER_TIMEOUT_MS", 50000)
    scraper_retry_base_seconds: float = _float("MAYABU_SCRAPER_RETRY_BASE_SECONDS", 2.0)
    scraper_max_pages: int = _int("MAYABU_SCRAPER_MAX_PAGES", 50)
    scraper_max_products: int = _int("MAYABU_SCRAPER_MAX_PRODUCTS", 1000)
    circuit_failure_threshold: int = _int("MAYABU_CIRCUIT_FAILURE_THRESHOLD", 5)
    circuit_cooldown_seconds: int = _int("MAYABU_CIRCUIT_COOLDOWN_SECONDS", 900)

    # Live price verification. Verification is bounded and never runs inside the API request.
    live_verify_fresh_seconds: int = _int("MAYABU_LIVE_VERIFY_FRESH_SECONDS", 180)
    live_verify_cooldown_seconds: int = _int("MAYABU_LIVE_VERIFY_COOLDOWN_SECONDS", 300)
    live_verify_failure_cooldown_seconds: int = _int(
        "MAYABU_LIVE_VERIFY_FAILURE_COOLDOWN_SECONDS", 900
    )
    live_verify_max_failure_cooldown_seconds: int = _int(
        "MAYABU_LIVE_VERIFY_MAX_FAILURE_COOLDOWN_SECONDS", 21600
    )
    live_verify_queue_max_active: int = _int(
        "MAYABU_LIVE_VERIFY_QUEUE_MAX_ACTIVE", 2000
    )
    live_verify_per_user_per_minute: int = _int(
        "MAYABU_LIVE_VERIFY_PER_USER_PER_MINUTE", 6
    )
    live_verify_global_per_minute: int = _int(
        "MAYABU_LIVE_VERIFY_GLOBAL_PER_MINUTE", 300
    )
    live_verify_max_offers_per_request: int = _int(
        "MAYABU_LIVE_VERIFY_MAX_OFFERS_PER_REQUEST", 4
    )
    live_verify_priority: int = _int("MAYABU_LIVE_VERIFY_PRIORITY", 5)
    live_verify_max_attempts: int = _int("MAYABU_LIVE_VERIFY_MAX_ATTEMPTS", 2)
    live_verify_estimated_seconds: int = _int(
        "MAYABU_LIVE_VERIFY_ESTIMATED_SECONDS", 15
    )
    live_verify_busy_retry_seconds: int = _int(
        "MAYABU_LIVE_VERIFY_BUSY_RETRY_SECONDS", 30
    )
    live_verify_lightweight_timeout_seconds: float = _float(
        "MAYABU_LIVE_VERIFY_LIGHTWEIGHT_TIMEOUT_SECONDS", 8.0
    )
    live_verify_distributed_slot_ttl_seconds: int = _int(
        "MAYABU_LIVE_VERIFY_DISTRIBUTED_SLOT_TTL_SECONDS", 90
    )
    live_verify_distributed_slot_wait_seconds: int = _int(
        "MAYABU_LIVE_VERIFY_DISTRIBUTED_SLOT_WAIT_SECONDS", 2
    )

    # Maintenance and retention.
    raw_item_retention_days: int = _int("MAYABU_RAW_ITEM_RETENTION_DAYS", 30)
    raw_price_retention_days: int = _int("MAYABU_RAW_PRICE_RETENTION_DAYS", 180)
    completed_task_retention_days: int = _int(
        "MAYABU_COMPLETED_TASK_RETENTION_DAYS", 30
    )
    live_verification_event_retention_days: int = _int(
        "MAYABU_LIVE_VERIFICATION_EVENT_RETENTION_DAYS", 30
    )
    search_document_batch_size: int = _int("MAYABU_SEARCH_DOCUMENT_BATCH_SIZE", 250)

    def validate(self) -> None:
        parsed = urlparse(self.database_url)
        if parsed.scheme not in {"postgresql", "postgres"} or not parsed.hostname:
            raise RuntimeError(
                "DATABASE_URL must be a valid postgresql:// or postgres:// URL"
            )
        if not 1 <= self.api_port <= 65535:
            raise RuntimeError("MAYABU_API_PORT must be between 1 and 65535")
        if not 1 <= self.api_workers <= 16:
            raise RuntimeError("MAYABU_API_WORKERS must be between 1 and 16")
        if not 1 <= self.api_threadpool_tokens <= 500:
            raise RuntimeError("MAYABU_API_THREADPOOL_TOKENS must be between 1 and 500")
        if self.environment.lower() in {"production", "prod"} and not self.admin_token:
            raise RuntimeError("MAYABU_ADMIN_TOKEN is required in production")
        if self.db_pool_min_size < 0:
            raise RuntimeError("MAYABU_DB_POOL_MIN_SIZE must be >= 0")
        if self.db_pool_max_size < max(1, self.db_pool_min_size):
            raise RuntimeError(
                "MAYABU_DB_POOL_MAX_SIZE must be >= min size and at least 1"
            )
        if self.db_pool_timeout_seconds <= 0 or self.db_connect_timeout_seconds <= 0:
            raise RuntimeError("Database timeout values must be positive")
        if self.worker_concurrency < 1 or self.platform_concurrency < 1:
            raise RuntimeError("Worker and platform concurrency must be positive")
        if self.worker_task_lease_minutes < 1:
            raise RuntimeError("MAYABU_WORKER_TASK_LEASE_MINUTES must be positive")
        if (
            not 1
            <= self.worker_lease_refresh_seconds
            < self.worker_task_lease_minutes * 60
        ):
            raise RuntimeError(
                "Worker lease refresh must be positive and shorter than the task lease"
            )
        if self.scraper_distributed_slot_ttl_seconds < 15:
            raise RuntimeError(
                "MAYABU_SCRAPER_DISTRIBUTED_SLOT_TTL_SECONDS must be at least 15"
            )
        if self.scraper_distributed_slot_wait_seconds < 1:
            raise RuntimeError(
                "MAYABU_SCRAPER_DISTRIBUTED_SLOT_WAIT_SECONDS must be positive"
            )
        if self.scraper_navigation_attempts < 1 or self.scraper_timeout_ms < 1:
            raise RuntimeError("Scraper attempts and timeout must be positive")
        if self.scraper_max_pages < 1 or self.scraper_max_products < 1:
            raise RuntimeError("Scraper safety limits must be positive")
        if self.circuit_failure_threshold < 1 or self.circuit_cooldown_seconds < 1:
            raise RuntimeError("Circuit-breaker settings must be positive")
        if self.live_verify_fresh_seconds < 0 or self.live_verify_cooldown_seconds < 1:
            raise RuntimeError(
                "Live verification freshness/cooldown settings are invalid"
            )
        if (
            self.live_verify_queue_max_active < 1
            or self.live_verify_per_user_per_minute < 1
            or self.live_verify_global_per_minute < 1
        ):
            raise RuntimeError("Live verification queue/rate limits must be positive")
        if not 1 <= self.live_verify_max_offers_per_request <= 10:
            raise RuntimeError(
                "MAYABU_LIVE_VERIFY_MAX_OFFERS_PER_REQUEST must be between 1 and 10"
            )
        if (
            not 1 <= self.live_verify_priority <= 1000
            or not 1 <= self.live_verify_max_attempts <= 20
        ):
            raise RuntimeError(
                "Live verification priority/attempt settings are invalid"
            )
        if self.live_verify_lightweight_timeout_seconds <= 0:
            raise RuntimeError("Live verification timeout must be positive")
        if self.live_verification_event_retention_days < 1:
            raise RuntimeError("Live verification event retention must be positive")


@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    settings = AppSettings()
    settings.validate()
    return settings
