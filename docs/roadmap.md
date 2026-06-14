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

## Phase 2: Frontend MVP

Goal: replace the temporary built-in HTML with a real frontend.

Deliverables:

- `apps/web` with Next.js
- selected shadcn/ui template
- upload page
- job progress state
- generated Markdown reader
- source PDF preview panel
- evidence button to page jump

Acceptance:

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
- `.env.example`
- mounted `data/` directory
- deployment runbook

Acceptance:

- `https://domain/` serves the frontend
- `https://domain/api/...` reaches the backend
- secrets are not committed
- deployment can be reproduced on another Linux server

## Phase 4: MVP Quality and Reliability

Goal: make generated output more stable and auditable.

Deliverables:

- stronger quality report
- parser/retrieval trace review tools
- better failed-job errors
- upload limits - done for courseware PDF type and size
- cache controls
- optional cleanup policy

Acceptance:

- failed jobs explain what failed
- generated output cites valid evidence IDs
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
- user accounts and permissions

Acceptance:

- heavier parsing improves retrieval quality on real complex PDFs
- infrastructure reduces operational risk rather than adding complexity for its own sake
