@echo off
call .venv\Scripts\activate.bat
if "%DATABASE_URL%"=="" set DATABASE_URL=postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu
python run_api.py
