# Repo Rules

## Repository Root

Use:

`D:\大二下\deep tutor\J-Study`

Do not work in the older `J study` folder.

## Branch Discipline

- Do not merge whole candidate branches without Supervisor approval.
- Prefer small, reviewable PRs.
- Ignore unrelated untracked folders unless the task card explicitly includes them.
- Current known untracked folders may include `frontend/`, `game/`, and `images/`.

## Implementation Discipline

- Keep changes surgical.
- Match existing style.
- Do not refactor unrelated code.
- Do not add speculative flexibility.
- Preserve FastAPI `POST /api/generate` as the main product path.

## Verification Discipline

Code Agent must run required checks when possible.

Supervisor decides final acceptance after review. For backend/security/upload/storage/generation changes, Supervisor should independently rerun focused checks or mark the verdict as limited.
