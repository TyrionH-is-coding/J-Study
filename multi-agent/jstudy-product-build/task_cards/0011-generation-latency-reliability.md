# Task 0011: Generation Latency And Reliability

## Supervisor

- Product/Supervisor source thread: `019ed023-8e41-7ad0-8117-6246b8ffa0bb`
- Dispatching/verification thread: `019fa956-f165-76b0-b49d-9462d2f52328`
- Assigned Code Agent: `019efec4-1e17-7443-8496-c1fea5d6bcb5`

## Required Baseline

- Repository: `D:\大二下\deep tutor\J-Study`
- Branch: `feature/backend-frontend-mvp`
- Required start SHA: the commit containing this task card, design and plan
- Previous pushed checkpoint before this task: `925f815`
- Start PowerShell sessions with:

```powershell
. "$env:USERPROFILE\.codex\scripts\Enter-CodexUtf8.ps1"
```

Record exact start SHA and protected status before edits. Do not reset, clean,
rebase, merge or overwrite concurrent work.

## Product Finding

The 2026-08-03 Tencent staging vertical test completed a six-page Job in
57.1 seconds. Server-side timing showed about 6.6 seconds in MinerU and
44.5 seconds in six serial section-generation calls.

The integration path passed, but the product latency gate failed. This task
must fix the serial generation bottleneck without weakening content contracts.

## Goal

Implement bounded, order-preserving concurrency for independent Learning Unit
generation, expose safe per-section timing metrics, and reduce redundant output
instructions while preserving all current sequence-first and artifact
integrity contracts.

## Authoritative Documents

1. `docs/superpowers/specs/2026-08-04-generation-latency-design.md`
2. `docs/superpowers/plans/2026-08-04-generation-latency-reliability.md`
3. `docs/architecture/overview.md`
4. `docs/product/service-modes.md`

The design and implementation plan are binding. If current code contradicts
them, stop and report the contradiction before broadening scope.

## Required Method

- Use test-driven development.
- Execute the authoritative plan task by task.
- Make focused Chinese commits after each phase.
- Preserve existing public API and persistence semantics.
- Do not use elapsed-time sleeps as the primary concurrency proof; use Events,
  Barriers or equivalent deterministic synchronization.
- Run an independent read-only review before requesting a verdict.

## Required Implementation

### Phase 0: Baseline

- Record branch, exact SHA and protected status.
- Run the existing backend suite before changes.
- Confirm the current serial loop in `_run_sequence_first()`.

### Phase 1: Bounded Scheduler

- Add a focused scheduling module under
  `packages/core/jstudy_core/materials/`.
- Keep one existing model call per Learning Unit.
- Enforce `1..4` concurrency with default `3`.
- Preserve final `MaterialSection.order` regardless of completion order.
- Propagate provider exceptions to the Worker.
- Cancel work that has not started and wait for running calls to settle.

### Phase 2: Frozen Settings

- Add `JSTUDY_GENERATION_MAX_CONCURRENCY`.
- Resolve it once in the claim-specific immutable `RuntimeSettings`.
- Pass it to the selected runner.
- Add Worker Compose pass-through and `.env.example`.
- Do not add an admin UI or database column.

### Phase 3: Pipeline And Metrics

- Replace only the sequence-first serial generation loop.
- Do not modify the frozen Manifest, Learning Map or Coverage Ledger.
- Do not change Package v2, evidence, citation or section identity.
- Add `generation_metrics` to the private trace:
  total duration, configured concurrency, section count, section id/order,
  section duration and final status.
- Never emit prompt, response, evidence content, keys or signed URLs.
- Add the narrow anti-redundancy prompt rule from the design.

### Phase 4: Failure And Regression Coverage

- Prove the active-call cap.
- Prove deterministic final ordering.
- Prove serial fallback with value `1`.
- Prove provider exceptions do not publish partial artifacts or completion.
- Prove timing metadata is safe and bounded.
- Keep all backend and frontend regressions green.

### Phase 5: Documentation And Report

- Document configuration, rollback and Worker-replica multiplication.
- Record that live performance remains a Supervisor gate.
- Produce the required Task 0011 report.

## Allowed Scope

- `.env.example`
- `deploy/docker-compose/api.compose.yml`
- `packages/core/jstudy_core/settings.py`
- `packages/core/jstudy_core/materials/**`
- `packages/core/jstudy_core/pipeline.py`
- `packages/core/jstudy_core/job_system/worker.py`
- directly relevant tests under `tests/`
- `README.md`
- `docs/architecture/overview.md`
- `docs/deployment/server-runbook.md`
- `docs/roadmap.md`
- `multi-agent/jstudy-product-build/reports/0011-generation-latency-reliability-report.md`

If another file is genuinely required, stop and explain why before editing it.

## Forbidden Scope

- public FastAPI route or request/response changes
- database models, migrations or repository schema
- Manifest, Learning Map, Coverage Ledger or Material Package schema changes
- MinerU behavior or fallback
- retrieval, evidence-selection or citation policy changes
- multi-section single-request generation
- progressive section publication
- Generation Fingerprint or cross-retry cache
- LLM/Embedding credential separation
- frontend product implementation
- HTML/PDF export
- Tencent Cloud, Cloudflare, Nginx, DNS or live provider mutation
- real credential files, local/server `.env`, runtime `data/`, uploads or outputs

Protected workspace content:

- `docs/deployment/tencent-staging-2026-08-03.md`
- `docs/reviews/full-staging-verification-2026-08-03.md`
- `multi-agent/jstudy-product-build/reports/supervisor_review.md`
- `.superpowers/`
- `frontend/`
- `game/`
- `images/`
- `outline_mode/`
- `scripts/`

## Acceptance Criteria

1. Six deterministic blocking fake calls demonstrate exactly three active
   calls with default configuration.
2. Active calls never exceed the configured cap.
3. Completion order cannot alter final section order.
4. Configuration `1` preserves serial behavior.
5. Invalid values outside `1..4` fail closed.
6. Provider exceptions retain the existing Worker retry/permanent behavior and
   cannot publish partial public artifacts, sections or completion.
7. Trace metrics contain no document content or credentials.
8. Existing sequence-first validation and artifact integrity remain unchanged.
9. Full backend, frontend and Compose regression gates pass.
10. The report does not claim the product latency target passed without a real
    Supervisor staging rerun.

## Post-Merge Supervisor Performance Gate

After a code verdict, the Supervisor will run the same six-page DeepSeek V4
Flash staging sample three times:

- median created-to-completed no more than 25 seconds;
- no individual run more than 35 seconds;
- 6/6 generated sections;
- manual content score at least 85/100;
- all persisted artifact hashes match.

Failure of this gate means the performance task remains incomplete even if all
deterministic tests pass.

## Required Verification

```powershell
python -m compileall -q apps packages
python -m unittest discover -s tests -v
Push-Location apps/web
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
Pop-Location
docker compose -f deploy/docker-compose/api.compose.yml config --services
git diff --check
git status --short
```

## Required Report

Return:

1. exact branch, start SHA, final SHA and phase commits;
2. focused RED/GREEN evidence;
3. deterministic proof of cap, order and serial fallback;
4. exact changed files;
5. full backend/frontend/Compose verification output and counts;
6. failure atomicity and safe timing-metadata evidence;
7. residual risks, including lack of live provider/staging timing;
8. confirmation that no credential or remote system was touched;
9. requested Supervisor verdict, no higher than `PASS_WITH_LIMITATIONS` until
   the real staging performance gate passes.
