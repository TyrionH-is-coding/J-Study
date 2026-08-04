# Server Deployment Runbook

## Purpose

This runbook describes the intended single-server deployment path for J-Study. It keeps the pilot portable so the same Docker Compose structure can move from the current Tencent Cloud server to a formal server later.

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

Current required pilot backend topology (`PostgreSQL + API + Worker`):

```text
postgres
jstudy-api
jstudy-worker
```

Frontend deployment phase:

```text
reverse-proxy
jstudy-web
jstudy-api
postgres
jstudy-worker
```

Future production phase:

```text
reverse-proxy
jstudy-web
jstudy-api
jstudy-worker
postgres
redis
object-storage integration
```

PostgreSQL, `jstudy-api`, and `jstudy-worker` are required for the first pilot. Redis and object storage remain optional until usage justifies them.

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

The deployment `.env` should start from `.env.example`.

Backend variables:

```text
SILICONFLOW_API_KEY=
SILICONFLOW_API_KEY_FILE=
SILICONFLOW_CHAT_MODEL=
SILICONFLOW_EMBED_MODEL=
MINERU_API_BASE_URL=
MINERU_API_TOKEN=
MINERU_MODEL_VERSION=
MINERU_LANGUAGE=
MINERU_POLL_INTERVAL_SECONDS=
MINERU_DEADLINE_SECONDS=
MINERU_MAX_RESULT_BYTES=
JSTUDY_API_PORT=8765
JSTUDY_ADMIN_TOKEN=
JSTUDY_SETTINGS_DIR=/app/data/settings
JSTUDY_JOBS_DIR=/app/data/jobs
JSTUDY_SOUL_PATH=
JSTUDY_MNEMONICS_PATH=
JSTUDY_MAX_PDF_BYTES=
JSTUDY_JOB_RETENTION_HOURS=72
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
- Keep `DATABASE_URL`, `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` consistent.
- URL-encode reserved characters in the password portion of `DATABASE_URL`.
- Treat `JSTUDY_MNEMONICS_PATH` as the current compatibility name for the prompt-rendered knowledge snippet file.
- Provider credential priority is nonempty `SILICONFLOW_API_KEY`, then nonempty `SILICONFLOW_API_KEY_FILE`, then the admin inline key, then the admin/default key file. Readiness, API submission snapshots, Worker claims, and pipeline execution use this same result.
- MinerU environment values are merged into the parser snapshot consumed by API availability checks and Worker runner configuration. This does not switch the current pipeline or parser default.
- A nonempty provider, model, MinerU, Soul/content path, upload-limit, or retention environment variable is an explicit deployment override. It takes precedence over `data/settings` and cannot be hot-updated from the admin page.
- Leave an admin-managed environment variable empty when `/admin/settings` should own it. The API reloads settings for each new submission and the worker for each new claim; an active claim keeps its starting snapshot.
- Keep `JSTUDY_JOB_RETENTION_HOURS=72` nonempty for the public pilot so cleanup cannot silently fall back to the application default of `0`.
- `JSTUDY_GENERATION_MAX_CONCURRENCY` accepts `1..4`, with 默认值 `3`.
  Set it to `1` for 串行回滚 when Provider throttling or reliability requires
  a conservative mode. The cap is per Job; total calls multiply with Worker 副本
  count, so do not scale replicas independently of Provider limits.
- Offline deterministic tests do not pass the latency gate. After deployment,
  the Supervisor must run the same six-page sample three times and verify a
  created-to-completed median no more than 25 秒 and no single run over 35 秒.
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

The API creates the current SQLModel tables on startup. Add Alembic migrations before making destructive schema changes.

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

After frontend work, add a full compose file or extend the existing deployment:

```text
deploy/docker-compose/app.compose.yml
```

Expected full service responsibilities:

- `reverse-proxy`: TLS termination and path routing.
- `jstudy-web`: Next.js frontend.
- `jstudy-api`: FastAPI backend.
- `postgres`: user, invite, session, and job metadata persistence.
- `jstudy-worker`: claim queued Jobs, execute generation, publish terminal state, and enforce retention.

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

Use this for backend smoke testing before the separate frontend and reverse proxy are ready:

```bash
cd /opt/jstudy/app
cp .env.example .env
# edit .env: set SILICONFLOW_API_KEY, JSTUDY_ADMIN_TOKEN, POSTGRES_PASSWORD,
# DATABASE_URL, JSTUDY_SESSION_SECRET, and JSTUDY_INVITE_REQUIRED
docker compose -f deploy/docker-compose/api.compose.yml up -d --build postgres jstudy-api jstudy-worker
```

Verify:

```bash
curl http://127.0.0.1:8765/api/health
curl http://127.0.0.1:8765/api/readiness
curl "http://127.0.0.1:8765/api/readiness?probe_provider=true"
```

The readiness response must be `ready` before pilot users submit PDFs.
Keep `JSTUDY_INVITE_REQUIRED=true` for normal pilot access. For a small private test, `JSTUDY_INVITE_REQUIRED=false` allows registration without invite codes; restore it before opening registration more broadly. When invite registration is enabled, create at least one reusable invite code from `/admin/settings?admin_token=...` before testing registration.

Readiness is not sufficient because the API only admits and queues work. After
registering or logging in a smoke-test user:

1. Submit one small test PDF through `POST /api/generate` and record its `job_id`.
2. Poll `GET /api/jobs/{job_id}` with the same authenticated session.
3. Confirm the Job leaves `queued`, proving `jstudy-worker` claimed it.
4. Confirm the Job reaches `completed` or `failed`; a terminal `failed` result is
   acceptable for topology verification only when its safe error is understood.
5. Inspect `docker compose -f deploy/docker-compose/api.compose.yml logs --tail=200 jstudy-worker`.

A Job that remains `queued` fails deployment acceptance even when `/api/health`
and `/api/readiness` pass.

The first Tencent Cloud backend-only trial record is tracked in
[`tencent-cloud-trial-2026-06-15.md`](tencent-cloud-trial-2026-06-15.md).

## Isolated Tencent Staging Scaffold

Task 0010 only prepares the local deployment scaffold. Remote checkout, Nginx,
DNS, TLS, and provider smoke tests remain Supervisor-operated steps after code
review.

Use a checkout at `/opt/jstudy-staging/app`. Its `.env`, `data/jobs`,
`data/settings`, and `data/postgres` must be independent from the old deployment.
Set these non-secret topology values in the staging `.env`:

```dotenv
JSTUDY_IMAGE_NAME=jstudy-backend:staging-test
JSTUDY_API_CONTAINER_NAME=jstudy-staging-api
JSTUDY_WORKER_CONTAINER_NAME=jstudy-staging-worker
JSTUDY_POSTGRES_CONTAINER_NAME=jstudy-staging-postgres
JSTUDY_API_BIND_ADDRESS=127.0.0.1
JSTUDY_API_PORT=8766
```

The published API is therefore limited to `127.0.0.1:8766`; container traffic
continues to use port `8765` and database hostname `postgres`.

### Startup, Status, And Logs

From the staging checkout:

```powershell
docker compose -p jstudy-staging --env-file .env -f deploy/docker-compose/api.compose.yml up -d --build
docker compose -p jstudy-staging --env-file .env -f deploy/docker-compose/api.compose.yml ps
docker compose -p jstudy-staging --env-file .env -f deploy/docker-compose/api.compose.yml logs --tail 200 jstudy-api jstudy-worker
```

Run Compose from a clean shell after changing `.env`. Do not source the old
`.env` and then overwrite the file in the same shell: exported parent-process
variables take precedence over `--env-file` and can silently recreate
containers with stale credentials or model values. Before a recreate, verify
that no unexpected runtime overrides remain in the parent environment.

Never reuse the 旧数据库目录. Do not commit `.env`, Token, 上传文件, or
生成产物. Do not run `down -v` against staging or the old deployment, and do
not operate the 旧 `jstudy` containers from staging commands.

### Acceptance

The remote deployment is not accepted until the Supervisor verifies:

1. `/api/health`, `/api/readiness`, and
   `/api/readiness?probe_provider=true`.
2. Registration, login, authenticated Cookie behavior, HTTPS, and Secure Cookie.
3. One synthetic PDF Job leaves `queued` and reaches `completed`, or reaches
   `failed` with a safe and understood terminal reason.
4. Worker processing and authenticated reads of Manifest, Learning Map,
   Coverage, and Package v2.
5. The API is published only through the intended loopback and proxy path.

### Staging Backup

Before an update, create a staging-only `backup` of:

- the staging `.env`, stored outside Git;
- `data/settings`;
- the staging PostgreSQL database;
- `data/jobs` only when the acceptance artifacts must be retained.

Record the reviewed Git SHA and image name with the backup. Never copy staging
credentials or data into the old deployment directories.

### Staging Rollback

Application `rollback` stops only the `jstudy-staging` Compose project, restores
the prior reviewed staging checkout/image and staging Nginx configuration, then
starts the same project again:

```powershell
docker compose -p jstudy-staging --env-file .env -f deploy/docker-compose/api.compose.yml down
docker compose -p jstudy-staging --env-file .env -f deploy/docker-compose/api.compose.yml up -d
```

Do not use `down -v`. Do not stop, recreate, or change the old `jstudy`
containers, database, data directories, domain, or certificates. Database
restore is a separate Supervisor-controlled action and requires a verified
staging backup.

## First Full Deployment After Frontend

Before the first full deployment, run the smaller production-like exercise in
[`first-production-like-deploy-plan.md`](first-production-like-deploy-plan.md).
That plan is the gate for proxy headers, same-site cookies, manifest capture,
backup, rollback, and real-browser verification.

Planned sequence:

1. Pull the reviewed branch or release tag.
2. Create or update `.env`.
3. Start PostgreSQL, API, and Worker.
4. Verify `jstudy-worker` is running and connected to the shared database and jobs volume.
5. Verify `/api/health` and `/api/readiness`.
6. Create at least one invite code from the admin panel when `JSTUDY_INVITE_REQUIRED=true`.
7. Start frontend.
8. Start or reload reverse proxy.
9. Verify HTTPS domain routes.
10. Register a test user, using the invite code when `JSTUDY_INVITE_REQUIRED=true`.
11. Upload a small test PDF, verify it leaves `queued` and reaches `completed` or `failed`, then verify citation preview for a completed Job.

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
docker compose -f deploy/docker-compose/app.compose.yml logs --tail=200 jstudy-worker
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
- `JSTUDY_SESSION_SECRET` is set.
- HTTPS is enabled.
- Cookies are `HttpOnly`, `Secure`, and `SameSite=Lax`.
- `JSTUDY_INVITE_REQUIRED=true` before public registration.
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

- Add frontend container after `apps/web` exists.
- Add reverse proxy config.
- Add release manifest generation before overwriting server files.
- Add real-browser deployment smoke checks for login, `/api/auth/me`, upload, polling, reader, and source preview.
- Add Alembic migrations before the schema needs versioned changes.
- Move uploaded PDFs and generated artifacts to object storage when pilot retention is no longer enough.
