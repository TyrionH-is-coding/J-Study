# Development Standards

## Scope Discipline

Make small changes that directly serve the current goal. Do not refactor adjacent code just because it looks imperfect. If unrelated problems are noticed, document them or add them to the roadmap instead of mixing them into the current change.

## Branching

Use `main` as the stable deployable branch.

Use short-lived branches:

```text
feature/<short-name>
fix/<short-name>
deploy/<target>
```

Current active branch:

```text
feature/backend-frontend-mvp
```

## Commit Rules

- one clear purpose per commit
- do not commit secrets, local `.env`, uploaded PDFs, logs, `web_jobs/`, or generated RAG outputs
- include tests or verification notes for behavior changes
- keep generated dependency lockfiles only when they belong to the app being changed

## Verification

Current backend baseline:

```powershell
python -m py_compile web_mvp.py mvp_runner.py apps/api/jstudy_api/app.py packages/core/jstudy_core/pipeline.py
python -m unittest discover -s tests -v
```

After the repository is reorganized, these commands should be replaced with app-specific commands.

Future expected checks:

```text
apps/api: backend tests and type/lint checks
apps/web: frontend tests, typecheck, lint, build
deploy: docker compose config validation
```

## Project Boundaries

Platform code should provide generic capabilities:

- upload
- parsing
- retrieval
- generation orchestration
- evidence contracts
- job status
- frontend rendering shell
- deployment

Domain code should provide subject behavior:

- prompt templates
- query planning
- evidence filtering
- mnemonics
- terminology
- quality checks
- question-generation policy

Medicine is the first domain pack, not the product boundary.

Current backend module ownership:

```text
apps/api/jstudy_api       FastAPI app and HTTP contract
packages/core/jstudy_core Pipeline orchestration, job lifecycle, provider calls, citations, runtime settings
packages/parsers          Document parsing implementations
packages/retrieval        Chunking and retrieval logic
packages/domains          Subject-specific behavior
```

## Parser Standards

All parsers should return page-aware text. Future parsers can return richer layout data, but page number must remain available for citation.

Default MVP parser:

```text
PyMuPDF
```

Future optional parser:

```text
MinerU
```

Do not make MinerU required for the first lightweight deployment.

## Frontend Standards

Use Next.js and shadcn/ui.

Frontend design should be template-first:

- choose a shadcn/ui template
- keep the main layout stable
- change color, density, texture, state styling, and product-specific components
- do not invent a new design system during MVP

Reader behavior:

- generated material and source preview should scroll independently
- evidence buttons should scroll only the source preview container
- API calls should use same-domain `/api/...` paths in deployment

## Deployment Standards

Use Docker Compose for the pilot deployment.

Deployment should be portable across servers:

- no manually installed app dependencies outside containers
- secrets in `.env`, never in Git
- `SILICONFLOW_API_KEY` is the deployment API key source
- persistent files mounted under a data volume
- domain routes frontend at `/` and backend at `/api/...`

Initial deployment can be single-server. Add Redis, Postgres, object storage, or workers when needed by real usage.

## Documentation Standards

Documentation should distinguish:

- current state
- target state
- decisions already made
- open questions
- future roadmap

Do not write docs that imply a refactor has already happened when it has not.

Archive historical MVP notes under `docs/archive/` instead of leaving them in the repository root.
