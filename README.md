# J-Study

J-Study is a multi-discipline study-material generation product. The current MVP starts with medicine because it is the first domain where we can validate quality, citation, and learning-output design with real domain judgment.

The product goal is not limited to medicine. The platform should eventually support different subject packs, each with its own prompts, retrieval strategy, output templates, quality checks, and question-generation logic.

## Current MVP

The current backend can:

- accept one courseware PDF and an optional outline
- expose public `scenario_id` and `parser_profile_id` options for the temporary upload UI
- extract page text with PyMuPDF
- use the `fast` parser profile as the public PyMuPDF path by default
- reserve a hidden/admin-only `quality` parser profile for a future MinerU-backed path
- require invite-gated email/password registration before users submit PDFs
- store user accounts, reusable invite codes, invite-code uses, and HTTP-only sessions in SQLModel-backed storage
- attach generated jobs to the owner user and block cross-user job access
- retrieve evidence chunks with embedding + BM25/RRF
- retrieve related mnemonics from `mnemonics.md`
- generate Markdown study material using `soul.md`
- emit evidence links so the UI can jump from "依据 E001" to the original PDF page

This is still a single-machine MVP. It does not yet include object storage, a production task queue, database-backed job records, or a separate frontend app.

## Repository Status

The repository is moving from MVP files to a formal product structure.

Current important files:

```text
apps/api/jstudy_api/    FastAPI MVP service and temporary UI module
packages/core/          Pipeline orchestration, job lifecycle, output storage, runtime settings, CLI
packages/core/jstudy_core/admin_settings.py JSON-backed admin settings and mnemonic rendering
packages/core/jstudy_core/auth_db.py SQLModel engine/session helpers for auth persistence
packages/core/jstudy_core/auth_models.py User, invite, invite-use, and session tables
packages/core/jstudy_core/auth_service.py Invite-gated auth and session service
packages/core/jstudy_core/citations.py Evidence item and citation-link contracts
packages/core/jstudy_core/cli.py Legacy CLI entrypoint implementation
packages/core/jstudy_core/jobs.py MVP job lifecycle store with JSON persistence
packages/core/jstudy_core/providers.py SiliconFlow chat and embedding client helpers
packages/core/jstudy_core/settings.py Runtime configuration helpers
packages/core/jstudy_core/storage.py Output path contracts and JSON helpers
packages/parsers/       PyMuPDF parser implementation
packages/retrieval/     Chunking, BM25/RRF, retrieval adapter
packages/domains/       Medicine domain pack and future subject packs
web_mvp.py              Compatibility shim for the old Uvicorn entrypoint
mvp_runner.py           Compatibility shim for the old CLI entrypoint
soul.md                 Medicine output style and study-material template
mnemonics.md            Medicine mnemonic seed library rendered for prompts
data/settings/          Runtime admin settings, model catalog, and structured mnemonics (created at runtime)
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
  parsers/              PyMuPDF default parser, future MinerU parser
  retrieval/            Chunking, embedding, BM25/RRF, RAG adapter
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
`JSTUDY_JOBS_DIR`, `JSTUDY_SOUL_PATH`, and `JSTUDY_MNEMONICS_PATH` can be used to move runtime data and domain templates outside the repository in Docker or on a server.
`JSTUDY_MAX_PDF_BYTES` controls the upload limit for courseware PDFs; the default is 50 MB.
`JSTUDY_JOB_RETENTION_HOURS` is optional. The application default is `0`, which disables cleanup, but public pilot deployments should set `72` or `168` so uploaded PDFs and generated artifacts do not accumulate indefinitely.
`DATABASE_URL` controls auth persistence. It defaults to a local SQLite file in development; Docker Compose uses Postgres.
Set `JSTUDY_SESSION_SECRET` before deployment. Use `JSTUDY_COOKIE_SECURE=true` when serving over HTTPS.

Health check:

```text
GET /api/health
```

Readiness check for deploy-time configuration:

```text
GET /api/readiness
```

`/api/health` only confirms the API process is alive. `/api/readiness` checks the jobs directory, domain prompt files, API key source, and PDF upload limit.
Use `/api/readiness?probe_provider=true` during deployment to run a live SiliconFlow chat and embedding connectivity probe.
`POST /api/generate` returns `503` with the readiness payload when required runtime configuration is missing.
`GET /api/options` returns public scenarios and parser profiles for the upload form.
`POST /api/generate` accepts optional `scenario_id` and `parser_profile_id` form fields. Missing values resolve to the admin-configured defaults.
`parser_profile_id=fast` maps to PyMuPDF. The reserved `quality` profile maps to MinerU, is hidden from normal users at first, and should be enabled only after MinerU is configured.
Job status is persisted in `JSTUDY_JOBS_DIR/jobs.json`; jobs that were queued or running during a server restart are marked failed because the MVP has no separate worker queue yet.
Completed jobs expose retrieval diagnostics at `/api/jobs/{job_id}/trace`.

User auth:

```text
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET /api/auth/me
```

Registration requires a reusable invite code created from the admin settings page or invite-code API.

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

The first admin settings version stores model catalog, RAG settings, web-search settings, parser settings, parser-profile visibility, content-pack scenarios and paths, and `mnemonics.json`. Structured mnemonic JSON is rendered back to Markdown for the existing prompt flow.

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

Backend Docker Compose scaffold with Postgres:

```powershell
docker compose -f deploy/docker-compose/api.compose.yml config
docker compose -f deploy/docker-compose/api.compose.yml up -d --build
```

## Key Documents

- [Product Vision](docs/product/vision.md)
- [Architecture Overview](docs/architecture/overview.md)
- [Roadmap](docs/roadmap.md)
- [Development Standards](docs/development/standards.md)
- [Git Workflow](docs/development/git-workflow.md)
- [User Auth and Invite Design](docs/superpowers/specs/2026-06-15-user-auth-invite-design.md)
- [Backend Security Validation](docs/security/backend-security-validation.md)
- [Server Deployment Runbook](docs/deployment/server-runbook.md)
- [Tencent Cloud Backend Trial Deployment](docs/deployment/tencent-cloud-trial-2026-06-15.md)

Historical MVP notes are kept under `docs/archive/`.
