-- 002_storage.sql
-- Supabase Storage configuration for private photo delivery.
--
-- This migration is Supabase specific: it writes to storage.buckets and storage.objects,
-- which only exist on a Supabase project. It is therefore NOT executed by the local test
-- harness, and it is reported as NOT TESTED locally. The verification procedure against a
-- real project is in database/README.md.
--
-- Object path convention: <photo_id>/<filename>
-- The photo id in the first path segment ties the object to its metadata row, which lets the
-- storage policy reuse public.can_view_photo() instead of duplicating the sharing rules.

begin;

-- Private bucket. public = false means no anonymous read, by URL or otherwise.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'photos',
    'photos',
    false,
    5242880,
    array['image/jpeg', 'image/png', 'image/webp']
)
on conflict (id) do update
    set public = false,
        file_size_limit = excluded.file_size_limit,
        allowed_mime_types = excluded.allowed_mime_types;

-- Read: the caller may read an object only when they may view its photo. Because the backend
-- issues short lived signed URLs, this policy governs direct client access and the signing
-- decision (the service role signs only after its own permission check).
drop policy if exists photos_read_permitted on storage.objects;
create policy photos_read_permitted on storage.objects
    for select to authenticated
    using (
        bucket_id = 'photos'
        and public.can_view_photo((split_part(name, '/', 1))::uuid)
    );

-- Insert: an authenticated user may upload only into the folder of a photo they own.
drop policy if exists photos_insert_owner on storage.objects;
create policy photos_insert_owner on storage.objects
    for insert to authenticated
    with check (
        bucket_id = 'photos'
        and exists (
            select 1 from public.photos p
            where p.id = (split_part(name, '/', 1))::uuid
              and p.owner_id = auth.uid()
        )
    );

-- Update and delete: the photo owner only.
drop policy if exists photos_update_owner on storage.objects;
create policy photos_update_owner on storage.objects
    for update to authenticated
    using (
        bucket_id = 'photos'
        and exists (
            select 1 from public.photos p
            where p.id = (split_part(name, '/', 1))::uuid
              and p.owner_id = auth.uid()
        )
    );

drop policy if exists photos_delete_owner on storage.objects;
create policy photos_delete_owner on storage.objects
    for delete to authenticated
    using (
        bucket_id = 'photos'
        and exists (
            select 1 from public.photos p
            where p.id = (split_part(name, '/', 1))::uuid
              and p.owner_id = auth.uid()
        )
    );

commit;
