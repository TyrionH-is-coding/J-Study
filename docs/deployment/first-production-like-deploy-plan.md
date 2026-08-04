# First Production-Like Deployment Plan

## Purpose

Run a small production-like deployment before the full frontend is finished. The goal is to verify routing, cookies, proxy headers, persistent volumes, logs, and rollback behavior with the same shape as the later public deployment.

This is a deployment gate, not a product launch.

## Minimal Vertical Slice

The first exercise should include:

- reverse proxy
- frontend service with login shell or placeholder authenticated route
- FastAPI backend
- Postgres
- mounted runtime volumes
- `GET /api/health`
- `GET /api/auth/me`
- one fake or synthetic job route if the real reader is not ready

Do not wait for the full reader UI before validating deployment semantics.

## Production Semantics to Freeze

Before publishing a test URL, record:

```text
domain
TLS termination point
reverse proxy product and version
trusted proxy IP/range
whether proxy headers are parsed
frontend origin
backend origin
cookie domain
cookie SameSite value
cookie Secure value
session secret source
mounted volume paths
log location
```

Default target:

```text
https://jstudy.online/        -> Next.js frontend
https://jstudy.online/api/... -> FastAPI backend
```

Keep frontend and backend same-site for MVP. Avoid CORS unless a later deployment decision requires it.

## Pre-Deployment Blockers

Do not open public testing until these backend limits exist:

- maximum PDF count per `course_outline` job
- total upload bytes per job
- single PDF size limit
- outline size limit and extension validation
- PDF MIME or magic-number validation
- parse timeout
- job-level concurrency or queue limit
- temporary file cleanup
- failed job cleanup
- expired artifact cleanup

## Release Manifest

Every production-like deploy must write a manifest before overwriting services:

```text
release_name
git_sha
branch_or_tag
image_digest_or_build_id
frontend_build_id
api_contract_version
material_package_schema_version
database_schema_version
config_sha
env_file_path_on_server
compose_file
reverse_proxy_config
backup_location
rollback_target
deployed_at
deployed_by
```

If the server baseline does not match the expected `git_sha`, compose file, or config hash, stop and report before overwriting files.

## Stage Gates

### A. Backup and Dry Run

Required:

- back up `.env`
- back up Postgres
- back up `data/settings`
- record current Git SHA and compose files
- verify restore location exists

Proceed only if the backup files exist and are readable.

### B. API and Database

Required:

- start Postgres
- start API
- verify `/api/health`
- verify `/api/readiness`
- verify auth tables exist
- verify logs do not contain secrets

### C. Frontend Service

Required:

- start Next.js service
- verify frontend build id
- verify `/login` or authenticated shell loads
- verify frontend calls same-site `/api/auth/me`

### D. Reverse Proxy and Domain

Required:

- enable HTTPS
- route `/api/*` to FastAPI
- route `/` to frontend
- verify cookie `HttpOnly`, `Secure`, and `SameSite=Lax`
- verify trusted proxy and client IP behavior is intentional

### E. Synthetic Account E2E

Required:

- register or log in with a synthetic account
- call `/api/auth/me`
- log out and confirm route guard
- run one small upload flow when the reader is available
- capture browser console errors
- test 390x844, 768x1024, and 1440x900 widths

Do not mark deployment accepted based only on HTTP 200 checks.

## Observability Minimum

Logs should include:

```text
request_id
job_id when present
service_mode
source_count
section_count
job_stage
duration_ms
provider
retry_count
error_type
```

Logs must not include:

- passwords
- cookies
- API keys
- complete document text
- raw uploaded file contents
- sensitive absolute upload paths

Add disk usage, queue length, failed-job rate, LLM cost, and job latency metrics before broader pilot usage.

## Rollback Rule

Rollback only the failed stage when possible.

If a database migration has run:

- prefer forward repair
- restore from backup only after confirming data loss risk
- do not manually edit production tables without a written recovery note

## Acceptance

The production-like deployment is accepted only when:

- release manifest is complete
- backup and rollback target are recorded
- health/readiness pass through the public domain
- same-site auth cookie flow works through the proxy
- synthetic account E2E passes
- browser console has zero unexpected errors
- mobile width has no horizontal overflow
- logs prove job/request observability without leaking secrets