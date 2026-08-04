# User Auth and Invite Design

## Goal

Add a minimal learner account system before building the full frontend. The system should let pilot users register with an email, password, and a shared invite code by default, then use J-Study with an HTTP-only cookie session. For small private tests, operators may temporarily set `JSTUDY_INVITE_REQUIRED=false` to allow registration without an invite code.

This design is for the first productized pilot. It should not add social login, email verification delivery, billing, teams, or admin user roles.

## Decisions

- Registration uses email, password, and invite code by default.
- `JSTUDY_INVITE_REQUIRED=false` may temporarily disable the invite-code requirement for small private tests.
- Invite codes can be shared by many users.
- Invite codes can be enabled or disabled by the operator.
- Email verification is represented by `email_verified`, defaulting to `false`, but it does not block registration or login in the first version.
- Login state uses an HTTP-only cookie session.
- Admin access remains protected by `JSTUDY_ADMIN_TOKEN`.
- Invite-code management belongs in the admin settings surface.
- Server deployment uses Postgres.
- Local app startup for the user is not required before server deployment, but automated tests must still cover the auth behavior.

## External Reuse Requirement

Before implementation, review current maintained FastAPI auth and database options instead of hand-rolling security primitives. At minimum compare:

- `fastapi-users` for reusable user-management patterns.
- Starlette/FastAPI session middleware options for cookie session behavior.
- SQLAlchemy or SQLModel for Postgres persistence.
- `pwdlib`, `argon2-cffi`, or Passlib for password hashing.
- Alembic for database migrations.

The implementation should use mature libraries for password hashing, ORM/database access, and migrations. Custom code should stay limited to J-Study-specific business rules such as invite validation, job ownership, and admin-panel integration.

## Recommended Approach

Use SQLAlchemy or SQLModel with Alembic migrations, a small auth service layer, and HTTP-only signed session cookies.

Do not introduce a large authentication framework unless it clearly reduces total code and fits the invite-code requirement cleanly. A thin local auth service is acceptable when it delegates password hashing, database persistence, and cookie signing to mature libraries.

## Data Model

### `users`

```text
id                 uuid primary key
email              text unique not null
password_hash      text not null
email_verified     boolean not null default false
is_active          boolean not null default true
created_at         timestamptz not null
updated_at         timestamptz not null
last_login_at      timestamptz null
```

Rules:

- Store normalized lowercase emails.
- Never store raw passwords.
- Reject registration if the email already exists.
- `email_verified=false` is informational in the MVP.

### `invite_codes`

```text
id                 uuid primary key
code               text unique not null
label              text not null default ''
enabled            boolean not null default true
created_at         timestamptz not null
updated_at         timestamptz not null
disabled_at        timestamptz null
```

Rules:

- Invite code is shared and reusable while enabled.
- No `max_uses` in the first version.
- Code matching should be exact after trimming whitespace.
- Operators can disable a code without deleting historical usage.

### `invite_code_uses`

```text
id                 uuid primary key
invite_code_id     uuid references invite_codes(id)
user_id            uuid references users(id)
email              text not null
used_at            timestamptz not null
```

Rules:

- Write one usage record after successful user creation.
- Keep usage records for audit even if the code is later disabled.

### Job Ownership

The current MVP stores jobs in JSON files. Once user auth is added, generated jobs must be tied to the current user.

First implementation target:

```text
jobs.owner_user_id uuid not null
```

If job persistence remains JSON temporarily, `owner_user_id` must be stored in job metadata and checked by every job result endpoint. The preferred implementation is to move job records into Postgres in the same auth/database phase.

## API Contract

### Public Auth Endpoints

```text
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

`POST /api/auth/register` request:

```json
{
  "email": "student@example.com",
  "password": "plain text from form",
  "invite_code": "MED-PILOT-2026"
}
```

Registration behavior:

- Validate email format.
- Require a password with a minimum length of 8 characters.
- Require an enabled invite code when `JSTUDY_INVITE_REQUIRED=true`.
- Create user with `email_verified=false`.
- Record invite-code usage only when invite registration is enabled.
- Start a session after successful registration.

`POST /api/auth/login` behavior:

- Validate email and password.
- Reject inactive users.
- Set HTTP-only session cookie on success.
- Update `last_login_at`.

`POST /api/auth/logout` behavior:

- Clear the session cookie.

`GET /api/auth/me` response:

```json
{
  "id": "uuid",
  "email": "student@example.com",
  "email_verified": false
}
```

### Admin Invite Endpoints

Protected by `JSTUDY_ADMIN_TOKEN`, not by user session:

```text
GET    /api/admin/invite-codes
POST   /api/admin/invite-codes
PATCH  /api/admin/invite-codes/{id}
GET    /api/admin/invite-codes/{id}/uses
```

Admin create request:

```json
{
  "code": "MED-PILOT-2026",
  "label": "Medicine pilot group"
}
```

Admin update request:

```json
{
  "label": "Medicine pilot group",
  "enabled": false
}
```

## Session Rules

Use HTTP-only cookies:

```text
HttpOnly=true
SameSite=Lax
Secure=true in production
Path=/
```

Deployment should keep frontend and backend on the same site:

```text
https://domain.example/        -> frontend
https://domain.example/api/... -> backend
```

This keeps cookie auth simple and avoids token storage in frontend JavaScript.

Session storage may be:

- signed cookie containing a session id, with session records in Postgres; recommended for revocation and logout clarity.
- fully signed cookie with user id and expiry; acceptable only if revocation is not needed.

Recommended first version: Postgres-backed sessions.

## Required Access Control

These endpoints should require a logged-in user:

```text
POST /api/generate
GET  /api/jobs/{job_id}
GET  /api/jobs/{job_id}/output
GET  /api/jobs/{job_id}/evidence
GET  /api/jobs/{job_id}/evidence-links
GET  /api/jobs/{job_id}/trace
GET  /api/jobs/{job_id}/pdf
GET  /api/jobs/{job_id}/pdf-info
GET  /api/jobs/{job_id}/pdf-page/{page}.png
```

Rules:

- Users can only see their own jobs.
- Unauthenticated requests return `401`.
- Authenticated requests for another user's job return `404`, not `403`, to avoid leaking job ids.
- `GET /api/options`, `GET /api/health`, and `GET /api/readiness` stay public.
- Admin settings and invite management remain protected by admin token.

## Frontend Requirements

The first frontend should include:

- login page
- register page with invite-code field
- logout action
- session restore using `/api/auth/me`
- route guard for the upload/reader app
- clear error messages for invalid invite, duplicate email, wrong password, and expired session

Do not build password reset, email verification flow, profile settings, or user roles in the first version.

## Admin UI Requirements

Add an Invite Codes section to the admin surface:

- list code, label, enabled state, created time, usage count
- create code
- edit label
- enable/disable code
- view usage records with email and used time

The admin surface remains operator-only and token-protected.

## Error Handling

- Invalid invite code: `400`
- Disabled invite code: `400`
- Duplicate email: `409`
- Invalid login credentials: `401`
- Missing session: `401`
- Unauthorized job access: `404`
- Missing database configuration at startup or readiness: readiness degraded

Do not reveal whether an email exists during login.

## Testing Plan

Backend tests:

- registration requires invite code by default
- registration can skip invite code when `JSTUDY_INVITE_REQUIRED=false`
- shared invite code can register multiple users
- disabled invite code is rejected
- duplicate email is rejected
- password is hashed, not stored raw
- login sets a session cookie
- logout clears session
- `/api/auth/me` returns the logged-in user
- unauthenticated job generation is rejected
- users cannot read another user's job
- admin invite endpoints require admin token

Migration/config tests:

- database URL is required in server deployment
- Alembic migrations create auth tables
- app readiness reports database status

Frontend contract tests:

- register form includes invite code
- login redirects into the app after success
- expired session redirects to login

## Non-Goals

- Email verification delivery.
- Password reset.
- Social login.
- User roles.
- Billing.
- Team workspaces.
- Invite-code max-use limits.
- Device/session management UI.

## Open Implementation Checkpoints

- Choose SQLAlchemy vs SQLModel after checking current ecosystem fit.
- Choose session implementation after comparing maintained Starlette/FastAPI options.
- Decide whether job persistence moves to Postgres in the same PR or in a separate PR. The preferred direction is same phase, but it may be split if the diff becomes too large.
