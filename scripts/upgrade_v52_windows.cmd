@echo off
setlocal
if not defined DATABASE_URL set DATABASE_URL=postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu
if not defined REDIS_URL set REDIS_URL=redis://127.0.0.1:6379/0
python -m mayabu_db.migrate || exit /b 1
python scripts\verify_v52.py || exit /b 1
python -m pytest -q || exit /b 1
echo Mayabu v5.2 upgrade verification completed.
