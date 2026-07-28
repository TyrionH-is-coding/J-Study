# MinerU Document Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the verified J-Study MVP as a Git checkpoint and add a tested, provider-isolated MinerU Precision Extract document layer.

**Architecture:** The new document package validates MinerU transport and ZIP output, normalizes provider data into a stable J-Study contract, and keeps PyMuPDF limited to PDF utilities. The existing generation pipeline remains active until the next migration phase, so every commit keeps the application runnable.

**Tech Stack:** Python 3.10+, FastAPI/Pydantic, httpx, PyMuPDF, unittest, Next.js verification.

---

## File Map

Create:

```text
packages/core/jstudy_core/documents/__init__.py
packages/core/jstudy_core/documents/models.py
packages/core/jstudy_core/documents/pdf_utility.py
packages/core/jstudy_core/documents/mineru_client.py
packages/core/jstudy_core/documents/mineru_normalizer.py
tests/test_document_models.py
tests/test_pdf_utility.py
tests/test_mineru_client.py
tests/test_mineru_normalizer.py
multi-agent/jstudy-product-build/reports/0005-baseline-inventory.md
multi-agent/jstudy-product-build/reports/0005-mineru-foundation-report.md
```

Modify:

```text
packages/core/jstudy_core/admin_settings.py
packages/core/jstudy_core/settings.py
packages/parsers/mineru_parser.py
packages/parsers/pymupdf_parser.py
tests/test_admin_settings.py
tests/test_settings.py
```

Do not modify public routes, frontend API contracts, generation behavior, job
persistence, or deployment configuration in this plan.

### Task 1: Verify and checkpoint the current MVP

**Files:**

- Create: `multi-agent/jstudy-product-build/reports/0005-baseline-inventory.md`
- Stage only paths authorized by task card `0005`

- [ ] **Step 1: Capture repository state**

Run:

```powershell
. "$env:USERPROFILE\.codex\scripts\Enter-CodexUtf8.ps1"
git status --short --branch
git rev-parse HEAD
git diff --check
```

Expected: branch and SHA are recorded; `git diff --check` reports no whitespace
error.

- [ ] **Step 2: Run the backend baseline**

Run:

```powershell
python -m unittest discover -s tests -v
```

Expected: all existing backend tests pass. Record the exact count.

- [ ] **Step 3: Run the frontend baseline**

Run from `apps/web`:

```powershell
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
```

Expected: all five commands pass. Record unit and E2E counts.

- [ ] **Step 4: Write the inventory**

The report must use this structure:

```markdown
# 0005 Baseline Inventory

- Branch:
- Pre-checkpoint SHA:
- Backend verification:
- Frontend verification:
- Included tracked changes:
- Included untracked product files:
- Excluded paths:
- Secret/runtime-data scan:
- Proposed staged paths:
- Checkpoint SHA:
```

- [ ] **Step 5: Stage and inspect**

Stage only the file list written in the inventory, then run:

```powershell
git diff --cached --name-only
git diff --cached --check
```

Expected: no `data`, `.env`, PDF, database, `frontend`, `game`, `images`,
`outline_mode`, or brainstorm artifact is staged.

- [ ] **Step 6: Create the checkpoint**

Run:

```powershell
git commit -m "chore: 固化前后端 MVP 重构基线"
git rev-parse HEAD
```

Expected: commit succeeds and the resulting SHA is written back to the
inventory.

### Task 2: Add the normalized document contract

**Files:**

- Create: `packages/core/jstudy_core/documents/__init__.py`
- Create: `packages/core/jstudy_core/documents/models.py`
- Test: `tests/test_document_models.py`

- [ ] **Step 1: Write contract tests**

Add tests equivalent to:

```python
import unittest

from packages.core.jstudy_core.documents.models import (
    DocumentContractError,
    ParsedBlock,
    ParsedDocument,
    ParsedPage,
)


class DocumentModelsTest(unittest.TestCase):
    def test_accepts_one_based_ordered_pages(self):
        page = ParsedPage(
            page_number=1,
            text="正文",
            markdown="正文",
            blocks=[
                ParsedBlock(
                    block_id="S001-P001-B001",
                    kind="text",
                    text="正文",
                    markdown="正文",
                )
            ],
        )
        document = ParsedDocument(
            source_id="S001",
            source_file="lecture.pdf",
            source_sha256="a" * 64,
            parser_version="3",
            parser_model="vlm",
            page_count=1,
            pages=[page],
        )
        self.assertEqual(document.pages[0].page_number, 1)

    def test_rejects_zero_based_page_number(self):
        with self.assertRaises(DocumentContractError):
            ParsedPage(page_number=0, text="", markdown="", blocks=[])

    def test_rejects_duplicate_page_numbers(self):
        page = ParsedPage(page_number=1, text="", markdown="", blocks=[])
        with self.assertRaises(DocumentContractError):
            ParsedDocument(
                source_id="S001",
                source_file="lecture.pdf",
                source_sha256="a" * 64,
                parser_version="3",
                parser_model="vlm",
                page_count=2,
                pages=[page, page],
            )
```

- [ ] **Step 2: Run the tests and confirm red**

Run:

```powershell
python -m unittest tests.test_document_models -v
```

Expected: import failure because the document package does not exist.

- [ ] **Step 3: Implement the contract**

Implement:

```python
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


class DocumentContractError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedBlock:
    block_id: str
    kind: str
    text: str = ""
    markdown: str = ""
    bbox: tuple[float, float, float, float] | None = None
    asset_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.block_id.strip():
            raise DocumentContractError("block_id is required")
        if self.bbox is not None:
            if len(self.bbox) != 4 or not all(math.isfinite(value) for value in self.bbox):
                raise DocumentContractError("bbox must contain four finite values")
            x0, y0, x1, y1 = self.bbox
            if x0 > x1 or y0 > y1:
                raise DocumentContractError("bbox coordinates are not ordered")


@dataclass(frozen=True)
class ParsedPage:
    page_number: int
    text: str
    markdown: str
    blocks: list[ParsedBlock]

    def __post_init__(self) -> None:
        if self.page_number < 1:
            raise DocumentContractError("page_number must be one-based")


@dataclass(frozen=True)
class ParsedDocument:
    source_id: str
    source_file: str
    source_sha256: str
    parser_version: str
    parser_model: str
    page_count: int
    pages: list[ParsedPage]
    contract_version: str = "1"
    parser_name: str = "mineru"
    warnings: list[str] = field(default_factory=list)
    provider_trace_id: str = ""

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise DocumentContractError("source_id is required")
        if self.page_count < 1:
            raise DocumentContractError("page_count must be positive")
        numbers = [page.page_number for page in self.pages]
        if numbers != list(range(1, self.page_count + 1)):
            raise DocumentContractError("pages must cover the source in ascending order")
```

Export the models from `documents/__init__.py`.

- [ ] **Step 4: Run the contract tests**

Run:

```powershell
python -m unittest tests.test_document_models -v
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add packages/core/jstudy_core/documents tests/test_document_models.py
git commit -m "feat: 建立统一文档解析契约"
```

### Task 3: Extract the PyMuPDF utility boundary

**Files:**

- Create: `packages/core/jstudy_core/documents/pdf_utility.py`
- Modify: `packages/parsers/pymupdf_parser.py`
- Test: `tests/test_pdf_utility.py`

- [ ] **Step 1: Write PDF utility tests**

Cover:

```python
validate_pdf(path)
pdf_sha256(path)
pdf_page_count(path)
render_pdf_page_png(path, page_number=1)
```

Use a temporary valid two-page PDF and assert:

```python
self.assertEqual(pdf_page_count(path), 2)
self.assertEqual(pdf_sha256(path), hashlib.sha256(path.read_bytes()).hexdigest())
self.assertTrue(render_pdf_page_png(path, 1).startswith(b"\x89PNG"))
```

Also assert that non-PDF bytes, corrupt PDF bytes, page `0`, and page `3`
raise `PdfValidationError`.

- [ ] **Step 2: Run the tests and confirm red**

Run:

```powershell
python -m unittest tests.test_pdf_utility -v
```

Expected: import failure.

- [ ] **Step 3: Implement the utility**

Use `fitz.open()` in context managers. `validate_pdf()` must check `%PDF-`
before opening. `render_pdf_page_png()` accepts one-based page numbers and
returns `page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False).tobytes("png")`.

Keep `extract_pdf_pages()` in `packages/parsers/pymupdf_parser.py` working for
the compatibility phase. It may import shared open/validation helpers but must
not become part of the new normalized parser contract.

- [ ] **Step 4: Run focused and regression tests**

Run:

```powershell
python -m unittest tests.test_pdf_utility tests.test_web_mvp -v
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add packages/core/jstudy_core/documents/pdf_utility.py packages/parsers/pymupdf_parser.py tests/test_pdf_utility.py
git commit -m "refactor: 分离 PDF 基础工具"
```

### Task 4: Implement the MinerU Precision Extract client

**Files:**

- Create: `packages/core/jstudy_core/documents/mineru_client.py`
- Test: `tests/test_mineru_client.py`

- [ ] **Step 1: Write mocked transport tests**

Use `httpx.MockTransport` and assert this request sequence for two files:

```text
POST https://mineru.net/api/v4/file-urls/batch
PUT https://approved-upload-host/... for S001
PUT https://approved-upload-host/... for S002
GET https://mineru.net/api/v4/extract-results/batch/{batch_id}
GET each approved full_zip_url
```

Test successful completion plus:

```text
provider code != 0
URL count mismatch
failed extraction
deadline exceeded
429 followed by success
unapproved download host
oversized ZIP
Bearer token absent from PUT
```

- [ ] **Step 2: Run the tests and confirm red**

Run:

```powershell
python -m unittest tests.test_mineru_client -v
```

Expected: import failure.

- [ ] **Step 3: Implement typed client records**

Implement frozen records:

```python
@dataclass(frozen=True)
class MinerUInput:
    source_id: str
    path: Path


@dataclass(frozen=True)
class MinerUArtifact:
    source_id: str
    provider_file_name: str
    zip_bytes: bytes
    trace_id: str


@dataclass(frozen=True)
class MinerUClientConfig:
    api_base_url: str = "https://mineru.net"
    model_version: str = "vlm"
    language: str = "ch"
    enable_table: bool = True
    enable_formula: bool = True
    is_ocr: bool = False
    poll_interval_seconds: float = 2.0
    deadline_seconds: float = 900.0
    max_result_bytes: int = 268435456
```

Define:

```python
class MinerUError(RuntimeError):
    code = "mineru_error"


class MinerUProviderError(MinerUError):
    code = "mineru_provider_error"


class MinerUProtocolError(MinerUError):
    code = "mineru_protocol_error"


class MinerUTimeoutError(MinerUError):
    code = "mineru_timeout"
```

Implement:

```python
class MinerUPrecisionClient:
    def __init__(
        self,
        token: str,
        config: MinerUClientConfig,
        client: httpx.Client,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None: ...

    def extract(self, files: list[MinerUInput]) -> list[MinerUArtifact]: ...
```

The method must submit signed-upload requests, upload raw files without the
Bearer header, poll with a bounded deadline, validate states, and stream ZIP
downloads while counting bytes.

- [ ] **Step 4: Run client tests**

Run:

```powershell
python -m unittest tests.test_mineru_client -v
```

Expected: pass without network access.

- [ ] **Step 5: Commit**

Run:

```powershell
git add packages/core/jstudy_core/documents/mineru_client.py tests/test_mineru_client.py
git commit -m "feat: 接入 MinerU 精准解析传输层"
```

### Task 5: Normalize MinerU ZIP output safely

**Files:**

- Create: `packages/core/jstudy_core/documents/mineru_normalizer.py`
- Test: `tests/test_mineru_normalizer.py`

- [ ] **Step 1: Build in-memory ZIP fixtures**

Tests must build ZIP bytes containing:

```text
full.md
lecture_content_list.json
images/table.png
```

The content list must include text, title, table, equation, header, and content
on zero-based pages `0` and `1`.

- [ ] **Step 2: Write normalization and ZIP-security tests**

Assert:

```python
document.page_count == 2
document.pages[0].page_number == 1
document.pages[1].page_number == 2
document.pages[0].blocks[0].block_id == "S001-P001-B001"
"header text" not in document.pages[0].text
```

Also test traversal member names, excessive expansion, malformed JSON, missing
content list, and `page_idx` outside the source page count.

- [ ] **Step 3: Run tests and confirm red**

Run:

```powershell
python -m unittest tests.test_mineru_normalizer -v
```

Expected: import failure.

- [ ] **Step 4: Implement the normalizer**

Implement:

```python
@dataclass(frozen=True)
class MinerUNormalizerLimits:
    max_members: int = 2000
    max_uncompressed_bytes: int = 536870912
    max_compression_ratio: float = 100.0


def normalize_mineru_zip(
    *,
    zip_bytes: bytes,
    source_id: str,
    source_file: str,
    source_sha256: str,
    source_page_count: int,
    parser_version: str,
    parser_model: str,
    provider_trace_id: str,
    artifact_dir: Path,
    limits: MinerUNormalizerLimits = MinerUNormalizerLimits(),
) -> ParsedDocument:
    ...
```

Use `PurePosixPath` to reject absolute and parent paths before extraction.
Reject symlink mode bits. Sum `ZipInfo.file_size` before extracting. Accept
exactly one legacy `*_content_list.json`. Convert `page_idx + 1`, create empty
pages for missing indexes, and produce deterministic block ids.

- [ ] **Step 5: Run normalizer tests**

Run:

```powershell
python -m unittest tests.test_mineru_normalizer -v
```

Expected: pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add packages/core/jstudy_core/documents/mineru_normalizer.py tests/test_mineru_normalizer.py
git commit -m "feat: 增加 MinerU 输出安全归一化"
```

### Task 6: Add runtime settings and compatibility adapter

**Files:**

- Modify: `packages/core/jstudy_core/admin_settings.py`
- Modify: `packages/core/jstudy_core/settings.py`
- Modify: `packages/parsers/mineru_parser.py`
- Test: `tests/test_admin_settings.py`
- Test: `tests/test_settings.py`

- [ ] **Step 1: Write settings tests**

Assert default and environment resolution for:

```text
MINERU_API_BASE_URL
MINERU_API_TOKEN
MINERU_MODEL_VERSION
MINERU_LANGUAGE
MINERU_POLL_INTERVAL_SECONDS
MINERU_DEADLINE_SECONDS
MINERU_MAX_RESULT_BYTES
```

Expected defaults:

```python
self.assertEqual(config.api_base_url, "https://mineru.net")
self.assertEqual(config.model_version, "vlm")
self.assertEqual(config.language, "ch")
self.assertTrue(config.enable_table)
self.assertTrue(config.enable_formula)
self.assertFalse(config.is_ocr)
self.assertEqual(config.deadline_seconds, 900)
```

- [ ] **Step 2: Run settings tests and confirm red**

Run:

```powershell
python -m unittest tests.test_admin_settings tests.test_settings -v
```

Expected: new assertions fail.

- [ ] **Step 3: Implement normalized settings**

Add a typed MinerU settings value to `RuntimeSettings`. Preserve current
parser-profile fields for compatibility, but mark them deprecated in the
settings module. Environment variables take precedence over admin JSON. Never
serialize the effective token into public responses.

- [ ] **Step 4: Implement the compatibility adapter**

Change `packages/parsers/mineru_parser.py` to accept an injected document
parser/client and adapt:

```python
return [
    {"page": page.page_number, "text": page.text}
    for page in parsed_document.pages
    if page.text.strip()
]
```

If no configured client is supplied, raise a typed configuration error without
including secrets.

- [ ] **Step 5: Run compatibility tests**

Run:

```powershell
python -m unittest tests.test_admin_settings tests.test_settings tests.test_parser_profile_router tests.test_mvp_runner -v
```

Expected: pass without a live MinerU request.

- [ ] **Step 6: Commit**

Run:

```powershell
git add packages/core/jstudy_core/admin_settings.py packages/core/jstudy_core/settings.py packages/parsers/mineru_parser.py tests/test_admin_settings.py tests/test_settings.py
git commit -m "chore: 补充 MinerU 运行配置"
```

### Task 7: Full verification and report

**Files:**

- Create: `multi-agent/jstudy-product-build/reports/0005-mineru-foundation-report.md`

- [ ] **Step 1: Run all backend checks**

Run:

```powershell
python -m unittest discover -s tests -v
python -m compileall apps packages
```

Expected: pass.

- [ ] **Step 2: Run all frontend checks**

Run from `apps/web`:

```powershell
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
```

Expected: pass.

- [ ] **Step 3: Prove tests are offline**

Review `tests/test_mineru_client.py` and confirm every HTTP call uses
`httpx.MockTransport`. Run the MinerU tests with an invalid proxy or disabled
network if the environment supports it; otherwise state that the mock transport
is the evidence and do not claim OS-level network isolation.

- [ ] **Step 4: Inspect repository integrity**

Run:

```powershell
git diff --check
git status --short
git log --oneline -6
```

Expected: no whitespace errors, no runtime data or secrets, and Chinese commit
messages for this plan.

- [ ] **Step 5: Write the report**

Use the multi-agent output contract and include:

```text
pre-checkpoint SHA
checkpoint SHA
final SHA
test counts
MinerU API v4 batch flow
document contract version 1
ZIP and download safety limits
deferred pipeline switch
deferred job/database migration
```

Do not push or merge. Request Supervisor review.
