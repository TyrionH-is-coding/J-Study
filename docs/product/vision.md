# Product Vision

## What J-Study Is

J-Study is a multi-discipline study-material generation product. It turns courseware and optional outlines into structured study materials, keeps the generated content tied to source evidence, and gives learners a way to jump back to the original page behind each claim.

The first validated domain is medicine. That does not define the long-term boundary of the product. Medicine is the first subject pack because domain quality can be judged directly and the initial workload is mostly organization, citation, and learning-output design.

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
   The product must run reliably before adding heavy infrastructure. Database-backed jobs, queues, object storage, and MinerU can be introduced when their value is proven by usage.

## Current MVP Scope

The MVP supports one courseware PDF plus an optional outline. It extracts text, retrieves evidence, generates Markdown study material, and maps evidence comments to original PDF pages.

The MVP does not yet include:

- user accounts or permissions
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
- retrieval query planner
- evidence filtering rules
- mnemonic or terminology library
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

This is one reason the architecture should reserve a heavier document parsing path such as MinerU, while keeping PyMuPDF as the lightweight MVP default.
