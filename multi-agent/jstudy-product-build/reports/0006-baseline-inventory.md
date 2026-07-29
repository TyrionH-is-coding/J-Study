# Task 0006 Phase 0 基线盘点

## 1. Git 基线

- 工作目录：`D:\大二下\deep tutor\J-Study`
- 当前分支：`feature/backend-frontend-mvp`
- 当前 HEAD：`f430bc9e13a7f0f8ed49cb6d1b94e4984d7efc12`
- HEAD subject：`文档：规划 PostgreSQL Job 与独立 Worker 重构`
- 任务要求基线：`b271e38 文档：确定 JSON 到 HTML 的资料渲染架构`
- 差异判断：当前 HEAD 是任务要求基线的直接后续任务文档提交，包含 `0006` 任务卡与实施计划；属于预期且不构成实现阻断。

## 2. Working Tree 排除项

已知 Supervisor-owned tracked modification：

- `multi-agent/jstudy-product-build/reports/supervisor_review.md`

已知 unrelated untracked directories：

- `.superpowers/`
- `frontend/`
- `game/`
- `images/`
- `outline_mode/`
- `scripts/`

本任务不得修改、删除、restore、stage 或 commit 上述文件与目录。不得运行 `push`、`merge`、`rebase`、`reset`、`clean` 或部署操作。

## 3. 基线验证

- `python -m compileall -q apps packages`：通过。
- `python -m unittest discover -s tests -v`：`173/173` 通过。
- `npm run lint`：通过。
- `npm run typecheck`：通过。
- `npm test`：Vitest `13/13` 通过。
- `npm run build`：Next.js production build 通过。
- `npm run test:e2e`：Playwright `12/12` 通过。

## 4. 当前生产路径

- `apps/api/jstudy_api/app.py` 当前通过 `JobStore(store_path=jobs_root / "jobs.json")` 持久化状态。
- `POST /api/generate` 当前调用 `BackgroundTasks.add_task(run_job, job_id)`，generation 在 FastAPI 进程内执行。
- queued/running Job 在旧 JSON store 重启时被标记为 failed，不具备 durable worker recovery。
- auth 已使用 SQLModel；`requirements.txt` 已包含 `sqlmodel` 与 `psycopg[binary]`，本任务不需要修改 dependency files。
- Compose 当前已有 `postgres` 与 `jstudy-api`，尚无独立 `jstudy-worker`。

## 5. 计划文件范围

新增：

- `packages/core/jstudy_core/job_system/__init__.py`
- `packages/core/jstudy_core/job_system/models.py`
- `packages/core/jstudy_core/job_system/states.py`
- `packages/core/jstudy_core/job_system/repository.py`
- `packages/core/jstudy_core/job_system/service.py`
- `packages/core/jstudy_core/job_system/worker.py`
- `apps/worker/__init__.py`
- `apps/worker/main.py`
- `tests/test_job_states.py`
- `tests/test_job_repository.py`
- `tests/test_job_service.py`
- `tests/test_job_worker.py`
- `multi-agent/jstudy-product-build/reports/0006-job-persistence-worker-report.md`

按需修改：

- `apps/api/jstudy_api/app.py`
- `apps/web/e2e/support/serve_backend.py`
- `packages/core/jstudy_core/auth_db.py`
- `packages/core/jstudy_core/jobs.py`
- `packages/core/jstudy_core/pipeline.py`
- `packages/core/jstudy_core/settings.py`
- `packages/core/jstudy_core/storage.py`
- `tests/test_web_mvp.py`
- `tests/test_security_controls.py`
- `tests/test_mvp_runner.py`
- `tests/test_deployment_files.py`（仅补充任务要求的 Compose contract 验证）
- `deploy/docker-compose/api.compose.yml`
- `deploy/docker-compose/README.md`
- `README.md`
- `docs/architecture/overview.md`
- `docs/roadmap.md`
- `multi-agent/jstudy-product-build/reports/0006-baseline-inventory.md`

## 6. 不变量与延期项

- 保留 public API URL、frontend-facing `status`、Markdown output、`material_package` v1、source identity 与 PDF preview contract。
- 不实施 HTML 或 `material-package.v2`，不移除 Markdown。
- 不切换 MinerU pipeline，不改变 parser profile 或默认 parser。
- 不做前端视觉重构，不改变登录/邀请码产品策略。
- legacy `packages/core/jstudy_core/jobs.py` 暂时保留为兼容边界；只有 production imports/call sites 切换到 `job_system`，删除须另行审查。
- SQLModel `create_all()` 仅用于 disposable pilot；版本化 schema migration 与生产迁移 runbook 延期到正式持久数据前完成。