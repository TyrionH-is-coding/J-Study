# Architecture Overview

## Summary

J-Study is a single-server MVP that should evolve into a formally structured product. The current backend now has canonical package paths: `apps/api/jstudy_api/app.py` serves the FastAPI MVP, `apps/api/jstudy_api/ui.py` owns the temporary built-in user UI, `apps/api/jstudy_api/admin_ui.py` owns the temporary backend-served admin settings page, `packages/core/jstudy_core/pipeline.py` orchestrates sequence-first generation, `packages/core/jstudy_core/courseware` owns manifest/map/coverage contracts and planning, `packages/core/jstudy_core/documents` owns normalized document contracts and the MinerU document service, `packages/core/jstudy_core/job_system` owns durable jobs and the independent Worker, `packages/core/jstudy_core/citations.py` owns evidence and citation-link contracts, `packages/core/jstudy_core/providers.py` owns SiliconFlow-compatible model calls, `packages/core/jstudy_core/settings.py` owns runtime resolution and deployment overrides, `packages/core/jstudy_core/storage.py` owns local output file contracts, and `packages/parsers` owns MinerU transport plus PyMuPDF utilities. Root-level `web_mvp.py` and `mvp_runner.py` remain compatibility shims for old commands.

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

Current sequence-first implementation:

```text
Upload one strict service-mode input shape + optional scenario
-> scenario and soul profile resolution
-> stable source identity and display-order snapshot
-> one batched MinerU Precision Extract request per Job
-> normalized ParsedDocument records in requested source order
-> deterministic courseware-manifest.v1
-> continuous learning-map.v1 units in source/page/block order
-> coverage-ledger.v1 for every normalized block
-> unit-local primary evidence
-> model-generated blocks with at most one format repair
-> server-owned section identity, evidence metadata, status, and quality
-> validated material-package.v2 blocks and citation runs
-> direct package quality audit
-> deterministic compatibility Markdown + evidence links
-> owner-scoped synchronization artifact APIs
```

Next product layer:

```text
Upload outline + courseware
-> stable source identities and editable courseware draft
-> user-confirmed courseware-manifest.v1
-> MinerU ParsedDocument for every source
-> ordered source/page/block stream
-> continuous learning-map.v1 units
-> sequence-first section generation
-> coverage-ledger.v1 and navigation-policy audit
-> validated material-package.v2
-> synchronized Reader and deterministic export

Embedding index
-> optional association discovery, search, and snippet deduplication
-> never controls the main learning sequence
```

## Service Mode Architecture

The platform should distinguish service mode from subject scenario and internal
parser infrastructure.

The approved target contracts are:

- `single_courseware`: exactly one PDF and no outline.
- `course_outline`: exactly one outline and at least one PDF.
- `multi_courseware`: at least two PDFs from the same course and no outline.

The modes are mutually exclusive and do not convert after submission. The
complete product rules live in `docs/product/service-modes.md`.

The backend implements all three strict admission and generation paths.
`multi_courseware` uses one Job, one batched MinerU parse, stable source
identity/display order, and the same sequence-first coordination and package
contracts. Cross-courseware association generation remains unimplemented while
candidate algorithms are evaluated. The formal `apps/web` business workflows
remain foundation placeholders.

The three implemented service modes use the same v2 package-output contract:

```text
material-package.v2
-> sections[]
   -> stable section id, title, order, and status
   -> source_ids and evidence_ids
   -> typed blocks and structural citation runs
   -> direct evidence quality metrics
-> deterministic compatibility Markdown assembled from sections
```

The difference is planning. Multi Courseware Mode currently follows the
admission-time courseware order without adding cross-courseware relationships.
Course Outline Mode uses the uploaded outline for matching, naming, and grouping
while preserving the confirmed source and page order; weak evidence remains
visible instead of being silently invented.

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
Users do not select a parser or parser tier. The Worker routes all three
implemented service modes through MinerU; empty, `fast`, and `quality` remain
request aliases only and do not change parser execution.

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

The retained optional retrieval toolkit is:

- page-aware chunking
- deterministic query planning from the current PDF text and optional outline
- embedding similarity
- BM25-style lexical matching
- reciprocal-rank fusion
- low-value chunk filtering
- per-query evidence limits

This lives in `packages/retrieval/` so it can be reused across domains.

Sequence-first generation consumes every usable MinerU block through continuous
learning units. Hybrid retrieval remains available for:

- optional cross-page relationship discovery
- later user questions and semantic search
- Knowledge Snippet similarity and feedback clustering
- explicitly requested topic-focused generation

It must not choose the primary section order or silently remove valid
courseware blocks from complete-material generation.

The versioned coordination artifacts are:

- `courseware-manifest.v1`: immutable source identity and display order snapshot
- `learning-map.v1`: continuous primary page ranges and material section mapping
- `coverage-ledger.v1`: used, ignored, duplicate, and unsupported block records

The detailed contract is defined in
`docs/superpowers/specs/2026-07-31-courseware-synchronized-learning-design.md`.

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
- keep `learning_position` separate from the PDF `viewer_position`
- allow Inspect Mode only for same-source citation jumps
- render cross-source relationships as non-interactive natural language
- switch top-level sources only through chapter/source navigation or explicit user action

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

Sequence-first generation dispatches one existing model call per Learning Unit
through a bounded, order-preserving scheduler. `JSTUDY_GENERATION_MAX_CONCURRENCY`
has legal range `1..4` and 默认值 `3`; value `1` is the supported 串行回滚.
The immutable Worker claim snapshot fixes the value for the running Job, and
completion order cannot change `MaterialSection.order`. Total provider
concurrency multiplies by Worker 副本 count, so replica changes require a fresh
rate-limit calculation. Deterministic tests verify this architecture, while the
Supervisor must still run the real six-page staging gate: median at most 25 秒
and every run at most 35 秒.

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

The backend exposes `GET /api/health` for reverse proxy and container liveness checks. `GET /api/readiness` reports whether runtime paths, prompt files, API key configuration, and PDF upload limits are ready for job execution. `GET /api/readiness?probe_provider=true` also performs a live SiliconFlow chat and embedding probe for deployment verification. `GET /api/options` returns public scenarios without parser profiles and exposes the three enabled service modes. `POST /api/generate` accepts empty or `single_courseware` `service_mode` with exactly one singular `pdf=<PDF>`; `course_outline` with one required `outline=<.md/.txt/.pdf>` plus at least one repeated `pdfs=<PDF>`; and `multi_courseware` with at least two repeated `pdfs=<PDF>`. The three multipart families are mutually exclusive. New clients omit `parser_profile_id`; empty, `fast`, and `quality` are bounded migration aliases, unknown values are rejected, and the Worker always uses MinerU. The metadata-only `mode` remains separate from service mode and subject scenario.

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

Completed jobs expose bounded strict `courseware-manifest.v1`, `learning-map.v1`, and `coverage-ledger.v1` through owner-scoped `/manifest`, `/learning-map`, and `/coverage` endpoints. Job status links these artifacts; source payloads preserve stable `source_id` separately from `original_filename`, `display_title`, and `display_order`. `GET /api/jobs/{job_id}/package` returns a strictly validated `material-package.v2` and keeps a bounded legacy v1 read branch. `GET /api/jobs/{job_id}/export` downloads deterministic compatibility Markdown. Multi-PDF previews use source-specific `/api/jobs/{job_id}/pdfs/{source_id}/...` endpoints; old first-source aliases remain compatible.

The generated quality report traverses typed blocks and citation runs directly. Unknown source, evidence, or citation identities are validation errors; unused evidence, weak-evidence sections, and failed sections remain explicit issues. Markdown is not parsed to calculate v2 quality.

The approved resumability boundary is section-scoped and content-addressed.
Each generated section will receive a `GenerationFingerprint` derived from
source SHA, Learning Unit/block identities, Soul and Snippet versions, provider
protocol/model, prompt version, and package schema. A successful section can be
reused only when that fingerprint matches exactly. Theme and renderer settings
belong to a separate `ExportFingerprint`; changing visual style must never
trigger another model generation.

Deterministic quality gates run before optional model review. Schema,
source/evidence/citation identity, manifest/map/coverage coordination, required
assets, unsafe content, renderer structural parity, and fingerprint compatibility
are code-checked contracts. LLM review may assist with semantic ambiguity but
cannot replace or silently override these gates.

Task 0008 did not add the organizer UI/API, an HTML renderer, remove Markdown,
introduce a database migration, or deploy the service. Existing disposable
pilot databases require reset because the source table gained display metadata.

## Current Technical Debt

The MVP intentionally has several temporary choices:

- root-level `web_mvp.py` and `mvp_runner.py` are compatibility shims
- outputs are local files

These should be addressed in roadmap order, not all at once.
