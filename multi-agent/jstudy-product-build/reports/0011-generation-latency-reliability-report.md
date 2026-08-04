# Task 0011 生成延迟与可靠性报告

## 1. Phase 0 基线

- Branch：`feature/backend-frontend-mvp`
- Exact start SHA：`1a68bc1ca5dc53ef1693a9e2d26f18a9f412bcf7`
- Start commit：`任务：发布生成性能与可靠性整改`
- 开始时确认没有遗留 staging 修改操作或远程会话；本任务未访问腾讯云、
  Cloudflare、Nginx、DNS、真实 Provider 或任何凭据。
- 开始时既有受保护状态：
  - modified：`docs/deployment/tencent-staging-2026-08-03.md`
  - modified：`multi-agent/jstudy-product-build/reports/supervisor_review.md`
  - untracked：`.superpowers/`、
    `docs/reviews/full-staging-verification-2026-08-03.md`、`frontend/`、
    `game/`、`images/`、`outline_mode/`、`scripts/`
- 上述内容保持原样，未修改、stage、提交、移动或清理。
- 修改前 backend baseline：`388/388`。

## 2. 实施合同

- sequence-first 仍保持每个 Learning Unit 一次独立模型调用，不改
  Manifest、Learning Map、Coverage Ledger、Material Package v2 或公开 API。
- 新增 Job 内有界并发，`JSTUDY_GENERATION_MAX_CONCURRENCY` 合法范围为
  `1..4`，默认值 `3`，值 `1` 提供串行回滚。
- Worker 在每次 claim 时取得 settings snapshot；运行中的 claim 不受后续
  配置变化影响。
- 并发完成顺序不影响最终 `MaterialSection.order`。
- 任一章节异常继续走既有 Worker retry/permanent 语义，不发布部分
  artifacts、sections 或 completed transition。
- trace 仅记录 section id、order、status、duration 和任务级计数/总耗时，
  不记录正文、prompt、evidence 内容、Provider 响应或凭据。
- prompt 只新增一条窄规则：同一 workflow/fact 默认选择最清晰的一种学习
  表达，第二种形式必须增加新信息。

## 3. 分阶段 RED/GREEN

### Task 1：调度器合同

- RED：`tests.test_material_scheduling` 因
  `jstudy_core.materials.scheduling` 尚不存在而导入失败。
- GREEN：`5/5`，使用 `Event`/`Barrier` 类确定性同步证明：
  - 六个请求在默认配置下恰好达到三个活动调用；
  - 活动调用不超过配置上限；
  - 乱序完成后结果按 `order` 排序；
  - 配置 `1` 保持串行；
  - provider exception 取消未开始工作并等待已开始工作收敛。
- 提交：
  `66a9fd4db80db648450212de5adb9dd99202d52f 测试：定义章节并发调度合同`
  和
  `8b568086a0e7a625ef5aa4005fc7b4ab560b37dd 功能：增加有界章节并发调度`。

### Task 2：配置与 Worker snapshot

- RED：
  - RuntimeSettings 缺少并发字段；
  - 非整数及范围外值未 fail closed；
  - Worker 未向 runner 传递 claim snapshot；
  - Compose 未向 Worker 透传变量。
- GREEN：settings、Worker 与 deployment focused tests `77/77`。
- Compose 仅向 Worker 透传
  `JSTUDY_GENERATION_MAX_CONCURRENCY`；API 不消费该执行参数。
- 提交：
  `55e54b7bb87f7010342cb30a759f2b84347e9cbf 功能：配置生成并发上限`。

### Task 3：sequence-first 并发接线

- RED：
  - 六个 blocking fake 调用不能同时启动三个；
  - runner 尚不接受并发 snapshot；
  - prompt 缺少防重复表达规则。
- GREEN：pipeline、Worker、settings 和 generation focused tests
  `105/105`。
- `_run_sequence_first()` 先冻结每章节输入，再通过有界调度器调用既有
  section generator；只在全部成功后按 order 构造 Package 和公开 artifacts。
- Worker provider exception 回归使用确定性 Event 协调，证明无 artifact、
  section 或 completed 写入。
- 提交：
  `c8cd5d5238c88e0766700b9fb968cf449eaca5b2 性能：并发生成独立学习章节`。

### Task 4：运维合同

- RED：README、architecture、runbook 和 roadmap 均未说明新变量、回滚、
  Worker 副本乘数及真实性能门禁。
- GREEN：deployment contract tests `13/13`。
- 四份文档统一记录：范围 `1..4`、默认 `3`、串行回滚 `1`、总并发随
  Worker 副本相乘，以及真实六页样本仍由 Supervisor 验证。

## 4. 完整验证

- `python -m compileall -q apps packages`：通过。
- `python -m unittest discover -s tests -v`：`398/398`。
- `apps/web` `npm run lint`：通过。
- `apps/web` `npm run typecheck`：通过。
- `apps/web` `npm test`：Vitest `5/5`。
- `apps/web` `npm run build`：Next.js production build 通过。
- `apps/web` `npm run test:e2e`：
  - 首次发现 3000 端口由前一日遗留的本地 Next.js 验证进程占用；
  - 停止该本地进程链并确认端口释放后重跑，Playwright `6/6`。
- `docker compose -f deploy/docker-compose/api.compose.yml config --services`：
  `postgres`、`jstudy-worker`、`jstudy-api`。
- `git diff --check`：通过。

## 5. 精确变更文件

- `.env.example`
- `README.md`
- `deploy/docker-compose/api.compose.yml`
- `docs/architecture/overview.md`
- `docs/deployment/server-runbook.md`
- `docs/roadmap.md`
- `packages/core/jstudy_core/job_system/worker.py`
- `packages/core/jstudy_core/materials/__init__.py`
- `packages/core/jstudy_core/materials/generation.py`
- `packages/core/jstudy_core/materials/scheduling.py`
- `packages/core/jstudy_core/pipeline.py`
- `packages/core/jstudy_core/settings.py`
- `tests/test_deployment_files.py`
- `tests/test_job_worker.py`
- `tests/test_material_generation.py`
- `tests/test_material_scheduling.py`
- `tests/test_mvp_runner.py`
- `tests/test_settings.py`
- `multi-agent/jstudy-product-build/reports/0011-generation-latency-reliability-report.md`

## 6. 可靠性与兼容性

- `ThreadPoolExecutor` 的 worker 数不超过配置与章节数中的较小值。
- 调度器收到异常后取消尚未开始的 futures，并等待已经开始的调用收敛后
  抛出原异常；pipeline 不构造部分 Package。
- Worker 原子完成边界、lease、retry、artifact hash 与 section persistence
  合同未改变。
- 既有 runner 调用方通过默认值 `3` 保持源码兼容。
- 新增 timing 字段位于既有 trace 私有 artifact，不进入公开 API schema，
  且列表规模受 Learning Unit 合同约束。

## 7. 残余风险与 Verdict 请求

- 按任务边界未调用 live Provider，也未访问真实凭据。
- 未修改或验证腾讯云、Cloudflare、Nginx、DNS 或远程 staging。
- deterministic fake 只能证明并发、顺序和失败合同，不能证明真实模型延迟。
- Worker 副本数量会乘以单 Job 并发上限，部署时仍需按 Provider rate limit
  设置副本数。
- Supervisor 仍需用同一六页 DeepSeek V4 Flash staging 样本运行三次，
  核验 created-to-completed 中位数不超过 25 秒、任一单次不超过 35 秒、
  6/6 sections、内容评分至少 85/100 和全部 artifact hash。
- 因真实 staging 性能门禁尚未执行，本任务请求 verdict：
  `PASS_WITH_LIMITATIONS`，不请求 `PASS`。

包含本报告的最终提交 SHA 无法在提交创建前自引用，精确 final SHA 在
Supervisor handoff 中回传。
