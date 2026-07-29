# Task 0006 PostgreSQL Job 持久化与独立 Worker 完成报告

## 1. Task

- Task card：`multi-agent/jstudy-product-build/task_cards/0006-job-persistence-worker.md`
- Source thread：`019fa956-f165-76b0-b49d-9462d2f52328`
- Code Agent thread：`019efec4-1e17-7443-8496-c1fea5d6bcb5`
- Status：`completed`
- Required baseline：`b271e38 文档：确定 JSON 到 HTML 的资料渲染架构`
- 实际开始 SHA：`f430bc9e13a7f0f8ed49cb6d1b94e4984d7efc12`
- 最终实现 SHA：`3091c6127ef12e917e0452dc1e620411dae86da5`
- 首次交付 SHA：`a23c11b3fda98fa0cabdf6dac4200e6162757656`
- Corrective 基线 verdict：`REVISE`
- Corrective 最终 SHA：本报告所在提交不能在提交自身中自指，以 Supervisor 回报中的完整 SHA 为准。

## 2. Summary

- 建立显式 Job 状态机，内部状态为 `queued -> parsing -> retrieving -> generating -> packaging -> completed`，并支持活动阶段到 `failed`、`cancelled`，以及受最大尝试次数约束的活动阶段回到 `queued`。
- 保持前端兼容状态：`queued`、`running`、`completed`、`failed`；新增 `state`、`stage`、`progress`、`attempt_count`、`error_code`，不公开 lease owner、服务器路径、原始异常或 provider secret。
- 使用 SQLModel 持久化 `jobs`、`job_sources`、`job_sections`、`job_artifacts`、`job_transitions`。所有读取按 `owner_user_id` 隔离，unknown job 与 foreign-owned job 保持同样的 `404`。
- 实现数据库原子认领、租约续期、过期租约恢复、CAS 防陈旧 Worker 写入、有限重试、原子 artifact 完成，以及 terminal Job 的有界 retention cleanup。
- `POST /api/generate` 只执行认证、流式上传、哈希、限制与幂等校验、持久化 queued Job，不再通过 FastAPI `BackgroundTasks` 或 runner 执行 generation。
- 新增独立入口 `python -m apps.worker.main`；Worker 一次处理一个 Job，同时支持 `single_courseware` 与 `course_outline`。
- 上传 admission 支持 PDF 数量、单 PDF、总上传、outline、队列容量、单用户活动 Job 限制；`Idempotency-Key` 按 owner 和请求 fingerprint 隔离。
- embedding cache 按 `job_id/attempt` 隔离，避免多个 Worker 处理不同 Job 时竞争同一个无锁 JSON cache。
- `/trace` 对路径字段和绝对路径递归脱敏，避免公开 jobs root、输入文件、cache 或其他服务器路径。
- Playwright support 使用真实 FastAPI、临时 SQL 数据库和独立 Worker loop；deterministic runner 仅注入 Worker，API 不内联执行。
- Compose 形成 `postgres`、`jstudy-api`、`jstudy-worker` 三服务；API 与 Worker 共享数据库、jobs volume 和运行配置，Worker 不暴露端口。
- Corrective patch 增加窄 settings provider boundary：每次新 submission 和新 claim
  重载运行配置；一次 submission/claim 只使用一个不可变 snapshot。热更新不得切换
  `database_url` 或 `jobs_root`。
- Compose 不再注入会覆盖管理端配置的模型、provider key、parser/Soul 路径、
  `max_pdf_bytes` 和 retention 环境值；API 与 Worker 从共享 `data/settings` 读取更新。
- `.md`/`.txt` outline 落盘后执行有界 UTF-8 strict decode；非法文本同步返回
  `invalid_outline`，不创建 Job，并清理临时目录。
- Worker 验证 material package type、service mode、section identity/order/status/quality
  和 artifact metadata；sections、artifacts 与 completed transition 在同一 lease-protected
  transaction 中写入。`single_courseware` 持久化 `full-material / 完整资料` section。

## 3. Changed Files

- `README.md`：更新 durable Job、独立 Worker 和 Compose 使用说明。
- `apps/api/jstudy_api/app.py`：切换 durable submission/owner-scoped polling，移除生产内联 runner，增加 DB readiness、公开 payload 脱敏和 submission settings snapshot。
- `apps/worker/__init__.py`：建立 Worker 应用包。
- `apps/worker/main.py`：新增独立 Worker CLI、`--once` 和逐 claim settings reload provider。
- `apps/web/e2e/support/serve_backend.py`：E2E 改为真实 API 加独立 Worker loop。
- `deploy/docker-compose/README.md`：记录三服务运行、检查、热更新配置来源和 pilot migration 边界。
- `deploy/docker-compose/api.compose.yml`：增加 PostgreSQL/API/Worker 共享拓扑，并避免注入覆盖管理端热更新的环境值。
- `docs/architecture/overview.md`：更新 Job persistence 和 Worker 架构。
- `docs/roadmap.md`：更新当前完成项与 schema migration 延期项。
- `multi-agent/jstudy-product-build/reports/0006-baseline-inventory.md`：记录 Phase 0 基线、排除项和测试基线。
- `packages/core/jstudy_core/auth_db.py`：统一创建 auth 与 Job SQLModel tables，并为 SQLite 测试启用外键。
- `packages/core/jstudy_core/job_system/__init__.py`：集中导出 Job system contract。
- `packages/core/jstudy_core/job_system/models.py`：定义五张 SQLModel 表、受控 enum 与安全相对路径 contract。
- `packages/core/jstudy_core/job_system/repository.py`：实现持久化、原子 admission/claim、lease、transition、artifact、section 原子完成和 retention。
- `packages/core/jstudy_core/job_system/service.py`：实现流式上传、哈希、限制、幂等、UTF-8 outline validation 和单次 settings snapshot durable submission。
- `packages/core/jstudy_core/job_system/states.py`：定义状态、合法迁移、公开状态和进度。
- `packages/core/jstudy_core/job_system/worker.py`：实现独立 Worker、逐 claim settings snapshot、heartbeat、重试、双 service mode、package section validation、原子完成和 cleanup。
- `packages/core/jstudy_core/pipeline.py`：增加可选 progress callback，不改变 parser 或生成结果 contract。
- `packages/core/jstudy_core/settings.py`：增加 Job/Worker/admission 环境配置、默认值和禁止 storage topology 热切换的 snapshot boundary。
- `tests/test_deployment_files.py`：验证三服务 Compose contract。
- `tests/test_job_repository.py`：覆盖 schema、ownership、原子 claim、lease、CAS、section/artifact transaction、retention 和路径安全。
- `tests/test_job_service.py`：覆盖上传限制、PDF/outline UTF-8 验证、settings reload、幂等、容量和清理。
- `tests/test_job_states.py`：覆盖合法/非法迁移、公开状态和进度。
- `tests/test_job_worker.py`：覆盖双 service mode、settings snapshot、heartbeat、重试、陈旧 Worker、section/artifact 原子完成、package validation、cache 隔离和 retention。
- `tests/test_mvp_runner.py`：覆盖 pipeline progress callback 兼容性。
- `tests/test_security_controls.py`：覆盖 durable ownership、公开错误、trace 路径脱敏和所有 artifact/source routes。
- `tests/test_settings.py`：覆盖 exact pilot defaults 和环境变量。
- `tests/test_web_mvp.py`：覆盖 queued submission、API/Worker 分离、管理端设置热更新、真实 admission+worker sections、重启持久化、状态和原有 route contract。
- `multi-agent/jstudy-product-build/reports/0006-job-persistence-worker-report.md`：本完成报告。

## 4. Verification

- `python -m compileall -q apps packages`：通过，退出码 `0`。
- `python -m unittest discover -s tests -v`：`281/281` 通过。
- 三项 corrective 联合 focused suite：`122/122` 通过。
- settings provider、Compose override 和 package service-mode 测试均完成 RED/GREEN。
- outline 非法 UTF-8 `.md`/`.txt` 子用例先因未抛出错误而 RED，修复后通过。
- section persistence 的 single/course/stale/transaction 测试先因无 repository 行为而 RED，修复后通过。
- trace/cache corrective focused tests：`2/2` 先红后绿。
- Worker/security/API focused tests：`62/62` 通过。
- Corrective 独立最终复核：无 findings；相关 focused suite `137/137` 通过。
- `npm run lint`：通过。
- `npm run typecheck`：通过。
- `npm run test -- --run`：Vitest `8` 个文件，`13/13` 通过。
- `npm run build`：Next.js production build 通过。
- `npm run test:e2e`：Playwright `12/12` 通过，覆盖 mobile `390`、tablet `768`、desktop `1440`。
- `docker compose -f deploy/docker-compose/api.compose.yml config --services`：通过，输出 `postgres`、`jstudy-api`、`jstudy-worker`。
- `git diff --check`：通过。
- checkpoint 文件审查：未 stage/commit `supervisor_review.md`、`data/`、`.env`、数据库、上传、生成 artifact 或六个排除目录。

Compose pilot 命令：

```powershell
docker compose -f deploy/docker-compose/api.compose.yml up -d postgres jstudy-api jstudy-worker
docker compose -f deploy/docker-compose/api.compose.yml ps
docker compose -f deploy/docker-compose/api.compose.yml logs -f jstudy-api jstudy-worker
```

## 5. Risks and Limitations

- 本机 Docker daemon 不可用，本任务未启动真实 PostgreSQL/API/Worker 容器，也未执行 PostgreSQL 迁移、claim 或故障恢复 smoke test；仅验证 SQLModel contract、PostgreSQL DDL/锁分支和 Compose 静态配置，不以 SQLite 结果宣称实机 PostgreSQL 已验证。
- Pilot 仍使用 SQLModel `create_all()`，仅适用于 disposable pilot data；持久生产数据启用前必须引入版本化 schema migration 和迁移 runbook。
- 未执行 live MinerU/provider 请求；现有 pipeline 与 parser 默认行为未切换，部署阶段仍需 provider smoke test。
- legacy `packages/core/jstudy_core/jobs.py` 和 JSON `JobStore` 保留，避免未经最终删除审查扩大范围；生产 FastAPI 已无 `JobStore`、`jobs.json`、`BackgroundTasks` 或 runner 调用。
- 未实施 HTML、`material-package.v2`，未移除 Markdown，未改变 MinerU/parser 默认路径，未做前端视觉重构、部署、push、merge、rebase、reset 或 clean。
- Supervisor-owned `multi-agent/jstudy-product-build/reports/supervisor_review.md` 与 `.superpowers/`、`frontend/`、`game/`、`images/`、`outline_mode/`、`scripts/` 保持在本任务提交之外。

## 6. Requested Supervisor Action

请独立复核最终交付提交，并给出一个 verdict：

`PASS` / `PASS_WITH_LIMITATIONS` / `REVISE` / `REJECT`
