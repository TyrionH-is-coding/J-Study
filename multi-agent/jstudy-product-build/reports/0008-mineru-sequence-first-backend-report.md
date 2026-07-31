# Task 0008 MinerU 顺序优先后端完成报告

## 1. Task

- Task card：`multi-agent/jstudy-product-build/task_cards/0008-mineru-sequence-first-backend.md`
- Source thread：`019fa956-f165-76b0-b49d-9462d2f52328`
- Code Agent thread：`019efec4-1e17-7443-8496-c1fea5d6bcb5`
- Status：`completed`
- 起始基线：`6f915dd92a0587348b9c5c234f311b241f0f6f8f`
- Corrective baseline：`633d15db1f0a30e3a797e3215b1e32ebd062e923`
- 第二轮 corrective baseline：`285aa8437378abe9d7aa3a6a062700f6d258600f`
- 最终 SHA：本报告所在提交不能在提交自身中自指，以 Supervisor 回报中的完整 SHA 为准。
- 基线核对：分支为 `feature/backend-frontend-mvp`；开始时仅有 Supervisor-owned `supervisor_review.md` 修改及任务卡列明的六个 untracked 排除目录，实施期间未修改、stage 或清理这些内容。
- 阶段提交：
  - `3903ebf 功能：增加课件清单与学习映射合同`
  - `f595312 功能：分离课件来源身份与显示顺序`
  - `d004036 功能：接入统一 MinerU 文档解析服务`
  - `8ec4c5c 功能：按课件顺序规划连续学习单元`
  - `ac84895 功能：让任务 Worker 使用 MinerU 有序文档`
  - `4f01054 功能：按连续课件单元生成完整资料`
  - `070a096 功能：公开课件同步资料合同`

## 2. 实现摘要

- 新增 strict `courseware-manifest.v1`、`learning-map.v1`、`coverage-ledger.v1` Pydantic 合同，拒绝未知字段、类型强制转换、重复 identity/order、跨 source block 和不一致 coverage metrics。
- `job_sources` 将稳定 `source_id` 与 `display_title`、`display_order`、outline mapping 及 origin metadata 分离。默认显示标题来自上传文件 stem，默认顺序来自上传次序。
- `MinerUDocumentService` 对一个 Job 的所有 PDF（以及 PDF outline）执行一次批量 MinerU 调用，校验返回 source 集合并恢复 J-Study 请求顺序；每个 ZIP 经安全 normalizer 转成 `ParsedDocument`。
- MinerU 提交前重新计算 Job-owned PDF SHA256 并与 admission identity 比对；内容被替换时以 permanent `source_identity_mismatch` 终止，不能让旧 identity 指向新内容。
- MinerU provider 错误分为 permanent rejection 与 retryable availability：401/403、provider 非零 code、明确 extraction failed 不重试；transport、429、5xx 继续使用有界 retry。
- PyMuPDF 只用于 PDF 校验、页数、metadata 和预览；Worker 不再调用 PyMuPDF 文本抽取，也没有 MinerU 失败后的文本抽取 fallback。
- 确定性 planner 按 Manifest display order、source page 和 block order 构造连续 Learning Unit；每个 normalized block 在 Coverage Ledger 中恰有一个 `used`、`ignored`、`duplicate` 或 `unsupported` disposition。
- `single_courseware` 与 `course_outline` 都按 Learning Map 顺序生成 v2 section。主 evidence 来自 unit 自身连续页段，Embedding/BM25/Top-K 不参与主顺序或 coverage 决策。
- Worker 在当前 lease snapshot 内生成 Manifest/Map/Ledger，将三类工件与既有 package、Markdown、evidence、quality、trace、sections 和 completed transition 一起通过既有原子完成边界提交；过期 lease 不能发布。
- shared coordination validator 核对 Coverage block/source/page identity、Manifest source、Learning Unit 与 used disposition 的一一对应，并锁定 Manifest display order、同 source page 前进和 ParsedDocument block order；pipeline、`/learning-map` 与 `/coverage` API 都拒绝跨工件不一致。
- `/api/options` 只公开 scenarios。新客户端省略 `parser_profile_id`；空值、`fast`、`quality` 仅为迁移别名，未知值返回 400，任何别名都不会改变 Worker-owned MinerU parser。
- 新增 owner-scoped、private-cache、bounded strict read API：
  - `GET /api/jobs/{job_id}/manifest`
  - `GET /api/jobs/{job_id}/learning-map`
  - `GET /api/jobs/{job_id}/coverage`
- source payload 公开 `source_id`、`original_filename`、`display_title`、`display_order`；不公开 MinerU signed URL、原始 provider JSON、ZIP、token、绝对路径或完整 ParsedDocument。
- citation link 保留 `relation` 与 `navigation_policy`；跨 source 关系可标记为 `cross_source / non_interactive`，不会制造强制跳转。

### Supervisor corrective patch

- MinerU 已是唯一产品解析路径，因此 readiness 新增不泄密的 `mineru` check。缺少 token 时 `/api/readiness` 为 degraded，`POST /api/generate` 在 admission 和上传落盘前返回安全 503；同进程 admin/runtime 热更新后，下一次 submission 立即使用新快照。
- MinerU ZIP 不再以 `bytes[]` 聚合返回。HTTP body 以流式 chunk 写入 job-owned 私有 `downloads/`，normalizer 直接读取 ZIP path；单 ZIP 上限保持 256 MiB，整个 batch 新增 512 MiB 累计上限。ZIP、signed URL 和 provider JSON 均不进入公开 artifact 表。
- Worker 仅关闭自己创建的 `MinerUDocumentService/httpx.Client`，成功、retryable failure 和 permanent failure 都确定性关闭；注入的测试/调用方 service 不由 Worker 关闭。
- shared `validate_manifest_snapshot()` 同时供 Worker 完成前和 `/manifest`、`/learning-map`、`/coverage` 使用，核对 Job identity、service mode、source 集合、文件名、SHA256、显示标题/顺序、outline mapping 与 origin metadata。任何偏差均在 Worker 侧成为 permanent `invalid_job_output`，API 侧统一返回安全 500。
- Job admission 现在持久化 outline 的安全原始文件名、SHA256、byte size 和 MIME。每次 claim 在任何 MinerU/provider I/O 前有界重算 size/SHA；不匹配永久失败且不重试。Manifest 使用持久化原始名和 admission SHA，不再暴露内部 `outline.pdf`/`outline.md` 文件名。

### Supervisor 第二轮 corrective patch

- normalizer 新增同一 Job 共享的 `MinerUBatchBudget`：总解压上限为 512 MiB，私有产物上限为 1 GiB。私有预算同时计算 retained original ZIP 与解压成员，不能再由 20 个分别合法的 ZIP 累积到约 10 GiB。
- `*_content_list.json` 使用独立 16 MiB 上限，并通过 bounded read 后才进入 JSON parse。普通 ZIP 成员统一经 `ZipFile.open()` 以 64 KiB chunk 流式落盘，不再调用 `archive.read(info)` 整成员载入内存。
- 下载 ZIP 在 normalization 成功后直接 move/rename 为 source 私有 `mineru-original.zip`，不再复制第二份。任一 source normalization 失败会删除整个本次 attempt 的 MinerU root，包括前序 source 输出、当前 partial member 和所有 download ZIP。
- Worker 在 runner 前分别 deep-copy 冻结 Manifest、Learning Map、Coverage。runner 返回后严格重读三份 typed artifact，与冻结值精确比较，再调用 shared coordination validator；任一变化永久失败为 `invalid_job_output`，不写 artifacts、sections 或 completed。
- 三个同步 API 共用一个 bundle read boundary，分别按持久化 `JobArtifact.sha256` 验证 Manifest、Learning Map、Coverage，并复用 Manifest/coordination validators。任一依赖 artifact 被篡改时，三个 endpoint 都返回各自现有安全 500，不返回篡改内容。

第二轮 corrective patch 精确文件：

- `apps/api/jstudy_api/app.py`
- `multi-agent/jstudy-product-build/reports/0008-mineru-sequence-first-backend-report.md`
- `packages/core/jstudy_core/documents/mineru_normalizer.py`
- `packages/core/jstudy_core/documents/service.py`
- `packages/core/jstudy_core/job_system/worker.py`
- `tests/test_document_service.py`
- `tests/test_job_worker.py`
- `tests/test_mineru_normalizer.py`
- `tests/test_web_mvp.py`

Corrective patch 精确文件：

- `apps/api/jstudy_api/app.py`
- `multi-agent/jstudy-product-build/reports/0008-mineru-sequence-first-backend-report.md`
- `packages/core/jstudy_core/courseware/__init__.py`
- `packages/core/jstudy_core/courseware/planning.py`
- `packages/core/jstudy_core/documents/mineru_client.py`
- `packages/core/jstudy_core/documents/mineru_normalizer.py`
- `packages/core/jstudy_core/documents/service.py`
- `packages/core/jstudy_core/job_system/models.py`
- `packages/core/jstudy_core/job_system/repository.py`
- `packages/core/jstudy_core/job_system/service.py`
- `packages/core/jstudy_core/job_system/worker.py`
- `packages/core/jstudy_core/settings.py`
- `tests/test_courseware_planning.py`
- `tests/test_document_service.py`
- `tests/test_job_service.py`
- `tests/test_job_worker.py`
- `tests/test_mineru_client.py`
- `tests/test_security_controls.py`
- `tests/test_settings.py`
- `tests/test_web_mvp.py`

## 3. Parser 调用链

```text
POST /api/generate
-> durable Job admission + immutable source identity
-> jstudy-worker claim + RuntimeSettings snapshot
-> JobSourceSnapshot(display order)
-> DocumentSource
-> MinerUDocumentService.parse
-> PyMuPDF validate_pdf/pdf_page_count utility
-> MinerUPrecisionClient.extract(one batch)
-> safe ZIP normalization
-> ParsedDocument[]
-> build_courseware_manifest
-> plan_learning_map + coverage ledger
-> sequence-first runner
-> material-package.v2 + compatibility artifacts
-> lease-protected atomic completion
```

真实 MinerU 请求：`not_run`。未读取真实 token；MinerU transport 测试继续使用 `httpx.MockTransport`，DocumentService/Worker 测试使用注入 fake service。

## 4. RED / GREEN 证据

- Task 1：RED 为 courseware contracts import 失败；GREEN `5/5`。
- Task 2：RED 为 Job source display fields 缺失；GREEN repository/service `66/66`。
- Task 3：RED 为 DocumentService import 失败；GREEN document/client/normalizer/settings `56/56`。
- Task 4：RED 为 planner import 失败；GREEN models/planner `7/7`。
- Task 5：RED 为 Worker 不接受 `document_service`；GREEN worker/repository `75/75`。
- Task 6：RED 为 runner 拒绝 sequence-first kwargs；GREEN pipeline/material/models `59/59`。
- Task 7：RED 显示 options 仍含 parser profiles、source metadata 缺失且新端点不存在；GREEN API/security `50/50`。
- 完整后端初次回归：`345/345`。
- 独立只读审查发现 2 个 P1 与 2 个 P2：source hash 未复核、provider error retry 过宽、Coverage 跨工件 identity 未校验、sequence trace 丢失原始文件名/snippet metadata。
- Corrective RED：缺失 `SourceIdentityError`/provider subtype/shared validator import；Coverage source/page mismatch 未被拒绝；sequence trace 缺少 `source_files`。
- Corrective GREEN：document/client/models/planning/sequence `31/31`，Worker/API error semantics `2/2`。
- 第二轮只读复核的 3 个 P2 已修复：主序列单调性、畸形 download `Content-Length` permanent protocol error、trace `file_name/page_count/parser_backend` 旧字段兼容。对应 RED `4` 项，GREEN `4/4`。
- 第三轮只读复核的 2 个 P2 已修复：Learning Unit page span 同时受 ParsedDocument/API source page count 约束；`ignored_reason_counts` 必须与 ignored entries 精确对账。对应 RED `3` 项，GREEN `3/3`。
- Supervisor corrective P1-1 RED：无 MinerU 时 readiness 仍 ready、submission 返回 200 并产生 queued Job；GREEN：settings/API/hot reload `3/3`。
- Supervisor corrective P1-2 RED：client config 无 batch limit、DocumentService 仍消费 `zip_bytes`、owned service 三条终止路径 close count 均为 0；GREEN：流式私有文件、累计上限与生命周期 `3/3`。
- Supervisor corrective P2-1 RED：共享 validator import 不存在，runner 篡改 Manifest SHA 后 Worker 仍 completed；GREEN：共享逐字段 validator、Worker、三个 API endpoint `3/3`。
- Supervisor corrective P2-2 RED：JobSnapshot 无 outline metadata、Worker command 无冻结字段、Manifest 返回内部 `outline.md`；GREEN：restart persistence、篡改前置拒绝、真实原始名 `4/4`。
- 提交前独立只读审查发现 2 个 P2：batch/normalizer 中途失败会遗留私有 ZIP；Manifest outline sections 的预期值仍来自待校验文件自身。对应 RED 显示 ZIP 残留、Worker completed、三个 API 返回 200；GREEN `5/5`，现在异常路径清理本批全部 ZIP，Worker 与 runner 前深拷贝 expected Manifest 精确比较，API 对 Manifest 内容复核原子完成时持久化的 artifact SHA。
- Corrective 完整后端：`361/361`；`compileall` exit 0。
- 前端未改动回归：lint、typecheck、Vitest `5/5`、production build、Playwright `6/6` 全部通过。
- 第二轮 corrective P1-1 RED：缺少 batch budget API；normalizer 对 content list 和普通成员均整成员读取；ZIP 被复制保留；第二个 source 失败后保留第一份与 partial 私有输出。GREEN：normalizer/service `25/25`，覆盖 batch aggregate、private ZIP accounting、16 MiB content list、无 `ZipFile.read()`、move 保留和整批 cleanup。
- 第二轮 corrective P2-1 RED：runner 仅篡改 Map 或 Coverage 后 Job 仍 completed，三个 endpoint 对两类 hash mismatch 均返回 200。GREEN：Worker/API 定向 `6/6`，两类 mutation 均 permanent no-write，三个 endpoint 均安全 500。
- 第二轮 corrective 相关回归：normalizer、document service、Worker、API `109/109`。
- 第二轮 corrective 完整后端：`369/369`；`compileall` exit 0。
- `test_sequence_generation_uses_learning_map_not_parsing_or_scores` 将 PyMuPDF/MinerU legacy extract 入口和 `select_evidence_chunks` patch 为立即失败，sequence-first 运行仍成功，证明主生成不调用文本抽取或 relevance selector。
- planner 输入不存在 similarity score，排序键只来自 Manifest display order 与 ParsedDocument page/block order；改变 embedding relevance 无法改变主 section 顺序。

## 5. 工件合同

- `result-courseware-manifest.json`：`courseware-manifest.v1`
- `result-learning-map.json`：`learning-map.v1`
- `result-coverage-ledger.json`：`coverage-ledger.v1`
- `result-package.json`：保持 `material-package.v2`
- `result-output.md`：继续由 v2 确定性派生
- evidence、evidence links、quality、trace：保持现有兼容 API 和文件合同

## 6. 精确变更文件

- `README.md`
- `apps/api/jstudy_api/app.py`
- `docs/architecture/overview.md`
- `docs/roadmap.md`
- `multi-agent/jstudy-product-build/reports/0008-mineru-sequence-first-backend-report.md`
- `packages/core/jstudy_core/citations.py`
- `packages/core/jstudy_core/courseware/__init__.py`
- `packages/core/jstudy_core/courseware/models.py`
- `packages/core/jstudy_core/courseware/planning.py`
- `packages/core/jstudy_core/documents/__init__.py`
- `packages/core/jstudy_core/documents/mineru_client.py`
- `packages/core/jstudy_core/documents/mineru_normalizer.py`
- `packages/core/jstudy_core/documents/service.py`
- `packages/core/jstudy_core/job_system/models.py`
- `packages/core/jstudy_core/job_system/repository.py`
- `packages/core/jstudy_core/job_system/service.py`
- `packages/core/jstudy_core/job_system/worker.py`
- `packages/core/jstudy_core/pipeline.py`
- `packages/core/jstudy_core/storage.py`
- `packages/core/jstudy_core/settings.py`
- `tests/test_courseware_models.py`
- `tests/test_courseware_planning.py`
- `tests/test_document_service.py`
- `tests/test_mineru_client.py`
- `tests/test_job_repository.py`
- `tests/test_job_service.py`
- `tests/test_job_worker.py`
- `tests/test_mvp_runner.py`
- `tests/test_security_controls.py`
- `tests/test_settings.py`
- `tests/test_web_mvp.py`

## 7. 剩余限制

- 未实现正式 courseware draft/organizer UI 或 organizer API；当前 title/order 是上传默认值，尚无用户确认与编辑闭环。
- 未实施 HTML renderer/theme、HTML export、Batch Courseware、question generation、BYOK、quota 或 billing。
- 未修改 `apps/web/**`；前端门只证明无回归，不证明 synchronized Reader 已消费三个新合同。
- 未引入 Alembic。`job_sources` 与 `jobs` 的新 outline identity 列会使旧 disposable pilot database 不兼容；旧 pilot DB 需要显式重建，不能对持久用户数据使用 `create_all()` 冒充迁移。
- 未执行 live MinerU provider smoke、真实 PostgreSQL smoke 或部署验收。
- 512 MiB 是一个 Job 的 MinerU ZIP 累计压缩传输上限，也是新的 Job 级总解压上限，不是公开上传配额。每个 ZIP 仍受 2,000 members、512 MiB uncompressed、100x compression ratio 与 16 MiB content-list 限制；retained ZIP 加全部解压成员受 1 GiB Job 私有磁盘预算约束。
- 当前 package hash 与后续读取仍沿用 Task 0007 已披露的受信单写者文件边界，理论 TOCTOU 风险未在本任务扩大处理。
- 临时 backend-served UI 仍保留历史 parser selector markup，但 `/api/options` 不再提供 parser profiles；正式 `apps/web` 接入应完全省略该控件。

## 8. Verdict 请求

请求 Supervisor 基于最终提交进行 fresh verdict；建议仅返回一个 verdict：`PASS` 或 `REVISE`。
