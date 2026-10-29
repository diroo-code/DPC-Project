# Phase 1 Report: Schema, Authentication Wiring and Test Harness

Project: TEB3033 Distributed Photo-Sharing and Commenting System
Date: 2026-10-29
Scope authorised: database schema, authentication wiring, test harness, in that order
Status: complete, awaiting approval for Phase 2
Application UI: not started, as instructed
Cloud resources: none created, none deployed, no paid action taken

## 1. What was built

| Area | Deliverable | Size |
|---|---|---|
| Schema | `database/migrations/001_init.sql` | 446 lines |
| Storage policies | `database/migrations/002_storage.sql` | 78 lines, Supabase only |
| Local Supabase stub | `database/testing/000_local_supabase_stub.sql` | 75 lines, test only |
| Local role bootstrap | `database/testing/bootstrap_local_role.sql` plus `setup_local_role.sh` | 25 lines |
| Backend application | `backend/app/` (config, db, security, deps, schemas, main, 2 routers) | 460 lines |
| Test harness | `backend/tests/` (conftest plus 3 suites) | 653 lines |
| Documentation | `database/README.md`, this report | |

Total 2,020 lines of SQL, Python and tests.

### 1.1 Database

Five tables with UUID primary keys, foreign keys and check constraints:

- `profiles`, one row per `auth.users` row, created by an `after insert` trigger on `auth.users`.
- `friendships`, with a directed requester and addressee, a status enum, and a partial unique index
  on the undirected pair so only one active relationship can exist while rejected requests remain as
  history.
- `photos`, metadata only, with the binary in Storage. The storage path must begin with the owner id,
  enforced by a check constraint.
- `comments`, cascading from photos, with length constraints.
- `photo_tags`, composite primary key on `(photo_id, tag)`, normalised to lower case by a check.

19 RLS policies across the five tables, 17 indexes, 5 triggers. The helper functions
`are_friends()` and `can_view_photo()` are `security definer` with a pinned `search_path`, and return
booleans only. The daily upload quota of 20 is enforced by a trigger, so it holds even if the API is
bypassed.

### 1.2 Authentication wiring

The backend never handles a password. Supabase Auth issues the token, and the API verifies it:

- HS256 verification with `SUPABASE_JWT_SECRET` for legacy projects.
- ES256/RS256/EdDSA verification through the project JWKS for current projects, selected by `kid`,
  with PyJWT caching the key set.
- Audience and expiry are required and verified. Missing, malformed, expired, wrong-audience and
  wrongly-signed tokens are all rejected with 401.
- `GET /api/v1/auth/me` returns the profile, creating it only if the trigger did not run, so accounts
  that predate the trigger still work.
- `PATCH /api/v1/auth/me` updates `display_name` and `bio`. Unknown fields are rejected with 422, so a
  client cannot attempt to change `id` or `username`.
- `GET /health` never touches the database. `GET /ready` reports database reachability and returns 503
  when it is down.

### 1.3 Test harness

A real PostgreSQL 15.19 instance, a dedicated database created per session, the Supabase stub applied,
then the production migration. RLS is exercised by `SET ROLE authenticated` with
`request.jwt.claim.sub`, which is the same mechanism a browser client uses. Running as the table owner
would bypass RLS and prove nothing, so that is deliberately avoided.

## 2. Decisions recorded

The nine decisions approved on 2026-10-29 are now part of `MASTER_PROMPT.md` Section F1 and are
reflected in the schema: friends-only visibility with an owner-only option, owner-only tagging, comment
deletion by author or photo owner, open registration with email confirmation, hard deletion with
cascade, 5 MB limits on JPEG, PNG and WebP, 20 uploads per day, 60 second signed URLs, and multi-user
design without waiting for the confirmed group size.

## 3. Verification

Every item below is a command that was run, with its actual result.

| # | Check | Command | Result | Status |
|---|---|---|---|---|
| 1 | Migration applies from scratch | `psql -v ON_ERROR_STOP=1 -f 001_init.sql` | exit 0, no warnings after the grant fix | PASS |
| 2 | Expected tables exist | information_schema query | 5 tables | PASS |
| 3 | RLS enabled on every table | pg_class query | 5 of 5 true | PASS |
| 4 | Policy inventory | pg_policies | 19 policies | PASS |
| 5 | Full test suite | `pytest` | 50 passed in 4.28 s | PASS |
| 6 | Schema and constraint tests | `pytest tests/test_schema.py` | 19 passed | PASS |
| 7 | RLS tests | `pytest tests/test_rls.py` | 13 passed | PASS |
| 8 | API and token tests | `pytest tests/test_auth_api.py` | 18 passed | PASS |
| 9 | Live server health | `GET /health` on a real Uvicorn process | 200, `{"status":"ok",...}` | PASS |
| 10 | Live database readiness | `GET /ready` | 200, `{"status":"ready","database":"ok"}` | PASS |
| 11 | Missing token rejected | `GET /api/v1/auth/me` | 401, `missing bearer token` | PASS |
| 12 | Malformed token rejected | Bearer not-a-jwt | 401, `malformed token header` | PASS |
| 13 | Valid token accepted | Bearer token, real signature | 200, profile from the trigger | PASS |
| 14 | Profile update | `PATCH /api/v1/auth/me` | 200, `updated_at` advanced | PASS |
| 15 | API documentation served | `GET /docs` | 200 | PASS |
| 16 | Clean shutdown | kill by PID | process stopped, port released | PASS |

Evidence files: `evidence/PHASE_1_PYTEST.log` (50 named tests) and
`evidence/PHASE_1_LIVE_CHECK.log` (the live HTTP transcript).

### 3.1 Starlette test-client deprecation: resolved by measurement

Phase 0 recorded `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated;
install httpx2` with FastAPI 0.162.0, Starlette 1.10.0 and HTTPX 0.28.1.

Both candidate resolutions were tested in a throwaway virtual environment before adoption. Adding
`httpx2` 2.16.0 produced a passing request and zero warnings, with **no version downgrades**. That
option was adopted. `pytest.ini` now turns a Starlette `DeprecationWarning` into a test error, so the
warning cannot silently return: the 50 passing tests are the proof that it is gone. The alternative,
pinning older FastAPI, Starlette and HTTPX versions, was not needed and was not adopted.

## 4. Security properties demonstrated

These are tested behaviours, not claims:

- A stranger sees no photo rows at all, a friend sees only `friends` visibility, and the owner sees
  both visibilities.
- The anonymous role has no table grants at all, which is stricter than an empty result set.
- A user cannot forge a friend request on another user's behalf; the insert is rejected by the policy.
- Only the addressee may accept a request. The requester's update affects zero rows.
- A non-friend cannot comment. A friend can. A friend cannot see comments on an owner-only photo.
- Comment deletion is limited to the author and the photo owner; a third party deletes zero rows.
- Only the photo owner can add tags, and a friend can read tags on a photo they may view.
- Only the owner can change photo metadata.
- Profile updates affect only the caller's row.
- Upload quota, MIME type, size, tag format, blank comments and self-friendship are all rejected at the
  database, independently of the API.
- Deleting a photo cascades to its comments and tags.

## 5. Not tested, and why

Stated plainly rather than scored as passing:

| Item | Reason | Will be verified |
|---|---|---|
| `002_storage.sql` bucket and object policies | Requires a real Supabase project; the `storage` schema is Supabase-managed and cannot be faithfully emulated | Phase 3, against the real project, using the seven step procedure in `database/README.md` |
| JWKS / ES256 verification path | Implemented, but only HS256 is exercised locally; no real project keys exist yet | Phase 3, with the first real Supabase token |
| Supabase email confirmation flow | Requires a real project and a mailbox | Phase 3 |
| Signed URL issuance and expiry | Depends on Storage; the endpoint does not exist yet | Phase 2 and Phase 3 |
| Rate limiting on API endpoints | Not implemented yet | Phase 2, before public deployment |
| Frontend | Out of Phase 1 scope by instruction | Phase 2 |

## 6. Limitations and risks to carry forward

1. **Signed URLs are bearer credentials.** As approved in decision 8, a valid URL works for whoever
   holds it until it expires. Mitigations are server-side permission checks before issuance, a 60
   second lifetime, and no logging of the URL itself. This residual risk will be documented in the
   report rather than described as solved.
2. **The backend uses a privileged database connection.** Therefore the explicit checks in application
   code are the primary control, and RLS protects the direct client path and acts as defence in depth.
   Every endpoint must still check ownership and friendship itself; RLS alone is not the argument.
3. **Profiles are readable by any authenticated user.** This is required for friend discovery by
   username. No email address is stored in `profiles`; email remains in `auth.users`, which the client
   cannot read. If the brief wants stricter profile privacy, the discovery query needs a different
   design, so this is recorded as a deliberate trade-off.
4. **The local cluster is SQL_ASCII.** Test databases are created explicitly as UTF8 from `template0`
   so tests match Supabase. This is a local environment quirk, not an application property.
5. **The quota counts by UTC day.** A user's local day may differ from the UTC boundary.

## 7. Phase 2 proposal

1. Photo endpoints: create, list feed with pagination, filtered search, delete with safe handling of a
   failed Storage delete.
2. Signed URL endpoint with the permission check and 60 second expiry.
3. Friend request endpoints and comment and tag endpoints, each with server-side checks mirroring the
   policies now proven.
4. React and Vite frontend scaffold wired to Supabase Auth, with the feed, upload and comments.
5. Locust scenario for concurrent uploads and comments.

Phase 1 is complete and stopped here. No Phase 2 work has begun.
