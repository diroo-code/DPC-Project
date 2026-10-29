-- 001_init.sql
-- Core schema for the TEB3033 photo sharing application.
-- Target: Supabase PostgreSQL. Depends on auth.users and auth.uid(), which Supabase provides.
-- For local testing, apply database/testing/000_local_supabase_stub.sql first.
--
-- Design notes:
--   * Photo binaries live in Storage. Only metadata lives here.
--   * RLS is enabled on every table. Storage policies live in 002_storage.sql.
--   * The backend connects with a privileged role, so application code checks permissions
--     explicitly as well. RLS protects the direct client path (Supabase JS) and acts as the
--     second line of defence, not the only one.

begin;

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------- types

do $$ begin
    create type public.friendship_status as enum ('pending', 'accepted', 'rejected');
exception when duplicate_object then null; end $$;

do $$ begin
    create type public.photo_visibility as enum ('friends', 'owner');
exception when duplicate_object then null; end $$;

-- ---------------------------------------------------------------- profiles

create table if not exists public.profiles (
    id           uuid primary key references auth.users (id) on delete cascade,
    username     text not null,
    display_name text not null,
    bio          text,
    avatar_path  text,
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now(),
    constraint profiles_username_format check (username ~ '^[a-z0-9_]{3,30}$'),
    constraint profiles_display_name_len check (char_length(btrim(display_name)) between 1 and 80),
    constraint profiles_bio_len check (bio is null or char_length(bio) <= 500)
);

create unique index if not exists profiles_username_key on public.profiles (lower(username));

-- ---------------------------------------------------------------- friendships

create table if not exists public.friendships (
    id            uuid primary key default gen_random_uuid(),
    requester_id  uuid not null references public.profiles (id) on delete cascade,
    addressee_id  uuid not null references public.profiles (id) on delete cascade,
    status        public.friendship_status not null default 'pending',
    created_at    timestamptz not null default now(),
    responded_at  timestamptz,
    constraint friendships_no_self check (requester_id <> addressee_id),
    constraint friendships_responded_consistency check (
        (status = 'pending' and responded_at is null)
        or (status in ('accepted', 'rejected') and responded_at is not null)
    )
);

create unique index if not exists friendships_unique_pair
    on public.friendships (requester_id, addressee_id);

-- One active relationship per pair, in either direction. Rejected rows are history and may repeat.
create unique index if not exists friendships_active_undirected
    on public.friendships (least(requester_id, addressee_id), greatest(requester_id, addressee_id))
    where status in ('pending', 'accepted');

create index if not exists friendships_addressee_idx
    on public.friendships (addressee_id, status);
create index if not exists friendships_requester_idx
    on public.friendships (requester_id, status);

-- ---------------------------------------------------------------- photos

create table if not exists public.photos (
    id           uuid primary key default gen_random_uuid(),
    owner_id     uuid not null references public.profiles (id) on delete cascade,
    storage_path text not null unique,
    caption      text,
    mime_type    text not null,
    size_bytes   integer not null,
    width        integer,
    height       integer,
    visibility   public.photo_visibility not null default 'friends',
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now(),
    constraint photos_mime_allowed check (mime_type in ('image/jpeg', 'image/png', 'image/webp')),
    constraint photos_size_limit check (size_bytes > 0 and size_bytes <= 5242880),
    constraint photos_caption_len check (caption is null or char_length(caption) <= 1000),
    constraint photos_dimensions_positive check (
        (width is null or width > 0) and (height is null or height > 0)
    ),
    -- The object path must start with the owner's id, so a photo row cannot point at
    -- another user's folder in the bucket.
    constraint photos_storage_path_shape check (storage_path like owner_id::text || '/%')
);

create index if not exists photos_owner_created_idx
    on public.photos (owner_id, created_at desc);
create index if not exists photos_created_idx
    on public.photos (created_at desc);
create index if not exists photos_visibility_idx
    on public.photos (visibility, created_at desc);

-- ---------------------------------------------------------------- comments

create table if not exists public.comments (
    id         uuid primary key default gen_random_uuid(),
    photo_id   uuid not null references public.photos (id) on delete cascade,
    author_id  uuid not null references public.profiles (id) on delete cascade,
    body       text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint comments_body_len check (char_length(btrim(body)) between 1 and 2000)
);

create index if not exists comments_photo_created_idx
    on public.comments (photo_id, created_at);
create index if not exists comments_author_idx
    on public.comments (author_id, created_at desc);

-- ---------------------------------------------------------------- photo_tags

create table if not exists public.photo_tags (
    photo_id   uuid not null references public.photos (id) on delete cascade,
    tag        text not null,
    created_at timestamptz not null default now(),
    primary key (photo_id, tag),
    constraint photo_tags_format check (tag = lower(tag) and tag ~ '^[a-z0-9][a-z0-9_-]{0,29}$')
);

create index if not exists photo_tags_tag_idx on public.photo_tags (tag);

-- ---------------------------------------------------------------- helper functions

-- True when the two users have an accepted friendship in either direction.
create or replace function public.are_friends(a uuid, b uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
    select exists (
        select 1
        from public.friendships f
        where f.status = 'accepted'
          and ((f.requester_id = a and f.addressee_id = b)
            or (f.requester_id = b and f.addressee_id = a))
    );
$$;

-- True when the caller may read the photo: the owner always, an accepted friend when the
-- photo is shared with friends. Anonymous callers resolve to false because auth.uid() is null.
create or replace function public.can_view_photo(p_photo_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
    select exists (
        select 1
        from public.photos ph
        where ph.id = p_photo_id
          and (
                ph.owner_id = auth.uid()
             or (ph.visibility = 'friends' and public.are_friends(ph.owner_id, auth.uid()))
          )
    );
$$;

create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at := now();
    return new;
end;
$$;

-- ---------------------------------------------------------------- triggers

drop trigger if exists profiles_touch_updated_at on public.profiles;
create trigger profiles_touch_updated_at
    before update on public.profiles
    for each row execute function public.touch_updated_at();

drop trigger if exists photos_touch_updated_at on public.photos;
create trigger photos_touch_updated_at
    before update on public.photos
    for each row execute function public.touch_updated_at();

drop trigger if exists comments_touch_updated_at on public.comments;
create trigger comments_touch_updated_at
    before update on public.comments
    for each row execute function public.touch_updated_at();

-- Create a profile automatically when Supabase Auth creates a user. The username comes from
-- sign-up metadata and falls back to a generated value, with a numeric suffix on collision.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    base_username text;
    candidate     text;
    suffix        int := 0;
begin
    base_username := lower(coalesce(new.raw_user_meta_data ->> 'username', ''));
    base_username := regexp_replace(base_username, '[^a-z0-9_]', '', 'g');

    if base_username is null or length(base_username) < 3 then
        base_username := 'user_' || substr(replace(new.id::text, '-', ''), 1, 8);
    end if;

    base_username := left(base_username, 24);
    candidate := base_username;

    loop
        begin
            insert into public.profiles (id, username, display_name)
            values (
                new.id,
                candidate,
                coalesce(
                    nullif(new.raw_user_meta_data ->> 'display_name', ''),
                    nullif(new.raw_user_meta_data ->> 'full_name', ''),
                    split_part(coalesce(new.email, 'user'), '@', 1)
                )
            );
            exit;
        exception when unique_violation then
            suffix := suffix + 1;
            if suffix > 50 then
                raise;
            end if;
            candidate := left(base_username, 20) || '_' || suffix::text;
        end;
    end loop;

    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();

-- Server-side upload quota. The API also checks this, but the database must not depend on
-- the API having done so.
create or replace function public.enforce_daily_upload_quota()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    used_today int;
begin
    select count(*) into used_today
    from public.photos
    where owner_id = new.owner_id
      and created_at >= date_trunc('day', now() at time zone 'utc') at time zone 'utc';

    if used_today >= 20 then
        raise exception 'daily upload limit reached: 20 photos per day'
            using errcode = 'P0001';
    end if;

    return new;
end;
$$;

drop trigger if exists photos_daily_quota on public.photos;
create trigger photos_daily_quota
    before insert on public.photos
    for each row execute function public.enforce_daily_upload_quota();

-- ---------------------------------------------------------------- row level security

alter table public.profiles    enable row level security;
alter table public.friendships enable row level security;
alter table public.photos      enable row level security;
alter table public.comments    enable row level security;
alter table public.photo_tags  enable row level security;

-- profiles: any authenticated user may read profiles (needed to find people to add).
-- Only the owner may insert or update their own row. Deletion cascades from auth.users.
drop policy if exists profiles_select_authenticated on public.profiles;
create policy profiles_select_authenticated on public.profiles
    for select to authenticated using (true);

drop policy if exists profiles_insert_self on public.profiles;
create policy profiles_insert_self on public.profiles
    for insert to authenticated with check (id = auth.uid());

drop policy if exists profiles_update_self on public.profiles;
create policy profiles_update_self on public.profiles
    for update to authenticated using (id = auth.uid()) with check (id = auth.uid());

-- friendships: visible to the two parties. A request may only be created by its requester.
-- Only the addressee may accept or reject. Either party may remove the row.
drop policy if exists friendships_select_parties on public.friendships;
create policy friendships_select_parties on public.friendships
    for select to authenticated
    using (requester_id = auth.uid() or addressee_id = auth.uid());

drop policy if exists friendships_insert_requester on public.friendships;
create policy friendships_insert_requester on public.friendships
    for insert to authenticated
    with check (requester_id = auth.uid() and status = 'pending' and responded_at is null);

drop policy if exists friendships_update_addressee on public.friendships;
create policy friendships_update_addressee on public.friendships
    for update to authenticated
    using (addressee_id = auth.uid() and status = 'pending')
    with check (
        addressee_id = auth.uid()
        and status in ('accepted', 'rejected')
        and responded_at is not null
    );

drop policy if exists friendships_delete_parties on public.friendships;
create policy friendships_delete_parties on public.friendships
    for delete to authenticated
    using (requester_id = auth.uid() or addressee_id = auth.uid());

-- photos: the owner sees and manages their own. Friends see rows marked 'friends'.
-- The visibility policy is the row level mirror of can_view_photo().
drop policy if exists photos_select_permitted on public.photos;
create policy photos_select_permitted on public.photos
    for select to authenticated
    using (
        owner_id = auth.uid()
        or (visibility = 'friends' and public.are_friends(owner_id, auth.uid()))
    );

drop policy if exists photos_insert_owner on public.photos;
create policy photos_insert_owner on public.photos
    for insert to authenticated
    with check (owner_id = auth.uid());

drop policy if exists photos_update_owner on public.photos;
create policy photos_update_owner on public.photos
    for update to authenticated
    using (owner_id = auth.uid())
    with check (owner_id = auth.uid());

drop policy if exists photos_delete_owner on public.photos;
create policy photos_delete_owner on public.photos
    for delete to authenticated
    using (owner_id = auth.uid());

-- comments: readable by anyone who may view the photo. Authors write their own comments.
-- Deletion is allowed for the comment author and for the photo owner.
drop policy if exists comments_select_viewable on public.comments;
create policy comments_select_viewable on public.comments
    for select to authenticated
    using (public.can_view_photo(photo_id));

drop policy if exists comments_insert_viewable on public.comments;
create policy comments_insert_viewable on public.comments
    for insert to authenticated
    with check (author_id = auth.uid() and public.can_view_photo(photo_id));

drop policy if exists comments_update_author on public.comments;
create policy comments_update_author on public.comments
    for update to authenticated
    using (author_id = auth.uid())
    with check (author_id = auth.uid());

drop policy if exists comments_delete_author_or_owner on public.comments;
create policy comments_delete_author_or_owner on public.comments
    for delete to authenticated
    using (
        author_id = auth.uid()
        or exists (
            select 1 from public.photos p
            where p.id = comments.photo_id and p.owner_id = auth.uid()
        )
    );

-- photo_tags: visible with the photo, managed by the photo owner only.
drop policy if exists photo_tags_select_viewable on public.photo_tags;
create policy photo_tags_select_viewable on public.photo_tags
    for select to authenticated
    using (public.can_view_photo(photo_id));

drop policy if exists photo_tags_insert_owner on public.photo_tags;
create policy photo_tags_insert_owner on public.photo_tags
    for insert to authenticated
    with check (
        exists (
            select 1 from public.photos p
            where p.id = photo_tags.photo_id and p.owner_id = auth.uid()
        )
    );

drop policy if exists photo_tags_update_owner on public.photo_tags;
create policy photo_tags_update_owner on public.photo_tags
    for update to authenticated
    using (
        exists (
            select 1 from public.photos p
            where p.id = photo_tags.photo_id and p.owner_id = auth.uid()
        )
    )
    with check (
        exists (
            select 1 from public.photos p
            where p.id = photo_tags.photo_id and p.owner_id = auth.uid()
        )
    );

drop policy if exists photo_tags_delete_owner on public.photo_tags;
create policy photo_tags_delete_owner on public.photo_tags
    for delete to authenticated
    using (
        exists (
            select 1 from public.photos p
            where p.id = photo_tags.photo_id and p.owner_id = auth.uid()
        )
    );

-- ---------------------------------------------------------------- grants

-- On Supabase these roles already exist with these grants. Applied defensively so the same
-- migration works on a plain PostgreSQL instance used for testing.
do $$
begin
    if exists (select 1 from pg_roles where rolname = 'authenticated') then
        execute 'grant usage on schema public to authenticated';
        execute 'grant select, insert, update, delete on all tables in schema public to authenticated';
        -- Only the two helper functions, deliberately. A blanket grant would also hand out
        -- execute on extension internals installed in this schema, and it warns for each one.
        execute 'grant execute on function public.are_friends(uuid, uuid) to authenticated';
        execute 'grant execute on function public.can_view_photo(uuid) to authenticated';
    end if;
end $$;

commit;
