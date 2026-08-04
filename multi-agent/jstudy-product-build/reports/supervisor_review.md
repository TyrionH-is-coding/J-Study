# Supervisor Review Log

## 2026-06-25: Code Agent Onboarding

- Task card: `multi-agent/jstudy-product-build/task_cards/0001-code-agent-onboarding.md`
- Code Agent thread id: `019efec4-1e17-7443-8496-c1fea5d6bcb5`
- Verdict: `PASS`

Supervisor-side verification:

- Read `multi-agent/jstudy-product-build/coordination/session_registry.md` and confirmed the Code Agent row is registered as `019efec4-1e17-7443-8496-c1fea5d6bcb5` with status `active`.
- Read `multi-agent/jstudy-product-build/task_cards/0001-code-agent-onboarding.md` and confirmed the task was onboarding/read-only except registry update.
- Ran `git status --short`; only untracked top-level folders are visible: `frontend/`, `game/`, `images/`, `multi-agent/`.
- Ran targeted search for the registered Code Agent id and onboarding references under `multi-agent/jstudy-product-build`.

Assessment:

- The Code Agent completed the requested onboarding report.
- The report correctly distinguishes the current backend pilot state from the next frontend construction phase.
- No evidence of business-code modification was found in this Supervisor pass.

Next action:

- Superseded by task `0002`: staged FastAPI-first candidate absorption with frontend-ready reader and contract foundations.

## 2026-06-25: FastAPI-First MVP Merge

- Task card: `multi-agent/jstudy-product-build/task_cards/0002-fastapi-first-mvp-merge.md`
- Code Agent thread id: `019efec4-1e17-7443-8496-c1fea5d6bcb5`
- Verdict: `PASS_WITH_LIMITATIONS`

Supervisor-side verification:

- Ran `git status --short`; tracked changes are limited to README/docs, FastAPI app/UI, core pipeline/storage/citations, and tests. Existing untracked folders remain: `frontend/`, `game/`, `images/`, `multi-agent/`.
- Ran `git diff --stat` and `git diff --name-status`; no whole-branch merge churn was found.
- Ran scoped forbidden-path status for `data`, `docs/reviews`, `packages/domains`, root soul files, deploy files, candidate notes/changelog files, `apps/web`, and `frontend`; only pre-existing untracked `frontend/` appeared.
- Read `multi-agent/jstudy-product-build/reports/0002-candidate-merge-inventory.md`.
- Reviewed diffs for `apps/api/jstudy_api/app.py`, `apps/api/jstudy_api/ui.py`, `packages/core/jstudy_core/pipeline.py`, `packages/core/jstudy_core/storage.py`, `packages/core/jstudy_core/citations.py`, and related tests.
- Ran the required compile command from the task card; exit code 0.
- Ran `python -m unittest discover -s tests -v`; result: `Ran 114 tests`, `OK`.
- Ran `git diff --check`; no whitespace errors, only the existing line-ending warning for `packages/core/jstudy_core/pipeline.py`.

Assessment:

- The Code Agent stayed within the staged FastAPI-first subset and did not merge whole candidate branches.
- `POST /api/generate` remains the official generation path.
- New `/api/jobs/{job_id}/package` and `/api/jobs/{job_id}/export` routes use the existing owner-checked artifact path.
- Existing auth, owner isolation, upload checks, evidence, trace, PDF preview, and cache-control tests pass.
- Formal docs were not deleted, tracked runtime `data/` was not added, blank subject profiles were not exposed, and deployment/domain files were not changed.

Limitations:

- `mode` is accepted only as metadata. It should not be treated as a completed generation-mode feature until a later spec defines allowed values, prompt behavior, and UI semantics.
- The `material_package` artifact is a single-courseware compatibility wrapper, not full batch/course-outline or true multi-section generation.
- KaTeX is loaded from CDN in the temporary backend UI. This is acceptable for pilot testing but should be revisited when the formal `apps/web` frontend is built.
- Evidence quote cleanup is intentionally heuristic and should be monitored on non-Chinese/non-English PDFs.

Next action:

- Keep these changes as a candidate for merge after human review.
- The next task should focus on formal frontend planning/template selection or a small follow-up that turns `mode` from metadata into a validated contract, not both at once.

## 2026-06-26: Course Outline Multi-PDF Backend

- Task card: `multi-agent/jstudy-product-build/task_cards/0003-course-outline-multipdf-backend.md`
- Code Agent thread id: `019efec4-1e17-7443-8496-c1fea5d6bcb5`
- Verdict: `PASS_WITH_LIMITATIONS`

Supervisor-side verification:

- Ran `git status --short`; tracked changes are limited to README/docs, FastAPI app/UI, core jobs/pipeline/storage/citations, retrieval chunks, and tests. Existing untracked folders include `.superpowers/`, `frontend/`, `game/`, `images/`, `multi-agent/`, and `outline_mode/`.
- Ran `git diff --stat` and `git diff --name-status`; no deploy, domain, root soul, domain-pack, or tracked runtime `data/` files were changed.
- Ran scoped forbidden-path status for `data`, `deploy`, `apps/web`, `frontend`, `packages/domains`, root soul files, deployment docs, and review docs; only pre-existing untracked `frontend/` appeared.
- Reviewed `multi-agent/jstudy-product-build/reports/0003-course-outline-backend-plan.md`.
- Reviewed diffs for `apps/api/jstudy_api/app.py`, `packages/core/jstudy_core/jobs.py`, `packages/core/jstudy_core/pipeline.py`, `packages/core/jstudy_core/citations.py`, `packages/retrieval/hybrid.py`, and related tests.
- Ran the required compile command from the task card; exit code 0.
- Ran `python -m unittest discover -s tests -v`; result: `Ran 120 tests`, `OK`.
- Ran `git diff --check`; no whitespace errors, only CRLF/LF warnings for README, FastAPI app, and pipeline.

Assessment:

- `POST /api/generate` now separates `service_mode` from metadata-only `mode`.
- Empty or `single_courseware` keeps the existing one-PDF path.
- `service_mode=course_outline` requires an outline and repeated `pdfs` uploads.
- Multi-PDF jobs record stable source ids such as `S001` and `S002`.
- Chunks, evidence items, evidence links, job status, package metadata, and source-specific PDF preview endpoints preserve source identity.
- Existing auth, owner isolation, upload validation, single-courseware behavior, package/export endpoints, and PDF preview tests pass.

Limitations:

- Course Outline Mode is a backend contract foundation, not final generation quality.
- Outline parsing is deterministic and simple; it supports Markdown headings and numbered lines, capped at 12 sections.
- There is currently no explicit backend cap on the number of uploaded PDFs or total multi-PDF upload size. Each PDF still uses the existing per-file limit, but public deployment should add a course-outline PDF-count or total-size cap.
- Course-outline generation may call the LLM once per parsed section; the section cap limits cost but does not make latency production-grade.
- The package uses one assembled Markdown/evidence artifact set with section metadata, not separate per-section artifact files.
- Formal `apps/web` frontend and UI for weak-evidence sections remain pending.

Next action:

- Continue frontend framework/design planning using the new mode-first and Course Outline backend contract.
- Before public deployment, add a small follow-up task for multi-PDF count/total-size limits.

## 2026-07-16: Frontend Foundation and Course Outline Workflow

- Task card: `multi-agent/jstudy-product-build/task_cards/0004-frontend-foundation-course-outline.md`
- Code Agent thread id: `019efec4-1e17-7443-8496-c1fea5d6bcb5`
- Verdict: `PASS_WITH_LIMITATIONS`

Supervisor-side verification:

- Reviewed `multi-agent/jstudy-product-build/reports/0004-frontend-plan.md` and confirmed Phase 0 was written before implementation.
- Reviewed the `apps/web` file list excluding ignored `node_modules`, `.next`, `test-results`, and `playwright-report`.
- Confirmed `apps/web/.gitignore` excludes build/dependency/test artifacts.
- Ran `git add --dry-run apps/web`; confirmed build artifacts are not staged and `.env.local.example` is now included.
- Checked for `localStorage`, `sessionStorage`, bearer-token style auth, `mode`/`service_mode`, and `source_id` usage under `apps/web/src` and `apps/web/e2e`.
- Reviewed `apps/web/src/lib/api/client.ts`, `apps/web/src/features/reader/job-workspace.tsx`, and `apps/web/src/features/source-preview/source-preview.tsx`.
- Verified suspected mojibake in `source-preview.tsx` and `apps/web/README.md` is terminal display only; the files read correctly as UTF-8.
- Ran `npm run lint`; pass.
- Ran `npm run typecheck`; pass.
- Ran `npm test`; pass, `8` test files and `13` tests.
- Ran `npm run build`; pass, Next production build completed.
- Ran `npm run test:e2e`; pass, `12/12` Playwright tests across `390x844`, `768x1024`, and `1440x900`.
- Ran `python -m unittest discover -s tests -v`; pass, `Ran 120 tests`, `OK`.
- Ran `git diff --check`; no whitespace errors, only existing CRLF/LF warnings for README, FastAPI app, and pipeline.

Supervisor cleanup:

- Updated `apps/web/.gitignore` so `.env.local.example` is trackable.
- Removed generated local `apps/web/AGENTS.md` and `apps/web/CLAUDE.md`; they were unnecessary for product code and one contained mojibake in local agent instructions.

Assessment:

- The first formal `apps/web` frontend exists and follows the approved Clinical Workbench direction.
- The implemented route shell covers `/`, `/login`, `/register`, `/modes`, `/modes/course-outline`, and `/jobs/[jobId]`.
- The frontend consumes existing backend contracts only; no FastAPI route changes or new backend endpoints were introduced for this task.
- Auth remains cookie-based. No long-lived token storage in URL, localStorage, or sessionStorage was found.
- Course Outline upload sends `service_mode=course_outline` and repeated `pdfs`; metadata-only `mode` is not used for service routing.
- API types and client code are centralized under `apps/web/src/lib/api`.
- Source identity uses `source_id`; file names are display labels only.
- Browser E2E uses real Next and FastAPI URLs with deterministic runner injection, rather than static screenshot-only verification.

Limitations:

- Playwright runs with `workers: 1` because existing backend job JSON writes are not concurrency-safe. This should be handled by a later backend job-store/concurrency task, not the frontend task.
- E2E uses a deterministic runner and does not call external LLM/provider services. It verifies the UI/API/auth/artifact contract, not provider latency or generation quality.
- Public deployment is still blocked by upload-boundary follow-up work: `max_pdfs`, total upload bytes, outline limit, MIME/magic validation, parse timeout, queue/concurrency limit, and cleanup.
- `npm audit` reported moderate advisories tied to the current Next/PostCSS dependency chain. No safe non-breaking upgrade was available in this task; revisit when upstream publishes a compatible fix.

Next action:

- Keep task `0004` as accepted with limitations.
- Create a narrow backend hardening task before public deployment for upload limits, queue/concurrency, cleanup, and job-store write safety.
- After that, prepare the first production-like deployment exercise using `docs/deployment/first-production-like-deploy-plan.md`.
