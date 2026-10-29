# Deployment Plan

Date: 2026-10-29
Status: preparation only. Nothing has been deployed, connected or created.

## 1. Target architecture

```
Browser
  |
  | HTTPS
  v
Cloudflare Pages (static React build)  ---- HTTPS /api/v1 ---->  Render (FastAPI, Uvicorn)
  |                                                                     |
  | HTTPS signed image URLs                                             | TLS Postgres
  v                                                                     v
Supabase Storage (private bucket)  <--- metadata ---  Supabase PostgreSQL + Auth
```

Three tiers, as the brief requires: presentation on Cloudflare Pages, application on Render, data in
Supabase PostgreSQL with object storage in Supabase Storage.

Why this split: the frontend is static after `vite build`, which Pages serves from its edge network at no
cost. FastAPI needs a long-running process, which Pages cannot provide, so it goes to Render. Supabase
provides Postgres, Auth and Storage in one project, which keeps the number of moving parts down.

## 2. Environment variables

### 2.1 Backend, set in Render (never committed)

| Variable | Required | Purpose | Notes |
|---|---|---|---|
| `DATABASE_URL` | Yes | Supabase Postgres connection string | Use the pooler host and a database password. Percent-encode the password |
| `SUPABASE_URL` | Yes | Project URL, also used to derive the JWKS URL | Public value |
| `SUPABASE_ANON_KEY` | Yes | Reserved for client-side flows | Public value |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Storage signing and administrative reads | **Secret.** Server only, never in `VITE_` |
| `SUPABASE_JWT_SECRET` | One of | HS256 verification for legacy projects | Secret. Omit if the project uses asymmetric keys |
| `SUPABASE_JWKS_URL` | One of | ES256/RS256 verification | Derived from `SUPABASE_URL` if omitted |
| `CORS_ORIGINS` | Yes | Allowed browser origin | Exactly the Pages URL, no wildcard |
| `STORAGE_BACKEND` | Yes | `supabase` in production | `local` only for tests |
| `STORAGE_SIGNING_SECRET` | Local only | HMAC for the local driver | Not needed with the Supabase driver |
| `SIGNED_URL_TTL_SECONDS` | No | Defaults to 60 | Keep at 60 |

### 2.2 Frontend, set at build time in Cloudflare Pages

| Variable | Required | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | Yes | Render service URL, for example `https://teb3033-api.onrender.com` |
| `VITE_SUPABASE_URL` | Yes | Project URL, also injected into the CSP `connect-src` and `img-src` |
| `VITE_SUPABASE_ANON_KEY` | Yes | Public anon key, used by Supabase Auth |
| `VITE_DEV_AUTH` | **Must be unset** | The development token field must not exist in production |

The build fails closed in one important sense: if `VITE_API_BASE_URL` is missing, the generated CSP keeps
`connect-src 'self'` and a separately hosted API is blocked by the browser. That is a deliberate
requirement, not a bug, and it is why the variables must be set before the first production build.

## 3. Content Security Policy at deploy time

The policy is generated during `vite build` from `VITE_API_BASE_URL` and `VITE_SUPABASE_URL`, and the
static header in `frontend/public/_headers` ships with the build.

| Directive | Production value |
|---|---|
| `default-src` | `'self'` |
| `script-src` | `'self'` |
| `style-src` | `'self' 'unsafe-inline'` (React style attributes) |
| `img-src` | `'self' data: blob: <Render origin> <Supabase origin>` |
| `connect-src` | `'self' <Render origin> <Supabase origin>` |
| `object-src` | `'none'` |
| `base-uri`, `form-action` | `'self'` |
| `frame-ancestors` | `'none'`, header only |
| `upgrade-insecure-requests` | present |

Requirement: rebuild after changing either origin. A stale build carries the old origins and will block
the API.

Note on `_headers`: Cloudflare Pages applies it only to the Pages project itself. It does not apply to the
Render API. Render responses are governed by the application's own headers and by CORS below.

## 4. CORS and HTTPS

| Item | Setting |
|---|---|
| Allowed origin | Exactly `https://<project>.pages.dev`, plus a custom domain if one is added |
| Methods | `GET, POST, PATCH, PUT, DELETE, OPTIONS` (already configured) |
| Allowed headers | `Authorization, Content-Type` |
| Credentials | `allow_credentials=True`, though the API uses bearer tokens rather than cookies |
| Wildcard | Never. `*` would defeat the token model |
| HTTPS | Required on both hosts. Cloudflare Pages is HTTPS by default; Render terminates TLS and provides `onrender.com` over HTTPS. Supabase requires TLS |

Additional requirement: Supabase Auth needs the deployed frontend URL in its Site URL and Redirect URLs,
otherwise confirmation links point at localhost. This is an owner action in the Supabase dashboard.

## 5. Deployment order

1. Owner creates the Supabase project, then applies `001_init.sql`, `002_storage.sql` and
   `003_view_helper.sql` in order, and confirms the `photos` bucket is private with a 5 MB limit.
2. Owner provides `DATABASE_URL`, project URL, anon key and service role key through Render's environment
   configuration, not through chat.
3. Owner creates the Render web service from the repository: build `pip install -r backend/requirements.txt`,
   start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, root directory `backend`.
4. Verify `GET /health` and `GET /ready` on the Render URL.
5. Owner creates the Cloudflare Pages project from the same repository: root `frontend`, build
   `npm ci && npm run build`, output `dist`, with the four `VITE_` variables set.
6. Set `CORS_ORIGINS` in Render to the exact Pages URL, then redeploy the backend.
7. Add the Pages URL to Supabase Auth Site URL and Redirect URLs.
8. Run the acceptance pass in section 7.

## 6. Known deployment limitations

### 6.1 Rate limiting is per process

The limiter holds counters in process memory. Render runs one instance on the free tier, so the limits are
exact. If the service is scaled to two or more instances, each enforces its own ceiling and the effective
limit multiplies. The correct fix is a shared counter in Redis, which is a paid or separately provisioned
component. For this project the single instance is adequate and the limitation is documented rather than
hidden.

### 6.2 Render free tier cold starts

Free web services are suspended when idle and take tens of seconds to resume on the next request. This
affects a live demonstration and the first page load after a quiet period. Mitigation: request `/health`
about a minute before the demonstration, and keep the demo short enough that the service stays warm.
Confirm the current idle policy in Render's dashboard at deployment time rather than trusting this note.

### 6.3 Supabase free tier pauses

Free projects are paused after one week of inactivity. A project left idle before grading will not respond
until it is restored from the dashboard. Mitigation: open the project the day before the demonstration and
confirm it is active.

### 6.4 Storage limits

The free tier includes 1 GB of file storage. At 5 MB per photo that is roughly 200 photos, so the 5 MB cap
and the 20-per-day quota are not just validation, they are the cost control.

### 6.5 No custom domain

The `pages.dev` and `onrender.com` hostnames are free. A custom domain requires a purchase, which is out of
scope for the RM0 target.

## 7. Post-deployment acceptance pass

Every item must be verified against the live URL before the deployment is called complete.

1. `GET https://<api>/health` returns 200 and the expected body.
2. `GET https://<api>/ready` returns 200 with `database: ok`.
3. Register a new account on the Pages URL, confirm the email, sign in.
4. Upload a photo, confirm the object exists in the private bucket, and confirm the feed renders it.
5. Second account, not a friend: feed empty, direct photo URL refused.
6. Send and accept a friend request, then confirm the photo appears for the friend.
7. Upload an owner-only photo and confirm the friend cannot open it.
8. Comment, then delete the comment as its author, then as the photo owner.
9. Search by caption and tag.
10. Confirm `curl -I` on the Pages URL shows the CSP header, and that the console shows no violations.
11. Confirm no secret appears in the browser bundle or in network responses.
12. Confirm the backend logs contain no tokens or keys.

## 8. Rollback

| Failure | Action |
|---|---|
| Bad frontend build | Cloudflare Pages keeps previous deployments; roll back in the dashboard |
| Bad backend deploy | Render keeps the previous deploy; roll back in the dashboard |
| Broken migration | Restore from the Supabase backup if on Pro, or re-apply from a clean project on free |
| Leaked secret | Rotate the key in Supabase or Render first, then redeploy; revoke the old value |

## 9. What still requires owner action or approval

| Step | Requires |
|---|---|
| Create Supabase project | Owner account, owner approval |
| Create Render service | Owner account, owner approval, payment method may be requested even on free |
| Create Cloudflare Pages project | Owner account, owner approval |
| Provide secrets to hosting dashboards | Owner, entered directly into the provider |
| Configure Supabase Auth URLs | Owner |
| Push to GitHub | Owner authorisation, and a remote that does not exist yet |
| Any paid resource | Explicit approval, currently none planned |

Nothing in this plan has been executed.
