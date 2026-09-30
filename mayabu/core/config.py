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
    # Isolates Redis keys across development/staging/production (slots, etc.).
    redis_key_prefix: str = (
        os.getenv("MAYABU_REDIS_KEY_PREFIX")
        or os.getenv("MAYABU_ENV", "development")
        or "development"
    )
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
    # Prefer sandbox on. Container hosts often need MAYABU_SCRAPER_CHROMIUM_NO_SANDBOX=1.
    scraper_chromium_no_sandbox: bool = _bool("MAYABU_SCRAPER_CHROMIUM_NO_SANDBOX", False)
    scraper_chromium_disable_dev_shm: bool = _bool(
        "MAYABU_SCRAPER_CHROMIUM_DISABLE_DEV_SHM", True
    )
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

    # Account / session auth.
    auth_session_cookie_name: str = os.getenv("MAYABU_AUTH_SESSION_COOKIE", "mayabu_session")
    auth_csrf_cookie_name: str = os.getenv("MAYABU_AUTH_CSRF_COOKIE", "mayabu_csrf")
    auth_session_days: int = _int("MAYABU_AUTH_SESSION_DAYS", 30)
    auth_verification_hours: int = _int("MAYABU_AUTH_VERIFICATION_HOURS", 48)
    auth_reset_hours: int = _int("MAYABU_AUTH_RESET_HOURS", 2)
    auth_cookie_samesite: str = os.getenv("MAYABU_AUTH_COOKIE_SAMESITE", "lax")
    auth_cookie_secure: bool | None = (
        None
        if os.getenv("MAYABU_AUTH_COOKIE_SECURE") in (None, "")
        else _bool("MAYABU_AUTH_COOKIE_SECURE", False)
    )
    auth_email_provider: str = os.getenv("MAYABU_AUTH_EMAIL_PROVIDER", "console")
    auth_email_from: str = os.getenv("MAYABU_AUTH_EMAIL_FROM", "Mayabu <noreply@mayabu.local>")
    auth_email_api_key: str = os.getenv("MAYABU_AUTH_EMAIL_API_KEY", "")
    auth_email_timeout_seconds: float = float(os.getenv("MAYABU_AUTH_EMAIL_TIMEOUT_SECONDS", "8") or 8)
    auth_public_base_url: str = os.getenv(
        "MAYABU_AUTH_PUBLIC_BASE_URL",
        os.getenv("MAYABU_PUBLIC_SITE_URL", "http://127.0.0.1:5173"),
    )
    auth_login_per_minute: int = _int("MAYABU_AUTH_LOGIN_PER_MINUTE", 10)
    auth_register_per_minute: int = _int("MAYABU_AUTH_REGISTER_PER_MINUTE", 5)
    auth_forgot_per_minute: int = _int("MAYABU_AUTH_FORGOT_PER_MINUTE", 5)
    auth_resend_per_minute: int = _int("MAYABU_AUTH_RESEND_PER_MINUTE", 3)
    auth_dev_inbox_enabled: bool = _bool("MAYABU_AUTH_DEV_INBOX", False)
    auth_session_touch_seconds: int = _int("MAYABU_AUTH_SESSION_TOUCH_SECONDS", 300)
    # When true (default in staging/production), detailed /api/health requires admin token.
    health_require_admin: bool | None = (
        None
        if os.getenv("MAYABU_HEALTH_REQUIRE_ADMIN") in (None, "")
        else _bool("MAYABU_HEALTH_REQUIRE_ADMIN", True)
    )
    release_version: str = os.getenv("MAYABU_RELEASE_VERSION", "") or ""
    git_sha: str = os.getenv("MAYABU_GIT_SHA", "") or ""

    # Automated price-intelligence scheduler. Off by default in development so
    # `npm run dev` does not generate unexpected retailer traffic.
    scheduler_enabled: bool = _bool("MAYABU_SCHEDULER_ENABLED", False)
    scheduler_tick_seconds: int = _int("MAYABU_SCHEDULER_TICK_SECONDS", 60)
    scheduler_lease_seconds: int = _int("MAYABU_SCHEDULER_LEASE_SECONDS", 90)
    scheduler_max_refresh_per_tick: int = _int("MAYABU_SCHEDULER_MAX_REFRESH_PER_TICK", 40)
    scheduler_max_discovery_per_tick: int = _int(
        "MAYABU_SCHEDULER_MAX_DISCOVERY_PER_TICK", 8
    )
    scheduler_max_demand_per_tick: int = _int("MAYABU_SCHEDULER_MAX_DEMAND_PER_TICK", 4)
    scheduler_max_enrich_per_tick: int = _int("MAYABU_SCHEDULER_MAX_ENRICH_PER_TICK", 6)
    scheduler_max_overlap_per_tick: int = _int("MAYABU_SCHEDULER_MAX_OVERLAP_PER_TICK", 8)
    scheduler_search_drain_per_tick: int = _int(
        "MAYABU_SCHEDULER_SEARCH_DRAIN_PER_TICK", 50
    )
    refresh_hot_minutes: int = _int("MAYABU_REFRESH_HOT_MINUTES", 180)
    refresh_normal_minutes: int = _int("MAYABU_REFRESH_NORMAL_MINUTES", 720)
    refresh_cold_minutes: int = _int("MAYABU_REFRESH_COLD_MINUTES", 1440)
    intelligence_stale_hours: int = _int("MAYABU_INTELLIGENCE_STALE_HOURS", 24)
    intelligence_min_observation_days: int = _int(
        "MAYABU_INTELLIGENCE_MIN_OBSERVATION_DAYS", 7
    )
    intelligence_min_tracking_days: int = _int(
        "MAYABU_INTELLIGENCE_MIN_TRACKING_DAYS", 14
    )

    def is_deployed_environment(self) -> bool:
        return self.environment.lower() in {"production", "prod", "staging"}

    def is_production_environment(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    def detailed_health_requires_admin(self) -> bool:
        if self.health_require_admin is not None:
            return self.health_require_admin
        return self.is_deployed_environment()

    def _contains_loopback(self, value: str) -> bool:
        lowered = (value or "").lower()
        return any(
            token in lowered
            for token in ("localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal")
        )

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
        if self.is_production_environment() and not self.admin_token:
            raise RuntimeError("MAYABU_ADMIN_TOKEN is required in production")
        if self.is_deployed_environment() and not self.admin_token:
            raise RuntimeError("MAYABU_ADMIN_TOKEN is required in staging/production")
        if "*" in self.cors_origins:
            raise RuntimeError("MAYABU_CORS_ORIGINS must not include '*' with credentialed auth")
        provider = (self.auth_email_provider or "console").strip().lower()
        allow_insecure_local = _bool("MAYABU_ALLOW_INSECURE_LOCAL", False)
        if self.is_production_environment():
            if self._contains_loopback(self.auth_public_base_url):
                raise RuntimeError(
                    "MAYABU_AUTH_PUBLIC_BASE_URL must not use localhost/loopback in production"
                )
            if not self.auth_public_base_url.lower().startswith("https://"):
                raise RuntimeError(
                    "MAYABU_AUTH_PUBLIC_BASE_URL must be https:// in production"
                )
            for origin in self.cors_origins:
                if self._contains_loopback(origin):
                    raise RuntimeError(
                        "MAYABU_CORS_ORIGINS must not include localhost/loopback in production"
                    )
                if origin and not origin.lower().startswith("https://"):
                    raise RuntimeError(
                        "MAYABU_CORS_ORIGINS must be https:// origins in production"
                    )
            if self.auth_dev_inbox_enabled:
                raise RuntimeError("MAYABU_AUTH_DEV_INBOX must be disabled in production")
            if self._contains_loopback(self.database_url):
                raise RuntimeError(
                    "DATABASE_URL must not point at localhost/loopback in production"
                )
            if provider in {"console", "dev", "test", "memory"}:
                raise RuntimeError(
                    "MAYABU_AUTH_EMAIL_PROVIDER must be a real provider (e.g. resend) in production"
                )
            if provider == "resend" and not (self.auth_email_api_key or "").strip():
                raise RuntimeError("MAYABU_AUTH_EMAIL_API_KEY is required when using Resend")
            if self.redis_url and self._contains_loopback(self.redis_url):
                raise RuntimeError("REDIS_URL must not use localhost/loopback in production")
            if self.auth_cookie_secure is False:
                raise RuntimeError("MAYABU_AUTH_COOKIE_SECURE must not be false in production")
            if "sslmode=disable" in self.database_url.lower():
                raise RuntimeError("DATABASE_URL must not use sslmode=disable in production")
        elif self.environment.lower() == "staging" and not allow_insecure_local:
            # Real staging hosts must look like production URLs; local insecure staging
            # requires explicit MAYABU_ALLOW_INSECURE_LOCAL=1.
            if self._contains_loopback(self.auth_public_base_url) or not self.auth_public_base_url.lower().startswith(
                "https://"
            ):
                raise RuntimeError(
                    "Staging requires https MAYABU_AUTH_PUBLIC_BASE_URL (or MAYABU_ALLOW_INSECURE_LOCAL=1 for local stacks)"
                )
            if self.auth_dev_inbox_enabled:
                raise RuntimeError(
                    "MAYABU_AUTH_DEV_INBOX must be disabled on real staging (use MAYABU_ALLOW_INSECURE_LOCAL=1 only for local)"
                )
            if self.auth_cookie_secure is False:
                raise RuntimeError(
                    "MAYABU_AUTH_COOKIE_SECURE must not be false on real staging"
                )
            if "sslmode=disable" in self.database_url.lower():
                raise RuntimeError("DATABASE_URL must not use sslmode=disable on real staging")
        if self.auth_email_timeout_seconds <= 0:
            raise RuntimeError("MAYABU_AUTH_EMAIL_TIMEOUT_SECONDS must be positive")
        if self.auth_session_touch_seconds < 30:
            raise RuntimeError("MAYABU_AUTH_SESSION_TOUCH_SECONDS must be >= 30")
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
        if self.search_cache_ttl_seconds < 1 or self.product_cache_ttl_seconds < 1:
            raise RuntimeError("Cache TTL values must be positive")
        if self.public_rate_limit_per_minute < 1:
            raise RuntimeError("MAYABU_PUBLIC_RATE_LIMIT_PER_MINUTE must be positive")
        if self.search_fetch_limit < 10 or self.search_fetch_limit > 2000:
            raise RuntimeError("MAYABU_SEARCH_FETCH_LIMIT must be between 10 and 2000")
        if self.scheduler_tick_seconds < 5 or self.scheduler_lease_seconds < 15:
            raise RuntimeError("Scheduler tick/lease intervals are too short")
        if self.scheduler_lease_seconds <= self.scheduler_tick_seconds:
            raise RuntimeError("MAYABU_SCHEDULER_LEASE_SECONDS must exceed tick interval")
        if (
            self.scheduler_max_refresh_per_tick < 1
            or self.scheduler_max_discovery_per_tick < 0
            or self.scheduler_max_demand_per_tick < 0
            or self.scheduler_max_enrich_per_tick < 0
            or self.scheduler_max_overlap_per_tick < 0
        ):
            raise RuntimeError("Scheduler per-tick limits are invalid")
        if not (
            30
            <= self.refresh_hot_minutes
            <= self.refresh_normal_minutes
            <= self.refresh_cold_minutes
            <= 10080
        ):
            raise RuntimeError(
                "Refresh HOT/NORMAL/COLD minutes must be ordered and at most 7 days"
            )
        if self.intelligence_stale_hours < 1 or self.intelligence_min_observation_days < 1:
            raise RuntimeError("Price-intelligence thresholds must be positive")
        # Soft guidance: warn via RuntimeError only for impossible total connections.
        if self.api_workers * self.db_pool_max_size > 200:
            raise RuntimeError(
                "api_workers * db_pool_max_size exceeds 200; reduce workers or pool size"
            )


@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    settings = AppSettings()
    settings.validate()
    return settings
