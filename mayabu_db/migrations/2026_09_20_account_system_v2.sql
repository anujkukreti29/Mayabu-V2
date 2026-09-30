-- Account System V2: efficient active-session listing (no schema breakage).

create index if not exists idx_user_sessions_user_active
  on user_sessions (user_id, last_seen_at desc)
  where revoked_at is null;

insert into schema_migrations(version) values ('2026_09_20_account_system_v2')
on conflict (version) do nothing;
