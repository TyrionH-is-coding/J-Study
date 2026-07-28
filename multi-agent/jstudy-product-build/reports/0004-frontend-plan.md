# 0004 Frontend Foundation Phase 0 Plan

## 1. Assumptions and Success Criteria

- `docs/frontend/clinical-workbench-spec.md` is the approved product and visual baseline. The untracked `frontend/frontend.txt` Ballpit experiment is not part of this task because it conflicts with the approved workbench direction and the prohibition on decorative orb-style UI.
- The current FastAPI implementation is the contract source. This task consumes existing `/api/*` routes and does not change backend files or route behavior.
- Course Outline Mode is the only enabled service-mode workflow. General, Engineering, Law, `batch_courseware`, and metadata-only `mode` are not exposed.
- Success means a user can register or sign in, choose Course Outline Mode, upload one outline plus one or more PDFs, follow the job through queued/running/completed/failed states, read sectioned material, switch sources by `source_id`, preview a cited page, and export the complete Markdown document.

## 2. Package Manager and Next.js Setup

- Package manager: `npm 10.9.7`, with a package-local lockfile at `apps/web/package-lock.json`. No root workspace file is needed because this is the repository's first JavaScript package.
- Runtime baseline: Node.js `22.22.2`.
- App scaffold: Next.js `16.2.10` App Router, React `19.2.4` (the version pinned by this Next scaffold), TypeScript, ESLint, `src/` layout, and alias `@/*`.
- Styling: Tailwind CSS `4.3.3` with CSS variables from the Clinical Workbench token set.
- Components: shadcn CLI `4.13.0`; only the base components used by this workflow are added under `src/components/ui`.
- Server state: `@tanstack/react-query 5.101.2`.
- Markdown: `react-markdown` plus `remark-gfm`; raw HTML is not enabled, so generated Markdown cannot inject executable HTML. Evidence comments are converted into explicit citation controls before rendering.
- Tests: Vitest + React Testing Library for narrow behavior tests and Playwright for browser acceptance.

## 3. Route Tree

```text
apps/web/src/app/
  page.tsx                         / redirects from GET /api/auth/me state
  login/page.tsx                   /login email/password form
  register/page.tsx                /register email/password/invite form
  modes/layout.tsx                 authenticated workspace shell
  modes/page.tsx                   /modes service-mode selector
  modes/course-outline/page.tsx    /modes/course-outline upload workflow
  jobs/[jobId]/page.tsx            /jobs/[jobId] polling and reader
```

Client-side guards use the same `GET /api/auth/me` query as the root redirect. They never store tokens; the backend HTTP-only cookie remains authoritative.

## 4. Module Boundaries

```text
apps/web/src/lib/api/              one API client and all auth/job/source/evidence/package types
apps/web/src/features/auth/        session query, forms, logout, protected-route behavior
apps/web/src/features/modes/       enabled service-mode selector only
apps/web/src/features/course-outline/
                                    outline/PDF selection, validation, FormData submit
apps/web/src/features/reader/      polling, output/package loading, section navigation, export
apps/web/src/features/source-preview/
                                    source_id selection, page image, citation-local scrolling
apps/web/src/components/ui/        shadcn primitives only, no business state
apps/web/src/styles/               Tailwind globals and Clinical Workbench tokens
apps/web/e2e/                      real-URL browser tests and deterministic backend test server
```

TanStack Query owns remote state. Feature-local React state owns selected files, section, source, and page. Redux, Zustand, a generic viewer abstraction, PWA, and i18n are not introduced.

## 5. API Type Strategy

The backend has no narrow generated schemas for these dictionary responses, so the first version defines one intentionally small TypeScript contract in `apps/web/src/lib/api/types.ts` and exports it only through `apps/web/src/lib/api/index.ts`.

Central types cover `User`, `ApiError`, `Options`, `GenerateResponse`, `JobStatus`, `SourceFile`, `PdfInfo`, `MaterialPackage`, `MaterialSection`, `EvidenceItem`, and `EvidenceLink`. Runtime boundary helpers validate required discriminants and arrays before feature code consumes responses. Feature folders import these types; they do not redefine auth/job/source/evidence shapes. `SourceFile.source_id` is the identity key and `file_name` is display-only.

Consumed routes:

```text
GET  /api/auth/me
POST /api/auth/login
POST /api/auth/register
POST /api/auth/logout
GET  /api/options
POST /api/generate
GET  /api/jobs/{job_id}
GET  /api/jobs/{job_id}/output
GET  /api/jobs/{job_id}/package
GET  /api/jobs/{job_id}/evidence-links
GET  /api/jobs/{job_id}/export
GET  /api/jobs/{job_id}/pdfs
GET  /api/jobs/{job_id}/pdfs/{source_id}/pdf-info
GET  /api/jobs/{job_id}/pdfs/{source_id}/pdf-page/{page_no}.png
```

## 6. Local `/api/*` Routing

`next.config.ts` rewrites `/api/:path*` to `${JSTUDY_API_ORIGIN}/api/:path*`, defaulting to `http://127.0.0.1:8000`. Browser code always calls relative `/api/...` URLs with `credentials: "include"`. This keeps the HTTP-only session cookie same-origin in local development and requires no CORS or FastAPI changes. Production can point `JSTUDY_API_ORIGIN` at the API service while preserving the same public-origin contract.

## 7. Browser E2E Strategy

- Playwright starts two real servers: a FastAPI process on `127.0.0.1:8000` instantiated from the existing `create_app()` with a deterministic test runner, and Next.js on `127.0.0.1:3000`.
- The support runner writes the same job output/package/evidence-link artifacts as the production runner and uses the existing auth, ownership, upload, polling, and source-preview routes. It does not add or alter backend endpoints.
- Tests navigate the real `http://127.0.0.1:3000` URL and cover registration/login/me/logout/guards, mode selection, one- and two-PDF upload, completed and failed job UI, source switching, citation-local scroll, refresh recovery, zero app-shell horizontal overflow, and unexpected console errors.
- Projects run at `390x844`, `768x1024`, and `1440x900`. DOM assertions and interactions are acceptance criteria; screenshots are supplemental evidence only.
- A failed-job E2E uses a filename recognized only by the injected test runner to raise an error after normal upload acceptance. This remains test support under `apps/web` and does not change production behavior.

## 8. TDD and Verification Sequence

1. Add API/client and pure rendering tests, run them red, then implement the centralized API layer.
2. Add auth/mode/upload interaction tests, run them red, then implement those routes and features.
3. Add reader/source-preview/citation tests, run them red, then implement the three-pane and responsive reader.
4. Add Playwright browser tests, run against the real URLs, and fix only failures within `apps/web`.
5. Run `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`, Playwright at all three viewports, `python -m unittest discover -s tests -v`, and `git diff --check`.

## 9. Risks and Stop Conditions

- The package contains section metadata but the generated body is returned as one Markdown document. The reader will split that document by section headings while preserving the package order; it will not invent a new backend section-content endpoint.
- Evidence links are represented by backend-inserted HTML comments. The frontend must transform only the recognized `<!-- evidence: E### -->` markers into citation controls and keep arbitrary raw HTML disabled.
- Registration invite requirements are runtime-dependent. The registration form includes an optional invite code and displays backend validation errors without guessing the server setting.
- Backend upload count/total-size/timeouts are explicitly deferred by the task card. The UI describes accepted file types but does not claim limits the backend does not expose.
- Stop and report if same-origin rewrites do not preserve the auth cookie, package/source shapes differ from the current implementation, or source-specific page PNG endpoints fail with valid PDFs.
