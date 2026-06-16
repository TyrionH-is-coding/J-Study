# Invite Required Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deployment-time switch that allows small pilot testing without invite codes while keeping invite-gated registration as the default.

**Architecture:** Keep `AuthService` as the single place that applies invite validation. Add `RuntimeSettings.invite_required`, read from `JSTUDY_INVITE_REQUIRED`, and pass it into `AuthService`. The temporary built-in UI should make the invite input optional because the backend remains authoritative.

**Tech Stack:** Python 3.12, FastAPI, SQLModel auth service, stdlib unittest, JSON-free environment settings.

---

## Files

- Modify `packages/core/jstudy_core/settings.py`: add `JSTUDY_INVITE_REQUIRED` and expose `RuntimeSettings.invite_required`.
- Modify `packages/core/jstudy_core/auth_service.py`: accept `invite_required` in the constructor and skip invite lookup/usage when false.
- Modify `apps/api/jstudy_api/app.py`: instantiate `AuthService(auth_engine, invite_required=runtime.invite_required)`.
- Modify `apps/api/jstudy_api/ui.py`: make the temporary invite-code input optional.
- Modify `tests/test_auth_service.py`: cover no-invite registration when disabled.
- Modify `tests/test_settings.py`: cover env parsing and default behavior.
- Modify `tests/test_web_mvp.py`: cover API registration without invite when disabled and the temporary UI optional field.
- Modify `.env.example`, `README.md`, `docs/deployment/server-runbook.md`, and `docs/security/backend-security-validation.md`: document the switch and deployment caution.

## Tasks

### Task 1: Settings Switch

- [x] Add failing tests in `tests/test_settings.py` asserting `invite_required` defaults to `True` and `JSTUDY_INVITE_REQUIRED=false` sets it to `False`.
- [x] Run `python -m unittest discover -s tests -p test_settings.py -v` and confirm the new assertions fail because `invite_required` does not exist.
- [x] Add `INVITE_REQUIRED_ENV = "JSTUDY_INVITE_REQUIRED"` and `invite_required: bool = True` to `RuntimeSettings`.
- [x] Populate `invite_required=env_bool(INVITE_REQUIRED_ENV, True)` in `RuntimeSettings.from_env`.
- [x] Re-run the focused settings tests and confirm they pass.

### Task 2: Auth Service Behavior

- [x] Add a failing test in `tests/test_auth_service.py` named `test_invite_can_be_disabled_for_small_pilot`.
- [x] The test should instantiate `AuthService(engine, invite_required=False)`, register without an invite code, and assert no invite uses exist.
- [x] Run `python -m unittest discover -s tests -p test_auth_service.py -v -k test_invite_can_be_disabled_for_small_pilot` and confirm it fails because `AuthService` has no `invite_required` parameter.
- [x] Update `AuthService.__init__` to accept `invite_required: bool = True`.
- [x] Update `register()` so it only requires, looks up, and records invite usage when `self.invite_required` is true.
- [x] Re-run `python -m unittest discover -s tests -p test_auth_service.py -v` and confirm existing invite behavior still passes.

### Task 3: API and Temporary UI

- [x] Add a failing API test in `tests/test_web_mvp.py` that creates `RuntimeSettings(invite_required=False)` and registers with no `invite_code`.
- [x] Add an assertion that `INDEX_HTML` does not contain `name="invite_code" type="text" autocomplete="off" required`.
- [x] Run the focused web tests and confirm they fail before implementation.
- [x] Pass `runtime.invite_required` into `AuthService` in `apps/api/jstudy_api/app.py`.
- [x] Remove `required` from the temporary invite-code input in `apps/api/jstudy_api/ui.py`.
- [x] Re-run `python -m unittest discover -s tests -p test_web_mvp.py -v -k invite` and confirm invite-related tests pass.

### Task 4: Documentation and Verification

- [x] Document `JSTUDY_INVITE_REQUIRED=false` in `.env.example`, `README.md`, `docs/deployment/server-runbook.md`, and `docs/security/backend-security-validation.md`.
- [x] Run `python -m unittest discover -s tests -v`.
- [x] Run `python -m py_compile apps/api/jstudy_api/app.py apps/api/jstudy_api/ui.py packages/core/jstudy_core/auth_service.py packages/core/jstudy_core/settings.py`.
- [x] Run `git diff --check`.
- [x] Commit with `feat: add invite requirement toggle` and push the current PR branch.

## Self-Review

- Spec coverage: supports temporary open registration, preserves default invite requirement, keeps admin invite features.
- Placeholder scan: no placeholders.
- Type consistency: `invite_required` and `JSTUDY_INVITE_REQUIRED` are used consistently.
