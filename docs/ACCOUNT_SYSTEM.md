# Mayabu Account System V2

## Overview

Builds on Account System V1 (PostgreSQL opaque sessions, Argon2id, CSRF, wishlist).

**Verification policy:** unverified users may keep a session and use wishlist. Account UI always shows “Email not verified” with resend. Do not mix partial feature gates.

## Email architecture

`EmailSender` protocol with:

- `ConsoleEmailSender` — local/E2E outbox (`MAYABU_AUTH_EMAIL_PROVIDER=console|dev|test|memory`)
- `NullEmailSender` — refuse delivery (`null|none|disabled`)
- `ResendEmailSender` — production HTTP API via httpx (`resend`)

Templates (`mayabu/auth/email_templates.py`): verification, password reset, password changed — HTML + plain text, escaped user values.

Registration never deletes an account if email delivery fails. Account stays unverified; resend remains available.

## Production email secrets (backend only)

```
MAYABU_AUTH_EMAIL_PROVIDER=resend
MAYABU_AUTH_EMAIL_FROM=Mayabu <noreply@your-domain>
MAYABU_AUTH_EMAIL_API_KEY=...          # never VITE_* / frontend
MAYABU_AUTH_EMAIL_TIMEOUT_SECONDS=8
MAYABU_AUTH_PUBLIC_BASE_URL=https://mayabu.com
MAYABU_AUTH_DEV_INBOX=0
MAYABU_ENV=production
```

Startup validation fails if production still uses `console`/`localhost` public URL or has `MAYABU_AUTH_DEV_INBOX=1`.

Dev inbox:

```
MAYABU_AUTH_DEV_INBOX=1
GET /api/auth/dev/last-outbound?kind=verification
GET /api/auth/dev/email-preview?kind=password_reset
```

## Sessions V2

- `GET /api/auth/sessions` — active sessions (device label, created, last seen, current)
- `POST /api/auth/sessions/revoke` — revoke one (current = logout)
- `POST /api/auth/logout-others` — revoke all except current
- `POST /api/auth/logout-all` — revoke all + clear cookie
- `last_seen_at` updates throttled (`MAYABU_AUTH_SESSION_TOUCH_SECONDS`, default 300)

Migration: `mayabu_db/migrations/2026_09_20_account_system_v2.sql`

## Frontend routes

- `/signup` → `/check-email`
- `/sign-in`, `/forgot-password`, `/reset-password`, `/verify-email`
- `/account` — profile, verification, security, sessions, wishlist summary

## Metrics

- `mayabu_email_send_total{type,result}` — verification | password_reset | password_changed
- `mayabu_auth_session_events_total{event}` — created | revoked | …

## Not in V2

- OAuth / social login
- Email change with re-verification
- Account deletion UX (requires password confirm + cascade; deferred)
- SMS OTP

## Staging soak

```
python scripts/auth_staging_soak.py --base-url http://127.0.0.1:8000 --users 3
```
