# Candidate Merge Inventory: Task 0002

## Baseline

- Current branch: `feature/backend-frontend-mvp`
- Code Agent thread: `019efec4-1e17-7443-8496-c1fea5d6bcb5`
- Required direction: FastAPI-first MVP path, no whole-branch merge.
- Initial `git status --short`: existing untracked `frontend/`, `game/`, `images`, and `multi-agent/`.

## Candidate Branch Summary

### `origin/feat/sectional-generation`

Observed with `git diff --name-status HEAD..origin/feat/sectional-generation`.

Useful source material:

- Multi-file and section-related source metadata ideas: `pdf_paths`, source-aware PDF preview, `source_file` on chunks, globally unique chunk IDs.
- Reader improvements from the shared UI lineage: job id visibility, export link, quality badge, better citation/PDF layout, Markdown/KaTeX rendering.
- Evidence quote cleanup in `packages/core/jstudy_core/citations.py`.
- Section parsing and section metadata ideas in `packages/core/jstudy_core/pipeline.py` and `tests/test_parse_outline_sections.py`.

Absorb directly:

- None by whole-file checkout. The branch mixes stable work with full multi-file behavior, user feedback endpoints, domain expansion, runtime data, and UI churn.

Reimplement manually:

- Small, owner-checked Markdown export endpoint.
- Evidence quote cleanup with focused tests.
- Minimal source-aware section/package metadata foundation that keeps current single-PDF `POST /api/generate` behavior.
- Reader pieces that are small and compatible with the current temporary UI.

Postpone:

- Full multi-file upload and `/api/jobs/{job_id}/pdfs`.
- LLM-inferred sectional generation and multi-round per-section generation.
- Job history sidebar.
- Feedback endpoint/widget and `serve_feedback_admin.py`.

Reject:

- Deleting `docs/reviews/collaborator-deployment-review-2026-06-16.md`.
- Adding tracked `data/settings/content_pack.json`.
- Root-level branch notes/changelog as formal repo changes.
- Exposing blank or unvalidated subject scenarios to users.

### `origin/feat/frontend-polish-katex`

Observed with `git diff --name-status HEAD..origin/feat/frontend-polish-katex`.

Useful source material:

- Markdown rendering fixes around bold text, tables, code blocks, and LaTeX placeholders.
- KaTeX rendering approach for the temporary backend-served UI.
- Job id/status visibility, quality badge, export button, citation/PDF split polish.
- Evidence quote cleanup.

Absorb directly:

- None by whole-file checkout. The UI diff is large, CDN-based, and includes feedback/history pieces outside this task's safe MVP scope.

Reimplement manually:

- Minimal Markdown inline rendering fixes.
- Safe KaTeX rendering support in the temporary UI if it stays isolated and does not become final product design.
- Export button and quality badge only after the backend export endpoint is present.
- Citation jump behavior that keeps source preview scrolling independent.

Postpone:

- Large visual refresh.
- Resizable pane system if it becomes layout-heavy.
- Job history sidebar.
- Feedback widget and standalone admin.

Reject:

- Deleting the formal collaborator review doc.
- Adding tracked runtime `data/`.
- CDN/font/design changes as final frontend direction before shadcn/ui template selection.

### `origin/feat/multi-domain-modes`

Observed with `git diff --name-status HEAD..origin/feat/multi-domain-modes`.

Useful source material:

- Separating `generation_mode` metadata from `scenario_id` and `parser_profile_id`.
- Domain module routing idea, if kept hidden/admin-safe.
- Embedding API key separation via `JSTUDY_EMBED_API_KEY`, if low-risk.

Absorb directly:

- None by whole-file checkout. The branch adds broad domain files and soul profiles and risks making unvalidated scenarios appear supported.

Reimplement manually:

- A narrow `generation_mode`/`mode` metadata field only if it defaults to current single-courseware behavior and remains distinct from service mode.

Postpone:

- General/engineering domain modules.
- Additional soul files and mode-specific soul prompts.

Reject:

- Making General/Engineering visible as supported user scenarios while they are still placeholder quality.
- Treating output-style modes as complete user-facing behavior without prompt/spec/test coverage.

## Phase Decisions

### Phase 1: FastAPI Product Path

Proceed with focused manual changes only:

- Add `GET /api/jobs/{job_id}/export`.
- Add optional `mode` metadata only as non-disruptive metadata, not as a complete generation-mode feature.
- Preserve `POST /api/generate` as single-PDF upload.
- Preserve auth/session/owner checks and upload validation.
- Add tests before production changes.

### Phase 2: Temporary UI and Reader

Proceed after Phase 1 is green:

- Add export button, quality badge, job id/status visibility, and safer Markdown/KaTeX rendering where small.
- Keep temporary UI separate from final `apps/web`.
- Do not create final frontend styling or root-level frontend code.

### Phase 3: Sectional and Material-Package Foundation

Proceed only with a small foundation:

- Add section/package metadata files for the existing single-courseware result.
- Do not implement full batch/course-outline generation.

### Phase 4: Soul/Domain/Profile Safety

Proceed only with product-safe hidden/default behavior:

- Keep `medicine-default` as the only validated default visible scenario.
- Do not add tracked root soul profiles or tracked `data/` runtime content.

### Phase 5: Documentation and Verification

Update only docs that directly describe implemented behavior.

Verification target:

- Required `py_compile` command from the task card.
- `python -m unittest discover -s tests -v`.
