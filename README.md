# TEB3033 Photo Sharing

**TEB3033 Distributed Photo-Sharing and Commenting System.** A functional, secure, multi-tier web
application where a group of friends registers, connects, uploads photos, shares them with friends they
have accepted, and comments on shared photos.

Stack: React + Vite frontend, Python + FastAPI backend, Supabase PostgreSQL for data, Supabase Auth for
identity, a private Supabase Storage bucket for images, Cloudflare Pages for the frontend and Render for
the backend.

**Current phase: Phase 0 accepted. The application specification is recorded. Phase 1 has not started
and no application code exists.** Implementation begins only after the owner approves Phase 1.

## Status

| Area | State | Evidence |
|---|---|---|
| Project structure | Created | `docs/PHASE_0_ENVIRONMENT_REPORT.md` |
| Master prompt | COMPLETE, decisions resolved 2026-10-29 | `MASTER_PROMPT.md` Sections E and F |
| Software readiness | Verified, 24 PASS | `docs/SOFTWARE_READINESS.md` |
| Phase 1: scaffolding | PARTIAL: backend and database done, React app and Git pending | `MASTER_PROMPT.md` Section G |
| Phase 2: database, auth, security | PARTIAL: PASS locally with 90 tests, live Supabase BLOCKED | `docs/PHASE_2_REPORT.md` |
| Phase 3: FastAPI backend | PASS: 115 tests, brief endpoint list verified | `docs/PHASE_3_REPORT.md` |
| Phase 4: React frontend | PARTIAL: 8 screens, 17 frontend tests, production build verified; live Supabase BLOCKED | `docs/PHASE_4_REPORT.md` |
| Phase 5: integration and security review | PASS: 16 browser checks, 134 backend tests, CSP and rate limiting implemented | `docs/PHASE_5_REPORT.md` |
| Git | Local repository, 4 commits, HEAD `f9d58a8`, clean tree, no remote | `docs/REPOSITORY_READINESS.md` |
| Phase 6: deployment preparation | Complete: repository audit, deployment plan, cost estimate | `docs/DEPLOYMENT_PLAN.md` |
| Supabase, Cloudflare, Render accounts | Not configured, owner action | readiness report section 8 |
| Storage policies | Written, NOT TESTED until a real project exists | `database/README.md` |

## Scope (approved)

In scope:

- Registration, login, logout and profile management.
- Friend requests with acceptance and rejection, and friend lists.
- Photo upload with captions and timestamps, into private storage.
- A feed containing only photos the current user may access.
- Secure image delivery for authorised viewers.
- Comments with correct author attribution, including deletion.
- Photo deletion by the owner.
- Search and filtering by uploader, date, caption and tags, with pagination.
- Clear error handling and loading states.

Explicitly load bearing: every protected operation is checked server side, Database and Storage
policies enforce access, and client-side checks never stand alone as security.

Data model: `profiles`, `friendships`, `photos`, `comments`, `photo_tags`, using UUIDs, foreign keys,
constraints, timestamps, indexes, and reproducible SQL migrations.

Deliverables beyond the running application: a verified public deployment URL, a source ZIP with no
build artefacts or secrets, a report of at most eight pages in Arial 11 with IEEE references, an
architecture diagram and a database diagram, deployment and cost documentation, multi-user test
methodology and results, and a presentation video of at most two minutes with a live demonstration.

## Layout

```
TEB3033-Photo-Sharing/
├── MASTER_PROMPT.md   execution rules and application specification (authoritative)
├── README.md          this file
├── frontend/          React + Vite application
├── backend/           Python + FastAPI application (.venv already prepared)
├── database/          SQL schema and migrations
├── docs/              architecture, deployment, testing, cost, phase reports
├── tests/             automated and integration tests
└── evidence/          verified results, screenshots, sanitised logs
```

## Setup (local development)

Written for this machine: Debian 12 LXC container on Proxmox. The system Python is PEP 668 managed, so
the backend uses its own virtual environment and never the system interpreter.

```bash
# backend
cd backend
python3 -m venv .venv          # already created in Phase 0
. .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# frontend
cd frontend
npm install
npm run dev
```

Secrets live in `.env` files that are never committed. No key, token or service role secret is stored
in this repository, and none is to be pasted into chat.

## Ground rules in force

- Every task has a defined expected result, an actual result, and a PASS, FAIL, PARTIAL, BLOCKED or
  NOT TESTED status backed by evidence.
- Work stops at each phase boundary for approval.
- No fabricated results, screenshots, URLs or costs.
- No changes to host networking, firewall, or unrelated services.
- Credentials never appear in logs, code, screenshots, or reports.

## Progress log

- **2026-10-29** Phase 0. Structure created at `/workspace/projects/TEB3033-Photo-Sharing`. Environment
  inspected, local toolchain verified with a live FastAPI health check and a real Vite production build,
  readiness report produced. Phase 0 accepted by the owner.
- **2026-10-29** Specification recorded. `MASTER_PROMPT.md` moved from PARTIAL to COMPLETE with the
  application specification as Section E, and Phase 1 entry conditions as Section F. No application
  code written. Phase 1 deliberately not started.
- **2026-10-29** Phase 1 complete and stopped for approval. Schema with 5 tables, 19 RLS policies and 5
  triggers; Supabase token verification for HS256 and JWKS; profile endpoints; a 50 test suite running
  against real PostgreSQL with RLS exercised as the `authenticated` role. Live Uvicorn checks passed.
  Starlette warning resolved by measurement. Storage policies written but NOT TESTED until a real
  Supabase project exists. Report: `docs/PHASE_1_REPORT.md`.
- **2026-10-29** Renumbered to the brief's phase definitions. The schema, authentication and security
  work described above is **Phase 2**; the backend API built before the brief arrived is **Phase 3** and
  is kept but not claimed as approved. Automated tests now 90, all passing. Phase 2 report:
  `docs/PHASE_2_REPORT.md`.

- **2026-10-29** Phase 4 complete and stopped for approval. React and Vite frontend in `frontend/`:
  login, register, feed, search, upload, photo detail with comments, friends and profile. 17 component
  tests, production build served and inspected, 115 backend tests still passing. Real Supabase
  authentication and Storage remain BLOCKED and the interface states that. Report:
  `docs/PHASE_4_REPORT.md`.

- **2026-10-29** Phase 5 complete and stopped for approval. Real browser end-to-end run with three
  accounts: 16 of 16 checks, covering upload, comments, friend requests, visibility, search, profile and
  an XSS attempt. Fixed a real defect: the first request after sign-in went out without a bearer token
  because the provider was installed in an effect. Security suite extended to 11 tests; 126 backend tests
  pass. Vitest upgraded to 5.0.5, clearing three dev advisories. CSP and rate limiting recorded as open
  risks. Report: `docs/PHASE_5_REPORT.md`.

- **2026-10-29** Security gaps closed locally. Content Security Policy generated at build time from the
  configured API and Supabase origins, plus Cloudflare Pages headers; 13 CSP checks pass including a
  live browser load with zero violations. Server-side sliding-window rate limiting on uploads,
  comments, friend requests, signed URLs and deletions, with 429 and Retry-After; concurrency test
  confirms exactly 10 of 30 racing requests are allowed. Backend 134 tests, frontend 17, browser E2E 16
  of 16, zero dependency advisories.

- **2026-10-29** Phase 6 preparation complete, stopped for approval. Repository audited: 89 tracked files,
  clean tree, no remote, no `.env`, no `node_modules`, no build output, gitleaks clean across all commits.
  Deployment architecture, environment variables, CSP origins, CORS and HTTPS requirements documented,
  including the multi-worker rate-limit limitation. Hosting limits verified against official pricing pages
  and three cost scenarios recorded. Nothing pushed, connected or deployed.
