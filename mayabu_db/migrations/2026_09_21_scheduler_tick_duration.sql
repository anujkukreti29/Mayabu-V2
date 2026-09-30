-- Scheduler heartbeat tick duration and last-tick job count.
-- Applied by mayabu_db.migrate; survives Redis restart.

alter table scheduler_heartbeats
  add column if not exists last_tick_duration_ms integer;

alter table scheduler_heartbeats
  add column if not exists last_tick_jobs integer;

insert into schema_migrations(version)
values ('2026_09_21_scheduler_tick_duration')
on conflict (version) do nothing;
