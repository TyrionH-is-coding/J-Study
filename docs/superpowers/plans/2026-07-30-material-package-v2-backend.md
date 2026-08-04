# Material Package v2 Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace model-authored Markdown as the primary generation result with a validated `material-package.v2` JSON artifact while preserving temporary Markdown compatibility for existing API and Worker contracts.

**Architecture:** Add a focused `materials` package containing strict Pydantic models, cross-reference validation, one-repair structured generation, direct package quality auditing, and deterministic compatibility Markdown serialization. Both existing service modes generate Package v2 section blocks; the Worker and package API accept validated v2 while continuing to read legacy v1 artifacts. React rendering, HTML export, MinerU pipeline switching, database migrations, and Markdown deletion remain separate tasks.

**Tech Stack:** Python 3.11, Pydantic v2 through FastAPI, existing SiliconFlow HTTP client, SQLModel Job Worker, `unittest`.

---

## File Map

Create:

- `packages/core/jstudy_core/materials/__init__.py`: stable exports for the material contract.
- `packages/core/jstudy_core/materials/models.py`: strict Package v2, section, block, and inline-run models.
- `packages/core/jstudy_core/materials/validation.py`: job evidence/source validation and direct package quality audit.
- `packages/core/jstudy_core/materials/generation.py`: structured section prompt, JSON parsing, and one controlled repair.
- `packages/core/jstudy_core/materials/compatibility.py`: deterministic Package v2 to Markdown compatibility serializer.
- `tests/test_material_models.py`: schema and size-limit tests.
- `tests/test_material_generation.py`: generation, repair, validation, quality, and compatibility tests.

Modify:

- `packages/core/jstudy_core/providers.py`: add JSON-object chat completion without changing Markdown helper behavior.
- `packages/core/jstudy_core/pipeline.py`: generate validated Package v2 in both current service modes and derive compatibility Markdown.
- `packages/core/jstudy_core/scenario_router.py`: include stable subject metadata in routing trace.
- `packages/core/jstudy_core/job_system/worker.py`: validate and persist Package v2 sections while retaining v1 read compatibility.
- `apps/api/jstudy_api/app.py`: validate v2 package responses and publish the v2 schema in OpenAPI without breaking legacy v1 reads.
- `tests/test_mvp_runner.py`: v2 pipeline artifacts and compatibility regression.
- `tests/test_job_worker.py`: v2 completion, section persistence, and rejection tests.
- `tests/test_web_mvp.py`: owner-scoped package response and OpenAPI contract.
- `tests/test_scenario_router.py`: subject routing metadata.
- `README.md`, `docs/architecture/overview.md`, `docs/roadmap.md`: implemented contract and remaining compatibility boundary.
- `multi-agent/jstudy-product-build/reports/0007-material-package-v2-backend-report.md`: execution report.

Do not modify `apps/web/**`, database tables, deployment files, parser selection, or runtime assets.

### Task 1: Define the strict Package v2 models

**Files:**
- Create: `packages/core/jstudy_core/materials/__init__.py`
- Create: `packages/core/jstudy_core/materials/models.py`
- Test: `tests/test_material_models.py`

- [ ] **Step 1: Write failing model tests**

Cover one valid package containing every initial block and inline-run type:

```python
payload = {
    "schema_version": "material-package.v2",
    "package_id": "job-123",
    "service_mode": "course_outline",
    "title": "课程学习资料",
    "subject": "medicine",
    "language": "zh-CN",
    "source_ids": ["S001"],
    "sections": [{
        "id": "section-001",
        "order": 1,
        "title": "绪论",
        "status": "generated",
        "quality": {
            "evidence_status": "sufficient",
            "evidence_count": 1,
            "cited_evidence_count": 1,
            "citation_coverage": 1.0
        },
        "source_ids": ["S001"],
        "evidence_ids": ["E001"],
        "blocks": [{
            "id": "block-001",
            "type": "paragraph",
            "runs": [
                {"type": "text", "text": "正文"},
                {"type": "citation", "evidence_id": "E001"}
            ]
        }]
    }],
    "rendering": {
        "default_theme": {
            "theme_id": "clinical-standard",
            "theme_version": "1.0.0"
        }
    }
}
```

Also assert rejection of:

- extra fields such as `raw_html`, `html`, `css`, and `script`;
- unknown block or run types;
- duplicate section ids/orders and duplicate block ids;
- heading levels other than 3 or 4;
- callout variants outside `key_point`, `note`, `warning`;
- more than 12 table columns, 100 rows, 120 blocks per section, or 8,000 characters in one text run;
- empty generated sections; empty blocks are allowed only for `failed`.

- [ ] **Step 2: Run the focused test and confirm RED**

```powershell
python -m unittest tests.test_material_models -v
```

Expected: import/model failures because the materials package does not exist.

- [ ] **Step 3: Implement strict Pydantic models**

Use `ConfigDict(extra="forbid")` on every public model. Define discriminated unions for:

```python
InlineRun = TextRun | StrongRun | EmphasisRun | InlineCodeRun | InlineFormulaRun | CitationRun
MaterialBlock = HeadingBlock | ParagraphBlock | ListBlock | TableBlock | CalloutBlock | FormulaBlock
```

Use these stable enum values:

```text
service_mode: single_courseware | course_outline
section status: generated | weak_evidence | failed
evidence status: sufficient | weak | failed
language: nonempty BCP-47-like string, initially zh-CN
```

Keep `full-material` for the single-courseware section id. Course-outline ids remain the deterministic outline ids such as `section-001`.

- [ ] **Step 4: Run model tests and confirm GREEN**

```powershell
python -m unittest tests.test_material_models -v
```

- [ ] **Step 5: Commit**

```powershell
git add packages/core/jstudy_core/materials tests/test_material_models.py
git commit -m "功能：定义资料包 v2 类型合同"
```

### Task 2: Add cross-reference validation, quality audit, and compatibility Markdown

**Files:**
- Create: `packages/core/jstudy_core/materials/validation.py`
- Create: `packages/core/jstudy_core/materials/compatibility.py`
- Test: `tests/test_material_generation.py`

- [ ] **Step 1: Write failing validation tests**

Test `validate_material_package(package, evidence, allowed_source_ids)` for:

- every package `source_id` belongs to the current job;
- every section source is declared at package level;
- every section evidence id exists in the current job;
- every citation run appears in that section's `evidence_ids`;
- unknown evidence and source ids fail with a stable validation code;
- retrying the same valid payload preserves section order and ids.

Test `audit_material_package()` returns:

```json
{
  "status": "pass",
  "metrics": {
    "section_count": 1,
    "generated_section_count": 1,
    "evidence_count": 1,
    "referenced_evidence_count": 1,
    "citation_coverage": 1.0
  },
  "issues": []
}
```

Warnings may report unused evidence or weak sections. Unknown citations are validation errors, not warnings.

- [ ] **Step 2: Write failing compatibility serializer tests**

`render_compatibility_markdown(package)` must:

- preserve section order;
- render headings, paragraphs, lists, tables, callouts, and formulas deterministically;
- convert citation runs to transitional `<!-- evidence: E001 -->` comments;
- never copy arbitrary HTML fields because the schema rejects them.

- [ ] **Step 3: Run focused tests and confirm RED**

```powershell
python -m unittest tests.test_material_generation -v
```

- [ ] **Step 4: Implement validation and direct quality audit**

Do not parse Markdown or HTML. Traverse typed sections, blocks, and citation runs. Return stable public issue codes such as:

```text
unknown_source_id
unknown_evidence_id
undeclared_section_evidence
unused_evidence
weak_evidence_section
failed_section
```

- [ ] **Step 5: Implement deterministic compatibility Markdown**

This serializer exists only for `/output`, the existing Markdown export, evidence-links compatibility, and current Worker artifact requirements. It must not become the HTML renderer.

- [ ] **Step 6: Run tests and confirm GREEN**

```powershell
python -m unittest tests.test_material_models tests.test_material_generation -v
```

- [ ] **Step 7: Commit**

```powershell
git add packages/core/jstudy_core/materials tests/test_material_generation.py
git commit -m "功能：校验资料包证据并生成兼容文本"
```

### Task 3: Add structured section generation with one controlled repair

**Files:**
- Modify: `packages/core/jstudy_core/providers.py`
- Create or modify: `packages/core/jstudy_core/materials/generation.py`
- Test: `tests/test_material_generation.py`

- [ ] **Step 1: Write failing provider and repair tests**

Verify the provider request includes:

```json
"response_format": {"type": "json_object"}
```

The official SiliconFlow JSON-mode contract is documented at:

```text
https://docs.siliconflow.cn/en/userguide/guides/json-mode
```

Test:

- valid JSON object returns a typed section;
- malformed JSON receives exactly one repair call;
- schema-invalid JSON receives exactly one repair call containing only safe validation summaries;
- a second invalid result returns a deterministic `failed` section with no model text copied into blocks;
- provider/network exceptions propagate so the existing Worker retry policy remains effective;
- raw model responses and credentials are never included in public errors or package output.

- [ ] **Step 2: Run focused tests and confirm RED**

```powershell
python -m unittest tests.test_material_generation -v
```

- [ ] **Step 3: Add `providers.generate_json_object()`**

Keep `generate_markdown()` unchanged for compatibility. The new helper should:

1. call `chat/completions`;
2. request JSON mode;
3. parse `choices[0].message.content` with `json.loads`;
4. require a JSON object;
5. raise a bounded error without embedding the full provider response.

- [ ] **Step 4: Implement section generation**

Build a generic output-format instruction around the selected Soul and evidence. Domain/Soul decides teaching content; the material schema decides output shape. Only validation failures get one format-repair attempt.

For sections with no evidence, do not call the model. Produce `weak_evidence` with a deterministic `note` callout that states the uploaded materials do not currently provide enough support.

- [ ] **Step 5: Run focused tests and confirm GREEN**

```powershell
python -m unittest tests.test_material_generation -v
```

- [ ] **Step 6: Commit**

```powershell
git add packages/core/jstudy_core/providers.py packages/core/jstudy_core/materials tests/test_material_generation.py
git commit -m "功能：增加结构化章节生成与受控修复"
```

### Task 4: Switch both pipelines to Package v2 while retaining compatibility artifacts

**Files:**
- Modify: `packages/core/jstudy_core/pipeline.py`
- Modify: `packages/core/jstudy_core/scenario_router.py`
- Modify: `tests/test_mvp_runner.py`
- Modify: `tests/test_scenario_router.py`

- [ ] **Step 1: Write failing pipeline contract tests**

For `single_courseware` and `course_outline`, assert:

- `result-package.json` has `schema_version=material-package.v2`;
- Package id is the Worker job id when supplied;
- single mode keeps section id `full-material`;
- course-outline ids and order match the parsed outline;
- package `source_ids` use `S001`, `S002`, never filenames;
- evidence ids and citation runs validate;
- Package v2 is the source of the compatibility Markdown;
- quality JSON comes from block/citation traversal;
- evidence-links continue to map citations to `source_id + page + chunk_id`;
- no provider output is treated as raw HTML.

- [ ] **Step 2: Run focused tests and confirm RED**

```powershell
python -m unittest tests.test_mvp_runner tests.test_scenario_router -v
```

- [ ] **Step 3: Add additive pipeline arguments**

Add optional, backward-compatible arguments:

```python
package_id: str | None = None
section_generator: Callable[..., MaterialSection] | None = None
```

The Worker supplies `package_id=job.id`. Direct tests and legacy callers may use `output_prefix` as the fallback id.

- [ ] **Step 4: Generate Package v2 first**

The generation order becomes:

```text
evidence -> structured sections -> validated package -> direct quality
         -> compatibility Markdown -> compatibility evidence links
```

Do not generate independent model-authored Markdown in parallel.

- [ ] **Step 5: Add subject to scenario trace metadata**

Use the resolved scenario or content pack subject. Package theme remains fixed to `clinical-standard@1.0.0`; it does not enter prompts or retrieval.

- [ ] **Step 6: Run focused regression and confirm GREEN**

```powershell
python -m unittest tests.test_material_models tests.test_material_generation tests.test_mvp_runner tests.test_scenario_router -v
```

- [ ] **Step 7: Commit**

```powershell
git add packages/core/jstudy_core/pipeline.py packages/core/jstudy_core/scenario_router.py tests/test_mvp_runner.py tests/test_scenario_router.py
git commit -m "功能：让现有生成管线输出资料包 v2"
```

### Task 5: Make Worker and package API v2-aware

**Files:**
- Modify: `packages/core/jstudy_core/job_system/worker.py`
- Modify: `apps/api/jstudy_api/app.py`
- Modify: `tests/test_job_worker.py`
- Modify: `tests/test_web_mvp.py`

- [ ] **Step 1: Write failing Worker tests**

Assert:

- validated v2 sections persist atomically with artifacts and terminal completion;
- Worker uses package section ids/order/status/quality/source ids/evidence ids;
- compatibility Markdown artifact remains required in this task;
- wrong service mode, unknown evidence/source, duplicate ids/orders, or malformed v2 fails with `invalid_job_output`;
- no artifacts or sections are committed after invalid output or stale lease;
- a legacy v1 package fixture still completes.

- [ ] **Step 2: Write failing API and OpenAPI tests**

Assert:

- owner receives the validated v2 payload;
- non-owner remains blocked;
- malformed persisted v2 never becomes an unvalidated public response;
- legacy v1 payload remains readable during migration;
- OpenAPI contains `MaterialPackageV2`, section, block, and citation schemas.

- [ ] **Step 3: Run focused tests and confirm RED**

```powershell
python -m unittest tests.test_job_worker tests.test_web_mvp tests.test_security_controls -v
```

- [ ] **Step 4: Implement v2 Worker parsing**

Use the shared Pydantic contract instead of duplicating v2 field parsing in `worker.py`. Keep the legacy v1 branch small and explicitly marked for later deletion.

The Worker should pass `package_id=job.id` to both current runners.

- [ ] **Step 5: Implement typed package response**

Expose a response union for validated v2 and the bounded legacy v1 contract. Do not add a second package endpoint and do not change owner checks or cache headers.

- [ ] **Step 6: Run focused tests and confirm GREEN**

```powershell
python -m unittest tests.test_job_worker tests.test_web_mvp tests.test_security_controls -v
```

- [ ] **Step 7: Commit**

```powershell
git add packages/core/jstudy_core/job_system/worker.py apps/api/jstudy_api/app.py tests/test_job_worker.py tests/test_web_mvp.py
git commit -m "功能：持久化并公开资料包 v2"
```

### Task 6: Document, verify, and report

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture/overview.md`
- Modify: `docs/roadmap.md`
- Create: `multi-agent/jstudy-product-build/reports/0007-material-package-v2-backend-report.md`

- [ ] **Step 1: Update contract documentation**

Record:

- new jobs produce `material-package.v2`;
- Markdown is derived compatibility output, not the primary source;
- package endpoint is owner-scoped and v2-validated;
- HTML renderer, HTML export, MinerU switch, and Markdown deletion remain pending;
- no database migration was introduced.

Correct the stale roadmap claim that section browsing is currently implemented in the rebuilt frontend.

- [ ] **Step 2: Run full backend verification**

```powershell
python -m compileall -q apps packages
python -m unittest discover -s tests -v
```

- [ ] **Step 3: Run unchanged frontend regression**

```powershell
Set-Location apps/web
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
Set-Location ../..
```

- [ ] **Step 4: Run repository checks**

```powershell
git diff --check
git status --short
```

Confirm no changes under:

```text
apps/web/**
deploy/**
data/**
frontend/**
game/**
images/**
outline_mode/**
scripts/**
multi-agent/jstudy-product-build/reports/supervisor_review.md
```

- [ ] **Step 5: Write the Task 0007 report**

Include exact baseline/final SHAs, test counts, package schema decisions, repair behavior, compatibility boundaries, skipped work, and any live-provider limitation.

- [ ] **Step 6: Commit documentation**

```powershell
git add README.md docs/architecture/overview.md docs/roadmap.md multi-agent/jstudy-product-build/reports/0007-material-package-v2-backend-report.md
git commit -m "文档：记录资料包 v2 后端合同"
```

## Completion Gate

Task 0007 is complete only when:

1. both current service modes write validated `material-package.v2`;
2. the model is never asked to produce raw HTML;
3. invalid block, source, evidence, or citation references are rejected;
4. format repair occurs at most once;
5. direct package quality no longer parses Markdown;
6. compatibility Markdown is deterministically derived from v2;
7. Worker atomic completion and owner isolation still pass;
8. legacy v1 package reads remain compatible;
9. OpenAPI publishes the v2 schema;
10. full backend and unchanged frontend suites pass.
