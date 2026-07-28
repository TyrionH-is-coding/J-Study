# Task Card: Code Agent Onboarding and Architecture Read

## Supervisor Thread

`019ed023-8e41-7ad0-8117-6246b8ffa0bb`

## Goal

Register the Code Agent session/thread id and build a shared understanding of J-Study's business architecture before any code editing task is assigned.

## Context

J-Study's backend foundation is mostly in place for the current pilot. The next major product phase is frontend construction and frontend-backend integration.

This first task is not an implementation task. It is an onboarding and alignment task so the Code Agent understands the product, repo boundaries, and current priorities before editing code.

## Required First Step

The Code Agent must identify its own session/thread id first.

Preferred method:

```text
/status
```

Then update:

`multi-agent/jstudy-product-build/coordination/session_registry.md`

Set the `Code Agent` row from `unassigned` to the actual Code Agent thread id and mark status as `active`.

If the environment does not support `/status` or direct file editing, the Code Agent must report its thread id in the completion report and ask the Supervisor to register it.

## Files to Read

Read these files before reporting:

- `README.md`
- `docs/product/vision.md`
- `docs/architecture/overview.md`
- `docs/roadmap.md`
- `docs/development/standards.md`
- `docs/development/git-workflow.md`
- `docs/reviews/collaborator-deployment-review-2026-06-16.md`
- `multi-agent/jstudy-product-build/README.md`
- `multi-agent/jstudy-product-build/agents/code-agent.md`
- `multi-agent/jstudy-product-build/coordination/workflow.md`
- `multi-agent/jstudy-product-build/coordination/output_contract.md`
- `multi-agent/jstudy-product-build/shared/project_context.md`
- `multi-agent/jstudy-product-build/shared/repo_rules.md`

The Code Agent may also inspect source files in read-only mode to understand boundaries:

- `apps/api/jstudy_api/app.py`
- `apps/api/jstudy_api/ui.py`
- `packages/core/jstudy_core/pipeline.py`
- `packages/core/jstudy_core/admin_settings.py`
- `packages/domains/medicine.py`

## Allowed Scope

The Code Agent may edit only:

- `multi-agent/jstudy-product-build/coordination/session_registry.md`

Only if needed, the Code Agent may add a short onboarding note under:

- `multi-agent/jstudy-product-build/reports/`

## Out of Scope

Do not modify:

- API routes
- frontend UI files
- backend pipeline code
- tests
- deployment files
- candidate branch code
- soul/profile/content-pack files

Do not implement export, history, multi-file upload, generation modes, or frontend features in this task.

## Required Report

Report back to Supervisor thread `019ed023-8e41-7ad0-8117-6246b8ffa0bb` in Chinese using `coordination/output_contract.md`.

The report must include:

1. Registered Code Agent thread id.
2. Understanding of J-Study's current product stage.
3. Understanding of the current backend state.
4. Why the next phase is frontend construction rather than broad backend expansion.
5. Key frontend-facing backend contracts already present.
6. Risks or unclear areas before frontend work starts.
7. Recommended first real implementation task, but without doing it.

## Verification

No code tests are required.

Verification for this task is:

- `session_registry.md` contains the Code Agent thread id, or the report explicitly says registration could not be performed.
- The report demonstrates the Code Agent has read the required docs.
- No business code files were modified.

## Suggested First Prompt to Code Agent

```text
You are the J-Study Code Agent.

First, identify your own Codex session/thread id. Use `/status` if available.

Then register it in:
multi-agent/jstudy-product-build/coordination/session_registry.md
on the Code Agent row.

After that, read the task card:
multi-agent/jstudy-product-build/task_cards/0001-code-agent-onboarding.md

This is an onboarding task only. Do not edit J-Study API, frontend, pipeline, tests, deployment, soul, content-pack, or candidate branch code.

J-Study backend work is mostly ready for the current pilot. The next product phase is frontend construction and frontend-backend integration. Your job in this first round is to understand the business architecture and report back to Supervisor thread 019ed023-8e41-7ad0-8117-6246b8ffa0bb.

Report in Chinese. Keep paths, commands, API routes, and identifiers in English where useful.
```
