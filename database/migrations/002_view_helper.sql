
-- 003_view_helper.sql
-- Shared photo visibility helpers for the backend and RLS policies.

begin;

-- Explicit-user check for trusted backend operations.
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
             or (
                    ph.visibility = 'friends'
                    and public.are_friends(ph.owner_id, p_user)
                )
          )
    );
$$;

-- Client-facing helper uses the authenticated caller's identity.
create or replace function public.can_view_photo(p_photo_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
    select public.user_can_view_photo(auth.uid(), p_photo_id);
$$;

-- Storage read policy helper: resolve the object path inside a
-- SECURITY DEFINER function to avoid direct photos-table RLS filtering.
create or replace function public.can_view_photo_storage_path(p_storage_path text)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
    select exists (
        select 1
        from public.photos ph
        where ph.storage_path = p_storage_path
          and public.user_can_view_photo(auth.uid(), ph.id)
    );
$$;

-- Restrict explicit arbitrary-user checks to trusted database roles.
revoke execute on function public.user_can_view_photo(uuid, uuid)
from public, anon, authenticated;

grant execute on function public.user_can_view_photo(uuid, uuid)
to postgres;

-- Authenticated users can check access only using their own identity.
revoke execute on function public.can_view_photo_storage_path(text)
from public, anon;

grant execute on function public.can_view_photo_storage_path(text)
to authenticated;

commit;
