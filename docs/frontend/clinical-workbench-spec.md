# Clinical Workbench Frontend Specification

## Status

This is the approved baseline for the first formal J-Study frontend. Do not start `apps/web` implementation by inventing a new visual direction or route model.

## Product Entry

The frontend is mode-first:

1. User signs in.
2. User lands on a service-mode selector.
3. The first completed workflow is Course Outline Mode.
4. Course Outline Mode asks for an outline first, then matching courseware PDFs.
5. Generated material is browsed by section and can be exported as a complete document.

Do not let the frontend use `mode` to infer service mode. The request field is `service_mode`.

## Visual Style

Name: Clinical Workbench.

The UI should feel like a professional reading and generation workspace, not a marketing landing page.

Baseline:

- restrained, clinical, high-contrast surface system
- dense but readable information layout
- three-pane reader on desktop
- bottom drawer or stacked panels on small screens
- no decorative hero, gradient orb, bokeh, or oversized marketing card layout
- no nested cards for page sections
- cards only for repeated items, modals, and framed tools

Suggested tokens:

```text
background: #F7F8FA
surface: #FFFFFF
surface-muted: #F1F4F7
border: #D8DEE6
text-primary: #17212B
text-secondary: #5B6773
accent: #0F766E
accent-muted: #CCFBF1
warning: #B45309
danger: #B42318
info: #2563EB
radius: 8px max for cards and panels
```

Typography:

- UI font: system sans-serif
- body size: 14-16px
- compact panel headings: 16-20px
- avoid viewport-scaled font sizes
- letter spacing: 0

## Technical Stack

Use:

- Next.js App Router
- TypeScript
- Tailwind CSS
- shadcn/ui
- TanStack Query

Do not add Redux, Zustand, PWA, i18n, a general file-viewer framework, or a full design-system package in the first frontend task unless a later task card explicitly requires it.

## Route Rules

Initial route set:

```text
/                     redirect by auth state
/login                email/password login
/register             email/password registration
/modes                service-mode selector
/modes/course-outline outline + multiple PDFs workflow
/jobs/[jobId]         material package reader
```

Admin routes are out of scope for the first formal frontend task.

## Module Boundaries

Use one source of truth per concern:

```text
apps/web/src/app                    App Router pages/layouts
apps/web/src/features/auth          auth forms, route guards, session hooks
apps/web/src/features/modes         service-mode selector
apps/web/src/features/course-outline upload and submit workflow
apps/web/src/features/reader        package/section browsing and export
apps/web/src/features/source-preview PDF source list, page preview, citation jump
apps/web/src/lib/api                API client and generated/validated types only
apps/web/src/components/ui          shadcn base components only
apps/web/src/styles                 Tailwind globals and design tokens
```

Rules:

- `course-outline` owns upload state and submit behavior only.
- `reader` owns material package loading, section navigation, and export controls.
- `source-preview` owns source switching, page rendering, and citation scrolling.
- `lib/api` must not contain UI state.
- `components/ui` must not contain J-Study business logic.
- File names must not be used as source keys; use `source_id`.

## API Contract Baseline

The first frontend must integrate the existing backend contract:

```text
GET  /api/auth/me
POST /api/auth/login
POST /api/auth/register
POST /api/auth/logout
GET  /api/options
POST /api/generate
GET  /api/jobs/{job_id}
GET  /api/jobs/{job_id}/package
GET  /api/jobs/{job_id}/export
GET  /api/jobs/{job_id}/pdfs
GET  /api/jobs/{job_id}/pdfs/{source_id}/pdf-info
GET  /api/jobs/{job_id}/pdfs/{source_id}/pdf-page/{page_no}.png
```

Course Outline upload:

```text
service_mode=course_outline
outline=<required .md/.txt/.pdf>
pdfs=<one or more PDFs, repeated multipart field>
scenario_id=<optional>
mode=<metadata only; hidden in first UI>
```

The approved target does not expose or submit `parser_profile_id`. MinerU is the
platform parsing service and parser configuration is admin-owned. The currently
implemented optional field is a migration artifact and will be removed when the
MinerU pipeline contract is switched.

Frontend must not hand-copy backend fields in multiple places. Prefer OpenAPI-generated or schema-validated TypeScript types before adding broad UI features.

## Reader Behavior

Desktop reader:

```text
left: section navigation and source list
center: generated material
right: source preview
```

Required behavior:

- refresh `/jobs/[jobId]` restores the reader from backend state
- section navigation does not lose selected source/page
- citation click scrolls only the source preview area
- citation targets use `job_id`, `source_id`, `page`, and `chunk_id`
- weak-evidence sections are visible but not treated as hard failures
- completed jobs expose full Markdown export

## Browser Acceptance Matrix

Run against the real local URL, not static `setContent` screenshots.

Viewports:

```text
390x844
768x1024
1440x900
```

Required checks:

- login, register, me, logout, route guard
- outline upload is accepted
- 1 PDF upload is accepted
- 2 PDF upload is accepted
- upper-limit PDF upload behavior is tested after backend limits exist
- job polling handles queued, completed, and failed states
- multi-source switching works
- citation click scrolls only the source preview
- refresh `/jobs/[jobId]` recovers state
- `clientWidth === scrollWidth` for primary app shell
- browser console has zero unexpected errors

Screenshots are evidence only. DOM assertions and real interactions are the pass/fail criteria.

## Hard Prohibitions

- Do not copy auth, job, source, or evidence types into separate drifting modules.
- Do not use filenames as source identity.
- Do not let frontend `mode` guess backend `service_mode`.
- Do not store long-lived tokens in URL, localStorage, or logs.
- Do not use static screenshot rendering as frontend completion proof.
- Do not expose blank General/Engineering/Law scenarios.
- Do not add broad state libraries or a generic document viewer before the first reader works.
- Do not commit runtime `data/`, uploads, secrets, or real user files.
