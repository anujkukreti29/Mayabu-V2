-- Account System V1: users, sessions, email verification, password reset, wishlist.
-- Idempotent / safe to re-apply.

create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  normalized_email text not null,
  password_hash text not null,
  display_name text,
  email_verified_at timestamptz,
  status text not null default 'active'
    check (status in ('active', 'disabled')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_login_at timestamptz
);

create unique index if not exists idx_users_normalized_email
  on users (normalized_email);
create unique index if not exists idx_users_email
  on users (email);

create table if not exists user_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  token_hash text not null,
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  expires_at timestamptz not null,
  revoked_at timestamptz,
  user_agent text
);

create unique index if not exists idx_user_sessions_token_hash
  on user_sessions (token_hash);
create index if not exists idx_user_sessions_user_id
  on user_sessions (user_id);
create index if not exists idx_user_sessions_expires
  on user_sessions (expires_at)
  where revoked_at is null;

create table if not exists email_verification_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  token_hash text not null,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  used_at timestamptz
);

create unique index if not exists idx_email_verification_token_hash
  on email_verification_tokens (token_hash);
create index if not exists idx_email_verification_user
  on email_verification_tokens (user_id, created_at desc);

create table if not exists password_reset_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  token_hash text not null,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  used_at timestamptz
);

create unique index if not exists idx_password_reset_token_hash
  on password_reset_tokens (token_hash);
create index if not exists idx_password_reset_user
  on password_reset_tokens (user_id, created_at desc);

create table if not exists user_wishlist (
  user_id uuid not null references users(id) on delete cascade,
  product_id uuid not null references product_clusters(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, product_id)
);

create index if not exists idx_user_wishlist_user_created
  on user_wishlist (user_id, created_at desc);
create index if not exists idx_user_wishlist_product
  on user_wishlist (product_id);

insert into schema_migrations(version) values ('2026_09_20_account_system_v1')
on conflict (version) do nothing;
