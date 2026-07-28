# Output Contract

## Language Rule

Reports, Supervisor reviews, completion report-backs, and local documentation default to Chinese.

Commands, paths, API routes, model names, branch names, exact error strings, identifiers, and verdict tokens may remain in English.

## Code Agent Completion Report

A Code Agent completion report must use this structure:

```md
# Code Agent Report

## 1. Task

- Task card:
- Source thread:
- Status: completed | blocked | partial

## 2. Summary

Short summary of what changed.

## 3. Changed Files

- path: change summary

## 4. Verification

- command:
- result:
- notes:

## 5. Risks and Limitations

- known risk
- unsupported claim
- skipped check

## 6. Requested Supervisor Action

`PASS` / `PASS_WITH_LIMITATIONS` / `REVISE` / `REJECT`
```

## Supervisor Review

A Supervisor review must include:

- verdict
- reason
- verification performed by Supervisor
- whether Code Agent verification was accepted, rerun, or limited
- next action

## Verdict Tokens

- `PASS`
- `PASS_WITH_LIMITATIONS`
- `REVISE`
- `REJECT`
