# Task 0007 Material Package v2 后端完成报告

## 1. Task

- Task card：`multi-agent/jstudy-product-build/task_cards/0007-material-package-v2-backend.md`
- Source thread：`019fa956-f165-76b0-b49d-9462d2f52328`
- Code Agent thread：`019efec4-1e17-7443-8496-c1fea5d6bcb5`
- Status：`completed`
- 生产/测试代码基线：`28acb39dffffc9214791d3f94cda46c18810923b`
- Supervisor planning commit：`3c14be134c0eb589b43fbe34d58d3fd830533135`
- 基线核对：`28acb39..3c14be1` 仅包含实施计划与 Task 0007 任务卡，`822` 行新增，`git diff --check` 通过。
- 阶段提交：
  - `4cc0abc 功能：定义资料包 v2 类型合同`
  - `b342527 功能：校验资料包证据并生成兼容文本`
  - `19cfed2 功能：增加结构化章节生成与受控修复`
  - `c6165fb 功能：让现有生成管线输出资料包 v2`
  - `d128cfc 功能：持久化并公开资料包 v2`
  - `7a71086 修复：加强资料包读取与格式指令`
- Corrective baseline：`c5fab8ff33a0333e2e5dccaa8816ed61b191beb2`
- Fresh review verdict：`REVISE`
- 最终 SHA：本报告所在提交不能在提交自身中自指，以 Supervisor 回报中的完整 SHA 为准。

## 2. Summary

- 为 `material-package.v2` 建立真正的 strict Pydantic contract，所有公开模型禁止未知字段和 JSON primitive 类型强制转换；首期只允许受控 heading、paragraph、list、table、callout、formula blocks 和六类 inline runs。
- 落实 section/block 稳定 identity、heading/callout 枚举、文本长度、block 数量和 table 行列上限；只有 `failed` section 可以没有 blocks。
- 共享 validator 校验 Job/package/section identity、evidence id 唯一性、evidence source 归属和 citation run 引用；新增稳定错误码包括 `package_id_mismatch`、`service_mode_mismatch`、`invalid_evidence_id`、`duplicate_evidence_id`、`invalid_evidence_source_id`、`evidence_source_not_in_job`、`evidence_source_not_in_package`、`evidence_source_not_in_section`。
- quality 不再解析 Markdown，而是直接遍历 typed blocks/citation runs，确定性计算 `evidence_count`、`cited_evidence_count`、`citation_coverage`，并校验 `evidence_status` 与 section status。浮点覆盖率使用绝对误差 `1e-9`、相对误差 `0`。
- 新增 SiliconFlow JSON-object helper，发送 `response_format={"type":"json_object"}`；JSON 或 schema 错误最多进行一次受控重新生成，修复提示只包含安全的字段位置/错误类型，不回显原始模型响应或 credential。
- 无 evidence 的 outline section 不调用 provider，确定性生成 `weak_evidence` note；第二次格式仍失败时生成无模型正文的确定性 `failed` section。网络/provider 异常继续向 Worker 传播以使用现有重试策略。
- `single_courseware` 与 `course_outline` 均先生成并验证 v2，再派生 quality、兼容 Markdown 和 evidence links；不再并行生成独立 Markdown。single section id 保持 `full-material`，course outline id/order 保持解析结果，source identity 使用 `S001`、`S002`。
- Worker 将 `job.id` 传为 `package_id`，用共享 v2 contract 和 Job-owned source/evidence 再校验；sections、artifacts 与 completed transition 继续通过既有 lease-protected transaction 原子写入。
- Worker 保留小型 legacy v1 分支；v2 wrong package/service identity、unknown source/evidence、duplicate identity、quality/status 不一致或 malformed schema 均以 `invalid_job_output` 失败，不提交 artifacts/sections。
- `GET /api/jobs/{job_id}/package` 保持 owner check 与 private cache，返回 validated v2 或 bounded legacy v1。Worker/API 使用同一个最多 `2 MiB` 的 package artifact reader；legacy v1 限制为最多 `120` sections/source files、每 section 最多 `120` source files、`1000` evidence ids、`64` quality keys 和 `32 KiB` quality JSON，另有限定 id/title/status/filename 长度。
- API readback 通过共享入口同时核对 persisted v2 的 `package_id`、`service_mode`、Job-owned sources/evidence 与确定性 quality/status；内部异常仍统一返回安全的 `500 / Material package is invalid`。
- 兼容 Markdown 对普通文本与标题中的 HTML-like 内容做转义；结构化 citation 仍确定性转成 `<!-- evidence: E001 -->`，保持现有 citation jump 和 `/output`、`/export` 合同。

## 3. Changed Files

- `README.md`：记录 v2 主产物、Markdown 派生兼容输出、owner-scoped typed package API 与 legacy v1 读取。
- `apps/api/jstudy_api/app.py`：增加 v2/legacy typed response union、persisted v2 schema 与 source/evidence 再校验。
- `docs/architecture/overview.md`：更新 typed generation、直接质量审计、兼容 Markdown 和未切 MinerU/HTML/迁移边界。
- `docs/roadmap.md`：记录 Task 0007 完成项与延期项。
- `multi-agent/jstudy-product-build/reports/0007-material-package-v2-backend-report.md`：本报告。
- `packages/core/jstudy_core/job_system/worker.py`：传递 Job package id，增加共享 v2 validation/persistence 分支并保留 legacy v1。
- `packages/core/jstudy_core/materials/__init__.py`：集中导出资料包公开合同。
- `packages/core/jstudy_core/materials/compatibility.py`：确定性生成兼容 Markdown，并转义 HTML-like 普通文本。
- `packages/core/jstudy_core/materials/generation.py`：结构化 section generation、一次受控修复、weak/failed 确定性 fallback。
- `packages/core/jstudy_core/materials/models.py`：严格 v2 models、discriminated unions 和 bounded legacy v1 models。
- `packages/core/jstudy_core/materials/validation.py`：source/evidence/citation 交叉引用与直接 quality audit。
- `packages/core/jstudy_core/pipeline.py`：两条现有 pipeline 改为 v2-first，并保留 additive runner 参数和兼容 artifacts。
- `packages/core/jstudy_core/providers.py`：新增 bounded `generate_json_object()`，保留原 `generate_markdown()`。
- `packages/core/jstudy_core/scenario_router.py`：把 resolved subject 放入 trace metadata。
- `tests/test_job_worker.py`：覆盖 v2 原子完成、package id、invalid v2、legacy v1 和无半完成写入。
- `tests/test_material_generation.py`：覆盖交叉引用、quality、Markdown、JSON mode、repair、安全错误和 deterministic fallback。
- `tests/test_material_models.py`：覆盖完整 v2 block/run contract、strict fields、identity 和资源上限。
- `tests/test_mvp_runner.py`：覆盖双 service mode v2、stable source、派生 Markdown/quality/links 和 additive generator。
- `tests/test_scenario_router.py`：覆盖 resolved subject trace。
- `tests/test_web_mvp.py`：覆盖 owner v2 read、persisted tamper rejection、legacy read 和 OpenAPI schemas。

### Corrective Patch 精确文件

- `apps/api/jstudy_api/app.py`
- `packages/core/jstudy_core/job_system/worker.py`
- `packages/core/jstudy_core/materials/generation.py`
- `packages/core/jstudy_core/materials/models.py`
- `packages/core/jstudy_core/materials/validation.py`
- `tests/test_job_worker.py`
- `tests/test_material_generation.py`
- `tests/test_material_models.py`
- `tests/test_web_mvp.py`
- `multi-agent/jstudy-product-build/reports/0007-material-package-v2-backend-report.md`

## 4. Verification

- Phase 1 RED：`tests.test_material_models` 因 `packages.core.jstudy_core.materials` 不存在而导入失败；实现后 `5/5` GREEN。
- Phase 2 RED：`tests.test_material_generation` 因 `materials.compatibility` 不存在而导入失败；validation/quality/Markdown 实现后与 models 合计 `12/12` GREEN。
- Phase 3 RED：`materials.generation` 不存在；JSON mode、一次 repair、safe summary、provider exception、weak/failed tests 实现后合计 `19/19` GREEN。
- Phase 4 RED：两条 runner 不接受 `package_id`/`section_generator`，scenario trace 无 `subject`，共 `5` 个预期错误；实现后 focused suite `54/54` GREEN。HTML-like 文本测试首次因单引号被过度转义而失败，改为 `quote=False` 后全部通过。
- Phase 5 RED：Worker 未传 `package_id` 且仍按 v1 解析，导致 v2 完成、五类 invalid v2 和 API typed read 共 `7` 个失败；实现后 Worker/API/security suite `74/74` GREEN。
- 最终 persisted package source/evidence 再校验与 mandatory system-level format instruction 回归：`62/62` 通过。
- Corrective RED：
  - evidence `source_id=S999`、duplicate evidence id、Package/Section source 错配均被旧 validator 接受；
  - persisted `SectionQuality`/status 篡改被旧 validator 接受；
  - `order=true`、numeric string、string boolean 被 Pydantic 强制转换；
  - legacy `121` sections、`501` 字符 title、超限 list/dict/quality JSON 共 `6` 个边界被接受；
  - Worker/API package 读取在 `json.loads` 前无统一字节上限。
- Corrective GREEN：
  - models/generation focused：`28/28` 通过，包括 provider coercion 失败只进行一次 repair；
  - Worker/API focused：`4/4` 通过，invalid output 不落 artifacts/sections，API 只返回安全错误；
  - shared validator 的 Job/package/section source、duplicate evidence、identity、quality/status 组合回归全部通过。
- `python -m compileall -q apps packages`：通过。
- `python -m unittest discover -s tests -v`：`328/328` 通过。
- `npm run lint`：通过。
- `npm run typecheck`：通过。
- `npm run test`：Vitest `2` 个文件，`5/5` 通过。
- `npm run build`：Next.js production build 通过。
- `npm run test:e2e`：Playwright desktop/tablet/mobile `6/6` 通过。
- `git diff --check`：通过。
- scope audit：未修改或 stage `apps/web/**`、deployment、database schema/migration、MinerU pipeline/default、`data/`、Supervisor-owned `supervisor_review.md` 或六个排除目录。

## 5. Risks and Limitations

- 未进行真实 SiliconFlow JSON-mode 请求；JSON request/response、repair 次数和异常边界均使用 deterministic mock 验证，部署阶段仍需 live provider smoke。
- 未重复执行真实 PostgreSQL/API/Worker 容器 smoke；原子完成与 stale lease 由 repository/Worker 自动测试验证，但不以 SQLite 结果宣称 PostgreSQL 实机验证。
- legacy v1 仅提供迁移期 bounded read；package artifact 最大 `2 MiB`，上限不是通用迁移框架。新 Job 一律生成 v2，legacy 删除仍需单独审查。
- `failed` section 是可持久化的 package-level 质量状态，不自动改写为 Worker 基础设施错误；消费者应读取 package/quality issues。
- Markdown 仍是六类必需公开 artifact 之一，只能由 v2 派生；本任务未删除旧 Markdown helper 或 compatibility API。
- 未实施 React/HTML renderer、HTML export、视觉主题、Batch Courseware、MinerU pipeline switch、数据库迁移、部署或 CLI cleanup。
- 未修改 `apps/web/**`；现有 frontend reader 仍消费当前兼容合同，正式 typed block renderer 属于后续任务。
- 未执行 push、merge、rebase、reset 或 clean。Supervisor-owned dirty file 与排除目录保持在提交之外。

## 6. Requested Supervisor Action

请独立复核最终提交，并给出 fresh verdict：

`PASS` / `PASS_WITH_LIMITATIONS` / `REVISE` / `REJECT`
