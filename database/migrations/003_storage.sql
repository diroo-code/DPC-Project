
-- 002_storage.sql
-- Supabase Storage configuration for private photo delivery.
-- Object path: <owner_uuid>/<photo_uuid>.<extension>

begin;

-- Private bucket: 5 MiB maximum, approved image formats only.
insert into storage.buckets (
    id, name, public, file_size_limit, allowed_mime_types
)
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

-- Read: use the SECURITY DEFINER helper to avoid direct photos-table RLS filtering.
drop policy if exists photos_read_permitted on storage.objects;
create policy photos_read_permitted on storage.objects
    for select to authenticated
    using (
        bucket_id = 'photos'
        and public.can_view_photo_storage_path(storage.objects.name)
    );

-- Insert: only the owner may upload to the path recorded for their photo.
drop policy if exists photos_insert_owner on storage.objects;
create policy photos_insert_owner on storage.objects
    for insert to authenticated
    with check (
        bucket_id = 'photos'
        and exists (
            select 1
            from public.photos p
            where p.storage_path = storage.objects.name
              and p.owner_id = auth.uid()
        )
    );

-- Update: only the owner of the associated photo.
drop policy if exists photos_update_owner on storage.objects;
create policy photos_update_owner on storage.objects
    for update to authenticated
    using (
        bucket_id = 'photos'
        and exists (
            select 1
            from public.photos p
            where p.storage_path = storage.objects.name
              and p.owner_id = auth.uid()
        )
    )
    with check (
        bucket_id = 'photos'
        and exists (
            select 1
            from public.photos p
            where p.storage_path = storage.objects.name
              and p.owner_id = auth.uid()
        )
    );

-- Delete: only the owner of the associated photo.
drop policy if exists photos_delete_owner on storage.objects;
create policy photos_delete_owner on storage.objects
    for delete to authenticated
    using (
        bucket_id = 'photos'
        and exists (
            select 1
            from public.photos p
            where p.storage_path = storage.objects.name
              and p.owner_id = auth.uid()
        )
    );

commit;
