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
web_mvp.py              FastAPI MVP service and temporary built-in test UI
mvp_runner.py           PDF -> retrieval -> prompt -> Markdown pipeline
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
  core/                 Shared workflow contracts, jobs, citations, result types
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
python -m py_compile web_mvp.py
python -m unittest discover -s tests -v
```

Run the current MVP service:

```powershell
python -m uvicorn web_mvp:app --host 127.0.0.1 --port 8765
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
