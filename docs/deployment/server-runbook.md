# Server Deployment Runbook

## Purpose

This runbook describes the intended single-server deployment path for J-Study. It is written before the full frontend and user-auth implementation so deployment choices stay reproducible instead of becoming a set of one-off shell commands.

## Deployment Principles

- Use Docker Compose for all application services.
- Keep secrets in `.env`, never in Git.
- Keep runtime data in mounted volumes.
- Use one domain with same-site routing:

```text
https://domain.example/        -> frontend
https://domain.example/api/... -> backend
```

- Keep the pilot portable so it can move from the current Tencent Cloud server to a formal server later.
- Do not require manually installed Python or Node dependencies on the server outside containers.

## Target Services

Current backend-only phase:

```text
jstudy-api
```

Auth/frontend deployment phase:

```text
reverse-proxy
jstudy-web
jstudy-api
postgres
```

Future production phase:

```text
reverse-proxy
jstudy-web
jstudy-api
worker
postgres
redis
object-storage integration
```

Redis, a worker, and object storage are not required for the first pilot unless usage proves they reduce operational risk.

## Server Prerequisites

Required on the Linux server:

- Docker Engine
- Docker Compose plugin
- Git
- Open inbound `80` and `443`
- Domain DNS A record pointing to the server
- A deployment user with permission to run Docker

Recommended directories:

```text
/opt/jstudy/app       git checkout
/opt/jstudy/data      mounted runtime data
/opt/jstudy/backups   database and env backups
```

## Environment Variables

The deployment `.env` should start from `.env.example` and add auth/database settings after they exist.

Current backend variables:

```text
SILICONFLOW_API_KEY=
SILICONFLOW_API_KEY_FILE=
SILICONFLOW_CHAT_MODEL=
SILICONFLOW_EMBED_MODEL=
JSTUDY_API_PORT=8765
JSTUDY_ADMIN_TOKEN=
JSTUDY_SETTINGS_DIR=/app/data/settings
JSTUDY_JOBS_DIR=/app/data/jobs
JSTUDY_SOUL_PATH=/app/soul.md
JSTUDY_MNEMONICS_PATH=/app/mnemonics.md
JSTUDY_MAX_PDF_BYTES=52428800
JSTUDY_JOB_RETENTION_HOURS=72
```

Auth/database variables to add with the user system:

```text
DATABASE_URL=postgresql+psycopg://jstudy:password@postgres:5432/jstudy
POSTGRES_DB=jstudy
POSTGRES_USER=jstudy
POSTGRES_PASSWORD=
JSTUDY_SESSION_SECRET=
JSTUDY_COOKIE_SECURE=true
```

Rules:

- Generate `JSTUDY_ADMIN_TOKEN`, `POSTGRES_PASSWORD`, and `JSTUDY_SESSION_SECRET` with high entropy.
- Do not reuse local/dev secrets on the server.
- Keep a copy of the production `.env` outside the repository and include it in backup procedures.

## Data Volumes

Current mounted data:

```text
data/jobs       uploaded PDFs, generated outputs, job JSON state
data/settings   admin-managed model/RAG/parser/content settings
```

Auth phase mounted data:

```text
data/postgres   Postgres database files
```

Retention:

- Keep `JSTUDY_JOB_RETENTION_HOURS=72` for public pilot testing.
- Use `168` only if reviewers need a full week.
- Do not leave retention disabled for public users.

Object storage:

- Local disk is acceptable for the pilot because citation preview needs the original PDF.
- Move uploaded PDFs and generated artifacts to Tencent COS when user history, course libraries, or formal multi-user accounts require durable storage beyond short review windows.

## Compose Layout

Backend-only compose exists at:

```text
deploy/docker-compose/api.compose.yml
```

After auth/frontend work, add a full compose file or extend the existing deployment:

```text
deploy/docker-compose/app.compose.yml
```

Expected full service responsibilities:

- `reverse-proxy`: TLS termination and path routing.
- `jstudy-web`: Next.js frontend.
- `jstudy-api`: FastAPI backend.
- `postgres`: user, invite, session, and job metadata persistence.

## Reverse Proxy Routing

Recommended path routing:

```text
/api/*           -> jstudy-api:8765
/admin/settings  -> jstudy-api:8765
/                -> jstudy-web:3000
```

Cookie requirements:

- Keep frontend and backend same-site.
- Use `Secure` cookies when HTTPS is enabled.
- Use `SameSite=Lax`.
- Avoid cross-origin frontend/backend deployment for the MVP.

Caddy is recommended for the first server because it can manage HTTPS automatically with less configuration. Nginx is also acceptable if existing server practice favors it.

## First Backend-Only Deployment

Use this only for backend smoke testing before auth/frontend is ready:

```bash
cd /opt/jstudy/app
cp .env.example .env
# edit .env: set SILICONFLOW_API_KEY and JSTUDY_ADMIN_TOKEN
docker compose -f deploy/docker-compose/api.compose.yml up -d --build
```

Verify:

```bash
curl http://127.0.0.1:8765/api/health
curl http://127.0.0.1:8765/api/readiness
curl "http://127.0.0.1:8765/api/readiness?probe_provider=true"
```

The readiness response must be `ready` before pilot users submit PDFs.

## First Full Deployment After Auth/Frontend

Planned sequence:

1. Pull the reviewed branch or release tag.
2. Create or update `.env`.
3. Start Postgres.
4. Run database migrations.
5. Start backend.
6. Verify `/api/health` and `/api/readiness`.
7. Create at least one invite code from the admin panel.
8. Start frontend.
9. Start or reload reverse proxy.
10. Verify HTTPS domain routes.
11. Register a test user with the invite code.
12. Upload a small test PDF and verify citation preview.

Expected commands will be finalized after `app.compose.yml` and migrations exist.

## Updating an Existing Deployment

Standard update:

```bash
cd /opt/jstudy/app
git fetch --all --prune
git checkout <release-branch-or-tag>
docker compose -f deploy/docker-compose/app.compose.yml pull
docker compose -f deploy/docker-compose/app.compose.yml build
docker compose -f deploy/docker-compose/app.compose.yml run --rm jstudy-api alembic upgrade head
docker compose -f deploy/docker-compose/app.compose.yml up -d
```

Verify after update:

```bash
curl https://domain.example/api/health
curl https://domain.example/api/readiness
```

Then test:

- login
- `/api/auth/me`
- upload job
- job output
- PDF citation preview

## Rollback

Rollback should be possible without hand-editing containers:

```bash
cd /opt/jstudy/app
git checkout <previous-release-tag>
docker compose -f deploy/docker-compose/app.compose.yml up -d --build
```

Database rollback is riskier than app rollback. For MVP:

- Prefer forward-only migrations.
- Back up Postgres before applying migrations.
- Avoid destructive migrations until there is a tested restore path.

## Backups

Back up:

- `.env`
- `data/settings`
- Postgres database

Pilot local job artifacts can usually be disposable because retention is short. If a pilot requires keeping job artifacts, include `data/jobs` in backups and document storage growth.

Recommended backup command after Postgres is added:

```bash
docker compose -f deploy/docker-compose/app.compose.yml exec postgres pg_dump -U jstudy jstudy > /opt/jstudy/backups/jstudy-$(date +%Y%m%d-%H%M%S).sql
```

## Monitoring and Logs

Minimal pilot checks:

```bash
docker compose -f deploy/docker-compose/app.compose.yml ps
docker compose -f deploy/docker-compose/app.compose.yml logs --tail=200 jstudy-api
docker compose -f deploy/docker-compose/app.compose.yml logs --tail=200 postgres
```

Health endpoints:

```text
GET /api/health
GET /api/readiness
```

Add external uptime monitoring after the domain is public.

## Security Checklist

Before public testing:

- `JSTUDY_ADMIN_TOKEN` is set.
- `JSTUDY_SESSION_SECRET` is set after auth exists.
- HTTPS is enabled.
- Cookies are `HttpOnly`, `Secure`, and `SameSite=Lax`.
- Invite registration is required.
- Admin invite endpoints require admin token.
- Users can only access their own jobs.
- `JSTUDY_JOB_RETENTION_HOURS` is nonzero.
- `.env` is not committed.
- Server firewall exposes only necessary ports.

## Migration to a Formal Server

To move from the pilot Tencent Cloud server to a formal server:

1. Freeze writes by disabling registration and uploads temporarily.
2. Back up `.env`, `data/settings`, and Postgres.
3. Copy repository release tag and runtime data to the new server.
4. Restore Postgres.
5. Restore `.env` with updated domain-specific values.
6. Start compose services.
7. Run readiness checks and a test login/upload.
8. Switch DNS.
9. Keep the old server available until DNS propagation and smoke tests pass.

If object storage has been introduced, migrate objects before switching DNS and verify signed/private access policies.

## Open Items Before Full Deployment

- Implement user auth and invite-code management.
- Add Postgres service and migrations.
- Move job ownership into user-aware persistence.
- Add frontend container after `apps/web` exists.
- Add reverse proxy config.
- Finalize exact deployment commands after the compose file exists.
