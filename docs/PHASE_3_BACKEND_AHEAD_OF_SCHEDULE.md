# Phase 2 Report: Backend API

Project: TEB3033 Distributed Photo-Sharing and Commenting System
Date: 2026-10-29
Scope: backend API only. No frontend, no Locust, no cloud resource, no deployment.
Status: complete, awaiting approval for Phase 3

## 1. Scope check before implementation

You asked me to compare the proposed scope against the master prompt before changing anything. The
comparison found a real gap:

- `MASTER_PROMPT.md` defined Phase 0, the Phase 1 entry conditions, and the phase protocol. It did
  **not** define Phase 2 or any later phase.
- The "Phase 2" in my Phase 1 report was my own proposal, and it bundled backend, frontend and
  concurrency testing into one phase. That was wrong for the reason you gave: those are separate
  deliverables with separate evidence.

Resolution: Section G was added to `MASTER_PROMPT.md` as an explicit phase plan, with phases 2 to 6
separated, and a Phase 2 boundary that excludes frontend, Locust and cloud. Only that boundary was
implemented here.

## 2. Implemented

| Endpoint | Behaviour | Permission rule |
|---|---|---|
| `POST /api/v1/photos` | Multipart upload, caption, visibility, comma separated tags | Authenticated, owner is always the caller |
| `GET /api/v1/photos` | Feed with `limit`, `offset`, `uploader`, `date_from`, `date_to`, `q`, `tag` | Only owner, or friend when visibility is `friends` |
| `GET /api/v1/photos/{id}` | Single photo with tags and comment count | Same visibility rule, 404 when not permitted |
| `DELETE /api/v1/photos/{id}` | Object deleted first, then metadata | Owner only; 403 for a visible photo, 404 for an invisible one |
| `GET /api/v1/photos/{id}/url` | 60 second signed URL | Same visibility rule, checked before signing |
| `PUT /api/v1/photos/{id}/tags` | Replace tag set | Owner only |
| `POST /api/v1/friends/requests` | Request by username | Caller is always the requester; self and duplicates rejected |
| `GET /api/v1/friends/requests` | Incoming and outgoing pending requests | Only the caller's own requests |
| `POST /api/v1/friends/requests/{id}/accept` | Accept | Addressee only, pending only |
| `POST /api/v1/friends/requests/{id}/reject` | Reject | Addressee only, pending only |
| `GET /api/v1/friends` | Accepted friends | Caller's friendships only |
| `DELETE /api/v1/friends/{id}` | Remove a friendship | Either party only |
| `GET/POST /api/v1/photos/{id}/comments` | List and create comments | Requires permission to view the photo |
| `DELETE /api/v1/comments/{id}` | Delete a comment | Author or photo owner only |

Supporting work:

- `database/migrations/003_view_helper.sql` adds `user_can_view_photo(user, photo)` so the API and the
  RLS policies share one definition of visibility. `can_view_photo()` now delegates to it. A drift
  between the two would have been a security bug, so the duplication was removed.
- `app/storage.py` defines one storage interface with two drivers. The local driver signs URLs with
  HMAC and an expiry; the Supabase driver is implemented but not tested.
- Deletion order is deliberate: the object is removed first. If storage fails, the row survives, the
  photo stays consistent, and the delete can be retried. Removing the row first would strand an
  unreachable object.

## 3. Tested, with results

`88 passed in 8.14s`, zero warnings. The 50 Phase 1 tests are unchanged and still passing, which
covers your instruction to preserve them.

| Suite | Tests | Status |
|---|---|---|
| `test_schema.py` | 19 | PASS |
| `test_rls.py` | 13 | PASS |
| `test_auth_api.py` | 18 | PASS |
| `test_photos_api.py` | 26 | PASS |
| `test_social_api.py` | 12 | PASS |
| **Total** | **88** | **PASS** |

Security-sensitive behaviours verified by test, not by inspection:

1. A non-friend sees an empty feed and receives 404 for the photo and for its signed URL.
2. A friend sees a `friends` photo and not an `owner` photo, in the feed, the single fetch and the URL.
3. A signed URL serves the exact uploaded bytes, and a tampered signature is rejected with 403.
4. A correctly signed but expired URL is rejected with 403 and the message says expired.
5. Deleting a photo removes both the row and the object, and cascades comments and tags.
6. A simulated storage outage during delete returns 502 and leaves the metadata row intact, so no
   silent inconsistency is created.
7. A non-owner cannot delete (403 when visible, 404 when not), cannot tag, and cannot edit metadata.
8. Only the addressee may accept or reject; the requester receives 403. A third party receives 403.
9. Duplicate requests in either direction are rejected with 409; self requests with 400; unknown users
   with 404.
10. Comments require permission to view the photo. Deletion is allowed for the author and the photo
    owner, and refused for a third party.
11. Upload validation rejects a declared image type whose bytes do not match, rejects files over 5 MB,
    and accepts only JPEG, PNG and WebP.
12. The 20-per-day quota returns 429 from the API and is independently enforced by a database trigger.
13. Tags are normalised to lower case; invalid characters are rejected with 422.
14. Every protected endpoint returns 401 without a token.

Live verification, three real users on a real Uvicorn process:

```
alice uploads            201, tags ['lake','sunset']
bob, not a friend        feed total 0, signed URL 404
alice asks, bob accepts  pending -> accepted, 200
bob after friendship     feed total 1, comment 201, author attributed correctly
signed URL               60 s, fetch 200, 2052 bytes, byte identical
carol requests URL       404
tampered signature       403
alice deletes            204, bob's feed total 0, only carol's object remains
carol accepts a request addressed to bob   403
unauthenticated upload   401
```

Evidence: `evidence/PHASE_2_PYTEST.log` (88 named tests), `evidence/PHASE_2_LIVE_CHECK.log`
(the full HTTP transcript), `tests/live_check_phase2.sh` (reproducible).

## 4. Not tested, and why

| Item | State | Reason |
|---|---|---|
| Supabase Storage driver (`SupabaseStorage`) | NOT TESTED | No Supabase project exists. Implemented against the documented client API only |
| `002_storage.sql` bucket and object policies | NOT TESTED | Requires the real `storage` schema. Procedure is documented in `database/README.md` |
| Real signed URL from Supabase | NOT TESTED | Same reason. Local HMAC driver proves expiry and tamper handling, not Supabase's implementation |
| Email confirmation on registration | NOT TESTED | Requires a live project and mailbox |
| Rate limiting | NOT IMPLEMENTED | Deliberate: it belongs with deployment hardening, not the API surface. Recorded for Phase 5 |
| Load behaviour under concurrency | NOT TESTED | Phase 4, by design |

## 5. Limitations

1. **Pagination is offset based.** Rows inserted between page requests can shift results. Acceptable at
   coursework scale and simpler to demonstrate; cursor pagination is the fix if the feed grows.
2. **Search uses `ILIKE`** on caption with no trigram index. Fine at this data volume, slow on a large
   table.
3. **The local media endpoint treats the signed URL as a capability.** Authorisation happens before
   signing, and the URL then works for anyone holding it until expiry. That matches Supabase signed URL
   semantics and is the residual risk already recorded in decision 8, not a defect introduced here.
4. **The Supabase driver has never executed.** It is code, not verified behaviour, and the report says so
   rather than implying parity with the tested driver.
5. **Quota boundaries use the UTC day**, so a user's local day can differ.
6. **Visibility checks cost a query.** Each read calls `user_can_view_photo`, and the feed embeds the
   same predicate. At this scale that is correct and simple; a materialised audience table would be the
   optimisation if needed.

## 6. Phase 3 proposal

Frontend only: React and Vite application wired to Supabase Auth for sign-in and to these endpoints for
feed, upload, friend requests and comments. No Locust, no deployment, no schema changes unless a
frontend requirement exposes a genuine gap, in which case it is raised rather than quietly patched.

Phase 2 is complete and stopped here.
