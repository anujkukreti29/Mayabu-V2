@echo off
setlocal
call .venv\Scripts\activate.bat
if errorlevel 1 exit /b 1
if "%DATABASE_URL%"=="" set DATABASE_URL=postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu
docker compose up -d postgres redis
if errorlevel 1 exit /b 1
python -m mayabu_db.migrate
if errorlevel 1 exit /b 1
python admin_review.py refresh-variant-groups --limit 10000
if errorlevel 1 exit /b 1
python admin_review.py backfill-search-documents --batch-size 500
if errorlevel 1 exit /b 1
python scripts\verify_v51.py
endlocal
