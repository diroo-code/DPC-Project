# Phase 5 — Integration Testing, Security Review and Bug Fixes

**Status: PASS** for everything the environment can verify. Supabase-dependent behaviour remains
BLOCKED and is not claimed as tested.

Date: 2026-10-29
Scope: integration, browser end-to-end testing, security review, dependency checks, bug fixes. No
deployment, no push, no public exposure.

## 1. Integration testing

The frontend and backend were run together as real processes: Uvicorn on port 8010 and the Vite dev
server on 5175, both bound to 127.0.0.1. Three controlled accounts were created directly in the
database, and a real Chromium instance drove the interface through Playwright.

**16 of 16 browser checks passed.** Full journey:

| Check | Result |
|---|---|
| Signed-in user lands on the feed | PASS |
| Upload through the form, then redirect to the photo | PASS |
| Access token is not in `localStorage` | PASS |
| Comment appears with the correct author | PASS |
| A script in a caption does not execute | PASS |
| The script text is displayed as text, not interpreted | PASS |
| Stranger sees an empty feed | PASS |
| Stranger sees no photo captions at all | PASS |
| Stranger cannot open a friend-only photo | PASS |
| Outgoing friend request appears for the sender | PASS |
| Recipient accepts, and both sides see the friendship | PASS |
| Friend sees the shared photo in the feed | PASS |
| Friend cannot open an owner-only photo | PASS |
| Search finds the matching caption | PASS |
| Search excludes the owner-only photo | PASS |
| Profile save is confirmed | PASS |

Roles exercised: photo owner, accepted friend, stranger, and a comment author, plus an author viewing
another user's comment permissions. All eight screens were reached: login, register, feed, search,
upload, photo detail, friends and profile.

## 2. Defects found and fixed

### D1. First request after sign-in went out unauthenticated (real defect, fixed)

The API client received its token through a provider installed in a `useEffect`. React runs child
effects before parent effects, so a screen's data fetch fired before the auth provider installed the
token. The request arrived with no `Authorization` header and the API correctly returned
`missing bearer token`.

Observed as an intermittent empty feed and a failed upload, which is exactly the kind of defect a
browser run finds and a component test with a mocked API cannot. Fixed by installing the provider
synchronously during render. Re-verified by the full browser run: 16 of 16 pass, including uploads and
feeds for all three accounts.

### D2. Test harness asked the wrong port, twice (test infrastructure, fixed)

Ports 8000 and 5173 were already occupied by unrelated services on this machine. My first run silently
tested against another application's page on 5173. The harness now uses 8010 and 5175, asserts the
served page is this project before testing, and kills the listener by PID rather than the `npx` wrapper.

### D3. Test selectors were ambiguous (test code, fixed)

"Upload" matched both the nav link and the empty-state link, and the upload assertion raced the render.
Selectors are now exact and the assertion waits for the heading.

## 3. Test results

| Suite | Result |
|---|---|
| Backend, full suite | **126 passed in 11.43 s** |
| Frontend component tests | **17 passed**, 4 files |
| Browser end-to-end | **16 of 16 checks passed** |
| Production build | Success, 77 modules, 353 ms |

Backend suite composition: 19 schema, 15 RLS, 18 auth, 26 photos, 12 social, 25 contract, 11 security.

## 4. Security review

| Area | What was checked | Result |
|---|---|---|
| XSS | A caption containing `<img src=x onerror=...>` uploaded through the UI and rendered on the photo page | PASS: no execution, text displayed literally. React escapes by default and the codebase has no `dangerouslySetInnerHTML` |
| API authorisation | Stranger, friend and owner access to feed, single photo, signed URL, comments, deletion, tagging | PASS: enforced server side and covered by 15 RLS tests plus contract tests |
| Token handling | Bearer only, `alg: none` forged token rejected, 401 carries `WWW-Authenticate`, token kept in `sessionStorage` not `localStorage` | PASS |
| CORS | Configured origin allowed, unknown origin receives no allow header, preflight allows `authorization` | PASS, three tests |
| Injection | SQL metacharacters in the search query, three payloads | PASS: parameterised, zero rows, table intact |
| Path traversal | Upload filename `../../etc/passwd.jpg` | PASS: server generates the object name from the photo id, path stays inside the storage root |
| Input validation | Oversize, wrong MIME, spoofed content, malformed UUID, JSON instead of multipart | PASS, rejected with 413, 415, 422 |
| Error leakage | Validation and 401 bodies inspected for tracebacks, driver names, SQL | PASS: none present |
| Secret exposure | Bundle scan for `service_role` and JWT-like strings; gitleaks on every commit | PASS: none found, scan clean |
| CSP | Response headers inspected | **NOT PRESENT.** No Content-Security-Policy is set. Recorded as an open risk, not a pass |
| Rate limiting | Code and behaviour inspected | **NOT IMPLEMENTED.** Recorded as an open risk, not a pass |

The two findings above are gaps, not defects in shipped code, and are listed in section 6 with the
concrete fix.

## 5. Dependency and production checks

| Check | Before | After |
|---|---|---|
| `npm audit --omit=dev` | 0 vulnerabilities | 0 vulnerabilities |
| `npm audit` including dev | 3 (1 moderate, 2 critical) in `vitest` and `tinypool` | **0**, after upgrading Vitest to 5.0.5 |
| `pip-audit -r requirements.txt` | No known vulnerabilities | No known vulnerabilities |
| Production build | Success | Success, 292.81 kB JS (92.07 kB gzip), 4.84 kB CSS |
| Bundle secret scan | Clean | Clean |

The critical advisories were in the test runner, which never ships, but a prototype-pollution RCE in a
developer tool is still worth removing. Vitest 5.0.5 required no test changes: all 17 frontend tests pass
on the new major version.

## 6. Remaining risks

1. **No Content-Security-Policy.** A strict policy is needed before public deployment, and it must be
   set by the hosting layer or a meta tag, not by the application code. Recommended: default-src 'self',
   img-src 'self' plus the Supabase storage origin, connect-src 'self' plus the API origin, no inline
   scripts.
2. **No rate limiting.** A login or upload flood is unthrottled. Recommended before deployment: a
   per-IP limiter on uploads, comments and auth-adjacent endpoints.
3. **Token in browser storage.** `sessionStorage` limits the blast radius but XSS would still read it.
   The CSP in item 1 and continued escaping discipline are the mitigations.
4. **Signed image URLs are bearer credentials** for 60 seconds.
5. **Supabase authentication was not exercised.** The browser run used the development token path. Real
   login, email confirmation and token refresh are BLOCKED.
6. **Storage is the local driver.** Real Supabase Storage upload and download remain BLOCKED.
7. **No load testing.** Phase 8 by the brief's numbering, not started.
8. **Ports 8000 and 5173 are occupied on this machine** by unrelated services, so the test harness uses
   8010 and 5175. Deployment must choose its own ports.

## 7. Blocked items

| Item | Reason |
|---|---|
| Supabase registration, login, email confirmation | No Supabase project |
| Supabase Storage upload, download, signed URLs | No Supabase project |
| Storage bucket and object policies | Requires the real `storage` schema |
| JWKS / ES256 verification | No real project keys |
| GitHub push | No remote and no authorisation |

## 8. Change summary

| File | Change |
|---|---|
| `frontend/src/lib/auth.jsx` | Token provider installed synchronously, fixing the unauthenticated first request |
| `frontend/vite.config.js` | Proxy target configurable; dev server port choice documented |
| `frontend/package.json` | Vitest upgraded to 5.0.5, clearing all advisories |
| `backend/tests/test_security_phase5.py` | 11 new security tests: CORS, algorithm confusion, SQL injection, path traversal, error leakage |
| `tests/e2e_phase5.py` | Real-browser end-to-end suite, 16 checks, self-contained servers and database |
| `docs/PHASE_5_REPORT.md` | This report |

Repository state: local Git only. No remote, nothing pushed, nothing deployed, no paid resource created.

## 9. Approval request

Phase 5 is complete and stopped. Phase 6 in the brief is GitHub and cloud deployment preparation, which
needs your accounts and explicitly your approval before anything leaves this machine. Please approve, or
ask for the CSP and rate limiting work to be folded into this phase first.

---

## 10. Post-review security additions (the two accepted gaps, now closed)

### 10.1 Content Security Policy

Implemented as both a build-time meta tag and a hosting header, because they cover different delivery
paths.

- `vite.config.js` injects a CSP meta tag during `vite build` only, so the dev server keeps working.
- `frontend/public/_headers` ships the Cloudflare Pages header policy, including `frame-ancestors`,
  which browsers ignore inside a meta tag. It also sets `X-Content-Type-Options`, `Referrer-Policy`,
  `Permissions-Policy` and `X-Frame-Options`.
- The policy is generated from `VITE_API_BASE_URL` and `VITE_SUPABASE_URL`, not hardcoded. A build
  pointed at real origins allows exactly those origins.

Directives in force:

```
default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';
img-src 'self' data: blob: <api origin> <supabase origin>;
font-src 'self'; connect-src 'self' <api origin> <supabase origin>;
object-src 'none'; base-uri 'self'; form-action 'self'; upgrade-insecure-requests
```

Evidence:

| Check | Result |
|---|---|
| 13 static and live checks in `tests/check_csp.py` | **13 of 13 pass** |
| `script-src` free of `unsafe-inline` and `unsafe-eval` | PASS |
| `object-src 'none'`, `base-uri 'self'` | PASS |
| `frame-ancestors 'none'` present in the header policy and absent from the meta tag | PASS |
| Built page loaded in Chromium with zero CSP violations | PASS |
| Build with example origins produced `connect-src 'self' https://api.example.test https://demo.supabase.co` and no wildcard | PASS |
| Default build, no origins configured | `connect-src 'self'` only |

Configuration requirement: the deployment build must set `VITE_API_BASE_URL` and `VITE_SUPABASE_URL`.
If the API origin is omitted, `connect-src` stays at `'self'` and a separately hosted API will be
blocked by the browser. That is a build-time requirement, recorded here rather than discovered during
deployment.

Limitations, stated plainly: `style-src` allows inline styles because the components use React style
attributes. Scripts remain strict. A nonce-based style policy would require removing those attributes.
The meta tag cannot enforce `frame-ancestors`, so the header policy is the control that matters on
Cloudflare Pages.

### 10.2 Server-side rate limiting

`backend/app/ratelimit.py` implements a sliding window keyed by authenticated user, guarded by a
`threading.Lock` so concurrent requests cannot both take the last slot.

| Bucket | Limit | Window |
|---|---|---|
| Photo upload | 10 | 60 s |
| Comment creation | 20 | 60 s |
| Friend request | 10 | 1 h |
| Signed URL issuance | 60 | 60 s |
| Photo deletion | 20 | 60 s |

Blocked requests return HTTP 429 with `Retry-After`, and a rejected request is not counted, so a client
cannot extend its own lockout by retrying.

Evidence, 8 new tests:

| Check | Result |
|---|---|
| Budget allows exactly N then blocks | PASS |
| Window expiry releases the budget | PASS |
| **30 concurrent threads racing for 10 slots, exactly 10 allowed** | PASS |
| Separate users have separate budgets | PASS |
| Comment endpoint returns 429 with `Retry-After` | PASS |
| Upload endpoint returns 429 and stores nothing on rejection | PASS |
| One user cannot spend another user's budget | PASS |
| Rejected requests do not extend the window | PASS |

Backend suite after both additions: **134 passed in 12.86 s**.

Limitations: the counters live in process memory. With one Uvicorn process the limit is exact; with
several workers each worker enforces its own limit, so the effective ceiling is multiplied. A shared
Redis counter is required for a multi-worker deployment, and that is recorded as a deployment task, not
claimed as solved. The numbers are constants in `LIMITS`, deliberately not environment-tunable, so a
misconfigured deployment cannot silently disable them.

### 10.3 Verification after the changes

| Check | Result |
|---|---|
| Backend suite | **134 passed in 12.86 s** |
| Frontend tests | **17 passed** |
| Browser end-to-end | **16 of 16 checks passed** |
| CSP checks | **13 of 13 passed** |
| `npm audit --omit=dev` | 0 vulnerabilities |
| `npm audit` including dev | 0 vulnerabilities |
| `pip-audit -r requirements.txt` | No known vulnerabilities |
| Production build | Success, 292.81 kB JS, 4.84 kB CSS |

### 10.4 Remaining risks after these fixes

1. `style-src` permits inline styles. Scripts do not.
2. Rate limiting is per process, so a multi-worker deployment needs a shared counter.
3. Supabase authentication and Storage remain BLOCKED and untested against a real project.
4. Signed URLs remain bearer credentials for 60 seconds.
5. No load testing yet; rate limiting has only been tested locally, not against a hosted service.
