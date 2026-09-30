"""Launch readiness unit tests (config, migrations listing, security headers)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_production_rejects_insecure_cookie_and_db_ssl_disable() -> None:
    from mayabu.core.config import AppSettings

    with pytest.raises(RuntimeError, match="MAYABU_AUTH_COOKIE_SECURE"):
        AppSettings(
            environment="production",
            admin_token="secret-token",
            auth_email_provider="resend",
            auth_email_api_key="re_test",
            auth_public_base_url="https://mayabu.example",
            auth_dev_inbox_enabled=False,
            auth_cookie_secure=False,
            database_url="postgresql://mayabu:x@db.internal:5432/mayabu",
            redis_url="redis://redis.internal:6379/0",
            cors_origins=("https://mayabu.example",),
        ).validate()

    with pytest.raises(RuntimeError, match="sslmode=disable"):
        AppSettings(
            environment="production",
            admin_token="secret-token",
            auth_email_provider="resend",
            auth_email_api_key="re_test",
            auth_public_base_url="https://mayabu.example",
            auth_dev_inbox_enabled=False,
            database_url="postgresql://mayabu:x@db.internal:5432/mayabu?sslmode=disable",
            redis_url="redis://redis.internal:6379/0",
            cors_origins=("https://mayabu.example",),
        ).validate()


def test_production_rejects_localhost_and_console_email() -> None:
    from mayabu.core.config import AppSettings

    settings = AppSettings(
        environment="production",
        admin_token="secret-token",
        auth_email_provider="console",
        auth_public_base_url="https://mayabu.example",
        auth_dev_inbox_enabled=False,
        database_url="postgresql://mayabu:x@db.internal:5432/mayabu",
        redis_url="redis://redis.internal:6379/0",
        cors_origins=("https://mayabu.example",),
    )
    with pytest.raises(RuntimeError, match="MAYABU_AUTH_EMAIL_PROVIDER"):
        settings.validate()


def test_production_rejects_loopback_public_url() -> None:
    from mayabu.core.config import AppSettings

    settings = AppSettings(
        environment="production",
        admin_token="secret-token",
        auth_email_provider="resend",
        auth_email_api_key="re_test",
        auth_public_base_url="http://127.0.0.1:5173",
        auth_dev_inbox_enabled=False,
        database_url="postgresql://mayabu:x@db.internal:5432/mayabu",
        cors_origins=("https://mayabu.example",),
    )
    with pytest.raises(RuntimeError, match="MAYABU_AUTH_PUBLIC_BASE_URL"):
        settings.validate()


def test_cors_star_rejected() -> None:
    from mayabu.core.config import AppSettings

    settings = AppSettings(
        environment="development",
        cors_origins=("*",),
        database_url="postgresql://mayabu:x@127.0.0.1:5433/mayabu",
    )
    with pytest.raises(RuntimeError, match="CORS"):
        settings.validate()


def test_staging_allows_insecure_local_opt_in() -> None:
    import os

    from mayabu.core.config import AppSettings

    os.environ["MAYABU_ALLOW_INSECURE_LOCAL"] = "1"
    try:
        settings = AppSettings(
            environment="staging",
            admin_token="staging-token",
            auth_public_base_url="http://127.0.0.1:5173",
            auth_dev_inbox_enabled=True,
            auth_email_provider="console",
            database_url="postgresql://mayabu:x@127.0.0.1:5433/mayabu",
            cors_origins=("http://127.0.0.1:5173",),
        )
        settings.validate()
    finally:
        os.environ.pop("MAYABU_ALLOW_INSECURE_LOCAL", None)


def test_migration_files_are_ordered() -> None:
    from mayabu_db.migrate import list_migration_files

    names = [p.stem for p in list_migration_files()]
    assert names == sorted(names)
    assert "2026_09_20_account_system_v1" in names
    assert "2026_09_20_account_system_v2" in names


def test_security_headers_on_api(monkeypatch) -> None:
    monkeypatch.setenv("MAYABU_ENV", "test")
    from mayabu.api.main import app
    from mayabu.core.config import get_app_settings

    get_app_settings.cache_clear()
    with TestClient(app) as client:
        response = client.get("/api/live")
        assert response.status_code == 200
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert "Referrer-Policy" in response.headers
    get_app_settings.cache_clear()


def test_metrics_requires_admin_when_token_set(monkeypatch) -> None:
    from dataclasses import replace

    from mayabu.api.main import app
    from mayabu.core.config import get_app_settings

    get_app_settings.cache_clear()
    patched = replace(get_app_settings(), admin_token="metrics-secret", environment="test")
    monkeypatch.setattr("mayabu.api.health_routes.get_app_settings", lambda: patched)
    with TestClient(app) as client:
        denied = client.get("/api/metrics")
        assert denied.status_code == 401
        ok = client.get("/api/metrics", headers={"X-Mayabu-Admin-Token": "metrics-secret"})
        assert ok.status_code == 200
        assert "text/plain" in ok.headers.get("content-type", "")
    get_app_settings.cache_clear()


def test_log_sanitizer_redacts_secrets() -> None:
    import logging

    from mayabu.core.logging import JsonFormatter

    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="t",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="ok",
        args=(),
        exc_info=None,
    )
    record.api_key = "super-secret"  # type: ignore[attr-defined]
    record.event = "test"
    line = formatter.format(record)
    assert "super-secret" not in line
    assert "[redacted]" in line
