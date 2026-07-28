# 0005 基线盘点

## 仓库基线

- Branch: `feature/backend-frontend-mvp`
- Pre-checkpoint SHA: `54629cefec1f54a7fc0f0f6d5bdf056be533d78a`
- Upstream: `origin/feature/backend-frontend-mvp`
- `git diff --check`: 通过；仅有 README、FastAPI app 和 pipeline 的既有 CRLF/LF 提示，无空白错误。

## 已跟踪修改

- `README.md`
- `apps/api/jstudy_api/app.py`
- `apps/api/jstudy_api/ui.py`
- `docs/architecture/overview.md`
- `docs/deployment/server-runbook.md`
- `docs/development/standards.md`
- `docs/product/vision.md`
- `docs/roadmap.md`
- `packages/core/jstudy_core/citations.py`
- `packages/core/jstudy_core/jobs.py`
- `packages/core/jstudy_core/pipeline.py`
- `packages/core/jstudy_core/storage.py`
- `packages/retrieval/hybrid.py`
- `tests/test_mvp_runner.py`
- `tests/test_security_controls.py`
- `tests/test_web_mvp.py`

这些修改对应已由 Supervisor 复核的 0002–0003 FastAPI/Course Outline 后端工作，以及与当前重构方向直接相关的文档更新。

## 纳入 checkpoint 的未跟踪产品路径

- `apps/web/**`: 0004 已通过 Supervisor 复核的正式 Next.js 前端。
- `docs/architecture/refactor-blueprint.md`: 0005 控制文档。
- `docs/deployment/first-production-like-deploy-plan.md`: 0004 后续部署计划文档。
- `docs/frontend/clinical-workbench-spec.md`: 0004 前端控制规范。
- `docs/superpowers/plans/2026-07-28-mineru-document-foundation.md`: Supervisor 编写的 0005 执行计划。
- `multi-agent/jstudy-product-build/**`: 0001–0005 任务卡、协调契约、计划、盘点和 Supervisor 复核记录。

## 明确排除的未跟踪路径

- `.superpowers/brainstorm/**`
- `frontend/**`
- `game/**`
- `images/**`
- `outline_mode/**`
- `scripts/**`

未发现待纳入 checkpoint 的 `data/**`、上传文件、生成产物、数据库、`jobs.json` 或真实 PDF。上述排除路径不会 stage、commit、删除或修改。

## 密钥与运行时数据扫描

- 对候选文件名检查了 `.env`、数据库、`jobs.json`、PDF、upload/output/generated/data 路径。
- 对候选文本检查了私钥头、长格式 `sk-` key、真实形态 Bearer 值和内联 API token/key。
- 未发现真实密钥、Authorization header 实值、cookie、数据库、上传物或用户产物。
- `apps/web/.env.local.example` 是 0004 Supervisor 已复核为应跟踪的样例文件，仅包含 `JSTUDY_API_ORIGIN=http://127.0.0.1:8000`，不含密钥或 token。

## 测试基线

- Backend: `python -m unittest discover -s tests -v` -> `Ran 120 tests`, `OK`。
- Backend sandbox note: 沙箱内 Python 无法写 Windows 临时目录，产生 76 个 `PermissionError`；同一命令经批准在沙箱外执行后 `120/120` 通过，确认不是代码回归。
- Frontend lint: `npm run lint` -> 通过。
- Frontend typecheck: `npm run typecheck` -> 通过。
- Frontend unit: `npm test` -> `8` files、`13/13` tests 通过。
- Frontend build: `npm run build` -> Next.js production build 通过。
- Frontend E2E: `npm run test:e2e` -> `12/12` 通过，覆盖 `390x844`、`768x1024`、`1440x900`。
- Frontend sandbox note: Vitest/Playwright 在沙箱内启动子进程时返回 `spawn EPERM`；经批准在沙箱外复跑后全部通过。

## checkpoint 精确文件清单

```text
README.md
apps/api/jstudy_api/app.py
apps/api/jstudy_api/ui.py
apps/web/.env.local.example
apps/web/.gitignore
apps/web/README.md
apps/web/components.json
apps/web/e2e/course-outline.spec.ts
apps/web/e2e/support/serve_backend.py
apps/web/eslint.config.mjs
apps/web/next.config.ts
apps/web/package-lock.json
apps/web/package.json
apps/web/playwright.config.ts
apps/web/postcss.config.mjs
apps/web/src/app/favicon.ico
apps/web/src/app/globals.css
apps/web/src/app/jobs/[jobId]/page.tsx
apps/web/src/app/layout.tsx
apps/web/src/app/login/page.tsx
apps/web/src/app/modes/course-outline/page.tsx
apps/web/src/app/modes/layout.tsx
apps/web/src/app/modes/page.tsx
apps/web/src/app/page.tsx
apps/web/src/app/providers.tsx
apps/web/src/app/register/page.tsx
apps/web/src/components/ui/alert.tsx
apps/web/src/components/ui/badge.tsx
apps/web/src/components/ui/button.tsx
apps/web/src/components/ui/input.tsx
apps/web/src/components/ui/label.tsx
apps/web/src/components/ui/progress.tsx
apps/web/src/features/auth/auth-form.test.tsx
apps/web/src/features/auth/auth-form.tsx
apps/web/src/features/auth/auth-gate.test.tsx
apps/web/src/features/auth/auth-gate.tsx
apps/web/src/features/auth/home-redirect.tsx
apps/web/src/features/auth/session.ts
apps/web/src/features/auth/workspace-shell.tsx
apps/web/src/features/course-outline/course-outline-form.test.tsx
apps/web/src/features/course-outline/course-outline-form.tsx
apps/web/src/features/reader/job-workspace.test.tsx
apps/web/src/features/reader/job-workspace.tsx
apps/web/src/features/reader/markdown-section.test.tsx
apps/web/src/features/reader/markdown-section.tsx
apps/web/src/features/reader/markdown.test.ts
apps/web/src/features/reader/markdown.ts
apps/web/src/features/source-preview/source-preview.test.tsx
apps/web/src/features/source-preview/source-preview.tsx
apps/web/src/lib/api/api.test.ts
apps/web/src/lib/api/client.ts
apps/web/src/lib/api/index.ts
apps/web/src/lib/api/types.ts
apps/web/src/lib/utils.ts
apps/web/src/test/render.tsx
apps/web/src/test/setup.ts
apps/web/tsconfig.json
apps/web/vitest.config.ts
docs/architecture/overview.md
docs/architecture/refactor-blueprint.md
docs/deployment/first-production-like-deploy-plan.md
docs/deployment/server-runbook.md
docs/development/standards.md
docs/frontend/clinical-workbench-spec.md
docs/product/vision.md
docs/roadmap.md
docs/superpowers/plans/2026-07-28-mineru-document-foundation.md
multi-agent/jstudy-product-build/README.md
multi-agent/jstudy-product-build/agents/code-agent.md
multi-agent/jstudy-product-build/agents/supervisor-agent.md
multi-agent/jstudy-product-build/coordination/output_contract.md
multi-agent/jstudy-product-build/coordination/session_registry.md
multi-agent/jstudy-product-build/coordination/task_card_template.md
multi-agent/jstudy-product-build/coordination/workflow.md
multi-agent/jstudy-product-build/reports/0002-candidate-merge-inventory.md
multi-agent/jstudy-product-build/reports/0003-course-outline-backend-plan.md
multi-agent/jstudy-product-build/reports/0004-frontend-plan.md
multi-agent/jstudy-product-build/reports/0005-baseline-inventory.md
multi-agent/jstudy-product-build/reports/next_actions.md
multi-agent/jstudy-product-build/reports/progress_log.md
multi-agent/jstudy-product-build/reports/supervisor_review.md
multi-agent/jstudy-product-build/shared/project_context.md
multi-agent/jstudy-product-build/shared/repo_rules.md
multi-agent/jstudy-product-build/task_cards/0001-code-agent-onboarding.md
multi-agent/jstudy-product-build/task_cards/0002-fastapi-first-mvp-merge.md
multi-agent/jstudy-product-build/task_cards/0003-course-outline-multipdf-backend.md
multi-agent/jstudy-product-build/task_cards/0004-frontend-foundation-course-outline.md
multi-agent/jstudy-product-build/task_cards/0005-refactor-checkpoint-mineru-foundation.md
packages/core/jstudy_core/citations.py
packages/core/jstudy_core/jobs.py
packages/core/jstudy_core/pipeline.py
packages/core/jstudy_core/storage.py
packages/retrieval/hybrid.py
tests/test_mvp_runner.py
tests/test_security_controls.py
tests/test_web_mvp.py
```

## checkpoint SHA

- Checkpoint SHA: 待 Phase 1 提交后回填。
