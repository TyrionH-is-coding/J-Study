# Backend Structure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Move the MVP backend behind formal product package paths without changing current API behavior.

**Architecture:** Keep the first change surgical: move the FastAPI app into `apps/api/jstudy_api/app.py` and the current generation pipeline into `packages/core/jstudy_core/pipeline.py`. Keep root-level `web_mvp.py` and `mvp_runner.py` as compatibility shims so old commands keep working while future code can import the canonical modules.

**Tech Stack:** Python, FastAPI, PyMuPDF, unittest.

---

### Task 1: Canonical Import Contract

**Files:**
- Create: `tests/test_project_structure.py`

- [x] **Step 1: Write the failing test**

```python
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class ProjectStructureTest(unittest.TestCase):
    def test_backend_imports_have_canonical_and_legacy_paths(self):
        from apps.api.jstudy_api.app import INDEX_HTML, app, create_app
        from packages.core.jstudy_core.pipeline import RagConfig, run_mvp
        from mvp_runner import run_mvp as legacy_run_mvp
        from web_mvp import create_app as legacy_create_app

        self.assertTrue(INDEX_HTML.startswith("\n<!doctype html>"))
        self.assertEqual(app.title, "J Study MVP")
        self.assertIs(legacy_create_app, create_app)
        self.assertIs(legacy_run_mvp, run_mvp)
        self.assertEqual(RagConfig().per_query_limit, 2)
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m unittest discover -s tests -p test_project_structure.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'apps'`.

- [x] **Step 3: Create canonical package paths and compatibility shims**

Move current implementation:

```powershell
New-Item -ItemType Directory -Force -Path apps\api\jstudy_api, packages\core\jstudy_core
git mv web_mvp.py apps\api\jstudy_api\app.py
git mv mvp_runner.py packages\core\jstudy_core\pipeline.py
```

Create package markers:

```text
apps/__init__.py
apps/api/__init__.py
apps/api/jstudy_api/__init__.py
packages/__init__.py
packages/core/__init__.py
packages/core/jstudy_core/__init__.py
```

Update imports:

```python
# apps/api/jstudy_api/app.py
from packages.core.jstudy_core.pipeline import ...
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROOT = PROJECT_ROOT
```

```python
# packages/core/jstudy_core/pipeline.py
PROJECT_ROOT = Path(__file__).resolve().parents[3]
root = PROJECT_ROOT
```

Add shims:

```python
# web_mvp.py
from apps.api.jstudy_api.app import INDEX_HTML, app, create_app

__all__ = ["INDEX_HTML", "app", "create_app"]
```

```python
# mvp_runner.py
from packages.core.jstudy_core.pipeline import *  # noqa: F401,F403
from packages.core.jstudy_core.pipeline import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 4: Run focused test to verify it passes**

Run: `python -m unittest discover -s tests -p test_project_structure.py -v`

Expected: PASS.

### Task 2: Preserve Existing Test Contracts

**Files:**
- Modify: `tests/test_mvp_runner.py`
- Modify: `tests/test_web_mvp.py`

- [x] **Step 1: Update tests to canonical imports**

Use canonical imports for implementation tests:

```python
from packages.core.jstudy_core.pipeline import ...
from apps.api.jstudy_api.app import INDEX_HTML, create_app
```

Update patch targets from `mvp_runner.*` to `packages.core.jstudy_core.pipeline.*`.

- [x] **Step 2: Run full backend test suite**

Run:

```powershell
python -m py_compile web_mvp.py mvp_runner.py apps/api/jstudy_api/app.py packages/core/jstudy_core/pipeline.py
python -m unittest discover -s tests -v
```

Expected: 21 tests pass.

### Task 3: Add Explicit Backend Dependencies

**Files:**
- Create: `requirements.txt`
- Modify: `README.md`
- Modify: `docs/architecture/overview.md`

- [x] **Step 1: Add dependency file**

```text
fastapi
uvicorn
python-multipart
PyMuPDF
httpx
```

- [x] **Step 2: Update docs with new backend paths**

Update local run examples to include both compatibility and canonical commands:

```powershell
python -m uvicorn web_mvp:app --host 127.0.0.1 --port 8765
python -m uvicorn apps.api.jstudy_api.app:app --host 127.0.0.1 --port 8765
```

- [x] **Step 3: Run final verification**

Run:

```powershell
python -m py_compile web_mvp.py mvp_runner.py apps/api/jstudy_api/app.py packages/core/jstudy_core/pipeline.py
python -m unittest discover -s tests -v
git status -sb
```

Expected: compile passes, 21 tests pass, only intended files are changed.
