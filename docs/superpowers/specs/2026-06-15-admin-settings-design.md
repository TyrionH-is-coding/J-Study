# Admin Settings Design

## Goal

Build a lightweight admin-only settings surface for J-Study so operators can configure model services, retrieval, web search, document parsing, and content packs from the backend UI instead of editing scattered files.

## Assumptions

- End users do not configure models. Operators configure the runtime before serving users.
- The first implementation should stay small and compatible with the current FastAPI single-server MVP.
- Configuration should be persisted under `data/settings/` so Docker Compose deployments can mount one durable directory.
- The data shape should borrow DeepTutor's `model_catalog.json` idea, but not copy its full provider registry or Next.js settings system.
- Web Search is important for the roadmap, but current generation does not depend on it yet. First version stores and diagnoses search configuration without injecting it into `run_mvp`.

## Architecture

The backend gets a new JSON-backed settings layer:

- `model_catalog.json`: model services and search profiles, grouped as `llm`, `embedding`, and `search`.
- `runtime.json`: RAG, parser, job, and upload settings.
- `content_pack.json`: pointers to prompt and mnemonic sources, plus future subject-pack metadata.
- `mnemonics.json`: structured mnemonic items for management; Markdown remains a prompt-rendering format.

`RuntimeSettings.from_env()` continues to support deployment environment overrides, but defaults to the JSON settings when present. The API reads settings per request so applying a new configuration does not require editing source files.

## Admin Surface

Add:

- `GET /admin/settings`: backend-served HTML settings page.
- `GET /api/admin/settings`: returns redacted settings for the page.
- `PUT /api/admin/settings`: saves settings.
- `POST /api/admin/settings/test/{service}`: runs a small diagnostic for `llm`, `embedding`, or `search`.

Admin endpoints require `JSTUDY_ADMIN_TOKEN` when it is set. The token can be supplied through `Authorization: Bearer <token>` or `?admin_token=<token>` for simple local use.

## UI Scope

One backend-served page with three sections:

- Model, RAG, and Web Search: chat model, embedding model, endpoint/API key, RAG chunking/top-k, web-search provider/API key/max results.
- Document Parsing: parser backend (`pymupdf` now, `mineru` reserved), OCR/table/formula options.
- Content Pack: `soul.md`, mnemonic source, subject, and content-pack name.

The page should be utilitarian and dense, matching the MVP's backend UI rather than a marketing page.

## Testing

Tests should cover:

- Default settings files are created and normalized.
- Runtime settings resolve model/RAG/parser/content-pack values from JSON.
- Admin endpoints require a token when configured.
- The admin page and settings API expose expected fields with API keys redacted on GET.
- Mnemonics JSON can be rendered to Markdown for existing prompt flow compatibility.

