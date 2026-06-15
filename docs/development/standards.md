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
python -m py_compile web_mvp.py mvp_runner.py apps/api/jstudy_api/app.py apps/api/jstudy_api/ui.py apps/api/jstudy_api/admin_ui.py packages/core/jstudy_core/admin_settings.py packages/core/jstudy_core/scenario_router.py packages/core/jstudy_core/parser_profile_router.py packages/core/jstudy_core/pipeline.py packages/core/jstudy_core/cli.py packages/core/jstudy_core/citations.py packages/core/jstudy_core/jobs.py packages/core/jstudy_core/providers.py packages/core/jstudy_core/settings.py packages/core/jstudy_core/storage.py packages/parsers/mineru_parser.py packages/parsers/pymupdf_parser.py
python -m unittest discover -s tests -v
```

After the repository is reorganized, these commands should be replaced with app-specific commands.

Future expected checks:

```text
apps/api: backend tests and type/lint checks
apps/web: frontend tests, typecheck, lint, build
deploy: docker compose -f deploy/docker-compose/api.compose.yml config
```

## Project Boundaries

Platform code should provide generic capabilities:

- upload
- parsing
- scenario routing
- parser-profile routing
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

`scenario_id` is the user-facing learning scene. It should resolve content-pack, prompt-profile, RAG-profile, and domain-rule choices. Do not hardcode new subject behavior into the medicine pack when it belongs in a scenario or future domain pack.

`parser_profile_id` is the user-facing parsing experience. It should resolve parser backend and visibility/admin rules. Do not couple a subject scenario to a parser profile.

Current backend module ownership:

```text
apps/api/jstudy_api       FastAPI app and HTTP contract
packages/core/jstudy_core Pipeline orchestration, job lifecycle and JSON persistence, provider calls, citations, runtime settings
packages/core/jstudy_core/admin_settings.py JSON-backed operator settings, content-pack config, mnemonic JSON rendering
packages/core/jstudy_core/citations.py Evidence item and citation-link contracts
packages/core/jstudy_core/providers.py External model-provider HTTP calls
packages/core/jstudy_core/storage.py Local output path contracts and JSON file helpers
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
Do not add automatic PDF difficulty scoring until there is evidence it is reliable. The current product choice is explicit user/admin selection: `fast` uses PyMuPDF; `quality` is reserved for MinerU and hidden until configured.

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
- `JSTUDY_ADMIN_TOKEN` should be set before exposing `/admin/settings`
- `JSTUDY_SETTINGS_DIR` should point at a mounted persistent settings directory in containerized deployment
- `JSTUDY_JOBS_DIR`, `JSTUDY_SOUL_PATH`, and `JSTUDY_MNEMONICS_PATH` should point at mounted deployment paths when containerized
- `JSTUDY_MAX_PDF_BYTES` should be set explicitly for server deployment
- `JSTUDY_JOB_RETENTION_HOURS` should be nonzero for public testing; use `72` or `168` unless there is a specific reason to keep outputs longer
- persistent files mounted under a data volume
- domain routes frontend at `/` and backend at `/api/...`
- reverse proxy health checks should call `/api/health`
- deployment verification should call `/api/readiness` after secrets and mounted files are configured
- deployment verification can call `/api/readiness?probe_provider=true` to check live SiliconFlow chat and embedding connectivity

Initial deployment can be single-server. Add Redis, Postgres, object storage, or workers when needed by real usage.
Local upload storage is acceptable for the pilot because PDF previews and citation jumps need the source file. For formal user history or course libraries, move uploads and generated artifacts to Tencent COS or another object store instead of growing local disk indefinitely.

## Documentation Standards

Documentation should distinguish:

- current state
- target state
- decisions already made
- open questions
- future roadmap

Do not write docs that imply a refactor has already happened when it has not.

Archive historical MVP notes under `docs/archive/` instead of leaving them in the repository root.
