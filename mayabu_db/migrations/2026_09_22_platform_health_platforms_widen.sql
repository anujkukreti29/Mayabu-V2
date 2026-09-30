-- Widen platform_health allowed platforms for schemas created before
-- vijaysales/poorvika/jiomart/bajajelectronics were added to the check.
-- Safe on already-wide constraints (drop + recreate).

alter table platform_health drop constraint if exists platform_health_platform_check;
alter table platform_health add constraint platform_health_platform_check check (
  platform in (
    'amazon',
    'flipkart',
    'croma',
    'reliancedigital',
    'vijaysales',
    'jiomart',
    'poorvika',
    'bajajelectronics'
  )
);

insert into platform_health(platform)
values
  ('vijaysales'),
  ('jiomart'),
  ('poorvika'),
  ('bajajelectronics')
on conflict (platform) do nothing;
