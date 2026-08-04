# Next Actions

## Immediate

1. Treat both `docs/architecture/refactor-blueprint.md` and
   `docs/superpowers/specs/2026-07-31-courseware-synchronized-learning-design.md`
   as controlling product contracts.
2. Preserve the verified Task 0005 MinerU foundation, Task 0006 durable
   PostgreSQL/Worker foundation, and Task 0007 Material Package v2 foundation.
3. Execute Task 0008 for the real MinerU Worker switch, frozen Courseware
   Manifest, continuous learning units, sequence-first generation and coverage
   audit.
4. Supervisor must independently verify that PyMuPDF text extraction and Top-K
   hybrid retrieval no longer control complete-material generation.
5. After Task 0008 passes, add the editable courseware draft/Organizer API and
   formal frontend organizer.
6. Keep HTML rendering, Alembic, quota/BYOK, and Tencent production-like
   deployment as subsequent independently gated phases.

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
