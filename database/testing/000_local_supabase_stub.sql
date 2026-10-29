-- 000_local_supabase_stub.sql
-- TEST ONLY. Never apply this to a Supabase project.
--
-- It reproduces the small part of Supabase that the schema depends on, so migrations and RLS
-- policies can be exercised against a plain PostgreSQL instance:
--   * the auth schema with auth.users
--   * auth.uid(), reading the same request.jwt.claim.sub setting that Supabase uses
--   * a minimal storage schema, enough to create the bucket and to unit test path handling
--   * the anon, authenticated and service_role roles
--
-- Applying the stub is what makes local RLS testing honest: tests can SET ROLE authenticated
-- and be subject to the same policies that apply to a real client.

begin;

create schema if not exists auth;

create table if not exists auth.users (
    id                 uuid primary key default gen_random_uuid(),
    email              text unique,
    raw_user_meta_data jsonb not null default '{}'::jsonb,
    created_at         timestamptz not null default now()
);

-- Mirrors Supabase: the subject of the current request, or null for an anonymous caller.
create or replace function auth.uid()
returns uuid
language sql
stable
as $$
    select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
$$;

create schema if not exists storage;

create table if not exists storage.buckets (
    id                 text primary key,
    name               text not null,
    public             boolean not null default false,
    file_size_limit    bigint,
    allowed_mime_types text[],
    created_at         timestamptz not null default now()
);

create table if not exists storage.objects (
    id         uuid primary key default gen_random_uuid(),
    bucket_id  text not null references storage.buckets (id) on delete cascade,
    name       text not null,
    owner      uuid,
    created_at timestamptz not null default now(),
    unique (bucket_id, name)
);

alter table storage.objects enable row level security;

-- Roles are cluster-level and are created once by bootstrap_local_role.sql as a superuser.
-- They must not be created here: PostgreSQL checks CREATEROLE privilege before it checks for a
-- duplicate name, so an unprivileged test role gets "permission denied" rather than a catchable
-- duplicate_object, and the exception handler would never fire.
do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'authenticated') then
        raise exception 'Role "authenticated" is missing. Run database/testing/setup_local_role.sh as root first.';
    end if;
    if not exists (select 1 from pg_roles where rolname = 'anon') then
        raise exception 'Role "anon" is missing. Run database/testing/setup_local_role.sh as root first.';
    end if;
end $$;

grant usage on schema public, auth, storage to anon, authenticated, service_role;
grant select on auth.users to authenticated;
grant select, insert, update, delete on storage.objects to authenticated;
grant select on storage.buckets to authenticated;

commit;
