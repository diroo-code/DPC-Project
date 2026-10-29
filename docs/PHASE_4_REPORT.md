# Phase 4 — React and Vite Frontend Implementation

**Status: PARTIAL.** Every screen is implemented, tested at the component level and built for
production. Real Supabase authentication and Storage remain BLOCKED, and the interface says so rather
than pretending otherwise.

Date: 2026-10-29
Scope: frontend only. No deployment, no Locust, no cloud resource.

## 1. Work completed

Screens implemented in `frontend/src/pages/`:

| Screen | Route | What it does |
|---|---|---|
| Login | `/login` | Email and password when Supabase is configured. Without it, an explicit notice, or a development token field when `VITE_DEV_AUTH=1` |
| Register | `/register` | Username, display name, email, password with client validation. Without Supabase it states that registration is blocked |
| Feed | `/` | Photos the user may see, signed image URLs, pagination with Load more, empty state, error state |
| Search | `/search` | Caption, tag, uploader and date filters against `/photos/search`, with pagination |
| Upload | `/upload` | File picker with client-side type and size checks, caption, visibility choice (friends or owner), tags |
| Photo detail | `/photos/:id` | Full image, metadata, tags, comments, add comment, delete own comment, delete photo with confirmation |
| Friends | `/friends` | Send request by username, incoming and outgoing requests, accept, reject, remove friend |
| Profile | `/profile` | View and edit display name and bio |

Cross-cutting: responsive layout, skip link, labelled fields, visible focus outlines, loading
indicators, empty states, error banners with retry, confirmation before destructive actions, and a
navigation bar that only appears when signed in.

## 2. Files created or modified

| File | Purpose |
|---|---|
| `frontend/package.json` | React 19, Vite 8, React Router 7, Supabase JS; Vitest and Testing Library |
| `frontend/vite.config.js` | Dev proxy to the API, automatic JSX runtime, Vitest jsdom setup |
| `frontend/index.html` | Entry document |
| `frontend/.env.example` | Public configuration only, with a warning about what must never be prefixed `VITE_` |
| `frontend/src/main.jsx`, `App.jsx` | Bootstrap and routes |
| `frontend/src/lib/api.js` | One API client: bearer token, error normalisation, 204 handling, media URL resolution |
| `frontend/src/lib/supabase.js` | Client created only when URL and anon key exist |
| `frontend/src/lib/auth.jsx` | Session context for Supabase, plus an explicitly gated development token path |
| `frontend/src/components/Layout.jsx`, `ui.jsx` | Navigation, protected route, spinner, banners, fields, confirm button |
| `frontend/src/pages/AuthPages.jsx` | Login and register |
| `frontend/src/pages/FeedPage.jsx` | Feed and search |
| `frontend/src/pages/UploadPage.jsx` | Upload |
| `frontend/src/pages/PhotoPage.jsx` | Photo detail and comments |
| `frontend/src/pages/FriendsPage.jsx` | Friend workflow |
| `frontend/src/pages/ProfilePage.jsx` | Profile editing |
| `frontend/src/styles.css` | Layout and visual system |
| `frontend/src/lib/api.test.js` | 6 API client tests |
| `frontend/src/pages/UploadPage.test.jsx` | 5 upload tests |
| `frontend/src/pages/AuthPages.test.jsx` | 2 blocked-auth tests |
| `frontend/src/pages/FeedPage.test.jsx` | 4 feed tests |
| `tests/live_check_phase4.sh` | Serves the production build and inspects the bundle |

## 3. API integration

| Screen | Endpoints used |
|---|---|
| Login, Register | Supabase Auth client, then `GET /api/v1/auth/me` |
| Feed | `GET /api/v1/photos`, `GET /api/v1/photos/{id}/url` per card |
| Search | `GET /api/v1/photos/search` |
| Upload | `POST /api/v1/photos` as multipart |
| Photo detail | `GET /api/v1/photos/{id}`, `GET /api/v1/photos/{id}/url`, `GET` and `POST /api/v1/photos/{id}/comments`, `DELETE /api/v1/comments/{id}`, `DELETE /api/v1/photos/{id}` |
| Friends | `GET` and `POST /api/v1/friends/requests`, accept, reject, `GET /api/v1/friends`, `DELETE /api/v1/friends/{id}` |
| Profile | `GET` and `PATCH /api/v1/auth/me` |

The frontend uses the versioned `/api/v1` contract. The backend also serves the brief's unprefixed
paths, so either works.

## 4. Test results

| Suite | Result |
|---|---|
| Frontend component tests | **17 passed**, 4 files, 1.90 s |
| Backend suite, unchanged | **115 passed in 10.60 s** |
| Production build | **Success**, 77 modules, 472 ms |
| Bundle inspection | No `service_role` reference, no JWT-like string |

Frontend test coverage:

- API client: bearer header, 204 handling, string detail, FastAPI validation array flattened,
  unreachable server mapped to a readable message, media URL resolution.
- Upload: rejects a GIF before sending, rejects files over 5 MB, requires a file, sends visibility and
  tags correctly, surfaces a server error instead of a success state.
- Auth screens: without Supabase, no dead password form and no fake registration.
- Feed: empty state with a route forward, renders caption, owner and tags, surfaces errors, does not
  call search without a term.

Production build output:

```
dist/index.html                   0.50 kB │ gzip:  0.31 kB
dist/assets/index-aQQCoIS1.css    4.84 kB │ gzip:  1.60 kB
dist/assets/index-3ulnUz6a.js   292.84 kB │ gzip: 92.08 kB
built in 472ms
```

Serving the built files: `/` 200, the JS asset 200, the CSS asset 200, correct document title, clean
shutdown, port released. The build is a real artefact, not a claim.

## 5. Problems encountered

1. **`React is not defined` in 11 tests.** The test transform used the classic JSX runtime. Fixed once
   with `esbuild: { jsx: "automatic" }` rather than adding an unused React import to every file.
2. **One ambiguous test assertion.** "JPEG, PNG or WebP" appeared in both a hint and an error, so the
   query matched two nodes. The assertion was made specific; the component was not changed.
3. **Preview server unreachable.** Vite bound to `localhost` (IPv6) while the check used 127.0.0.1.
   Fixed with `--host 127.0.0.1`.
4. **Port left bound after preview.** Killing the `npx` wrapper left its child listening. The check now
   kills the listener by its own pid and asserts the port is released.
5. **Bundle build warning.** Vite 8 uses `oxc` and warns that the `esbuild` option is ignored for the
   build, while the test runner still uses it. Cosmetic; the build succeeds. Resolving it means moving
   the JSX setting to the `oxc` shape, which I did not guess at.

## 6. Security and operational considerations

- **No privileged key in the bundle.** Verified by inspection: no `service_role`, no JWT-like string.
  Only `VITE_` values are compiled in, and `.env.example` states the rule.
- **The development token path is gated twice.** It appears only when Supabase is absent and
  `VITE_DEV_AUTH=1`, and the token lives in `sessionStorage`, not `localStorage`. It is a development
  affordance and is documented as one.
- **Expired sessions are handled.** A 401 from `/auth/me` clears the token and returns the user to
  sign-in; expired signed image URLs render a clear message rather than a broken image.
- **The interface never claims Supabase works.** Login, register and upload each say what is
  unavailable and why.
- **No browser automation has been run.** The tests are jsdom component tests. A real browser pass
  against the running backend is Phase 5 work, and this report does not claim it.

## 7. Outstanding items

| Item | State |
|---|---|
| Supabase registration, login, email confirmation | BLOCKED, no project |
| Real Supabase Storage upload and signed URLs | BLOCKED, local driver used |
| Supabase JS auth exercised end to end | NOT TESTED |
| Browser end to end run with three accounts | NOT TESTED, Phase 5 |
| Git remote and push | NOT DONE, no remote and no approval |
| Git local repository | DONE, first commit `11ea1e7` |

## 8. Remaining risks

1. **XSS would expose the access token**, since it lives in browser storage. React escaping and the
   absence of `dangerouslySetInnerHTML` are the current mitigations; a strict CSP is a Phase 5 item.
2. **Signed image URLs are bearer credentials** for 60 seconds.
3. **Client-side validation is a courtesy**; the server re-validates type, size and quota, and the tests
   cover that separation.
4. **No rate limiting**, so the UI can hammer the API.
5. **Offset pagination** can shift on inserts between pages.
6. **jsdom is not a browser**: layout, CORS and real navigation are unverified until Phase 5.

## 9. Next phase

Phase 5 is integration, security review and bug fixes, including a real browser pass and dependency
checks. No Phase 5 work has started. Nothing was deployed, no public service was exposed, and no paid
resource was created.

## 10. Approval request

Phase 4 is complete to the extent the environment allows, and stopped. Please approve Phase 5, or name
any screen you want changed first.
