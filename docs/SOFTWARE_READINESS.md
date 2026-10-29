# Software Readiness Report

Project: TEB3033 Photo Sharing
Date: 2026-10-29
Scope: local development environment only. Cloud service configuration is listed separately, because
installing a client library is not evidence that an account is configured.

Status vocabulary: PASS, FAIL, PARTIAL, BLOCKED, NOT TESTED.

## 1. Core development tools

| Software | Required version | Existing status | Action taken | Installation location | Verification | Status |
|---|---|---|---|---|---|---|
| Git | Any current release | Installed, 2.39.5 | Reused | System | `git --version` | PASS |
| Python 3 | 3.10 or later for this stack | Installed, 3.11.2 at `/usr/bin/python3` | Reused | System | `--version`, venv built from it | PASS |
| venv | Bundled with Python 3 | Available | Reused | System | Created `backend/.venv` successfully | PASS |
| pip | Bundled, project-local | 23.0.1 on system, upgraded inside the venv | Upgraded in venv only | `backend/.venv` | `pip --version`, packed install succeeded | PASS |
| Node.js | LTS | Installed, v24.20.0 | Reused | System | `--version`, Vite build succeeded | PASS |
| npm | Bundled with Node | Installed, 11.19.0 | Reused | System | `--version`, install and build succeeded | PASS |
| Code editor, VS Code Remote SSH | Not applicable on a server | Absent on this host | Deferred to the owner's Windows machine | Owner side | Not executed | NOT TESTED |

## 2. Python backend

All installed into `/workspace/projects/TEB3033-Photo-Sharing/backend/.venv`, from PyPI, in an isolated
environment with no access to the Hermes runtime packages.

| Software | Version | Action taken | Verification | Status |
|---|---|---|---|---|
| FastAPI | 0.162.0 | Installed | Imported; served a live request | PASS |
| Uvicorn | 0.54.0 | Installed with standard extras | Started a server, `GET /health` returned 200 | PASS |
| Starlette | 1.10.0 | Installed as a FastAPI dependency | Runtime of the smoke server | PASS |
| Pydantic | 2.14.1 | Installed | Imported and used in the response model path | PASS |
| python-dotenv | 1.2.4 | Installed | Imported | PASS |
| python-multipart | 0.0.32 | Installed, required for form and file uploads | Imported | PASS |
| supabase (Python client) | 2.33.0 | Installed | Imported; dependency chain resolved | PASS |
| pytest | 9.2.0 | Installed | Collected and ran 2 tests, both passed | PASS |
| HTTPX | 0.28.1 | Installed | Used by the test client in the passing tests | PASS |
| Locust | 2.47.0 | Installed | Imported; command available in the venv | PASS |

Recorded in `backend/requirements.txt` and `backend/requirements-dev.txt` with pinned versions.

## 3. Frontend

Verified with a throwaway React and Vite application in `/tmp/vite-smoke`, which was created for
verification only. No frontend application files were added to the project, because Phase 0 forbids
implementation.

| Software | Version | Action taken | Verification | Status |
|---|---|---|---|---|
| React | 19.3.1 | Scaffolded in the throwaway app | Rendered through a production build | PASS |
| Vite | 8.3.5 | Scaffolded | `npm run build` produced `dist` in 235 ms | PASS |
| @vitejs/plugin-react | 6.1.2 | Scaffolded | Part of the successful build | PASS |
| @supabase/supabase-js | 2.118.0 | Installed in the throwaway app | Imported, `createClient` built a client with `auth` present, build still succeeded | PASS |
| Linter (oxlint) | Bundled with the template | Executed | `npm run lint` emitted no findings | PASS |

Build artefact: `dist/index.html` plus 5 asset files, 296 KB total. This proves the toolchain can
compile and bundle, which is the acceptance criterion, not that an application exists.

## 4. Testing, quality and utilities

| Software | Version | Action taken | Verification | Status |
|---|---|---|---|---|
| pytest | 9.2.0 | Installed in the venv | 2 tests passed in 0.30 s | PASS |
| HTTPX | 0.28.1 | Installed | Exercised by the test client | PASS |
| Locust | 2.47.0 | Installed | Imported successfully | PASS |
| curl | 7.88.1 | Reused | Used for every HTTP check in Phase 0 | PASS |
| Docker | 20.10.24 | Present, not used | `docker info` reports a live daemon | PASS |
| Docker Compose | 5.5.1 | Present, not used | `docker compose version` | PASS |
| psql, pg_dump | PostgreSQL 15.19 | Present | `--version` | PASS |
| sqlite3 | Not installed | Not installed | Not required: Supabase provides PostgreSQL | NOT TESTED |

## 5. Backend acceptance test, actual output

Task: start the FastAPI backend and confirm it serves health.

- Expected: the server starts without errors, `GET /health` returns HTTP 200, and the body contains
  the expected healthy status.
- Observed: HTTP 200, body `{"status":"ok","service":"smoke","version":"1.0.0"}`, `/docs` returned 200.
- Test suite: `2 passed, 1 warning in 0.30s`, pytest exit code 0.
- Shutdown: process stopped by PID, port released.
- Status: PASS.

The smoke server was a four line fixture in `/tmp`, not application code.

## 6. Cloud services and deployment tooling

Client libraries are installed. Accounts, credentials and deployment configuration are not, and no
claim is made that they are.

| Item | State | Why | Status |
|---|---|---|---|
| Supabase project, URL, keys | Not configured | Requires the owner's account and the data model | BLOCKED |
| Supabase CLI | Not installed | Local stack needs a decision on Docker based local development | NOT TESTED |
| Cloudflare Pages project and API token | Not configured | Requires the owner's account, and a decision between Git integration and direct upload | BLOCKED |
| wrangler CLI | Not installed | Only useful once the Cloudflare account exists | NOT TESTED |
| Render service and deploy hook | Not configured | Requires the owner's account | BLOCKED |
| Render CLI | Not installed | Only useful once the Render account exists | NOT TESTED |
| GitHub repository and access | Not configured | Needed only if the assessment requires a repository | NOT TESTED |

No paid operation was performed. No public endpoint was exposed.

## 7. Known warnings to resolve in Phase 1

1. **Starlette test client deprecation.** The passing tests emit
   `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2`.
   Current combination is FastAPI 0.162.0, Starlette 1.10.0, HTTPX 0.28.1. It works today. The options
   are to add `httpx2` for test client support or to pin a combination that does not warn. Decide when
   the test layout is defined.
2. **Locust import warning.** Importing Locust after SSL produces a gevent monkey-patch warning. It does
   not affect the Locust command line. Keep Locust out of the FastAPI process and run it as its own
   command.
3. **Node version.** v24.20.0 is installed and builds successfully. If the brief or the deployment
   target requires a specific Node line, pin it with a version manager before Phase 1.

## 8. Manual actions required from the owner

1. **Supply the application specification.** Everything after Phase 0 depends on it.
2. **Supabase:** create the project and provide the project URL, the anon key, and the service role key.
   Keys go into a local `.env` file that is never committed or pasted into chat.
3. **Cloudflare:** create the account and a Pages project, and decide between Git integration and direct
   upload. A scoped API token is needed only for direct upload.
4. **Render:** create the account and the service, or provide a deploy hook.
5. **GitHub:** create the repository if the assessment requires one, and confirm access.
6. **Confirm the assessment constraints:** deadline, report requirements, marking rubric, whether
   deployed URLs are graded, and the demonstration date.
7. **Optional:** VS Code Remote SSH from the Windows machine, if that is the preferred editing route.

## 9. Exit criteria

| Criterion | Status |
|---|---|
| All required local development tools installed and verified | PASS |
| Dependency versions recorded in dependency files | PASS |
| Remaining blockers documented | PASS |
| Application implementation not started | PASS |
| Owner approval obtained before Phase 1 | PENDING |
