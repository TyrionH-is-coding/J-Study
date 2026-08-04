# Task 0007: Material Package v2 Backend

## Supervisor Thread

`019fa956-f165-76b0-b49d-9462d2f52328`

## Required Code Baseline

Branch:

```text
feature/backend-frontend-mvp
```

Required source-code baseline:

```text
28acb39dffffc9214791d3f94cda46c18810923b
```

The Supervisor planning commit that adds this task card and its implementation
plan is allowed on top of that source-code baseline. Before editing, confirm
that no production or test code changed between `28acb39...` and the planning
commit, then record the dirty worktree. Do not reset, clean, rebase, merge, or
overwrite existing user/Supervisor files.

## Goal

Make `material-package.v2` the validated primary backend generation artifact for `single_courseware` and `course_outline`, with section blocks and structural citations, while retaining deterministic Markdown compatibility for current APIs.

## Authoritative Design and Plan

Read before implementation:

```text
docs/architecture/material-package-html-rendering.md
docs/superpowers/plans/2026-07-30-material-package-v2-backend.md
docs/architecture/refactor-blueprint.md
multi-agent/jstudy-product-build/reports/0006-job-persistence-worker-report.md
```

SiliconFlow JSON mode reference:

```text
https://docs.siliconflow.cn/en/userguide/guides/json-mode
```

Use `response_format={"type":"json_object"}` plus strict local validation. Do not assume every configured model provides server-enforced JSON Schema.

## Allowed Scope

Create:

```text
packages/core/jstudy_core/materials/**
tests/test_material_models.py
tests/test_material_generation.py
multi-agent/jstudy-product-build/reports/0007-material-package-v2-backend-report.md
```

Modify only as required:

```text
packages/core/jstudy_core/providers.py
packages/core/jstudy_core/pipeline.py
packages/core/jstudy_core/scenario_router.py
packages/core/jstudy_core/job_system/worker.py
apps/api/jstudy_api/app.py
tests/test_mvp_runner.py
tests/test_scenario_router.py
tests/test_job_worker.py
tests/test_web_mvp.py
tests/test_security_controls.py
README.md
docs/architecture/overview.md
docs/roadmap.md
```

## Out of Scope

Do not implement or modify:

- `apps/web/**`
- React Material Renderer
- HTML export or theme UI
- `clinical-standard` CSS/tokens
- login/signup pages or frontend visual work
- MinerU pipeline switch or parser default
- public parser choice removal
- database schema or migration
- Job state machine semantics
- Docker/Compose/deployment
- multiple themes
- Markdown endpoint deletion
- legacy CLI cleanup
- Knowledge Snippet feedback
- Batch Courseware Mode

Do not touch:

```text
multi-agent/jstudy-product-build/reports/supervisor_review.md
.superpowers/
frontend/
game/
images/
outline_mode/
scripts/
data/
```

## Required Contract

### Package

New generation outputs must use:

```text
schema_version = material-package.v2
```

Top-level required fields:

```text
schema_version
package_id
service_mode
title
subject
language
source_ids
sections
rendering.default_theme.theme_id
rendering.default_theme.theme_version
```

Initial block types:

```text
heading
paragraph
list
table
callout
formula
```

Initial inline-run types:

```text
text
strong
emphasis
inline_code
inline_formula
citation
```

Use strict Pydantic models with unknown fields forbidden. There is no raw HTML, CSS, script, iframe, URL, image, or custom component field.

### Stable Identities

- Worker supplies `package_id=job.id`.
- Single Courseware keeps `full-material`.
- Course Outline keeps deterministic outline section ids and order.
- Sources use `S001`, `S002`; filenames are display metadata only.
- Block ids are unique within a section.
- Retry must not renumber sources or planned sections.

### Limits

Enforce at least:

- 120 blocks per section;
- 8,000 characters per text-bearing run;
- table maximum 12 columns and 100 rows;
- heading level only 3 or 4;
- callout variant only `key_point`, `note`, or `warning`.

### Evidence and Quality

- Package and section source ids must belong to the current Job.
- Section evidence ids must belong to current Job evidence.
- Citation runs must reference ids declared by that section.
- Unknown evidence/source/citation references fail validation.
- Quality is calculated from typed blocks and citations, not Markdown parsing.
- Weak-evidence sections remain explicit and do not become hard Job failures.

### Structured Generation

- Add a JSON-object provider helper without changing existing provider helpers.
- Model output is parsed and locally validated.
- Schema/format failure allows at most one controlled repair call.
- A second invalid response produces a deterministic `failed` section without copying raw model output into public artifacts.
- Network/provider exceptions continue through the existing Worker retry path.
- Raw provider responses may not enter package, public API, logs, or safe error messages.

### Compatibility

- Package v2 is the primary content source.
- Current Markdown output is deterministically serialized from Package v2.
- Existing `/output`, `/export`, evidence-links, and required Markdown artifact remain during this task.
- Existing legacy v1 package artifacts remain readable.
- Do not maintain two independent model-authored content sources.

### Worker and API

- Worker validates v2 before atomic artifact/section completion.
- Invalid package output fails with `invalid_job_output` and writes no new artifacts/sections.
- Stale lease behavior remains unchanged.
- `GET /api/jobs/{job_id}/package` keeps owner checks and private cache behavior.
- OpenAPI publishes Package v2, section, block, and citation schemas.
- Legacy v1 package response remains bounded and compatible.

## TDD and Phase Order

Execute the implementation plan in order:

1. strict models;
2. cross-reference validation and quality;
3. compatibility Markdown;
4. JSON generation and one repair;
5. pipeline integration;
6. Worker/API integration;
7. docs and full verification.

For each phase:

1. write the focused failing test;
2. run it and record the expected RED reason;
3. implement the smallest change;
4. run focused GREEN;
5. commit with a Chinese commit message.

Do not weaken, skip, or delete tests to obtain a pass.

## Verification

Backend:

```powershell
. "$env:USERPROFILE\.codex\scripts\Enter-CodexUtf8.ps1"
$env:PYTHONUTF8=1
$env:PYTHONIOENCODING="utf-8"
python -m compileall -q apps packages
python -m unittest discover -s tests -v
```

Frontend regression from `apps/web`:

```powershell
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
```

Repository:

```powershell
git diff --check
git status --short
git diff --stat 28acb39dffffc9214791d3f94cda46c18810923b
```

No live SiliconFlow request is required for PASS. Provider tests must use deterministic injected responses or mocked transport and must not read a real key.

## Required Report

Create:

```text
multi-agent/jstudy-product-build/reports/0007-material-package-v2-backend-report.md
```

Use:

1. Task
2. Summary
3. Changed Files
4. Verification
5. Risks and Limitations
6. Requested Supervisor Action

Report:

- baseline and final SHA;
- exact test counts;
- Package v2 model and limits;
- section generation and repair behavior;
- evidence/source/citation validation;
- direct quality calculation;
- compatibility Markdown boundary;
- Worker atomic completion;
- API/OpenAPI contract;
- legacy v1 behavior;
- excluded/deferred work;
- whether live provider calls were skipped.

Request one verdict:

```text
PASS
PASS_WITH_LIMITATIONS
REVISE
REJECT
```

## Acceptance Gate

Request review only when:

1. both current service modes generate validated Package v2;
2. invalid structure and references are rejected;
3. format repair occurs no more than once;
4. Package v2 is the primary content source;
5. Markdown is derived compatibility output;
6. Worker and owner boundaries remain intact;
7. legacy v1 package reads still work;
8. OpenAPI exposes v2 schemas;
9. full backend and unchanged frontend gates pass;
10. forbidden files remain untouched.
