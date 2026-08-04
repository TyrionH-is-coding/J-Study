# Task Card: FastAPI-First MVP Merge and Frontend-Ready Foundation

## Supervisor Thread

`019ed023-8e41-7ad0-8117-6246b8ffa0bb`

## Code Agent Thread

`019efec4-1e17-7443-8496-c1fea5d6bcb5`

## Goal

Absorb the useful work from prepared candidate branches into the current `feature/backend-frontend-mvp` branch, with FastAPI product-path stability as the first priority and frontend-ready contracts as the second priority.

This is a larger task than onboarding. It is still not permission to merge whole branches blindly.

## Product Priority

The official product path is FastAPI-first:

```text
POST /api/generate
GET /api/jobs/{job_id}
GET /api/jobs/{job_id}/output
GET /api/jobs/{job_id}/evidence
GET /api/jobs/{job_id}/evidence-links
GET /api/jobs/{job_id}/trace
GET /api/jobs/{job_id}/pdf
GET /api/jobs/{job_id}/pdf-info
GET /api/jobs/{job_id}/pdf-page/{page_no}.png
```

CLI compatibility is secondary unless the same change is cheap and safe.

## Candidate Branches to Inspect

Inspect these branches before editing:

- `origin/feat/sectional-generation`
- `origin/feat/frontend-polish-katex`
- `origin/feat/multi-domain-modes`

Use the branches as source material. Do not run `git merge` for an entire candidate branch unless the Supervisor explicitly approves it later.

## Required Phase Structure

Execute this task in phases. If a phase uncovers a conflict that would require changing the product direction, stop and report instead of guessing.

### Phase 0: Inventory and Merge Plan

Before business-code edits, inspect candidate changes:

```powershell
git status --short
git diff --name-status HEAD..origin/feat/sectional-generation
git diff --name-status HEAD..origin/feat/frontend-polish-katex
git diff --name-status HEAD..origin/feat/multi-domain-modes
```

Create:

- `multi-agent/jstudy-product-build/reports/0002-candidate-merge-inventory.md`

The inventory must list:

- which branch changes will be absorbed directly
- which branch changes will be reimplemented manually
- which branch changes will be postponed
- any branch changes that must be rejected

At minimum, call out these known risk areas:

- candidate branches delete `docs/reviews/collaborator-deployment-review-2026-06-16.md`; do not delete this file
- candidate branches add files under ignored `data/`; do not add tracked runtime data unless there is a clear repository-level default that belongs outside `data/`
- standalone helper services such as `serve_feedback_admin.py` are not part of the main product path unless explicitly justified
- blank subject profiles must not become visible user options

### Phase 1: FastAPI Product Path Merge

Prioritize stable API/pipeline work that helps the real web product.

Allowed focus:

- preserve and improve `POST /api/generate`
- preserve auth/session/user ownership checks
- preserve upload validation and PDF limits
- preserve `GET /api/options`
- preserve job polling and artifact URLs
- improve evidence/citation contracts where needed for the reader
- improve PDF preview metadata/page contracts where needed
- absorb globally unique chunk/evidence id fixes if present and safe
- absorb section/package output contracts only when they remain compatible with current single-courseware MVP

Do not:

- replace the FastAPI app with a different entrypoint
- make CLI behavior the primary contract
- add broad unrelated endpoints
- break existing admin settings or invite/auth behavior
- implement full `batch_courseware` or `course_outline` unless the code is already coherent, covered by tests, and does not destabilize `single_courseware`

If adding a service-mode field, it must default to the current `single_courseware` behavior and must keep `scenario_id` and `parser_profile_id` separate.

### Phase 2: Temporary UI, Reader, Markdown, KaTeX, and Citation Jump

After Phase 1 is stable, absorb useful reader/UI work from candidate branches.

Allowed focus:

- temporary backend-served UI in `apps/api/jstudy_api/ui.py`
- Markdown display polish
- KaTeX rendering support if the candidate branch contains a safe implementation
- job id/status visibility for debugging
- source preview and evidence jump behavior
- keeping generated material and source preview as separate scroll areas

Do not:

- build a final visual design from scratch
- move UI work into a non-approved location such as a root-level `frontend/` folder
- create a large final Next.js UI before the user selects the shadcn/ui template
- let evidence clicks scroll the whole page instead of the source preview area

If `apps/web` is created, keep it minimal and clearly separate from temporary backend UI. The minimum acceptable scaffold is a placeholder authenticated shell that documents which existing FastAPI contracts it will call. Do not invent the final product layout.

### Phase 3: Sectional and Material-Package Foundation

Absorb only the stable foundation needed for future section-by-section browsing and full-document export.

Allowed focus:

- section metadata models
- section-level evidence link shape
- full-material package shape
- current single-courseware output represented in a way that can later become sectioned
- tests proving evidence ids stay unique across sections/chunks

Do not:

- claim full multi-courseware support is complete unless upload, storage, retrieval, evidence, UI, and tests all prove it
- claim course-outline mode is complete unless outline parsing, section order, evidence coverage, UI browsing, and export are all implemented and tested
- silently generate content for outline nodes with weak or missing evidence

### Phase 4: Soul Profiles, Domain Profiles, and Content Pack Safety

Absorb domain/soul/profile work only if it respects the current product decision:

- medicine is the first validated domain, not the long-term product boundary
- users choose visible scenarios from the upload page
- admins control which scenarios are visible
- blank general/engineering/law profiles may exist only as hidden placeholders
- knowledge snippets are a reviewed quality asset, not independent factual evidence

Do not add tracked runtime files under `data/`. If a default content-pack change is needed, put it in the existing code/config location used by the current admin settings system and explain the choice in the report.

### Phase 5: Documentation and Verification

Update only docs that directly reflect merged behavior.

Do not delete formal docs to match candidate branches.

Run backend verification from repository root:

```powershell
python -m py_compile web_mvp.py mvp_runner.py apps/api/jstudy_api/app.py apps/api/jstudy_api/ui.py apps/api/jstudy_api/admin_ui.py packages/core/jstudy_core/admin_settings.py packages/core/jstudy_core/auth_db.py packages/core/jstudy_core/auth_models.py packages/core/jstudy_core/auth_service.py packages/core/jstudy_core/scenario_router.py packages/core/jstudy_core/parser_profile_router.py packages/core/jstudy_core/pipeline.py packages/core/jstudy_core/cli.py packages/core/jstudy_core/citations.py packages/core/jstudy_core/jobs.py packages/core/jstudy_core/providers.py packages/core/jstudy_core/settings.py packages/core/jstudy_core/storage.py packages/parsers/mineru_parser.py packages/parsers/pymupdf_parser.py
python -m unittest discover -s tests -v
```

If a frontend scaffold is added, also run the matching frontend install/build/lint commands and report exact commands used. If frontend dependencies cannot be installed or the template decision is missing, report that as a limitation instead of pretending the frontend is complete.

## Allowed Files and Modules

The task may modify:

- `apps/api/jstudy_api/app.py`
- `apps/api/jstudy_api/ui.py`
- `apps/api/jstudy_api/admin_ui.py` only if an existing admin setting display needs to stay consistent
- `packages/core/jstudy_core/*.py`
- `packages/domains/*.py`
- `packages/retrieval/*.py`
- `packages/parsers/*.py` only if parser contracts need a small compatibility update
- `tests/*.py`
- `docs/product/vision.md`
- `docs/architecture/overview.md`
- `docs/roadmap.md`
- `docs/development/*.md`
- `docs/reviews/collaborator-deployment-review-2026-06-16.md`
- `multi-agent/jstudy-product-build/reports/0002-candidate-merge-inventory.md`
- `multi-agent/jstudy-product-build/reports/`
- `apps/web/` only for a minimal frontend-ready scaffold if the implementation reaches that point safely

## Out of Scope

Do not:

- merge whole candidate branches blindly
- delete formal docs
- add tracked runtime files under `data/`
- expose blank subject scenarios to users
- implement payment, pricing, billing, or quota
- deploy to Tencent Cloud
- change Cloudflare/domain configuration
- make MinerU the default parser
- turn user-facing model configuration into a normal-user feature
- build final UI styling without the user's selected shadcn/ui template
- make broad storage changes such as Tencent COS migration

## Checkpoint Rule

Continue phase by phase if verification remains green and the product direction is clear.

Stop and report to Supervisor if:

- a candidate branch requires deleting current formal docs
- a candidate branch requires a broad API redesign
- auth, ownership, upload validation, or evidence links would regress
- frontend scaffold requires a template or package-manager decision not present in the repo
- a phase would require implementing full batch/course-outline mode beyond stable foundations

## Required Final Report

Report back to Supervisor thread `019ed023-8e41-7ad0-8117-6246b8ffa0bb` in Chinese using `coordination/output_contract.md`.

The report must include:

1. Source Code Agent thread id.
2. Task card path.
3. Phase-by-phase summary.
4. Candidate branch inventory path and key decisions.
5. Changed files.
6. Behavior changed.
7. Verification commands and results.
8. Any skipped candidate changes and reasons.
9. Risks or limitations.
10. Requested Supervisor action: `PASS`, `PASS_WITH_LIMITATIONS`, `REVISE`, or `REJECT`.

## Success Criteria

- FastAPI `POST /api/generate` remains the official generation path.
- Existing auth, permission, upload, job ownership, evidence, and PDF preview contracts do not regress.
- Stable candidate work is absorbed without whole-branch merge churn.
- Temporary UI/reader improvements are integrated only after backend contract stability.
- Section/package foundations are present only to the extent they are coherent and verifiable.
- Formal docs remain intact and are updated only where behavior changed.
- Backend verification passes, or failures are explained with exact error output and a narrow fix proposal.

## Suggested Prompt for This Task

```text
You are the J-Study Code Agent.

Execute:

multi-agent/jstudy-product-build/task_cards/0002-fastapi-first-mvp-merge.md

This is a larger staged merge task. FastAPI product-path capability is the first priority. Use candidate branches as source material, but do not merge whole branches blindly.

Proceed phase by phase:

1. Inventory candidate branches and write the inventory report.
2. Merge or manually absorb stable FastAPI product-path work.
3. Absorb temporary UI/reader/Markdown/KaTeX/citation-jump improvements only after the backend contract is stable.
4. Absorb only safe section/package foundations.
5. Absorb soul/domain/profile work only if admin-hidden and product-safe.
6. Run verification and report back in Chinese to Supervisor thread 019ed023-8e41-7ad0-8117-6246b8ffa0bb.

Do not delete formal docs, do not add tracked runtime data under data/, do not expose blank scenarios, do not deploy, and do not build a final UI without the user's selected shadcn/ui template.
```
