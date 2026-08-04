# Task Card: Refactor Checkpoint and MinerU Document Foundation

## Supervisor Thread

`019ed023-8e41-7ad0-8117-6246b8ffa0bb`

## Goal

Create a recoverable Git checkpoint for the verified 0002-0004 MVP, then build
and test the normalized MinerU Precision Extract document layer without deleting
or switching the existing generation pipeline yet.

## Context

The approved refactor direction is:

- all product text/structure extraction will use MinerU
- users will not choose a parser
- PyMuPDF remains for PDF validation, metadata, and page rendering only
- the first production deployment uses the MinerU Precision Extract cloud API
- J-Study runs on Tencent Cloud
- the spare computer is a future optional MinerU worker, not a production
  dependency
- current databases, uploads, and generated jobs are disposable test data

Read before editing:

- `docs/architecture/refactor-blueprint.md`
- `docs/architecture/overview.md`
- `docs/frontend/clinical-workbench-spec.md`
- `multi-agent/jstudy-product-build/shared/project_context.md`
- `multi-agent/jstudy-product-build/shared/repo_rules.md`
- `multi-agent/jstudy-product-build/coordination/output_contract.md`

The working tree contains accepted but uncommitted work from tasks 0002-0004.
`apps/web` and `multi-agent` are currently untracked in the known baseline. Do
not start structural edits until that state is inventoried, tested, and
checkpointed.

## Baseline Assumption

Expected branch:

```text
feature/backend-frontend-mvp
```

The Code Agent must record the actual branch and `HEAD` SHA. If the branch,
working tree, or test baseline differs materially from this task card, stop
before committing and report the difference.

## Allowed Scope

Checkpoint scope:

- `README.md`
- `apps/api/**`
- `apps/web/**`
- `docs/**`
- `packages/**`
- `tests/**`
- `multi-agent/jstudy-product-build/**`
- root compatibility shims already tracked by Git

MinerU foundation implementation scope:

- `packages/core/jstudy_core/documents/**`
- `packages/parsers/mineru_parser.py` only as a compatibility adapter
- `packages/parsers/pymupdf_parser.py` only to delegate reusable PDF utility
  behavior without changing current extraction behavior
- `packages/core/jstudy_core/admin_settings.py` for MinerU runtime defaults
- `packages/core/jstudy_core/settings.py` for typed MinerU runtime resolution
- `tests/test_document_models.py`
- `tests/test_mineru_client.py`
- `tests/test_mineru_normalizer.py`
- `tests/test_pdf_utility.py`
- focused existing tests required by settings compatibility
- `requirements.txt` only if the implementation cannot use the existing
  `httpx`, standard library, and Pydantic/FastAPI dependencies
- `multi-agent/jstudy-product-build/reports/0005-*.md`

## Explicitly Excluded

Do not stage, commit, delete, or modify:

- `data/**`
- secrets, `.env` files, API tokens, uploaded PDFs, or generated user artifacts
- unrelated root `frontend/**`
- `game/**`
- `images/**`
- root `outline_mode/**`
- `.superpowers/brainstorm/**`
- Cloudflare or Tencent production configuration
- candidate branches

Do not:

- switch `run_mvp()` or `run_course_outline()` to MinerU in this task
- remove PyMuPDF text extraction yet
- remove parser-profile routing yet
- change frontend request or response contracts
- change public FastAPI routes
- migrate jobs to PostgreSQL
- add a separate worker or queue
- rewrite generation, retrieval, citations, Soul Profiles, or Knowledge Snippets
- make a live MinerU call in automated tests
- add a generic plugin/provider framework

## Required Phase 0: Inventory Before Commit

Create:

- `multi-agent/jstudy-product-build/reports/0005-baseline-inventory.md`

The report must contain:

1. current branch and `HEAD` SHA
2. tracked modifications
3. untracked product paths included in the checkpoint
4. excluded untracked paths
5. secret/runtime-data scan result
6. backend test result
7. frontend lint/typecheck/unit/build/E2E result
8. the exact files proposed for the checkpoint commit

Run:

```powershell
. "$env:USERPROFILE\.codex\scripts\Enter-CodexUtf8.ps1"
git status --short --branch
git rev-parse HEAD
git diff --check
python -m unittest discover -s tests -v
```

From `apps/web` run:

```powershell
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
```

If a test fails, do not hide it by changing expected behavior. Record the
failure and stop unless the failure is solely an unavailable external
dependency already documented by task 0004.

Before staging, inspect candidate filenames and content for:

```text
API keys
Authorization headers with real values
cookies
.env files
database files
jobs.json
uploads
generated PDFs
generated outputs
```

Do not print secret values into the report or terminal transcript.

## Required Phase 1: Checkpoint Commit

Stage only the accepted product files listed in the Phase 0 report. Re-run:

```powershell
git diff --cached --name-only
git diff --cached --check
```

The staged list must not contain any explicitly excluded path.

Create one Chinese checkpoint commit:

```text
chore: 固化前后端 MVP 重构基线
```

Record the resulting commit SHA in:

- `multi-agent/jstudy-product-build/reports/0005-baseline-inventory.md`

Do not push, merge, rebase, tag, reset, or clean the worktree.

If committing the accepted baseline would mix unknown user work with tasks
0002-0004, stop and request Supervisor review instead of guessing.

## Required Phase 2: Normalized Document Models

Create:

```text
packages/core/jstudy_core/documents/__init__.py
packages/core/jstudy_core/documents/models.py
```

Use Pydantic models or frozen dataclasses with explicit validation. The public
contract must include:

```python
class ParsedBlock:
    block_id: str
    kind: str
    text: str
    markdown: str
    bbox: tuple[float, float, float, float] | None
    asset_path: str | None
    metadata: dict[str, Any]


class ParsedPage:
    page_number: int
    text: str
    markdown: str
    blocks: list[ParsedBlock]


class ParsedDocument:
    contract_version: str
    source_id: str
    source_file: str
    source_sha256: str
    parser_name: str
    parser_version: str
    parser_model: str
    page_count: int
    pages: list[ParsedPage]
    warnings: list[str]
    provider_trace_id: str
```

Required invariants:

- `contract_version` starts at `1`
- `source_id` is supplied by J-Study and is not inferred from a filename
- `page_number` is one-based and positive
- page numbers are unique and ascending
- `page_count` equals the source PDF page count, even when a page has no text
- each block id is stable within the normalized artifact
- bbox is absent or contains four finite ordered coordinates
- missing optional MinerU fields normalize safely
- an empty document fails with a typed normalization error

Write failing tests first in `tests/test_document_models.py`, run them, then
implement the minimum model code.

## Required Phase 3: PyMuPDF Utility Boundary

Create:

```text
packages/core/jstudy_core/documents/pdf_utility.py
tests/test_pdf_utility.py
```

Move or wrap only these responsibilities:

- PDF magic/header validation
- opening and corruption validation
- page count
- page metadata
- page PNG rendering
- SHA256 calculation

The utility must not expose extracted page text as its new product contract.

Keep existing functions working through compatibility delegation so the public
API and current tests do not change in this task.

Required tests:

- rejects a non-PDF header
- rejects a corrupt PDF
- returns deterministic SHA256
- returns correct page count
- rejects page zero and out-of-range pages
- renders a valid PNG

## Required Phase 4: MinerU Precision Extract Transport

Create:

```text
packages/core/jstudy_core/documents/mineru_client.py
tests/test_mineru_client.py
```

Use the existing `httpx` dependency and an injected `httpx.Client` or
`httpx.MockTransport`. Do not make network calls in the test suite.

Implement the official Precision Extract local-file flow:

```text
POST /api/v4/file-urls/batch
PUT each file to its returned signed URL
GET /api/v4/extract-results/batch/{batch_id}
download full_zip_url after state=done
```

Defaults:

```text
base_url=https://mineru.net
model_version=vlm
language=ch
enable_table=true
enable_formula=true
is_ocr=false
poll_interval_seconds=2
deadline_seconds=900
max_result_bytes=268435456
```

Use the persisted J-Study `source_id` as MinerU `data_id`.

Define typed transport results for:

- batch submission
- per-source provider state
- completed ZIP artifact
- provider trace id

Map provider states:

```text
waiting-file | pending | running | converting -> nonterminal
done -> completed
failed -> typed MinerUProviderError
unknown -> typed MinerUProtocolError
```

Required behavior:

- Bearer token is attached only to `mineru.net` API calls
- signed upload requests do not receive the Bearer token
- response `code` must equal `0`
- response fields are validated before use
- file URL count must match submitted file count
- polling stops at the configured deadline
- HTTP connect/read/write timeouts are explicit
- transient HTTP 429/5xx polling failures use bounded retries
- authentication and invalid-input failures are not retried indefinitely
- loggable errors never contain the token or full signed URL query
- download hosts are restricted to HTTPS and an explicit allowlist
- downloads stop above `max_result_bytes`

Required mocked tests:

- successful two-file submission, upload, polling, and ZIP download
- file URL count mismatch
- provider error code
- failed extraction with safe error
- timeout
- bounded retry on 429/5xx
- no Bearer header on signed upload
- rejected non-HTTPS or unapproved result URL
- oversized result rejection
- token redaction

Do not implement callbacks in this phase.

## Required Phase 5: Safe MinerU Output Normalization

Create:

```text
packages/core/jstudy_core/documents/mineru_normalizer.py
tests/test_mineru_normalizer.py
```

Normalize the stable MinerU `content_list.json` format. Do not make
`content_list_v2.json` the J-Study contract because MinerU currently labels it
developmental.

ZIP handling requirements:

- reject absolute paths
- reject `..` traversal
- reject symlinks
- cap member count
- cap total uncompressed bytes
- cap compression ratio
- extract only into the job-owned target directory
- require exactly one usable `*_content_list.json`
- preserve `full.md` and original ZIP as private artifacts when present
- reject malformed JSON

Normalization rules:

- convert MinerU `page_idx` from zero-based to one-based exactly once
- group content in reading order by page
- map text/title/list/table/equation/image/code to J-Study block kinds
- retain table Markdown or HTML as block Markdown
- retain formula text as block Markdown
- retain bbox and image-relative paths when present
- exclude headers, footers, and page numbers from retrieval text but retain a
  warning/count in metadata
- include empty source pages so citation page numbering never shifts
- compare normalized page indexes against the PyMuPDF page count
- reject content referencing pages outside the source PDF
- generate deterministic block ids from source id, page, and block order

The normalizer must return `ParsedDocument`, never a loose dictionary.

Test fixtures must be generated inside temporary directories. Do not commit real
courseware or MinerU output containing user material.

Required tests:

- mixed two-page content normalization
- zero-based to one-based conversion
- empty page preservation
- table and formula preservation
- header/footer exclusion from retrieval text
- malformed/out-of-range page rejection
- missing content list rejection
- traversal ZIP rejection
- decompression-limit rejection
- deterministic block ids

## Required Phase 6: Runtime Configuration

Update MinerU runtime configuration without changing public parser routing yet.

Required normalized settings:

```json
{
  "parser": {
    "provider": "mineru",
    "mineru": {
      "api_base_url": "https://mineru.net",
      "api_token": "",
      "model_version": "vlm",
      "language": "ch",
      "enable_table": true,
      "enable_formula": true,
      "is_ocr": false,
      "poll_interval_seconds": 2,
      "deadline_seconds": 900,
      "max_result_bytes": 268435456
    }
  }
}
```

Rules:

- environment variables override persisted admin settings
- token values are never returned by public endpoints
- existing parser-profile settings remain readable during this compatibility
  phase but are marked deprecated in code comments/docs
- readiness can report `mineru_configured=false` without breaking current fake
  runner tests
- no real token is added to a repository file

Suggested environment names:

```text
MINERU_API_BASE_URL
MINERU_API_TOKEN
MINERU_MODEL_VERSION
MINERU_LANGUAGE
MINERU_POLL_INTERVAL_SECONDS
MINERU_DEADLINE_SECONDS
MINERU_MAX_RESULT_BYTES
```

## Required Phase 7: Compatibility Adapter

Update `packages/parsers/mineru_parser.py` so it delegates to the new document
service only when a configured client is supplied. Do not silently construct a
live client from global state inside tests.

The old function may temporarily return the legacy:

```python
list[{"page": int, "text": str}]
```

by adapting `ParsedDocument.pages`. Mark this compatibility shape for removal in
the next pipeline-switch task.

Do not change the default parser backend or existing public API behavior in this
task.

## Verification

Focused checks:

```powershell
python -m unittest tests.test_document_models tests.test_pdf_utility tests.test_mineru_client tests.test_mineru_normalizer -v
python -m unittest tests.test_admin_settings tests.test_settings tests.test_parser_profile_router -v
```

Full backend:

```powershell
python -m unittest discover -s tests -v
python -m compileall apps packages
```

Frontend regression from `apps/web`:

```powershell
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
```

Repository:

```powershell
git diff --check
git status --short
```

No live MinerU request is required for `PASS`. If `MINERU_API_TOKEN` happens to
exist locally, do not use it without a separate explicit Supervisor instruction.

## Commit Discipline

After the baseline checkpoint, use Chinese commit messages. Suggested commits:

```text
feat: 建立统一文档解析契约
feat: 接入 MinerU 精准解析传输层
feat: 增加 MinerU 输出安全归一化
chore: 补充 MinerU 运行配置
```

Do not push or merge.

## Stop and Report If

Stop instead of guessing if:

- baseline tests do not match the previously reported 120 backend tests and 12
  E2E tests
- accepted 0002-0004 files cannot be separated from unrelated user work
- the official MinerU v4 response differs from the documented batch contract
- a secure ZIP/result implementation would require a new dependency
- current PyMuPDF functions cannot be delegated without changing API behavior
- a test requires a real API token
- any secret or real user artifact is found in the proposed checkpoint

## Report-Back

Report using:

- `multi-agent/jstudy-product-build/coordination/output_contract.md`

The report must additionally include:

- pre-refactor and checkpoint SHAs
- exact checkpoint file list or a path to the inventory containing it
- MinerU API version and official documentation date reviewed
- normalized contract version
- security limits selected for ZIP/download handling
- proof that automated tests made no live MinerU request
- deferred deletions and the task that should own them

Request one Supervisor verdict:

`PASS`, `PASS_WITH_LIMITATIONS`, `REVISE`, or `REJECT`.
