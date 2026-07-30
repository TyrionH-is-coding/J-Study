# Architecture Overview

## Summary

J-Study is a single-server MVP that should evolve into a formally structured product. The current backend now has canonical package paths: `apps/api/jstudy_api/app.py` serves the FastAPI MVP, `apps/api/jstudy_api/ui.py` owns the temporary built-in user UI, `apps/api/jstudy_api/admin_ui.py` owns the temporary backend-served admin settings page, `packages/core/jstudy_core/pipeline.py` orchestrates the generation pipeline, `packages/core/jstudy_core/cli.py` owns the legacy CLI entrypoint implementation, `packages/core/jstudy_core/admin_settings.py` owns JSON-backed runtime admin settings, `packages/core/jstudy_core/scenario_router.py` owns learning-scenario resolution, `packages/core/jstudy_core/parser_profile_router.py` owns user-facing parser-profile resolution, `packages/core/jstudy_core/citations.py` owns evidence and citation-link contracts, `packages/core/jstudy_core/jobs.py` owns the MVP job lifecycle and JSON persistence, `packages/core/jstudy_core/providers.py` owns SiliconFlow-compatible chat and embedding calls, `packages/core/jstudy_core/settings.py` owns runtime resolution and deployment overrides, `packages/core/jstudy_core/storage.py` owns local output file contracts, `packages/parsers` owns document parsing, `packages/retrieval` owns chunking and hybrid retrieval, and `packages/domains/medicine.py` owns the first subject pack. Root-level `web_mvp.py` and `mvp_runner.py` remain compatibility shims for old commands.

The architecture should support vertical depth rather than only broad generality. DeepTutor is the reference for mature RAG and configuration patterns, but J-Study's quality advantage should come from subject-specific soul profiles and a reviewed knowledge snippet ecosystem. Those libraries can stay thin while the service is being made deployable; the architecture must make them easy to expand later without rewriting the platform.

## Target Repository Structure

```text
apps/
  api/
    # FastAPI service, upload endpoints, job status, result APIs
  web/
    # Next.js + shadcn/ui frontend
packages/
  core/
    # workflow contracts, job models, citations, output result types
  parsers/
    # MinerU product parser; PyMuPDF PDF utility
  retrieval/
    # chunking, BM25/RRF, RAG adapters
  domains/
    medicine/
      # first subject pack
configs/
  rag/
deploy/
  docker-compose/
docs/
```

The first backend reorganization steps are implemented. Further steps should split runtime settings, job state, storage, and provider calls without changing API behavior.

## Runtime Flow

```text
Upload single PDF or course outline + multiple PDFs + optional scenario
-> scenario and soul profile resolution
-> selected parser profile, with PyMuPDF still the public default
-> chunks with page metadata
-> source/outline-driven retrieval query planner
-> embedding + lexical retrieval
-> evidence selection
-> approved knowledge snippet retrieval
-> structured section generation with at most one format repair
-> validated material-package.v2 blocks and citation runs
-> direct package quality audit
-> deterministic compatibility Markdown + evidence links
-> frontend reader with source-page citation jumps
```

## Service Mode Architecture

The platform should distinguish service mode from subject scenario and internal
parser infrastructure.

- `single_courseware`: one PDF, optional outline, one generated material output. This remains the compatible default MVP path.
- `batch_courseware`: multiple PDFs, optional user notes or loose outline, one material package. The web app should browse the package by chapter or topic and should also export the complete package as one document.
- `course_outline`: course outline plus all courseware for a full course, one material package. The backend contract is implemented with required outline upload, repeated `pdfs`, source identities such as `S001`, and section package metadata. The formal `apps/web` workflow now covers upload, polling, section browsing, source-specific page preview, citation jump, and full Markdown export.

The two currently implemented service modes now use the same v2 package-output contract. Batch Courseware remains pending:

```text
material-package.v2
-> sections[]
   -> stable section id, title, order, and status
   -> source_ids and evidence_ids
   -> typed blocks and structural citation runs
   -> direct evidence quality metrics
-> deterministic compatibility Markdown assembled from sections
```

The difference is planning. Batch Courseware Mode can derive sections from uploaded file order, detected headings, or inferred topics. Course Outline Mode follows the uploaded outline first and marks sections with weak evidence in the package instead of silently inventing support.

## Platform Layer

The platform layer should own common product behavior:

- file upload
- job lifecycle
- learning-scenario resolution
- document parsing orchestration
- parser provider configuration
- retrieval execution
- evidence link contracts
- output storage
- service mode routing
- material package and section-output contracts
- API response shape
- deployment and runtime configuration

It should not own medicine-specific prompt wording, knowledge-snippet rules, or subject quality standards.

The platform should expose stable routing hooks for vertical assets. A new subject should mainly add or enable a scenario, a soul profile, approved snippets, and optional domain code; it should not require changes to upload, job, parser, retrieval, or deployment infrastructure.

## Document Parser Boundary

The approved target uses MinerU for all product text and structure extraction.
Users do not select a parser or parser tier. The current PyMuPDF extraction path
is a temporary migration implementation, not the target product contract.

MinerU output must be normalized into the versioned J-Study document contract
before retrieval. The contract preserves:

- stable J-Study `source_id`
- source filename and SHA256
- one-based source page number
- text and Markdown
- ordered typed blocks
- tables, formulas, image references, and bounding boxes when available
- parser/model/version metadata and safe warnings

PyMuPDF remains an internal utility for:

- PDF magic and corruption validation
- page count and page metadata
- page PNG rendering for source preview
- validation of MinerU page references

There is no automatic difficulty score and no silent fallback from MinerU to
PyMuPDF text extraction. MinerU failure produces a stable job error and an
explicit retry path.

The full migration design is defined in
`docs/architecture/refactor-blueprint.md`.

## Retrieval Layer

The current MVP retrieval approach is:

- page-aware chunking
- deterministic query planning from the current PDF text and optional outline
- embedding similarity
- BM25-style lexical matching
- reciprocal-rank fusion
- low-value chunk filtering
- per-query evidence limits

This lives in `packages/retrieval/` so it can be reused across domains.

The query planner must not default to a fixed lecture topic. The earliest cocci-specific MVP queries have been removed from the default path; subject-specific query lists belong in explicit scenarios or domain profiles, not in the medicine default.

## Domain Layer

Domain packs should define subject-specific behavior. The first pack is `medicine`.

Expected domain-pack responsibilities:

- query planning
- soul profile and prompt template
- output style rules
- knowledge snippet and terminology sources
- evidence filtering rules
- quality audit rules
- future question-generation policy

The public `scenario_id` selects the learning scene, such as `medicine-default` or `general-default`. A scenario points at a content pack, prompt profile, RAG profile, and domain rules. The prompt profile resolves to a soul profile, and the soul profile supplies the subject-specific `soul_path` used by generation. This keeps subject routing independent from parser choice.

The preferred model is hybrid:

- configuration files for simple prompt and rule changes
- code modules for advanced planners, filters, graders, and generators

## Frontend Architecture

The formal frontend foundation is `apps/web` with Next.js App Router, TypeScript, Tailwind CSS, shadcn/ui, and TanStack Query. Browser code calls relative `/api/*` routes; local Next.js rewrites proxy those requests to `JSTUDY_API_ORIGIN`, preserving the backend HTTP-only cookie as a same-origin browser flow without FastAPI CORS changes.

Design rules:

- follow the approved Clinical Workbench specification in `docs/frontend/clinical-workbench-spec.md`
- keep API contracts and auth/job/source/evidence types centralized under `apps/web/src/lib/api`
- use TanStack Query for server state and feature-local React state for file, section, source, and page selection
- build the desktop reader as section index, generated material, and source preview panes, with stacked panels at smaller widths
- use `source_id` as identity and filenames only as display labels
- keep citation jumps inside the source preview scroll area instead of scrolling the whole page

## Deployment Architecture

The first deploy target is a single Linux server using Docker Compose.

Recommended routing:

```text
https://domain.example/        -> Next.js frontend
https://domain.example/api/... -> FastAPI backend
```

This avoids early CORS complexity and makes the pilot easier to migrate.

Expected deployment components:

- reverse proxy: Nginx or Caddy
- frontend container
- backend container
- mounted `data/` volume for uploads, outputs, and cache
- `.env` for runtime secrets

当前 durable execution foundation 使用 `postgres`、`jstudy-api`、
`jstudy-worker` 三服务拓扑。API 只校验上传并持久化 queued Job；独立 worker
通过原子认领、lease 和 bounded retry 执行现有 pipeline。两者共享
PostgreSQL 与 jobs read-write volume，`jstudy-worker` 不暴露端口。Redis
仍不在当前架构中。Pilot artifact 可继续位于挂载卷，后续再通过 storage
boundary 迁移到 Tencent COS。

Runtime settings are centralized in `packages/core/jstudy_core/settings.py`. `JSTUDY_DATABASE_URL`, `JSTUDY_JOBS_DIR`, and `JSTUDY_SETTINGS_DIR` are fixed process/topology settings. Provider credentials, models, MinerU settings, Soul/content paths, upload limits, and retention are admin-managed unless a corresponding nonempty process environment variable explicitly overrides them. An empty environment value falls back to shared `data/settings`; Compose therefore leaves model defaults empty. `JSTUDY_MNEMONICS_PATH` is the current compatibility name for the prompt-rendered knowledge snippet file used by the MVP pipeline.

Operator-editable settings are persisted under `JSTUDY_SETTINGS_DIR`, defaulting to `data/settings`. The current files are `model_catalog.json` for LLM, embedding, and web-search profiles; `runtime.json` for RAG, parser, parser profiles, upload, and cleanup settings; `content_pack.json` for subject-pack paths, scenarios, and soul profiles; and `mnemonics.json` as the compatibility filename for structured knowledge snippet items. The API takes a fresh snapshot for every submission, while the worker takes one for every claim; a claim already in progress keeps that snapshot. Nonempty environment overrides require a process restart to change and intentionally take precedence over the admin catalog.

## Soul Profile Library

The root `soul.md` is the current medicine default, not the long-term global template. `content_pack.json` owns a lightweight soul profile library. A scenario's `prompt_profile` selects a soul profile; that soul profile provides the `soul_path` used for the generation job.

The default library contains:

- `medicine-default`: active, points to `soul.md`
- `general-blank`: placeholder, empty path, scenario disabled
- `engineering-blank`: placeholder, empty path, scenario disabled
- `law-blank`: placeholder, empty path, scenario disabled

Users should choose the scenario on the upload page. Admins should control visibility by enabling or disabling scenario entries. A blank placeholder must receive a real `soul_path` before the scenario is enabled; the backend does not silently fall back from an explicitly blank soul profile to the medicine soul.

Soul profiles are curated vertical assets. They should encode the subject's learning style, output priorities, terminology conventions, common traps, and generation philosophy. The MVP only needs routing and safe defaults; the actual profile content can be built gradually by the product owner as each subject matures.

## Knowledge Snippet Library

The original memory-aid seed file should evolve into a broader knowledge snippet library. A snippet may be a memory aid, terminology explanation, comparison table, workflow summary, common pitfall, or high-quality wording pattern. The library is a second retrieval source after courseware RAG, not a replacement for courseware evidence.

This library is part of J-Study's vertical ecosystem. It should not become a generic bag of prompts. Snippets should remain tied to scenario, subject, review status, and evidence expectations so the same platform can serve different fields without flattening their learning logic.

The safe feedback loop has three layers:

- raw feedback: user-selected liked fragments, tied to job id, owner user id, output location, source evidence ids, scenario, subject, and timestamp
- candidate snippets: semantically deduplicated clusters visible only to administrators
- approved snippets: reviewed entries that can be retrieved during generation

The MVP hook should collect raw feedback into an admin-visible candidate pool only. It should not automatically replace generated content. Future retrieval may use approved snippets as expression and structure guidance, but factual claims must still be supported by the current uploaded document's evidence.

The admin surface is available at `GET /admin/settings`, backed by `GET/PUT /api/admin/settings` and `POST /api/admin/settings/test/{llm|embedding|search}`. Set `JSTUDY_ADMIN_TOKEN` in server deployments so only operators can read or write model keys and runtime settings.

The backend exposes `GET /api/health` for reverse proxy and container liveness checks. `GET /api/readiness` reports whether runtime paths, prompt files, API key configuration, and PDF upload limits are ready for job execution. `GET /api/readiness?probe_provider=true` also performs a live SiliconFlow chat and embedding probe for deployment verification. `GET /api/options` returns public scenarios and parser profiles. `POST /api/generate` accepts empty or `single_courseware` `service_mode` with `pdf=<one PDF>`, and accepts `service_mode=course_outline` with required `outline=<.md/.txt/.pdf>` plus repeated `pdfs=<PDF>` uploads. It also accepts optional `scenario_id`, `parser_profile_id`, and metadata-only `mode`, rejects files above `JSTUDY_MAX_PDF_BYTES`, and returns `503` with readiness details when required runtime configuration is missing. The current `mode` field is metadata only; it is intentionally separate from service mode, subject scenario, and parser profile.

Dynamic API responses that drive polling and runtime state use `Cache-Control: no-store`. Uploaded/generated job artifacts such as markdown output, evidence JSON, material-package JSON, retrieval trace, PDF metadata, original PDF, Markdown export, and rendered PDF page PNGs use `Cache-Control: private, max-age=0, must-revalidate` so browsers can revalidate private previews without serving stale job state.

Job、source、section、artifact 与 append-only transition 持久化在 PostgreSQL。
API 不执行 pipeline；`jstudy-worker` 负责认领、续租、状态推进、artifact
发布与 retention。旧 `jobs.json` 实现仍保留为 compatibility boundary，
但 production API/worker 不 import 或写入它。

`JSTUDY_JOB_RETENTION_HOURS` defaults to `0`, which disables cleanup. Public
pilot `.env` files must provide a deliberate nonzero override such as `72` or
`168`. Retention is worker-owned:
worker 只删除超过 TTL、terminal、无 lease 且目录安全归属于
`JSTUDY_JOBS_DIR/{job_id}` 的 Job；active 或 leased Job 不会被清理。

`GET /api/health` 是纯 liveness；`GET /api/readiness` 是 readiness，并检查
数据库连接和执行所需配置。`JSTUDY_DATABASE_URL` 是首选数据库变量，
`DATABASE_URL` 仅作为兼容 fallback。

当前 SQLModel `create_all()` 只适用于数据可丢弃的 disposable pilot。
持久用户数据启用前必须引入 versioned migrations，并形成迁移、回滚、
备份与恢复 runbook。

Uploaded PDFs stay on local disk during the pilot because citation preview needs the original source file. This is acceptable for a small trial only with nonzero retention. When J-Study needs persistent user history, course libraries, or formal multi-user accounts, uploaded PDFs and generated artifacts should move to Tencent COS or equivalent object storage, with metadata kept in a database and lifecycle rules enforced outside the app process.

Completed jobs expose the retrieval trace through `GET /api/jobs/{job_id}/trace`. This returns the selected chunks, query traces, RAG settings, source file metadata, and knowledge snippet hits already written by the pipeline so backend quality issues can be reviewed without shell access to the server. `GET /api/jobs/{job_id}/package` returns a strictly validated `material-package.v2` for new jobs and keeps a bounded legacy v1 read branch during migration. Single-courseware jobs keep section id `full-material`; course-outline jobs keep deterministic outline section ids and order. The endpoint remains owner-scoped and never returns malformed persisted v2 as an unvalidated response. `GET /api/jobs/{job_id}/export` downloads Markdown deterministically derived from v2 with the same owner checks as the other job artifacts. Multi-PDF jobs should use source-specific preview endpoints under `/api/jobs/{job_id}/pdfs/{source_id}/...`; old `/pdf-info` and `/pdf-page/{page}.png` endpoints remain first-source compatibility aliases.

The generated quality report traverses typed blocks and citation runs directly. Unknown source, evidence, or citation identities are validation errors; unused evidence, weak-evidence sections, and failed sections remain explicit issues. Markdown is not parsed to calculate v2 quality.

This task did not add an HTML renderer or export path, switch the generation pipeline to MinerU, remove Markdown, or introduce a database migration.

## Current Technical Debt

The MVP intentionally has several temporary choices:

- root-level `web_mvp.py` and `mvp_runner.py` are compatibility shims
- outputs are local files

These should be addressed in roadmap order, not all at once.
