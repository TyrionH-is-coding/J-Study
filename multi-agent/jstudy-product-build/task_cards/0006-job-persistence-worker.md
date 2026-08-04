# Task Card: PostgreSQL Job Persistence and Separate Worker

## Supervisor Thread

`019ed023-8e41-7ad0-8117-6246b8ffa0bb`

## Code Agent Thread

`019efec4-1e17-7443-8496-c1fea5d6bcb5`

## Baseline

Expected branch:

```text
feature/backend-frontend-mvp
```

Required baseline commit:

```text
b271e38
```

Commit subject:

```text
文档：确定 JSON 到 HTML 的资料渲染架构
```

Before editing, record:

```powershell
. "$env:USERPROFILE\.codex\scripts\Enter-CodexUtf8.ps1"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
git status --short --branch
git rev-parse HEAD
git log -1 --oneline
```

The known working tree contains a Supervisor-owned tracked modification:

```text
multi-agent/jstudy-product-build/reports/supervisor_review.md
```

Do not modify, stage, restore, or commit that file.

Known unrelated untracked directories:

```text
.superpowers/
frontend/
game/
images/
outline_mode/
scripts/
```

Do not modify, stage, delete, clean, or commit them.

If the actual baseline differs materially, stop before implementation and
report the difference.

## Goal

Replace the production `jobs.json` and FastAPI in-process `BackgroundTasks`
execution path with:

1. an explicit, tested job state machine;
2. SQLModel/PostgreSQL job/source/section/artifact/transition persistence;
3. atomic worker claims with leases and bounded retries;
4. a separately runnable worker process;
5. durable owner-scoped API polling and artifact access;
6. upload admission limits and optional idempotent submission;
7. an API + worker + PostgreSQL Compose topology.

Preserve the current FastAPI contract, current frontend behavior, current
Markdown output, current material package version, and current parser behavior.

## Required Plan

Read and execute the implementation plan in order:

```text
multi-agent/jstudy-product-build/reports/0006-job-persistence-worker-plan.md
```

Also read before editing:

```text
docs/architecture/refactor-blueprint.md
docs/architecture/material-package-html-rendering.md
docs/architecture/overview.md
docs/frontend/clinical-workbench-spec.md
multi-agent/jstudy-product-build/shared/project_context.md
multi-agent/jstudy-product-build/shared/repo_rules.md
multi-agent/jstudy-product-build/coordination/output_contract.md
```

Write a short Phase 0 inventory before code:

```text
multi-agent/jstudy-product-build/reports/0006-baseline-inventory.md
```

It must record the actual branch/SHA, working-tree exclusions, current test
baseline, planned files, and any variance from this task card.

## Execution Method

- Execute the plan phase by phase.
- Use test-driven development for each behavior change.
- Run the focused RED test before implementing.
- Make the minimum implementation required to make it pass.
- Re-run focused tests after each phase.
- Do not broaden the task when adjacent cleanup becomes visible.
- Use explicit UTF-8 PowerShell reads/writes and preserve
  `PYTHONUTF8=1`/`PYTHONIOENCODING=utf-8`.
- Use Chinese README/documentation additions and Chinese commit messages.

You may create checkpoint commits after coherent passing phases. Do not push,
merge, rebase, reset, clean, tag, or deploy.

## Required State Contract

Persist these canonical internal states:

```text
queued
parsing
retrieving
generating
packaging
completed
failed
cancelled
```

Keep the frontend-facing compatibility `status`:

```text
queued
running
completed
failed
```

The response may add `state`, `stage`, `progress`, `attempt_count`, and
`error_code`. Do not expose lease owner, server paths, raw traces, provider
secrets, or internal exception details.

## Required Database Contract

Persist:

```text
jobs
job_sources
job_sections
job_artifacts
job_transitions
```

Required guarantees:

- owner-scoped reads;
- stable `source_id`;
- append-only transition history;
- atomic claim;
- bounded lease recovery;
- artifact metadata;
- retention selection;
- owner-scoped idempotency key;
- safe relative filesystem paths.

Production uses PostgreSQL. File-backed SQLite remains supported for tests. Do
not add Redis, Celery, or another queue service.

## Required API Behavior

`POST /api/generate` must:

1. authenticate;
2. validate service-mode fields and upload limits;
3. stream files into a job-owned temporary directory;
4. compute source/outline hashes;
5. enforce queue/user limits;
6. enforce optional `Idempotency-Key`;
7. persist a queued job;
8. return without running generation.

The production FastAPI process must not call the runner or register generation
through `BackgroundTasks`.

Existing routes and owner checks remain compatible, including:

```text
/api/jobs/{job_id}
/api/jobs/{job_id}/output
/api/jobs/{job_id}/package
/api/jobs/{job_id}/export
/api/jobs/{job_id}/evidence
/api/jobs/{job_id}/evidence-links
/api/jobs/{job_id}/trace
/api/jobs/{job_id}/pdf
/api/jobs/{job_id}/pdf-info
/api/jobs/{job_id}/pdf-page/{page_no}.png
/api/jobs/{job_id}/pdfs
/api/jobs/{job_id}/pdfs/{source_id}/pdf
/api/jobs/{job_id}/pdfs/{source_id}/pdf-info
/api/jobs/{job_id}/pdfs/{source_id}/pdf-page/{page_no}.png
```

An unknown job and a foreign-owned job must remain indistinguishable.

## Required Worker Behavior

Provide:

```powershell
python -m apps.worker.main
```

The worker must:

- recover expired leases;
- atomically claim one queued job;
- use current `service_mode` to invoke the existing runner;
- record parsing/retrieving/generating/packaging progress;
- renew the lease;
- record output artifacts;
- complete, retry, fail, or cancel through the state machine;
- perform bounded retention cleanup;
- process one job at a time in the first version.

Tests must prove that two worker instances cannot both claim the same job.

## Required Admission Limits

Add typed environment-backed limits with the exact pilot defaults from the
implementation plan:

- maximum PDF count;
- maximum bytes per PDF;
- maximum total upload bytes;
- maximum outline bytes;
- queue capacity;
- per-user active-job limit;
- worker polling interval;
- lease duration;
- maximum attempts.

Validate PDF MIME/magic using the existing PDF utility boundary. Do not trust
the browser filename alone.

## Required E2E Topology

Update the existing Playwright backend support to run a real API plus a real
worker loop against a temporary SQL database and jobs root. The runner may
remain deterministic, but the API must not execute it inline.

All current browser flows and viewport assertions must continue to pass.

## Required Compose Topology

Update the pilot Compose stack to:

```text
postgres
jstudy-api
jstudy-worker
```

API and worker share the database and jobs volume. The worker exposes no public
port.

Document that SQLModel `create_all()` is acceptable only while pilot data is
disposable. A versioned migration system remains a required deployment task
before production data becomes durable.

## Allowed Scope

Implementation:

```text
apps/api/jstudy_api/app.py
apps/worker/**
apps/web/e2e/support/serve_backend.py
packages/core/jstudy_core/job_system/**
packages/core/jstudy_core/auth_db.py
packages/core/jstudy_core/jobs.py
packages/core/jstudy_core/pipeline.py
packages/core/jstudy_core/settings.py
packages/core/jstudy_core/storage.py
tests/test_job_states.py
tests/test_job_repository.py
tests/test_job_service.py
tests/test_job_worker.py
tests/test_web_mvp.py
tests/test_security_controls.py
tests/test_mvp_runner.py
deploy/docker-compose/api.compose.yml
deploy/docker-compose/README.md
README.md
docs/architecture/overview.md
docs/roadmap.md
multi-agent/jstudy-product-build/reports/0006-*.md
```

Dependency files may change only if the existing installed dependencies cannot
implement the required behavior.

## Explicitly Excluded

Do not:

- implement HTML output or `material-package.v2`;
- remove Markdown output;
- switch either pipeline to MinerU;
- remove PyMuPDF compatibility code;
- change parser profiles or parser defaults;
- redesign retrieval, generation, citation, Soul Profile, or snippet logic;
- redesign the frontend;
- add Batch Courseware;
- change login/invite product policy;
- add Redis, Celery, Kafka, or a plugin framework;
- deploy to Tencent Cloud or change Cloudflare/domain configuration;
- commit secrets, `.env` files, databases, uploads, generated artifacts, or
  runtime `data/`;
- delete the legacy JSON JobStore without an explicit final deletion review.

## Verification

Focused tests must be reported phase by phase.

Final backend:

```powershell
python -m compileall -q apps packages
python -m unittest discover -s tests -v
```

Final frontend from `apps/web`:

```powershell
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
```

Repository:

```powershell
git diff --check
git status --short
git diff --stat b271e38
```

Do not weaken or delete tests to obtain a pass.

## Required Report

Create:

```text
multi-agent/jstudy-product-build/reports/0006-job-persistence-worker-report.md
```

Use the standard sections:

1. Task
2. Summary
3. Changed Files
4. Verification
5. Risks and Limitations
6. Requested Supervisor Action

Include:

- baseline and final SHA;
- exact test counts;
- state and transition contract;
- SQL tables and ownership guarantees;
- claim/lease/retry behavior;
- API compatibility;
- E2E topology;
- Compose commands;
- legacy JSON store status;
- any deferred schema migration work;
- skipped/excluded items.

Request one verdict:

```text
PASS
PASS_WITH_LIMITATIONS
REVISE
REJECT
```

## Acceptance Gate

Request review only when:

1. production FastAPI no longer executes jobs in-process;
2. a separately runnable worker supports both current service modes;
3. queued jobs persist across restart;
4. atomic claim and stale-lease tests pass;
5. every transition uses the central state machine;
6. owner isolation still covers all job artifacts and source previews;
7. limits and idempotency tests pass;
8. existing frontend contract remains compatible;
9. backend and frontend full suites pass;
10. Compose contains PostgreSQL, API, worker, and shared storage;
11. no HTML or MinerU pipeline switch entered this task;
12. excluded and Supervisor-owned files remain untouched.
