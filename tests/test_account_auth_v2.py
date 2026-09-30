"""Extended Account System V2 tests: sessions, email templates, races, provider failure."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("psycopg")

DATABASE_URL = os.getenv("MAYABU_TEST_DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("MAYABU_TEST_DATABASE_URL not set", allow_module_level=True)

os.environ.setdefault("MAYABU_AUTH_DEV_INBOX", "1")
os.environ.setdefault("MAYABU_AUTH_EMAIL_PROVIDER", "console")
os.environ.setdefault("MAYABU_ENV", "test")
os.environ.setdefault("MAYABU_AUTH_REGISTER_PER_MINUTE", "200")
os.environ.setdefault("MAYABU_AUTH_LOGIN_PER_MINUTE", "200")
os.environ.setdefault("MAYABU_AUTH_FORGOT_PER_MINUTE", "200")
os.environ.setdefault("MAYABU_AUTH_RESEND_PER_MINUTE", "200")


@pytest.fixture()
def client(monkeypatch):
    from mayabu.api.main import app
    from mayabu.auth.email import get_email_outbox
    from mayabu.core.config import get_app_settings

    monkeypatch.setenv("MAYABU_AUTH_DEV_INBOX", "1")
    monkeypatch.setenv("MAYABU_AUTH_EMAIL_PROVIDER", "console")
    monkeypatch.setenv("MAYABU_AUTH_REGISTER_PER_MINUTE", "200")
    monkeypatch.setenv("MAYABU_AUTH_LOGIN_PER_MINUTE", "200")
    monkeypatch.setenv("MAYABU_AUTH_FORGOT_PER_MINUTE", "200")
    monkeypatch.setenv("MAYABU_AUTH_RESEND_PER_MINUTE", "200")
    get_app_settings.cache_clear()
    get_email_outbox().clear()

    with TestClient(app) as test_client:
        yield test_client

    get_email_outbox().clear()
    get_app_settings.cache_clear()


def _csrf_headers(client: TestClient) -> dict[str, str]:
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200
    token = response.json()["csrf_token"]
    return {"X-CSRF-Token": token, "Origin": "http://127.0.0.1:5173"}


def _unique_email(prefix: str = "user") -> str:
    return f"{prefix}.{os.getpid()}.{threading.get_ident()}@example.test"


def _register(client: TestClient, email: str, password: str = "secure-passphrase") -> None:
    headers = _csrf_headers(client)
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "Tester"},
        headers=headers,
    )
    assert response.status_code == 200, response.text


def test_email_templates_escape_and_multipart() -> None:
    from mayabu.auth.email_templates import password_changed_email, verification_email

    content = verification_email(
        to_email='evil<script>@x.com',
        verify_url="https://mayabu.com/verify-email?token=abc",
        hours=48,
    )
    assert "<script>" not in content.html_body
    assert "evil&lt;script&gt;@x.com" in content.html_body
    assert "https://mayabu.com/verify-email?token=abc" in content.text_body
    assert password_changed_email().kind == "password_changed"


def test_session_list_and_revoke(client: TestClient) -> None:
    email = _unique_email("sess")
    _register(client, email)
    listed = client.get("/api/auth/sessions")
    assert listed.status_code == 200
    sessions = listed.json()["sessions"]
    assert len(sessions) >= 1
    assert any(item["current"] for item in sessions)

    # Second session via another client
    other = TestClient(client.app)
    headers = _csrf_headers(other)
    assert (
        other.post(
            "/api/auth/login",
            json={"email": email, "password": "secure-passphrase"},
            headers=headers,
        ).status_code
        == 200
    )
    other_sessions = other.get("/api/auth/sessions").json()["sessions"]
    assert len(other_sessions) >= 2

    headers = _csrf_headers(other)
    revoked = other.post("/api/auth/logout-others", headers=headers)
    assert revoked.status_code == 200
    assert revoked.json()["revoked"] >= 1
    remaining = other.get("/api/auth/sessions").json()["sessions"]
    assert len(remaining) == 1
    assert remaining[0]["current"] is True


def test_password_reset_race_only_one_succeeds(client: TestClient) -> None:
    from mayabu.auth.email import get_email_outbox

    email = _unique_email("race-reset")
    _register(client, email)
    headers = _csrf_headers(client)
    assert client.post("/api/auth/forgot-password", json={"email": email}, headers=headers).status_code == 200
    reset_mail = get_email_outbox().latest(kind="password_reset", to=email)
    assert reset_mail is not None
    token = reset_mail.meta["token"]
    cookie = client.cookies.get("mayabu_csrf")

    def worker(password: str) -> int:
        local = TestClient(client.app)
        local.cookies.set("mayabu_csrf", cookie)
        response = local.post(
            "/api/auth/reset-password",
            json={"token": token, "password": password},
            headers={"X-CSRF-Token": cookie, "Origin": "http://127.0.0.1:5173"},
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        codes = [
            f.result()
            for f in as_completed(
                [
                    pool.submit(worker, "winner-password1"),
                    pool.submit(worker, "loser-password12"),
                    pool.submit(worker, "loser-password13"),
                    pool.submit(worker, "loser-password14"),
                ]
            )
        ]
    assert codes.count(200) == 1
    assert all(code in {200, 400} for code in codes)


def test_email_provider_failure_keeps_account(client: TestClient, monkeypatch) -> None:
    failing = MagicMock()
    failing.send.return_value = False
    monkeypatch.setattr("mayabu.api.auth_routes.get_email_sender", lambda: failing)

    email = _unique_email("fail-mail")
    headers = _csrf_headers(client)
    created = client.post(
        "/api/auth/register",
        json={"email": email, "password": "still-created1"},
        headers=headers,
    )
    assert created.status_code == 200
    assert created.json()["verification_email_queued"] is False
    me = client.get("/api/auth/me").json()["user"]
    assert me is not None
    assert me["email"].lower() == email
    assert me["email_verified"] is False


def test_dev_inbox_disabled_without_flag(client: TestClient, monkeypatch) -> None:
    from dataclasses import replace

    from mayabu.core.config import get_app_settings

    patched = replace(get_app_settings(), auth_dev_inbox_enabled=False)
    monkeypatch.setattr("mayabu.api.auth_routes.get_app_settings", lambda: patched)
    response = client.get("/api/auth/dev/last-outbound")
    assert response.status_code == 404


def test_verification_reuse_reports_already_verified(client: TestClient) -> None:
    from mayabu.auth.email import get_email_outbox

    email = _unique_email("reverify")
    _register(client, email)
    token = get_email_outbox().latest(kind="verification", to=email).meta["token"]
    headers = _csrf_headers(client)
    assert client.post("/api/auth/verify-email", json={"token": token}, headers=headers).status_code == 200
    headers = _csrf_headers(client)
    again = client.post("/api/auth/verify-email", json={"token": token}, headers=headers)
    assert again.status_code == 200
    assert again.json()["status"] == "already_verified"


def test_production_email_config_rejects_console() -> None:
    from mayabu.core.config import AppSettings

    settings = AppSettings(
        environment="production",
        admin_token="secret",
        auth_email_provider="console",
        auth_public_base_url="https://mayabu.com",
        auth_dev_inbox_enabled=False,
        database_url="postgresql://mayabu:x@db.internal:5432/mayabu",
        cors_origins=("https://mayabu.com",),
    )
    with pytest.raises(RuntimeError, match="MAYABU_AUTH_EMAIL_PROVIDER"):
        settings.validate()


def test_resend_html_email_present(client: TestClient) -> None:
    from mayabu.auth.email import get_email_outbox

    email = _unique_email("html")
    _register(client, email)
    message = get_email_outbox().latest(kind="verification", to=email)
    assert message is not None
    assert message.html_body and "<html" in message.html_body.lower()
    assert "Mayabu" in message.html_body
