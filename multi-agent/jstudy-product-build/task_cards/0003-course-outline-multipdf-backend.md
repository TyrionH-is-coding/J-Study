# Task Card: Course Outline Mode Multi-PDF Backend

## Supervisor Thread

`019ed023-8e41-7ad0-8117-6246b8ffa0bb`

## Code Agent Thread

`019efec4-1e17-7443-8496-c1fea5d6bcb5`

## Goal

Implement the first backend version of `course_outline` service mode:

1. User uploads a course outline first.
2. User uploads one or more matching courseware PDFs.
3. Backend stores all source PDFs with stable source identity.
4. Backend generates a material package organized by outline sections.
5. Each generated section carries evidence ids and source PDF/page references.
6. Existing `single_courseware` behavior remains compatible.

This task is backend-only. Do not build the final `apps/web` frontend.

## Product Context

The frontend direction has changed: the first screen should be a service-mode selector. The first mode to complete is **Course Outline Mode**, not a generic upload page.

The backend currently supports:

- `POST /api/generate` with one `pdf` and optional `outline`
- single-courseware output
- `material_package` wrapper for the single-courseware output
- PDF preview endpoints for one source PDF

This task should extend the backend so the future frontend can call a real course-outline workflow.

## Key Decisions

### Service Mode Field

Add a separate form field:

```text
service_mode
```

Allowed values for this task:

- empty or `single_courseware`: existing behavior
- `course_outline`: new outline-first multi-PDF behavior

Do not use the existing `mode` field for service mode. `mode` remains metadata only.

### Upload Contract

Keep existing single-courseware compatibility:

```text
POST /api/generate
pdf=<one PDF>
outline=<optional outline>
scenario_id=<optional>
parser_profile_id=<optional>
mode=<metadata only>
```

Add course-outline contract:

```text
POST /api/generate
service_mode=course_outline
outline=<required .md/.txt/.pdf outline>
pdfs=<one or more PDF files, repeated multipart field>
scenario_id=<optional>
parser_profile_id=<optional>
mode=<metadata only>
```

Validation rules:

- `course_outline` requires `outline`.
- `course_outline` requires at least one uploaded PDF in `pdfs`.
- Each courseware file must pass the existing PDF header and size validation.
- Preserve existing single-courseware `pdf` behavior.
- Reject unsupported `service_mode` with `400`.
- Do not silently treat `mode` as service mode.

### Source Identity

Course-outline jobs need stable source identity:

```json
{
  "source_id": "S001",
  "file_name": "lecture-01.pdf",
  "page_count": 42
}
```

Evidence and citation targets must include:

- `source_id`
- `source_file`
- `page`
- `chunk_id`
- `quote`

Existing single-PDF evidence links must keep working.

## Implementation Phases

### Phase 0: Contract Inventory

Before editing code, inspect:

- `apps/api/jstudy_api/app.py`
- `packages/core/jstudy_core/jobs.py`
- `packages/core/jstudy_core/pipeline.py`
- `packages/core/jstudy_core/storage.py`
- `packages/core/jstudy_core/citations.py`
- `packages/retrieval/hybrid.py`
- `tests/test_web_mvp.py`
- `tests/test_mvp_runner.py`
- `tests/test_security_controls.py`
- `docs/architecture/overview.md`
- `docs/roadmap.md`

Create a short implementation note:

- `multi-agent/jstudy-product-build/reports/0003-course-outline-backend-plan.md`

The note should list:

- exact API changes
- exact artifact shape
- tests to add
- any assumptions

### Phase 1: Data Model and Storage Contract

Update job storage and output contracts with backward compatibility.

Expected shape:

- `JobRecord` can still expose `pdf_path` for old single-courseware jobs.
- Course-outline jobs can store multiple PDF paths, preferably as `pdf_paths` or source metadata.
- Persist and reload multi-PDF metadata in `jobs.json`.
- `build_output_paths()` includes paths needed for material package and existing artifacts.

Do not migrate old job JSON. Missing new fields should default safely.

### Phase 2: Retrieval Source Identity

Add source identity to chunks/evidence without breaking old callers.

Acceptable approach:

- Extend `Chunk` with optional `source_id` and `source_file`.
- Extend `chunk_pages()` with optional `source_id` and `source_file`.
- Make chunk ids unique across multi-PDF jobs. Example: `S001-C001`, `S002-C001`.
- Update evidence item construction so multi-PDF evidence targets preserve source identity.
- Keep old single-PDF behavior compatible.

Add tests proving:

- two PDFs can produce chunks with distinct ids
- evidence items include correct `source_id` and `source_file`
- existing single-PDF tests still pass

### Phase 3: Outline Parsing

Implement a small deterministic outline parser.

Requirements:

- Accept `.md` and `.txt` outline files as UTF-8 text.
- Accept `.pdf` outline files by extracting page text with the current parser path.
- Parse sections from Markdown headings and numbered lines.
- Keep first version simple: title, order, id, optional raw text.
- Cap generated sections to a safe default such as 12 sections.
- If no usable section is found, fail with a clear error.

Do not build an editor or LLM-based outline parser in this task.

### Phase 4: Course Outline Pipeline

Add a separate function or clearly separated path for course-outline generation.

Preferred shape:

```python
run_course_outline(
    outline_path: Path,
    pdf_paths: list[Path],
    ...
) -> dict[str, Path]
```

Behavior:

1. Parse the outline into ordered sections.
2. Parse all uploaded PDFs with the selected parser backend.
3. Chunk all sources with stable `source_id`.
4. Retrieve evidence per outline section across all chunks.
5. Generate section Markdown with evidence comments.
6. Assemble a full Markdown export from all sections.
7. Write one `material_package` JSON containing sections, source files, evidence ids, quality status, and artifact filenames.

Keep the implementation conservative:

- It is acceptable to call the LLM once per section for this first version.
- It is acceptable to cap sections for cost and latency.
- It is acceptable for weakly supported sections to include a warning/status in the package.
- Do not claim batch/course-outline quality is final.

### Phase 5: FastAPI Routing

Update `POST /api/generate`:

- Add `service_mode`.
- Add repeated `pdfs` upload field for `course_outline`.
- Keep old single `pdf` field working.
- Save files under the job input directory with safe names.
- Record `service_mode` and source metadata in job metadata.
- Dispatch to the correct runner path in `run_job`.

Add source-list and multi-PDF preview endpoints:

```text
GET /api/jobs/{job_id}/pdfs
GET /api/jobs/{job_id}/pdfs/{source_id}/pdf
GET /api/jobs/{job_id}/pdfs/{source_id}/pdf-info
GET /api/jobs/{job_id}/pdfs/{source_id}/pdf-page/{page_no}.png
```

Keep existing single-PDF endpoints working:

```text
GET /api/jobs/{job_id}/pdf
GET /api/jobs/{job_id}/pdf-info
GET /api/jobs/{job_id}/pdf-page/{page_no}.png
```

For course-outline jobs, the old single-PDF endpoints may point to the first source PDF for compatibility, but the new frontend should use the source-specific endpoints.

### Phase 6: Documentation

Update only directly relevant docs:

- `README.md`
- `docs/architecture/overview.md`
- `docs/roadmap.md`

Document:

- `service_mode=course_outline`
- repeated `pdfs` upload field
- source-specific PDF preview endpoints
- package section shape
- current limitations

Do not edit deployment or Cloudflare docs.

## Out of Scope

Do not:

- build the formal frontend
- change the selected shadcn/ui template decision
- implement object storage
- implement production queue/worker
- implement payment/pricing/quota
- make MinerU the default parser
- change Cloudflare/domain/deployment settings
- turn `mode` into formal generation-mode behavior
- implement full batch courseware mode without outline
- add user history/library UI
- add tracked runtime files under `data/`

## Tests Required

Add or update tests for:

1. `POST /api/generate` rejects unsupported `service_mode`.
2. `course_outline` rejects missing outline.
3. `course_outline` rejects missing PDFs.
4. `course_outline` accepts repeated `pdfs` and creates a job.
5. Course-outline job status includes package/source preview URLs.
6. Other users cannot access source-specific PDF/package/export artifacts.
7. Pipeline writes a `material_package` with multiple source files and ordered outline sections.
8. Evidence links include `source_id` and source file identity.
9. Existing single-courseware tests still pass.

## Verification Commands

Run from repository root:

```powershell
python -m py_compile web_mvp.py mvp_runner.py apps/api/jstudy_api/app.py apps/api/jstudy_api/ui.py apps/api/jstudy_api/admin_ui.py packages/core/jstudy_core/admin_settings.py packages/core/jstudy_core/auth_db.py packages/core/jstudy_core/auth_models.py packages/core/jstudy_core/auth_service.py packages/core/jstudy_core/scenario_router.py packages/core/jstudy_core/parser_profile_router.py packages/core/jstudy_core/pipeline.py packages/core/jstudy_core/cli.py packages/core/jstudy_core/citations.py packages/core/jstudy_core/jobs.py packages/core/jstudy_core/providers.py packages/core/jstudy_core/settings.py packages/core/jstudy_core/storage.py packages/parsers/mineru_parser.py packages/parsers/pymupdf_parser.py
python -m unittest discover -s tests -v
git diff --check
```

## Stop and Report If

Stop and report instead of guessing if:

- FastAPI cannot accept optional `pdf` plus repeated `pdfs` cleanly without breaking old tests.
- Course-outline pipeline would require a broad prompt/domain redesign.
- Source-specific PDF preview endpoints require incompatible job-store changes.
- Runtime cost becomes uncontrolled because outline parsing produces too many sections.
- A change would regress auth, owner checks, upload validation, or existing single-courseware behavior.

## Required Report

Report back to Supervisor thread `019ed023-8e41-7ad0-8117-6246b8ffa0bb` in Chinese using `coordination/output_contract.md`.

Include:

1. Source Code Agent thread id.
2. Task card path.
3. API contract implemented.
4. Material package shape.
5. Changed files.
6. Tests added.
7. Verification commands and results.
8. Known limitations.
9. Requested Supervisor action.

## Suggested Prompt for This Task

```text
You are the J-Study Code Agent.

Execute:

multi-agent/jstudy-product-build/task_cards/0003-course-outline-multipdf-backend.md

The frontend direction is now mode-first. The first formal workflow is Course Outline Mode: upload outline first, then upload matching courseware PDFs. Implement the backend contract for this workflow.

Keep existing single-courseware behavior working. Add `service_mode=course_outline`, repeated `pdfs` upload support, source-specific PDF preview endpoints, outline-section material package output, section-level evidence/source identity, and tests.

Do not build final frontend, do not change deployment/domain settings, do not make MinerU default, do not turn `mode` into formal generation-mode behavior, and do not add tracked runtime data under `data/`.

Report back in Chinese to Supervisor thread 019ed023-8e41-7ad0-8117-6246b8ffa0bb.
```
