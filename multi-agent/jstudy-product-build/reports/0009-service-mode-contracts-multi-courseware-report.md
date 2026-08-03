# Task 0009 三种工作流合同与多课件后端报告

## 1. Phase 0 基线

- Task card：`multi-agent/jstudy-product-build/task_cards/0009-service-mode-contracts-multi-courseware.md`
- Implementation plan：`docs/superpowers/plans/2026-08-03-service-mode-contracts-multi-courseware.md`
- Branch：`feature/backend-frontend-mvp`
- Exact start SHA：`861e42f8f8721185edaa02308dd8ebb2da47e62f`
- Start commit：`文档：准备多课件后端工作流任务`
- Documentation baseline：`6389199`
- `6389199..861e42f` 只包含实施计划、任务卡和 session registry 更新。
- 开始时既有受保护状态：
  - modified：`multi-agent/jstudy-product-build/reports/supervisor_review.md`
  - untracked：`.superpowers/`、`frontend/`、`game/`、`images/`、`outline_mode/`、`scripts/`
- 上述受保护内容不得修改、stage、提交、移动或清理。

## 2. 权威合同

- `single_courseware`：只接受一个 singular multipart `pdf`；拒绝 `outline` 与 repeated `pdfs`。
- `course_outline`：要求一个 `outline` 和至少一个 repeated multipart `pdfs`；拒绝 singular `pdf`。
- `multi_courseware`：要求至少两个 repeated multipart `pdfs`；拒绝 `outline` 与 singular `pdf`。
- 三种模式互斥，不做服务端转换；非法请求不得创建 Job 或残留 input directory。
- Worker 继续强制使用 MinerU；metadata-only `mode`、scenario 行为和 parser alias 语义不扩展。
- 当前继续使用真实可用的 `medicine-default`，不切换到空白 `general-default`。
- `multi_courseware` 只实现按上传显示顺序推进的 sequence-first 基线。跨课件关联算法仍为实验决策，本任务不实现关联发现、评分、生成、图或 UI 合同。

## 3. 实施与验证

### Task 1：严格模型合同

- RED：`python -m unittest tests.test_courseware_models tests.test_material_models -v`
  因 `multi_courseware` 不在 Manifest 与 Package v2 Literal 中失败。
- GREEN：`16/16`。
- 实现：
  - `CoursewareManifestV1` 严格区分 single、outline、multi 的来源数与
    outline shape；
  - `MaterialPackageV2` 接受 `multi_courseware`；
  - `LegacyMaterialPackageV1` 不扩展 multi。
- 提交：`b2bcde1 功能：增加三种资料工作流严格合同`。

### Task 2：API 与 Job admission

- RED：合法的 single+outline 旧兼容仍被接受，multi 被拒绝，混合 multipart
  字段被静默忽略，`/api/options` 缺少三种 service mode。
- GREEN：
  `python -m unittest tests.test_job_service tests.test_web_mvp tests.test_security_controls -v`
  为 `79/79`。
- 实现：
  - single 只接受 singular `pdf`；
  - course outline 只接受一个 `outline` 与 repeated `pdfs`；
  - multi 只接受至少两个 repeated `pdfs`；
  - 禁止字段与混合 multipart family 返回结构化 400；
  - 拒绝请求不创建 Job、input directory 或 idempotency row；
  - multi 保留 `S001`、`S002` 和 admission-time upload order；
  - `/api/options` 公开三种 enabled service mode，默认 single。
- 提交：`9380b77 功能：收紧工作流上传与准入边界`。

### Task 3：sequence-first multi pipeline

- RED：`python -m unittest tests.test_mvp_runner -v` 因缺少
  `run_multi_courseware` 导入失败。
- GREEN：`31/31`。
- 实现：
  - 新增 `run_multi_courseware`；
  - 只消费 Worker 提供的 `ParsedDocument`、Manifest、Learning Map 与
    Coverage Ledger；
  - 复用 sequence-first 生成，Manifest `display_order` 控制主顺序；
  - 不调用 parser、BM25/embedding、RRF 或关联算法；
  - 不产生 association 输出。
- 提交：`fd11591 功能：增加多课件顺序生成管线`。

### Task 4：Worker 与既有结果 API

- RED：
  - Worker 与 HTTP 终态测试均因 `JobWorker.__init__()` 不接受
    `multi_runner` 而失败；
  - 这是新增测试到达的预期生产缺口。
- GREEN：
  `python -m unittest tests.test_job_worker tests.test_web_mvp -v`
  为 `90/90`。
- 实现：
  - 新增默认且可注入的 `multi_runner=run_multi_courseware`；
  - settings snapshot 克隆继续透传同一个 multi runner；
  - 仅 `multi_courseware` dispatch 到 multi runner；
  - 两份 ordered source 复用一次 MinerU batch parse；
  - 复用冻结 Manifest/Map/Coverage 校验、artifact hashing、Package v2
    校验、lease/heartbeat 与原子完成事务；
  - package service mode 错配或同步产物被 runner 篡改时永久
    `invalid_job_output`，不写 artifacts/sections；
  - 完成后 status、package、manifest、learning-map、coverage、
    source-specific PDF preview 与 Markdown export 继续通过 owner-scoped
    既有 endpoint。
- 提交：`8fefaf9 功能：接入多课件 Worker 正式路径`。

## 4. 明确未实施

- 不实现跨课件关联发现、候选生成、相似度评分、模型验证、关系图或 UI。
- 不改变 embedding 的辅助边界；embedding 不控制主资料顺序。
- 不修改 `apps/web/**`、`deploy/**`、数据库结构或 MinerU-only Worker
  决策。
- 不启用空白 `general-default`；继续使用可用的
  `medicine-default`。
- 不做 live MinerU、真实 PostgreSQL/container 或部署 smoke。

## 5. 完整验证

首次完整 backend discovery 为 `378/379`，唯一失败来自
`tests/test_courseware_planning.py` 的旧 fixture：它用
`course_outline` 构造无 outline 的两来源 Manifest。严格合同生效后该
shape 必须拒绝，因此将 fixture 改为语义一致的 `multi_courseware`。
该文件不在首选 allowed tests 列表中，但这是恢复完整回归且不放宽生产
合同所必需的测试修正。

修正 fixture 后：

- `python -m compileall -q apps packages`：通过；
- `python -m unittest discover -s tests -v`：`379/379`；
- `apps/web` `npm run lint`：通过；
- `apps/web` `npm run typecheck`：通过；
- `apps/web` `npm test`：Vitest `5/5`；
- `apps/web` `npm run build`：Next.js production build 通过；
- `apps/web` `npm run test:e2e`：Playwright `6/6`；
- `git diff --check`：通过。

## 6. 精确变更文件

生产代码：

- `apps/api/jstudy_api/app.py`
- `packages/core/jstudy_core/courseware/models.py`
- `packages/core/jstudy_core/job_system/service.py`
- `packages/core/jstudy_core/job_system/worker.py`
- `packages/core/jstudy_core/materials/models.py`
- `packages/core/jstudy_core/pipeline.py`

测试：

- `tests/test_courseware_models.py`
- `tests/test_courseware_planning.py`
- `tests/test_job_service.py`
- `tests/test_job_worker.py`
- `tests/test_material_models.py`
- `tests/test_mvp_runner.py`
- `tests/test_web_mvp.py`

文档与报告：

- `README.md`
- `docs/architecture/overview.md`
- `docs/product/service-modes.md`
- `docs/roadmap.md`
- `multi-agent/jstudy-product-build/reports/0009-service-mode-contracts-multi-courseware-report.md`

## 7. 残余风险

- 未调用 live MinerU；自动测试使用 fake/mocked document service，不能代替
  provider smoke。
- 未做真实 PostgreSQL、container 或部署 smoke。
- multi 的当前顺序是 admission-time upload/display order；正式前端
  Organizer、用户确认排序和重命名尚未实现。
- 跨课件关联算法尚未选型或实现，当前 Package 不产生 association 输出。
- `apps/web` 尚未接入三种正式工作流入口，本任务只回归既有 foundation。
- `general-default` 仍是空白占位，运行时继续使用
  `medicine-default`。

包含本报告的最终提交 SHA 无法在提交创建前自引用，精确 final SHA 在
Supervisor handoff 中回传。

## 8. Fresh review corrective patch

### 基线与范围

- Task 0009 原 final：`5dc70edce9e6ec055f630061868398099ee1bbcd`。
- corrective 开始时 HEAD：
  `cd5a92f2d2c426afa856b18065cb067d541a46b7`。
- `cd5a92f` 只新增 Supervisor 的认证闭环计划；corrective 未回退、改写
  或 stage 该提交。
- 受保护 dirty/untracked 内容保持原样。

### 重复 scalar multipart

- RED：
  - single 同名 `pdf` 提交两次返回 200 并创建 Job；
  - course outline 同名 `outline` 提交两次返回 200 并创建 Job。
- 修复：在 route 内读取 Starlette 原始 form multi-dict，通过
  `getlist()` 在 JobService admission 前核对 scalar cardinality。
- GREEN：两种重复字段均返回结构化 400；repository 无 queued Job，
  jobs root 无 input directory，owner/idempotency key 无记录。
- repeated `pdfs` 继续保持合法多值语义。

### Package 与冻结 coordination 完整性

- RED：multi Package 的 source 遗漏、source 逆序、section 遗漏和
  section 逆序均被 Worker 错误完成。
- 修复：新增共享 `validate_material_package_coordination()`，Worker 在
  原子完成前核对：
  - `package.source_ids` 与 Manifest ordered source 完全相等且同序；
  - Package sections 与 Learning Map ordered units 数量、位置一一对应；
  - `section.id == unit.material_section_id`；
  - `section.order == unit.order`；
  - `section.source_ids == [unit.primary_source_id]`。
- GREEN：四类错配均永久 `invalid_job_output`，不写 artifacts/sections；
  合法 single、outline、multi v2 path 继续完成。
- 测试 fake runner 改为从真实 frozen Learning Map 构造 `unit-*`
  section identity，避免 pre-sequence fixture 绕开合同。

### Corrective 验证

- focused Worker/Web：`93/93`；
- `python -m compileall -q apps packages`：通过；
- backend full：`382/382`；
- frontend lint、typecheck：通过；
- Vitest：`5/5`；
- Next.js production build：通过；
- Playwright 首次因已有 PID 占用 3000、测试 server 改用 3001 而失败；
  该进程随后自行退出，确认 3000 无监听后重跑：`6/6`；
- `git diff --check`：提交前最终检查。

### Corrective 精确文件

- `apps/api/jstudy_api/app.py`
- `packages/core/jstudy_core/job_system/worker.py`
- `packages/core/jstudy_core/materials/__init__.py`
- `packages/core/jstudy_core/materials/validation.py`
- `tests/test_job_worker.py`
- `tests/test_web_mvp.py`
- `multi-agent/jstudy-product-build/reports/0009-service-mode-contracts-multi-courseware-report.md`
