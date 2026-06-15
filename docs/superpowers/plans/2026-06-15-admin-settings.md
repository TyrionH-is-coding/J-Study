# Admin Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an admin-only backend settings page and JSON-backed runtime configuration for model, RAG, search, parser, and content-pack management.

**Architecture:** Add a small `AdminSettingsService` that owns JSON files under `data/settings/`, then make `RuntimeSettings` resolve from that service while preserving environment overrides. Add FastAPI admin endpoints and a backend-rendered HTML page.

**Tech Stack:** Python 3.12, FastAPI, stdlib JSON/pathlib, existing unittest/TestClient suite, backend-served HTML/CSS/JS.

---

## Files

- Create `packages/core/jstudy_core/admin_settings.py`: JSON defaults, normalization, redaction, token check helpers, knowledge snippet rendering.
- Modify `packages/core/jstudy_core/settings.py`: read JSON-backed defaults and expose parser/RAG/content fields.
- Modify `packages/core/jstudy_core/pipeline.py`: accept `rag_config` generated from runtime settings and consume future knowledge snippet JSON rendering through the existing `mnemonics_path` compatibility contract.
- Modify `apps/api/jstudy_api/app.py`: add admin settings API routes and pass runtime RAG settings to jobs.
- Modify `apps/api/jstudy_api/ui.py`: keep user MVP page unchanged.
- Create `apps/api/jstudy_api/admin_ui.py`: backend-served admin settings page.
- Add tests in `tests/test_admin_settings.py` and focused additions to `tests/test_settings.py` / `tests/test_web_mvp.py`.
- Update `README.md` and `docs/architecture/overview.md`.

## Tasks

### Task 1: JSON Settings Service

- [ ] Write failing tests in `tests/test_admin_settings.py` for default creation, redacted public payloads, update persistence, and knowledge snippet JSON rendering.
- [ ] Run `python -m unittest tests.test_admin_settings -v` and confirm failures are caused by missing `admin_settings.py`.
- [ ] Implement `AdminSettingsService` with defaults for model catalog, runtime settings, content pack, and knowledge snippets.
- [ ] Re-run `python -m unittest tests.test_admin_settings -v` and confirm it passes.

### Task 2: Runtime Resolution

- [ ] Add failing tests showing `RuntimeSettings.from_env(root)` reads JSON defaults when env vars are absent and env vars still override JSON.
- [ ] Run `python -m unittest tests.test_settings -v` and confirm the new tests fail.
- [ ] Extend `RuntimeSettings` with `admin_settings_dir`, `rag_config`, `parser_config`, `content_pack`, and resolved `chat_model`, `embed_model`, `api_key_path` from the catalog.
- [ ] Re-run `python -m unittest tests.test_settings -v`.

### Task 3: Admin API and Page

- [ ] Add failing API tests for `GET /admin/settings`, `GET /api/admin/settings`, `PUT /api/admin/settings`, token protection, and redacted API keys.
- [ ] Run `python -m unittest tests.test_web_mvp -v` and confirm failures are expected.
- [ ] Add `admin_ui.py` and FastAPI routes in `app.py`.
- [ ] Re-run `python -m unittest tests.test_web_mvp -v`.

### Task 4: Job Runtime Integration

- [ ] Add failing test that `/api/generate` passes configured RAG values from admin settings into the runner.
- [ ] Run the focused test and confirm failure.
- [ ] Update `run_job` to pass `runtime.rag_config`.
- [ ] Re-run the focused test.

### Task 5: Documentation and Full Verification

- [ ] Update README and architecture docs with admin settings path, token, and deployment mount notes.
- [ ] Run `python -m py_compile web_mvp.py mvp_runner.py apps/api/jstudy_api/app.py apps/api/jstudy_api/ui.py apps/api/jstudy_api/admin_ui.py packages/core/jstudy_core/*.py`.
- [ ] Run `python -m unittest discover -s tests -v`.
- [ ] Run `docker compose -f deploy\docker-compose\api.compose.yml config`.
- [ ] Run `git diff --check`.
- [ ] Commit and push only tracked project changes, leaving untracked `images/` untouched.
