-- bootstrap_local_role.sql
-- LOCAL DEVELOPMENT ONLY. Run once, as a PostgreSQL superuser, before the test suite.
--
-- Creates the unprivileged role the tests use, and the Supabase role names at cluster level so
-- the stub can grant membership. Never run this against a Supabase project.

do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'anon') then
        create role anon nologin;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'authenticated') then
        create role authenticated nologin;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'service_role') then
        create role service_role nologin bypassrls;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'itp_app') then
        create role itp_app login password 'itp_local_only' createdb;
    end if;
end $$;

-- The test role must be able to SET ROLE authenticated, which is how RLS is exercised.
grant authenticated to itp_app;
grant anon to itp_app;
