# J-Study

J-Study is a multi-discipline study-material generation product. Medicine was
the first domain used to validate quality, citation, and learning-output design.
The approved product default is General Mode; the current runtime must keep
Medicine active until a real `general-default` Soul Profile replaces the blank
placeholder.

The product goal is not limited to medicine. The platform should eventually support different subject packs, each with its own prompts, retrieval strategy, output templates, quality checks, and question-generation logic.

Compared with DeepTutor's broader general-purpose direction, J-Study should build vertical depth through curated soul profiles and a reviewed knowledge snippet library. These libraries can start small while the backend, frontend, and deployment path are made reliable.

The product is not a generic PDF RAG assistant. Its core direction is
courseware-synchronized learning: the main material follows the
user-confirmed courseware and page order, while semantic retrieval only adds
optional relationships without controlling the reading sequence.

Permanent documentation starts at `docs/README.md`. Product mode contracts are
maintained in `docs/product/service-modes.md`; task cards and Agent reports are
delivery evidence rather than product truth.

## Approved Refactor Direction

Task 0008 与 0009 已实现 2026-07-28 解析器和 sequence-first 架构的首批
后端切片：

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

- `service_mode=single_courseware` 只接受一个 singular `pdf`，不接受
  outline 或 repeated `pdfs`
- `service_mode=course_outline` 接受一个必需 outline 和至少一个 repeated
  `pdfs`
- `service_mode=multi_courseware` 接受至少两个 repeated `pdfs`，不接受
  outline 或 singular `pdf`
- expose public subject scenarios without exposing parser choices
- batch-parse all Job sources through MinerU Precision Extract and normalize them to versioned `ParsedDocument` contracts
- retain PyMuPDF only for PDF validation, page count, metadata, and source preview rendering
- accept only empty, `fast`, and `quality` as bounded legacy request aliases; the Worker always owns the MinerU parser choice
- require invite-gated email/password registration by default before users submit PDFs
- store user accounts, reusable invite codes, invite-code uses, and HTTP-only sessions in SQLModel-backed storage
- attach generated jobs to the owner user and block cross-user job access
- freeze source identity, display metadata, and outline mapping in `courseware-manifest.v1`
- plan ordered continuous units in `learning-map.v1` and record every normalized block in `coverage-ledger.v1`
- generate complete materials in learning-map order; embedding/BM25 relevance does not control the primary sequence
- retrieve related knowledge snippets from the current legacy `mnemonics.md` prompt-rendered seed file
- 三种 service mode 均使用所选 scenario 的 Soul Profile 生成严格校验的
  `material-package.v2` sections
- derive compatibility Markdown and its evidence links deterministically from the validated package instead of generating an independent Markdown response
- emit evidence links so the UI can jump from evidence ids to the correct source PDF page

This is still a single-server pilot architecture. PostgreSQL-backed Job records, an independent Worker, and `apps/web` now exist; object storage, versioned database migrations, and a production queue broker remain pending.

MinerU failures remain typed Worker failures; there is no silent fallback to
PyMuPDF text extraction. Tests use mocked MinerU transport and do not constitute
a live provider smoke test.

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
MinerU environment values are merged into the immutable settings snapshot used
for each Worker claim and its MinerU client. Empty environment values fall back
to admin settings; nonempty environment values remain explicit process
overrides.
The API snapshots current settings for each new submission, and the worker snapshots them for each new claim; a running claim is not mutated midway. `JSTUDY_SOUL_PATH` is the compatibility fallback for the default active pack, while selected scenarios should normally resolve their own soul profile path from `content_pack.json`. `JSTUDY_MNEMONICS_PATH` remains the compatibility name for the prompt-rendered knowledge snippet file.
The application retention default is `0`, which disables cleanup. Public pilot `.env` files must keep `JSTUDY_JOB_RETENTION_HOURS=72` or another deliberate nonzero override so uploaded PDFs and generated artifacts do not accumulate indefinitely. Durable Job retention 由独立 worker 执行，API 不负责清理。
`JSTUDY_GENERATION_MAX_CONCURRENCY` 控制单个 Job 的独立章节模型调用上限，
合法范围为 `1..4`，默认值 `4`；设为 `1` 是不改内容合同的串行回滚方式。
单 Worker 的活动调用上限为该值；多个 Worker 副本的总上限为该值乘以
副本数，扩容前必须核算 Provider 限流。
确定性测试只证明调度合同；仍须由 Supervisor 对真实 6 页样本复验中位数
不超过 25 秒、任一单次不超过 35 秒，才能通过产品延迟门禁。
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
`GET /api/options` returns public scenarios only. New clients omit
`parser_profile_id`; empty, `fast`, and `quality` remain bounded migration
aliases, while unknown values are rejected and no alias changes the
Worker-owned MinerU parser.
`POST /api/generate` 接受可选 `scenario_id`、legacy
`parser_profile_id`、仅作为 metadata 的 `mode` 和 `service_mode`。
空 `service_mode` 或 `single_courseware` 要求恰好一个 singular
`pdf=<PDF>`；`course_outline` 要求一个
`outline=<.md/.txt/.pdf>` 和至少一个 repeated `pdfs=<PDF>`；
`multi_courseware` 要求至少两个 repeated `pdfs=<PDF>`。三种 multipart
shape 互斥，非法组合不会创建 Job。`scenario_id` 解析
`content_pack_id`、`prompt_profile` 和对应 `soul_profile`。
Job、source、section、artifact 和 transition 已由 SQLModel 持久化到 PostgreSQL；独立 `jstudy-worker` 通过 lease 认领并执行 queued Job，API 只负责 durable submission 和 owner-scoped read。旧 `jobs.json` 代码仍保留为 compatibility boundary，但 production API/worker 不 import 或写入它。
Completed jobs expose owner-scoped, bounded, strictly validated synchronization artifacts at `/api/jobs/{job_id}/manifest`, `/api/jobs/{job_id}/learning-map`, and `/api/jobs/{job_id}/coverage`, plus retrieval diagnostics at `/api/jobs/{job_id}/trace`, `material-package.v2` at `/api/jobs/{job_id}/package`, and deterministic compatibility Markdown at `/api/jobs/{job_id}/export`. Source lists include `source_id`, `original_filename`, `display_title`, and `display_order`. Source previews remain available through the legacy first-source aliases and source-specific `/api/jobs/{job_id}/pdfs/{source_id}/...` endpoints.

Multi Courseware 当前按稳定 `display_order` 复用同一 sequence-first 路径，
不会拆成多个独立单 PDF Job。跨课件关联发现、评分、生成和 UI 仍处于实验
决策阶段，当前未实现。

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
