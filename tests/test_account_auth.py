"""Account auth and wishlist integration tests against live PostgreSQL."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

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


def test_register_login_me_logout_flow(client: TestClient) -> None:
    email = _unique_email("reg")
    headers = _csrf_headers(client)
    created = client.post(
        "/api/auth/register",
        json={"email": email.upper(), "password": "passphrase-ok", "display_name": "Ada"},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["user"]["email"].lower() == email
    assert body["user"]["email_verified"] is False

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"].lower() == email

    headers = _csrf_headers(client)
    logged_out = client.post("/api/auth/logout", headers=headers)
    assert logged_out.status_code == 200
    assert client.get("/api/auth/me").json()["user"] is None

    headers = _csrf_headers(client)
    bad = client.post(
        "/api/auth/login",
        json={"email": email, "password": "wrong-password"},
        headers=headers,
    )
    assert bad.status_code == 401
    assert bad.json()["detail"] == "Invalid email or password."

    headers = _csrf_headers(client)
    ok = client.post(
        "/api/auth/login",
        json={"email": email, "password": "passphrase-ok"},
        headers=headers,
    )
    assert ok.status_code == 200
    assert client.get("/api/auth/me").json()["user"]["display_name"] == "Ada"


def test_duplicate_email_and_weak_password(client: TestClient) -> None:
    email = _unique_email("dup")
    headers = _csrf_headers(client)
    first = client.post(
        "/api/auth/register",
        json={"email": email, "password": "good-password"},
        headers=headers,
    )
    assert first.status_code == 200
    headers = _csrf_headers(client)
    second = client.post(
        "/api/auth/register",
        json={"email": email.upper(), "password": "good-password"},
        headers=headers,
    )
    assert second.status_code == 409
    headers = _csrf_headers(client)
    weak = client.post(
        "/api/auth/register",
        json={"email": _unique_email("weak"), "password": "short"},
        headers=headers,
    )
    assert weak.status_code == 400


def test_verification_and_password_reset(client: TestClient) -> None:
    from mayabu.auth.email import get_email_outbox

    email = _unique_email("verify")
    headers = _csrf_headers(client)
    assert (
        client.post(
            "/api/auth/register",
            json={"email": email, "password": "initial-secret"},
            headers=headers,
        ).status_code
        == 200
    )
    outbound = get_email_outbox().latest(kind="verification", to=email)
    assert outbound is not None
    token = outbound.meta["token"]

    headers = _csrf_headers(client)
    verified = client.post("/api/auth/verify-email", json={"token": token}, headers=headers)
    assert verified.status_code == 200
    assert client.get("/api/auth/me").json()["user"]["email_verified"] is True

    headers = _csrf_headers(client)
    reused = client.post("/api/auth/verify-email", json={"token": token}, headers=headers)
    assert reused.status_code == 200
    assert reused.json()["status"] == "already_verified"

    headers = _csrf_headers(client)
    forgot = client.post("/api/auth/forgot-password", json={"email": email}, headers=headers)
    assert forgot.status_code == 200
    assert "If an account exists" in forgot.json()["message"]
    reset_mail = get_email_outbox().latest(kind="password_reset", to=email)
    assert reset_mail is not None
    reset_token = reset_mail.meta["token"]

    headers = _csrf_headers(client)
    reset = client.post(
        "/api/auth/reset-password",
        json={"token": reset_token, "password": "replacement-secret"},
        headers=headers,
    )
    assert reset.status_code == 200
    assert client.get("/api/auth/me").json()["user"] is None

    headers = _csrf_headers(client)
    old = client.post(
        "/api/auth/login",
        json={"email": email, "password": "initial-secret"},
        headers=headers,
    )
    assert old.status_code == 401
    headers = _csrf_headers(client)
    new = client.post(
        "/api/auth/login",
        json={"email": email, "password": "replacement-secret"},
        headers=headers,
    )
    assert new.status_code == 200

    headers = _csrf_headers(client)
    reuse_reset = client.post(
        "/api/auth/reset-password",
        json={"token": reset_token, "password": "another-secret1"},
        headers=headers,
    )
    assert reuse_reset.status_code == 400


def test_csrf_rejection(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": "a@example.com", "password": "password12"},
        headers={"Origin": "http://127.0.0.1:5173"},
    )
    assert response.status_code == 403


def test_safe_next_path() -> None:
    from mayabu.api.auth_routes import safe_next_path

    assert safe_next_path("/wishlist") == "/wishlist"
    assert safe_next_path("/account?tab=1") == "/account?tab=1"
    assert safe_next_path("https://evil.example/") is None
    assert safe_next_path("//evil.example") is None
    assert safe_next_path("/\\evil") is None


def test_wishlist_auth_and_idempotency(client: TestClient) -> None:
    import psycopg
    from psycopg.rows import dict_row

    email = _unique_email("wish")
    headers = _csrf_headers(client)
    assert (
        client.post(
            "/api/auth/register",
            json={"email": email, "password": "wishlist-secret"},
            headers=headers,
        ).status_code
        == 200
    )

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select id::text as id from product_clusters
            where status = 'active' and category = 'laptop'
            order by created_at desc limit 1
            """
        )
        row = cur.fetchone()
    if not row:
        pytest.skip("No public laptop products available for wishlist test")
    product_id = row["id"]

    assert client.get("/api/wishlist").status_code == 200
    headers = _csrf_headers(client)
    added = client.post(f"/api/wishlist/{product_id}", headers=headers)
    assert added.status_code == 200
    assert added.json()["status"] in {"added", "exists"}
    headers = _csrf_headers(client)
    again = client.post(f"/api/wishlist/{product_id}", headers=headers)
    assert again.status_code == 200
    assert again.json()["status"] == "exists"
    listed = client.get("/api/wishlist")
    assert listed.status_code == 200
    assert any(item["id"] == product_id for item in listed.json()["products"])
    status = client.get(f"/api/wishlist/status?ids={product_id}")
    assert status.json()["status"][product_id] is True
    headers = _csrf_headers(client)
    removed = client.delete(f"/api/wishlist/{product_id}", headers=headers)
    assert removed.status_code == 200
    headers = _csrf_headers(client)
    absent = client.delete(f"/api/wishlist/{product_id}", headers=headers)
    assert absent.status_code == 200
    assert absent.json()["status"] == "absent"


def test_price_watch_upsert_and_validation(client: TestClient) -> None:
    """Watch PATCH creates wishlist row when missing and validates target bounds."""
    import psycopg
    from psycopg.rows import dict_row

    email = _unique_email("watch")
    headers = _csrf_headers(client)
    assert (
        client.post(
            "/api/auth/register",
            json={"email": email, "password": "watch-password1"},
            headers=headers,
        ).status_code
        == 200
    )

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select id::text as id from product_clusters
            where status = 'active'
            order by created_at desc limit 1
            """
        )
        row = cur.fetchone()
        if not row:
            cur.execute(
                """
                insert into product_clusters(canonical_title, brand, category, status)
                values (
                  'Mayabu Watch Fixture Laptop',
                  'Mayabu',
                  'laptop',
                  'active'
                )
                returning id::text as id
                """
            )
            row = cur.fetchone()
            conn.commit()
    assert row, "Could not resolve or seed a public product for watch test"
    product_id = row["id"]

    headers = _csrf_headers(client)
    created = client.patch(
        f"/api/wishlist/{product_id}",
        json={"target_price": 49999, "notify_on_drop": False},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["status"] == "updated"
    assert body["target_price"] == 49999
    assert body["watch_delivery"] == "deferred"
    assert "email" not in body["message"].lower()

    listed = client.get("/api/wishlist")
    assert listed.status_code == 200
    wish = next(item for item in listed.json()["products"] if item["id"] == product_id)
    assert wish["target_price"] == 49999

    headers = _csrf_headers(client)
    invalid = client.patch(
        f"/api/wishlist/{product_id}",
        json={"target_price": 0, "notify_on_drop": True},
        headers=headers,
    )
    assert invalid.status_code == 422

    headers = _csrf_headers(client)
    huge = client.patch(
        f"/api/wishlist/{product_id}",
        json={"target_price": 50_000_000, "notify_on_drop": True},
        headers=headers,
    )
    assert huge.status_code == 422

    headers = _csrf_headers(client)
    drop_only = client.patch(
        f"/api/wishlist/{product_id}",
        json={"target_price": None, "notify_on_drop": True},
        headers=headers,
    )
    assert drop_only.status_code == 200
    assert drop_only.json()["notify_on_drop"] is True
    assert drop_only.json()["target_price"] is None


def test_concurrent_duplicate_registration(client: TestClient) -> None:
    email = _unique_email("race")
    # Seed CSRF cookie once on this client.
    _csrf_headers(client)
    cookie = client.cookies.get("mayabu_csrf")
    assert cookie

    def worker() -> int:
        local = TestClient(client.app)
        local.cookies.set("mayabu_csrf", cookie)
        response = local.post(
            "/api/auth/register",
            json={"email": email, "password": "race-password1"},
            headers={"X-CSRF-Token": cookie, "Origin": "http://127.0.0.1:5173"},
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=6) as pool:
        codes = [f.result() for f in as_completed([pool.submit(worker) for _ in range(6)])]
    assert 200 in codes
    assert codes.count(200) == 1
    assert all(code in {200, 409, 429} for code in codes)


def test_password_hashing_unit() -> None:
    from mayabu.auth.passwords import (
        hash_password,
        normalize_email,
        validate_password,
        verify_password,
    )

    assert normalize_email("  Ada@Example.COM ") == "ada@example.com"
    assert validate_password("short") is not None
    assert validate_password("long enough passphrase") is None
    digest = hash_password("long enough passphrase")
    assert digest.startswith("$argon2")
    assert verify_password(digest, "long enough passphrase")
    assert not verify_password(digest, "nope")
