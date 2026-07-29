# Development Standards

## Scope Discipline

Make small changes that directly serve the current goal. Do not refactor adjacent code just because it looks imperfect. If unrelated problems are noticed, document them or add them to the roadmap instead of mixing them into the current change.

## Product Direction

J-Study should be more vertical than DeepTutor. Use DeepTutor as a reference for reusable framework ideas such as RAG flow, model configuration, and operational patterns, but do not copy its broad general-purpose positioning into J-Study.

The core service must run before the vertical libraries are complete. Keep backend, frontend, deployment, auth, parser routing, scenario routing, and storage boundaries moving toward a working pilot. Treat `soul` profiles and the knowledge snippet library as curated product assets that will be improved one subject at a time.

When a change touches subject behavior, first ask whether it belongs in:

- platform code: routing, parsing, retrieval, jobs, API contracts, deployment
- a soul profile: output philosophy, learning style, subject-specific generation rules
- the knowledge snippet library: reviewed reusable explanations, memory aids, comparisons, pitfalls, or wording patterns
- domain code: planners, filters, graders, question-generation logic that cannot stay as data

Do not hardcode vertical knowledge into generic platform code. Do not block service delivery on fully populated subject libraries.

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

## Windows Encoding

Use a UTF-8 PowerShell session before local development commands, especially when reading or writing Chinese paths, Markdown, JSON, or generated reports:

```powershell
. .\scripts\Enter-JStudyDev.ps1
```

This sets the current console and Python subprocess I/O to UTF-8 and provides two helper functions:

```powershell
Get-Utf8Text -LiteralPath "docs\product\vision.md"
Set-Utf8NoBomText -LiteralPath "tmp\example.md" -Value "# 标题`n"
```

Do not treat mojibake in the terminal as proof that a file is corrupted. Re-check with explicit UTF-8 reads, JSON parsing, tests, or API responses before editing content.

When a command involves Chinese paths, prefer `-LiteralPath` and avoid fragile inline quoting. For scripts that pass paths into Python or another shell, put the path in an environment variable first instead of embedding it in a complex one-liner.

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
- knowledge snippets
- terminology
- quality checks
- question-generation policy

Medicine is the first domain pack, not the product boundary.

`scenario_id` is the user-facing learning scene. It should resolve content-pack, prompt-profile, soul-profile, RAG-profile, and domain-rule choices. Do not hardcode new subject behavior into the medicine pack when it belongs in a scenario or future domain pack.

Parser selection is not a user-facing product choice. The platform uses MinerU
for content extraction, while admins control provider credentials and runtime
limits. Do not couple a subject scenario to parser infrastructure.

Current backend module ownership:

```text
apps/api/jstudy_api       FastAPI app and HTTP contract
packages/core/jstudy_core Pipeline orchestration, job lifecycle and JSON persistence, provider calls, citations, runtime settings
packages/core/jstudy_core/admin_settings.py JSON-backed operator settings, content-pack config, knowledge-snippet JSON rendering
packages/core/jstudy_core/citations.py Evidence item and citation-link contracts
packages/core/jstudy_core/providers.py External model-provider HTTP calls
packages/core/jstudy_core/storage.py Local output path contracts and JSON file helpers
packages/parsers          Document parsing implementations
packages/retrieval        Chunking and retrieval logic
packages/domains          Subject-specific behavior
```

## Parser Standards

All product text and structure extraction uses MinerU and must pass through the
versioned normalized document contract before retrieval. The contract keeps
stable `source_id`, one-based source pages, ordered blocks, parser metadata, and
warnings.

PyMuPDF is an internal utility only:

- PDF validation
- SHA256 and metadata
- page count
- source-preview PNG rendering
- MinerU page-reference validation

Do not:

- expose parser selection to users
- use PyMuPDF-extracted text as a silent MinerU fallback
- pass raw MinerU dictionaries into retrieval or generation
- use filenames as source identity
- build automatic PDF difficulty scoring

Follow `docs/architecture/refactor-blueprint.md` for the migration and deletion
gates.

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
- nonempty provider/model/MinerU/content/upload/retention environment variables are explicit deployment overrides; empty values fall back to shared `data/settings`
- admin-managed settings are reloaded for each new API submission and worker claim; an active claim keeps its settings snapshot
- `JSTUDY_ADMIN_TOKEN` should be set before exposing `/admin/settings`
- `JSTUDY_SETTINGS_DIR` should point at a mounted persistent settings directory in containerized deployment
- `JSTUDY_JOBS_DIR` should point at a mounted deployment path when containerized
- `JSTUDY_MNEMONICS_PATH` is a compatibility name for the prompt-rendered knowledge snippet file until the runtime contract is renamed
- leave admin-managed Compose values such as model selection and `JSTUDY_MAX_PDF_BYTES` empty unless an immutable deployment override is intended
- `JSTUDY_JOB_RETENTION_HOURS` must have a nonzero public-pilot source; `.env.example` uses `72`
- persistent files mounted under a data volume
- domain routes frontend at `/` and backend at `/api/...`
- reverse proxy health checks should call `/api/health`
- deployment verification should call `/api/readiness` after secrets and mounted files are configured
- deployment verification can call `/api/readiness?probe_provider=true` to check live SiliconFlow chat and embedding connectivity

Initial deployment can be single-server. Add Redis, Postgres, object storage, or workers when needed by real usage.
Local upload storage is acceptable for the pilot because PDF previews and citation jumps need the source file. For formal user history or course libraries, move uploads and generated artifacts to Tencent COS or another object store instead of growing local disk indefinitely.

## Knowledge Snippet Feedback Standards

The user feedback loop should be conservative:

- liked user selections are raw feedback, not approved product knowledge
- semantic similarity is for deduplication and clustering, not automatic adoption
- administrator review is required before a candidate becomes an approved snippet
- approved snippets can guide expression, structure, and memory aids, but factual claims still require current-upload evidence
- automatic replacement is out of scope until the evidence-matching rules are precise enough to prevent ambiguous reuse

## Documentation Standards

Documentation should distinguish:

- current state
- target state
- decisions already made
- open questions
- future roadmap

Do not write docs that imply a refactor has already happened when it has not.

Archive historical MVP notes under `docs/archive/` instead of leaving them in the repository root.
