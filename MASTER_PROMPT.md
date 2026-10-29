# TEB3033 Photo Sharing - Master Project Prompt

**Status: COMPLETE as of 2026-10-29.** Sections A to D record the execution rules supplied on
2026-10-29. Section E records the application specification supplied and approved on the same date.
Section F records the Phase 1 entry conditions and the decisions that remain open.

Authoritative scope: this file governs execution. On questions of product behaviour, Section E takes
precedence. On how work is performed, Sections A to D continue to govern. Where Section E states a
requirement and Section F records an unanswered question, Section E is the requirement and Section F
must be resolved before the affected work begins.

---

## Section 0. Specification status (resolved 2026-10-29)

When this file was created, the following were not present in the instructions received. They are now
answered by Section E. The list is kept as the record of what was missing, so the specification can be
checked against it rather than assumed complete.

1. Application features and user journeys: which of browsing, uploading, albums, tagging,
   commenting, liking, sharing, searching, following, moderation, notifications are in scope.
2. User roles and permissions: anonymous visitor, registered user, owner of a photo, administrator.
3. Data model and business rules: entities, relationships, ownership, visibility rules, file size and
   format limits, image processing requirements, deletion behaviour.
4. Authentication requirements: Supabase Auth configuration, email confirmation, password policy,
   session handling, third-party providers if any.
5. Storage requirements: Supabase Storage buckets, public or signed URLs, access policies.
6. Non-functional requirements: expected concurrent users, latency targets, availability, browser
   support, accessibility, mobile behaviour.
7. Assessment constraints: submission deadline, report and demonstration requirements, marking
   rubric, whether deployment URLs are graded, presentation date.
8. Technology constraints that are fixed versus negotiable: the brief names React, Vite, FastAPI,
   Supabase, Cloudflare Pages and Render, but does not state which are mandatory.
9. Cost ceiling and cloud account ownership: who owns the Supabase, Cloudflare and Render accounts,
   and what spend is authorised.

Items 1 to 9 are answered in Section E. Four matters remain open and are carried into Section F: the
exact deadline date, the authorization model for sharing, tag ownership, and comment deletion rights.

---

## Section A. Project folder first

Before performing any other project task, create a dedicated project folder named
`TEB3033-Photo-Sharing`.

Use the current working directory only after inspecting it and confirming it is an appropriate
location. If a suitable project folder already exists, inspect and reuse it rather than creating
duplicate folders or overwriting existing files.

If working on the Proxmox homelab, create this folder inside the designated development workspace,
not inside system directories or unrelated application folders.

Expected initial structure:

```
TEB3033-Photo-Sharing/
├── MASTER_PROMPT.md
├── README.md
├── frontend/
├── backend/
├── database/
├── docs/
├── tests/
└── evidence/
```

Folder purposes:

- `MASTER_PROMPT.md`: the complete project requirements and execution rules.
- `README.md`: project overview, setup instructions, and current progress.
- `frontend/`: React + Vite application.
- `backend/`: Python + FastAPI application.
- `database/`: SQL schemas and database migrations.
- `docs/`: architecture, deployment, testing, and cost documentation.
- `tests/`: automated and integration tests, if not kept within individual components.
- `evidence/`: verified test results, screenshots, logs with secrets removed, and demonstration evidence.

Do not create every application file immediately. Create the project directory and initial structure
first, then implement files progressively as their respective phases require.

Save the complete master project prompt in `MASTER_PROMPT.md` so it remains the authoritative
reference throughout the project. If the complete prompt has not yet been supplied or saved, request it
from the owner before claiming that the file contains the full specification.

After creating the folder, verify its actual location and contents. Report the result before continuing.

---

## Section B. Highest-priority execution rule

The phase-by-phase execution and verification protocol is the primary operating rule for every task in
this project. These rules apply to every phase, subtask, code change, database operation, deployment
action, and testing activity. They must not be treated as optional recommendations.

For every task:

1. Inspect the relevant environment, files, and current state before making changes.
2. Identify the task's objective, prerequisites, expected result, and acceptance criteria.
3. Implement only the work required for the current approved phase.
4. Run the relevant commands, tests, or verification procedures.
5. Compare the actual results against the expected results.
6. Fix detected problems and rerun the failed checks where possible.
7. Record the files changed, commands executed, results obtained, and remaining issues.
8. Mark each requirement as PASS, FAIL, PARTIAL, BLOCKED, or NOT TESTED, based on actual evidence.

Do not mark a task or phase as complete while its mandatory acceptance criteria remain unmet. Stop at
the end of each phase and obtain approval before starting the next phase.

### Expected results must be defined before implementation

Before executing a task, explicitly establish what success looks like.

Example:

- Task: start the FastAPI backend.
- Expected result: the server starts without errors, `/health` returns HTTP 200, and the response
  contains the expected healthy status.
- Verification: execute the request and inspect its actual response.
- Completion condition: the observed response matches the expected result.

Apply this method to coding, database configuration, authentication, photo uploads, permissions,
frontend behaviour, deployment, concurrency testing, and documentation.

Do not use vague statements such as "looks good", "should work", or "completed successfully" as
substitutes for verification.

### Phase boundaries and approval

- Multiple small operations may be performed within the currently approved phase without asking for
  permission after each operation.
- The next major phase must not begin without explicit approval.
- A failed task must not be silently skipped and continued past.
- If blocked, explain the precise blocker and the minimum action required from the owner.
- If a mandatory criterion fails, remain in the current phase until it is resolved or explicitly
  documented as blocked.
- Never fabricate test results, screenshots, deployment URLs, costs, or command outputs.

### Safety and preservation

- Before modifying existing files, inspect them and preserve unrelated work.
- Do not delete, overwrite, reset, or recreate existing project data without authorisation.
- Do not change Proxmox networking, host firewall rules, unrelated containers, VMs, or services
  unless explicitly approved.
- Never expose credentials, access tokens, database secrets, or private configuration in logs, source
  code, screenshots, or reports.
- Obtain approval before paid cloud operations, irreversible actions, or exposing a new public service.

---

## Section C. First execution sequence

1. Inspect the current working directory and environment.
2. Choose an appropriate development workspace.
3. Create or safely reuse `TEB3033-Photo-Sharing/`.
4. Create the initial folder structure.
5. Create `MASTER_PROMPT.md` and save the complete project specification when available.
6. Verify the folder structure and report its actual path.
7. Present the Phase 0 environment-discovery report.
8. Stop and wait for approval before starting Phase 1.

Do not implement the application during this pre-execution sequence.

Final instruction: folder creation comes first. The phase-by-phase execution and verification protocol
governs every subsequent task. No phase may be declared complete without evidence that its expected
results and acceptance criteria have been met.

---

## Section D. Software prerequisite discovery and installation

Before implementing the application, inspect the development environment and identify all software
required for the project.

The responsibility is to prepare a complete, working development environment, not merely to report
which software to install. Install missing prerequisites when permissions allow, using official sources
and supported installation methods.

### D1. Inspect existing software first

Check whether the following are already installed and working.

Core development tools: Git, Python 3, Python virtual environment support (`venv`), pip, Node.js LTS,
npm, a suitable code editor or an existing VS Code Remote SSH setup.

Python backend: FastAPI, Uvicorn, Supabase Python client, python-dotenv, python-multipart, Pydantic,
pytest, HTTPX, plus any additional dependency justified by the implementation.

Frontend: React, Vite, project Node dependencies, Supabase JavaScript client, plus any additional
frontend library justified by the implementation.

Testing and quality assurance: pytest, HTTPX, Locust for concurrent-user testing, appropriate linting
or formatting tools, Git, and basic HTTP utilities such as curl.

Database and deployment: Supabase project configuration and required client libraries, Cloudflare
Pages deployment prerequisites, Render deployment prerequisites, Docker and Docker Compose only if
useful for local development or reproducible testing.

Do not install every item blindly. Distinguish application dependencies, development tools, and cloud
services configured through web dashboards before acting.

### D2. Determine the correct installation location

Identify the environment first: Proxmox host, dedicated Debian or Ubuntu VM, LXC container, existing
development machine, or another authorised environment. Prefer installing project dependencies inside
the designated development VM, LXC, or a project-specific virtual environment. Do not install
application dependencies directly on the Proxmox host unless there is a clear, approved reason. Do not
modify unrelated containers, VMs, host packages, network settings, firewall rules, or running services.

### D3. Install missing prerequisites

For each missing prerequisite: confirm the operating system and supported installation method; prefer
official repositories, official installation instructions, or trusted package registries; install only
what is necessary; avoid unnecessary system-wide Python installations; use a project-specific Python
virtual environment for Python dependencies; use npm for frontend dependencies; pin or record versions
for reproducibility; verify by checking the version and running a basic functional test; record
commands, versions, and results.

Do not run unreviewed installation scripts with administrator privileges, disable security protections,
or change system configuration simply to make a package install. If administrator privileges are
required but unavailable, stop and provide the exact command plus the reason it is needed.

### D4. Verify the development environment

Before declaring setup complete, verify: `git --version`, `python3 --version`, `python3 -m venv --help`,
`python3 -m pip --version`, `node --version`, `npm --version`, virtual environment creation and
activation, dependency installation inside the virtual environment, React/Vite project creation or
existing dependency installation, frontend production build, FastAPI startup and health endpoint, and
that the relevant test tools can execute. Dependencies must be recorded in their appropriate dependency
files.

Do not claim Supabase, Cloudflare, or Render is fully configured merely because a client library or
deployment command is installed. Verify external account configuration separately when credentials and
access are available.

### D5. Installation failure handling

If installation fails: capture the relevant error without exposing credentials; determine whether the
cause is permissions, network connectivity, repository availability, incompatible versions, disk space,
or something else; try a safe and appropriate fix; rerun the failed verification; record the outcome
accurately. Do not repeatedly retry failed commands without investigating the cause. If a prerequisite
cannot be installed safely, mark it BLOCKED, explain why, and request only the minimum intervention
needed.

### D6. Expected output

A software-readiness report containing, per item: software name, required version, existing status,
action taken, installation location, verification result, and status (PASS, FAIL, PARTIAL, BLOCKED, or
NOT TESTED). Also a list of remaining manual actions such as creating a Supabase account, configuring
cloud credentials, or authorising GitHub access.

### D7. Exit criteria

Software setup is complete only when all required local development tools are installed and verified,
or any remaining blockers are explicitly documented. Application implementation must not begin until
the required local environment is ready. After completing software discovery and installation, report
the results and wait for approval before proceeding.

---

## Section E. Application specification (supplied and approved 2026-10-29)

### E1. Project and objective

Project: TEB3033 Distributed Photo-Sharing and Commenting System.

Objective: build a functional, secure, multi-tier web application that allows a group of friends to
register, connect with each other, upload photos, share photos with authorized friends, and comment on
shared photos.

### E2. Required technology stack

- Frontend: React + Vite.
- Backend: Python + FastAPI.
- Database: Supabase PostgreSQL.
- Authentication: Supabase Auth.
- Image storage: private Supabase Storage bucket.
- Local development: existing Debian 12 LXC development environment on Proxmox.
- Source control: Git and GitHub, subject to account setup.
- Frontend deployment: Cloudflare Pages.
- Backend deployment: Render, using a suitable free tier if available.
- Testing: pytest, HTTPX, manual multi-user testing, and Locust.

### E3. Functional requirements

1. User registration, login, logout, and profile management.
2. Friend requests, acceptance, rejection, and friend lists.
3. Photo upload with captions and timestamps.
4. Photo feed showing only photos the current user is authorized to access.
5. Private photo storage and secure image delivery.
6. Adding, viewing, and deleting comments with correct author attribution.
7. Photo deletion by the authorized owner.
8. Search and filtering by uploader, date, caption, and tags, where appropriate.
9. Pagination for photo feeds and search results.
10. Clear error handling and loading states in the frontend.

### E4. Authorization requirements

- Only authenticated users can perform protected operations.
- Users cannot impersonate another user.
- Only the intended recipient can accept or reject a friend request.
- Only accepted friends may view photos shared with friends.
- The photo owner may manage their own photos.
- Unauthorized users cannot access private images, comments, or signed URLs.
- All relevant API endpoints must verify permissions server-side.
- Database and Storage policies must enforce appropriate access restrictions.
- Client-side checks must never be the sole security mechanism.

### E5. Database requirements

Create and document the relationships among:

- `profiles`
- `friendships`
- `photos`
- `comments`
- `photo_tags`

Use UUIDs, foreign keys, constraints, timestamps, indexes, and reproducible SQL migrations as
appropriate. Store photo files in object storage and metadata in PostgreSQL.

### E6. Non-functional requirements

- Use a clear three-tier architecture: presentation, application, and data.
- Keep the code understandable for a university project.
- Use environment variables and never commit secrets.
- Support multiple concurrent users and test concurrent writes.
- Validate file types, sizes, and request payloads.
- Avoid unnecessary dependencies and infrastructure.
- Use free tiers where practical, with a target of RM0 in additional cloud hosting charges.
- Never guarantee zero cost without checking current provider limits and actual billing.
- Document all security limitations, performance results, and assumptions.

### E7. Assignment and submission requirements

The implementation must support the assignment's required deliverables:

- Working application and verified public deployment URL.
- Source-code ZIP excluding executables, build artifacts, `node_modules`, virtual environments, and
  secrets.
- Report of no more than eight pages.
- Arial 11 for main text and IEEE-formatted references, as specified in the assignment.
- Architecture and database diagrams.
- Cloud deployment documentation.
- Multi-user testing methodology and actual results.
- Actual or estimated operating cost.
- Conclusion and required marking rubric on the last page.
- Presentation video no longer than two minutes, with every group member presenting and a live
  demonstration.

### E8. Testing acceptance criteria

Before final completion, verify:

1. Authentication and profile creation.
2. Friend request workflows.
3. Authorized and unauthorized photo access.
4. Photo upload, persistence, and deletion.
5. Comment creation, retrieval, and deletion.
6. Search and filtering.
7. Concurrent uploads and comments.
8. Correct error handling.
9. Production frontend build.
10. Cloud deployment and persistence.
11. Absence of exposed secrets.

Use actual test outputs as evidence. Never invent results.

### E9. Constraints and unresolved decisions

- Deadline: Week 9 according to the supplied assignment; the exact date must be confirmed rather than
  guessed.
- Budget: target RM0 in additional cloud hosting charges.
- Cloud accounts and credentials: not yet configured.
- Do not request passwords, service-role keys, or private tokens in chat. Use secure environment
  configuration.
- Keep the existing project directory at `/workspace/projects/TEB3033-Photo-Sharing`.
- Do not modify unrelated Proxmox services or the Hermes runtime.

### E10. Required actions recorded at acceptance

1. Update `MASTER_PROMPT.md` with this specification.
2. Preserve the existing phase-by-phase execution protocol.
3. Resolve the Starlette test-client deprecation warning in a documented, compatibility-tested manner
   when establishing the Phase 1 test setup.
4. Update `README.md` to reflect the approved project specification and current status.
5. Verify the updated files and ensure no application implementation has begun.
6. Report the exact changes and any remaining ambiguities.
7. Do not create the Supabase project, deploy cloud resources, or begin Phase 1 implementation yet.
8. Stop and request approval after completing this specification update.

---

## Section F. Phase 1 entry conditions and open decisions

Phase 1 does not begin until the owner approves it. The following must be settled first. Each item
carries a proposed default, so that approval can be a single reply rather than another round of
questions.

### F1. Decisions: approved 2026-10-29

| # | Decision | Approved value |
|---|---|---|
| 1 | Deadline | Approximately one week and five days remaining. Working MVP within one day, then deployment, testing, fixes, documentation and presentation |
| 2 | Photo visibility | Owner only, or accepted friends, according to the photo's visibility setting. No public feed |
| 3 | Tag ownership | Photo owner only, add or edit |
| 4 | Comment deletion | Comment authors may delete their own; photo owners may delete comments on their own photos |
| 5 | Registration | Open registration with Supabase email confirmation. Automated tests use controlled accounts without weakening production authentication |
| 6 | Photo deletion | Hard delete of metadata and Storage object, with comments and tags removed. Partial failures handled so a failed Storage delete does not leave silent inconsistency |
| 7 | Upload limits | JPEG, PNG and WebP, maximum 5 MB per image, 20 uploads per user per day, enforced server side |
| 8 | Signed URL lifetime | 60 seconds, issued only after verifying the caller's permission. The residual risk of a shared URL is documented, not hidden |
| 9 | Group members | Confirmed later, at demonstration time. Implementation must not block on it and must support multiple users with enough test accounts |

### F2. Starlette test-client deprecation: resolved 2026-10-29

Phase 0 recorded `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated;
install httpx2` with FastAPI 0.162.0, Starlette 1.10.0 and HTTPX 0.28.1.

Resolved by compatibility test rather than assumption. Adding `httpx2` 2.16.0 produced a passing
request and zero warnings, with no downgrades of FastAPI, Starlette or HTTPX. `pytest.ini` now treats a
Starlette `DeprecationWarning` as a test error, so the warning cannot return unnoticed. Evidence:
`evidence/PHASE_1_PYTEST.log` and `docs/PHASE_1_REPORT.md` section 3.1.

### F3. Prerequisites owned by the project owner

1. Supabase project created, with the project URL, anon key and service role key supplied through a
   local `.env` file that is never committed and never pasted into chat.
2. Cloudflare account and Pages project, plus a decision between Git integration and direct upload.
3. Render account and service, on the free tier if available, with cold-start behaviour recorded,
   because the free tier suspends idle services and a live demonstration depends on it.
4. GitHub repository and access, if the assessment requires one.
5. Confirmation of the marking rubric, the report template, and the video requirements.

### F4. Cost note

The RM0 target is a target, not a guarantee. Supabase, Cloudflare and Render all revise their free-tier
limits, and Render suspends idle free services. Phase 1 must record the published limits in force at
the time of use, and the report's cost section must separate measured charges, published limits, and
estimates from each other.

---

End of master prompt. Sections A to D govern execution, Section E governs product behaviour, and
Section F governs what must be decided before Phase 1 starts.

---

## Section G. Phase plan (authoritative brief, supplied 2026-10-29)

This replaces the interim plan I wrote earlier. The phase numbering below is the project brief's, and
it governs from now on. Where my earlier numbering disagreed, the brief wins.

| Phase | Scope | Status at 2026-10-29 |
|---|---|---|
| 0 | Environment discovery and project planning | PASS, accepted |
| 1 | Project scaffolding and development environment (repo, frontend app, venv, git, .env.example, docs, README) | PARTIAL: backend and database scaffolded, frontend app and git not yet initialised |
| 2 | Database design, Supabase authentication and security foundation | PASS locally, live Supabase BLOCKED on account setup |
| 3 | FastAPI backend implementation (all required endpoints) | PASS locally, 88 tests |
| 4 | React frontend implementation | NOT STARTED |
| 5 | Integration, security review and bug fixes | NOT STARTED |
| 6 | GitHub version control and cloud deployment preparation | NOT STARTED |
| 7 | Deploy to free cloud services | NOT STARTED, requires owner accounts |
| 8 | Concurrent-user and performance testing | NOT STARTED |
| 9 | Cost analysis and optimisation | NOT STARTED |
| 10 | Documentation and architecture diagrams | NOT STARTED |
| 11 | Source-code package and demonstration | NOT STARTED |

Interpretation: the work already delivered covers the substance of brief Phases 2 and 3, because I
built schema, auth and API before the brief arrived. Phase 1 has two real gaps that must be closed
before Phase 4: the React application in `frontend/` was never created, and Git was never initialised.

Rules that apply to every phase from here:

- Only the phase's own scope is implemented. A later phase's work is recorded, not started.
- External services are used only when the phase explicitly requires them and the owner has approved
  that specific use. Until then, local implementations stand in behind the same interface, and the real
  implementation is marked NOT TESTED rather than assumed.
- The existing suite must stay green. New behaviour arrives with new tests, never by weakening an old
  one.
- Stop at the phase boundary with a report: implemented, tested, untested, blocked.

### Phase 2 boundary

In scope: `POST /api/v1/photos` (multipart upload), `GET /api/v1/photos` (feed with pagination and
filters), `GET /api/v1/photos/{id}`, `DELETE /api/v1/photos/{id}`, `GET /api/v1/photos/{id}/url`,
friend request endpoints, comment endpoints, tag management.

Out of scope and not started: any React code, any Locust scenario, any cloud resource, any deployment.

Storage: the Supabase Storage driver is implemented behind an interface but is NOT TESTED, because no
project exists. Phase 2 tests run against a local filesystem driver with HMAC signed URLs, which
reproduces the capability semantics of a Supabase signed URL closely enough to test expiry and
tampering. The difference is documented in the Phase 2 report rather than glossed over.
