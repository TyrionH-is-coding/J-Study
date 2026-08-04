# Dynamic Study Query Planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the cocci-specific hardcoded default RAG query list and generate study queries from the uploaded PDF text and optional outline.

**Architecture:** Keep the `StudyQuery` contract and retrieval layer unchanged. Replace the `medicine.build_study_queries()` cocci list with a deterministic topic extractor that builds generic medicine-study query modules from current source text and outline. Update the pipeline to pass extracted chunks and outline text into the planner before embedding query texts.

**Tech Stack:** Python 3.12, stdlib regex/string processing, existing `unittest` suite, current hybrid RAG adapter.

---

## Files

- Modify `packages/domains/medicine.py`: replace cocci query constants with dynamic topic extraction and generic query modules.
- Modify `packages/core/jstudy_core/pipeline.py`: pass chunk text and outline text into `build_study_queries()`.
- Modify `tests/test_mvp_runner.py`: replace cocci-locking tests with dynamic planner tests and add pipeline argument coverage.
- Modify `tests/test_backend_boundaries.py`: keep import boundary coverage without requiring the old count.
- Update `README.md` and `docs/architecture/overview.md`: document source-driven query planning.

## Tasks

### Task 1: Red Tests for Dynamic Query Planning

- [x] Add a test proving `build_study_queries(source_text=..., outline=...)` includes source/outline topics such as antigen, antibody, complement, and hypersensitivity.
- [x] Add a test proving non-cocci source text does not emit cocci-specific terms like `staphylococcus`, `gonococcus`, or `葡萄球菌`.
- [x] Update the old `test_study_queries_cover_multiple_learning_modules` so it expects generic modules such as `overview`, `key_concepts`, `mechanisms`, and `comparisons`.
- [x] Run `python -m unittest discover -s tests -p test_mvp_runner.py -v -k study_queries` and confirm failure because the planner is still cocci-specific.

### Task 2: Implement Dynamic Planner

- [x] Replace `build_study_queries()` in `packages/domains/medicine.py` with a function signature `build_study_queries(source_text: str = "", outline: str = "") -> list[StudyQuery]`.
- [x] Add helper functions to extract topic terms from outline lines, headings, Chinese phrases, and English medical terms.
- [x] Generate 6 generic query modules: overview, key concepts, mechanisms, comparisons, clinical/lab, and exam review.
- [x] Use extracted topics in each query and in `required_any`; when no topics exist, use neutral medical-study fallback terms.
- [x] Re-run `python -m unittest discover -s tests -p test_mvp_runner.py -v -k study_queries` and confirm pass.

### Task 3: Wire Pipeline to Source Text and Outline

- [x] Add a failing test that patches `pipeline.build_study_queries` and asserts `run_mvp()` passes joined chunk text and uploaded outline text.
- [x] Run the focused test and confirm failure because `run_mvp()` currently calls `build_study_queries()` with no arguments.
- [x] Read outline once near query planning and reuse the same string for prompt generation.
- [x] Call `build_study_queries(source_text="\n".join(chunk.text for chunk in chunks), outline=outline_text)`.
- [x] Re-run the focused pipeline test.

### Task 4: Documentation and Verification

- [x] Update README and architecture docs to say RAG queries are source/outline-driven, not cocci-hardcoded.
- [x] Run `python -m unittest discover -s tests -v`.
- [x] Run `python -m py_compile packages/domains/medicine.py packages/core/jstudy_core/pipeline.py`.
- [x] Run `git diff --check`.
- [ ] Commit with `fix: generate study queries from uploaded content` and push the current PR branch.

## Self-Review

- Spec coverage: removes cocci defaults, keeps retrieval adapter unchanged, preserves single-courseware MVP behavior.
- Placeholder scan: no placeholders.
- Type consistency: `source_text`, `outline`, `StudyQuery`, `required_any`, and trace fields stay consistent.
