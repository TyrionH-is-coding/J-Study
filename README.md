# J-Study

J-Study is a multi-discipline study-material generation product. The current MVP starts with medicine because it is the first domain where we can validate quality, citation, and learning-output design with real domain judgment.

The product goal is not limited to medicine. The platform should eventually support different subject packs, each with its own prompts, retrieval strategy, output templates, quality checks, and question-generation logic.

## Current MVP

The current backend can:

- accept one courseware PDF and an optional outline
- extract page text with PyMuPDF
- retrieve evidence chunks with embedding + BM25/RRF
- retrieve related mnemonics from `mnemonics.md`
- generate Markdown study material using `soul.md`
- emit evidence links so the UI can jump from "依据 E001" to the original PDF page

This is still a single-machine MVP. It does not yet include users, database-backed jobs, object storage, a production task queue, or a separate frontend app.

## Repository Status

The repository is moving from MVP files to a formal product structure.

Current important files:

```text
apps/api/jstudy_api/    FastAPI MVP service and temporary built-in test UI
packages/core/          Pipeline orchestration, job lifecycle, output storage, runtime settings, CLI
packages/core/jstudy_core/jobs.py In-memory MVP job lifecycle store
packages/core/jstudy_core/providers.py SiliconFlow chat and embedding client helpers
packages/core/jstudy_core/settings.py Runtime configuration helpers
packages/core/jstudy_core/storage.py Output path contracts and JSON helpers
packages/parsers/       PyMuPDF parser implementation
packages/retrieval/     Chunking, BM25/RRF, retrieval adapter
packages/domains/       Medicine domain pack and future subject packs
web_mvp.py              Compatibility shim for the old Uvicorn entrypoint
mvp_runner.py           Compatibility shim for the old CLI entrypoint
soul.md                 Medicine output style and study-material template
mnemonics.md            Medicine mnemonic seed library
rag-config.example.json Example RAG settings
tests/                  Current backend and rendering contract tests
docs/                   Product, architecture, roadmap, and development docs
```

Target structure:

```text
apps/
  api/                  FastAPI backend
  web/                  Next.js + shadcn/ui frontend
packages/
  core/                 Shared workflow orchestration, citations, result types
  parsers/              PyMuPDF default parser, future MinerU parser
  retrieval/            Chunking, embedding, BM25/RRF, RAG adapter
  domains/
    medicine/           First subject pack
configs/
  rag/                  Runtime examples and safe defaults
deploy/
  docker-compose/       Single-server deployment assets
docs/
```

## Local Verification

Run from the repository root:

```powershell
python -m py_compile web_mvp.py mvp_runner.py apps/api/jstudy_api/app.py packages/core/jstudy_core/pipeline.py packages/core/jstudy_core/jobs.py packages/core/jstudy_core/providers.py packages/core/jstudy_core/settings.py packages/core/jstudy_core/storage.py
python -m unittest discover -s tests -v
```

Install backend dependencies:

```powershell
python -m pip install -r requirements.txt
```

Configure the API key with an environment variable:

```powershell
$env:SILICONFLOW_API_KEY="your-key"
```

For deployment, start from [.env.example](.env.example) and keep real secrets out of Git.
`JSTUDY_JOBS_DIR`, `JSTUDY_SOUL_PATH`, and `JSTUDY_MNEMONICS_PATH` can be used to move runtime data and domain templates outside the repository in Docker or on a server.

Run the current MVP service with the compatibility entrypoint:

```powershell
python -m uvicorn web_mvp:app --host 127.0.0.1 --port 8765
```

Or with the canonical backend entrypoint:

```powershell
python -m uvicorn apps.api.jstudy_api.app:app --host 127.0.0.1 --port 8765
```

Then open:

```text
http://127.0.0.1:8765/
```

## Key Documents

- [Product Vision](docs/product/vision.md)
- [Architecture Overview](docs/architecture/overview.md)
- [Roadmap](docs/roadmap.md)
- [Development Standards](docs/development/standards.md)
- [Git Workflow](docs/development/git-workflow.md)

Historical MVP notes are kept under `docs/archive/`.
