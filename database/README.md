# Database

Supabase PostgreSQL. Photo binaries live in Storage. Metadata and access rules live here.

## Files

| File | Purpose | Where it runs |
|---|---|---|
| `migrations/001_init.sql` | Tables, enums, indexes, constraints, helper functions, triggers, RLS policies | Supabase and local tests |
| `migrations/002_storage.sql` | Private `photos` bucket and `storage.objects` policies | Supabase only |
| `testing/000_local_supabase_stub.sql` | Minimal `auth` and `storage` schemas plus the Supabase roles | Local tests only, never production |

Order matters: the stub must exist before `001_init.sql`, because the migration references
`auth.users`, `auth.uid()` and the `authenticated` role.

## Applying to a Supabase project

1. Create the project and open the SQL editor.
2. Run `001_init.sql`.
3. Run `002_storage.sql`.
4. Confirm in Storage that the `photos` bucket exists, is private, and has the 5 MB limit and the
   three allowed MIME types.

`002_storage.sql` cannot run on plain PostgreSQL because `storage` is a Supabase-managed schema.
That is why the local suite reports it as NOT TESTED rather than pretending coverage.

## Verifying storage policies manually, once a project exists

These steps are the evidence trail for the storage layer. They must be run with real accounts, and
the results recorded in the phase report.

1. As user A, create a photo row and upload an object to `<photo_id>/original.jpg`.
2. As user A, request a signed URL through the API and confirm it downloads.
3. As user B, not a friend, request a signed URL for the same photo through the API. Expected:
   HTTP 403 and no URL.
4. As user B, attempt a direct Storage download using B's own access token and the object path.
   Expected: permission denied, because the select policy calls `can_view_photo`.
5. As user B, attempt an upload into A's folder. Expected: permission denied by the insert policy.
6. Make A and B friends, set the photo visibility to `friends`, repeat step 3. Expected: a URL is
   issued, and it works until it expires.
7. Delete the photo as A. Confirm the row is gone and the object is gone.

## Local testing

The test suite creates a dedicated database, applies the stub, applies `001_init.sql`, and runs the
schema, RLS and API tests against it. Nothing touches an existing database.

```bash
cd backend
. .venv/bin/activate
pytest -q
```

## Notes on the model

- `profiles.username` is unique case-insensitively through an index on `lower(username)`.
- `friendships` allows one active relationship per pair in either direction. Rejected requests stay
  as history and do not block a later request.
- The photo object path must start with the owner's id, enforced by a check constraint, so a row
  cannot point into another user's folder.
- The daily upload quota of 20 is enforced by a trigger, not only by the API, so it holds even if a
  client bypasses the API.
- `can_view_photo()` and `are_friends()` are `security definer` helpers with a pinned `search_path`.
  They return booleans only and expose no rows.
