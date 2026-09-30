#!/usr/bin/env python3
"""Local Account System V2 critical-path E2E (API + console/dev inbox).

Requires a running API with MAYABU_AUTH_DEV_INBOX=1 (development).
Does not prove Resend or HTTPS Secure cookies.
"""

from __future__ import annotations

import argparse
import re
import time
import uuid

import httpx


def _csrf(client: httpx.Client) -> str:
    response = client.get("/api/auth/csrf")
    response.raise_for_status()
    token = response.json().get("csrf_token") or client.cookies.get("mayabu_csrf")
    if not token:
        raise RuntimeError(f"CSRF missing; cookies={dict(client.cookies)}")
    return token


def _headers(csrf: str) -> dict[str, str]:
    return {"X-CSRF-Token": csrf, "Content-Type": "application/json"}


def _extract_token(msg: dict) -> str | None:
    meta = msg.get("meta") or {}
    if meta.get("token"):
        return str(meta["token"])
    body = msg.get("text_body") or ""
    match = re.search(r"token=([^\s&]+)", body)
    return match.group(1) if match else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    email = f"staging-proof.{uuid.uuid4().hex[:10]}@example.test"
    password = "passphrase-ok-local"
    new_password = "passphrase-ok-reset"
    base = args.base_url.rstrip("/")

    with httpx.Client(base_url=base, timeout=30.0, follow_redirects=True) as client:
        peek = client.get("/api/auth/dev/last-outbound")
        if peek.status_code == 404:
            print("FAIL dev inbox unavailable (need MAYABU_AUTH_DEV_INBOX=1 for local proof)")
            return 1
        print(f"OK dev_inbox status={peek.status_code}")

        csrf = _csrf(client)
        signup = client.post(
            "/api/auth/register",
            headers=_headers(csrf),
            json={
                "email": email,
                "password": password,
                "display_name": "Local Staging Proof",
            },
        )
        print(
            f"{'OK' if signup.status_code in {200, 201} else 'FAIL'} "
            f"signup {signup.status_code} {signup.text[:200]}"
        )
        if signup.status_code not in {200, 201}:
            return 1

        time.sleep(0.3)
        inbox = client.get("/api/auth/dev/last-outbound", params={"kind": "verification"})
        msg = (inbox.json() or {}).get("message") or {}
        token = _extract_token(msg)
        if not token:
            print(f"FAIL no verification token in inbox meta={msg.get('meta')}")
            return 1
        print("OK verification_email_received")

        csrf = _csrf(client)
        verify = client.post(
            "/api/auth/verify-email",
            headers=_headers(csrf),
            json={"token": token},
        )
        print(f"{'OK' if verify.status_code == 200 else 'FAIL'} verify {verify.status_code} {verify.text[:160]}")
        if verify.status_code != 200:
            return 1

        csrf = _csrf(client)
        logout = client.post("/api/auth/logout", headers=_headers(csrf))
        print(f"{'OK' if logout.status_code in {200, 204} else 'FAIL'} logout {logout.status_code}")

        csrf = _csrf(client)
        login = client.post(
            "/api/auth/login",
            headers=_headers(csrf),
            json={"email": email, "password": password},
        )
        print(f"{'OK' if login.status_code == 200 else 'FAIL'} login {login.status_code}")
        if login.status_code != 200:
            return 1

        me = client.get("/api/auth/me")
        me_body = me.json() if me.status_code == 200 else {}
        authenticated = bool(me_body.get("authenticated") or me_body.get("user"))
        print(f"{'OK' if me.status_code == 200 and authenticated else 'FAIL'} me {me.status_code}")

        search = client.get("/api/search", params={"q": "laptop", "limit": 1})
        payload = search.json() or {}
        items = payload.get("items") or payload.get("results") or payload.get("products") or []
        if not items:
            print(f"FAIL no search results for wishlist seed keys={list(payload.keys())}")
            return 1
        product_id = items[0].get("id") or items[0].get("product_id")
        csrf = _csrf(client)
        add = client.post(f"/api/wishlist/{product_id}", headers=_headers(csrf))
        print(f"{'OK' if add.status_code in {200, 201} else 'FAIL'} wishlist_add {add.status_code} {add.text[:160]}")
        if add.status_code not in {200, 201}:
            return 1

        csrf = _csrf(client)
        client.post("/api/auth/logout", headers=_headers(csrf))
        csrf = _csrf(client)
        client.post(
            "/api/auth/login",
            headers=_headers(csrf),
            json={"email": email, "password": password},
        )
        wl = client.get("/api/wishlist")
        rows = ((wl.json() or {}).get("items") or (wl.json() or {}).get("products") or [])
        wl_ok = wl.status_code == 200 and (
            product_id in wl.text
            or any((row.get("id") == product_id or row.get("product_id") == product_id) for row in rows)
        )
        print(f"{'OK' if wl_ok else 'FAIL'} wishlist_persists {wl.status_code}")
        if not wl_ok:
            return 1

        csrf = _csrf(client)
        forgot = client.post(
            "/api/auth/forgot-password",
            headers=_headers(csrf),
            json={"email": email},
        )
        print(f"{'OK' if forgot.status_code in {200, 202} else 'FAIL'} forgot {forgot.status_code}")
        time.sleep(0.3)
        reset_inbox = client.get("/api/auth/dev/last-outbound", params={"kind": "password_reset"})
        rmsg = (reset_inbox.json() or {}).get("message") or {}
        reset_token = _extract_token(rmsg)
        if not reset_token:
            print("FAIL no reset token")
            return 1
        print("OK reset_email_received")

        csrf = _csrf(client)
        reset = client.post(
            "/api/auth/reset-password",
            headers=_headers(csrf),
            json={"token": reset_token, "password": new_password},
        )
        print(f"{'OK' if reset.status_code == 200 else 'FAIL'} reset {reset.status_code} {reset.text[:160]}")
        if reset.status_code != 200:
            return 1

        csrf = _csrf(client)
        old_login = client.post(
            "/api/auth/login",
            headers=_headers(csrf),
            json={"email": email, "password": password},
        )
        print(f"{'OK' if old_login.status_code in {401, 403} else 'FAIL'} old_password_rejected {old_login.status_code}")
        if old_login.status_code not in {401, 403}:
            return 1

        csrf = _csrf(client)
        new_login = client.post(
            "/api/auth/login",
            headers=_headers(csrf),
            json={"email": email, "password": new_password},
        )
        print(f"{'OK' if new_login.status_code == 200 else 'FAIL'} new_password_login {new_login.status_code}")
        if new_login.status_code != 200:
            return 1

        sessions = client.get("/api/auth/sessions")
        print(f"{'OK' if sessions.status_code == 200 else 'FAIL'} sessions {sessions.status_code}")

        csrf = _csrf(client)
        logout_all = client.post("/api/auth/logout-all", headers=_headers(csrf))
        print(f"{'OK' if logout_all.status_code in {200, 204} else 'FAIL'} logout_all {logout_all.status_code}")

        print(f"PASS local_account_v2_critical_path email={email}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
