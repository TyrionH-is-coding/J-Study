# User Auth Invite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add invite-gated email/password user auth with HTTP-only cookie sessions and admin-managed reusable invite codes.

**Architecture:** Use mature libraries for database models and password hashing, while keeping J-Study-specific invite validation and job ownership in small local service modules. SQLModel owns tables and query ergonomics; pwdlib owns password hashing; the API sets an opaque session token cookie and stores only a token hash in the database.

**Tech Stack:** FastAPI, SQLModel/SQLAlchemy, pwdlib[argon2], psycopg for Postgres deployment, unittest, HTTP-only cookies.

---

## Reuse Decision

Reviewed library direction before implementation:

- FastAPI Users has cookie transport and SQLAlchemy support, but its built-in registration flow is heavier than needed for the shared invite-code rule.
- Starlette has signed cookie sessions, but DB-backed opaque sessions are better here because logout and server-side invalidation stay clear.
- SQLModel is a thin FastAPI-friendly layer over SQLAlchemy and Pydantic.
- pwdlib provides a modern password-hashing wrapper and avoids hand-rolling password security.

Implementation will reuse SQLModel, pwdlib, and psycopg rather than copying GitHub snippets or writing password/session primitives from scratch.

## File Structure

- Modify: `requirements.txt`
  - Add `sqlmodel`, `pwdlib[argon2]`, and `psycopg[binary]`.
- Modify: `packages/core/jstudy_core/settings.py`
  - Add database/session runtime settings.
- Create: `packages/core/jstudy_core/auth_models.py`
  - SQLModel tables for users, invite codes, invite uses, and sessions.
- Create: `packages/core/jstudy_core/auth_db.py`
  - Engine/session factory and schema creation helper.
- Create: `packages/core/jstudy_core/auth_service.py`
  - Email normalization, password hashing, registration, login, session creation, invite management.
- Modify: `packages/core/jstudy_core/jobs.py`
  - Store optional `owner_user_id` in metadata and helper access checks.
- Modify: `apps/api/jstudy_api/app.py`
  - Add auth endpoints, admin invite endpoints, cookie handling, database wiring, and job access checks.
- Modify: `apps/api/jstudy_api/admin_ui.py`
  - Add an invite-code admin section.
- Modify: `apps/api/jstudy_api/ui.py`
  - Add a minimal temporary login/register gate before the upload form.
- Modify: `deploy/docker-compose/api.compose.yml`
  - Add Postgres and database/session environment variables.
- Modify: `.env.example`
  - Add database and session settings.
- Modify docs:
  - `README.md`
  - `docs/deployment/server-runbook.md`
- Tests:
  - Create `tests/test_auth_service.py`
  - Extend `tests/test_settings.py`
  - Extend `tests/test_web_mvp.py`
  - Extend `tests/test_deployment_files.py`

## Task 1: Add Auth Dependencies and Runtime Settings

**Files:**
- Modify: `requirements.txt`
- Modify: `packages/core/jstudy_core/settings.py`
- Test: `tests/test_settings.py`

- [ ] **Step 1: Write failing settings test**

Add a test that sets `DATABASE_URL`, `JSTUDY_SESSION_SECRET`, and `JSTUDY_COOKIE_SECURE`, then asserts `RuntimeSettings` exposes them.

- [ ] **Step 2: Run the settings test to verify failure**

Run:

```powershell
python -m unittest discover -s tests -p test_settings.py -v -k auth_database
```

Expected: fail because auth/database fields do not exist.

- [ ] **Step 3: Add dependencies and settings fields**

Add to `requirements.txt`:

```text
sqlmodel
pwdlib[argon2]
psycopg[binary]
```

Add runtime env names and dataclass fields:

```python
DATABASE_URL_ENV = "DATABASE_URL"
SESSION_SECRET_ENV = "JSTUDY_SESSION_SECRET"
COOKIE_SECURE_ENV = "JSTUDY_COOKIE_SECURE"
COOKIE_NAME_ENV = "JSTUDY_SESSION_COOKIE_NAME"

database_url: str = ""
session_secret: str = ""
cookie_secure: bool = False
session_cookie_name: str = "jstudy_session"
```

Default `database_url` to `sqlite:///{jobs_root}/jstudy.db` when `DATABASE_URL` is absent.

- [ ] **Step 4: Run settings tests**

Run:

```powershell
python -m unittest discover -s tests -p test_settings.py -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add requirements.txt packages/core/jstudy_core/settings.py tests/test_settings.py
git commit -m "feat: add auth runtime settings"
```

## Task 2: Add Auth Models and Service

**Files:**
- Create: `packages/core/jstudy_core/auth_models.py`
- Create: `packages/core/jstudy_core/auth_db.py`
- Create: `packages/core/jstudy_core/auth_service.py`
- Test: `tests/test_auth_service.py`

- [ ] **Step 1: Write failing service tests**

Create tests for:

- shared invite code can register two users
- disabled invite code is rejected
- duplicate email is rejected
- stored password is hashed
- login creates an opaque session token and stores only its hash
- invalid login raises an auth error
- session token resolves the current user
- logout deletes the session

- [ ] **Step 2: Run service tests to verify failure**

Run:

```powershell
python -m unittest discover -s tests -p test_auth_service.py -v
```

Expected: fail because modules do not exist.

- [ ] **Step 3: Implement models**

Use SQLModel tables:

- `User`
- `InviteCode`
- `InviteCodeUse`
- `UserSession`

Use string UUID primary keys to keep JSON/API serialization simple.

- [ ] **Step 4: Implement DB helpers**

Create:

```python
create_auth_engine(database_url: str)
create_auth_tables(engine)
session_scope(engine)
```

For SQLite URLs, pass `connect_args={"check_same_thread": False}`.

- [ ] **Step 5: Implement service**

Create `AuthService` with:

```python
create_invite_code(code: str, label: str = "")
list_invite_codes()
set_invite_code_enabled(invite_id: str, enabled: bool)
list_invite_uses(invite_id: str)
register(email: str, password: str, invite_code: str) -> User
login(email: str, password: str) -> tuple[User, str]
create_session(user_id: str) -> str
get_user_by_token(token: str) -> User | None
logout(token: str) -> None
```

Use `pwdlib.PasswordHash.recommended()` for hash/verify. Store `sha256(token)` in `UserSession`, never the raw token.

- [ ] **Step 6: Run service tests**

Run:

```powershell
python -m unittest discover -s tests -p test_auth_service.py -v
```

Expected: pass.

- [ ] **Step 7: Commit**

```powershell
git add packages/core/jstudy_core/auth_models.py packages/core/jstudy_core/auth_db.py packages/core/jstudy_core/auth_service.py tests/test_auth_service.py
git commit -m "feat: add invite auth service"
```

## Task 3: Add Auth and Invite API Endpoints

**Files:**
- Modify: `apps/api/jstudy_api/app.py`
- Test: `tests/test_web_mvp.py`

- [ ] **Step 1: Write failing API tests**

Add tests for:

- `POST /api/auth/register` requires invite code and sets cookie on success
- `POST /api/auth/login` sets cookie
- `GET /api/auth/me` returns current user
- `POST /api/auth/logout` clears cookie
- admin invite CRUD endpoints require admin token
- shared invite code can register multiple users through API

- [ ] **Step 2: Run API tests to verify failure**

Run:

```powershell
python -m unittest discover -s tests -p test_web_mvp.py -v -k auth
```

Expected: fail because endpoints do not exist.

- [ ] **Step 3: Wire auth service into `create_app`**

Create the auth engine from `runtime.database_url`, call `create_auth_tables(engine)`, and instantiate `AuthService`.

- [ ] **Step 4: Add cookie helpers**

Add:

```python
def set_session_cookie(response: Response, runtime: RuntimeSettings, token: str) -> None
def clear_session_cookie(response: Response, runtime: RuntimeSettings) -> None
def session_token_from_request(request: Request, runtime: RuntimeSettings) -> str
```

Cookie flags:

```text
httponly=True
samesite="lax"
secure=runtime.cookie_secure
path="/"
```

- [ ] **Step 5: Add auth endpoints**

Add:

```text
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

- [ ] **Step 6: Add admin invite endpoints**

Add:

```text
GET    /api/admin/invite-codes
POST   /api/admin/invite-codes
PATCH  /api/admin/invite-codes/{invite_id}
GET    /api/admin/invite-codes/{invite_id}/uses
```

- [ ] **Step 7: Run API tests**

Run:

```powershell
python -m unittest discover -s tests -p test_web_mvp.py -v
```

Expected: pass.

- [ ] **Step 8: Commit**

```powershell
git add apps/api/jstudy_api/app.py tests/test_web_mvp.py
git commit -m "feat: add auth and invite api"
```

## Task 4: Protect Generation and Job Artifacts

**Files:**
- Modify: `apps/api/jstudy_api/app.py`
- Modify: `packages/core/jstudy_core/jobs.py`
- Test: `tests/test_web_mvp.py`
- Test: `tests/test_job_store.py`

- [ ] **Step 1: Write failing ownership tests**

Add tests that:

- unauthenticated `POST /api/generate` returns `401`
- authenticated `POST /api/generate` succeeds
- generated job metadata includes `owner_user_id`
- another logged-in user gets `404` for job status and artifact endpoints

- [ ] **Step 2: Run ownership tests to verify failure**

Run:

```powershell
python -m unittest discover -s tests -p test_web_mvp.py -v -k owner
```

Expected: fail because endpoints are not auth-gated.

- [ ] **Step 3: Store owner metadata on job creation**

Resolve the current user before readiness/generation and add:

```python
"owner_user_id": current_user.id
```

to job metadata.

- [ ] **Step 4: Add owner checks**

Change `job_or_404` to accept the current user and return `404` when `job.metadata["owner_user_id"]` does not match.

- [ ] **Step 5: Update existing web tests**

Use helper methods to register/login before generation tests that expect success.

- [ ] **Step 6: Run web and job tests**

Run:

```powershell
python -m unittest discover -s tests -p test_web_mvp.py -v
python -m unittest discover -s tests -p test_job_store.py -v
```

Expected: pass.

- [ ] **Step 7: Commit**

```powershell
git add apps/api/jstudy_api/app.py packages/core/jstudy_core/jobs.py tests/test_web_mvp.py tests/test_job_store.py
git commit -m "feat: require auth for user jobs"
```

## Task 5: Add Temporary UI and Admin Invite Controls

**Files:**
- Modify: `apps/api/jstudy_api/ui.py`
- Modify: `apps/api/jstudy_api/admin_ui.py`
- Test: `tests/test_web_mvp.py`

- [ ] **Step 1: Write failing UI contract tests**

Assert `INDEX_HTML` contains `/api/auth/login`, `/api/auth/register`, `/api/auth/me`, and an `invite_code` field. Assert `ADMIN_SETTINGS_HTML` contains `/api/admin/invite-codes`.

- [ ] **Step 2: Run UI tests to verify failure**

Run:

```powershell
python -m unittest discover -s tests -p test_web_mvp.py -v -k invite
```

Expected: fail because UI controls do not exist.

- [ ] **Step 3: Add minimal upload UI auth gate**

Add login/register forms above the existing upload form. On page load call `/api/auth/me`; show upload only when authenticated.

- [ ] **Step 4: Add admin invite section**

Add a small section to list invite codes, create a code, toggle enabled, and view usage count.

- [ ] **Step 5: Run web tests**

Run:

```powershell
python -m unittest discover -s tests -p test_web_mvp.py -v
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add apps/api/jstudy_api/ui.py apps/api/jstudy_api/admin_ui.py tests/test_web_mvp.py
git commit -m "feat: add invite auth controls"
```

## Task 6: Update Deployment Config and Docs

**Files:**
- Modify: `.env.example`
- Modify: `deploy/docker-compose/api.compose.yml`
- Modify: `deploy/docker-compose/README.md`
- Modify: `docs/deployment/server-runbook.md`
- Modify: `README.md`
- Test: `tests/test_deployment_files.py`

- [ ] **Step 1: Write failing deployment test**

Assert compose references `postgres`, `DATABASE_URL`, and `JSTUDY_SESSION_SECRET`.

- [ ] **Step 2: Run deployment test to verify failure**

Run:

```powershell
python -m unittest discover -s tests -p test_deployment_files.py -v
```

Expected: fail because compose does not include Postgres/auth env yet.

- [ ] **Step 3: Update config and docs**

Add Postgres service and backend env vars:

```text
DATABASE_URL
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
JSTUDY_SESSION_SECRET
JSTUDY_COOKIE_SECURE
```

- [ ] **Step 4: Run deployment checks**

Run:

```powershell
python -m unittest discover -s tests -p test_deployment_files.py -v
docker compose -f deploy\docker-compose\api.compose.yml config
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add .env.example deploy/docker-compose/api.compose.yml deploy/docker-compose/README.md docs/deployment/server-runbook.md README.md tests/test_deployment_files.py
git commit -m "docs: add auth deployment config"
```

## Task 7: Final Verification

**Files:**
- No code edits unless verification exposes a failure.

- [ ] **Step 1: Install dependencies if needed**

Run:

```powershell
python -m pip install -r requirements.txt
```

- [ ] **Step 2: Compile check**

Run:

```powershell
python -m py_compile web_mvp.py mvp_runner.py apps/api/jstudy_api/app.py apps/api/jstudy_api/ui.py apps/api/jstudy_api/admin_ui.py packages/core/jstudy_core/admin_settings.py packages/core/jstudy_core/auth_db.py packages/core/jstudy_core/auth_models.py packages/core/jstudy_core/auth_service.py packages/core/jstudy_core/scenario_router.py packages/core/jstudy_core/parser_profile_router.py packages/core/jstudy_core/pipeline.py packages/core/jstudy_core/cli.py packages/core/jstudy_core/citations.py packages/core/jstudy_core/jobs.py packages/core/jstudy_core/providers.py packages/core/jstudy_core/settings.py packages/core/jstudy_core/storage.py packages/parsers/mineru_parser.py packages/parsers/pymupdf_parser.py
```

- [ ] **Step 3: Full tests**

Run:

```powershell
python -m unittest discover -s tests -v
```

- [ ] **Step 4: Diff and compose checks**

Run:

```powershell
git diff --check
docker compose -f deploy\docker-compose\api.compose.yml config
```

- [ ] **Step 5: Push branch**

Run:

```powershell
git push
```

## Self-Review

- Spec coverage: invite-gated registration, shared invite codes, email verification field, cookie session, admin invite management, Postgres deployment, and job ownership are covered.
- Marker scan: no unfinished implementation markers remain.
- Type consistency: `User`, `InviteCode`, `InviteCodeUse`, `UserSession`, `AuthService`, `owner_user_id`, `DATABASE_URL`, and `JSTUDY_SESSION_SECRET` names are consistent.
