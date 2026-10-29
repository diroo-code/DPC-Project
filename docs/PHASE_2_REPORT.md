# Phase 2 — Database Design, Supabase Authentication, and Security Foundation

**Status: PARTIAL.** The database schema, RLS policies, authentication verification and local security
tests all pass. Live Supabase integration is BLOCKED because no Supabase project exists yet, which the
brief explicitly allows provided it is marked as such and the setup is requested.

Date: 2026-10-29
Scope: schema, auth foundation, security policies, local tests. No frontend, no deployment, no load
testing.

## 1. Work completed

- Designed and wrote the version-controlled schema: `profiles`, `friendships`, `photos`, `comments`,
  `photo_tags`, with UUID primary keys, foreign keys, check constraints, timestamps and indexes.
- Linked `profiles` to `auth.users` with an `after insert` trigger that creates the profile after
  registration, including a collision-safe username fallback and an API-side recovery path for accounts
  that predate the trigger.
- Implemented the friend-request lifecycle as a directed row with `pending`, `accepted`, `rejected`, a
  partial unique index that permits only one active relationship per pair in either direction, and a
  consistency constraint tying `responded_at` to a non-pending status.
- Implemented photo visibility as an enum of `friends` and `owner`, with a single SQL function,
  `user_can_view_photo(user, photo)`, shared by the API and the RLS policies so the rule cannot drift.
- Wrote 19 RLS policies across the five tables, plus 4 Storage object policies in a separate Supabase
  migration.
- Enforced the upload quota of 20 per day in a trigger, and the 5 MB limit and three MIME types in check
  constraints, so the database does not depend on the API for either.
- Added a local Supabase stub (auth schema, `auth.uid()`, storage schema, roles) so migrations and
  policies can be exercised against real PostgreSQL without any cloud account.
- Built the test harness: 90 tests, RLS exercised by `SET ROLE authenticated` with a JWT subject.

## 2. Files created or modified

| File | Purpose |
|---|---|
| `database/migrations/001_init.sql` | Tables, enums, 17 indexes, 19 RLS policies, 5 triggers, helper functions |
| `database/migrations/002_storage.sql` | Private `photos` bucket and 4 `storage.objects` policies, Supabase only |
| `database/migrations/003_view_helper.sql` | Two-argument visibility function; `can_view_photo()` now delegates to it |
| `database/testing/000_local_supabase_stub.sql` | Test-only auth and storage schemas plus role precondition check |
| `database/testing/bootstrap_local_role.sql` | Cluster role `itp_app` and Supabase role names, run once as superuser |
| `database/testing/setup_local_role.sh` | Wrapper that applies the bootstrap |
| `database/README.md` | Schema notes, application order, and the manual Storage verification procedure |
| `backend/app/config.py` | Environment-only configuration, no secrets in code |
| `backend/app/security.py` | Supabase JWT verification, HS256 and JWKS |
| `backend/app/deps.py` | Bearer token dependency, 401 on anything unverified |
| `backend/app/permissions.py` | Permission checks that call the same SQL function the policies use |
| `backend/app/db.py` | Parameterised database access |
| `backend/app/schemas.py` | Request and response models |
| `backend/app/routers/auth.py` | `GET` and `PATCH /api/v1/auth/me` |
| `backend/tests/conftest.py` | Real database per session, Supabase stub, RLS role switching, token factory |
| `backend/tests/test_schema.py` | 19 constraint and trigger tests |
| `backend/tests/test_rls.py` | 15 policy tests, including the security rules in the brief |
| `backend/tests/test_auth_api.py` | 18 token and profile tests |

## 3. Commands executed

| Command | Actual outcome |
|---|---|
| `psql -v ON_ERROR_STOP=1 -f database/testing/000_local_supabase_stub.sql` | exit 0 |
| `psql -v ON_ERROR_STOP=1 -f database/migrations/001_init.sql` | exit 0, no warnings after the grant fix |
| `psql -v ON_ERROR_STOP=1 -f database/migrations/003_view_helper.sql` | exit 0 |
| `python -m pytest -v -o addopts=""` | **90 passed in 8.33 s**, zero warnings |
| `psql -tAc "select count(*) from pg_policies where schemaname='public'"` | 19 |
| `psql -tAc "select count(*) from pg_indexes where schemaname='public'"` | 17 |
| Secret pattern scan over the project, excluding the virtual environment | 0 hits |

## 4. Verification results

Every row is an executed test, not an inspection.

| Test | Expected | Actual | Result |
|---|---|---|---|
| Schema applies from scratch | No errors | exit 0 | PASS |
| Five required tables exist | 5 tables | 5 | PASS |
| RLS enabled on every table | 5 of 5 | 5 of 5 | PASS |
| Profile created after registration | Row with username and display name | Created by trigger | PASS (local stub; live Supabase BLOCKED) |
| Duplicate username handled | Suffixed, no failure | `alice_1` style suffix | PASS |
| Unauthenticated user reads protected data | Denied | `InsufficientPrivilege`, no grants at all | PASS |
| Profile update limited to self | 0 rows for another user | 0 rows | PASS |
| Valid friend request | Insert allowed | Allowed | PASS |
| Forged friend request on another user's behalf | Denied | `InsufficientPrivilege` | PASS |
| Friendship inserted as already accepted | Denied | `InsufficientPrivilege` | PASS |
| Only recipient accepts or rejects | Requester 0 rows, recipient 1 row | 0 and 1 | PASS |
| Duplicate active friendship either direction | Rejected | `UniqueViolation` | PASS |
| Non-friend reads photo | No rows | 0 rows | PASS |
| Friend reads `friends` photo, not `owner` photo | One visible, one hidden | Correct | PASS |
| Comment by non-friend | Denied | `InsufficientPrivilege` | PASS |
| Comment attributed to another user | Denied | `InsufficientPrivilege` | PASS |
| Comments on an owner-only photo hidden from a friend | No rows | 0 rows | PASS |
| Comment deletion rights | Author and photo owner only | Author 1 row, owner 1 row, third party 0 | PASS |
| Tag creation | Owner only | Friend denied, owner allowed | PASS |
| Photo metadata update | Owner only | Friend 0 rows | PASS |
| Upload quota | 21st rejected | `RaiseException` | PASS |
| Photo MIME, size, path ownership constraints | Rejected | `CheckViolation` | PASS |
| Cascading delete | Comments and tags removed | 0 and 0 | PASS |
| `are_friends` and `can_view_photo` agree with the policies | Same answers | Same answers | PASS |
| Private Storage bucket and object policies | Objects not publicly readable | Migration written, not executed | NOT TESTED, BLOCKED |
| Live Supabase registration and email confirmation | Works | No project exists | NOT TESTED, BLOCKED |

## 5. Problems encountered

1. **Role creation failed with "permission denied".** PostgreSQL checks `CREATEROLE` privilege before it
   checks for a duplicate name, so the stub's `exception when duplicate_object` never fired. Fixed by
   moving role creation to a superuser bootstrap script and making the stub assert the roles exist.
2. **Every text column returned as bytes.** The cluster's template databases are SQL_ASCII. Test
   databases are now created explicitly as UTF8 from `template0`, which also matches Supabase.
3. **Blanket function grant warned on pgcrypto internals.** Narrowed to the two helper functions.
4. **Two of my own tests were wrong.** An uppercase username is rejected by the format check before it
   reaches the case-insensitive index, and an uppercase tag is normalised rather than rejected. The
   tests were corrected; the schema was not loosened.
5. **Visibility rule existed twice.** The API needed an explicit user id while the policies relied on
   `auth.uid()`. Rather than duplicate the predicate, migration 003 introduced
   `user_can_view_photo(user, photo)` and made `can_view_photo()` delegate to it.

## 6. Security and operational considerations

- **The backend uses a privileged database connection.** Application checks are therefore the primary
  control, and RLS is the second line protecting direct client access. Both were tested.
- **Storage policies are unverified.** `002_storage.sql` is written and reviewed but has never run,
  because `storage` is Supabase-managed. It is marked NOT TESTED, not passed.
- **A signed URL is a bearer credential.** It works for whoever holds it until it expires. The
  mitigation is a 60 second lifetime and a permission check before issue, not a claim that it cannot
  leak.
- **Profiles are readable by any authenticated user,** which friend discovery requires. No email address
  is stored in `profiles`; it stays in `auth.users`.
- **Keys.** No secret is in the repository. Configuration is environment-only, with `.env.example`
  containing placeholders. The service role key is used server side only.
- **Live Supabase is BLOCKED** on project creation, which requires the owner's account.

## 7. Outstanding items

1. **Supabase project** (owner action): create it, then provide the project URL, anon key and service
   role key through a local `.env` file, never through chat. Until then, live registration, email
   confirmation, Storage and the storage policies remain BLOCKED.
2. **Frontend `.env.example`** and the React application are a Phase 1 scaffolding gap, not Phase 2
   work, so they were not created here.
3. **Git initialisation** is also a Phase 1 gap, deliberately not done in this phase.
4. **Phase 3 work exists ahead of its approval.** The backend API was built before this brief arrived and
   is preserved rather than discarded. It will be verified against the brief's Phase 3 endpoint list when
   that phase is approved.

## 8. Next phase

Per the brief, Phase 3 is the FastAPI backend implementation. The substance already exists and passes 90
tests, so the work would be verification and gap closure against the brief's required endpoint list
(`/health`, `/me`, `/profiles/{user_id}`, friends, photos, comments, `/photos/search`) rather than a
rebuild. No Phase 3 work will start without approval.

## 9. Approval request

Phase 2 is complete to the extent possible without a Supabase project. Please approve either:

- **A.** Phase 2 accepted as PARTIAL with live Supabase BLOCKED, and authorise Phase 3 verification; or
- **B.** Provide the Supabase project details first, so Storage policies, registration and email
  confirmation can move from BLOCKED to PASS before Phase 3.

No further work has been started.
