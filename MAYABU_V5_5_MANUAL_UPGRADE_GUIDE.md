# Mayabu v5.4 to v5.5 Manual Upgrade

No database migration is required.

Copy or replace only the files listed in `PATCH_MANIFEST_V5_5.txt`.

After copying backend files:

```cmd
.venv\Scripts\activate.bat
python -m compileall mayabu mayabu_db mayabu_refresh
python -m pytest -q
```

After copying frontend files:

```cmd
cd frontend
npm ci
npm run typecheck
npm run lint
npm run format:check
npm run test
npm run build
node scripts\verify-prerender.mjs
node scripts\verify-seo.mjs
```

Restart the API, worker, and frontend only after the checks pass. Existing PostgreSQL and Redis data can remain in place.
