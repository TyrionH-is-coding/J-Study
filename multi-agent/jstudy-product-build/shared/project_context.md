# J-Study Project Context

J-Study is a FastAPI-first education product currently validating a medicine-focused study-material generation workflow.

The long-term product is multi-discipline. Medicine is the first validated domain, not the final boundary.

## Current Product Stage

The backend is mostly ready for the current pilot path. The immediate next product phase is frontend construction and frontend-backend integration.

That does not mean backend work is finished forever. It means new backend work should be driven by explicit frontend needs, deployment needs, or clearly scoped task cards.

## Current Product Decisions

- The intended product path is FastAPI `POST /api/generate`.
- CLI compatibility is secondary unless explicitly scoped into a task.
- The approved target is MinerU-only product extraction through the MinerU
  Precision Extract cloud API.
- Parser choice is admin/runtime infrastructure and is not exposed to users.
- PyMuPDF remains an internal utility for PDF validation, metadata, and page
  rendering; it must not remain a product text-extraction path after migration.
- The current PyMuPDF pipeline remains temporarily active only until the
  contract-first MinerU migration passes its verification gates.
- Frontend direction is a formal web frontend based on selected shadcn/ui templates; temporary backend-served UI may be used for pilot testing.
- Users should not configure model providers; model/RAG/parser/content-pack settings are admin-owned.
- Soul profiles and knowledge snippet library are core vertical assets.
- Next.js, FastAPI, PostgreSQL, worker, and persistent storage deploy on Tencent
  Cloud. The spare computer is a future optional MinerU worker, not an initial
  production dependency.
- Current databases, uploads, and generated jobs are disposable test data.
  Product documents, Soul Profiles, Knowledge Snippets, and admin configuration
  schemas are durable.

The controlling refactor document is:

- `docs/architecture/refactor-blueprint.md`

## Candidate Branch Context

Candidate branches may contain useful work, but should not be merged wholesale:

- `feat/multi-domain-modes`
- `feat/frontend-polish-katex`
- `feat/sectional-generation`

The current preferred absorption path after Code Agent onboarding is a larger FastAPI-first MVP merge task with staged checkpoints:

1. inspect candidate branches and write an inventory before editing business code
2. prioritize stable FastAPI product-path capabilities around `POST /api/generate`, job status, artifacts, evidence links, PDF preview, and section/package contracts
3. absorb useful temporary UI, Markdown, KaTeX, reader, and citation-jump improvements only after the backend contract is stable
4. absorb soul/profile/content-pack work only when it preserves admin-controlled visibility and does not expose blank subject profiles
5. keep CLI compatibility, standalone admin helper services, and broad batch/course-outline expansion secondary unless explicitly scoped by the task card
