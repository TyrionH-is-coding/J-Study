# Snippet Feedback Loop Design

## Goal

Leave a clear product and backend hook for turning user-liked generated fragments into an administrator-reviewed knowledge snippet ecosystem. This should improve answer quality as usage grows without allowing ambiguous, unsupported, or context-specific fragments to be copied into unrelated outputs.

## Assumptions

- This is a roadmap and data-contract design first, not an immediate generation feature.
- User-liked fragments should enter an administrator-visible candidate pool by default.
- The first implementation should not automatically replace generated content.
- The current `mnemonics.md`, `mnemonics.json`, and `JSTUDY_MNEMONICS_PATH` names remain compatibility contracts until the backend runtime is renamed.
- Knowledge snippets are broader than memory aids. They can include memory aids, terminology explanations, comparison tables, workflow summaries, common pitfalls, and polished expression patterns.

## Architecture

The feedback loop has three layers:

1. Raw feedback records store what users selected and liked.
2. Candidate snippet clusters group semantically similar feedback for administrator review.
3. Approved knowledge snippets become retrievable auxiliary guidance during generation.

Raw feedback should capture:

- user id
- job id
- scenario id and subject
- selected text
- source output location when available
- associated evidence ids from the generated markdown
- source PDF page targets from evidence links when available
- embedding status
- creation timestamp

Candidate clusters should capture:

- representative text
- similar feedback ids
- semantic similarity score range
- like count and unique-user count
- subject and topic labels
- review status: `candidate`, `approved`, `rejected`, `deprecated`
- administrator notes

Approved snippets should capture:

- snippet text
- snippet type: memory aid, terminology, comparison, workflow, pitfall, expression pattern
- subject, topic, tags
- source policy: expression-only, factual-with-evidence-required, or memory-aid
- review metadata
- version and deprecation state

## Data Flow

```text
User selects generated fragment and likes it
-> frontend sends raw feedback
-> backend stores feedback with user/job/evidence metadata
-> embedding job embeds selected text
-> semantic deduplication finds or creates a candidate cluster
-> administrator reviews candidates
-> approved snippets become eligible for retrieval
-> generation retrieves approved snippets only after courseware RAG
```

Courseware RAG remains the source of truth. Knowledge snippet retrieval is a second pass that can improve wording, structure, and recall, but it cannot justify factual claims by itself.

## Safety Rules

- A liked fragment is not product knowledge.
- Embedding similarity is not a correctness signal.
- Candidate snippets cannot affect generation.
- Approved expression-only snippets may guide style or structure.
- Approved factual snippets require supporting evidence from the current uploaded material before their claims can appear in output.
- Automatic replacement remains disabled until current-upload evidence matching is reliable enough to handle ambiguous concepts.
- Every generated factual section must keep citation behavior tied to current evidence ids.

## MVP Hook

The first implementation should be intentionally small:

- add a feedback API endpoint for selected liked fragments
- persist feedback records with ownership and job association
- reject feedback for jobs not owned by the current user
- store associated evidence ids when the frontend can provide them
- reserve embedding and clustering fields without making them required
- expose candidate data later in the admin surface

The MVP hook should not change `run_mvp` output generation.

## Testing

Tests should cover:

- unauthenticated users cannot submit feedback
- users cannot submit feedback for another user's job
- empty or oversized selected text is rejected
- evidence ids are stored as metadata, not trusted as proof by themselves
- candidate and approved statuses are distinct
- generation does not consume raw feedback or candidate snippets

## Open Implementation Notes

The current backend still names the prompt-rendered snippet file `mnemonics.md` and the structured admin file `mnemonics.json`. Documentation should describe these as compatibility names. A later implementation can add a migration to `knowledge_snippets.json` and keep backward-compatible loading for existing deployments.
