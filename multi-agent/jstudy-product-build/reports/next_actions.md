# Next Actions

## Immediate

1. Treat `docs/architecture/refactor-blueprint.md` as the controlling
   contract-first refactor decision.
2. Execute
   `multi-agent/jstudy-product-build/task_cards/0005-refactor-checkpoint-mineru-foundation.md`.
3. Supervisor must independently verify the checkpoint contents, mocked MinerU
   transport, ZIP safety, normalized page mapping, and full regression suites.
4. After task 0005 passes, write task 0006 for the actual MinerU pipeline switch
   and public parser-profile removal.
5. Keep PostgreSQL job migration, separate worker, frontend contract update, and
   Tencent production-like deployment as subsequent independently gated phases.
6. Before public deployment, add course-outline upload boundaries: PDF count,
   total upload bytes, outline size, MIME/magic validation, parse timeout,
   queue/concurrency limit, and cleanup.

## Supervisor Verification Policy

Do not treat Code Agent verification as final acceptance by default.

For onboarding tasks, Supervisor should at minimum:

- confirm the Code Agent thread id is registered
- confirm no business code was modified
- check that the report reflects the required J-Study architecture docs
- issue a verdict in `reports/supervisor_review.md`

For task `0002`, FastAPI product-path changes are explicitly in scope, but only when they serve the official `POST /api/generate` flow, job artifacts, evidence/PDF preview contracts, reader behavior, or stable section/package foundations. Whole-branch merges, unrelated API expansion, tracked runtime data under `data/`, and final frontend design remain out of scope.

For task `0004`, Supervisor should not accept the work based only on build success or screenshots. Acceptance requires review of the real route structure, API type ownership, module boundaries, auth cookie behavior, source-id based citation flow, and real-browser checks at mobile/tablet/desktop widths.

For task `0005`, the checkpoint commit is part of the safety boundary. Supervisor
must compare its file list against the inventory before reviewing new MinerU
code. A passing mocked transport test is not a live-provider acceptance test;
the first token-backed smoke run requires a separate explicit instruction and a
non-sensitive fixture.
