# Mayabu v5.5 React + Vite Frontend

React 19, Vite, React Router Framework Mode, strict TypeScript, SSR, hydration, and prerendered public pages. FastAPI remains the only business backend.

## Windows CMD

```cmd
cd frontend
copy .env.example .env
npm ci
npm run dev
```

Required production variables:

```env
VITE_API_BASE_URL=https://api.example.com
VITE_SITE_URL=https://www.example.com
VITE_APP_ENV=production
```

## Checks

```cmd
npm run typecheck
npm run lint
npm run format:check
npm run test
npm run build
node scripts\verify-prerender.mjs
node scripts\verify-seo.mjs
npm run test:e2e
```

Stored prices render immediately. Verification is background-only, bounded, visibility-aware, and keeps the last valid price after failure. Search, compare, admin, account, and verification-job indexing policies remain explicit.

Deals, tracker, authentication, assistant, and admin UI remain feature-gated until real backend contracts and authorization are available.
