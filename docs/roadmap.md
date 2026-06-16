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
- user can choose an exposed scenario before upload
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

## Phase 4.5: Service Mode Model

Goal: define the product and backend boundary for the three generation modes before expanding upload flows.

Deliverables:

- explicit `single_courseware`, `batch_courseware`, and `course_outline` service modes
- frontend upload entry points that can explain the three modes without mixing them with subject scenario or parser choice
- backend request contract that records service mode separately from `scenario_id` and `parser_profile_id`
- package-output contract for multi-section material
- section-level evidence, source-file metadata, and quality status model
- full-export contract that can assemble all sections into one complete document

Acceptance:

- Single Courseware Mode remains the default MVP path and produces one generated material output
- Batch Courseware Mode is designed as a chapter/topic-browsable material package, not just several independent single-PDF jobs
- Course Outline Mode is designed as an outline-driven material package whose section order follows the uploaded outline
- Batch Courseware Mode and Course Outline Mode both support web browsing by section and full-document export
- service mode selection does not change the selected subject scenario or parser profile

## Phase 5: Multi-Discipline Domain Packs

Goal: prove that medicine is a first domain, not a hard-coded product boundary, while keeping J-Study more vertical than a general DeepTutor-style assistant.

Deliverables:

- stable domain-pack interface
- medicine pack extracted from root templates
- subject-specific soul profile authoring path
- scenario visibility managed by admin settings
- at least one second lightweight domain prototype
- domain-specific query planner contract

Acceptance:

- adding a new subject does not require editing platform pipeline code
- medicine-specific prompts and rules live under `packages/domains/medicine`
- a new subject can start with a blank hidden soul profile, then become visible only after the profile has usable content
- service delivery is not blocked by fully populated soul libraries

## Phase 5.25: Batch Courseware Mode

Goal: let users upload multiple related courseware PDFs and receive one navigable study-material package.

Deliverables:

- multi-PDF upload API and frontend flow
- source-file metadata in chunks, evidence, and citation links
- section planning from file order, detected headings, or inferred topics
- cross-file retrieval and evidence aggregation
- duplicate-topic handling across uploaded PDFs
- package reader with section navigation and source preview
- full-document export assembled from package sections

Acceptance:

- user can upload multiple PDFs in one job
- generated output is browsable by chapter or topic in the web app
- each section can cite evidence from one or more source PDFs
- user can export the whole package as one complete material file
- the system does not lose source-file identity when rendering citation jumps

## Phase 5.4: Course Outline Mode

Goal: turn a full course outline plus all courseware into a course-level material package.

Deliverables:

- outline upload and parsing workflow
- outline-node section plan
- retrieval across all uploaded courseware per outline node
- evidence coverage report per outline node
- section-by-section web browsing
- full course-material export

Acceptance:

- user can upload a course outline and multiple courseware PDFs
- output order follows the uploaded outline
- each outline node shows whether evidence is sufficient, weak, or missing
- generated sections can cite evidence from any uploaded courseware
- user can browse the course package by section and export the complete course material

## Phase 5.5: Knowledge Snippet Feedback Hook

Goal: leave the product hook for user-driven quality improvement without making feedback affect generation too early, and grow J-Study's vertical snippet ecosystem one reviewed candidate at a time.

Deliverables:

- frontend selection-and-like event shape
- backend raw feedback API contract
- feedback records tied to user, job, scenario, subject, selected text, and source evidence ids
- embedding generation for feedback fragments
- semantic deduplication into administrator-visible candidate clusters
- review status model: `candidate`, `approved`, `rejected`, `deprecated`
- subject and scenario metadata on every snippet candidate
- manual review workflow before snippets become reusable product knowledge

Acceptance:

- liked fragments are saved as raw feedback only
- candidate clusters are visible to administrators
- no candidate can affect generation until it is approved
- approved snippets are retrieved as auxiliary guidance, not as independent fact sources
- automatic replacement remains disabled until current-upload evidence matching is reliable
- snippet growth improves vertical quality without turning the library into generic prompt storage

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
