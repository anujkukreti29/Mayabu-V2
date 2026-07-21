# Mayabu v5.2 React + Vite Frontend Build Report

Date: 18 July 2026

## Result

The obsolete Next.js frontend was replaced with a new React + Vite implementation using React Router Framework Mode. The Mayabu v5.2 FastAPI, PostgreSQL, Redis, matching, migration, cache, durable-job, verification-admission, and Playwright worker architecture was preserved.

The frontend is a working SSR/prerender production foundation, not a client-only SPA. The client bundle, SSR server bundle, ten stable prerendered routes, typed API boundary, unit/component suite, formatting, linting, TypeScript, SEO checks, runtime SSR status checks, and dependency audit passed.

Browser E2E scenarios are included but could not execute in this environment because the installed Chromium is managed with `URLBlocklist: ["*"]`. Every navigation fails before application code runs with `net::ERR_BLOCKED_BY_ADMINISTRATOR`. The tests must be run on a normal Windows/Linux development machine after `npx playwright install chromium`.

Because browser E2E and Docker image execution were not validated here, this report does not claim that every production-readiness gate is complete.

## Frontend stack

- React 19.0.0
- React Router 7.18.1 Framework Mode
- Vite 6.4.3
- TypeScript 5.7.3 with strict checking
- Tailwind CSS 3.4.17
- TanStack Query 5.66.8
- Zod 3.24.2
- React Hook Form 7.54.2
- Radix UI primitives
- Recharts 2.15.1, loaded only by the product price-history route
- Vitest 3.2.7 and React Testing Library
- Playwright 1.61.1
- ESLint 9.39.2 and Prettier 3.5.3

## Rendering architecture

- React Router SSR server bundle on Node.js.
- Browser hydration through `entry.client.tsx`.
- Server rendering through `entry.server.tsx`.
- Route loaders call the typed FastAPI adapters.
- Ten stable routes are prerendered.
- Search and product pages render useful initial HTML.
- Product pages use stable IDs and canonical slugs.
- Missing products return HTTP 404.
- Old product slugs return HTTP 308 to the canonical route.
- FastAPI remains the only business backend.

## Integrated FastAPI endpoints

- `GET /api/search`
- `GET /api/products/{product_id}`
- `GET /api/products/{product_id}/offers`
- `GET /api/products/{product_id}/similar-variants`
- `GET /api/products/{product_id}/price-history`
- `POST /api/products/{product_id}/verify-price`
- `GET /api/verification-jobs/{task_id}`
- `GET /api/products/{product_id}/verification-status`
- `GET /api/health`
- `GET /api/ready`

The frontend does not invent optional backend contracts. Deals, tracker, authentication, assistant, and admin features remain disabled or truthful unavailable states unless explicitly enabled with working backend support.

## Implemented routes

Public and indexable where appropriate:

- `/`
- `/laptops`
- `/mobile-phones`
- `/products/:productId/:productSlug`
- `/platforms`
- `/how-it-works`
- `/about`
- `/contact`
- `/privacy`
- `/terms`
- `/disclaimer`

Noindex or feature-gated:

- `/search`
- `/compare`
- `/deals`
- `/tracker`
- `/assistant`
- `/login`
- `/signup`
- `/account/*`
- `/admin/*`

Service routes:

- `/health`
- `/robots.txt`
- `/sitemap.xml`

## Major corrections and improvements

- Removed all Next.js App Router, `next/*`, metadata API, image component, and `NEXT_PUBLIC_*` assumptions.
- Rebuilt the frontend with React Router SSR, hydration, route loaders, correct status codes, and prerendering.
- Corrected the old Zod input/output typing mismatch instead of suppressing it.
- Added a central API client with request IDs, safe GET retries, mutation protections, combined timeout/cancellation signals, and normalized errors.
- Kept exact matches, similar variants, and related products separate.
- Prevented zero, NaN, undefined, and invalid MRP/discount display.
- Added validated retailer links with approved-domain and HTTPS checks.
- Added canonical product-slug redirects and correct 404 metadata.
- Added Product and BreadcrumbList structured data using visible valid backend data only.
- Added robots and sitemap policies that exclude search, filters, compare, account, admin, and verification URLs.
- Added a non-blocking verification state machine covering fresh, cooldown, queue pressure, shared jobs, running, completed, out of stock, blocked/captcha, temporary unavailability, rate limiting, failure, and browser polling expiry.
- Fixed repeated terminal cache invalidation and stale stored task cleanup.
- Added page-visibility-aware polling and bounded 2-second/4-second polling behavior.
- Added responsive offer cards, comparison UI, accessible mobile navigation, focus management, skip navigation, live-region status announcements, and 44px controls.
- Added Content Security Policy and restrictive browser security headers.
- Disabled production source maps.
- Updated vulnerable development tooling; final `npm audit` reports zero vulnerabilities across production and development dependencies.
- Added deterministic local API fixtures; frontend tests never contact live ecommerce websites.

## Quality gates executed

Passed:

- `npm install` / dependency resolution
- `npm run typecheck`
- `npm run lint`
- `npm run test`
- `npm run test:coverage`
- `npm run format:check`
- `npm run build`
- Client bundle verification
- SSR server bundle verification
- Ten-route prerender verification
- SEO verification for key prerendered routes
- Runtime SSR checks with deterministic API fixtures
- HTTP 200 home/search/product checks
- HTTP 308 canonical product-slug redirect check
- HTTP 404 product and generic missing-route checks
- Search `noindex, follow` check
- Missing-page `noindex, nofollow` check
- Product and breadcrumb structured-data check
- `robots.txt` and `sitemap.xml` response checks
- `npm audit` with zero known vulnerabilities
- Backend Python compile check for `mayabu`, `mayabu_db`, and `mayabu_refresh`

Automated test result:

- 9 Vitest files passed.
- 29 unit/component tests passed.
- 10 Playwright scenarios are discovered across desktop and mobile projects.

Not executable in this environment:

- `npm run test:e2e`: blocked by host Chromium administrator policy before page navigation.
- Docker image build/run: Docker CLI/daemon is not installed in this runtime.
- Live integration against the user's PostgreSQL, Redis, FastAPI process, and real stored catalog: those services and data were not available here.
- Real retailer verification: intentionally excluded from frontend CI and not required for frontend browser tests.

## Runtime SSR checks

With the deterministic FastAPI-compatible fixture server:

- `/` -> 200
- `/search?q=ASUS%20Vivobook` -> 200 and `noindex, follow`
- Canonical product page -> 200
- Wrong product slug -> 308 to the correct slug
- Missing product -> 404, `Product Not Found | Mayabu`, `noindex, nofollow`
- Unknown route -> 404, `Page Not Found | Mayabu`, `noindex, nofollow`
- `/robots.txt` -> 200
- `/sitemap.xml` -> 200

## Known limitations

- The contact form validates user input but does not claim successful delivery because Mayabu v5.2 has no confirmed public contact endpoint.
- Deals are hidden until the backend exposes trustworthy price-drop/historical-low data.
- Tracker, account, authentication, assistant, and admin routes require real backend contracts and authorization before enablement.
- Product sitemap generation currently includes static canonical routes only; large-scale product sitemap generation needs a verified backend product-export contract.
- Legal text requires professional legal review before public launch.
- Recharts is lazy-loaded, but the product chart chunk remains the heaviest route-specific asset and should be monitored during real Lighthouse testing.
- React Router 7 prints non-blocking warnings about optional React Router 8 future flags. They were not enabled blindly because doing so would change routing behavior and requires a dedicated migration test.

## Windows CMD setup

From the full-stack project root:

```cmd
cd frontend
copy .env.example .env
npm ci
npm run typecheck
npm run lint
npm run test
npm run build
npm run dev
```

Open `http://127.0.0.1:5173`.

For browser tests on the user's machine:

```cmd
cd frontend
npx playwright install chromium
npm run test:e2e
```

For the production SSR bundle:

```cmd
cd frontend
set VITE_API_BASE_URL=https://your-api-domain.example
set VITE_SITE_URL=https://your-frontend-domain.example
set VITE_APP_ENV=production
npm run build
set PORT=3000
npm run start
```

Do not place database, Redis, scraper, proxy, or admin credentials in `VITE_*` variables.
