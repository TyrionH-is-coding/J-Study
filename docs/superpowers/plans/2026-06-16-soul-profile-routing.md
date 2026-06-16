# Soul Profile Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lightweight soul profile library so user-selected scenarios can route generation to different subject-specific soul files while admins control which scenarios are visible.

**Architecture:** Reuse the existing `content_pack.json` and `scenario.prompt_profile` fields. Add a normalized `soul_profiles` list to content-pack settings, resolve the selected scenario's soul profile during `/api/generate`, and keep `JSTUDY_SOUL_PATH` as a compatibility fallback for the default active pack. Placeholder profiles stay disabled through their scenarios until an admin supplies real soul content.

**Tech Stack:** Python 3.12, FastAPI, stdlib pathlib, existing unittest/TestClient suite, JSON-backed admin settings.

---

## Files

- Modify `packages/core/jstudy_core/admin_settings.py`: add default blank soul profiles and normalize `soul_profiles`.
- Modify `packages/core/jstudy_core/scenario_router.py`: resolve scenario soul profile metadata.
- Modify `apps/api/jstudy_api/app.py`: store selected content paths on each job and pass scenario-specific `soul_path` to the runner.
- Modify `tests/test_admin_settings.py`: verify default soul profiles and disabled placeholder scenarios.
- Modify `tests/test_scenario_router.py`: verify prompt profile resolution.
- Modify `tests/test_web_mvp.py`: verify `/api/generate` uses the selected scenario soul path.
- Update `README.md` and `docs/architecture/overview.md`: document the soul profile library.

## Tasks

### Task 1: Add Soul Profile Defaults

- [x] Write a failing test in `tests/test_admin_settings.py` asserting default `content_pack` has `soul_profiles` for `medicine-default`, `general-blank`, `engineering-blank`, and `law-blank`, and that placeholder scenarios are disabled.
- [x] Run `python -m unittest tests.test_admin_settings.AdminSettingsTest.test_content_pack_defaults_include_soul_profiles -v` and confirm it fails because `soul_profiles` is missing.
- [x] Add `_normalize_soul_profiles()` and include `soul_profiles` in `_content_pack_default()` and `_normalize_content_pack()`.
- [x] Re-run the focused admin settings test and confirm it passes.

### Task 2: Resolve Scenario Soul Profiles

- [x] Write a failing test in `tests/test_scenario_router.py` asserting `resolve_scenario()` returns the matching `soul_profile` for a selected scenario's `prompt_profile`.
- [x] Run `python -m unittest tests.test_scenario_router.ScenarioRouterTest.test_resolves_prompt_profile_to_soul_profile -v` and confirm it fails because `ScenarioResolution` has no `soul_profile`.
- [x] Extend `ScenarioResolution` with `soul_profile` and have `resolve_scenario()` match `scenario.prompt_profile` against `content_config.soul_profiles`.
- [x] Re-run the focused scenario router test and confirm it passes.

### Task 3: Route Generation by Selected Soul Profile

- [x] Write a failing test in `tests/test_web_mvp.py` asserting `/api/generate` with `scenario_id=general-default` passes the general soul path to the runner.
- [x] Run `python -m unittest tests.test_web_mvp.WebMvpTest.test_generate_uses_selected_scenario_soul_profile -v` and confirm it fails because generation still uses `runtime.soul_path`.
- [x] Add small path-resolution helpers in `apps/api/jstudy_api/app.py` and store `soul_path` / `mnemonics_path` in job metadata when the job is created.
- [x] Update `run_job()` to pass those stored paths into the runner.
- [x] Re-run the focused web test and confirm it passes.

### Task 4: Documentation and Regression

- [x] Update README and architecture docs to describe `scenario_id -> prompt_profile -> soul_profile -> soul_path`.
- [x] Run `python -m unittest tests.test_admin_settings tests.test_scenario_router tests.test_web_mvp.WebMvpTest.test_generate_uses_default_scenario_and_fast_parser_profile tests.test_web_mvp.WebMvpTest.test_generate_uses_selected_scenario_soul_profile -v`.
- [x] Run `python -m py_compile apps/api/jstudy_api/app.py packages/core/jstudy_core/admin_settings.py packages/core/jstudy_core/scenario_router.py`.
- [x] Run `git diff --check`.
- [ ] Commit with `feat: route generation by soul profile`.

## Self-Review

- Spec coverage: user-selected scenario drives soul profile selection; admin visibility remains scenario `enabled`; placeholder profiles exist but disabled by default; no database change.
- Placeholder scan: no implementation placeholder is required by this plan; blank profiles are explicit product placeholders and are disabled.
- Type consistency: `soul_profiles`, `soul_profile`, `prompt_profile`, `soul_path`, and `content_pack_id` are used consistently.
