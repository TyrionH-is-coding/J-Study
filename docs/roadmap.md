# Roadmap

## Phase 0: Repository and Documentation Baseline

Goal: make the project understandable before adding more code.

Deliverables:

- product vision
- architecture overview
- roadmap
- development standards
- archived MVP handoff notes
- target repository structure

Acceptance:

- a new contributor can understand the product direction from `README.md`
- root-level documents are not scattered
- current MVP verification commands are documented

## Phase 1: Formalize the MVP Backend

Goal: keep the current backend behavior while moving it into a product structure.

Deliverables:

- move FastAPI code to `apps/api` - done
- move generation pipeline behind `packages/core` - done
- split parser, retrieval, and medicine domain logic into dedicated modules - done
- keep PyMuPDF as the initial MVP parser - done historically; superseded by
  the 2026-07-28 MinerU migration decision
- keep existing tests passing - done
- add explicit dependency file - done
- split runtime settings and job lifecycle - done
- split provider calls - done
- split storage/output contracts - done
- split legacy CLI entrypoint from pipeline orchestration - done
- add lightweight JSON job persistence for single-server deployment - done

Acceptance:

- existing API contract still works
- `python -m unittest discover -s tests -v` passes
- old root-level scripts are documented as compatibility shims
- runtime settings can come from environment variables before server deployment - done for API key, model names, jobs directory, and template paths

## Phase 1R: Contract-First Platform Refactor

Goal: preserve the validated MVP while replacing temporary parser, job, and
module boundaries with production-oriented contracts.

Deliverables:

- verified Git checkpoint for tasks 0002-0004
- normalized MinerU document contract
- MinerU Precision Extract cloud client
- safe result download and ZIP normalization
- PyMuPDF limited to PDF validation and source preview utilities
- explicit job state machine
- PostgreSQL job/source/section/artifact/transition persistence（Task 0006 foundation 已实现）
- separate API and `jstudy-worker` processes（Task 0006 foundation 已实现）
- typed FastAPI schemas and OpenAPI/frontend contract validation
- removal of public parser choice

Acceptance:

- every refactor phase keeps backend and frontend regression suites passing
- Course Outline Mode works through MinerU end to end
- job ownership, progress, and artifacts survive process restart
- no raw MinerU provider structure leaks into retrieval or frontend code
- no user-facing parser profile remains
- the checkpoint SHA and deletion gates are recorded

Task 0006 当前边界：

- Compose 使用 `postgres`、`jstudy-api`、`jstudy-worker`，worker 无公开端口；
- API durable submission 与 worker lease/retry/retention 已分离；
- 旧 `jobs.json` 仅保留 compatibility boundary，production 不 import；
- SQLModel `create_all()` 仅用于 disposable pilot；
- 持久数据上线前仍必须交付 versioned migrations 和迁移/回滚/备份 runbook；
- HTML 仍属于后续任务；Task 0008 已完成 MinerU Worker pipeline 切换。

Task 0007 当前边界：

- `single_courseware` 与 `course_outline` 新 Job 均生成严格校验的 `material-package.v2`；
- citation/source/evidence 交叉引用与质量指标直接从 typed blocks 计算；
- JSON 格式或 schema 失败最多进行一次受控修复；
- Markdown 由 v2 确定性派生并继续满足现有 `/output` 与 `/export` 兼容合同；
- Worker 原子持久化 v2 sections/artifacts/completion，package API 保持 owner check 并继续读取 legacy v1；
- 未实施 React/HTML renderer、HTML export、MinerU pipeline switch、Markdown 删除或数据库迁移。

## Phase 1S: Courseware-Synchronized Generation

Goal: replace the current relevance-first complete-material path with a
courseware-order-first backend contract.

Approved design:

- `docs/superpowers/specs/2026-07-31-courseware-synchronized-learning-design.md`

Task 0008 delivered the first backend slice:

- persist stable source display metadata without changing `source_id`
- freeze `courseware-manifest.v1` for each generation Job
- connect MinerU Precision Extract to the real Worker path
- normalize every source to `ParsedDocument`
- build ordered, continuous `learning-map.v1` units
- generate material sections in Manifest order instead of Top-K retrieval order
- write `coverage-ledger.v1` for every usable/ignored block
- mark cross-source relationships `navigation_policy=non_interactive`
- remove parser selection from public options while retaining bounded request compatibility

Completed acceptance:

- both implemented service modes use the same Worker-owned MinerU document service
- stable source identity remains independent from display title and order
- every normalized block receives one coverage disposition
- complete-material section order follows the deterministic learning map, not embedding relevance
- owner-scoped APIs publish manifest, learning map, and coverage ledger with private cache headers
- PyMuPDF remains only on PDF validation, metadata, and preview utility paths

Task 0008 does not include:

- formal frontend organizer, drag-and-drop, or rename UI
- semantic auto-organization quality tuning
- HTML renderer or theme presets
- Multi Courseware Mode
- Alembic or production deployment
- question generation, BYOK, quota, or billing

Later phases add the editable courseware draft/organizer, synchronized Reader,
HTML rendering, and production-like deployment after the backend contracts pass.

Implementation order is controlled by:

- `docs/architecture/refactor-blueprint.md`
- `multi-agent/jstudy-product-build/task_cards/0005-refactor-checkpoint-mineru-foundation.md`
- `multi-agent/jstudy-product-build/task_cards/0008-mineru-sequence-first-backend.md`

## Phase 1.5: User Auth and Invite Gate

Goal: add the minimum user boundary before the full frontend is built.

Deliverables:

- Postgres-backed user persistence
- email/password registration and login
- reusable invite code required for registration
- `email_verified` field reserved but not enforced
- HTTP-only cookie session
- admin-token-protected invite-code management
- user-owned jobs and result access control

Acceptance:

- users can register only with an enabled invite code
- one shared invite code can register multiple users
- users can only see their own jobs and generated artifacts
- admin invite management remains protected by `JSTUDY_ADMIN_TOKEN`
- auth behavior is covered by automated tests before server deployment

## Phase 2: Frontend foundation rebuilt; business workflows pending

Goal: maintain a reproducible Next.js foundation before reconnecting product workflows.

Deliverables:

- `apps/web` with Next.js App Router, TypeScript, Tailwind, shadcn/ui configuration, and TanStack Query - done
- shared application shell and explicit route placeholders - done
- centralized relative `/api/*` request boundary - done
- unit, production-build, and three-viewport browser verification - done
- formal brand and visual language - pending
- login, registration, cookie session guard, and logout - pending
- Course Outline upload and job polling - pending
- generated material reader and source-specific PDF preview - pending
- citation-to-source-preview interaction - pending

Acceptance:

- all six foundation routes open directly
- route placeholders do not present fake forms or sample business data
- browser API calls are constrained to the relative `/api/*` boundary
- primary application shell has no horizontal overflow at required viewports
- business workflow completion is not claimed until it is reimplemented and tested

## Phase 3: Single-Server Deployment

Goal: deploy the MVP to the prepared domain and server.

Deliverables:

- backend Dockerfile - done
- backend Docker Compose scaffold - done
- frontend Dockerfile after `apps/web` exists
- reverse proxy config
- `.env.example` - done for backend runtime settings
- mounted `data/` directory - done for backend jobs
- deployment runbook - done for backend-only Docker Compose; full runbook after frontend and reverse proxy exist

Acceptance:

- `https://domain/` serves the frontend
- `https://domain/api/...` reaches the backend
- secrets are not committed
- deployment can be reproduced on another Linux server

## Phase 4: MVP Quality and Reliability

Goal: make generated output more stable and auditable.

Deliverables:

- stronger quality report - done for evidence-id validation, unused-evidence warnings, implementation wording checks, and section citation coverage
- parser/retrieval trace review tools - done for retrieval trace API
- Markdown export endpoint - done for completed single-courseware jobs
- single-courseware material-package metadata wrapper - done as a compatibility foundation, not full multi-section generation
- better failed-job errors - done with exception type in job status
- upload limits - done for courseware PDF type and size
- cache controls - done for dynamic API status responses and private generated artifacts
- optional cleanup policy - done with disabled-by-default finished-job retention

Acceptance:

- failed jobs explain what failed
- generated output cites valid evidence IDs
- quality reports show citation coverage by markdown section
- frontend polling is not served stale job state from browser caches
- single-server deployments can opt into finished-job cleanup without deleting queued or running jobs
- low-quality output is flagged before user trust is damaged

## Phase 4.5: Service Mode Model

Goal: implement the approved, mutually exclusive product contracts for the three
generation workflows without mixing them with subject profiles or parser
infrastructure.

Deliverables:

- explicit `single_courseware`, `course_outline`, and `multi_courseware`
  service modes - backend paths currently exist for `single_courseware` and
  `course_outline`; strict input cleanup and `multi_courseware` remain pending
- frontend upload entry points that explain the three modes without mixing them
  with subject scenario or internal parser infrastructure
- backend request contract that records service mode separately from
  `scenario_id` - currently done for `course_outline`; legacy
  `parser_profile_id` is no longer advertised and remains only as bounded
  empty/`fast`/`quality` request compatibility
- package-output contract for multi-section material - strict v2 backend contract done for `single_courseware` and `course_outline`
- section-level blocks, structural citations, source/evidence identities, and direct quality status - backend v2 done for both implemented modes
- full-export contract that can assemble all sections into one complete document
- Multi Courseware association discovery that proposes cross-source candidates,
  validates both sides, and adds bounded non-interactive knowledge connections
  without changing the main Learning Map

Acceptance:

- Single Courseware accepts exactly one PDF and no outline
- Course Outline accepts exactly one outline and at least one PDF
- Multi Courseware accepts at least two PDFs from the same course and no outline
- Multi Courseware is not implemented as several independent single-PDF jobs
- Course Outline uses the outline for matching and grouping while preserving the
  user-confirmed courseware and page order
- Multi Courseware and Course Outline both support web browsing by section and full-document export
- cross-courseware relationships are evidence-bounded, rendered as natural
  language, and never become automatic cross-courseware Reader navigation
- service mode selection does not change the selected subject scenario or parser profile

## Phase 5: Multi-Discipline Domain Packs

Goal: prove that medicine is a first domain, not a hard-coded product boundary, while keeping J-Study more vertical than a general DeepTutor-style assistant.

Deliverables:

- stable domain-pack interface
- medicine pack extracted from root templates
- subject-specific soul profile authoring path
- scenario visibility managed by admin settings
- at least one second lightweight domain prototype
- domain-specific query planner contract

Acceptance:

- adding a new subject does not require editing platform pipeline code
- medicine-specific prompts and rules live under `packages/domains/medicine`
- a new subject can start with a blank hidden soul profile, then become visible only after the profile has usable content
- service delivery is not blocked by fully populated soul libraries

## Phase 5.25: Multi Courseware Mode

Goal: let users upload at least two ordered PDFs from the same course and receive
one sequence-first material package with bounded cross-courseware knowledge
connections.

Deliverables:

- strict `multi_courseware` admission with at least two PDFs and no outline
- frontend entry point that distinguishes Multi Courseware from Course Outline
- user-confirmed source title and order before generation
- source-file metadata in chunks, evidence, and citation links - done
- sequence-first section planning from the confirmed source/page/block order
- embedding-based candidate discovery across different `source_id` values
- dual-sided evidence validation and explicit relationship classification
- bounded association hints that never reorder the main Learning Map
- duplicate relationship merging within a learning unit
- non-interactive natural-language relationship rendering in the Reader
- package reader with section navigation and source preview
- full-document export assembled from package sections

Acceptance:

- user can upload at least two PDFs from the same course in one Job
- an outline is rejected with a clear instruction to use Course Outline Mode
- generated output is browsable by chapter or topic in the web app
- the main material follows the user-confirmed source and page order
- every displayed cross-courseware relationship has evidence from both sources
- association failure omits the relationship without failing the main material
- cross-courseware relationships do not navigate the Reader to another source
- user can export the whole package as one complete material file
- the system does not lose source-file identity when rendering citation jumps

## Phase 5.4: Course Outline Mode

Goal: turn a full course outline plus all courseware into a course-level material package.

Deliverables:

- outline upload and deterministic parsing workflow - backend done
- outline-node section plan - backend done
- retrieval across all uploaded courseware per outline node - backend first version done
- evidence coverage report per outline node - typed block/citation audit done
- section-by-section web browsing - done in `apps/web`
- full course-material Markdown export - deterministically derived from v2

Acceptance:

- user can upload a course outline and multiple courseware PDFs
- output order follows the uploaded outline
- each outline node shows whether evidence is sufficient, weak, or missing
- generated sections can cite evidence from any uploaded courseware
- user can browse the course package by section and export the complete course material

## Phase 5.5: Knowledge Snippet Feedback Hook

Goal: leave the product hook for user-driven quality improvement without making feedback affect generation too early, and grow J-Study's vertical snippet ecosystem one reviewed candidate at a time.

Deliverables:

- frontend selection-and-like event shape
- backend raw feedback API contract
- feedback records tied to user, job, scenario, subject, selected text, and source evidence ids
- embedding generation for feedback fragments
- semantic deduplication into administrator-visible candidate clusters
- review status model: `candidate`, `approved`, `rejected`, `deprecated`
- subject and scenario metadata on every snippet candidate
- manual review workflow before snippets become reusable product knowledge

Acceptance:

- liked fragments are saved as raw feedback only
- candidate clusters are visible to administrators
- no candidate can affect generation until it is approved
- approved snippets are retrieved as auxiliary guidance, not as independent fact sources
- automatic replacement remains disabled until current-upload evidence matching is reliable
- snippet growth improves vertical quality without turning the library into generic prompt storage

## Phase 6: Question Generation

Goal: generate new questions from past papers and courseware.

Deliverables:

- past-paper parsing workflow
- extracted question templates
- question style classification
- source-topic alignment
- generated questions with evidence-backed explanations

Acceptance:

- system can generate new questions in the style of uploaded past papers
- answers and explanations cite courseware evidence when possible

## Phase 7: Scale-Driven Production Services

Goal: add infrastructure only when product usage justifies it.

Possible deliverables:

- Redis queue
- Tencent COS or equivalent object storage
- spare-computer or dedicated self-hosted MinerU worker
- multi-worker routing and cost controls
- advanced user roles and permissions

Acceptance:

- added infrastructure is justified by measured queue, storage, availability, or
  provider-cost pressure
- self-hosted parsing matches the normalized MinerU contract and does not change
  product behavior
