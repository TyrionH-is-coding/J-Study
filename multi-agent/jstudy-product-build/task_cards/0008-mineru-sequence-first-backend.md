# Task 0008: MinerU Sequence-First Courseware Backend

## Supervisor

- Product/Supervisor source task: `019ed023-8e41-7ad0-8117-6246b8ffa0bb`
- Dispatching task: `019fa956-f165-76b0-b49d-9462d2f52328`
- Assigned Code Agent: `019efec4-1e17-7443-8496-c1fea5d6bcb5`

## Required Baseline

- Repository: `D:\大二下\deep tutor\J-Study`
- Branch: `feature/backend-frontend-mvp`
- Verified production-code baseline before this task's documentation:
  `61cc8c2c786c`
- Start from the commit containing this task card.
- Before editing production code, record the exact start SHA and verify that the
  only pre-existing dirty/untracked paths are the protected paths listed below.
- Do not push, merge, rebase, reset, clean, or delete protected content.

## Goal

Replace the current PyMuPDF plus relevance-ranked complete-material path with a
MinerU-backed, courseware-order-first backend slice for both existing service
modes.

Task 0008 must deliver:

1. stable source display metadata separate from `source_id`;
2. immutable `courseware-manifest.v1`;
3. real Worker integration with the existing MinerU client and normalizer;
4. ordered continuous `learning-map.v1`;
5. `coverage-ledger.v1` for parsed blocks;
6. sequence-first `material-package.v2` generation;
7. owner-scoped read APIs for synchronization artifacts;
8. removal of parser choice from public product options.

## Product Contract

The authoritative design is:

- `docs/superpowers/specs/2026-07-31-courseware-synchronized-learning-design.md`

The detailed implementation order is:

- `docs/superpowers/plans/2026-07-31-mineru-sequence-first-backend.md`

The controlling principles are:

- the user-confirmed courseware sequence controls the main learning path;
- source page/block order controls generation inside a courseware;
- embedding may discover associations but cannot reorder main sections;
- MinerU performs all product text and structure extraction;
- PyMuPDF is limited to validation, metadata, page count, page rendering, and
  MinerU page-reference validation;
- no silent fallback from MinerU text extraction to PyMuPDF;
- cross-source relationships are retained for provenance but use
  `navigation_policy=non_interactive`;
- `material-package.v2` remains schema-stable.

## Allowed Scope

Production code:

- `apps/api/jstudy_api/app.py`
- `packages/core/jstudy_core/courseware/**`
- `packages/core/jstudy_core/documents/**`
- `packages/core/jstudy_core/job_system/**`
- `packages/core/jstudy_core/materials/generation.py`
- `packages/core/jstudy_core/citations.py`
- `packages/core/jstudy_core/pipeline.py`
- `packages/core/jstudy_core/settings.py`
- `packages/core/jstudy_core/storage.py`
- `packages/parsers/**` only where needed to remove production page-list routing
- `packages/retrieval/**` only for a narrow compatibility boundary or tests

Tests:

- new focused tests named in the implementation plan
- existing backend tests affected by the intentional contract

Documentation:

- `README.md`
- `docs/architecture/overview.md`
- `docs/roadmap.md`
- Task 0008 report and implementation notes

## Forbidden Scope

Do not implement or modify:

- `apps/web/**`
- frontend visual design, login, organizer UI, drag-and-drop, or Reader UI
- `deploy/**`, Cloudflare, Nginx, Docker topology, or server configuration
- `data/**` or any runtime settings/upload/artifact file
- Alembic or durable production database migration
- HTML renderer, HTML export, theme presets, or Markdown deletion
- Batch Courseware Mode
- auto-organization model quality, LLM title suggestions, or confidence UI
- daily quota, billing, user BYOK, Codex OAuth, or provider expansion
- question generation
- Soul Profile or Knowledge Snippet content edits
- legacy deletion beyond production call-path disconnection

Protected existing workspace content:

- `multi-agent/jstudy-product-build/reports/supervisor_review.md`
- `.superpowers/`
- `frontend/`
- `game/`
- `images/`
- `outline_mode/`
- `scripts/`

Do not stage, commit, overwrite, move, or delete these paths.

## Required Contracts

### 1. Source identity

- `source_id` is assigned once at admission and never recomputed.
- `original_filename` is immutable.
- Persist:
  - `display_title`
  - `display_order`
  - `primary_outline_section_id`
  - `title_origin`
  - `order_origin`
- Task 0008 defaults title/order to filename stem and upload order.
- Reordering display metadata must never change `source_id`, PDF path, evidence
  identity, or preview endpoint.

### 2. Courseware Manifest

Create strict `courseware-manifest.v1`.

It must contain:

- Job/manifest identity
- service mode
- optional parsed outline metadata
- source SHA256
- stable identity
- display title/order
- outline mapping
- origin metadata

The Worker and all retries consume the same persisted source snapshot.

### 3. MinerU parsing

- Use the existing MinerU Precision Extract v4 client.
- Submit source IDs as MinerU `data_id`.
- Normalize ZIP results through the existing safe normalizer.
- Preserve one-based page numbers and stable block IDs.
- Parse multi-PDF Jobs in one ordered batch where supported.
- Parse PDF outlines through MinerU with a reserved internal identity, while
  keeping them outside courseware source/evidence/preview contracts.
- Continue bounded strict UTF-8 reads for Markdown/TXT outlines.
- Use PyMuPDF utility only for PDF validation and page counts.
- Do not call legacy PyMuPDF text extraction in the Worker path.
- Do not call a MinerU page-list adapter without an explicit real parser.
- Map temporary provider errors into existing bounded Worker retry.
- Treat malformed/safety/page-mapping/empty-document errors as permanent.

### 4. Learning Map

Create strict `learning-map.v1`.

Every unit:

- has one primary source;
- uses a continuous page span;
- keeps ordered block IDs;
- maps to one Material Package section ID;
- follows Manifest display order, then page order;
- never crosses a source boundary.

Initial planner is deterministic. It may use headings, page boundaries and a
character budget. It must not use embedding, BM25, RRF, or an LLM.

### 5. Coverage Ledger

Create strict `coverage-ledger.v1`.

Every normalized block must be:

- `used`
- `ignored`
- `duplicate`
- `unsupported`

No block may disappear because Top-K retrieval did not select it.

Record coverage and jump metrics without inventing product thresholds.

### 6. Sequence-first generation

- Runners receive normalized documents, manifest, learning map and ledger.
- Runners do not parse PDFs again.
- Generate one strict v2 section per learning unit in map order.
- Primary evidence comes from the unit's continuous page span.
- Same-source adjacent evidence may be supporting.
- Cross-source evidence is non-interactive.
- Similarity scores cannot change main section order.
- Existing structured JSON generation and one bounded repair remain.
- Existing Markdown/evidence/links/quality/trace/package compatibility remains.

### 7. API

- `/api/options` no longer advertises parser profiles.
- New clients omit `parser_profile_id`.
- During migration, empty, `fast`, and `quality` request values may be accepted
  as bounded aliases, but none may switch the Worker away from MinerU.
- Unknown values remain rejected.
- Add owner-scoped, private-cache read endpoints:
  - `GET /api/jobs/{job_id}/manifest`
  - `GET /api/jobs/{job_id}/learning-map`
  - `GET /api/jobs/{job_id}/coverage`
- Source responses include identity and display metadata.
- Do not expose MinerU signed URLs, raw provider JSON, private ZIPs, credentials,
  absolute paths, or complete document text through new endpoints.

### 8. Material Package compatibility

- Do not change the meaning of `material-package.v2`.
- Manifest, learning map and ledger are separate versioned artifacts.
- Legacy v1 package reads and deterministic Markdown remain until later
  deletion gates.

## TDD Phase Order

Execute in this order:

1. strict courseware models
2. source display persistence
3. MinerU document service
4. deterministic manifest/learning/coverage planning
5. Worker parsing and artifact integration
6. sequence-first runner generation
7. API publication and security
8. full regression and report

Each phase must:

- start with a focused failing test;
- implement the smallest contract needed;
- run its focused suite;
- commit with a Chinese commit message;
- preserve the protected workspace boundary.

Do not start the next phase while the focused suite is red.

## Required Verification

Backend:

```powershell
python -m compileall -q apps packages
python -m unittest discover -s tests -v
```

Frontend regression only:

```powershell
Set-Location apps/web
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
```

Required focused evidence:

- PyMuPDF text extractor patched to raise but production Worker tests pass
- mocked MinerU service receives stable source IDs
- provider result reordering does not change Manifest order
- similarity-score changes do not change generated section order
- every parsed block appears exactly once in Coverage Ledger
- invalid MinerU output cannot atomically complete a Job
- stale lease cannot persist the new artifacts
- all three new endpoints reject another owner

## Live MinerU Boundary

Do not read a real token or call MinerU unless the user gives a separate explicit
instruction.

Mocked transport tests are required but are not live acceptance. The report must
state one of:

- `live_mineru_smoke: not_run`
- `live_mineru_smoke: passed` with a non-sensitive fixture and redacted trace
- `live_mineru_smoke: failed` with a safe error summary

## Database Boundary

Current runtime data is disposable test data, but Task 0008 does not implement
Alembic. If SQLModel columns change:

- tests must create a fresh database;
- documentation must state that an old local pilot database must be reset;
- do not claim an in-place production migration exists.

## Required Report

Create:

`multi-agent/jstudy-product-build/reports/0008-mineru-sequence-first-backend-report.md`

Use:

```markdown
# Code Agent Report

## 1. Task
## 2. Summary
## 3. Phase Commits
## 4. Changed Files
## 5. Verification
## 6. Product Contract Evidence
## 7. Risks and Limitations
## 8. Requested Supervisor Action
```

Return exactly one requested verdict:

`PASS` / `PASS_WITH_LIMITATIONS` / `REVISE` / `REJECT`

## Acceptance Gate

Supervisor may pass Task 0008 only if:

1. both existing service modes use MinerU normalized documents;
2. production Worker never uses PyMuPDF text extraction;
3. source identity and display ordering are independent;
4. main material order follows Manifest and continuous source spans;
5. Top-K hybrid retrieval no longer controls complete-material coverage/order;
6. coverage includes every normalized block;
7. cross-source navigation is non-interactive;
8. Job ownership, state, lease, retry and atomic completion remain correct;
9. Material Package v2 remains valid and compatible;
10. full backend and unchanged frontend gates pass;
11. no protected path enters a commit;
12. the report is honest about live MinerU and database migration limits.
