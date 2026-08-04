# Scenario and Parser Profile Router Design

## Goal

Add a routing layer that lets J-Study support multiple learning scenarios and user-selectable parser profiles. The parser decision should no longer depend on automatic PDF difficulty scoring. Users eventually choose a clear product option, while admins control which options are visible.

## Current Decision

We will use the combined product model:

- `scenario_id`: the learning scene, such as Medicine or General.
- `parser_profile_id`: the parsing experience, such as Fast or Quality.

Initial pilot behavior:

- `fast` uses PyMuPDF.
- `quality` uses MinerU.
- `fast` is the public default.
- `quality` is hidden from normal users at first and reserved for admin testing.
- A future pricing layer can make `quality` paid-only without changing the parser interface.

## Assumptions

- Users should understand parser choice as a product option, not as an implementation detail.
- Automatic PDF difficulty detection is too early for the MVP and may make behavior hard to explain.
- Admin settings remain the source of truth for default scenario, enabled scenarios, parser profiles, parser visibility, and retention settings.
- Medicine is the first scenario because it fits the pilot, but the system must not hard-code medicine-only assumptions into the pipeline.
- PyMuPDF remains the default parser for lightweight deployment.
- MinerU is optional and should not be required for the first server deployment.
- Current uploads are local files under `JSTUDY_JOBS_DIR`. This is acceptable for the pilot only if retention is enabled before real usage grows.

## Recommended Approach

Use two separate routers:

- `ScenarioRouter`: resolves the effective learning scenario from user input or the admin default.
- `ParserProfileRouter`: resolves the effective parser profile from user input or the admin default.

These routers should remain independent. A medicine scenario does not imply MinerU, and a high-quality parser profile does not imply a specific subject.

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

## Parser Profile Routing

The frontend generation form should send an optional `parser_profile_id`. If it is missing, the backend uses the admin-configured default parser profile.

Each parser profile should define:

- `id`
- `display_name`
- `backend`: `pymupdf` or `mineru`
- `enabled`
- `visible_to_users`
- `requires_admin`
- `tier`: `free`, `paid`, or `internal`
- `estimated_wait`: short user-facing wait description

The MVP should ship with:

- `fast`: PyMuPDF, enabled, visible, free.
- `quality`: MinerU, hidden, admin-only, internal, disabled until MinerU is configured.

The public UI should only show enabled profiles where `visible_to_users` is true and `requires_admin` is false. In the initial pilot this means ordinary users only see or implicitly use `fast`.

Admins can enable `quality` after MinerU is configured, keep it hidden while testing through admin-only workflows, and later make it visible behind an account tier when pricing is ready.

## Admin Settings

Extend `content_pack.json` with scenario definitions:

- `default_scenario_id`
- `scenarios`

Extend `runtime.json` with parser profile definitions:

- `parser_profiles.default_profile_id`
- `parser_profiles.profiles`

Keep existing parser settings for backend-specific configuration such as MinerU endpoint and token.

## Job Trace

Every generation job should persist routing metadata in the job trace:

- requested scenario
- resolved scenario
- content pack id
- prompt profile
- RAG profile
- requested parser profile
- resolved parser profile
- parser backend
- whether the parser profile was public, admin-only, or hidden

This gives us enough data to review product usage and parser quality before adding pricing or more advanced parser workflows.

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
- Unknown parser profile: return 400 with the invalid `parser_profile_id`.
- Disabled parser profile: return 400 and ask the user to choose another parser profile.
- Hidden or admin-only parser profile requested by a normal user: return 403.
- MinerU profile selected but MinerU is not configured: return 503 and tell the user to use fast parsing for now.
- PyMuPDF extracts no usable text: fail the job with a clear parser error. Do not silently retry MinerU unless the user selected the MinerU-backed profile.
- Cleanup failure should not block new jobs, but it should be logged.

## Testing

Add focused tests for:

- default scenario resolution from admin settings
- user-selected scenario overriding the admin default
- disabled or unknown scenarios being rejected
- default parser profile resolution to `fast`
- user-selected public parser profile overriding the default
- hidden or admin-only `quality` being rejected for normal users
- admin context being allowed to resolve hidden `quality`
- MinerU-backed profile failing clearly when MinerU is not configured
- generation job trace including scenario and parser profile metadata
- retention configuration preserving current local storage behavior while deleting expired finished jobs

## Non-Goals

- Do not implement automatic PDF difficulty scoring in this step.
- Do not implement automatic subject detection in this step.
- Do not add a database only for routing.
- Do not implement payments in this step.
- Do not require MinerU for the lightweight server deployment.
