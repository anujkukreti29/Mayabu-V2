# Mayabu v4.5.2 Frontend + Matching Stability Report

## Goal

This build is a consolidated testing package so you do not have to keep extracting a new zip for every small frontend/backend fix.

## Fixed / improved

### Frontend UX

- React + Vite + TypeScript frontend remains the main frontend.
- Product cards now support real `image_url` from the search API.
- Product card titles are clamped so long marketplace titles do not break the grid.
- Product specs are clamped to keep cards readable.
- Card grid uses wider cards so desktop does not show too many narrow columns.
- Product detail page uses product image or best-offer image.
- The product card no longer claims multi-platform matching when there is only one platform. It shows multi-platform wording only when `platform_count > 1`.
- Removed `package-lock.json` so local `npm install` does not reuse an internal registry URL.
- Frontend dependency versions are no longer `latest`; this reduces random install drift.

### Backend/API

- Search cache key moved to `search:{category}:v4:*` so scoped invalidation works with the existing cache deletion logic.
- Product detail API now returns `image_url` for the product object too, not only individual offers.
- Search ranking now gives stronger priority to exact query coverage, brand/spec matches, and multi-platform products.

### Product matching / merging

- Added safe automatic duplicate-product merge support.
- `run_mayabu_db.py` now runs a safe duplicate auto-merge pass after all selected platforms finish scraping, unless `--skip-auto-merge` is passed.
- Added CLI command:

```cmd
python admin_review.py auto-merge-duplicates --limit 100 --min-score 92
```

This does not blindly merge fuzzy matches. It only auto-merges high-confidence duplicate clusters with strong identity signals such as exact variant key, model-code overlap, or multiple exact specs.

## Important note about platform count

Mayabu will show `Same product found on 2+ platforms` only when the database has actually merged listings under the same product cluster. It will not fake multi-platform count for broad search results.

For broad query `laptop`, many platforms return different laptop models, so many cards may correctly remain single-platform. To test matching, scrape a specific product model query across all platforms.

Recommended test:

```cmd
python run_mayabu_db.py "Asus Vivobook 14 ultra 5 225h" --platforms flipkart amazon reliancedigital croma --max-pages 1 --max-products 10
python admin_review.py auto-merge-duplicates --limit 100 --min-score 92
```

Then search the same query in the frontend.

## Run commands

Backend:

```cmd
cd "C:\Users\anujk\Desktop\Mayabu V4\mayabu_v4_5_2_frontend_matching_stability\mayabu_v4_5_1_product_matching_backend"
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if not exist .env copy .env.example .env
docker compose up -d
python -m mayabu_db.migrate
python run_api.py
```

Frontend:

```cmd
cd "C:\Users\anujk\Desktop\Mayabu V4\mayabu_v4_5_2_frontend_matching_stability\mayabu_v4_5_1_product_matching_backend\frontend"
copy .env.example .env
npm config set registry https://registry.npmjs.org/
npm install --registry=https://registry.npmjs.org/
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```
