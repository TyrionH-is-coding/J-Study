# MinerU Sequence-First Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make both existing J-Study generation modes consume MinerU `ParsedDocument` objects and generate complete materials from continuous courseware-ordered learning units instead of relevance-ranked Top-K chunks.

**Architecture:** The Worker owns one immutable settings snapshot, batch-parses Job sources through a new MinerU document service, and passes normalized documents plus a frozen `courseware-manifest.v1` to deterministic learning-unit planning. The pipeline generates `material-package.v2` sections in learning-map order, while separate manifest, learning-map, and coverage-ledger artifacts preserve synchronization metadata without changing the v2 package schema.

**Tech Stack:** Python 3.11+, FastAPI, SQLModel, Pydantic v2, httpx, PyMuPDF utility layer, existing MinerU Precision Extract client/normalizer, unittest, SQLite test database, PostgreSQL-compatible SQLModel definitions.

---

## File Structure

Create:

- `packages/core/jstudy_core/courseware/__init__.py`
  - public exports for manifest, learning-map, and coverage contracts
- `packages/core/jstudy_core/courseware/models.py`
  - strict versioned Pydantic models
- `packages/core/jstudy_core/courseware/planning.py`
  - deterministic manifest snapshot and continuous learning-unit planning
- `packages/core/jstudy_core/documents/service.py`
  - MinerU batch orchestration returning normalized `ParsedDocument` objects
- `tests/test_courseware_models.py`
  - strict contract and identity tests
- `tests/test_courseware_planning.py`
  - ordering, continuity, outline mapping, and coverage tests
- `tests/test_document_service.py`
  - mocked MinerU batch orchestration and error mapping tests

Modify:

- `packages/core/jstudy_core/job_system/models.py`
  - persist display metadata independently from `source_id`
- `packages/core/jstudy_core/job_system/repository.py`
  - carry display metadata in create/read snapshots
- `packages/core/jstudy_core/job_system/service.py`
  - assign immutable identity and default display fields at admission
- `packages/core/jstudy_core/job_system/worker.py`
  - run MinerU parse, planning, generation, and artifact completion
- `packages/core/jstudy_core/pipeline.py`
  - accept normalized documents and generate in learning-map order
- `packages/core/jstudy_core/citations.py`
  - add relation and navigation policy to evidence-link output
- `packages/core/jstudy_core/storage.py`
  - expose manifest, learning-map, and coverage-ledger output paths
- `packages/core/jstudy_core/settings.py`
  - expose typed MinerU service configuration to the Worker
- `packages/core/jstudy_core/materials/generation.py`
  - generate one section from ordered unit evidence without changing v2 models
- `apps/api/jstudy_api/app.py`
  - remove public parser options and expose owner-scoped synchronization artifacts
- existing backend tests
  - update compatibility fixtures and add regressions
- current architecture, roadmap, README, and Task 0008 report
  - record actual behavior only

Do not modify:

- `apps/web/**`
- `deploy/**`
- `data/**`
- `multi-agent/jstudy-product-build/reports/supervisor_review.md`
- `.superpowers/`, `frontend/`, `game/`, `images/`, `outline_mode/`, `scripts/`

## Task 1: Add Strict Courseware Contracts

**Files:**

- Create: `packages/core/jstudy_core/courseware/__init__.py`
- Create: `packages/core/jstudy_core/courseware/models.py`
- Test: `tests/test_courseware_models.py`

- [ ] **Step 1: Write failing strict-model tests**

Cover:

```python
def test_manifest_keeps_identity_separate_from_display_order():
    manifest = CoursewareManifestV1.model_validate(
        {
            "schema_version": "courseware-manifest.v1",
            "manifest_id": "job-1",
            "job_id": "job-1",
            "service_mode": "course_outline",
            "outline": None,
            "sources": [
                {
                    "source_id": "S001",
                    "original_filename": "b.pdf",
                    "sha256": "a" * 64,
                    "display_title": "球菌",
                    "display_order": 2,
                    "primary_outline_section_id": None,
                    "title_origin": "user",
                    "order_origin": "user",
                },
                {
                    "source_id": "S002",
                    "original_filename": "a.pdf",
                    "sha256": "b" * 64,
                    "display_title": "绪论",
                    "display_order": 1,
                    "primary_outline_section_id": None,
                    "title_origin": "auto",
                    "order_origin": "auto",
                },
            ],
        }
    )
    assert [item.source_id for item in manifest.ordered_sources()] == ["S002", "S001"]
    assert manifest.sources[0].source_id == "S001"
```

Also reject:

- duplicate `source_id`
- duplicate `display_order`
- malformed SHA256
- unsupported origin values
- `page_start > page_end`
- a learning unit containing block IDs from another source
- duplicate block disposition in a coverage ledger
- numeric strings and booleans for strict integer fields

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```powershell
python -m unittest tests.test_courseware_models -v
```

Expected: import failure because the new package does not exist.

- [ ] **Step 3: Implement strict models**

Use `ConfigDict(extra="forbid", strict=True)` and literal schema versions.
Required models:

```python
class OutlineSection(StrictModel):
    id: str
    order: int
    title: str


class ManifestOutline(StrictModel):
    original_filename: str
    sha256: str
    sections: list[OutlineSection]


class ManifestSource(StrictModel):
    source_id: str
    original_filename: str
    sha256: str
    display_title: str
    display_order: int
    primary_outline_section_id: str | None
    title_origin: Literal["upload", "auto", "user"]
    order_origin: Literal["upload", "auto", "user"]


class CoursewareManifestV1(StrictModel):
    schema_version: Literal["courseware-manifest.v1"]
    manifest_id: str
    job_id: str
    service_mode: Literal["single_courseware", "course_outline"]
    outline: ManifestOutline | None
    sources: list[ManifestSource]

    def ordered_sources(self) -> list[ManifestSource]:
        return sorted(self.sources, key=lambda item: item.display_order)
```

Add equivalent strict models for:

- `LearningUnit`
- `LearningMapV1`
- `CoverageEntry`
- `CoverageMetrics`
- `CoverageLedgerV1`

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run:

```powershell
python -m unittest tests.test_courseware_models -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add packages/core/jstudy_core/courseware tests/test_courseware_models.py
git commit -m "功能：增加课件清单与学习映射合同"
```

## Task 2: Persist Stable Source Display Metadata

**Files:**

- Modify: `packages/core/jstudy_core/job_system/models.py`
- Modify: `packages/core/jstudy_core/job_system/repository.py`
- Modify: `packages/core/jstudy_core/job_system/service.py`
- Test: `tests/test_job_repository.py`
- Test: `tests/test_job_service.py`

- [ ] **Step 1: Write failing admission and repository tests**

Required assertions:

```python
assert source.source_id == "S001"
assert source.original_filename == "203-mid-02.pdf"
assert source.display_title == "203-mid-02"
assert source.display_order == 1
assert source.title_origin == "upload"
assert source.order_origin == "upload"
assert source.primary_outline_section_id is None
```

Add a repository test proving that changing display order in a test fixture never
changes `source_id` or the stored relative PDF path.

- [ ] **Step 2: Run focused tests and confirm RED**

```powershell
python -m unittest tests.test_job_repository tests.test_job_service -v
```

Expected: snapshots do not expose display fields.

- [ ] **Step 3: Add fields and snapshots**

Add to `JobSource`, `JobSourceInput`, and `JobSourceSnapshot`:

```python
display_title: str
display_order: int
primary_outline_section_id: str | None
title_origin: str
order_origin: str
```

Admission behavior:

```python
source_id = f"S{index:03d}"
display_title = Path(original_filename).stem.strip() or source_id
display_order = index
title_origin = "upload"
order_origin = "upload"
```

Do not sort repository reads by `source_id`. Return both the stable identity and
display order; consumers that need learning order sort by `display_order`.

- [ ] **Step 4: Run focused tests and confirm GREEN**

```powershell
python -m unittest tests.test_job_repository tests.test_job_service -v
```

- [ ] **Step 5: Commit**

```powershell
git add packages/core/jstudy_core/job_system/models.py packages/core/jstudy_core/job_system/repository.py packages/core/jstudy_core/job_system/service.py tests/test_job_repository.py tests/test_job_service.py
git commit -m "功能：分离课件来源身份与显示顺序"
```

## Task 3: Add the MinerU Document Service

**Files:**

- Create: `packages/core/jstudy_core/documents/service.py`
- Modify: `packages/core/jstudy_core/documents/__init__.py`
- Modify: `packages/core/jstudy_core/settings.py`
- Test: `tests/test_document_service.py`
- Test: `tests/test_settings.py`

- [ ] **Step 1: Write failing service tests**

Use `httpx.MockTransport` through the existing client injection boundary.
Verify:

- all Job PDFs are submitted in one ordered batch
- a PDF outline is parsed through MinerU with an internal outline identity and
  is not exposed as a courseware source
- Markdown/TXT outlines still use bounded strict UTF-8 reads
- MinerU `data_id` equals the stable `source_id`
- results returned by the provider in another order are restored to Manifest order
- each ZIP is normalized with the source PDF page count from the PyMuPDF utility
- returned objects are `ParsedDocument`
- timeout and provider failures preserve stable error classes
- no real network access occurs

- [ ] **Step 2: Run focused tests and confirm RED**

```powershell
python -m unittest tests.test_document_service tests.test_settings -v
```

- [ ] **Step 3: Implement `MinerUDocumentService`**

Public shape:

```python
class MinerUDocumentService:
    def __init__(
        self,
        client: MinerUPrecisionClient,
        *,
        normalizer: Callable[..., ParsedDocument] = normalize_mineru_zip,
    ) -> None: ...

    def parse(
        self,
        sources: list[DocumentSource],
        *,
        artifact_root: Path,
    ) -> list[ParsedDocument]: ...
```

`DocumentSource` carries:

```python
source_id: str
pdf_path: Path
sha256: str
```

The service may use PyMuPDF only through the existing PDF utility to validate
and count pages. It must never call `extract_pdf_pages()`.

For a PDF outline, use a reserved internal identity that cannot collide with
`S001` source identities. Normalize it through the same document service, join
its ordered page text for outline parsing, and exclude it from Manifest sources,
evidence, citation, source preview, and Material Package source IDs.

- [ ] **Step 4: Build MinerU configuration from one Worker snapshot**

Map the existing typed settings into `MinerUClientConfig` once per claim.
Reject a missing token with a stable configuration error before provider I/O.
Do not log tokens, signed URLs, local absolute paths, or document content.

- [ ] **Step 5: Run focused tests and confirm GREEN**

```powershell
python -m unittest tests.test_document_service tests.test_mineru_client tests.test_mineru_normalizer tests.test_settings -v
```

- [ ] **Step 6: Commit**

```powershell
git add packages/core/jstudy_core/documents packages/core/jstudy_core/settings.py tests/test_document_service.py tests/test_settings.py
git commit -m "功能：接入统一 MinerU 文档解析服务"
```

## Task 4: Build Deterministic Manifest and Learning Units

**Files:**

- Create: `packages/core/jstudy_core/courseware/planning.py`
- Test: `tests/test_courseware_planning.py`
- Modify: `tests/test_courseware_models.py`

- [ ] **Step 1: Write failing planning tests**

Fixtures must contain:

- two sources where source IDs and display order differ
- heading blocks at page boundaries
- a long source requiring a character-budget split
- cover/empty/unsupported blocks
- more sources than outline sections

Verify:

```python
assert [unit.primary_source_id for unit in learning_map.units] == [
    "S002",
    "S002",
    "S001",
]
assert all(unit.page_start <= unit.page_end for unit in learning_map.units)
assert coverage.metrics.usable_block_count == (
    coverage.metrics.used_block_count
    + coverage.metrics.ignored_block_count
    + coverage.metrics.duplicate_block_count
    + coverage.metrics.unsupported_block_count
)
```

- [ ] **Step 2: Run focused tests and confirm RED**

```powershell
python -m unittest tests.test_courseware_planning -v
```

- [ ] **Step 3: Implement default Manifest construction**

Build the immutable snapshot from Job and JobSource snapshots:

- preserve persisted `source_id`
- preserve `display_order`
- include source SHA256
- parse deterministic outline sections with the existing outline parser
- map source N to outline section N only when no explicit mapping exists
- leave overflow sources unmapped rather than guessing

- [ ] **Step 4: Implement learning-unit boundaries**

Initial deterministic rules:

1. never cross a source boundary
2. begin a new unit at a new heading page when the current unit is non-empty
3. begin a new unit before adding a page that would exceed the configured
   character budget
4. keep all blocks on the same page together unless one page alone exceeds the
   budget
5. preserve page and block order
6. classify empty, cover-only, auxiliary, duplicate, and unsupported blocks in
   the ledger

Do not use embedding, BM25, RRF, or an LLM in this planner.

- [ ] **Step 5: Run focused tests and confirm GREEN**

```powershell
python -m unittest tests.test_courseware_models tests.test_courseware_planning -v
```

- [ ] **Step 6: Commit**

```powershell
git add packages/core/jstudy_core/courseware tests/test_courseware_models.py tests/test_courseware_planning.py
git commit -m "功能：按课件顺序规划连续学习单元"
```

## Task 5: Switch the Worker to MinerU and Ordered Inputs

**Files:**

- Modify: `packages/core/jstudy_core/job_system/models.py`
- Modify: `packages/core/jstudy_core/job_system/worker.py`
- Modify: `packages/core/jstudy_core/storage.py`
- Test: `tests/test_job_worker.py`

- [ ] **Step 1: Write failing Worker tests**

Tests must prove:

- the Worker calls the injected document service exactly once per claim
- both service modes receive `parsed_documents`, `courseware_manifest`,
  `learning_map`, and `coverage_ledger`
- PyMuPDF text extraction is patched to raise and is never called
- Worker retry reuses stable source identity and display order
- MinerU timeout is retryable within the existing attempt limit
- invalid MinerU output is permanent and does not write completed artifacts
- stale leases cannot write manifest, map, ledger, package, or sections

- [ ] **Step 2: Run focused tests and confirm RED**

```powershell
python -m unittest tests.test_job_worker -v
```

- [ ] **Step 3: Add artifact paths and kinds**

Add versioned JSON artifacts:

```text
result-courseware-manifest.json
result-learning-map.json
result-coverage-ledger.json
```

The three artifacts are owner-scoped and immutable after completion. The
existing six public artifact requirements remain enforced.

- [ ] **Step 4: Integrate parsing and planning**

Worker claim order:

```text
load immutable settings snapshot
-> resolve Job sources and outline
-> parse all PDFs with MinerU service
-> build Courseware Manifest
-> build Learning Map and Coverage Ledger
-> invoke the selected service-mode runner
-> validate all artifacts
-> complete atomically under the current lease
```

Remove `_parser_routing()` from the production Worker call path. Keep old
profile code only if required by compatibility tests.

- [ ] **Step 5: Run focused tests and confirm GREEN**

```powershell
python -m unittest tests.test_job_worker tests.test_job_repository -v
```

- [ ] **Step 6: Commit**

```powershell
git add packages/core/jstudy_core/job_system packages/core/jstudy_core/storage.py tests/test_job_worker.py
git commit -m "功能：让任务 Worker 使用 MinerU 有序文档"
```

## Task 6: Replace Top-K Main Generation with Sequence-First Generation

**Files:**

- Modify: `packages/core/jstudy_core/pipeline.py`
- Modify: `packages/core/jstudy_core/materials/generation.py`
- Modify: `packages/core/jstudy_core/citations.py`
- Test: `tests/test_mvp_runner.py`
- Test: `tests/test_material_generation.py`

- [ ] **Step 1: Write failing generation tests**

Required fixture order:

```text
Manifest display order: S002, S001
S002 units: P1-P3, P4-P7
S001 units: P2-P5
```

Verify generated section order remains:

```text
S002 P1-P3 -> S002 P4-P7 -> S001 P2-P5
```

Patch these functions to raise if called from complete-material generation:

- `extract_pdf_pages`
- `extract_pdf_pages_with_mineru`
- `select_evidence_chunks`
- `retrieve_chunks_hybrid`

The pipeline already receives normalized documents and must not parse again.

- [ ] **Step 2: Run focused tests and confirm RED**

```powershell
python -m unittest tests.test_mvp_runner tests.test_material_generation -v
```

- [ ] **Step 3: Build unit-local evidence**

For each Learning Unit:

- preserve block order
- assign evidence IDs deterministically in unit order
- classify evidence inside the primary page span as `primary`
- allow same-source adjacent evidence as `supporting`
- mark any cross-source evidence as `cross_reference` and
  `navigation_policy=non_interactive`

Do not expose technical Evidence IDs as the only user-visible label.

- [ ] **Step 4: Generate v2 sections in Learning Map order**

Reuse the existing strict JSON-object generation and one-repair boundary.
Continue producing:

- `material-package.v2`
- deterministic Markdown
- evidence
- evidence links
- quality
- trace

Trace must identify:

```json
{
  "generation_strategy": "sequence-first",
  "manifest_schema": "courseware-manifest.v1",
  "learning_map_schema": "learning-map.v1",
  "coverage_schema": "coverage-ledger.v1"
}
```

Do not change the `material-package.v2` schema version.

- [ ] **Step 5: Keep embedding outside ordering**

Knowledge Snippet retrieval may still use embeddings. Any later relationship
discovery must be additive and cannot alter `learning_map.units`.
Tests must prove that changing mocked similarity scores does not change the
material section order.

- [ ] **Step 6: Run focused tests and confirm GREEN**

```powershell
python -m unittest tests.test_mvp_runner tests.test_material_generation tests.test_material_models -v
```

- [ ] **Step 7: Commit**

```powershell
git add packages/core/jstudy_core/pipeline.py packages/core/jstudy_core/materials/generation.py packages/core/jstudy_core/citations.py tests/test_mvp_runner.py tests/test_material_generation.py
git commit -m "功能：按连续课件单元生成完整资料"
```

## Task 7: Publish the New Owner-Scoped Contracts

**Files:**

- Modify: `apps/api/jstudy_api/app.py`
- Test: `tests/test_web_mvp.py`
- Test: `tests/test_security_controls.py`

- [ ] **Step 1: Write failing API tests**

Required behavior:

- `/api/options` returns scenarios but no public parser profile selector
- `POST /api/generate` accepts an omitted parser profile
- bounded compatibility accepts old `fast` and `quality` values without
  changing the Worker-owned MinerU parser
- unknown parser values remain rejected
- Job status exposes manifest, learning-map, and coverage URLs
- each new endpoint enforces owner isolation and private cache headers
- source list returns `source_id`, `original_filename`, `display_title`, and
  `display_order`

- [ ] **Step 2: Run focused tests and confirm RED**

```powershell
python -m unittest tests.test_web_mvp tests.test_security_controls -v
```

- [ ] **Step 3: Add endpoints**

```text
GET /api/jobs/{job_id}/manifest
GET /api/jobs/{job_id}/learning-map
GET /api/jobs/{job_id}/coverage
```

Read payloads with bounded JSON readers and strict models. Do not expose private
MinerU ZIPs, signed URLs, provider traces, absolute paths, or document content
outside the established artifacts.

- [ ] **Step 4: Run focused tests and confirm GREEN**

```powershell
python -m unittest tests.test_web_mvp tests.test_security_controls -v
```

- [ ] **Step 5: Commit**

```powershell
git add apps/api/jstudy_api/app.py tests/test_web_mvp.py tests/test_security_controls.py
git commit -m "功能：公开课件同步资料合同"
```

## Task 8: Full Regression, Documentation, and Report

**Files:**

- Modify: `README.md`
- Modify: `docs/architecture/overview.md`
- Modify: `docs/roadmap.md`
- Create: `multi-agent/jstudy-product-build/reports/0008-mineru-sequence-first-backend-report.md`
- Modify: existing tests only when required by the intentional contract change

- [ ] **Step 1: Run Python compilation**

```powershell
python -m compileall -q apps packages
```

Expected: exit code 0.

- [ ] **Step 2: Run complete backend tests**

```powershell
python -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 3: Run unchanged frontend gates**

From `apps/web`:

```powershell
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
```

Expected: all pass. These gates only prove no frontend regression; they do not
prove that the new organizer or synchronized Reader exists.

- [ ] **Step 4: Run scope and whitespace checks**

```powershell
git diff --check
git status --short
```

Confirm no forbidden path is staged.

- [ ] **Step 5: Write the report**

The report must state:

- exact start and final SHA
- exact changed files
- the parser call chain
- whether any real MinerU request was made
- focused and full test counts
- evidence that PyMuPDF text extraction is absent from the Worker path
- evidence that changing relevance scores cannot change main section order
- artifact schemas and API endpoints
- remaining limitations: organizer UI/API, HTML, migrations, deployment

- [ ] **Step 6: Commit**

```powershell
git add README.md docs/architecture/overview.md docs/roadmap.md multi-agent/jstudy-product-build/reports/0008-mineru-sequence-first-backend-report.md
git commit -m "文档：记录 MinerU 顺序生成后端合同"
```

## Self-Review Checklist

- Every approved Task 0008 requirement maps to a task above.
- No implementation step requires editing `apps/web`, deployment, runtime data,
  or the Supervisor report.
- `material-package.v2` remains immutable.
- The plan does not claim that the future organizer, HTML renderer, BYOK,
  Alembic, or production deployment is implemented.
- Mocked MinerU tests are not described as live-provider verification.
- PyMuPDF remains available for PDF utility behavior but not product text
  extraction.
- Sequence planning is deterministic and does not depend on embedding scores.
