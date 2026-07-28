# J-Study Multi-Agent Product Build

This folder defines the lightweight multi-agent workflow for J-Study.

J-Study uses this thread as the product and architecture discussion thread. Code editing should be delegated to a separate Code Agent thread only after the discussion has converged into a scoped task card with explicit checkpoints and verification.

## Roles

- Supervisor Thread: product discussion, architecture decisions, task-card writing, Code Agent review, final verdict.
- Code Agent Thread: implementation only, scoped to one task card at a time.

## Current Threads

See `coordination/session_registry.md`.

## Operating Rule

Do not ask a Code Agent to "improve J-Study" broadly. Every delegated task must have:

- a concrete goal
- allowed files or modules
- explicit out-of-scope items
- verification requirements
- required report-back format

## Intended Use

Use this workflow first to onboard a Code Agent into the J-Study product and repo context. After the Code Agent registers its session id and reports back, use later task cards to safely absorb selected work from candidate branches such as:

- `feat/multi-domain-modes`
- `feat/frontend-polish-katex`
- `feat/sectional-generation`

The first task card is not an implementation task. It is `task_cards/0001-code-agent-onboarding.md`.

After onboarding, the current implementation direction is `task_cards/0002-fastapi-first-mvp-merge.md`: a staged FastAPI-first absorption of candidate branch work, followed by frontend-ready reader and contract foundations. Even for larger task cards, the Code Agent should execute in reviewable phases and must not merge whole candidate branches blindly.
