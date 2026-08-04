# Task Card: Frontend Foundation and Course Outline Workflow

## Supervisor Thread

`019ed023-8e41-7ad0-8117-6246b8ffa0bb`

## Goal

Create the first formal `apps/web` frontend foundation for J-Study and integrate the existing Course Outline Mode backend contract without expanding backend scope.

## Context

J-Study now has:

- FastAPI `single_courseware` compatibility path.
- `course_outline` backend contract with `outline` + repeated `pdfs`.
- Stable source identity such as `S001` and source-specific preview endpoints.
- Section-level `material_package` output.

The frontend must start from the approved Clinical Workbench baseline:

- `docs/frontend/clinical-workbench-spec.md`

This task should freeze the product/visual contract before implementing. Do not recreate the visual direction during coding.

## Allowed Scope

Allowed files/directories:

- `apps/web/**`
- frontend package/config files required for `apps/web`
- `docs/frontend/**`
- `docs/architecture/overview.md` only for frontend contract notes
- `docs/roadmap.md` only for status updates
- `multi-agent/jstudy-product-build/reports/0004-frontend-plan.md`

If a package manager workspace file is needed at repository root, keep it minimal and explain why in the report.

## Out of Scope

Do not:

- change FastAPI route behavior
- add new backend endpoints
- change `POST /api/generate` contract
- implement admin UI
- implement payment, quota, object storage, or MinerU default behavior
- implement `batch_courseware`
- expose blank General/Engineering/Law scenarios
- add Redux, Zustand, PWA, i18n, or a generic file-viewer framework
- commit runtime `data/`, uploads, secrets, or real user files
- change deployment/domain configuration

## Required Phase 0: Plan Before Code

Before creating `apps/web`, write:

- `multi-agent/jstudy-product-build/reports/0004-frontend-plan.md`

The plan must state:

1. exact package manager and Next.js setup
2. route tree
3. module boundaries
4. API type strategy
5. how `/api/*` calls are routed in local dev
6. browser E2E strategy
7. assumptions and risks

Stop and report if the package manager or local dev proxy choice is unclear.

## Requirements

### 1. Stack

Use:

- Next.js App Router
- TypeScript
- Tailwind CSS
- shadcn/ui
- TanStack Query

### 2. Routes

Implement the initial route shell:

```text
/                     redirect by auth state
/login                email/password login
/register             email/password registration
/modes                service-mode selector
/modes/course-outline outline + multi-PDF upload workflow
/jobs/[jobId]         material package reader
```

### 3. Auth

Integrate existing backend routes:

```text
GET  /api/auth/me
POST /api/auth/login
POST /api/auth/register
POST /api/auth/logout
```

Use HTTP-only cookie behavior from the backend. Do not store long-lived tokens in localStorage, URL, or logs.

### 4. Course Outline Submit

Use the backend contract:

```text
POST /api/generate
service_mode=course_outline
outline=<required .md/.txt/.pdf>
pdfs=<one or more PDFs, repeated multipart field>
scenario_id=<optional>
parser_profile_id=<optional>
mode=<metadata only; hidden in first UI>
```

Frontend must not use `mode` to infer service mode.

### 5. Reader

Implement the minimum reader:

- load `GET /api/jobs/{job_id}`
- load `GET /api/jobs/{job_id}/package`
- show section navigation
- render generated Markdown safely
- show full export link from `export_url`
- show weak-evidence status when provided
- show source list from `GET /api/jobs/{job_id}/pdfs`
- use source-specific PDF page preview endpoints
- citation click scrolls only the source preview area

File names are display labels only. Use `source_id` as identity.

### 6. API Types

Keep one frontend API type source under `apps/web/src/lib/api`.

Preferred:

- generate or validate TypeScript types from OpenAPI/backend schemas if available

Acceptable first version:

- define a single narrow set of TypeScript types in `lib/api`
- do not duplicate job/source/evidence shapes in feature folders

### 7. Styling

Follow:

- `docs/frontend/clinical-workbench-spec.md`

No marketing hero. No decorative gradient orbs. No nested cards. Keep card radius at 8px or less.

### 8. Real Browser Acceptance

Add a browser E2E skeleton or documented command path that opens the real running app URL.

Required viewports:

```text
390x844
768x1024
1440x900
```

Checks should cover:

- login/register/me/logout/route guard
- mode selector
- outline + 1 PDF submit
- outline + 2 PDFs submit
- job polling completed/failed states
- multi-source switching
- citation click only scrolls source preview
- refresh `/jobs/[jobId]` restores reader state
- no horizontal overflow in the app shell
- browser console has zero unexpected errors

Static screenshots are not sufficient as final acceptance.

## Backend Follow-Up Dependency

Before public deployment, a separate backend task must add:

- `max_pdfs`
- `total_upload_bytes`
- single PDF size limit review
- outline size and extension limit
- PDF MIME or magic-number validation
- parse timeout
- job concurrency or queue limit
- temp/failed/expired artifact cleanup policy

Do not implement these backend changes in this frontend task unless the Supervisor explicitly issues a separate task card.

## Verification Commands

Run the frontend checks selected in Phase 0, plus:

```powershell
python -m unittest discover -s tests -v
git diff --check
```

If backend dependencies are missing locally, report that clearly and still run frontend build/lint/type checks.

## Stop and Report If

Stop instead of guessing if:

- local dev proxy choice would require backend route changes
- backend package shape does not match docs
- PDF preview endpoints cannot support source-specific rendering
- auth cookie behavior fails in same-site local dev
- shadcn setup requires a broad repo restructure
- implementing the reader would require a generic document-viewer framework

## Required Report

Report back to Supervisor thread `019ed023-8e41-7ad0-8117-6246b8ffa0bb` in Chinese using `coordination/output_contract.md`.

Include:

1. Code Agent thread id.
2. Task card path.
3. Routes implemented.
4. API contracts consumed.
5. Module structure.
6. Changed files.
7. Verification commands and results.
8. Browser acceptance evidence.
9. Known limitations.
10. Requested Supervisor action.

## Suggested Prompt for Code Agent

```text
You are the J-Study Code Agent.

Execute:

multi-agent/jstudy-product-build/task_cards/0004-frontend-foundation-course-outline.md

Start by reading docs/frontend/clinical-workbench-spec.md and writing the required Phase 0 plan. Then implement the first formal apps/web frontend using Next.js App Router, TypeScript, Tailwind, shadcn/ui, and TanStack Query.

Integrate the existing backend only. Do not add backend endpoints. The first workflow is Course Outline Mode: mode selector -> upload outline -> upload matching PDFs -> poll job -> read sectioned material package -> preview source PDFs -> citation jump.

Report back in Chinese to Supervisor thread 019ed023-8e41-7ad0-8117-6246b8ffa0bb.
```