# Task 0009: Service Mode Contracts And Multi Courseware Baseline

## Supervisor

- Product/Supervisor source task: `019ed023-8e41-7ad0-8117-6246b8ffa0bb`
- Dispatching task: `019fa956-f165-76b0-b49d-9462d2f52328`
- Assigned Code Agent: `019efec4-1e17-7443-8496-c1fea5d6bcb5`

## Required Baseline

- Repository: `D:\大二下\deep tutor\J-Study`
- Branch: `feature/backend-frontend-mvp`
- Documentation baseline before this task card: `6389199`
- Start from the commit containing this task card.
- Before production edits, record the exact start SHA and verify the protected
  dirty/untracked paths.
- Do not push, merge, rebase, reset, clean, or delete protected content.
- Start PowerShell sessions with:

```powershell
. "$env:USERPROFILE\.codex\scripts\Enter-CodexUtf8.ps1"
```

## Goal

Implement the three strict service-mode upload contracts and add the first
production `multi_courseware` backend path.

The new path must:

1. accept at least two PDFs and no outline;
2. preserve stable source identity and upload display order;
3. batch-parse through the existing MinerU-only Worker path;
4. generate existing Manifest, Learning Map, Coverage Ledger, Material Package
   v2, Markdown compatibility, evidence, quality, and trace artifacts;
5. remain sequence-first;
6. deliberately omit cross-courseware associations until experiments select an
   algorithm.

## Authoritative Documents

- Product contract: `docs/product/service-modes.md`
- Content/export contract: `docs/product/study-materials.md`
- Implementation plan:
  `docs/superpowers/plans/2026-08-03-service-mode-contracts-multi-courseware.md`

If code and an old report conflict with these documents, stop and report the
conflict. Do not silently preserve stale optional-outline behavior.

## Required Skills And Method

- Use `superpowers:subagent-driven-development` or
  `superpowers:executing-plans`.
- Use test-driven development: each phase must show a focused RED before the
  implementation and GREEN afterward.
- Use Chinese README/document changes and Chinese commit messages.
- Keep changes surgical. Reuse existing admission, MinerU, planning, validation,
  Worker lease, artifact, ownership, and cache mechanisms.

## Strict Public Contract

| Mode | Required | Forbidden |
|---|---|---|
| `single_courseware` | exactly one singular multipart `pdf` | `outline`, repeated `pdfs` |
| `course_outline` | one `outline`, at least one repeated multipart `pdfs` | singular `pdf` |
| `multi_courseware` | at least two repeated multipart `pdfs` | `outline`, singular `pdf` |

Additional rules:

- the three modes are mutually exclusive;
- no server-side mode conversion;
- invalid submissions return a stable structured 400 error;
- invalid submissions create no Job and leave no input directory;
- existing PDF count, per-file size, aggregate size, MIME/magic, queue,
  idempotency, and ownership limits remain active;
- metadata-only `mode` is not extended;
- parser aliases cannot change the Worker away from MinerU.

## Required Implementation

### Phase 0: Baseline

- Record exact branch, start SHA, status, protected paths, and relevant
  production contracts.
- Create:
  `multi-agent/jstudy-product-build/reports/0009-service-mode-contracts-multi-courseware-report.md`.
- Do not edit production code until the baseline is recorded.

### Phase 1: Strict Models

- Add `multi_courseware` to `CoursewareManifestV1`.
- Enforce per-mode outline/source count rules in the Manifest validator.
- Add `multi_courseware` to `MaterialPackageV2`.
- Do not add it to `LegacyMaterialPackageV1`.
- Add strict model tests, including booleans/coercion and invalid shape
  regressions where relevant.

### Phase 2: Admission And API

- Add `multi_courseware` to `SUPPORTED_SERVICE_MODES`.
- Make single-courseware reject every outline.
- Make course-outline require one valid outline and one or more PDFs.
- Make multi-courseware require at least two PDFs and reject every outline.
- Reject incorrect multipart field families; do not ignore them.
- Extend `/api/options` with:
  - `default_service_mode=single_courseware`;
  - an enabled list of all three service modes.
- Keep Scenario behavior unchanged. Do not switch to an empty
  `general-default`.

### Phase 3: Pipeline

- Add `run_multi_courseware()`.
- Require existing normalized Parsed Documents and the frozen synchronization
  bundle.
- Call the existing sequence-first generator with
  `service_mode="multi_courseware"`.
- Use the title `多课件学习资料`.
- Do not add a legacy parser/retrieval fallback.
- Do not call embedding, BM25, RRF, Web Search, or an association model to order
  or enrich the multi-courseware material in this task.

### Phase 4: Worker And Artifacts

- Add an injectable/default `multi_runner`.
- Dispatch only `multi_courseware` Jobs to it.
- Reuse one MinerU batch parse across all Job sources.
- Preserve the existing frozen Manifest/Map/Coverage validation before and
  after the runner.
- Reuse existing artifact hashing, bounded reads, package validation,
  lease/heartbeat, retry, and atomic completion.
- Ensure status, package, manifest, learning-map, coverage, source preview, and
  export endpoints work through existing owner checks.

### Phase 5: Documentation And Verification

- Update only actual implementation state in README, architecture, roadmap, and
  service-mode product document.
- Explicitly state that cross-courseware association remains unimplemented and
  experimental.
- Run the complete backend and frontend regression gates from the plan.
- Write exact test counts and residual risks in the report.

## Allowed Scope

Production:

- `apps/api/jstudy_api/app.py`
- `packages/core/jstudy_core/courseware/models.py`
- `packages/core/jstudy_core/materials/models.py`
- `packages/core/jstudy_core/job_system/service.py`
- `packages/core/jstudy_core/job_system/worker.py`
- `packages/core/jstudy_core/pipeline.py`

Tests:

- `tests/test_courseware_models.py`
- `tests/test_material_models.py`
- `tests/test_job_service.py`
- `tests/test_web_mvp.py`
- `tests/test_security_controls.py`
- `tests/test_mvp_runner.py`
- `tests/test_job_worker.py`

Documentation/report:

- `README.md`
- `docs/architecture/overview.md`
- `docs/roadmap.md`
- `docs/product/service-modes.md`
- `multi-agent/jstudy-product-build/reports/0009-service-mode-contracts-multi-courseware-report.md`

If another file is genuinely required, record why before editing it and list it
explicitly in the final report.

## Forbidden Scope

Do not implement or modify:

- `apps/web/**`
- `deploy/**`
- `data/**`
- cross-courseware association discovery, scoring, generation, graph, or UI
- `general-default` Soul/Profile content or default switch
- Courseware Organizer, auto-sort, drag/drop, rename, or user confirmation
- HTML/Markdown/PDF renderer or export changes
- section retry, generation fingerprints, export fingerprints, or cache work
- Alembic or database migration
- provider/BYOK/quota/billing work
- frontend, deployment, Cloudflare, Nginx, or server configuration
- parser selector removal beyond existing product behavior
- legacy deletions

Protected existing workspace content:

- `multi-agent/jstudy-product-build/reports/supervisor_review.md`
- `.superpowers/`
- `frontend/`
- `game/`
- `images/`
- `outline_mode/`
- `scripts/`

Do not stage, commit, overwrite, move, or delete these paths.

## Acceptance Criteria

1. All three strict input matrices pass at service and HTTP levels.
2. Invalid field combinations create no Job or stored input.
3. `/api/options` exposes the three enabled service modes and single as default.
4. A two-PDF multi Job reaches terminal state through the dedicated Worker
   dispatch.
5. Multi output is sequence-first and preserves source identity/display order.
6. All required public and synchronization artifacts pass existing validation.
7. No association output, retrieval-based ordering, or PyMuPDF text fallback is
   introduced.
8. Existing single and outline behavior remains compatible except for the
   intentional removal of optional outline from single mode.
9. Full backend and frontend regression gates pass.
10. No protected file, runtime artifact, upload, database, key, or secret is
    committed.

## Required Verification

```powershell
python -m compileall -q apps packages
python -m unittest discover -s tests -v

Set-Location apps/web
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
Set-Location ../..

git diff --check
git status --short
```

Live MinerU, PostgreSQL containers, and production deployment are not required
for PASS on this task, but their absence must be reported honestly.

## Required Report

Return:

1. task, branch, exact start/final SHA;
2. phase-by-phase summary;
3. exact changed files;
4. focused RED/GREEN and full verification results;
5. risks and skipped live checks;
6. explicit statement that association remains experimental and absent;
7. requested Supervisor verdict:
   `PASS` / `PASS_WITH_LIMITATIONS` / `REVISE` / `REJECT`.
