# Generation Latency And Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace serial Learning Unit generation with bounded, order-preserving concurrency and publish safe per-section timing metrics without changing J-Study content contracts.

**Architecture:** Add a focused scheduler under `materials/` that accepts immutable section requests, invokes the existing section generator with a bounded thread pool, and returns ordered sections plus timing metadata. Pass one frozen concurrency setting from the Worker claim into the sequence-first runner, then write only safe metrics into the existing private trace artifact.

**Tech Stack:** Python 3, `concurrent.futures.ThreadPoolExecutor`, dataclasses, `time.perf_counter`, SQLModel Worker integration, `unittest`.

---

### Task 1: Freeze The Baseline And Add Scheduler RED Tests

**Files:**
- Create: `tests/test_material_scheduling.py`
- Read: `packages/core/jstudy_core/pipeline.py`
- Read: `packages/core/jstudy_core/materials/generation.py`

- [ ] **Step 1: Record the exact baseline**

Run:

```powershell
git status --short --branch
git rev-parse HEAD
python -m unittest discover -s tests -v
```

Expected: existing protected dirty paths remain untouched and the backend suite
passes before implementation.

- [ ] **Step 2: Write a concurrency-cap RED test**

Create a thread-safe fake generator that increments an active counter, signals
when three calls are active, blocks on an event, and records the maximum active
count. Start `generate_sections_bounded()` from a test thread with six requests
and `max_concurrency=3`.

Assert:

```python
self.assertTrue(three_started.wait(timeout=2))
self.assertEqual(observed_max_active, 3)
release.set()
self.assertEqual([item.order for item in result.sections], [1, 2, 3, 4, 5, 6])
```

- [ ] **Step 3: Write order and serial-mode RED tests**

Use different release events so calls finish in reverse order. Assert returned
sections remain in request order. With `max_concurrency=1`, assert the observed
maximum active count is exactly one.

- [ ] **Step 4: Write exception RED tests**

Make one fake call raise `RuntimeError("provider unavailable")`. Assert the same
exception escapes and no partial result object is returned.

- [ ] **Step 5: Run the RED tests**

Run:

```powershell
python -m unittest tests.test_material_scheduling -v
```

Expected: FAIL because the scheduling module does not exist.

- [ ] **Step 6: Commit the tests**

```powershell
git add tests/test_material_scheduling.py
git commit -m "测试：定义章节并发调度合同"
```

### Task 2: Implement The Bounded Scheduler

**Files:**
- Create: `packages/core/jstudy_core/materials/scheduling.py`
- Modify: `packages/core/jstudy_core/materials/__init__.py`
- Test: `tests/test_material_scheduling.py`

- [ ] **Step 1: Add immutable request and metrics models**

Define focused frozen dataclasses equivalent to:

```python
@dataclass(frozen=True)
class SectionGenerationRequest:
    section_id: str
    order: int
    title: str
    evidence: tuple[Mapping[str, Any], ...]
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class SectionTiming:
    section_id: str
    order: int
    status: str
    duration_ms: int


@dataclass(frozen=True)
class SectionGenerationResult:
    sections: tuple[MaterialSection, ...]
    total_duration_ms: int
    max_concurrency: int
    timings: tuple[SectionTiming, ...]
```

Keep API Key, model, base URL and Soul outside metrics and public
serialization.

- [ ] **Step 2: Implement one measured call**

Wrap the existing `SectionGenerator` with `time.perf_counter()` and return both
the generated section and its duration. Do not catch provider exceptions in
this wrapper.

- [ ] **Step 3: Implement bounded scheduling**

Validate `1 <= max_concurrency <= 4`. Submit requests to
`ThreadPoolExecutor(max_workers=min(max_concurrency, len(requests)))`. Store
future results by request order, not completion order.

On the first raised exception:

```python
for pending in futures:
    pending.cancel()
executor.shutdown(wait=True, cancel_futures=True)
raise
```

Ensure normal shutdown occurs exactly once and no background thread remains
after the function returns.

- [ ] **Step 4: Export the scheduling contract**

Export only the request/result types and `generate_sections_bounded` from
`packages/core/jstudy_core/materials/__init__.py`.

- [ ] **Step 5: Run focused tests**

```powershell
python -m unittest tests.test_material_scheduling -v
```

Expected: all scheduler tests pass without sleeps as the primary synchronization
mechanism.

- [ ] **Step 6: Commit**

```powershell
git add packages/core/jstudy_core/materials tests/test_material_scheduling.py
git commit -m "功能：增加有界章节并发调度"
```

### Task 3: Add The Frozen Runtime Setting

**Files:**
- Modify: `packages/core/jstudy_core/settings.py`
- Modify: `packages/core/jstudy_core/job_system/worker.py`
- Modify: `.env.example`
- Modify: `deploy/docker-compose/api.compose.yml`
- Test: `tests/test_settings.py`
- Test: `tests/test_deployment_files.py`
- Test: `tests/test_job_worker.py`

- [ ] **Step 1: Write settings RED tests**

Assert:

```python
self.assertEqual(settings.generation_max_concurrency, 3)
```

and environment values `1` and `4` are accepted while `0`, `5`, and
non-integers fail closed.

- [ ] **Step 2: Write Worker snapshot RED test**

Create a Worker with a settings snapshot containing
`generation_max_concurrency=2`. Assert the runner receives exactly `2`, and
changing the settings provider after claim does not alter that runner call.

- [ ] **Step 3: Implement the bounded setting**

Add:

```python
GENERATION_MAX_CONCURRENCY_ENV = "JSTUDY_GENERATION_MAX_CONCURRENCY"
DEFAULT_GENERATION_MAX_CONCURRENCY = 3
```

Add a small bounded integer parser and the frozen dataclass field. Do not add an
admin page or database column.

- [ ] **Step 4: Pass the snapshot into the runner**

Add `generation_max_concurrency` to the Worker runner kwargs built from the
claim-specific `RuntimeSettings`.

- [ ] **Step 5: Wire deployment configuration**

Add the variable with default `3` to `.env.example` and pass it through to the
Worker service in Compose. Do not change API ports, service names, data mounts
or provider precedence.

- [ ] **Step 6: Run focused tests**

```powershell
python -m unittest tests.test_settings tests.test_job_worker tests.test_deployment_files -v
```

- [ ] **Step 7: Commit**

```powershell
git add .env.example deploy/docker-compose/api.compose.yml packages/core/jstudy_core/settings.py packages/core/jstudy_core/job_system/worker.py tests/test_settings.py tests/test_job_worker.py tests/test_deployment_files.py
git commit -m "功能：配置生成并发上限"
```

### Task 4: Integrate Scheduling Into Sequence-First Generation

**Files:**
- Modify: `packages/core/jstudy_core/pipeline.py`
- Modify: `packages/core/jstudy_core/materials/generation.py`
- Test: `tests/test_mvp_runner.py`
- Test: `tests/test_job_worker.py`
- Test: `tests/test_material_generation.py`

- [ ] **Step 1: Write pipeline RED tests**

Inject a blocking fake `section_generator` into the sequence-first runner.
Assert six Learning Units reach three simultaneous calls when configured to
three, and the final package section order remains deterministic.

Assert the trace includes:

```python
{
    "max_concurrency": 3,
    "section_count": 6,
    "total_duration_ms": unittest.mock.ANY,
    "sections": [
        {
            "section_id": "unit-001",
            "order": 1,
            "status": "generated",
            "duration_ms": unittest.mock.ANY,
        }
    ],
}
```

- [ ] **Step 2: Build immutable generation requests**

In `_run_sequence_first()`, construct requests in
`learning_map.ordered_units()` order. Copy evidence records into immutable
tuples or read-only equivalents before dispatch so workers do not mutate shared
lists.

- [ ] **Step 3: Replace only the serial loop**

Call `generate_sections_bounded()` and use its ordered sections to build the
existing `MaterialPackageV2`. Do not change package identity, section identity,
evidence ids, source ids, title resolution or quality validation.

- [ ] **Step 4: Write safe timing metrics**

Serialize the scheduler result into `trace["generation_metrics"]`. Include only
section id, order, status, durations, count and concurrency. Do not include
evidence text, prompt, response JSON, API Key or signed URL.

- [ ] **Step 5: Tighten the anti-redundancy prompt**

Add one explicit instruction to `_messages()`:

```text
Do not fully repeat the same workflow or fact as prose, a list, and a table.
Choose the single clearest learning representation unless a second form adds
new information.
```

Keep all existing schema, citation and source-preservation instructions.

- [ ] **Step 6: Verify Worker failure atomicity**

Add a Worker regression where one concurrent provider call raises. Assert the
Job follows the existing retry/failure contract and no package, sections or
completed transition is committed.

- [ ] **Step 7: Run focused tests**

```powershell
python -m unittest tests.test_material_scheduling tests.test_material_generation tests.test_mvp_runner tests.test_job_worker -v
```

- [ ] **Step 8: Commit**

```powershell
git add packages/core/jstudy_core/pipeline.py packages/core/jstudy_core/materials/generation.py tests/test_material_generation.py tests/test_mvp_runner.py tests/test_job_worker.py
git commit -m "性能：并发生成独立学习章节"
```

### Task 5: Document And Verify

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture/overview.md`
- Modify: `docs/deployment/server-runbook.md`
- Modify: `docs/roadmap.md`
- Create: `multi-agent/jstudy-product-build/reports/0011-generation-latency-reliability-report.md`

- [ ] **Step 1: Document the operational contract**

Document the default `3`, legal range `1..4`, per-Job meaning, serial rollback
value `1`, and the fact that total concurrency multiplies with Worker replicas.

- [ ] **Step 2: Document the validation boundary**

State explicitly that deterministic tests prove scheduling behavior, but only
the Supervisor's real DeepSeek V4 Flash staging benchmark can pass the product
latency gate.

- [ ] **Step 3: Run complete verification**

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

Expected:

- all backend and frontend tests pass;
- Compose services remain `postgres`, `jstudy-api`, `jstudy-worker`;
- protected dirty/untracked paths remain unchanged;
- no secret, runtime data, upload or generated artifact is staged.

- [ ] **Step 4: Write the report**

Report exact start/final SHAs, phase commits, RED/GREEN evidence, test counts,
changed files, concurrency behavior, remaining limits, and a requested verdict.
Because live staging is forbidden in this task, request no more than
`PASS_WITH_LIMITATIONS`.

- [ ] **Step 5: Commit**

```powershell
git add README.md docs/architecture/overview.md docs/deployment/server-runbook.md docs/roadmap.md multi-agent/jstudy-product-build/reports/0011-generation-latency-reliability-report.md
git commit -m "文档：记录生成性能整改合同"
```
