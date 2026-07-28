# Workflow

## Purpose

This workflow keeps J-Study product discussion separate from code execution.

The Supervisor thread discusses and decides. The Code Agent thread edits code from a scoped task card with explicit checkpoints and verification.

## Steps

1. Human and Supervisor discuss the product or engineering problem.
2. Supervisor writes or updates a task card.
3. Supervisor sends the task card to the Code Agent.
4. Code Agent executes only that task. The task may be onboarding, read-only review, or code editing.
5. Code Agent runs required verification or reports why verification is blocked.
6. Code Agent reports back to the Supervisor thread.
7. Supervisor performs a review gate.
8. Supervisor returns a verdict: `PASS`, `PASS_WITH_LIMITATIONS`, `REVISE`, or `REJECT`.
9. Human decides whether to merge, deploy, or assign another task.

## Mandatory Report-Back Rule

The next Supervisor step is blocked until the Code Agent reports back.

The report must include:

- source Code Agent thread id
- task card path
- changed files
- behavior changed
- verification run
- verification failures or blockers
- known risks
- requested Supervisor action

## Supervisor Verification Gate

Code Agent verification is necessary but not sufficient.

Supervisor review should be proportional to risk:

| Change Type | Supervisor Action |
| --- | --- |
| Onboarding or read-only review | Confirm registration, required files read, and no business code modified. |
| Documentation only | Inspect diff and placement. |
| Narrow UI copy/style | Inspect diff; run static checks when cheap. |
| Narrow API or backend behavior | Inspect diff; rerun focused tests where available. |
| Auth, permissions, uploads, storage, data ownership, injection, deployment | Independently rerun focused tests or manual checks before `PASS`. |
| LLM/RAG generation pipeline | Inspect trace behavior and rerun focused tests or sample dry-run where practical. |

If the Supervisor cannot independently verify a risky change, the verdict should be `PASS_WITH_LIMITATIONS` or `REVISE`.

## Scope Control

Each task card should be small enough to review in one pass.

If a task mixes independent concerns, split it before assignment.
