#!/usr/bin/env python3
"""Modest Account V2 staging soak (register → verify → wishlist → reset)."""

from __future__ import annotations

import argparse
import re
import sys
import time
import uuid

import httpx


def _csrf(client: httpx.Client) -> dict[str, str]:
    response = client.get("/api/auth/csrf")
    response.raise_for_status()
    token = response.json()["csrf_token"]
    return {"X-CSRF-Token": token, "Origin": "http://127.0.0.1:5173"}


def _token_from_outbox(client: httpx.Client, kind: str) -> str:
    response = client.get("/api/auth/dev/last-outbound", params={"kind": kind})
    response.raise_for_status()
    message = response.json().get("message") or {}
    meta = message.get("meta") or {}
    if meta.get("token"):
        return str(meta["token"])
    body = message.get("text_body") or ""
    match = re.search(r"token=([A-Za-z0-9_-]+)", body)
    if not match:
        raise RuntimeError(f"No {kind} token in outbox")
    return match.group(1)


def soak_one(client: httpx.Client, index: int) -> None:
    email = f"soak.{index}.{uuid.uuid4().hex[:8]}@example.test"
    password = "soak-passphrase-1"
    headers = _csrf(client)
    created = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": f"Soak {index}"},
        headers=headers,
    )
    created.raise_for_status()
    verify_token = _token_from_outbox(client, "verification")
    headers = _csrf(client)
    verified = client.post("/api/auth/verify-email", json={"token": verify_token}, headers=headers)
    verified.raise_for_status()
    me = client.get("/api/auth/me")
    me.raise_for_status()
    assert me.json()["user"]["email_verified"] is True

    # Optional wishlist if products exist
    search = client.get("/api/search", params={"q": "laptop", "limit": 1})
    if search.status_code == 200:
        products = (search.json().get("products") or search.json().get("results") or [])
        if products:
            product_id = products[0].get("id")
            if product_id:
                headers = _csrf(client)
                client.post(f"/api/wishlist/{product_id}", headers=headers).raise_for_status()
                listed = client.get("/api/wishlist")
                listed.raise_for_status()

    headers = _csrf(client)
    client.post("/api/auth/logout", headers=headers).raise_for_status()
    headers = _csrf(client)
    client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
        headers=headers,
    ).raise_for_status()

    headers = _csrf(client)
    client.post("/api/auth/forgot-password", json={"email": email}, headers=headers).raise_for_status()
    reset_token = _token_from_outbox(client, "password_reset")
    new_password = "soak-passphrase-2"
    headers = _csrf(client)
    client.post(
        "/api/auth/reset-password",
        json={"token": reset_token, "password": new_password},
        headers=headers,
    ).raise_for_status()
    headers = _csrf(client)
    bad = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
        headers=headers,
    )
    assert bad.status_code == 401
    headers = _csrf(client)
    client.post(
        "/api/auth/login",
        json={"email": email, "password": new_password},
        headers=headers,
    ).raise_for_status()
    sessions = client.get("/api/auth/sessions")
    sessions.raise_for_status()
    assert sessions.json()["sessions"]
    headers = _csrf(client)
    client.post("/api/auth/logout-all", headers=headers).raise_for_status()
    print(f"ok user={email}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--users", type=int, default=3)
    args = parser.parse_args()
    started = time.perf_counter()
    with httpx.Client(base_url=args.base_url, timeout=30.0, follow_redirects=True) as client:
        health = client.get("/api/health")
        if health.status_code >= 400:
            print("backend unhealthy", health.status_code, file=sys.stderr)
            return 2
        for index in range(max(1, args.users)):
            soak_one(client, index)
    print(f"soak_complete users={args.users} seconds={time.perf_counter() - started:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
