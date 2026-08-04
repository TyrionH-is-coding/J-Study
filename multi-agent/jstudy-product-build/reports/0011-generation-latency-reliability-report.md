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

## 8. Live staging REVISE corrective

### 8.1 Corrective baseline

- 委派要求先执行
  `git fetch origin feature/backend-frontend-mvp`，已执行。
- 委派文本中的短标识 `ab1e8469d8b` 无法由 Git 解析。
- fetch 后本地 HEAD 与
  `origin/feature/backend-frontend-mvp` 均为唯一匹配 Task 0011 验收报告的
  提交：
  `ab1e846b4f7ae6aa7acde225721440dfad8f445f`
  （`文档：记录 V4 Flash 并发生成验收`）。
- corrective start SHA 因此记录为上述完整 SHA；本地与远端分叉计数为
  `0/0`。
- 开始时既有受保护 modified/untracked 内容与原报告一致，corrective
  未覆盖、stage、提交、移动或清理这些内容。

### 8.2 Supervisor live 证据

- 三次 server created-to-finished 为 `34.701s`、`36.046s`、`25.892s`；
  中位数 `34.701s`，最大值 `36.046s`，未通过 `25s/35s` 门禁。
- Run 1 只有 `5/6` sections，quality fail，人工 `79/100`；其余两次为
  `6/6`、`92/100` 与 `90/100`。
- `30/30` artifact hashes 匹配，trace 证明并发 `3` 已生效。
- Run 1 `unit-003` 两次结构/语义验证后进入空 failed section，旧 trace
  没有最终安全 validation code。
- 成功结果仍出现同一七步流程的完整列表/表格重复，证明 prompt-only
  规则不足。

### 8.3 安全诊断与局部恢复

- RED：
  - generation 无 diagnostic outcome；
  - scheduler timing 只有 id/order/status/duration；
  - trace 没有 Provider 调用硬上限；
  - 两次验证失败后立即产生 failed section。
- GREEN：
  - 每节 trace timing 新增 `attempt_count`、`failure_category` 和
    `failure_code`；
  - Provider JSON、Material validation 和 Pydantic schema code 分别使用
    固定 allowlist；任何未知 code 归一化为对应固定 fallback；
  - 不记录 prompt、正文、evidence、Provider 原始响应、URL、key 或异常
    正文；
  - 前两次格式/结构验证均失败后，只对当前失败节进行一次第三次定向恢复；
  - 成功节不重复调用；运行时 Provider 异常仍立即上抛并走既有 Worker
    retry/permanent 语义；
  - 单节单次 claim 的 Provider 调用硬上限为 `3`，包含正常调用、一次格式
    修复和一次定向恢复；N 个 Learning Unit 的单次 claim 上限为 `3 * N`；
  - 结构化章节生成显式设置 transport retries 为 `0`，因此一次逻辑尝试
    只产生一次 HTTP 请求，trace 上限与实际传输次数一致；
  - 可重试 Provider 运行时故障仍可按既有 Worker Job retry 开启新 claim，
    因此整个 Job 生命周期的理论硬上限为
    `3 * N * worker_max_attempts`；格式/结构局部恢复不会重跑成功节；
  - 局部仍失败时保留原位置的空 failed section；trace 同时记录
    `non_failed_section_count` 与 `failed_section_count`，不把 section 总数
    伪装为成功数；
  - Worker 并发异常回归继续证明：取消未启动工作，等待已启动调用收敛，
    不写 artifacts、sections 或 completed transition。
- 提交：
  - `9365cf7 修复：增加章节定向恢复与安全诊断`
  - `89ca5af 修复：明确章节局部失败计数`

### 8.4 默认并发调整

- RED：四并发调度已经可用，但 RuntimeSettings、Compose、`.env.example`
  和文档默认仍为 `3`。
- GREEN：
  - 默认值改为 `4`，合法范围继续为 `1..4`；
  - `Event` 确定性测试证明六个任务恰好有四个同时活动，未创建无界线程；
  - 显式值 `3` 的并发/顺序测试继续保留；
  - 值 `1` 继续提供串行回滚；
  - 一个 Worker 最多有该值个活动 section calls；多个 Worker 的 Provider
    活动调用上限为该值乘以 Worker 副本数。
- 未增加额外 Worker、无界线程或 speculative Provider calls。
- 提交：`a1927b0 性能：将章节并发默认上限调整为四`。

### 8.5 确定性重复规整

- RED：相同两步 workflow、相同逐条 citation 的完整列表与完整表格均被
  保留。
- GREEN：
  - 只在同一 section 内比较 list items 与 table rows；
  - 只规整单列表格，避免忽略多列边界中的新增信息；
  - 每个 inline run 的 type/value/order 必须逐项完全相同，只折叠空白，
    保留标点、公式与 citation 位置；
  - citation 对应关系必须完全相同且整体非空；
  - 满足上述条件时保留 table、移除 list；
  - 表格增加新信息或逐行 citation 归属变化时，两种表达均保留。
- 这不是模糊匹配或通用语义去重系统。
- 提交：
  - `a67648f 修复：规整列表与表格完全重复表达`
  - `9a23bcc 修复：收紧重复表达的证据对应`
  - `2c674ec 修复：收紧生成调用上限与安全规整`

### 8.6 Corrective focused verification

- scheduler、generation、pipeline、settings、Worker、deployment：
  `151/151`。
- `python -m compileall -q apps packages`：通过。
- backend full：`409/409`。
- `apps/web` lint、typecheck：通过。
- Vitest：`5/5`。
- Next.js production build：通过。
- Playwright：`6/6`。
- Compose services：`postgres`、`jstudy-api`、`jstudy-worker`。
- corrective range 与 worktree `git diff --check`：通过。
- corrective range 只包含本节列出的 18 个允许文件。
- 最终 status 只保留 corrective 开始前已记录的受保护
  modified/untracked 内容。

### 8.7 Corrective 精确文件

- `.env.example`
- `README.md`
- `deploy/docker-compose/api.compose.yml`
- `docs/architecture/overview.md`
- `docs/deployment/server-runbook.md`
- `docs/roadmap.md`
- `packages/core/jstudy_core/materials/__init__.py`
- `packages/core/jstudy_core/materials/generation.py`
- `packages/core/jstudy_core/materials/scheduling.py`
- `packages/core/jstudy_core/pipeline.py`
- `packages/core/jstudy_core/providers.py`
- `packages/core/jstudy_core/settings.py`
- `tests/test_deployment_files.py`
- `tests/test_material_generation.py`
- `tests/test_material_scheduling.py`
- `tests/test_mvp_runner.py`
- `tests/test_settings.py`
- `multi-agent/jstudy-product-build/reports/0011-generation-latency-reliability-report.md`

### 8.8 Corrective residual risks

- 本轮未访问 staging、SSH、Cloudflare、Nginx、DNS、真实 Provider 或凭据，
  也未提交 live Job。
- 默认并发 `4` 与第三次定向恢复可能增加瞬时 Provider 压力；硬上限和
  Worker 副本乘数已明确，但仍需按真实 Provider rate limit 验证。
- 精确重复规整有意保守，不处理措辞不同但语义重复的内容。
- 独立只读审查首次发现 transport retry、重复签名和诊断 allowlist 三项
  P1/P2；均补 RED 后由 `2c674ec` 修正。修正后 focused、backend full 与
  frontend 全套重新执行。
- 二次独立只读复核确认三项 finding 均关闭，相关离线回归 `7/7`，未发现
  新的 P0-P2。
- 不能从 deterministic tests 宣称真实延迟、6/6 完整性或人工质量门禁
  已通过。
- corrective 完成后仍只请求 `PASS_WITH_LIMITATIONS`；Supervisor 必须
  重新运行三次相同 live staging 样本后再判断真实性能门禁。

## 9. 去重边界 fresh REVISE corrective

### 9.1 Baseline 与范围

- Exact corrective baseline：
  `bd566721f8869bbb0bca7e5e6d97af4d8cb43063`。
- Supervisor 已确认诊断、单节三次调用上限、定向恢复、默认并发 `4` 和
  allowlist 均正确；本轮不修改这些合同。
- 未访问 SSH、staging、Provider、Cloudflare、Nginx、DNS 或凭据，也未
  提交 live Job。
- 生产与测试修改严格限制为：
  - `packages/core/jstudy_core/materials/generation.py`
  - `tests/test_material_generation.py`
- 本报告是唯一额外文档文件。

### 9.2 RED

- `ordered=True` list 与相同单列表格被错误去重，流程显式顺序丢失。
- `heading A -> list -> heading B -> table` 被全 section signature set
  跨 heading 匹配，输出留下 heading 但删除其内容。
- list/table 中 `inline_code` 的双空格与单空格被折叠为相同。
- list/table 中 `inline_formula` 的空白差异被折叠为相同。
- 正向控制：局部相邻的 unordered list 与逐 run 完全相同单列表格应继续
  只保留 table。

五项定向测试首次运行结果：四个反例失败，正向控制通过，证明测试到达
Supervisor 复现的生产缺口。

### 9.3 GREEN

- `ordered=True` list 的去重签名固定为不可用，永远不会因 table 被删除。
- 删除全 section signature set；改为从左到右扫描原 block 序列，只比较
  直接相邻且类型集合恰好为 `{list, table}` 的 pair。
- heading、callout、paragraph 或任何其他 block 都会切断匹配，因此不会
  跨作用域删除，也不会产生本轮去重导致的空 heading。
- `text`、`strong`、`emphasis` 只折叠空白后比较。
- `inline_code` 与 `inline_formula` 保留原字符串，逐字符比较。
- citation identity、run type、run value 和 run order 继续精确比较。
- 保持既有保守边界：只处理单列表格、非空逐 run 完全相同且含 citation
  的相邻 unordered list/table；多列表格、新增信息、标点变化和 citation
  归属变化继续保留。
- generation focused：`37/37`。
- `python -m compileall -q apps packages`：通过。
- backend full：`413/413`。
- `apps/web` lint、typecheck：通过。
- Vitest：`5/5`。
- Next.js production build：通过。
- Playwright：`6/6`。
- 提交：`e9d4cf8 修复：限制重复规整为相邻无序列表`。

### 9.4 Residual risk

- 该规整有意保守，不处理非相邻或措辞不同的语义重复。
- 本轮不声称真实性能门禁通过，仍请求 `PASS_WITH_LIMITATIONS`，等待
  Supervisor 重新执行 live staging。
