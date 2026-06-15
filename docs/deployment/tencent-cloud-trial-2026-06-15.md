# Tencent Cloud Backend Trial Deployment

Date: 2026-06-15

## Scope

This record captures the first backend-only J-Study smoke deployment on the Tencent Cloud pilot server. It verifies the current PR branch can run with Docker Compose, Postgres, invite-gated auth, admin settings, provider connectivity, and one real PDF generation job.

This is not the final frontend deployment. The backend is running on the server and is reachable through the pilot domain.

## Server

```text
SSH alias: tencent-cloud
Host: VM-0-4-ubuntu
Public IP: 43.157.84.138
Domain: jstudy.online
Remote user: ubuntu
Application path: /opt/jstudy/app
Git branch: feature/backend-frontend-mvp
Application code commit tested: e899b8b
Compose file: deploy/docker-compose/api.compose.yml
Environment file: /opt/jstudy/app/.env
Environment file permissions: 600 ubuntu:ubuntu
Nginx site: /etc/nginx/sites-available/jstudy.online
TLS certificate: /etc/letsencrypt/live/jstudy.online/fullchain.pem
```

Runtime versions observed on the server:

```text
Docker version 29.5.2
Docker Compose version v5.1.4
Git version 2.34.1
```

## Environment

The server `.env` was generated at:

```text
/opt/jstudy/app/.env
```

Secrets are not committed. The file contains:

```text
SILICONFLOW_API_KEY=SET
JSTUDY_ADMIN_TOKEN=SET
POSTGRES_PASSWORD=SET
DATABASE_URL=SET
JSTUDY_SESSION_SECRET=SET
```

Notes:

- The SiliconFlow key was reused from an existing server-local environment file.
- `JSTUDY_ADMIN_TOKEN` was rotated after the first smoke request used a query parameter and therefore appeared in container access logs.
- Use `Authorization: Bearer <token>` for admin requests going forward.
- `JSTUDY_COOKIE_SECURE=true` after HTTPS was configured.

## DNS and Reverse Proxy

Cloudflare DNS:

```text
Zone: jstudy.online
Record: A jstudy.online -> 43.157.84.138
Proxy mode: DNS only
```

Nginx:

```text
HTTP :80  -> redirects to HTTPS
HTTPS :443 -> proxies to http://127.0.0.1:8765
client_max_body_size: 60m
proxy_read_timeout: 300s
proxy_send_timeout: 300s
```

TLS:

```text
Issuer path: Let's Encrypt via certbot nginx plugin
Certificate path: /etc/letsencrypt/live/jstudy.online/fullchain.pem
Private key path: /etc/letsencrypt/live/jstudy.online/privkey.pem
Expires: 2026-09-13
Renewal: certbot scheduled renewal task installed
```

Certbot note:

- The server had a user-local `cryptography` package that conflicted with the apt-managed certbot stack.
- Running certbot with `PYTHONNOUSERSITE=1` avoided loading `/home/ubuntu/.local/lib/python3.10/site-packages`.
- Command shape used:

```bash
sudo env PYTHONNOUSERSITE=1 certbot --nginx -d jstudy.online --non-interactive --agree-tos --register-unsafely-without-email --redirect
```

## Services

Started with:

```bash
cd /opt/jstudy/app
docker compose -f deploy/docker-compose/api.compose.yml --env-file .env up -d --build
```

Observed services:

```text
jstudy-api        Up, healthy, 0.0.0.0:8765->8765/tcp
jstudy-postgres   Up, healthy, 5432/tcp internal
```

Mounted runtime data:

```text
/opt/jstudy/app/data/jobs       -> /app/data/jobs
/opt/jstudy/app/data/settings   -> /app/data/settings
/opt/jstudy/app/data/postgres   -> /var/lib/postgresql/data
```

## Verification Evidence

Compose config:

```text
docker compose -f deploy/docker-compose/api.compose.yml --env-file .env config
Result: OK
```

Health:

```text
GET https://jstudy.online/api/health
Result: 200
Body: {"status":"ok","service":"jstudy-api"}
```

Readiness:

```text
GET https://jstudy.online/api/readiness
Result: 200
Status: ready
Checks:
- jobs_root: ok
- soul_path: ok
- mnemonics_path: ok
- api_key: ok, SILICONFLOW_API_KEY
- max_pdf_bytes: ok, 52428800
- job_retention_hours: ok, 72 hours
```

Provider probe:

```text
GET https://jstudy.online/api/readiness?probe_provider=true
Result: 200
provider_connectivity: ok
embedding: ok
chat: ok
detail: chat and embedding reachable
```

Admin access:

```text
GET /admin/settings with Authorization: Bearer <token>
Result: 200

GET /admin/settings without token
Result: 401
```

Cookie check:

```text
POST https://jstudy.online/api/auth/register
Result: 200
Set-Cookie: jstudy_session=<redacted>; HttpOnly; Path=/; SameSite=lax; Secure
```

Invite/auth smoke:

```text
POST /api/admin/invite-codes
Result: 200

POST /api/auth/register
Result: 200

GET /api/auth/me with session cookie
Result: 200
```

Server-local PDF generation smoke:

```text
POST /api/generate with a one-page PDF
Result: 200
Job ID: 68ea5f32d850
Final job status: completed
Job error: empty

GET /api/jobs/68ea5f32d850/output
Result: 200
Markdown chars: 6046

GET /api/jobs/68ea5f32d850/pdf-info
Result: 200
PDF page count: 1

GET /api/jobs/68ea5f32d850/pdf-page/1.png
Result: 200
PNG bytes: 5815
```

HTTPS domain PDF generation smoke:

```text
POST https://jstudy.online/api/generate with a one-page PDF
Result: 200
Job ID: 95a2f5c726f7
Final job status: completed
Job error: empty

GET /api/jobs/95a2f5c726f7/output
Result: 200
Markdown chars: 4703

GET /api/jobs/95a2f5c726f7/pdf-info
Result: 200
PDF page count: 1

GET /api/jobs/95a2f5c726f7/pdf-page/1.png
Result: 200
PNG bytes: 5591
```

## Public Access Finding

Direct public access from the local workstation to `http://43.157.84.138:8765/api/health` timed out even though Docker published `0.0.0.0:8765` and UFW was inactive. Container logs showed no request reaching the API container.

Likely cause: Tencent Cloud security group or public network path does not allow direct `8765` traffic.

Resolution: use Nginx on ports `80` and `443` with `jstudy.online`, proxying to `127.0.0.1:8765`. This is closer to the intended production shape and avoids opening an extra public port.

## Current Status

The backend is running on Tencent Cloud and has passed HTTPS domain smoke tests for:

- Docker Compose startup
- Postgres health
- FastAPI health/readiness
- SiliconFlow chat and embedding probe
- HTTP to HTTPS redirect
- Nginx reverse proxy
- Let's Encrypt TLS
- admin token enforcement
- invite-code creation
- user registration/session
- Secure HTTP-only session cookie
- PDF upload and generation
- output/PDF artifact retrieval

Frontend deployment remains pending. The current public domain serves the temporary backend UI and API directly.

## Follow-Up

Before broader external users test:

1. Add the formal frontend service.
2. Change Nginx routing so `/` points to frontend and `/api/*` plus `/admin/settings` point to the backend.
3. Keep `JSTUDY_COOKIE_SECURE=true`.
4. Re-run:

```bash
curl https://jstudy.online/api/health
curl https://jstudy.online/api/readiness
curl "https://jstudy.online/api/readiness?probe_provider=true"
```
