# PostgreSQL backup and restore

## Managed provider (recommended)

Use the provider’s:

- automated daily backups
- point-in-time recovery (PITR) where available
- encrypted at rest

Mayabu application backups are a supplement, not a replacement.

## Manual pre-deploy backup

Requires `pg_dump` on PATH **or** use the Postgres container client:

```bash
set DATABASE_URL=postgresql://...
python scripts/backup_postgres.py --out-dir artifacts/backups --label predeploy
```

Docker workaround (when host PATH has no `pg_dump`):

```bash
docker exec <postgres-container> pg_dump -Fc -U mayabu -d mayabu_test -f /tmp/mayabu.dump
docker cp <postgres-container>:/tmp/mayabu.dump artifacts/backups/
```

Produces a custom-format `.dump` file.

### Local drill record (2026-09-20)

| Item | Value |
|------|--------|
| Source DB | `mayabu_test` @ Docker `127.0.0.1:5433` |
| Method | `docker exec … pg_dump -Fc` |
| Backup duration | ~0.6s |
| Size | 596244 bytes |
| Restore target | **separate** `mayabu_restore_drill` |
| Restore method | `pg_restore --no-owner` |
| Restore duration | ~2s |
| Validation | products 205, listings 278, observations 386, users 171, wishlist 8, sessions 234, migrations 6 |

This is **LOCAL PASS** only — not managed-Postgres / PITR proof.

## Restore to a SEPARATE database

Never overwrite primary staging/production during drills.

```bash
set MAYABU_RESTORE_DATABASE_URL=postgresql://mayabu:…@127.0.0.1:5433/mayabu_restore_drill
python scripts/restore_postgres.py --dump artifacts/backups/mayabu-….dump --target-url %MAYABU_RESTORE_DATABASE_URL% --create-db
```

Primary-looking names (`mayabu`, `postgres`) are refused unless `MAYABU_ALLOW_PRIMARY_RESTORE=1`.

## Validation after restore

Confirm:

- `schema_migrations` rows present
- `users` / `product_clusters` counts sane
- `/api/ready` against an API pointed at the restore DB (optional)

## Sessions / recent prices

- Restoring an older dump revokes “current” live sessions that were created after the backup (cookies become invalid).
- Price observations newer than the backup are lost until re-scraped/refreshed.

## When to restore

- Catastrophic data corruption
- Accidental destructive migration (prefer forward-fix first)
- Provider-assisted PITR for fine-grained recovery

## Pre-deploy checklist

1. Take manual dump or confirm managed snapshot
2. Apply migrations on staging clone first
3. Smoke tests
4. Only then migrate production
