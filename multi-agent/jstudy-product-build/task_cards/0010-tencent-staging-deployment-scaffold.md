# Task 0010: Tencent Staging Deployment Scaffold

## Supervisor

- Product/Supervisor source task: `019ed023-8e41-7ad0-8117-6246b8ffa0bb`
- Dispatching task: `019fa956-f165-76b0-b49d-9462d2f52328`
- Assigned Code Agent: `019efec4-1e17-7443-8496-c1fea5d6bcb5`

## Required Baseline

- Repository: `D:\大二下\deep tutor\J-Study`
- Branch: `feature/backend-frontend-mvp`
- Required start SHA: the commit containing this task card and plan
- Pushed backend checkpoint before this task: `f684fdc8e50e99eca9b73883991950a804a24b44`
- Start PowerShell sessions with:

```powershell
. "$env:USERPROFILE\.codex\scripts\Enter-CodexUtf8.ps1"
```

Record exact start SHA and protected status before edits. Do not reset, clean,
rebase, merge, push, or touch protected content.

## Goal

Parameterize the existing PostgreSQL + FastAPI + Worker Compose file so an
isolated staging stack can coexist with the old Tencent Cloud deployment while
preserving all current defaults.

## Authoritative Plan

`docs/superpowers/plans/2026-08-03-tencent-staging-deployment.md`

Use test-driven development and implement the plan task by task. Keep this a
deployment-scaffold change; do not modify product behavior.

## Required Contract

Add environment interpolation with these defaults:

| Variable | Default |
|---|---|
| `JSTUDY_IMAGE_NAME` | `jstudy-backend:pilot` |
| `JSTUDY_API_CONTAINER_NAME` | `jstudy-api` |
| `JSTUDY_WORKER_CONTAINER_NAME` | `jstudy-worker` |
| `JSTUDY_POSTGRES_CONTAINER_NAME` | `jstudy-postgres` |
| `JSTUDY_API_BIND_ADDRESS` | `0.0.0.0` |
| `JSTUDY_API_PORT` | `8765` |

The staging example and tests must prove:

```text
image=jstudy-backend:staging-test
api container=jstudy-staging-api
worker container=jstudy-staging-worker
postgres container=jstudy-staging-postgres
published API=127.0.0.1:8766
services=postgres,jstudy-api,jstudy-worker
```

Do not change service names, internal port `8765`, relative data mounts,
database hostname `postgres`, healthcheck, Worker command, provider precedence,
or current default behavior.

## Allowed Scope

- `.env.example`
- `deploy/docker-compose/api.compose.yml`
- `deploy/docker-compose/README.md`
- `docs/deployment/server-runbook.md`
- `tests/test_deployment_files.py`
- `multi-agent/jstudy-product-build/reports/0010-tencent-staging-deployment-report.md`

If another file is required, stop and report why before editing it.

## Forbidden Scope

- `apps/**`
- `packages/**`
- all product API, Worker, pipeline, database schema, frontend, auth, and model behavior
- `data/**`
- Nginx, Cloudflare, DNS, Tencent Cloud, local or server `.env`
- any credential file or token
- live MinerU/SiliconFlow calls
- old `/opt/jstudy/app` deployment

Protected workspace content:

- `multi-agent/jstudy-product-build/reports/supervisor_review.md`
- `.superpowers/`
- `frontend/`
- `game/`
- `images/`
- `outline_mode/`
- `scripts/`

## Acceptance Criteria

1. Existing no-env Compose configuration preserves all old defaults.
2. Staging env values produce isolated image/container names and loopback port.
3. API and Worker still share settings/jobs/database configuration.
4. Compose services remain exactly PostgreSQL + API + Worker.
5. Documentation contains startup, status, logs, acceptance, backup, rollback,
   and explicit no-secret/no-`down -v` boundaries.
6. No secret, upload, runtime data, database, or protected path is committed.
7. Full backend regression remains green.

## Required Verification

```powershell
python -m unittest tests.test_deployment_files -v
python -m compileall -q apps packages
python -m unittest discover -s tests -v
docker compose -f deploy/docker-compose/api.compose.yml config --services
git diff --check
git status --short
```

Frontend tests are not required because `apps/web/**` is forbidden and the
runtime application contract does not change.

## Required Report

Return:

1. exact branch, start SHA, final SHA;
2. focused RED/GREEN evidence;
3. exact changed files;
4. full verification output and counts;
5. residual risks;
6. confirmation that no remote system or credential was touched;
7. requested Supervisor verdict:
   `PASS` / `PASS_WITH_LIMITATIONS` / `REVISE` / `REJECT`.
