# Phase 3 — FastAPI Backend Implementation (verification and gap closure)

**Status: PASS** for the brief's endpoint list, with live Supabase integration still BLOCKED.

Date: 2026-10-29
Method: audit first, fix only gaps, preserve all working code.

## 1. Endpoint audit matrix

Every required endpoint, where it lives, how it is authorised, and the tests that prove it.

| Required endpoint | Implementation | Authorisation | Test evidence | Status |
|---|---|---|---|---|
| `GET /health` | `routers/health.py` | None, by design, never touches the database | `test_health_at_root`, `test_health_returns_expected_shape` | PASS |
| `GET /me` | `routers/auth.py`, `brief_router` | Bearer token, unverified tokens rejected | `test_me_requires_a_token`, `test_me_returns_the_caller_profile`, `test_me_and_versioned_route_agree` | PASS (added) |
| `GET /profiles/{user_id}` | `routers/profiles.py` | Authenticated; public fields only, no email | `test_profile_returns_public_fields_only`, `…requires_authentication`, `…unknown_id_is_404`, `…malformed_id_is_422` | PASS (added) |
| `POST /friends/requests` | `routers/social.py` | Caller is always the requester; self, unknown and duplicate rejected | `test_send_request`, `test_cannot_befriend_yourself`, `test_unknown_username_returns_404`, `test_duplicate_request_is_rejected` | PASS |
| `GET /friends/requests` | `routers/social.py` | Only the caller's incoming and outgoing requests | `test_requests_are_listed_by_direction` | PASS |
| `POST /friends/requests/{id}/accept` | `routers/social.py` | Addressee only, pending only | `test_only_the_addressee_can_accept` | PASS |
| `POST /friends/requests/{id}/reject` | `routers/social.py` | Addressee only, pending only | `test_reject_leaves_no_friendship` | PASS |
| `GET /friends` | `routers/social.py` | Accepted friendships of the caller only | `test_friends_list_and_removal`, `test_friends_at_brief_path` | PASS |
| `POST /photos` | `routers/photos.py` | Authenticated; owner is the caller; MIME, size and quota validated server side | `test_upload_creates_row_tags_and_object`, `…requires_authentication`, `…unsupported_type`, `…oversize_file`, `…content_that_does_not_match`, `test_api_enforces_the_daily_quota` | PASS |
| `GET /photos` | `routers/photos.py` | Visibility predicate: owner, or friend when `friends` | `test_feed_shows_only_visible_photos`, `test_feed_pagination`, `test_photos_path_mirrors_the_versioned_contract` | PASS |
| `GET /photos/{photo_id}` | `routers/photos.py` | Same predicate; 404 rather than leaking existence | `test_get_photo_hides_from_stranger`, `test_single_photo_and_delete_at_brief_paths` | PASS |
| `DELETE /photos/{photo_id}` | `routers/photos.py` | Owner only; 403 when visible, 404 when not; storage failure leaves the row intact | `test_delete_removes_row_and_object`, `…non_owner_is_forbidden`, `…aborts_when_storage_fails` | PASS |
| `POST /photos/{id}/comments` | `routers/social.py` | Requires permission to view the photo; author is the caller | `test_comment_on_a_shared_photo`, `test_cannot_comment_on_an_owner_only_photo` | PASS |
| `GET /photos/{id}/comments` | `routers/social.py` | Requires permission to view the photo | `test_comment_on_a_shared_photo`, `test_comments_at_brief_paths` | PASS |
| `DELETE /comments/{id}` | `routers/social.py` | Comment author or photo owner only | `test_comment_deletion_by_author_and_owner` | PASS |
| `GET /photos/search?q=` | `routers/photos.py` | Same visibility predicate as the feed | `test_search_matches_caption`, `…does_not_leak_invisible_photos`, `…filters_by_tag_and_uploader`, `…pagination`, `…requires_a_query` | PASS (added) |
| Signed URL (supporting) | `GET /photos/{id}/url` | Permission checked before signing, 60 second TTL | `test_signed_url_for_owner_and_friend_only`, `…serves_the_actual_bytes`, `…rejects_a_tampered_signature`, `…expires` | PASS |

Route surface: the versioned contract is `/api/v1/...` and the brief's literal paths are served by the
same handlers mounted a second time, hidden from the OpenAPI schema. One implementation, two entry
points, no drift.

## 2. Files created or modified

| File | Change |
|---|---|
| `backend/app/routers/photos.py` | Prefix removed so the router can be mounted twice; query extracted into `_query_photos`; `GET /photos/search` added before `/{photo_id}` so "search" is not parsed as a UUID |
| `backend/app/routers/social.py` | Prefix removed for the same dual mounting |
| `backend/app/routers/profiles.py` | New: `GET /profiles/{user_id}` returning public fields only |
| `backend/app/routers/auth.py` | New `brief_router` serving `GET /me` from the same handler as `/api/v1/auth/me` |
| `backend/app/schemas.py` | `PublicProfileOut` with no email field |
| `backend/app/main.py` | Mounts the versioned and brief paths; imports the profiles router |
| `backend/tests/test_phase3_contract.py` | New: 25 tests covering the required endpoints, negative cases, invalid input, pagination and errors |
| `tests/live_check_phase3.sh` | New: live verification of the brief paths on a real server |
| `docs/PHASE_3_REPORT.md` | This report |

## 3. Commands executed

| Command | Actual outcome |
|---|---|
| `python -m pytest -v -o addopts=""` | **115 passed in 10.58 s**, zero warnings |
| `bash tests/live_check_phase3.sh` | exit 0, all brief paths correct |
| Route introspection of the app | 5 visible routes plus 4 lazily included routers |

## 4. Verification results

Suite composition, all passing:

| Suite | Tests |
|---|---|
| `test_schema.py` | 19 |
| `test_rls.py` | 15 |
| `test_auth_api.py` | 18 |
| `test_photos_api.py` | 26 |
| `test_social_api.py` | 12 |
| `test_phase3_contract.py` | 25 |
| **Total** | **115** |

The 90 tests that existed before this phase still pass unchanged. Nothing was weakened to make a new
test pass.

Live server, real database, brief paths:

```
GET /health                200
GET /me (no token)         401
GET /me                    200, profile for the token subject
GET /profiles/{id}         200, public fields only
GET /profiles/unknown      404
POST /photos               201
GET /photos                200, total 1
GET /photos/search?q=      200, total 1
GET /photos/search (no q)  422
GET /photos/{id}/comments  200
GET /friends               200
GET /photos/{id}           200
DELETE /photos/{id}        204
```

Negative coverage added this phase: missing and malformed query parameters (`limit=0`, `limit=51`,
`offset=-1`, overlong `q`), missing search query, unknown ids, malformed UUIDs, unknown routes, wrong
HTTP method, non-owner deletion and tagging at the brief paths.

## 5. Problems encountered

1. **Apparent missing routes.** Introspecting `app.routes` showed only five routes, which looked like
   the routers had never been included. They had: FastAPI 0.162 stores included routers lazily as
   `_IncludedRouter` objects and resolves them per request. I verified this before changing anything,
   because "fixing" it would have broken a working application.
2. **Route ordering.** `/photos/search` must be declared before `/photos/{photo_id}` or the path segment
   is parsed as a UUID and returns 422. It is declared first and a test asserts the search behaviour.
3. **Dual mounting.** Mounting the same router twice produces duplicate operation ids in the schema, so
   the brief paths are mounted with `include_in_schema=False`. The published contract stays single.

## 6. Blocked items

| Item | State | Reason |
|---|---|---|
| Supabase registration and email confirmation | BLOCKED | No project exists |
| Supabase Storage upload, download and signed URLs | BLOCKED | No project exists; local driver tested instead |
| Storage bucket and object policies (`002_storage.sql`) | BLOCKED | The `storage` schema is Supabase-managed |
| JWKS / ES256 token verification | NOT TESTED | Only HS256 is exercised locally; no real project keys |

None of these are claimed as passing anywhere in this report.

## 7. Outstanding work from the original plan

Recorded, not skipped:

1. **React and Vite scaffolding.** `frontend/` is still empty. The toolchain was verified in Phase 0 with
   a throwaway application, but the project's own frontend has not been created. This is Phase 4 work.
2. **Git initialisation.** The project has `.gitignore` but no repository. This belongs to the plan's
   Phase 1 and Phase 6; it is not done, and no commit history exists yet.

## 8. Remaining risks

1. **Offset pagination** can shift results when rows are inserted between page requests.
2. **Search is `ILIKE`** with no trigram index: fine at this size, slower on a large table.
3. **Local storage driver** is a test double. The Supabase driver has never executed.
4. **Signed URLs are bearer credentials** for 60 seconds, by design.
5. **No rate limiting** on any endpoint yet.
6. **Profile enumeration** by UUID is possible for any authenticated user, which friend discovery
   requires. No email is exposed.

## 9. Next phase

Phase 4 is the React and Vite frontend. No frontend work has been started. Deployment, Locust and cloud
resources remain untouched.

## 10. Approval request

Phase 3 is complete and stopped. Please approve Phase 4, or ask for any part of this audit to be
re-verified first.
