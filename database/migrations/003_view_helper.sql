-- 003_view_helper.sql
-- Adds a two-argument visibility helper so the application and the RLS policies share one
-- definition of "may this user see this photo".
--
-- Why: can_view_photo() reads auth.uid(), which is only meaningful for a client connection carrying
-- a user token. The backend connects with a privileged role, so it needs to pass the user id
-- explicitly. Duplicating the predicate in Python would let the two definitions drift apart, and a
-- drift in a visibility rule is a security bug.

begin;

create or replace function public.user_can_view_photo(p_user uuid, p_photo uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
    select exists (
        select 1
        from public.photos ph
        where ph.id = p_photo
          and p_user is not null
          and (
                ph.owner_id = p_user
             or (ph.visibility = 'friends' and public.are_friends(ph.owner_id, p_user))
          )
    );
$$;

-- The policy helper now delegates, so there is exactly one definition of the rule.
create or replace function public.can_view_photo(p_photo_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
    select public.user_can_view_photo(auth.uid(), p_photo_id);
$$;

do $$
begin
    if exists (select 1 from pg_roles where rolname = 'authenticated') then
        execute 'grant execute on function public.user_can_view_photo(uuid, uuid) to authenticated';
    end if;
end $$;

commit;
