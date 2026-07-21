# Mayabu v5.2 Upgrade Guide

Use the patch only on an existing Mayabu v5.1 folder. Use the full package for a clean folder or any older version.

## Windows CMD

```cmd
.venv\Scripts\activate.bat
set DATABASE_URL=postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu
set REDIS_URL=redis://127.0.0.1:6379/0

docker compose up -d postgres redis
python -m mayabu_db.migrate
python scripts\verify_v52.py
python -m pytest -q
```

Start API:

```cmd
python run_api.py
```

Start worker in another terminal:

```cmd
.venv\Scripts\activate.bat
set DATABASE_URL=postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu
set REDIS_URL=redis://127.0.0.1:6379/0
python worker_db.py --loop --concurrency 2
```

Start frontend:

```cmd
cd frontend
npm install --registry=https://registry.npmjs.org/
npm run dev
```

Open a product and click **Verify current price**.

## Production limits to tune after load testing

```env
MAYABU_LIVE_VERIFY_PER_USER_PER_MINUTE=6
MAYABU_LIVE_VERIFY_GLOBAL_PER_MINUTE=300
MAYABU_LIVE_VERIFY_QUEUE_MAX_ACTIVE=2000
MAYABU_LIVE_VERIFY_DISTRIBUTED_SLOT_WAIT_SECONDS=2
MAYABU_LIVE_VERIFICATION_EVENT_RETENTION_DAYS=30
MAYABU_TRUST_PROXY_HEADERS=false
```
