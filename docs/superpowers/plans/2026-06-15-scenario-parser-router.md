# Scenario Parser Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add scenario routing and automatic parser routing so users can choose a learning scene while the backend selects PyMuPDF or MinerU policy automatically.

**Architecture:** Keep routing in small backend modules. `ScenarioRouter` resolves the effective content pack and scenario from admin settings. `ParserRouter` scores PDF complexity and returns a decision object. The FastAPI upload endpoint stores the chosen scenario and parser decision in job metadata, and the pipeline writes that routing metadata into the retrieval trace.

**Tech Stack:** Python, FastAPI, PyMuPDF, unittest, JSON admin settings.

---

## Work Order

1. Extend admin settings schema for scenarios and parser-router policy.
2. Add scenario resolution as a standalone backend module.
3. Add parser complexity scoring and backend decision as a standalone parser module.
4. Store routing metadata on jobs.
5. Pass scenario/parser metadata through API and pipeline into trace output.
6. Add a user-facing scenario selector to the temporary upload UI.
7. Add admin UI fields for default scenario and parser-router mode.
8. Tighten deployment docs around local storage retention.

Do not add a database or require MinerU in this plan.

## File Structure

- Create: `packages/core/jstudy_core/scenario_router.py`
  - Owns scenario validation and default resolution.
- Create: `packages/parsers/router.py`
  - Owns PDF complexity analysis and parser backend choice.
- Create: `packages/parsers/mineru_parser.py`
  - Owns the MinerU adapter boundary and returns a clear runtime error if called before a configured implementation is available.
- Modify: `packages/core/jstudy_core/admin_settings.py`
  - Adds default scenarios and parser-router policy.
- Modify: `packages/core/jstudy_core/settings.py`
  - Exposes scenario catalog and parser-router settings through `RuntimeSettings`.
- Modify: `packages/core/jstudy_core/jobs.py`
  - Persists job metadata for scenario and parser decision.
- Modify: `packages/core/jstudy_core/pipeline.py`
  - Accepts parser backend and routing metadata, then writes them to trace JSON.
- Modify: `apps/api/jstudy_api/app.py`
  - Accepts `scenario_id`, resolves scenario, runs parser routing, and passes metadata to background jobs.
- Modify: `apps/api/jstudy_api/ui.py`
  - Adds a compact scenario selector to the existing upload form.
- Modify: `apps/api/jstudy_api/admin_ui.py`
  - Adds default scenario and parser-router controls.
- Modify: `README.md`, `docs/architecture/overview.md`, `docs/development/standards.md`, `deploy/docker-compose/README.md`
  - Documents routing behavior and production retention settings.
- Tests:
  - `tests/test_admin_settings.py`
  - `tests/test_settings.py`
  - `tests/test_scenario_router.py`
  - `tests/test_parser_router.py`
  - `tests/test_job_store.py`
  - `tests/test_mvp_runner.py`
  - `tests/test_web_mvp.py`

---

### Task 1: Extend Admin Settings Schema

**Files:**
- Modify: `packages/core/jstudy_core/admin_settings.py`
- Test: `tests/test_admin_settings.py`

- [ ] **Step 1: Write failing tests for scenario and parser-router defaults**

Add tests:

```python
def test_content_pack_defaults_include_scenarios(self):
    with TemporaryDirectory() as tmp:
        service = AdminSettingsService(Path(tmp) / "settings")
        payload = service.load_content_pack()

    self.assertEqual(payload["default_scenario_id"], "medicine-default")
    self.assertEqual(payload["active_pack_id"], "medicine-default")
    scenario_ids = {item["id"] for item in payload["scenarios"]}
    self.assertIn("medicine-default", scenario_ids)
    self.assertIn("general-default", scenario_ids)


def test_runtime_defaults_include_parser_router_policy(self):
    with TemporaryDirectory() as tmp:
        service = AdminSettingsService(Path(tmp) / "settings")
        payload = service.load_runtime()

    router = payload["parser_router"]
    self.assertEqual(router["mode"], "auto")
    self.assertEqual(router["default_backend"], "pymupdf")
    self.assertFalse(router["mineru_enabled"])
    self.assertTrue(router["fallback_to_pymupdf"])
    self.assertGreater(router["thresholds"]["complexity_score_mineru_min"], 0)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m unittest tests.test_admin_settings.AdminSettingsTest.test_content_pack_defaults_include_scenarios tests.test_admin_settings.AdminSettingsTest.test_runtime_defaults_include_parser_router_policy -v
```

Expected: fail because `default_scenario_id`, `scenarios`, and `parser_router` do not exist yet.

- [ ] **Step 3: Add minimal admin settings defaults and normalization**

Update `_runtime_default()` to include:

```python
"parser_router": {
    "mode": "auto",
    "default_backend": "pymupdf",
    "mineru_enabled": False,
    "fallback_to_pymupdf": True,
    "thresholds": {
        "page_count_mineru_min": 80,
        "text_density_min": 120,
        "empty_page_ratio_max": 0.25,
        "image_object_ratio_max": 3,
        "complexity_score_mineru_min": 60,
    },
},
```

Update `_content_pack_default()` to include:

```python
"default_scenario_id": "medicine-default",
"scenarios": [
    {
        "id": "medicine-default",
        "display_name": "Medicine",
        "subject": "medicine",
        "enabled": True,
        "content_pack_id": "medicine-default",
        "prompt_profile": "medicine-default",
        "rag_profile": "default",
        "domain_rules": ["medicine"],
    },
    {
        "id": "general-default",
        "display_name": "General",
        "subject": "general",
        "enabled": True,
        "content_pack_id": "medicine-default",
        "prompt_profile": "general-default",
        "rag_profile": "default",
        "domain_rules": [],
    },
],
```

Add helper normalization functions:

```python
def _choice(value: Any, allowed: set[str], default: str) -> str:
    text = _string(value)
    return text if text in allowed else default


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
```

Extend `_normalize_runtime()` to normalize `parser_router`. Extend `_normalize_content_pack()` to normalize `default_scenario_id` and `scenarios`, and ensure the default scenario points to an enabled scenario.

- [ ] **Step 4: Run admin settings tests**

Run:

```powershell
python -m unittest tests.test_admin_settings -v
```

Expected: all admin settings tests pass.

- [ ] **Step 5: Commit**

```powershell
git add packages/core/jstudy_core/admin_settings.py tests/test_admin_settings.py
git commit -m "feat: add routing settings schema"
```

---

### Task 2: Add Runtime Settings Accessors

**Files:**
- Modify: `packages/core/jstudy_core/settings.py`
- Test: `tests/test_settings.py`

- [ ] **Step 1: Write failing runtime settings test**

Add:

```python
def test_runtime_settings_exposes_scenarios_and_parser_router(self):
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        self.write_required_files(root)
        service = AdminSettingsService(root / "data" / "settings")
        content = service.load_content_pack()
        content["default_scenario_id"] = "general-default"
        service.save_content_pack(content)

        settings = RuntimeSettings.from_env(root)

    self.assertEqual(settings.default_scenario_id, "general-default")
    self.assertIn("medicine-default", {item["id"] for item in settings.scenarios})
    self.assertEqual(settings.parser_router_config["mode"], "auto")
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
python -m unittest tests.test_settings.SettingsTest.test_runtime_settings_exposes_scenarios_and_parser_router -v
```

Expected: fail because `RuntimeSettings` has no scenario fields.

- [ ] **Step 3: Extend `RuntimeSettings`**

Add dataclass fields:

```python
default_scenario_id: str = "medicine-default"
scenarios: list[dict[str, Any]] = field(default_factory=list)
parser_router_config: dict[str, Any] = field(default_factory=dict)
```

Populate them inside `from_env()`:

```python
default_scenario_id=str(content.get("default_scenario_id") or content.get("active_pack_id") or "medicine-default"),
scenarios=list(content.get("scenarios", [])),
parser_router_config=dict(runtime.get("parser_router", {})),
```

- [ ] **Step 4: Run settings tests**

Run:

```powershell
python -m unittest tests.test_settings -v
```

Expected: all settings tests pass.

- [ ] **Step 5: Commit**

```powershell
git add packages/core/jstudy_core/settings.py tests/test_settings.py
git commit -m "feat: expose routing settings"
```

---

### Task 3: Add Scenario Router

**Files:**
- Create: `packages/core/jstudy_core/scenario_router.py`
- Test: `tests/test_scenario_router.py`

- [ ] **Step 1: Write failing scenario router tests**

Create `tests/test_scenario_router.py`:

```python
import unittest

from packages.core.jstudy_core.scenario_router import (
    ScenarioRoutingError,
    resolve_scenario,
)


class ScenarioRouterTest(unittest.TestCase):
    def test_uses_default_when_user_does_not_choose(self):
        content = {
            "default_scenario_id": "medicine-default",
            "packs": [{"id": "medicine-default", "enabled": True}],
            "scenarios": [
                {
                    "id": "medicine-default",
                    "enabled": True,
                    "content_pack_id": "medicine-default",
                    "prompt_profile": "medicine-default",
                    "rag_profile": "default",
                    "domain_rules": ["medicine"],
                }
            ],
        }

        resolved = resolve_scenario(content, requested_scenario_id="")

        self.assertEqual(resolved.scenario_id, "medicine-default")
        self.assertEqual(resolved.content_pack["id"], "medicine-default")

    def test_user_choice_overrides_default(self):
        content = {
            "default_scenario_id": "medicine-default",
            "packs": [
                {"id": "medicine-default", "enabled": True},
                {"id": "general-default", "enabled": True},
            ],
            "scenarios": [
                {"id": "medicine-default", "enabled": True, "content_pack_id": "medicine-default"},
                {"id": "general-default", "enabled": True, "content_pack_id": "general-default"},
            ],
        }

        resolved = resolve_scenario(content, requested_scenario_id="general-default")

        self.assertEqual(resolved.scenario_id, "general-default")
        self.assertEqual(resolved.content_pack["id"], "general-default")

    def test_rejects_disabled_scenario(self):
        content = {
            "default_scenario_id": "medicine-default",
            "packs": [{"id": "medicine-default", "enabled": True}],
            "scenarios": [
                {"id": "medicine-default", "enabled": False, "content_pack_id": "medicine-default"}
            ],
        }

        with self.assertRaises(ScenarioRoutingError):
            resolve_scenario(content, requested_scenario_id="medicine-default")
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
python -m unittest tests.test_scenario_router -v
```

Expected: fail because the module does not exist.

- [ ] **Step 3: Implement scenario router**

Create `packages/core/jstudy_core/scenario_router.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ScenarioRoutingError(ValueError):
    pass


@dataclass(frozen=True)
class ScenarioResolution:
    requested_scenario_id: str
    scenario_id: str
    scenario: dict[str, Any]
    content_pack: dict[str, Any]

    def trace_metadata(self) -> dict[str, Any]:
        return {
            "requested_scenario_id": self.requested_scenario_id,
            "resolved_scenario_id": self.scenario_id,
            "content_pack_id": self.content_pack.get("id", ""),
            "prompt_profile": self.scenario.get("prompt_profile", ""),
            "rag_profile": self.scenario.get("rag_profile", ""),
            "domain_rules": self.scenario.get("domain_rules", []),
        }


def resolve_scenario(content_pack: dict[str, Any], requested_scenario_id: str | None = None) -> ScenarioResolution:
    requested = (requested_scenario_id or "").strip()
    selected_id = requested or str(content_pack.get("default_scenario_id") or content_pack.get("active_pack_id") or "")
    scenarios = content_pack.get("scenarios", [])
    scenario = next((item for item in scenarios if item.get("id") == selected_id), None)
    if scenario is None:
        raise ScenarioRoutingError(f"Unknown scenario_id: {selected_id}")
    if not scenario.get("enabled", True):
        raise ScenarioRoutingError(f"Scenario is disabled: {selected_id}")

    pack_id = str(scenario.get("content_pack_id") or content_pack.get("active_pack_id") or "")
    packs = content_pack.get("packs", [])
    pack = next((item for item in packs if item.get("id") == pack_id), None)
    if pack is None:
        raise ScenarioRoutingError(f"Scenario content pack not found: {pack_id}")
    if not pack.get("enabled", True):
        raise ScenarioRoutingError(f"Scenario content pack is disabled: {pack_id}")

    return ScenarioResolution(
        requested_scenario_id=requested,
        scenario_id=selected_id,
        scenario=scenario,
        content_pack=pack,
    )
```

- [ ] **Step 4: Run scenario router tests**

Run:

```powershell
python -m unittest tests.test_scenario_router -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add packages/core/jstudy_core/scenario_router.py tests/test_scenario_router.py
git commit -m "feat: add scenario router"
```

---

### Task 4: Add Parser Router

**Files:**
- Create: `packages/parsers/router.py`
- Create: `packages/parsers/mineru_parser.py`
- Modify: `packages/parsers/__init__.py`
- Test: `tests/test_parser_router.py`

- [ ] **Step 1: Write failing parser router tests**

Create `tests/test_parser_router.py`:

```python
import unittest

from packages.parsers.router import PdfComplexityMetrics, choose_parser_backend


class ParserRouterTest(unittest.TestCase):
    def test_simple_pdf_chooses_pymupdf(self):
        config = {
            "mode": "auto",
            "default_backend": "pymupdf",
            "mineru_enabled": True,
            "fallback_to_pymupdf": True,
            "thresholds": {"complexity_score_mineru_min": 60},
        }
        metrics = PdfComplexityMetrics(
            page_count=20,
            average_text_chars=500,
            empty_page_ratio=0.0,
            image_object_ratio=1.0,
            table_hint_ratio=0.0,
        )

        decision = choose_parser_backend(metrics, config)

        self.assertEqual(decision.selected_backend, "pymupdf")
        self.assertLess(decision.complexity_score, 60)

    def test_complex_pdf_chooses_mineru_when_enabled(self):
        config = {
            "mode": "auto",
            "default_backend": "pymupdf",
            "mineru_enabled": True,
            "fallback_to_pymupdf": True,
            "thresholds": {"complexity_score_mineru_min": 60},
        }
        metrics = PdfComplexityMetrics(
            page_count=100,
            average_text_chars=40,
            empty_page_ratio=0.4,
            image_object_ratio=6.0,
            table_hint_ratio=0.35,
        )

        decision = choose_parser_backend(metrics, config)

        self.assertEqual(decision.selected_backend, "mineru")
        self.assertIn("low_text_density", decision.reasons)

    def test_complex_pdf_falls_back_when_mineru_disabled(self):
        config = {
            "mode": "auto",
            "default_backend": "pymupdf",
            "mineru_enabled": False,
            "fallback_to_pymupdf": True,
            "thresholds": {"complexity_score_mineru_min": 60},
        }
        metrics = PdfComplexityMetrics(
            page_count=100,
            average_text_chars=40,
            empty_page_ratio=0.4,
            image_object_ratio=6.0,
            table_hint_ratio=0.35,
        )

        decision = choose_parser_backend(metrics, config)

        self.assertEqual(decision.selected_backend, "pymupdf")
        self.assertTrue(decision.fallback)
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
python -m unittest tests.test_parser_router -v
```

Expected: fail because `packages.parsers.router` does not exist.

- [ ] **Step 3: Implement parser router decisions**

Create `packages/parsers/router.py`:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import fitz


@dataclass(frozen=True)
class PdfComplexityMetrics:
    page_count: int
    average_text_chars: float
    empty_page_ratio: float
    image_object_ratio: float
    table_hint_ratio: float


@dataclass(frozen=True)
class ParserDecision:
    selected_backend: str
    complexity_score: int
    reasons: list[str]
    fallback: bool
    mineru_available: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyze_pdf_complexity(pdf_path: Path, sample_pages: int = 12) -> PdfComplexityMetrics:
    text_lengths: list[int] = []
    image_objects = 0
    table_hints = 0
    with fitz.open(str(pdf_path)) as doc:
        page_count = len(doc)
        for index, page in enumerate(doc):
            if index >= sample_pages:
                break
            text = page.get_text("text") or ""
            text_lengths.append(len(text.strip()))
            image_objects += len(page.get_images(full=True))
            table_hints += text.count("|") + text.count("\t")

    sampled = max(1, len(text_lengths))
    empty_pages = sum(1 for length in text_lengths if length < 40)
    average_text = sum(text_lengths) / sampled
    return PdfComplexityMetrics(
        page_count=page_count,
        average_text_chars=average_text,
        empty_page_ratio=empty_pages / sampled,
        image_object_ratio=image_objects / sampled,
        table_hint_ratio=min(1.0, table_hints / max(1, sum(text_lengths))),
    )


def choose_parser_backend(metrics: PdfComplexityMetrics, config: dict[str, Any]) -> ParserDecision:
    mode = str(config.get("mode") or "auto")
    default_backend = str(config.get("default_backend") or "pymupdf")
    mineru_enabled = bool(config.get("mineru_enabled"))
    fallback_to_pymupdf = bool(config.get("fallback_to_pymupdf", True))
    thresholds = config.get("thresholds", {}) if isinstance(config.get("thresholds"), dict) else {}
    score_min = int(thresholds.get("complexity_score_mineru_min", 60))

    if mode == "force_pymupdf":
        return ParserDecision(default_backend, 0, ["forced_pymupdf"], False, mineru_enabled)
    if mode == "force_mineru":
        if mineru_enabled:
            return ParserDecision("mineru", 100, ["forced_mineru"], False, True)
        return ParserDecision("pymupdf", 100, ["forced_mineru_unavailable"], fallback_to_pymupdf, False)

    score, reasons = _score(metrics)
    if score >= score_min and mineru_enabled:
        return ParserDecision("mineru", score, reasons, False, True)
    if score >= score_min:
        return ParserDecision("pymupdf", score, reasons + ["mineru_unavailable"], fallback_to_pymupdf, False)
    return ParserDecision(default_backend, score, reasons, False, mineru_enabled)


def _score(metrics: PdfComplexityMetrics) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    if metrics.page_count >= 80:
        score += 15
        reasons.append("large_document")
    if metrics.average_text_chars < 120:
        score += 35
        reasons.append("low_text_density")
    if metrics.empty_page_ratio > 0.25:
        score += 25
        reasons.append("many_empty_pages")
    if metrics.image_object_ratio > 3:
        score += 20
        reasons.append("image_dense")
    if metrics.table_hint_ratio > 0.02:
        score += 15
        reasons.append("table_like_text")
    return min(score, 100), reasons
```

Create `packages/parsers/mineru_parser.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any


def extract_pdf_pages_with_mineru(pdf_path: Path, config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    raise RuntimeError("MinerU parser is selected but no MinerU adapter is configured")
```

Update `packages/parsers/__init__.py`:

```python
from .pymupdf_parser import extract_pdf_pages
from .router import ParserDecision, PdfComplexityMetrics, analyze_pdf_complexity, choose_parser_backend

__all__ = [
    "ParserDecision",
    "PdfComplexityMetrics",
    "analyze_pdf_complexity",
    "choose_parser_backend",
    "extract_pdf_pages",
]
```

- [ ] **Step 4: Run parser tests**

Run:

```powershell
python -m unittest tests.test_parser_router -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add packages/parsers/router.py packages/parsers/mineru_parser.py packages/parsers/__init__.py tests/test_parser_router.py
git commit -m "feat: add parser router"
```

---

### Task 5: Persist Job Routing Metadata

**Files:**
- Modify: `packages/core/jstudy_core/jobs.py`
- Test: `tests/test_job_store.py`

- [ ] **Step 1: Write failing metadata persistence test**

Add:

```python
def test_job_store_persists_routing_metadata(self):
    with TemporaryDirectory() as tmp:
        store_path = Path(tmp) / "jobs.json"
        store = JobStore(store_path=store_path)
        store.create(
            job_id="job-1",
            pdf_path=Path("input/lecture.pdf"),
            output_dir=Path("job-1/output"),
            metadata={"scenario": {"resolved_scenario_id": "medicine-default"}},
        )

        restored = JobStore(store_path=store_path).require("job-1")

    self.assertEqual(restored.metadata["scenario"]["resolved_scenario_id"], "medicine-default")
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
python -m unittest tests.test_job_store.JobStoreTest.test_job_store_persists_routing_metadata -v
```

Expected: fail because `JobRecord` has no `metadata` field.

- [ ] **Step 3: Add metadata to job records**

Update `JobRecord`:

```python
metadata: dict[str, Any] = field(default_factory=dict)
```

Add to `to_dict()`:

```python
"metadata": self.metadata,
```

Add to `from_dict()`:

```python
metadata=payload.get("metadata", {}),
```

Add to `JobStore.create()` signature:

```python
metadata: dict[str, Any] | None = None,
```

Pass it into `JobRecord`:

```python
metadata=metadata or {},
```

- [ ] **Step 4: Run job store tests**

Run:

```powershell
python -m unittest tests.test_job_store -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add packages/core/jstudy_core/jobs.py tests/test_job_store.py
git commit -m "feat: persist job routing metadata"
```

---

### Task 6: Pass Routing Through Pipeline Trace

**Files:**
- Modify: `packages/core/jstudy_core/pipeline.py`
- Test: `tests/test_mvp_runner.py`

- [ ] **Step 1: Write failing trace metadata test**

Add to an existing `run_mvp` test:

```python
outputs = run_mvp(
    pdf_path=pdf,
    soul_path=soul,
    mnemonics_path=mnemonics,
    api_key_path=api_key,
    output_dir=root / "out",
    chat_model="chat",
    embed_model="embed",
    rag_config=RagConfig(top_k_candidates=1, per_query_limit=1),
    parser_backend="pymupdf",
    parser_decision={"selected_backend": "pymupdf", "complexity_score": 12},
    routing_metadata={"resolved_scenario_id": "medicine-default"},
)
trace = read_json(outputs["trace"])
self.assertEqual(trace["parser"]["backend"], "pymupdf")
self.assertEqual(trace["parser"]["decision"]["complexity_score"], 12)
self.assertEqual(trace["scenario"]["resolved_scenario_id"], "medicine-default")
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
python -m unittest tests.test_mvp_runner.MvpRunnerTest.test_run_mvp_writes_links_quality_cache_and_uses_outline -v
```

Expected: fail because `run_mvp` does not accept routing metadata.

- [ ] **Step 3: Extend pipeline signature and trace**

Add parameters to `run_mvp()`:

```python
parser_backend: str = "pymupdf",
parser_decision: dict[str, Any] | None = None,
routing_metadata: dict[str, Any] | None = None,
```

Import `Any` from `typing`.

Change extraction:

```python
if parser_backend != "pymupdf":
    raise RuntimeError(f"Parser backend is not available in this build: {parser_backend}")
pages = extract_pdf_pages(pdf_path)
```

Add to trace payload:

```python
"scenario": routing_metadata or {},
"parser": {
    "backend": parser_backend,
    "decision": parser_decision or {"selected_backend": parser_backend},
},
```

- [ ] **Step 4: Run MVP runner tests**

Run:

```powershell
python -m unittest tests.test_mvp_runner -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add packages/core/jstudy_core/pipeline.py tests/test_mvp_runner.py
git commit -m "feat: write routing metadata to trace"
```

---

### Task 7: Integrate Routing Into FastAPI Generation

**Files:**
- Modify: `apps/api/jstudy_api/app.py`
- Test: `tests/test_web_mvp.py`

- [ ] **Step 1: Write failing API test for scenario submission**

Add:

```python
def test_generate_accepts_scenario_and_passes_routing_metadata(self):
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        settings = self.ready_settings(root)
        captured = {}

        def runner(**kwargs):
            captured.update(kwargs)
            output_dir = kwargs["output_dir"]
            output_dir.mkdir(parents=True, exist_ok=True)
            paths = build_output_paths(output_dir, "result")
            write_json(paths.trace, {})
            write_json(paths.evidence, [])
            write_json(paths.evidence_links, [])
            write_json(paths.quality, {"status": "ok"})
            paths.markdown.write_text("ok\n", encoding="utf-8")
            write_json(paths.chunks, [])
            return paths.as_dict()

        app = create_app(base_dir=root / "jobs", runner=runner, settings=settings)
        client = TestClient(app)
        response = client.post(
            "/api/generate",
            data={"scenario_id": "medicine-default"},
            files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
        )

    self.assertEqual(response.status_code, 200)
    self.assertEqual(captured["routing_metadata"]["resolved_scenario_id"], "medicine-default")
    self.assertEqual(captured["parser_backend"], "pymupdf")
    self.assertIn("selected_backend", captured["parser_decision"])
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
python -m unittest tests.test_web_mvp.WebMvpTest.test_generate_accepts_scenario_and_passes_routing_metadata -v
```

Expected: fail because the endpoint does not accept `scenario_id` or route parser decisions.

- [ ] **Step 3: Update API endpoint**

Modify imports:

```python
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from packages.core.jstudy_core.scenario_router import ScenarioRoutingError, resolve_scenario
from packages.parsers.router import analyze_pdf_complexity, choose_parser_backend
```

Add `scenario_id` form field:

```python
scenario_id: str = Form(""),
```

After saving the PDF:

```python
try:
    scenario = resolve_scenario(runtime.content_pack, scenario_id)
except ScenarioRoutingError as exc:
    raise HTTPException(status_code=400, detail=str(exc))

metrics = analyze_pdf_complexity(pdf_path)
decision = choose_parser_backend(metrics, runtime.parser_router_config)
routing_metadata = scenario.trace_metadata()
```

Pass metadata to job creation:

```python
jobs.create(
    job_id=job_id,
    pdf_path=pdf_path,
    outline_path=outline_path,
    output_dir=job_dir / "output",
    metadata={
        "scenario": routing_metadata,
        "parser_decision": decision.to_dict(),
    },
)
```

In `run_job()` pass to runner:

```python
"parser_backend": job.metadata.get("parser_decision", {}).get("selected_backend", "pymupdf"),
"parser_decision": job.metadata.get("parser_decision", {}),
"routing_metadata": job.metadata.get("scenario", {}),
```

- [ ] **Step 4: Add rejection test for unknown scenario**

Add:

```python
def test_generate_rejects_unknown_scenario(self):
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        settings = self.ready_settings(root)
        app = create_app(base_dir=root / "jobs", settings=settings)
        client = TestClient(app)

        response = client.post(
            "/api/generate",
            data={"scenario_id": "unknown"},
            files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
        )

    self.assertEqual(response.status_code, 400)
    self.assertIn("Unknown scenario_id", response.json()["detail"])
```

- [ ] **Step 5: Run web tests**

Run:

```powershell
python -m unittest tests.test_web_mvp -v
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add apps/api/jstudy_api/app.py tests/test_web_mvp.py
git commit -m "feat: route generation jobs by scenario and parser"
```

---

### Task 8: Add Scenario Selector to User UI

**Files:**
- Modify: `apps/api/jstudy_api/ui.py`
- Test: `tests/test_web_mvp.py`

- [ ] **Step 1: Write failing UI contract test**

Add:

```python
def test_index_html_contains_scenario_selector(self):
    self.assertIn('name="scenario_id"', INDEX_HTML)
    self.assertIn("medicine-default", INDEX_HTML)
    self.assertIn("general-default", INDEX_HTML)
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
python -m unittest tests.test_web_mvp.WebMvpTest.test_index_html_contains_scenario_selector -v
```

Expected: fail because the current form has no scenario selector.

- [ ] **Step 3: Add compact selector**

Inside the upload form, add:

```html
<label>学习场景</label>
<select name="scenario_id">
  <option value="">默认场景</option>
  <option value="medicine-default">医学</option>
  <option value="general-default">通用</option>
</select>
```

Keep existing layout and styling. Do not rebuild the temporary UI in this task.

- [ ] **Step 4: Run UI contract test**

Run:

```powershell
python -m unittest tests.test_web_mvp.WebMvpTest.test_index_html_contains_scenario_selector -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/jstudy_api/ui.py tests/test_web_mvp.py
git commit -m "feat: add scenario selector"
```

---

### Task 9: Add Admin UI Controls

**Files:**
- Modify: `apps/api/jstudy_api/admin_ui.py`
- Test: `tests/test_web_mvp.py`

- [ ] **Step 1: Write failing admin UI test**

Add:

```python
def test_admin_settings_page_contains_routing_controls(self):
    self.assertIn("defaultScenarioId", ADMIN_SETTINGS_HTML)
    self.assertIn("parserRouterMode", ADMIN_SETTINGS_HTML)
    self.assertIn("mineruEnabled", ADMIN_SETTINGS_HTML)
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
python -m unittest tests.test_web_mvp.WebMvpTest.test_admin_settings_page_contains_routing_controls -v
```

Expected: fail because controls are not present.

- [ ] **Step 3: Add routing controls to admin page**

Add fields near the Content Pack and Document Parsing sections:

```html
<label>Default scenario
  <select id="defaultScenarioId"></select>
</label>
<label>Parser router mode
  <select id="parserRouterMode">
    <option value="auto">Auto</option>
    <option value="force_pymupdf">Force PyMuPDF</option>
    <option value="force_mineru">Force MinerU</option>
  </select>
</label>
<label><span><input id="mineruEnabled" type="checkbox"> MinerU available</span></label>
```

Wire JavaScript to read/write:

```javascript
el.defaultScenarioId.value = settings.content_pack.default_scenario_id || settings.content_pack.active_pack_id;
el.parserRouterMode.value = settings.runtime.parser_router.mode || "auto";
el.mineruEnabled.checked = Boolean(settings.runtime.parser_router.mineru_enabled);
```

On save:

```javascript
settings.content_pack.default_scenario_id = el.defaultScenarioId.value;
settings.runtime.parser_router.mode = el.parserRouterMode.value;
settings.runtime.parser_router.mineru_enabled = el.mineruEnabled.checked;
```

- [ ] **Step 4: Run admin UI test**

Run:

```powershell
python -m unittest tests.test_web_mvp.WebMvpTest.test_admin_settings_page_contains_routing_controls -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/jstudy_api/admin_ui.py tests/test_web_mvp.py
git commit -m "feat: add routing controls to admin settings"
```

---

### Task 10: Update Docs and Deployment Defaults

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture/overview.md`
- Modify: `docs/development/standards.md`
- Modify: `deploy/docker-compose/README.md`
- Modify: `.env.example`

- [ ] **Step 1: Update docs**

Document:

- User scenario choice: default from admin settings, optional user override.
- Parser routing: `auto`, `force_pymupdf`, `force_mineru`.
- Storage policy: local files in `JSTUDY_JOBS_DIR` are required for citation preview during the pilot.
- Deployment recommendation: set `JSTUDY_JOB_RETENTION_HOURS=72` or `168` before public testing.
- Formal deployment direction: Tencent COS plus lifecycle rules once user history or course libraries are needed.

- [ ] **Step 2: Update `.env.example`**

Set:

```env
JSTUDY_JOB_RETENTION_HOURS=72
```

If this is too aggressive for development, document that local developers can set it to `0`.

- [ ] **Step 3: Run docs-related tests and config check**

Run:

```powershell
python -m unittest tests.test_deployment_files -v
docker compose -f deploy\docker-compose\api.compose.yml config
```

Expected: both commands pass.

- [ ] **Step 4: Commit**

```powershell
git add README.md docs/architecture/overview.md docs/development/standards.md deploy/docker-compose/README.md .env.example
git commit -m "docs: document routing and storage retention"
```

---

### Task 11: Final Verification

**Files:**
- No code edits unless verification exposes a failure.

- [ ] **Step 1: Run compile check**

```powershell
python -m py_compile web_mvp.py mvp_runner.py apps/api/jstudy_api/app.py apps/api/jstudy_api/ui.py apps/api/jstudy_api/admin_ui.py packages/core/jstudy_core/admin_settings.py packages/core/jstudy_core/scenario_router.py packages/core/jstudy_core/pipeline.py packages/core/jstudy_core/cli.py packages/core/jstudy_core/citations.py packages/core/jstudy_core/jobs.py packages/core/jstudy_core/providers.py packages/core/jstudy_core/settings.py packages/core/jstudy_core/storage.py packages/parsers/router.py packages/parsers/mineru_parser.py packages/parsers/pymupdf_parser.py
```

Expected: exit code 0.

- [ ] **Step 2: Run full tests**

```powershell
python -m unittest discover -s tests -v
```

Expected: all tests pass. Existing `httpx TestClient` deprecation warning may appear.

- [ ] **Step 3: Run diff and compose checks**

```powershell
git diff --check
docker compose -f deploy\docker-compose\api.compose.yml config
```

Expected: exit code 0 for both. Windows line-ending warnings are acceptable if there are no whitespace errors.

- [ ] **Step 4: Push branch**

```powershell
git push
```

Expected: current `feature/backend-frontend-mvp` branch pushes to `origin/feature/backend-frontend-mvp`.

---

## Self-Review

- Spec coverage: scenario routing, parser routing, job trace metadata, admin settings, user UI, storage retention, and non-database deployment are covered.
- Marker scan: no unfinished markers or unspecified implementation steps are intentionally left in the plan.
- Type consistency: `ScenarioResolution.trace_metadata()`, `ParserDecision.to_dict()`, `parser_router_config`, `routing_metadata`, and `parser_decision` are named consistently across tasks.
