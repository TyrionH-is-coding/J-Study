# Roadmap

## Phase 0: Repository and Documentation Baseline

Goal: make the project understandable before adding more code.

Deliverables:

- product vision
- architecture overview
- roadmap
- development standards
- archived MVP handoff notes
- target repository structure

Acceptance:

- a new contributor can understand the product direction from `README.md`
- root-level documents are not scattered
- current MVP verification commands are documented

## Phase 1: Formalize the MVP Backend

Goal: keep the current backend behavior while moving it into a product structure.

Deliverables:

- move FastAPI code to `apps/api` - done
- move generation pipeline behind `packages/core` - done
- split parser, retrieval, and medicine domain logic into dedicated modules - done
- keep PyMuPDF as default parser - done
- keep existing tests passing - done
- add explicit dependency file - done
- split runtime settings and job lifecycle - done
- split provider calls - done
- split storage/output contracts - done
- split legacy CLI entrypoint from pipeline orchestration - done
- add lightweight JSON job persistence for single-server deployment - done

Acceptance:

- existing API contract still works
- `python -m unittest discover -s tests -v` passes
- old root-level scripts are documented as compatibility shims
- runtime settings can come from environment variables before server deployment - done for API key, model names, jobs directory, and template paths

## Phase 1.5: User Auth and Invite Gate

Goal: add the minimum user boundary before the full frontend is built.

Deliverables:

- Postgres-backed user persistence
- email/password registration and login
- reusable invite code required for registration
- `email_verified` field reserved but not enforced
- HTTP-only cookie session
- admin-token-protected invite-code management
- user-owned jobs and result access control

Acceptance:

- users can register only with an enabled invite code
- one shared invite code can register multiple users
- users can only see their own jobs and generated artifacts
- admin invite management remains protected by `JSTUDY_ADMIN_TOKEN`
- auth behavior is covered by automated tests before server deployment

## Phase 2: Frontend MVP

Goal: replace the temporary built-in HTML with a real frontend.

Deliverables:

- `apps/web` with Next.js
- selected shadcn/ui template
- login and registration pages
- upload page
- job progress state
- generated Markdown reader
- source PDF preview panel
- evidence button to page jump

Acceptance:

- unauthenticated users see the login/register flow
- user can upload a PDF from the frontend
- generated output displays cleanly
- clicking "依据 E001" scrolls only the source preview area
- frontend and backend run locally together

## Phase 3: Single-Server Deployment

Goal: deploy the MVP to the prepared domain and server.

Deliverables:

- backend Dockerfile - done
- backend Docker Compose scaffold - done
- frontend Dockerfile after `apps/web` exists
- reverse proxy config
- `.env.example` - done for backend runtime settings
- mounted `data/` directory - done for backend jobs
- deployment runbook - done for backend-only Docker Compose; full runbook after frontend and reverse proxy exist

Acceptance:

- `https://domain/` serves the frontend
- `https://domain/api/...` reaches the backend
- secrets are not committed
- deployment can be reproduced on another Linux server

## Phase 4: MVP Quality and Reliability

Goal: make generated output more stable and auditable.

Deliverables:

- stronger quality report - done for evidence-id validation, unused-evidence warnings, implementation wording checks, and section citation coverage
- parser/retrieval trace review tools - done for retrieval trace API
- better failed-job errors - done with exception type in job status
- upload limits - done for courseware PDF type and size
- cache controls - done for dynamic API status responses and private generated artifacts
- optional cleanup policy - done with disabled-by-default finished-job retention

Acceptance:

- failed jobs explain what failed
- generated output cites valid evidence IDs
- quality reports show citation coverage by markdown section
- frontend polling is not served stale job state from browser caches
- single-server deployments can opt into finished-job cleanup without deleting queued or running jobs
- low-quality output is flagged before user trust is damaged

## Phase 5: Multi-Discipline Domain Packs

Goal: prove that medicine is a first domain, not a hard-coded product boundary.

Deliverables:

- stable domain-pack interface
- medicine pack extracted from root templates
- at least one second lightweight domain prototype
- domain-specific query planner contract

Acceptance:

- adding a new subject does not require editing platform pipeline code
- medicine-specific prompts and rules live under `packages/domains/medicine`

## Phase 5.5: Knowledge Snippet Feedback Hook

Goal: leave the product hook for user-driven quality improvement without making feedback affect generation too early.

Deliverables:

- frontend selection-and-like event shape
- backend raw feedback API contract
- feedback records tied to user, job, scenario, subject, selected text, and source evidence ids
- embedding generation for feedback fragments
- semantic deduplication into administrator-visible candidate clusters
- review status model: `candidate`, `approved`, `rejected`, `deprecated`

Acceptance:

- liked fragments are saved as raw feedback only
- candidate clusters are visible to administrators
- no candidate can affect generation until it is approved
- approved snippets are retrieved as auxiliary guidance, not as independent fact sources
- automatic replacement remains disabled until current-upload evidence matching is reliable

## Phase 6: Question Generation

Goal: generate new questions from past papers and courseware.

Deliverables:

- past-paper parsing workflow
- extracted question templates
- question style classification
- source-topic alignment
- generated questions with evidence-backed explanations

Acceptance:

- system can generate new questions in the style of uploaded past papers
- answers and explanations cite courseware evidence when possible

## Phase 7: Heavier Parsing and Production Services

Goal: add infrastructure only when product usage justifies it.

Possible deliverables:

- MinerU parser implementation
- parser selection policy
- background worker
- Redis queue
- Postgres job store
- object storage
- advanced user roles and permissions

Acceptance:

- heavier parsing improves retrieval quality on real complex PDFs
- infrastructure reduces operational risk rather than adding complexity for its own sake
