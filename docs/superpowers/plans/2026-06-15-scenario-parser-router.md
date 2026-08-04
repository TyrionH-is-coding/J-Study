# Scenario Parser Profile Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add scenario routing and parser profile routing so users choose a learning scene and, when exposed, a clear parsing experience such as Fast or Quality.

**Architecture:** Keep routing in small backend modules. `ScenarioRouter` resolves the effective content pack and scenario from admin settings. `ParserProfileRouter` resolves a user-facing parser profile, enforces visibility/admin rules, and maps the profile to a parser backend. The API stores routing metadata on the job, and the pipeline writes the selected scenario and parser profile into trace output.

**Tech Stack:** Python, FastAPI, PyMuPDF, unittest, JSON admin settings.

---

## Work Order

1. Extend admin settings schema for scenarios and parser profiles.
2. Expose scenario and parser profile settings through `RuntimeSettings`.
3. Add `ScenarioRouter`.
4. Add `ParserProfileRouter`.
5. Persist routing metadata on jobs.
6. Pass routing metadata through the pipeline trace.
7. Integrate scenario/profile resolution into the FastAPI generation endpoint.
8. Add a public options endpoint and update the temporary upload UI.
9. Add admin UI controls for default scenario and parser profile visibility.
10. Update docs and deployment retention guidance.

Do not add PDF complexity scoring. Do not require MinerU in the lightweight deployment.

## File Structure

- Create: `packages/core/jstudy_core/scenario_router.py`
  - Owns scenario validation and default resolution.
- Create: `packages/core/jstudy_core/parser_profile_router.py`
  - Owns parser profile validation, visibility rules, admin-only gating, and backend selection.
- Create: `packages/parsers/mineru_parser.py`
  - Owns the future MinerU adapter boundary and returns a clear runtime error until a real adapter is configured.
- Modify: `packages/core/jstudy_core/admin_settings.py`
  - Adds default scenarios and parser profile settings.
- Modify: `packages/core/jstudy_core/settings.py`
  - Exposes full content-pack config and parser-profile config.
- Modify: `packages/core/jstudy_core/jobs.py`
  - Persists job metadata for scenario and parser profile decisions.
- Modify: `packages/core/jstudy_core/pipeline.py`
  - Accepts parser backend and routing metadata, then writes them to trace JSON.
- Modify: `apps/api/jstudy_api/app.py`
  - Accepts `scenario_id` and `parser_profile_id`, resolves routing, and passes metadata to background jobs.
- Modify: `apps/api/jstudy_api/ui.py`
  - Loads public options and includes a parser profile selector only when multiple public profiles are available.
- Modify: `apps/api/jstudy_api/admin_ui.py`
  - Adds default scenario and parser profile controls.
- Modify docs:
  - `README.md`
  - `docs/architecture/overview.md`
  - `docs/development/standards.md`
  - `deploy/docker-compose/README.md`
  - `.env.example`

---

### Task 1: Extend Admin Settings Schema

**Files:**
- Modify: `packages/core/jstudy_core/admin_settings.py`
- Test: `tests/test_admin_settings.py`

- [ ] **Step 1: Write failing tests for scenarios and parser profiles**

Add tests:

```python
def test_content_pack_defaults_include_scenarios(self):
    with TemporaryDirectory() as tmp:
        service = AdminSettingsService(Path(tmp) / "settings")
        payload = service.load_content_pack()

    self.assertEqual(payload["default_scenario_id"], "medicine-default")
    scenario_ids = {item["id"] for item in payload["scenarios"]}
    self.assertIn("medicine-default", scenario_ids)
    self.assertIn("general-default", scenario_ids)


def test_runtime_defaults_include_parser_profiles(self):
    with TemporaryDirectory() as tmp:
        service = AdminSettingsService(Path(tmp) / "settings")
        payload = service.load_runtime()

    profiles = payload["parser_profiles"]
    self.assertEqual(profiles["default_profile_id"], "fast")
    by_id = {item["id"]: item for item in profiles["profiles"]}
    self.assertEqual(by_id["fast"]["backend"], "pymupdf")
    self.assertTrue(by_id["fast"]["visible_to_users"])
    self.assertEqual(by_id["quality"]["backend"], "mineru")
    self.assertFalse(by_id["quality"]["visible_to_users"])
    self.assertTrue(by_id["quality"]["requires_admin"])
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m unittest tests.test_admin_settings.AdminSettingsTest.test_content_pack_defaults_include_scenarios tests.test_admin_settings.AdminSettingsTest.test_runtime_defaults_include_parser_profiles -v
```

Expected: fail because `default_scenario_id`, `scenarios`, and `parser_profiles` do not exist yet.

- [ ] **Step 3: Add defaults**

Update `_content_pack_default()` with:

```python
"default_scenario_id": "medicine-default",
"scenarios": [
    {
        "id": "medicine-default",
        "display_name": "医学",
        "subject": "medicine",
        "enabled": True,
        "content_pack_id": "medicine-default",
        "prompt_profile": "medicine-default",
        "rag_profile": "default",
        "domain_rules": ["medicine"],
    },
    {
        "id": "general-default",
        "display_name": "通用",
        "subject": "general",
        "enabled": True,
        "content_pack_id": "medicine-default",
        "prompt_profile": "general-default",
        "rag_profile": "default",
        "domain_rules": [],
    },
],
```

Update `_runtime_default()` with:

```python
"parser_profiles": {
    "default_profile_id": "fast",
    "profiles": [
        {
            "id": "fast",
            "display_name": "快速解析",
            "backend": "pymupdf",
            "enabled": True,
            "visible_to_users": True,
            "requires_admin": False,
            "tier": "free",
            "estimated_wait": "较短",
        },
        {
            "id": "quality",
            "display_name": "高质量解析",
            "backend": "mineru",
            "enabled": False,
            "visible_to_users": False,
            "requires_admin": True,
            "tier": "internal",
            "estimated_wait": "较长",
        },
    ],
},
```

Add helpers:

```python
def _choice(value: Any, allowed: set[str], default: str) -> str:
    text = _string(value)
    return text if text in allowed else default


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
```

Extend `_normalize_runtime()` to normalize `parser_profiles`. Extend `_normalize_content_pack()` to normalize `default_scenario_id` and `scenarios`.

- [ ] **Step 4: Run admin settings tests**

Run:

```powershell
python -m unittest tests.test_admin_settings -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add packages/core/jstudy_core/admin_settings.py tests/test_admin_settings.py
git commit -m "feat: add scenario and parser profile settings"
```

---

### Task 2: Expose Routing Settings at Runtime

**Files:**
- Modify: `packages/core/jstudy_core/settings.py`
- Test: `tests/test_settings.py`

- [ ] **Step 1: Write failing runtime test**

Add:

```python
def test_runtime_settings_exposes_scenario_and_parser_profile_config(self):
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
    self.assertEqual(settings.parser_profiles_config["default_profile_id"], "fast")
    self.assertEqual(settings.content_pack_config["default_scenario_id"], "general-default")
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
python -m unittest tests.test_settings.SettingsTest.test_runtime_settings_exposes_scenario_and_parser_profile_config -v
```

Expected: fail because `RuntimeSettings` has no routing fields.

- [ ] **Step 3: Extend `RuntimeSettings`**

Add dataclass fields:

```python
content_pack_config: dict[str, Any] = field(default_factory=dict)
default_scenario_id: str = "medicine-default"
scenarios: list[dict[str, Any]] = field(default_factory=list)
parser_profiles_config: dict[str, Any] = field(default_factory=dict)
```

Populate them in `from_env()`:

```python
content_pack_config=content,
default_scenario_id=str(content.get("default_scenario_id") or content.get("active_pack_id") or "medicine-default"),
scenarios=list(content.get("scenarios", [])),
parser_profiles_config=dict(runtime.get("parser_profiles", {})),
```

- [ ] **Step 4: Run settings tests**

Run:

```powershell
python -m unittest tests.test_settings -v
```

Expected: pass.

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

- [ ] **Step 1: Write failing tests**

Create `tests/test_scenario_router.py`:

```python
import unittest

from packages.core.jstudy_core.scenario_router import ScenarioRoutingError, resolve_scenario


class ScenarioRouterTest(unittest.TestCase):
    def test_uses_default_when_user_does_not_choose(self):
        config = {
            "default_scenario_id": "medicine-default",
            "packs": [{"id": "medicine-default", "enabled": True}],
            "scenarios": [
                {"id": "medicine-default", "enabled": True, "content_pack_id": "medicine-default"}
            ],
        }

        resolved = resolve_scenario(config, requested_scenario_id="")

        self.assertEqual(resolved.scenario_id, "medicine-default")
        self.assertEqual(resolved.content_pack["id"], "medicine-default")

    def test_user_choice_overrides_default(self):
        config = {
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

        resolved = resolve_scenario(config, requested_scenario_id="general-default")

        self.assertEqual(resolved.scenario_id, "general-default")

    def test_rejects_disabled_scenario(self):
        config = {
            "default_scenario_id": "medicine-default",
            "packs": [{"id": "medicine-default", "enabled": True}],
            "scenarios": [
                {"id": "medicine-default", "enabled": False, "content_pack_id": "medicine-default"}
            ],
        }

        with self.assertRaises(ScenarioRoutingError):
            resolve_scenario(config, requested_scenario_id="medicine-default")
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
python -m unittest tests.test_scenario_router -v
```

Expected: fail because the module does not exist.

- [ ] **Step 3: Implement `ScenarioRouter`**

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


def resolve_scenario(content_config: dict[str, Any], requested_scenario_id: str | None = None) -> ScenarioResolution:
    requested = (requested_scenario_id or "").strip()
    selected_id = requested or str(content_config.get("default_scenario_id") or content_config.get("active_pack_id") or "")
    scenario = next((item for item in content_config.get("scenarios", []) if item.get("id") == selected_id), None)
    if scenario is None:
        raise ScenarioRoutingError(f"Unknown scenario_id: {selected_id}")
    if not scenario.get("enabled", True):
        raise ScenarioRoutingError(f"Scenario is disabled: {selected_id}")

    pack_id = str(scenario.get("content_pack_id") or content_config.get("active_pack_id") or "")
    pack = next((item for item in content_config.get("packs", []) if item.get("id") == pack_id), None)
    if pack is None:
        raise ScenarioRoutingError(f"Scenario content pack not found: {pack_id}")
    if not pack.get("enabled", True):
        raise ScenarioRoutingError(f"Scenario content pack is disabled: {pack_id}")

    return ScenarioResolution(requested, selected_id, scenario, pack)
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

### Task 4: Add Parser Profile Router

**Files:**
- Create: `packages/core/jstudy_core/parser_profile_router.py`
- Create: `packages/parsers/mineru_parser.py`
- Test: `tests/test_parser_profile_router.py`

- [ ] **Step 1: Write failing parser profile tests**

Create `tests/test_parser_profile_router.py`:

```python
import unittest

from packages.core.jstudy_core.parser_profile_router import (
    ParserProfileRoutingError,
    ParserProfileUnavailable,
    public_parser_profiles,
    resolve_parser_profile,
)


class ParserProfileRouterTest(unittest.TestCase):
    def config(self):
        return {
            "default_profile_id": "fast",
            "profiles": [
                {
                    "id": "fast",
                    "display_name": "快速解析",
                    "backend": "pymupdf",
                    "enabled": True,
                    "visible_to_users": True,
                    "requires_admin": False,
                    "tier": "free",
                },
                {
                    "id": "quality",
                    "display_name": "高质量解析",
                    "backend": "mineru",
                    "enabled": True,
                    "visible_to_users": False,
                    "requires_admin": True,
                    "tier": "internal",
                },
            ],
        }

    def test_uses_default_fast_profile(self):
        resolved = resolve_parser_profile(self.config(), requested_profile_id="", is_admin=False)

        self.assertEqual(resolved.profile_id, "fast")
        self.assertEqual(resolved.backend, "pymupdf")

    def test_public_profiles_hide_admin_quality(self):
        profiles = public_parser_profiles(self.config())

        self.assertEqual([item["id"] for item in profiles], ["fast"])

    def test_rejects_hidden_quality_for_normal_user(self):
        with self.assertRaises(ParserProfileRoutingError):
            resolve_parser_profile(self.config(), requested_profile_id="quality", is_admin=False)

    def test_allows_hidden_quality_for_admin(self):
        resolved = resolve_parser_profile(self.config(), requested_profile_id="quality", is_admin=True)

        self.assertEqual(resolved.backend, "mineru")
        self.assertTrue(resolved.requires_admin)

    def test_rejects_mineru_when_not_configured(self):
        with self.assertRaises(ParserProfileUnavailable):
            resolve_parser_profile(
                self.config(),
                requested_profile_id="quality",
                is_admin=True,
                parser_config={"mineru": {"api_token": "", "local_cli_path": ""}},
            )
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
python -m unittest tests.test_parser_profile_router -v
```

Expected: fail because the module does not exist.

- [ ] **Step 3: Implement parser profile router**

Create `packages/core/jstudy_core/parser_profile_router.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ParserProfileRoutingError(ValueError):
    pass


class ParserProfileUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class ParserProfileResolution:
    requested_profile_id: str
    profile_id: str
    display_name: str
    backend: str
    tier: str
    visible_to_users: bool
    requires_admin: bool

    def trace_metadata(self) -> dict[str, Any]:
        return {
            "requested_parser_profile_id": self.requested_profile_id,
            "resolved_parser_profile_id": self.profile_id,
            "display_name": self.display_name,
            "backend": self.backend,
            "tier": self.tier,
            "visible_to_users": self.visible_to_users,
            "requires_admin": self.requires_admin,
        }


def public_parser_profiles(config: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": profile.get("id", ""),
            "display_name": profile.get("display_name", ""),
            "estimated_wait": profile.get("estimated_wait", ""),
            "tier": profile.get("tier", ""),
        }
        for profile in config.get("profiles", [])
        if profile.get("enabled", True)
        and profile.get("visible_to_users", False)
        and not profile.get("requires_admin", False)
    ]


def resolve_parser_profile(
    config: dict[str, Any],
    requested_profile_id: str | None = None,
    is_admin: bool = False,
    parser_config: dict[str, Any] | None = None,
) -> ParserProfileResolution:
    requested = (requested_profile_id or "").strip()
    selected_id = requested or str(config.get("default_profile_id") or "fast")
    profile = next((item for item in config.get("profiles", []) if item.get("id") == selected_id), None)
    if profile is None:
        raise ParserProfileRoutingError(f"Unknown parser_profile_id: {selected_id}")
    if not profile.get("enabled", True):
        raise ParserProfileRoutingError(f"Parser profile is disabled: {selected_id}")
    if profile.get("requires_admin", False) and not is_admin:
        raise ParserProfileRoutingError(f"Parser profile requires admin access: {selected_id}")
    if not profile.get("visible_to_users", False) and not is_admin:
        raise ParserProfileRoutingError(f"Parser profile is not available: {selected_id}")

    backend = str(profile.get("backend") or "pymupdf")
    if backend == "mineru" and parser_config is not None and not _mineru_configured(parser_config):
        raise ParserProfileUnavailable("MinerU is not configured; use fast parsing for now")

    return ParserProfileResolution(
        requested_profile_id=requested,
        profile_id=selected_id,
        display_name=str(profile.get("display_name") or selected_id),
        backend=backend,
        tier=str(profile.get("tier") or ""),
        visible_to_users=bool(profile.get("visible_to_users", False)),
        requires_admin=bool(profile.get("requires_admin", False)),
    )


def _mineru_configured(parser_config: dict[str, Any]) -> bool:
    mineru = parser_config.get("mineru", {}) if isinstance(parser_config.get("mineru"), dict) else {}
    return bool(str(mineru.get("api_token") or "").strip() or str(mineru.get("local_cli_path") or "").strip())
```

Create `packages/parsers/mineru_parser.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any


def extract_pdf_pages_with_mineru(pdf_path: Path, config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    raise RuntimeError("MinerU parser is selected but no MinerU adapter is configured")
```

- [ ] **Step 4: Run parser profile tests**

Run:

```powershell
python -m unittest tests.test_parser_profile_router -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add packages/core/jstudy_core/parser_profile_router.py packages/parsers/mineru_parser.py tests/test_parser_profile_router.py
git commit -m "feat: add parser profile router"
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
            metadata={
                "scenario": {"resolved_scenario_id": "medicine-default"},
                "parser_profile": {"resolved_parser_profile_id": "fast"},
            },
        )

        restored = JobStore(store_path=store_path).require("job-1")

    self.assertEqual(restored.metadata["scenario"]["resolved_scenario_id"], "medicine-default")
    self.assertEqual(restored.metadata["parser_profile"]["resolved_parser_profile_id"], "fast")
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

Add to `JobStore.create()`:

```python
metadata: dict[str, Any] | None = None,
```

and pass:

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
git commit -m "feat: persist routing metadata"
```

---

### Task 6: Write Routing Metadata to Pipeline Trace

**Files:**
- Modify: `packages/core/jstudy_core/pipeline.py`
- Test: `tests/test_mvp_runner.py`

- [ ] **Step 1: Write failing trace test**

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
    routing_metadata={
        "scenario": {"resolved_scenario_id": "medicine-default"},
        "parser_profile": {"resolved_parser_profile_id": "fast", "backend": "pymupdf"},
    },
)
trace = read_json(outputs["trace"])
self.assertEqual(trace["scenario"]["resolved_scenario_id"], "medicine-default")
self.assertEqual(trace["parser_profile"]["resolved_parser_profile_id"], "fast")
self.assertEqual(trace["parser"]["backend"], "pymupdf")
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
python -m unittest tests.test_mvp_runner.MvpRunnerTest.test_run_mvp_writes_links_quality_cache_and_uses_outline -v
```

Expected: fail because `run_mvp` does not accept parser or routing metadata.

- [ ] **Step 3: Extend pipeline**

Add parameters:

```python
parser_backend: str = "pymupdf",
routing_metadata: dict[str, Any] | None = None,
parser_config: dict[str, Any] | None = None,
```

Import:

```python
from typing import Any
from packages.parsers.mineru_parser import extract_pdf_pages_with_mineru
```

Choose parser:

```python
if parser_backend == "pymupdf":
    pages = extract_pdf_pages(pdf_path)
elif parser_backend == "mineru":
    pages = extract_pdf_pages_with_mineru(pdf_path, parser_config or {})
else:
    raise RuntimeError(f"Unknown parser backend: {parser_backend}")
```

Add trace fields:

```python
"scenario": (routing_metadata or {}).get("scenario", {}),
"parser_profile": (routing_metadata or {}).get("parser_profile", {}),
"parser": {"backend": parser_backend},
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
git commit -m "feat: write parser profile metadata to trace"
```

---

### Task 7: Integrate Routing Into FastAPI

**Files:**
- Modify: `apps/api/jstudy_api/app.py`
- Test: `tests/test_web_mvp.py`

- [ ] **Step 1: Write failing API test for default fast profile**

Add:

```python
def test_generate_uses_default_scenario_and_fast_parser_profile(self):
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
            write_json(paths.chunks, [])
            paths.markdown.write_text("ok\n", encoding="utf-8")
            return paths.as_dict()

        app = create_app(base_dir=root / "jobs", runner=runner, settings=settings)
        client = TestClient(app)
        response = client.post(
            "/api/generate",
            files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
        )

    self.assertEqual(response.status_code, 200)
    self.assertEqual(captured["parser_backend"], "pymupdf")
    self.assertEqual(captured["routing_metadata"]["parser_profile"]["resolved_parser_profile_id"], "fast")
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
python -m unittest tests.test_web_mvp.WebMvpTest.test_generate_uses_default_scenario_and_fast_parser_profile -v
```

Expected: fail because the endpoint does not resolve parser profiles.

- [ ] **Step 3: Update API imports and admin helper**

Add imports:

```python
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from packages.core.jstudy_core.parser_profile_router import (
    ParserProfileRoutingError,
    ParserProfileUnavailable,
    public_parser_profiles,
    resolve_parser_profile,
)
from packages.core.jstudy_core.scenario_router import ScenarioRoutingError, resolve_scenario
```

Add helper:

```python
def is_admin_request(request: Request) -> bool:
    expected = os.getenv(ADMIN_TOKEN_ENV, "").strip()
    if not expected:
        return False
    auth = request.headers.get("authorization", "").strip()
    bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    query = request.query_params.get("admin_token", "").strip()
    return expected in {bearer, query}
```

Update `require_admin()` to call `is_admin_request(request)`.

- [ ] **Step 4: Resolve scenario and parser profile in `/api/generate`**

Add form fields:

```python
scenario_id: str = Form(""),
parser_profile_id: str = Form(""),
```

After saving the PDF:

```python
try:
    scenario = resolve_scenario(runtime.content_pack_config, scenario_id)
    parser_profile = resolve_parser_profile(
        runtime.parser_profiles_config,
        parser_profile_id,
        is_admin=is_admin_request(request),
        parser_config=runtime.parser_config,
    )
except ScenarioRoutingError as exc:
    raise HTTPException(status_code=400, detail=str(exc))
except ParserProfileRoutingError as exc:
    raise HTTPException(status_code=403, detail=str(exc))
except ParserProfileUnavailable as exc:
    raise HTTPException(status_code=503, detail=str(exc))
```

Create metadata:

```python
routing_metadata = {
    "scenario": scenario.trace_metadata(),
    "parser_profile": parser_profile.trace_metadata(),
}
```

Pass to job:

```python
metadata=routing_metadata,
```

Pass to runner:

```python
"parser_backend": job.metadata.get("parser_profile", {}).get("backend", "pymupdf"),
"routing_metadata": job.metadata,
"parser_config": runtime.parser_config,
```

- [ ] **Step 5: Add hidden quality rejection test**

Add:

```python
def test_generate_rejects_hidden_quality_parser_for_public_user(self):
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        settings = self.ready_settings(root)
        app = create_app(base_dir=root / "jobs", settings=settings)
        client = TestClient(app)

        response = client.post(
            "/api/generate",
            data={"parser_profile_id": "quality"},
            files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
        )

    self.assertEqual(response.status_code, 403)
```

- [ ] **Step 6: Run web tests**

Run:

```powershell
python -m unittest tests.test_web_mvp -v
```

Expected: pass.

- [ ] **Step 7: Commit**

```powershell
git add apps/api/jstudy_api/app.py tests/test_web_mvp.py
git commit -m "feat: route generation by scenario and parser profile"
```

---

### Task 8: Add Public Options Endpoint and Upload UI

**Files:**
- Modify: `apps/api/jstudy_api/app.py`
- Modify: `apps/api/jstudy_api/ui.py`
- Test: `tests/test_web_mvp.py`

- [ ] **Step 1: Write failing options endpoint test**

Add:

```python
def test_options_endpoint_returns_public_scenarios_and_parser_profiles(self):
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        settings = self.ready_settings(root)
        app = create_app(base_dir=root / "jobs", settings=settings)
        client = TestClient(app)

        response = client.get("/api/options")

    self.assertEqual(response.status_code, 200)
    payload = response.json()
    self.assertIn("medicine-default", {item["id"] for item in payload["scenarios"]})
    self.assertEqual([item["id"] for item in payload["parser_profiles"]], ["fast"])
```

- [ ] **Step 2: Add `/api/options`**

Add route:

```python
@app.get("/api/options")
def options(response: Response) -> dict[str, Any]:
    set_no_store(response)
    scenarios = [
        {
            "id": item.get("id", ""),
            "display_name": item.get("display_name", ""),
            "subject": item.get("subject", ""),
        }
        for item in runtime.scenarios
        if item.get("enabled", True)
    ]
    return {
        "default_scenario_id": runtime.default_scenario_id,
        "scenarios": scenarios,
        "default_parser_profile_id": runtime.parser_profiles_config.get("default_profile_id", "fast"),
        "parser_profiles": public_parser_profiles(runtime.parser_profiles_config),
    }
```

- [ ] **Step 3: Write failing UI contract test**

Add:

```python
def test_index_html_loads_scenario_and_parser_profile_options(self):
    self.assertIn("/api/options", INDEX_HTML)
    self.assertIn('name="scenario_id"', INDEX_HTML)
    self.assertIn('name="parser_profile_id"', INDEX_HTML)
```

- [ ] **Step 4: Update temporary UI**

Add form fields:

```html
<label>学习场景</label>
<select name="scenario_id" id="scenarioSelect"></select>
<label id="parserProfileLabel">解析方式</label>
<select name="parser_profile_id" id="parserProfileSelect"></select>
```

Add JS:

```javascript
async function loadOptions() {
  const res = await fetch("/api/options");
  const options = await res.json();
  scenarioSelect.innerHTML = options.scenarios.map(item =>
    `<option value="${item.id}">${item.display_name}</option>`
  ).join("");
  scenarioSelect.value = options.default_scenario_id || "";

  parserProfileSelect.innerHTML = options.parser_profiles.map(item =>
    `<option value="${item.id}">${item.display_name}</option>`
  ).join("");
  parserProfileSelect.value = options.default_parser_profile_id || "fast";
  const showParser = options.parser_profiles.length > 1;
  parserProfileLabel.hidden = !showParser;
  parserProfileSelect.hidden = !showParser;
}
loadOptions().catch(() => {});
```

- [ ] **Step 5: Run web tests**

Run:

```powershell
python -m unittest tests.test_web_mvp -v
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add apps/api/jstudy_api/app.py apps/api/jstudy_api/ui.py tests/test_web_mvp.py
git commit -m "feat: expose public routing options"
```

---

### Task 9: Add Admin UI Controls

**Files:**
- Modify: `apps/api/jstudy_api/admin_ui.py`
- Test: `tests/test_web_mvp.py`

- [ ] **Step 1: Write failing admin UI contract test**

Add:

```python
def test_admin_settings_page_contains_parser_profile_controls(self):
    self.assertIn("defaultScenarioId", ADMIN_SETTINGS_HTML)
    self.assertIn("defaultParserProfileId", ADMIN_SETTINGS_HTML)
    self.assertIn("qualityVisibleToUsers", ADMIN_SETTINGS_HTML)
    self.assertIn("qualityEnabled", ADMIN_SETTINGS_HTML)
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
python -m unittest tests.test_web_mvp.WebMvpTest.test_admin_settings_page_contains_parser_profile_controls -v
```

Expected: fail because controls are not present.

- [ ] **Step 3: Add admin controls**

Add controls:

```html
<label>Default scenario <select id="defaultScenarioId"></select></label>
<label>Default parser profile <select id="defaultParserProfileId"></select></label>
<label><span><input id="qualityEnabled" type="checkbox"> Enable quality profile</span></label>
<label><span><input id="qualityVisibleToUsers" type="checkbox"> Show quality profile to users</span></label>
```

Wire JS to read/write `settings.content_pack.default_scenario_id`, `settings.runtime.parser_profiles.default_profile_id`, and the `quality` profile's `enabled` and `visible_to_users` fields.

- [ ] **Step 4: Run admin UI test**

Run:

```powershell
python -m unittest tests.test_web_mvp.WebMvpTest.test_admin_settings_page_contains_parser_profile_controls -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/jstudy_api/admin_ui.py tests/test_web_mvp.py
git commit -m "feat: add parser profile admin controls"
```

---

### Task 10: Update Docs and Deployment Guidance

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture/overview.md`
- Modify: `docs/development/standards.md`
- Modify: `deploy/docker-compose/README.md`
- Modify: `.env.example`

- [ ] **Step 1: Document product model**

Document:

- `scenario_id` controls subject/content behavior.
- `parser_profile_id` controls parsing experience.
- `fast` is PyMuPDF and public by default.
- `quality` is MinerU-backed, hidden from normal users at first, and intended for admin testing before paid exposure.
- Automatic PDF difficulty scoring is not part of this implementation.

- [ ] **Step 2: Document storage retention**

Document:

- Uploaded PDFs are local during the pilot because citation preview needs the source file.
- Public testing should set `JSTUDY_JOB_RETENTION_HOURS=72` or `168`.
- Formal deployment should move uploads and generated artifacts to Tencent COS when user history or course libraries are needed.

- [ ] **Step 3: Run docs/config checks**

Run:

```powershell
python -m unittest tests.test_deployment_files -v
docker compose -f deploy\docker-compose\api.compose.yml config
```

Expected: pass.

- [ ] **Step 4: Commit**

```powershell
git add README.md docs/architecture/overview.md docs/development/standards.md deploy/docker-compose/README.md .env.example
git commit -m "docs: document parser profile routing"
```

---

### Task 11: Final Verification

**Files:**
- No code edits unless verification exposes a failure.

- [ ] **Step 1: Run compile check**

```powershell
python -m py_compile web_mvp.py mvp_runner.py apps/api/jstudy_api/app.py apps/api/jstudy_api/ui.py apps/api/jstudy_api/admin_ui.py packages/core/jstudy_core/admin_settings.py packages/core/jstudy_core/scenario_router.py packages/core/jstudy_core/parser_profile_router.py packages/core/jstudy_core/pipeline.py packages/core/jstudy_core/cli.py packages/core/jstudy_core/citations.py packages/core/jstudy_core/jobs.py packages/core/jstudy_core/providers.py packages/core/jstudy_core/settings.py packages/core/jstudy_core/storage.py packages/parsers/mineru_parser.py packages/parsers/pymupdf_parser.py
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

- Spec coverage: scenario routing, parser profile routing, hidden quality profile, admin testing path, job trace metadata, public options, admin settings, storage retention, and non-database deployment are covered.
- Marker scan: no unfinished markers or unspecified implementation steps are intentionally left in the plan.
- Type consistency: `ScenarioResolution.trace_metadata()`, `ParserProfileResolution.trace_metadata()`, `parser_profiles_config`, `routing_metadata`, and `parser_profile_id` are named consistently across tasks.
