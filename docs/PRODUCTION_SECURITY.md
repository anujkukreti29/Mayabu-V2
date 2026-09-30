# Mayabu production security

## Secrets classification

**Public (frontend / VITE_*):** site URL, canonical host, app env, feature flags, browser API mode.

**Server-only:** `DATABASE_URL`, `REDIS_URL`, `MAYABU_ADMIN_TOKEN`, `MAYABU_AUTH_EMAIL_API_KEY`, provider credentials.

Never log passwords, API keys, session/CSRF/raw verification/reset tokens, or Authorization headers.
JSON logging sanitizes common secret field names.

## Cookies

| Cookie | HttpOnly | Secure (prod/staging) | SameSite | Path | Domain |
|--------|----------|------------------------|----------|------|--------|
| `mayabu_session` | yes | yes | Lax | `/` | host-only (preferred) |
| `mayabu_csrf` | no | yes | Lax | `/` | host-only |

Do not set broad `Domain=.example.com` unless cross-subdomain auth is required.

## CSRF / CORS / Origin

- Double-submit CSRF cookie + `X-CSRF-Token`
- Allowed Origin/Referer from `MAYABU_CORS_ORIGINS`
- Never `*` with credentials

Prefer same-origin `/api` via reverse proxy to minimize CORS.

## Trusted proxies

Enable `MAYABU_TRUST_PROXY_HEADERS=true` only behind a trusted edge that strips client-supplied forwarded headers.

## Security headers

API middleware sets: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, strict API CSP, HSTS on HTTPS staging/production.

Frontend SSR sets CSP suitable for images from `https:`, plus `Cache-Control: private, no-store` and `Vary: Cookie` to prevent auth hydration leaking through shared caches.

HSTS preload is **not** enabled automatically.

## Metrics / health exposure

- `/api/live`, `/api/ready` — public
- `/api/health`, `/api/metrics` — require admin token in staging/production

## Auth tokens

Opaque session token in cookie; only hash stored in PostgreSQL.
Verification/reset tokens hashed, single-use, expiry-bounded.

## DB roles (recommended)

| Role | Use |
|------|-----|
| `mayabu_migrator` | run migrations |
| `mayabu_app` | API/worker DML without DDL |

## Staging isolation

- Staging `VITE_APP_ENV=staging` → noindex
- Staging robots disallow
- No production email domain mix-ups
- No shared session cookie domain with production

## External retailer links

Keep `rel` attributes (`noopener`, `noreferrer`, `sponsored` where applicable) and URL allowlisting — do not proxy retailer destinations.
