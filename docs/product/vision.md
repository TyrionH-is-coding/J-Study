# Product Vision

## What J-Study Is

J-Study is a multi-discipline, courseware-synchronized learning product. It
turns courseware, or courseware plus an outline in the dedicated outline
workflow, into structured study materials while
preserving the teacher's original teaching sequence. Generated content remains
tied to source evidence, and learners can return to the original page behind a
claim without losing their position in the main learning path.

The product default is General Mode. Medicine was the first validation domain,
but it does not define either the default experience or the long-term boundary.
General Mode remains neutral and never detects or silently switches the user's
discipline. Future Medicine, Engineering, and Humanities modes add broad
discipline-specific quality assets only when the user explicitly selects them.

J-Study is intentionally more vertical than DeepTutor. DeepTutor can remain a broad general-purpose learning framework; J-Study should build subject-specific depth through curated soul profiles and a reviewed knowledge snippet library. Those two libraries are product assets, not incidental prompt files. They will be improved one subject at a time after the core service is running.

## Product Principles

1. Source-grounded output comes first.
   Generated material should be tied to courseware evidence wherever possible. Evidence IDs and page jumps are a core product behavior, not a decoration.

2. Courseware order defines the main learning path.
   Complete-material generation follows the user-confirmed courseware order,
   source page order, and continuous learning units. Semantic similarity may
   discover useful relationships, but it must not reorder the main material or
   make the synchronized reader jump repeatedly between distant pages.

3. Multi-discipline by design.
   Platform code should not hard-code medicine-specific templates, prompts, query plans, or quality rules. Those belong in domain packs.

4. Lightweight MVP, formal boundaries.
   The first deployable version should stay simple enough to run on one server, but its boundaries should support later growth.

5. Template-first frontend.
   The frontend should use a selected shadcn/ui template as the layout foundation. We can adjust color, typography, texture, state, and domain-specific components, but should not redesign the whole layout during the MVP.

6. Deployable beats theoretical.
   The product must run reliably before adding speculative infrastructure.
   MinerU cloud parsing and database-backed job state are now approved
   foundations; Redis, object storage, and self-hosted parsing remain
   measurement-driven additions.

7. Vertical quality compounds through curated libraries.
   The platform should make it easy to route by subject and scenario, but quality will come from manually refined soul profiles and reviewed knowledge snippets. Do not dilute the product into a fully generic assistant before the vertical libraries have depth.

## Current MVP Scope

The backend currently supports Single Courseware and Course Outline submissions,
durable Jobs, multiple PDFs, source previews, and strict
`material-package.v2`. The Worker uses MinerU for product text and structure,
freezes a versioned Courseware Manifest, builds continuous learning units, and
generates complete materials in source/page/block order. Embedding no longer
controls the main learning sequence.

The next product-backend milestones are:

1. provide a real `general-default` Soul Profile and make it the product default;
2. tighten the three service-mode input contracts;
3. implement Multi Courseware association discovery and evidence validation;
4. implement the Courseware Organizer and user-confirmed Manifest workflow;
5. expose the confirmed workflows through the formal frontend.

The controlling design is
`docs/superpowers/specs/2026-07-31-courseware-synchronized-learning-design.md`.

## Service Modes

J-Study should support three service modes. They should share the same source-grounded generation philosophy, but they should not be treated as the same backend workflow.

1. Single Courseware Mode
   Exactly one courseware PDF produces one structured study material output.
   The target product contract does not accept an outline in this workflow.

2. Course Outline Mode
   The user uploads a course outline plus all courseware for a full course. The
   outline helps match, name, and group courseware, while the user-confirmed
   Courseware Manifest defines the source order used by generation. The backend
   builds continuous learning units from the ordered MinerU document stream,
   shows the result as a chapter-by-chapter course package, and allows exporting
   the complete material. Missing or weak coverage remains visible.

3. Multi Courseware Mode
   The user uploads at least two ordered courseware PDFs from the same course
   without an outline. The main material follows the confirmed courseware order.
   Embedding proposes cross-courseware relationships, an evidence-bounded model
   pass validates and classifies them, and a small number of useful relationships
   are rendered as non-interactive natural-language study connections.

The strict contracts and current implementation status are maintained in
`docs/product/service-modes.md`.

The current product does not yet include:

- the formal courseware organizer and editable draft workflow
- Multi Courseware admission and association generation
- completed frontend auth/upload/polling/reader workflows
- object storage and versioned database migrations
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

The product default should be a real `general-default` profile. The current
runtime still has Medicine as its only complete domain asset, so General must
not be enabled from a blank placeholder. Future broad discipline modes should
be added without rewriting the platform pipeline.

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
