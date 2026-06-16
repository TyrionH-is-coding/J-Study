# Collaborator Deployment Review - 2026-06-16

## Scope

User request: inspect the collaborator GitHub PR and deployed backend at `https://jstudy.shuttlescope.org/`, then decide which changes are worth bringing into our current branch.

Decision after review: do not merge code yet. This report records what looks reusable, what should wait, and what should not be copied.

## Evidence Checked

- GitHub PR list: only PR #1 exists.
- PR #1 head branch: `feature/backend-frontend-mvp`.
- PR #1 head commit: `d3cffd6`, the same commit as our current local branch before this review.
- Deployed service health: `GET https://jstudy.shuttlescope.org/api/health` returned `{"status":"ok","service":"jstudy-api"}`.
- Deployed readiness without provider probe: ready.
- Deployed readiness with provider probe: degraded because SiliconFlow returned HTTP 401 for both chat and embedding.
- Deployed OpenAPI showed two contracts not present in our current branch:
  - `GET /api/jobs/{job_id}/export`
  - `POST /api/generate` accepts an optional `mode` form field.
- Deployed `/api/options` exposed `medicine-default`, `general-default`, and `engineering-default`.
- Deployed `/admin/settings` returned the admin page without an admin token in the inspected request.

Important finding: there is no separate external PR diff to cherry-pick. The visible GitHub PR is our own current feature branch against `main`. Differences observed on `jstudy.shuttlescope.org` appear to come from an independently deployed working tree or local runtime settings, not a separate GitHub PR branch.

## Recommended to Consider for Direct Inclusion

### 1. Markdown export endpoint

Observed behavior:

- Deployed OpenAPI includes `GET /api/jobs/{job_id}/export`.
- Deployed temporary UI points its download button to `/api/jobs/{job_id}/export`.

Why it is useful:

- It is small, backend-owned, and aligns with both current single-courseware mode and future material-package export.
- It does not require changing generation quality or prompt behavior.
- It gives the current temporary UI and future frontend a stable download contract.

Recommended implementation shape:

- Add `export_url` to `GET /api/jobs/{job_id}`.
- Add `GET /api/jobs/{job_id}/export`.
- Reuse existing owner checks and completed-output checks.
- Return the generated Markdown as an attachment with private cache headers.
- Add tests for auth ownership, response headers, and output content.

Risk:

- Low. This is the safest item to bring in.

### 2. Explicit generation-mode metadata, but not behavior yet

Observed behavior:

- Deployed OpenAPI adds `mode` to `POST /api/generate`.
- Deployed UI shows mode pills: summary, exam quick review, and rewrite.

Why it may be useful:

- The frontend will need a way to distinguish output styles later.
- Recording mode in job metadata can help frontend experiments and analytics.

Why not fully adopt now:

- The deployed mode pills appear to be UI-level affordances. There is no verified evidence that they change prompt rules or generation output.
- We have just separated service modes such as `single_courseware`, `batch_courseware`, and `course_outline`. Those are not the same thing as output-style modes like summary or exam quick review.
- If users can select a mode that does not affect generation, the UI becomes misleading.

Recommended implementation shape if adopted:

- Add a small validated backend contract only.
- Store the selected mode in job metadata.
- Do not show mode controls in the frontend until the prompt/soul behavior is specified and tested.
- Keep output-style mode naming separate from service-mode naming.

Risk:

- Medium if exposed to users too early.
- Low if stored as hidden metadata only.

## Frontend Ideas Worth Reusing Later

These should inform the formal `apps/web` frontend, not be copied wholesale into the current backend-served temporary UI.

- Scenario cards are clearer than a plain select when there are multiple subjects.
- A segmented control is a good fit for output-style modes once those modes have real behavior.
- A visible quality badge near the generated output is useful.
- A download button belongs in the reader header.
- Progress labels such as parsing, retrieving evidence, and generating are better than a raw status string.
- KaTeX rendering may be valuable for math-heavy subjects, but should be added through the formal frontend dependency stack rather than a CDN script in the temporary page.

Reason to defer:

- We already plan to build the real frontend with Next.js and shadcn/ui. Large edits to the temporary HTML would create throwaway UI churn.

## Should Not Be Copied as-is

### 1. Enabling blank General and Engineering scenarios for users

Observed behavior:

- Deployed `/api/options` exposes `general-default` and `engineering-default`.

Why not copy:

- Our current product direction says blank soul profiles remain hidden until they have usable content.
- Exposing blank domains makes users think those subjects are supported.
- It weakens the vertical-quality strategy.

Recommendation:

- Keep only `medicine-default` visible by default.
- Enable General or Engineering only after their soul profile has real content.

### 2. Public admin settings page without token

Observed behavior:

- `GET /admin/settings` returned HTML without an admin token.

Why not copy:

- This is a deployment risk, not a feature.
- Admin settings include model configuration and invite-code management.

Recommendation:

- Ensure production-like deployments set `JSTUDY_ADMIN_TOKEN`.
- Keep query-token admin access temporary; replace with proper admin session later.

### 3. External CDN dependencies in backend-served temporary UI

Observed behavior:

- Deployed page loads Google Fonts, KaTeX CSS, and KaTeX JS from CDNs.

Why not copy now:

- The backend-served UI is temporary.
- CDN availability and privacy should be handled deliberately in the formal frontend build.

Recommendation:

- Revisit KaTeX and font choices in `apps/web`.

## Deployment Issues Found

These are useful operational feedback, not merge candidates.

- Provider probe failed with SiliconFlow HTTP 401 for chat and embedding. The deployed API key is invalid or not the intended key.
- Job retention is disabled. This is acceptable for short debugging but should not be left that way for public pilot usage.
- Admin settings appeared accessible without an admin token. Verify `JSTUDY_ADMIN_TOKEN` on that deployment.
- The deployed site exposes additional scenarios that our current product rules intentionally hide.

## Suggested Next Steps

1. Do not merge the deployed branch as-is.
2. Add the Markdown export endpoint in a small backend PR with tests.
3. Decide whether output-style modes are part of the upcoming frontend MVP. If yes, write a short spec that distinguishes output-style mode from service mode.
4. Use the collaborator UI only as frontend inspiration for `apps/web`.
5. Ask the collaborator to push any deployment-only changes to a separate branch if they want specific code reviewed.
