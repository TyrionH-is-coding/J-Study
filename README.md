# J-Study

J-Study is a multi-discipline study-material generation product. The current MVP starts with medicine because it is the first domain where we can validate quality, citation, and learning-output design with real domain judgment.

The product goal is not limited to medicine. The platform should eventually support different subject packs, each with its own prompts, retrieval strategy, output templates, quality checks, and question-generation logic.

Compared with DeepTutor's broader general-purpose direction, J-Study should build vertical depth through curated soul profiles and a reviewed knowledge snippet library. These libraries can start small while the backend, frontend, and deployment path are made reliable.

The product is not a generic PDF RAG assistant. Its core direction is
courseware-synchronized learning: the main material follows the
user-confirmed courseware and page order, while semantic retrieval only adds
optional relationships without controlling the reading sequence.

## Approved Refactor Direction

The bullets under `Current MVP` describe the implementation that exists today,
not the final parser architecture. The approved 2026-07-28 target is:

- MinerU Precision Extract cloud API for all product text/structure extraction
- no user-facing parser selection
- PyMuPDF retained only for PDF validation, metadata, and page preview rendering
- Tencent Cloud for Next.js, FastAPI, PostgreSQL, worker, and persistent storage
- the spare computer reserved as a future optional MinerU worker

The controlling design and migration gates are in:

- `docs/architecture/refactor-blueprint.md`
- `docs/superpowers/specs/2026-07-31-courseware-synchronized-learning-design.md`

## Current MVP

The current backend can:

- accept one courseware PDF and an optional outline
- accept `service_mode=course_outline` with a required outline and one or more repeated `pdfs` uploads
- expose public `scenario_id` and `parser_profile_id` options for the temporary upload UI
- extract page text with PyMuPDF
- use the `fast` parser profile as the public PyMuPDF path by default
- reserve a hidden/admin-only `quality` parser profile for a future MinerU-backed path
- require invite-gated email/password registration by default before users submit PDFs
- store user accounts, reusable invite codes, invite-code uses, and HTTP-only sessions in SQLModel-backed storage
- attach generated jobs to the owner user and block cross-user job access
- build RAG study queries from the uploaded PDF text and optional outline
- retrieve evidence chunks with embedding + BM25/RRF
- retrieve related knowledge snippets from the current legacy `mnemonics.md` prompt-rendered seed file
- generate strictly validated `material-package.v2` sections for both current service modes using the selected scenario's soul profile
- derive compatibility Markdown and its evidence links deterministically from the validated package instead of generating an independent Markdown response
- emit evidence links so the UI can jump from evidence ids to the correct source PDF page

This is still a single-server pilot architecture. PostgreSQL-backed Job records, an independent Worker, and `apps/web` now exist; object storage, versioned database migrations, and a production queue broker remain pending.

The PyMuPDF plus hybrid-retrieval bullets above describe current migration
behavior. They are not the target complete-material pipeline. Task 0008 will
connect MinerU to the real Worker path and make ordered learning units, coverage
and sequence-first generation the primary path. PyMuPDF remains installed for
validation and page preview only.

## Repository Status

The repository is moving from MVP files to a formal product structure.

Current important files:

```text
apps/api/jstudy_api/    FastAPI MVP service and temporary UI module
packages/core/          Pipeline orchestration, job lifecycle, output storage, runtime settings, CLI
packages/core/jstudy_core/admin_settings.py JSON-backed admin settings and knowledge-snippet rendering
packages/core/jstudy_core/auth_db.py SQLModel engine/session helpers for auth persistence
packages/core/jstudy_core/auth_models.py User, invite, invite-use, and session tables
packages/core/jstudy_core/auth_service.py Invite-gated auth and session service
packages/core/jstudy_core/citations.py Evidence item and citation-link contracts
packages/core/jstudy_core/cli.py Legacy CLI entrypoint implementation
packages/core/jstudy_core/jobs.py MVP job lifecycle store with JSON persistence
packages/core/jstudy_core/providers.py SiliconFlow chat and embedding client helpers
packages/core/jstudy_core/settings.py Runtime configuration helpers
packages/core/jstudy_core/storage.py Output path contracts and JSON helpers
packages/parsers/       MinerU compatibility adapter and legacy PyMuPDF text parser
packages/retrieval/     Current hybrid retrieval plus future auxiliary association search
packages/domains/       Medicine domain pack and future subject packs
web_mvp.py              Compatibility shim for the old Uvicorn entrypoint
mvp_runner.py           Compatibility shim for the old CLI entrypoint
soul.md                 Medicine default soul profile and study-material rules
mnemonics.md            Legacy prompt-rendered knowledge snippet seed file
data/settings/          Runtime admin settings, model catalog, and structured knowledge snippets (created at runtime)
rag-config.example.json Example RAG settings
tests/                  Current backend and rendering contract tests
docs/                   Product, architecture, roadmap, and development docs
```

Target structure:

```text
apps/
  api/                  FastAPI backend
  web/                  Next.js + shadcn/ui frontend
packages/
  core/                 Shared workflow orchestration, citations, result types
  parsers/              MinerU product parser; PyMuPDF PDF utilities only
  retrieval/            Auxiliary search, association, and snippet retrieval
  domains/
    medicine/           First subject pack
configs/
  rag/                  Runtime examples and safe defaults
deploy/
  docker-compose/       Single-server deployment assets
docs/
```

## Local Verification

Run from the repository root:

```powershell
python -m py_compile web_mvp.py mvp_runner.py apps/api/jstudy_api/app.py apps/api/jstudy_api/ui.py apps/api/jstudy_api/admin_ui.py packages/core/jstudy_core/admin_settings.py packages/core/jstudy_core/auth_db.py packages/core/jstudy_core/auth_models.py packages/core/jstudy_core/auth_service.py packages/core/jstudy_core/scenario_router.py packages/core/jstudy_core/parser_profile_router.py packages/core/jstudy_core/pipeline.py packages/core/jstudy_core/cli.py packages/core/jstudy_core/citations.py packages/core/jstudy_core/jobs.py packages/core/jstudy_core/providers.py packages/core/jstudy_core/settings.py packages/core/jstudy_core/storage.py packages/parsers/mineru_parser.py packages/parsers/pymupdf_parser.py
python -m unittest discover -s tests -v
```

Install backend dependencies:

```powershell
python -m pip install -r requirements.txt
```

Configure the API key with an environment variable:

```powershell
$env:SILICONFLOW_API_KEY="your-key"
```

For deployment, start from [.env.example](.env.example) and keep real secrets out of Git.
Operators can use `/admin/settings` to edit JSON-backed runtime settings instead of editing files by hand. Set `JSTUDY_ADMIN_TOKEN` in deployment; then open `/admin/settings?admin_token=...` or send `Authorization: Bearer ...`.
The admin settings directory defaults to `data/settings` and can be moved with `JSTUDY_SETTINGS_DIR`.
`JSTUDY_JOBS_DIR` is a fixed topology setting. Provider credential priority is one contract across readiness, API snapshots, Worker claims, and pipeline execution: nonempty `SILICONFLOW_API_KEY`, then nonempty `SILICONFLOW_API_KEY_FILE`, then the admin inline key, then the admin/default key file. Admin-managed values such as provider credentials, model selection, Soul/content paths, parser settings, `JSTUDY_MAX_PDF_BYTES`, and retention are loaded from shared `data/settings` when the corresponding process environment variable is empty. A nonempty environment value is an explicit deployment override and cannot be hot-updated through `/admin/settings`.
MinerU environment values are merged into the same parser snapshot used by API profile availability checks and Worker runner configuration. This configuration contract does not switch the current pipeline or parser default.
The API snapshots current settings for each new submission, and the worker snapshots them for each new claim; a running claim is not mutated midway. `JSTUDY_SOUL_PATH` is the compatibility fallback for the default active pack, while selected scenarios should normally resolve their own soul profile path from `content_pack.json`. `JSTUDY_MNEMONICS_PATH` remains the compatibility name for the prompt-rendered knowledge snippet file.
The application retention default is `0`, which disables cleanup. Public pilot `.env` files must keep `JSTUDY_JOB_RETENTION_HOURS=72` or another deliberate nonzero override so uploaded PDFs and generated artifacts do not accumulate indefinitely. Durable Job retention 由独立 worker 执行，API 不负责清理。
`JSTUDY_DATABASE_URL` controls Job and auth persistence and takes precedence over the legacy-compatible `DATABASE_URL`. It defaults to a local SQLite file in development; Docker Compose uses PostgreSQL.
Set `JSTUDY_SESSION_SECRET` before deployment. Use `JSTUDY_COOKIE_SECURE=true` when serving over HTTPS.
`JSTUDY_INVITE_REQUIRED` defaults to `true`. For small private tests only, set `JSTUDY_INVITE_REQUIRED=false` to allow registration without an invite code; set it back to `true` before broader public access.

Health check:

```text
GET /api/health
```

Readiness check for deploy-time configuration:

```text
GET /api/readiness
```

`/api/health` 是 liveness，只确认 API 进程存活。`/api/readiness` 是 readiness，检查 jobs directory、domain prompt files、API key、PDF upload limit 和数据库连接。
Use `/api/readiness?probe_provider=true` during deployment to run a live SiliconFlow chat and embedding connectivity probe.
`POST /api/generate` returns `503` with the readiness payload when required runtime configuration is missing.
`GET /api/options` currently returns public scenarios and parser profiles for
the temporary upload form. The approved product contract removes parser choice
from public options after the MinerU pipeline switch.
`POST /api/generate` accepts optional `scenario_id`, `parser_profile_id`, `mode`, and `service_mode` form fields. Missing scenario and parser values resolve to the admin-configured defaults. Empty `service_mode` or `single_courseware` keeps the existing `pdf=<one PDF>` path. `service_mode=course_outline` requires `outline=<.md/.txt/.pdf>` and at least one repeated `pdfs=<PDF>` upload. `mode` is stored as generation metadata for frontend experiments, but it does not replace service mode, subject scenario, or parser profile behavior. `scenario_id` resolves `content_pack_id`, `prompt_profile`, and the matching `soul_profile`, so different subjects can use different soul files without changing code.
`parser_profile_id=fast` currently maps to PyMuPDF and the reserved `quality`
profile currently maps to an incomplete MinerU compatibility adapter. New
product clients must not rely on these profiles. Task 0008 keeps only bounded
request compatibility while making MinerU the Worker-owned parser.
Job、source、section、artifact 和 transition 已由 SQLModel 持久化到 PostgreSQL；独立 `jstudy-worker` 通过 lease 认领并执行 queued Job，API 只负责 durable submission 和 owner-scoped read。旧 `jobs.json` 代码仍保留为 compatibility boundary，但 production API/worker 不 import 或写入它。
Completed jobs expose retrieval diagnostics at `/api/jobs/{job_id}/trace`, the owner-scoped and schema-validated `material-package.v2` payload at `/api/jobs/{job_id}/package`, and a deterministic compatibility Markdown attachment at `/api/jobs/{job_id}/export`. The package endpoint continues to read the bounded legacy v1 contract during migration. Source previews are available through the legacy first-source endpoints `/api/jobs/{job_id}/pdf-info` and `/api/jobs/{job_id}/pdf-page/{page}.png`, plus source-specific endpoints `/api/jobs/{job_id}/pdfs`, `/api/jobs/{job_id}/pdfs/{source_id}/pdf-info`, and `/api/jobs/{job_id}/pdfs/{source_id}/pdf-page/{page}.png`.

User auth:

```text
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET /api/auth/me
```

Registration requires a reusable invite code created from the admin settings page or invite-code API when `JSTUDY_INVITE_REQUIRED=true`.

Admin settings:

```text
GET /admin/settings
GET /api/admin/settings
PUT /api/admin/settings
POST /api/admin/settings/test/{llm|embedding|search}
GET /api/admin/invite-codes
POST /api/admin/invite-codes
PATCH /api/admin/invite-codes/{invite_id}
GET /api/admin/invite-codes/{invite_id}/uses
```

The first admin settings version stores model catalog, RAG settings, web-search settings, parser settings, parser-profile visibility, content-pack scenarios, soul profiles, content paths, and the current compatibility file `mnemonics.json`. Structured knowledge snippet JSON is rendered back to Markdown for the existing prompt flow.

The default soul library includes the active `medicine-default` profile plus disabled blank placeholders for general, engineering, and law scenarios. Users choose scenarios from the upload page; admins control which scenarios are visible by enabling or disabling scenario entries. Blank placeholder profiles must receive a real `soul_path` before the scenario is exposed.

Knowledge snippets are the long-term replacement for the narrower memory-aid library. The safe product direction is a feedback loop: users can later select and like high-quality generated fragments, the backend stores those fragments as admin-visible candidates, semantic deduplication clusters similar fragments, and only reviewed snippets can enter the approved library. Approved snippets may improve structure, wording, and recall, but they must not become independent fact sources unless the current upload also provides supporting evidence.

Uploaded PDFs are stored locally during the pilot because the source preview and citation jumps need the original file. When J-Study needs persistent user history, course libraries, or formal multi-user accounts, move uploaded PDFs and generated artifacts to object storage such as Tencent COS and keep metadata in a database.

Run the current MVP service with the compatibility entrypoint:

```powershell
python -m uvicorn web_mvp:app --host 127.0.0.1 --port 8765
```

Or with the canonical backend entrypoint:

```powershell
python -m uvicorn apps.api.jstudy_api.app:app --host 127.0.0.1 --port 8765
```

Then open:

```text
http://127.0.0.1:8765/
```

Backend Docker Compose 三服务拓扑包含 `postgres`、`jstudy-api` 和 `jstudy-worker`。API 与 worker 共享数据库、jobs volume 和运行设置；worker 不暴露端口：

```powershell
docker compose -f deploy/docker-compose/api.compose.yml config
docker compose -f deploy/docker-compose/api.compose.yml up -d --build
docker compose -f deploy/docker-compose/api.compose.yml logs -f
docker compose -f deploy/docker-compose/api.compose.yml down
```

当前 SQLModel `create_all()` 只允许用于数据可丢弃的 disposable pilot。开始保存持久用户数据前，必须采用 versioned migrations，并准备迁移、回滚、备份和恢复 runbook。详细操作见 [Docker Compose 运行手册](deploy/docker-compose/README.md)。

## Key Documents

- [Product Vision](docs/product/vision.md)
- [Architecture Overview](docs/architecture/overview.md)
- [Roadmap](docs/roadmap.md)
- [Development Standards](docs/development/standards.md)
- [Git Workflow](docs/development/git-workflow.md)
- [User Auth and Invite Design](docs/superpowers/specs/2026-06-15-user-auth-invite-design.md)
- [Snippet Feedback Loop Design](docs/superpowers/specs/2026-06-15-snippet-feedback-loop-design.md)
- [Backend Security Validation](docs/security/backend-security-validation.md)
- [Frontend Dependency Risk Register](docs/security/frontend-dependency-risk-register.md)
- [Server Deployment Runbook](docs/deployment/server-runbook.md)
- [Tencent Cloud Backend Trial Deployment](docs/deployment/tencent-cloud-trial-2026-06-15.md)

Historical MVP notes are kept under `docs/archive/`.
