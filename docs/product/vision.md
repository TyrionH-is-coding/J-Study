# Product Vision

## What J-Study Is

J-Study is a multi-discipline study-material generation product. It turns courseware and optional outlines into structured study materials, keeps the generated content tied to source evidence, and gives learners a way to jump back to the original page behind each claim.

The first validated domain is medicine. That does not define the long-term boundary of the product. Medicine is the first subject pack because domain quality can be judged directly and the initial workload is mostly organization, citation, and learning-output design.

J-Study is intentionally more vertical than DeepTutor. DeepTutor can remain a broad general-purpose learning framework; J-Study should build subject-specific depth through curated soul profiles and a reviewed knowledge snippet library. Those two libraries are product assets, not incidental prompt files. They will be improved one subject at a time after the core service is running.

## Product Principles

1. Source-grounded output comes first.
   Generated material should be tied to courseware evidence wherever possible. Evidence IDs and page jumps are a core product behavior, not a decoration.

2. Multi-discipline by design.
   Platform code should not hard-code medicine-specific templates, prompts, query plans, or quality rules. Those belong in domain packs.

3. Lightweight MVP, formal boundaries.
   The first deployable version should stay simple enough to run on one server, but its boundaries should support later growth.

4. Template-first frontend.
   The frontend should use a selected shadcn/ui template as the layout foundation. We can adjust color, typography, texture, state, and domain-specific components, but should not redesign the whole layout during the MVP.

5. Deployable beats theoretical.
   The product must run reliably before adding speculative infrastructure.
   MinerU cloud parsing and database-backed job state are now approved
   foundations; Redis, object storage, and self-hosted parsing remain
   measurement-driven additions.

6. Vertical quality compounds through curated libraries.
   The platform should make it easy to route by subject and scenario, but quality will come from manually refined soul profiles and reviewed knowledge snippets. Do not dilute the product into a fully generic assistant before the vertical libraries have depth.

## Current MVP Scope

The MVP supports one courseware PDF plus an optional outline. It extracts text, retrieves evidence, generates Markdown study material, and maps evidence comments to original PDF pages.

## Service Modes

J-Study should support three service modes. They should share the same source-grounded generation philosophy, but they should not be treated as the same backend workflow.

1. Single Courseware Mode
   One courseware PDF produces one structured study material output. This is the current MVP path and remains the first priority because it validates parsing, retrieval, citations, generation quality, auth, and deployment with the smallest surface area.

2. Batch Courseware Mode
   Multiple courseware PDFs are uploaded together and become one study-material package. The package should be browsable by chapter or topic in the web app and exportable as one complete document. Unlike the current MVP, this mode needs source-file metadata, cross-file evidence aggregation, duplicate-topic handling, and a package output model instead of assuming one markdown file per job.

3. Course Outline Mode
   The user uploads a course outline plus all courseware for a full course. The outline becomes the organizing contract: the system should split the course into outline nodes, retrieve evidence across all uploaded courseware for each node, show the result as a chapter-by-chapter course package in the web app, and allow exporting the whole package as complete course material. Missing or weak evidence should be visible per outline node.

Batch Courseware Mode and Course Outline Mode should converge on the same user-facing output model: a navigable material package with section-level evidence and full-document export. Their main difference is how the section plan is created.

The MVP does not yet include:

- persistent job database
- production queue or worker process
- object storage
- multi-courseware outline mode
- formal frontend app
- question generation from past exam papers

## Domain Packs

A domain pack owns subject-specific behavior:

- output template
- prompt fragments
- soul profiles
- retrieval query planner
- evidence filtering rules
- knowledge snippet and terminology library
- quality checks
- question-generation rules

The default domain pack is `medicine`. Future domains should be added without rewriting the platform pipeline.

J-Study should use a hybrid domain-pack model:

- simple behavior can be expressed with Markdown, YAML, or JSON configuration
- complex behavior can be implemented with code behind a stable interface

## Future Question Generation

Question generation is a future product pillar. The likely path is:

1. parse past exam papers
2. extract question structure and style
3. map questions to courseware topics and evidence
4. generate new questions with similar structure
5. provide answer explanations tied to courseware evidence

This is why the product standardizes content extraction on MinerU. PyMuPDF
remains an internal validation and page-rendering utility, while users see one
consistent parsing experience.

## Knowledge Snippet Feedback Loop

J-Study should accumulate quality improvements from real usage without allowing ambiguous or unsupported fragments to spread across users.

The intended path is:

1. A user selects a high-quality fragment in generated material and likes it.
2. The backend stores the fragment as raw feedback with job, user, scenario, subject, and evidence metadata.
3. Embedding-based similarity groups near-duplicate feedback into administrator-visible candidate clusters.
4. Only reviewed candidates become approved knowledge snippets.
5. Approved snippets may be retrieved during future generation as memory aids, structure guidance, or polished expression patterns.

Approved snippets must not become independent fact sources. If a snippet contains factual claims, the current uploaded material must still provide supporting evidence before that content can appear in the final output. The first implementation should leave only the feedback hook and candidate-pool data model; automatic replacement is explicitly out of scope.
