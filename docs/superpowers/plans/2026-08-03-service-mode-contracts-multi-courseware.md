# Service Mode Contracts And Multi Courseware Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce the three user-confirmed service-mode input contracts and add a production `multi_courseware` backend path that generates the existing sequence-first synchronization artifacts and `material-package.v2` from at least two ordered PDFs.

**Architecture:** Admission remains the only authority for valid Job shape. FastAPI maps multipart fields into that contract, the Worker batch-parses all accepted PDFs through the existing MinerU document service, and a dedicated multi-courseware runner consumes the frozen Manifest, Learning Map, and Coverage Ledger. The initial multi-courseware path deliberately performs no cross-courseware association; the ordered main material is usable even while association methods remain an experiment.

**Tech Stack:** Python 3.11+, FastAPI, SQLModel, Pydantic v2, existing MinerU Precision Extract service, existing Job Worker and lease model, existing `courseware-manifest.v1`, `learning-map.v1`, `coverage-ledger.v1`, `material-package.v2`, unittest.

---

## Product Decisions

Authoritative product documents:

- `docs/product/service-modes.md`
- `docs/product/study-materials.md`

Task 0009 implements only these confirmed contracts:

| `service_mode` | Accepted multipart input | Rejected input |
|---|---|---|
| `single_courseware` | exactly one `pdf` | `outline`, repeated `pdfs`, zero or multiple PDFs |
| `course_outline` | exactly one `outline`, one or more repeated `pdfs` | singular `pdf`, missing outline |
| `multi_courseware` | two or more repeated `pdfs` | `outline`, singular `pdf`, fewer than two PDFs |

All three modes:

- use the same MinerU-only Worker extraction path;
- preserve stable `source_id`;
- preserve upload order as initial `display_order`;
- generate Manifest, Learning Map, Coverage Ledger, package, Markdown compatibility, evidence, quality, and trace artifacts;
- remain sequence-first.

`multi_courseware` in this task does **not** discover or render cross-courseware
associations. That experiment has not selected a production algorithm.

## File Structure

Modify:

- `packages/core/jstudy_core/courseware/models.py`
  - add `multi_courseware` to the strict Manifest contract and validate per-mode
    source/outline shape
- `packages/core/jstudy_core/materials/models.py`
  - add `multi_courseware` to `MaterialPackageV2` only
- `packages/core/jstudy_core/job_system/service.py`
  - enforce all three admission shapes
- `apps/api/jstudy_api/app.py`
  - enforce multipart field names, expose service-mode options, and pass repeated
    PDFs for outline and multi-courseware Jobs
- `packages/core/jstudy_core/pipeline.py`
  - add a sequence-only `run_multi_courseware()` wrapper
- `packages/core/jstudy_core/job_system/worker.py`
  - dispatch `multi_courseware` to the dedicated runner
- affected backend tests
- `README.md`
- `docs/architecture/overview.md`
- `docs/roadmap.md`
- `docs/product/service-modes.md`
- `multi-agent/jstudy-product-build/reports/0009-service-mode-contracts-multi-courseware-report.md`

Do not modify:

- `apps/web/**`
- `deploy/**`
- `data/**`
- Soul Profile or Knowledge Snippet content
- cross-courseware association or retrieval algorithms
- HTML, Markdown, or PDF renderer implementation
- Alembic or database topology
- protected existing dirty/untracked paths

## Task 1: Freeze The Three Strict Domain Contracts

**Files:**

- Modify: `packages/core/jstudy_core/courseware/models.py`
- Modify: `packages/core/jstudy_core/materials/models.py`
- Test: `tests/test_courseware_models.py`
- Test: `tests/test_material_models.py`

- [ ] **Step 1: Add failing strict-model tests**

Add tests proving:

```python
CoursewareManifestV1.model_validate(
    {
        "schema_version": "courseware-manifest.v1",
        "manifest_id": "job-1",
        "job_id": "job-1",
        "service_mode": "multi_courseware",
        "outline": None,
        "sources": [source_s001, source_s002],
    }
)
```

is valid, while the following are invalid:

- `single_courseware` with an outline;
- `single_courseware` with zero or two sources;
- `course_outline` without an outline;
- `multi_courseware` with an outline;
- `multi_courseware` with fewer than two sources.

Also prove `MaterialPackageV2` accepts `multi_courseware`, while
`LegacyMaterialPackageV1` remains bounded to its existing migration modes.

- [ ] **Step 2: Confirm RED**

```powershell
python -m unittest tests.test_courseware_models tests.test_material_models -v
```

Expected: `multi_courseware` is rejected and per-mode shape is not fully
validated.

- [ ] **Step 3: Implement the minimum model changes**

Update the v1 Manifest literal:

```python
service_mode: Literal[
    "single_courseware",
    "course_outline",
    "multi_courseware",
]
```

In `validate_manifest()`, enforce the exact source/outline shape for each mode.
Do not infer or convert one mode to another.

Update only the v2 package literal:

```python
service_mode: Literal[
    "single_courseware",
    "course_outline",
    "multi_courseware",
]
```

Do not broaden the legacy v1 package.

- [ ] **Step 4: Confirm GREEN**

```powershell
python -m unittest tests.test_courseware_models tests.test_material_models -v
```

- [ ] **Step 5: Commit**

```powershell
git add packages/core/jstudy_core/courseware/models.py packages/core/jstudy_core/materials/models.py tests/test_courseware_models.py tests/test_material_models.py
git commit -m "功能：增加三种资料工作流严格合同"
```

## Task 2: Enforce Admission And Multipart Boundaries

**Files:**

- Modify: `packages/core/jstudy_core/job_system/service.py`
- Modify: `apps/api/jstudy_api/app.py`
- Test: `tests/test_job_service.py`
- Test: `tests/test_web_mvp.py`
- Test: `tests/test_security_controls.py` only if an existing generic ownership
  test needs a multi-courseware fixture

- [ ] **Step 1: Add failing admission tests**

Required service-level matrix:

```text
single: 1 PDF + no outline -> accepted
single: outline -> invalid_outline
single: 2 PDFs -> invalid_pdf
outline: outline + 1..max PDFs -> accepted
outline: no outline -> invalid_outline
multi: 2..max PDFs + no outline -> accepted
multi: 1 PDF -> invalid_pdf
multi: outline -> invalid_outline
```

The tests must also prove that failed admission:

- creates no Job row;
- leaves no Job input directory;
- does not consume an idempotency key.

- [ ] **Step 2: Add failing HTTP contract tests**

The public multipart contract is intentionally explicit:

```python
# single
files={"pdf": ("single.pdf", pdf_bytes, "application/pdf")}

# outline
files=[
    ("outline", ("outline.md", outline_bytes, "text/markdown")),
    ("pdfs", ("one.pdf", pdf_one, "application/pdf")),
]

# multi
files=[
    ("pdfs", ("one.pdf", pdf_one, "application/pdf")),
    ("pdfs", ("two.pdf", pdf_two, "application/pdf")),
]
```

Reject mixed field shapes before submission:

- `single_courseware` with repeated `pdfs`;
- `course_outline` or `multi_courseware` with singular `pdf`;
- any forbidden outline.

Responses must use stable structured admission errors and must not create a Job.

Add `/api/options` assertions for:

```json
{
  "default_service_mode": "single_courseware",
  "service_modes": [
    {"id": "single_courseware", "enabled": true},
    {"id": "course_outline", "enabled": true},
    {"id": "multi_courseware", "enabled": true}
  ]
}
```

Keep labels concise and product-facing. Do not add parser choice or scenario
auto-detection.

- [ ] **Step 3: Confirm RED**

```powershell
python -m unittest tests.test_job_service tests.test_web_mvp -v
```

- [ ] **Step 4: Implement service validation**

Set:

```python
SUPPORTED_SERVICE_MODES = frozenset(
    {"single_courseware", "course_outline", "multi_courseware"}
)
```

Use existing error codes where their semantics are already correct:

- PDF count/field problems: `invalid_pdf`;
- outline presence/absence/extension problems: `invalid_outline`.

Keep detailed safe messages so the frontend can direct the user to the correct
mode. Do not add a second mode-normalization layer.

- [ ] **Step 5: Implement FastAPI multipart mapping**

Normalize non-empty uploads once, then validate field family:

```python
single_pdf = pdf if pdf is not None and pdf.filename else None
repeated_pdfs = tuple(
    item for item in (pdfs or []) if item is not None and item.filename
)
```

Map:

- single -> singular upload only;
- outline -> repeated uploads plus outline;
- multi -> repeated uploads only.

Do not silently ignore a populated field that is forbidden for the selected
mode.

- [ ] **Step 6: Confirm GREEN**

```powershell
python -m unittest tests.test_job_service tests.test_web_mvp tests.test_security_controls -v
```

- [ ] **Step 7: Commit**

```powershell
git add apps/api/jstudy_api/app.py packages/core/jstudy_core/job_system/service.py tests/test_job_service.py tests/test_web_mvp.py tests/test_security_controls.py
git commit -m "功能：收紧工作流上传与准入边界"
```

## Task 3: Add The Sequence-Only Multi-Courseware Runner

**Files:**

- Modify: `packages/core/jstudy_core/pipeline.py`
- Test: `tests/test_mvp_runner.py`

- [ ] **Step 1: Add a failing runner test**

Construct two normalized `ParsedDocument` fixtures and their frozen
Manifest/Map/Coverage bundle. Assert:

- source order follows Manifest `display_order`;
- unit and section order follows Learning Map;
- package mode is `multi_courseware`;
- every section remains source-scoped;
- package title is `多课件学习资料`;
- all current compatibility artifacts are written;
- no embedding, BM25, RRF, or cross-source association function is called.

- [ ] **Step 2: Confirm RED**

```powershell
python -m unittest tests.test_mvp_runner -v
```

Expected: `run_multi_courseware` does not exist.

- [ ] **Step 3: Implement `run_multi_courseware()`**

The new runner must require:

```python
parsed_documents: Sequence[ParsedDocument]
courseware_manifest: CoursewareManifestV1
learning_map: LearningMapV1
coverage_ledger: CoverageLedgerV1
```

It must call the existing `_run_sequence_first()` with:

```python
service_mode="multi_courseware"
```

Do not add a legacy PyMuPDF/RAG branch and do not invent association output.

- [ ] **Step 4: Confirm GREEN**

```powershell
python -m unittest tests.test_mvp_runner -v
```

- [ ] **Step 5: Commit**

```powershell
git add packages/core/jstudy_core/pipeline.py tests/test_mvp_runner.py
git commit -m "功能：增加多课件顺序生成管线"
```

## Task 4: Dispatch Multi-Courseware Jobs Through The Worker

**Files:**

- Modify: `packages/core/jstudy_core/job_system/worker.py`
- Test: `tests/test_job_worker.py`
- Test: `tests/test_web_mvp.py`

- [ ] **Step 1: Add failing Worker tests**

Prove that a `multi_courseware` Job:

- uses one batch MinerU parse for all ordered sources;
- invokes only `multi_runner`;
- receives the immutable settings snapshot and frozen coordination bundle;
- writes Manifest, Learning Map, Coverage, package, Markdown, evidence, links,
  quality, trace, and sections;
- reaches `completed` only through the existing lease-protected atomic
  completion;
- fails permanently with `invalid_job_output` if the returned package reports a
  different service mode or mutates the coordination bundle.

Also prove that two sources retain their admission-time `source_id` and initial
upload `display_order`.

- [ ] **Step 2: Confirm RED**

```powershell
python -m unittest tests.test_job_worker tests.test_web_mvp -v
```

- [ ] **Step 3: Add the dedicated runner dependency**

Constructor shape:

```python
multi_runner: Runner = run_multi_courseware
```

Pass it through runtime-settings cloning and select it only for
`job.service_mode == "multi_courseware"`.

Reuse the current MinerU document service, planning, validation, artifact
hashing, and atomic completion. Do not duplicate those mechanisms.

- [ ] **Step 4: Confirm GREEN**

```powershell
python -m unittest tests.test_job_worker tests.test_web_mvp -v
```

- [ ] **Step 5: Commit**

```powershell
git add packages/core/jstudy_core/job_system/worker.py tests/test_job_worker.py tests/test_web_mvp.py
git commit -m "功能：接入多课件 Worker 正式路径"
```

## Task 5: Document Actual Behavior And Run All Gates

**Files:**

- Modify: `README.md`
- Modify: `docs/architecture/overview.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/product/service-modes.md`
- Create: `multi-agent/jstudy-product-build/reports/0009-service-mode-contracts-multi-courseware-report.md`

- [ ] **Step 1: Update only implemented-state documentation**

Document:

- the exact multipart contract;
- all three implemented service modes;
- MinerU-only Worker extraction;
- sequence-first multi-courseware baseline;
- cross-courseware associations remain an experiment and are absent from Task
  0009 output;
- current `medicine-default` remains until a real general Soul exists.

Do not mark frontend, organizer, association, HTML/PDF, deployment, or general
mode as completed.

- [ ] **Step 2: Run backend verification**

```powershell
python -m compileall -q apps packages
python -m unittest discover -s tests -v
```

- [ ] **Step 3: Run frontend regression gates**

```powershell
Set-Location apps/web
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
Set-Location ../..
```

These prove no regression only. They do not prove the unimplemented frontend
workflow.

- [ ] **Step 4: Run repository checks**

```powershell
git diff --check
git status --short
```

Confirm that no protected path, runtime data, secret, upload, database, MinerU
result, or generated Job artifact is staged.

- [ ] **Step 5: Write the completion report**

The report must include:

- exact start and final SHA;
- phase-by-phase implementation;
- changed files;
- RED/GREEN evidence;
- complete verification counts;
- skipped live MinerU/PostgreSQL/deployment tests;
- explicit statement that cross-courseware association is not implemented;
- requested Supervisor verdict.

- [ ] **Step 6: Final commit**

```powershell
git add README.md docs/architecture/overview.md docs/roadmap.md docs/product/service-modes.md multi-agent/jstudy-product-build/reports/0009-service-mode-contracts-multi-courseware-report.md
git commit -m "文档：记录多课件后端工作流基线"
```

## Final Self-Review

- [ ] Every accepted Job matches exactly one service mode.
- [ ] Forbidden multipart fields are rejected, not ignored.
- [ ] Failed admission creates no Job and no input residue.
- [ ] Multi-courseware requires at least two PDFs and no outline.
- [ ] MinerU remains the only Worker text/structure parser.
- [ ] The multi runner has no legacy PyMuPDF/RAG fallback.
- [ ] Learning Map and package order remain sequence-first.
- [ ] No cross-courseware association algorithm or UI contract was invented.
- [ ] Existing owner checks and private cache rules cover all artifacts.
- [ ] Legacy package v1 was not broadened.
- [ ] No placeholder, TODO, empty implementation, secret, or runtime data was
  committed.
