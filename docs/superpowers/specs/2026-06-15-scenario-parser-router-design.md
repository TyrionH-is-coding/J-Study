# Scenario and Parser Router Design

## Goal

Add a routing layer that lets J-Study support multiple learning scenarios while choosing the document parser automatically. The first production-like behavior should stay lightweight: users can choose a scenario, admins control the default, and parser auto-routing starts with simple rules plus decision logging.

## Assumptions

- Users should see scenario choices such as Medicine or General, but should not need to understand parser internals.
- Admin settings remain the source of truth for default scenario, enabled scenarios, parser policy, and retention settings.
- Medicine is the first scenario because it fits the pilot, but the system must not hard-code medicine-only assumptions into the pipeline.
- PyMuPDF remains the default parser for lightweight deployment.
- MinerU is optional and should be selected only when the PDF appears complex and MinerU is configured as available.
- Current uploads are local files under `JSTUDY_JOBS_DIR`. This is acceptable for the pilot only if retention is enabled before real usage grows.

## Recommended Approach

Use two separate routers:

- `ScenarioRouter`: resolves the effective learning scenario from user input or the admin default.
- `ParserRouter`: inspects the uploaded PDF and decides whether to use PyMuPDF or MinerU.

These routers should remain independent. A medicine scenario does not always require MinerU, and a complex PDF is not always medicine.

## Scenario Routing

The frontend generation form should send an optional `scenario_id`. If it is missing, the backend uses the admin-configured default scenario.

Each scenario should define:

- `id`
- `display_name`
- `subject`
- `enabled`
- `content_pack_id`
- `prompt_profile`
- `rag_profile`
- `domain_rules`

The backend should reject disabled or unknown scenarios with a clear 400 response. The MVP should ship with:

- `medicine-default`
- `general-default`

The first version does not need automatic subject detection. Manual selection plus an admin default is enough for the pilot.

## Parser Routing

Parser routing should support these modes:

- `auto`: inspect the PDF and choose a parser.
- `force_pymupdf`: always use PyMuPDF.
- `force_mineru`: always use MinerU when available; otherwise fail or fallback based on policy.

The default should be `auto`.

The first auto policy should score lightweight signals:

- page count
- average extracted text length per page
- empty or near-empty page ratio
- image and drawing object density when available from PyMuPDF
- table-like text hints
- extraction quality after a small PyMuPDF sample

The router returns a `ParserDecision`:

- `selected_backend`
- `complexity_score`
- `reasons`
- `fallback`
- `mineru_available`

If the PDF is complex and MinerU is available, choose MinerU. If the PDF is complex but MinerU is unavailable, fallback to PyMuPDF and record the risk in the decision.

## Admin Settings

Extend `content_pack.json` with scenario definitions:

- `default_scenario_id`
- `scenarios`

Extend `runtime.json` with parser routing policy:

- `parser_router.mode`
- `parser_router.default_backend`
- `parser_router.mineru_enabled`
- `parser_router.fallback_to_pymupdf`
- `parser_router.thresholds`

Keep existing parser settings for backend-specific configuration such as MinerU endpoint and token.

## Job Trace

Every generation job should persist routing metadata in the job trace:

- requested scenario
- resolved scenario
- content pack id
- prompt profile
- RAG profile
- parser decision

This gives us enough data to review whether the routing policy is working before adding heavier automation.

## Upload Storage Policy

The current server stores uploaded PDFs locally because the citation panel needs the original PDF for page preview and page-level evidence jumps. That is correct for the MVP, but the default cleanup behavior should not be used for long-running public service.

Pilot deployment should use:

- local disk storage under `JSTUDY_JOBS_DIR`
- explicit upload size limit through `JSTUDY_MAX_PDF_BYTES`
- nonzero `JSTUDY_JOB_RETENTION_HOURS`, for example 72 or 168 hours
- cleanup of completed and failed job directories after the TTL

This means generated materials and PDF previews remain available for a short review window, but uploads do not accumulate forever.

When J-Study needs persistent user history, course libraries, or formal multi-user accounts, move uploaded PDFs and generated artifacts to object storage such as Tencent COS. The app should then keep metadata in a database and rely on object-storage lifecycle rules, quotas, and archival policies.

## Error Handling

- Unknown scenario: return 400 with the invalid `scenario_id`.
- Disabled scenario: return 400 and ask the user to choose another scenario.
- MinerU selected but unavailable: fallback to PyMuPDF only if `fallback_to_pymupdf` is enabled; otherwise fail fast with a clear runtime error.
- PyMuPDF extracts no usable text: mark the parser decision as poor quality and, in `auto` mode, retry with MinerU if available.
- Cleanup failure should not block new jobs, but it should be logged.

## Testing

Add focused tests for:

- default scenario resolution from admin settings
- user-selected scenario overriding the admin default
- disabled or unknown scenarios being rejected
- simple PDF choosing PyMuPDF
- sparse or complex PDF choosing MinerU when available
- complex PDF falling back to PyMuPDF when MinerU is unavailable and fallback is enabled
- generation job trace including scenario and parser decision metadata
- retention configuration preserving current local storage behavior while deleting expired finished jobs

## Non-Goals

- Do not implement automatic subject detection in this step.
- Do not add a database only for routing.
- Do not require MinerU for the lightweight server deployment.
- Do not build learning-based router thresholds before collecting real routing decisions.
