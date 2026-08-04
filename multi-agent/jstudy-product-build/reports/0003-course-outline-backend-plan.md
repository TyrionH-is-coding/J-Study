# 0003 Course Outline Multi-PDF Backend Plan

## Assumptions

- This task continues on top of the current uncommitted 0002 FastAPI product-path work.
- `service_mode` is a new upload contract field. Empty value and `single_courseware` keep the existing one-PDF behavior.
- Existing `mode` remains metadata/generation hint only and is passed through as `generation_mode`; it is not used to select a service mode.
- Course Outline Mode will use the same auth, job storage, parser profile, scenario routing, upload limits, output directory, and artifact URLs as the current FastAPI path.
- First implementation caps outline sections to 12. Unsupported or empty outlines fail clearly instead of inventing sections.
- Existing single-PDF preview endpoints stay compatible and point to the first source PDF. New frontend should use source-specific preview endpoints.

## API Changes

- `POST /api/generate`
  - Existing single-courseware request remains:
    - `pdf=<one PDF>`
    - `outline=<optional .md/.txt/.pdf>`
    - `scenario_id`, `parser_profile_id`, `mode`
  - New course-outline request:
    - `service_mode=course_outline`
    - `outline=<required .md/.txt/.pdf>`
    - `pdfs=<one or more PDF files as repeated multipart field>`
    - `scenario_id`, `parser_profile_id`, `mode`
  - Validation:
    - unsupported `service_mode` returns `400`
    - `course_outline` requires `outline`
    - `course_outline` requires at least one valid uploaded PDF in `pdfs`
    - each PDF uses existing header/size validation
- `GET /api/jobs/{job_id}` adds:
  - `service_mode`
  - `source_files`
  - `pdfs_url`
  - `source_pdf_url_template`
  - `source_pdf_info_url_template`
  - `source_pdf_page_url_template`
- New source-specific preview endpoints:
  - `GET /api/jobs/{job_id}/pdfs`
  - `GET /api/jobs/{job_id}/pdfs/{source_id}/pdf`
  - `GET /api/jobs/{job_id}/pdfs/{source_id}/pdf-info`
  - `GET /api/jobs/{job_id}/pdfs/{source_id}/pdf-page/{page_no}.png`

## Artifact Shape

`result-package.json` remains a `material_package`.

Course-outline package shape:

```json
{
  "type": "material_package",
  "service_mode": "course_outline",
  "generation_mode": "metadata-only",
  "source_files": [
    {
      "source_id": "S001",
      "file_name": "lecture-01.pdf",
      "page_count": 42,
      "parser_backend": "pymupdf"
    }
  ],
  "sections": [
    {
      "id": "section-001",
      "title": "Unit 1",
      "order": 1,
      "status": "generated",
      "quality": {
        "evidence_count": 2
      },
      "source_files": ["S001"],
      "evidence_ids": ["E001", "E002"],
      "artifact_filenames": {
        "markdown": "result-output.md",
        "evidence": "result-evidence.json",
        "evidence_links": "result-evidence_links.json",
        "quality": "result-quality.json",
        "package": "result-package.json"
      }
    }
  ]
}
```

Evidence and citation targets include `source_id`, `source_file`, `page`, `chunk_id`, and `quote`.

## Tests To Add

- `POST /api/generate` rejects unsupported `service_mode`.
- `course_outline` rejects missing outline.
- `course_outline` rejects missing repeated `pdfs`.
- `course_outline` accepts repeated `pdfs`, records source metadata, and exposes source preview URLs.
- Other users cannot access source-specific PDF preview artifacts.
- `chunk_pages()` can attach source identity and produce source-scoped chunk ids.
- Evidence items and evidence links preserve `source_id` and source file identity.
- `parse_outline_sections()` extracts ordered sections from Markdown headings and numbered lines.
- `run_course_outline()` writes a multi-source, ordered-section `material_package`.
- Existing single-courseware tests continue to pass.

## Files Expected To Change

- `apps/api/jstudy_api/app.py`
- `packages/core/jstudy_core/jobs.py`
- `packages/core/jstudy_core/pipeline.py`
- `packages/core/jstudy_core/citations.py`
- `packages/retrieval/hybrid.py`
- `tests/test_web_mvp.py`
- `tests/test_mvp_runner.py`
- `tests/test_security_controls.py`
- `README.md`
- `docs/architecture/overview.md`
- `docs/roadmap.md`

## Verification

- `python -m py_compile web_mvp.py mvp_runner.py apps/api/jstudy_api/app.py apps/api/jstudy_api/ui.py apps/api/jstudy_api/admin_ui.py packages/core/jstudy_core/admin_settings.py packages/core/jstudy_core/auth_db.py packages/core/jstudy_core/auth_models.py packages/core/jstudy_core/auth_service.py packages/core/jstudy_core/scenario_router.py packages/core/jstudy_core/parser_profile_router.py packages/core/jstudy_core/pipeline.py packages/core/jstudy_core/cli.py packages/core/jstudy_core/citations.py packages/core/jstudy_core/jobs.py packages/core/jstudy_core/providers.py packages/core/jstudy_core/settings.py packages/core/jstudy_core/storage.py packages/parsers/mineru_parser.py packages/parsers/pymupdf_parser.py`
- `python -m unittest discover -s tests -v`
- `git diff --check`
