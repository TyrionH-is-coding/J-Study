# Architecture Overview

## Summary

J-Study is a single-server MVP that should evolve into a formally structured product. The current backend now has canonical package paths: `apps/api/jstudy_api/app.py` serves the FastAPI MVP, `packages/core/jstudy_core/pipeline.py` orchestrates the generation pipeline, `packages/parsers` owns document parsing, `packages/retrieval` owns chunking and hybrid retrieval, and `packages/domains/medicine.py` owns the first subject pack. Root-level `web_mvp.py` and `mvp_runner.py` remain compatibility shims for old commands.

## Target Repository Structure

```text
apps/
  api/
    # FastAPI service, upload endpoints, job status, result APIs
  web/
    # Next.js + shadcn/ui frontend
packages/
  core/
    # workflow contracts, job models, citations, output result types
  parsers/
    # PyMuPDF parser now; future MinerU implementation
  retrieval/
    # chunking, BM25/RRF, RAG adapters
  domains/
    medicine/
      # first subject pack
configs/
  rag/
deploy/
  docker-compose/
docs/
```

The first backend reorganization steps are implemented. Further steps should split runtime settings, job state, storage, and provider calls without changing API behavior.

## Runtime Flow

```text
Upload PDF + optional outline
-> Document Parser
-> chunks with page metadata
-> retrieval query planner
-> embedding + lexical retrieval
-> evidence selection
-> domain prompt/template
-> LLM generation
-> Markdown + evidence + evidence links + quality report
-> frontend reader with source-page citation jumps
```

## Platform Layer

The platform layer should own common product behavior:

- file upload
- job lifecycle
- parser selection
- retrieval execution
- evidence link contracts
- output storage
- API response shape
- deployment and runtime configuration

It should not own medicine-specific prompt wording, mnemonic rules, or subject quality standards.

## Document Parser Boundary

The parser boundary is intentional. Parser output should preserve enough metadata to support citation jumps:

- source file
- page number
- extracted text
- optional layout blocks
- optional table or image references
- optional bounding boxes in future versions

### Default Parser: PyMuPDF

PyMuPDF is the default MVP parser. It is fast, simple to deploy, and good enough for text-first PPT-exported PDFs where citation to the original page is already available.

### Future Parser: MinerU

MinerU should be added as a heavier optional parser, not as the first deployment dependency. It is valuable for complex layouts, tables, scanned documents, Office files, and future past-paper question extraction.

The architecture should allow:

```text
parser = pymupdf | mineru
```

without rewriting retrieval or domain logic.

## Retrieval Layer

The current MVP retrieval approach is:

- page-aware chunking
- embedding similarity
- BM25-style lexical matching
- reciprocal-rank fusion
- low-value chunk filtering
- per-query evidence limits

This lives in `packages/retrieval/` so it can be reused across domains.

## Domain Layer

Domain packs should define subject-specific behavior. The first pack is `medicine`.

Expected domain-pack responsibilities:

- query planning
- prompt template
- output style rules
- mnemonic and terminology sources
- evidence filtering rules
- quality audit rules
- future question-generation policy

The preferred model is hybrid:

- configuration files for simple prompt and rule changes
- code modules for advanced planners, filters, graders, and generators

## Frontend Architecture

The frontend should be `apps/web` with Next.js and shadcn/ui.

Design rules:

- start from a selected shadcn/ui template
- keep the template's main layout stable
- adjust brand color, typography, density, states, and product-specific panels
- build the reader around two independent areas: generated material and source preview
- source preview should support citation jumps without scrolling the whole page

## Deployment Architecture

The first deploy target is a single Linux server using Docker Compose.

Recommended routing:

```text
https://domain.example/        -> Next.js frontend
https://domain.example/api/... -> FastAPI backend
```

This avoids early CORS complexity and makes the pilot easier to migrate.

Expected deployment components:

- reverse proxy: Nginx or Caddy
- frontend container
- backend container
- mounted `data/` volume for uploads, outputs, and cache
- `.env` for runtime secrets

Future components can include Redis, Postgres, object storage, and a separate worker.

## Current Technical Debt

The MVP intentionally has several temporary choices:

- `apps/api/jstudy_api/app.py` still combines API and temporary UI
- `packages/core/jstudy_core/pipeline.py` still combines provider calls, evidence item building, citation links, orchestration, and CLI
- root-level `web_mvp.py` and `mvp_runner.py` are compatibility shims
- job state is in memory
- outputs are local files
- API key currently comes from a local file in the old workflow

These should be addressed in roadmap order, not all at once.
