# Architecture Overview

## Summary

J-Study is a single-server MVP that should evolve into a formally structured product. The current backend now has canonical package paths: `apps/api/jstudy_api/app.py` serves the FastAPI MVP, `apps/api/jstudy_api/ui.py` owns the temporary built-in user UI, `apps/api/jstudy_api/admin_ui.py` owns the temporary backend-served admin settings page, `packages/core/jstudy_core/pipeline.py` orchestrates the generation pipeline, `packages/core/jstudy_core/cli.py` owns the legacy CLI entrypoint implementation, `packages/core/jstudy_core/admin_settings.py` owns JSON-backed runtime admin settings, `packages/core/jstudy_core/scenario_router.py` owns learning-scenario resolution, `packages/core/jstudy_core/parser_profile_router.py` owns user-facing parser-profile resolution, `packages/core/jstudy_core/citations.py` owns evidence and citation-link contracts, `packages/core/jstudy_core/jobs.py` owns the MVP job lifecycle and JSON persistence, `packages/core/jstudy_core/providers.py` owns SiliconFlow-compatible chat and embedding calls, `packages/core/jstudy_core/settings.py` owns runtime resolution and deployment overrides, `packages/core/jstudy_core/storage.py` owns local output file contracts, `packages/parsers` owns document parsing, `packages/retrieval` owns chunking and hybrid retrieval, and `packages/domains/medicine.py` owns the first subject pack. Root-level `web_mvp.py` and `mvp_runner.py` remain compatibility shims for old commands.

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
    # PyMuPDF parser now; future MinerU implementation
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
Upload PDF + optional outline + optional scenario/parser profile
-> Document Parser
-> chunks with page metadata
-> retrieval query planner
-> embedding + lexical retrieval
-> evidence selection
-> approved knowledge snippet retrieval
-> domain prompt/template
-> LLM generation
-> Markdown + evidence + evidence links + quality report
-> frontend reader with source-page citation jumps
```

## Platform Layer

The platform layer should own common product behavior:

- file upload
- job lifecycle
- learning-scenario resolution
- parser-profile visibility and routing
- parser selection
- retrieval execution
- evidence link contracts
- output storage
- API response shape
- deployment and runtime configuration

It should not own medicine-specific prompt wording, knowledge-snippet rules, or subject quality standards.

## Document Parser Boundary

The parser boundary is intentional. Parser output should preserve enough metadata to support citation jumps:

- source file
- page number
- extracted text
- optional layout blocks
- optional table or image references
- optional bounding boxes in future versions

### Parser Profiles

Users choose a product-facing parser profile when the profile is exposed. The backend currently defines:

- `fast`: PyMuPDF, enabled and visible to users by default.
- `quality`: MinerU-backed, hidden from normal users and admin-only until MinerU is configured and the product tier is ready.

Automatic PDF difficulty scoring is not part of the current implementation. The system should not silently upgrade a job to MinerU; the selected parser profile is the source of truth.

### Default Parser: PyMuPDF

PyMuPDF is the default MVP parser. It is fast, simple to deploy, and good enough for text-first PPT-exported PDFs where citation to the original page is already available.

### Future Parser: MinerU

MinerU should be added as a heavier optional parser, not as the first deployment dependency. It is valuable for complex layouts, tables, scanned documents, Office files, and future past-paper question extraction.

The architecture should allow:

```text
parser = pymupdf | mineru
```

without rewriting retrieval or domain logic.

## Retrieval Layer

The current MVP retrieval approach is:

- page-aware chunking
- embedding similarity
- BM25-style lexical matching
- reciprocal-rank fusion
- low-value chunk filtering
- per-query evidence limits

This lives in `packages/retrieval/` so it can be reused across domains.

## Domain Layer

Domain packs should define subject-specific behavior. The first pack is `medicine`.

Expected domain-pack responsibilities:

- query planning
- prompt template
- output style rules
- knowledge snippet and terminology sources
- evidence filtering rules
- quality audit rules
- future question-generation policy

The public `scenario_id` selects the learning scene, such as `medicine-default` or `general-default`. A scenario points at a content pack, prompt profile, RAG profile, and domain rules. This keeps subject routing independent from parser choice.

The preferred model is hybrid:

- configuration files for simple prompt and rule changes
- code modules for advanced planners, filters, graders, and generators

## Frontend Architecture

The frontend should be `apps/web` with Next.js and shadcn/ui.

Design rules:

- start from a selected shadcn/ui template
- keep the template's main layout stable
- adjust brand color, typography, density, states, and product-specific panels
- build the reader around two independent areas: generated material and source preview
- source preview should support citation jumps without scrolling the whole page

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

Future components can include Redis, Postgres, object storage, and a separate worker.

Runtime settings are centralized in `packages/core/jstudy_core/settings.py`. `SILICONFLOW_API_KEY` is the primary API key source; `SILICONFLOW_API_KEY_FILE` is the file fallback. `JSTUDY_JOBS_DIR`, `JSTUDY_SOUL_PATH`, `JSTUDY_MNEMONICS_PATH`, `JSTUDY_MAX_PDF_BYTES`, `JSTUDY_JOB_RETENTION_HOURS`, `SILICONFLOW_CHAT_MODEL`, and `SILICONFLOW_EMBED_MODEL` control deploy-time paths, upload limits, optional cleanup, and model choices. `JSTUDY_MNEMONICS_PATH` is the current compatibility name for the prompt-rendered knowledge snippet file used by the MVP pipeline.

Operator-editable settings are persisted under `JSTUDY_SETTINGS_DIR`, defaulting to `data/settings`. The current files are `model_catalog.json` for LLM, embedding, and web-search profiles; `runtime.json` for RAG, parser, parser profiles, upload, and cleanup settings; `content_pack.json` for subject-pack paths and scenarios; and `mnemonics.json` as the compatibility filename for structured knowledge snippet items. Environment variables remain deployment overrides and take precedence where they overlap with admin settings.

## Knowledge Snippet Library

The original memory-aid seed file should evolve into a broader knowledge snippet library. A snippet may be a memory aid, terminology explanation, comparison table, workflow summary, common pitfall, or high-quality wording pattern. The library is a second retrieval source after courseware RAG, not a replacement for courseware evidence.

The safe feedback loop has three layers:

- raw feedback: user-selected liked fragments, tied to job id, owner user id, output location, source evidence ids, scenario, subject, and timestamp
- candidate snippets: semantically deduplicated clusters visible only to administrators
- approved snippets: reviewed entries that can be retrieved during generation

The MVP hook should collect raw feedback into an admin-visible candidate pool only. It should not automatically replace generated content. Future retrieval may use approved snippets as expression and structure guidance, but factual claims must still be supported by the current uploaded document's evidence.

The admin surface is available at `GET /admin/settings`, backed by `GET/PUT /api/admin/settings` and `POST /api/admin/settings/test/{llm|embedding|search}`. Set `JSTUDY_ADMIN_TOKEN` in server deployments so only operators can read or write model keys and runtime settings.

The backend exposes `GET /api/health` for reverse proxy and container liveness checks. `GET /api/readiness` reports whether runtime paths, prompt files, API key configuration, and PDF upload limits are ready for job execution. `GET /api/readiness?probe_provider=true` also performs a live SiliconFlow chat and embedding probe for deployment verification. `GET /api/options` returns public scenarios and parser profiles. `POST /api/generate` accepts PDF uploads only, optional `scenario_id` and `parser_profile_id` form fields, rejects files above `JSTUDY_MAX_PDF_BYTES`, and returns `503` with readiness details when required runtime configuration is missing.

Dynamic API responses that drive polling and runtime state use `Cache-Control: no-store`. Uploaded/generated job artifacts such as markdown output, evidence JSON, retrieval trace, PDF metadata, original PDF, and rendered PDF page PNGs use `Cache-Control: private, max-age=0, must-revalidate` so browsers can revalidate private previews without serving stale job state.

Job status persists to `JSTUDY_JOBS_DIR/jobs.json` so completed and failed jobs remain visible after a process restart. Queued or running jobs are marked failed on restart because the current MVP does not yet have a separate resumable worker queue.

`JSTUDY_JOB_RETENTION_HOURS` defaults to `0`, which disables cleanup. Public pilot deployments should set it to `72` or `168`. When set to a positive number, the API prunes completed or failed jobs older than that TTL during app startup and before accepting a new generation job. Cleanup removes the persisted job record and the job directory only when the directory is safely shaped as `JSTUDY_JOBS_DIR/{job_id}`. Queued and running jobs are never pruned by this policy.

Uploaded PDFs stay on local disk during the pilot because citation preview needs the original source file. This is acceptable for a small trial only with nonzero retention. When J-Study needs persistent user history, course libraries, or formal multi-user accounts, uploaded PDFs and generated artifacts should move to Tencent COS or equivalent object storage, with metadata kept in a database and lifecycle rules enforced outside the app process.

Completed jobs expose the retrieval trace through `GET /api/jobs/{job_id}/trace`. This returns the selected chunks, query traces, RAG settings, and knowledge snippet hits already written by the pipeline so backend quality issues can be reviewed without shell access to the server.

The generated quality report checks whether hidden evidence comments exist, whether cited evidence IDs are valid, whether retrieved evidence was left unused, whether implementation-facing wording leaked into the output, and whether each markdown section has citation coverage. Missing section citations are warnings so the MVP can surface review risk without blocking otherwise valid output.

## Current Technical Debt

The MVP intentionally has several temporary choices:

- root-level `web_mvp.py` and `mvp_runner.py` are compatibility shims
- outputs are local files

These should be addressed in roadmap order, not all at once.
