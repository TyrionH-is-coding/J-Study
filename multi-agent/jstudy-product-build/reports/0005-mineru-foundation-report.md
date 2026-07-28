# Code Agent Report

## 1. Task

- Task card: `multi-agent/jstudy-product-build/task_cards/0005-refactor-checkpoint-mineru-foundation.md`
- Source thread: `019ed023-8e41-7ad0-8117-6246b8ffa0bb`
- Code Agent thread: `019efec4-1e17-7443-8496-c1fea5d6bcb5`
- Status: `completed`
- Branch: `feature/backend-frontend-mvp`
- Pre-refactor SHA: `54629cefec1f54a7fc0f0f6d5bdf056be533d78a`
- Checkpoint SHA: `e7a55bb9db25fd499112536ea8f4da25b190a944`
- Implementation SHA before this report: `0b82ae3b01f97b27a56a56a6f5293eb8d9719840`
- Checkpoint exact file list: `multi-agent/jstudy-product-build/reports/0005-baseline-inventory.md`

## 2. Summary

已严格按 Phase 0→7 完成：先盘点并验证 0002–0004 基线，创建 96 文件 checkpoint；随后建立 `ParsedDocument` contract v1、PyMuPDF 验证/元数据/渲染 utility boundary、MinerU Precision Extract v4 传输层、安全 ZIP 归一化、运行时配置和显式注入的旧页列表兼容适配器。

本任务没有切换 `run_mvp()` 或 `run_course_outline()`，没有改变公共 FastAPI route、前端请求/响应 contract、parser 默认行为或 Job 数据库。自动测试没有使用真实 token，也没有调用真实 MinerU。

MinerU 官方文档复核日期为 `2026-07-28`：

- Precision Extract API v4: `https://mineru.net/doc/docs/index_en/`
- 输出文件说明: `https://opendatalab.github.io/MinerU/reference/output_files/`

J-Study 归一化只采用稳定的 legacy `*_content_list.json`；明确不采用官方标注为 developmental 的 `content_list_v2.json`。

## 3. Changed Files

- `multi-agent/jstudy-product-build/reports/0005-baseline-inventory.md`: 记录 checkpoint SHA。
- `packages/core/jstudy_core/documents/__init__.py`: 导出统一文档 contract。
- `packages/core/jstudy_core/documents/models.py`: contract v1 与页码、bbox、source identity、block id 等不变量。
- `packages/core/jstudy_core/documents/pdf_utility.py`: PDF header、损坏校验、SHA256、页数/元数据和 PNG 渲染边界。
- `packages/core/jstudy_core/documents/mineru_client.py`: v4 batch submit、signed PUT、poll、ZIP 下载及 typed errors/results。
- `packages/core/jstudy_core/documents/mineru_normalizer.py`: 安全解压、legacy content list 归一化和私有原始产物保留。
- `packages/parsers/pymupdf_parser.py`: 复用 PDF 校验 utility，保留既有文本提取行为。
- `packages/parsers/mineru_parser.py`: 仅在显式注入 document parser 时转换为 legacy page list。
- `packages/core/jstudy_core/admin_settings.py`: MinerU 默认配置、兼容字段和 token 脱敏。
- `packages/core/jstudy_core/settings.py`: typed MinerU 配置、环境变量覆盖及 readiness 状态。
- `tests/test_document_models.py`: contract v1 验证测试。
- `tests/test_pdf_utility.py`: PDF utility 边界测试。
- `tests/test_mineru_client.py`: 全 MockTransport 传输、错误、安全和兼容适配器测试。
- `tests/test_mineru_normalizer.py`: 归一化、页码、资产和 ZIP 攻击面测试。
- `tests/test_admin_settings.py`: 默认设置、保存和 token 脱敏回归。
- `tests/test_settings.py`: 环境覆盖、typed config 和 readiness 回归。

## 4. Verification

- Command: `python -m unittest tests.test_document_models tests.test_pdf_utility tests.test_mineru_client tests.test_mineru_normalizer -v`
- Result: `43/43` 通过。
- Command: `python -m unittest tests.test_admin_settings tests.test_settings tests.test_parser_profile_router tests.test_mvp_runner -v`
- Result: `59/59` 通过。
- Command: 清空 `MINERU_API_TOKEN`，将 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY` 指向 `127.0.0.1:1` 后运行 `python -m unittest tests.test_mineru_client -v`
- Result: `17/17` 通过；所有 HTTP 请求均由注入的 `httpx.MockTransport` 处理，证明自动测试不依赖真实 MinerU 网络或 token。
- Command: `python -m unittest discover -s tests -v`
- Result: `168/168` 通过。
- Command: `python -m compileall -q apps packages`
- Result: 通过。
- Command: `npm run lint && npm run typecheck && npm run test && npm run build && npm run test:e2e`（PowerShell 逐项 fail-fast）
- Result: lint、typecheck、Next.js build 通过；Vitest `13/13`，Playwright `12/12` 通过。
- Command: `git diff --check`、checkpoint 后文件范围审查、tracked runtime/secret filename scan
- Result: 通过；实现变更仅落在任务卡允许范围；未跟踪排除目录保持未 stage，未发现新增 tracked `data/`、真实 PDF、数据库、token 或 `.env`。
- Notes: 沙箱内 Windows 系统临时目录写入会触发 `PermissionError`；所有计入结果的 Python/Vitest/Playwright 测试均已在获批的沙箱外环境用真实退出码复跑。

### 安全限制

- MinerU ZIP: 最多 `2000` members。
- MinerU ZIP: 总解压后大小最多 `536870912` bytes（512 MiB）。
- MinerU ZIP: 单成员压缩比最多 `100x`。
- Result download: 最多 `268435456` bytes（256 MiB），同时检查 `Content-Length` 与流式累计大小。
- Result URL: 仅 HTTPS，默认 allowlist 为 `cdn-mineru.openxlab.org.cn` 和 `mineru.oss-cn-shanghai.aliyuncs.com`。
- ZIP path: 拒绝 absolute path、drive path、`..` traversal、duplicate path 和 symlink；仅解压到 job-owned target。
- Content contract: 必须恰有一个可用 `*_content_list.json`；拒绝 malformed JSON、缺失资产、越界页和空有效文档。

## 5. Risks and Limitations

- 未做 live MinerU smoke test；按任务卡，`PASS` 不要求真实 token 或在线请求。
- compatibility adapter 仍返回临时 `list[{"page", "text"}]` 形状；下一张 pipeline-switch 任务应让 generation pipeline 直接消费 `ParsedDocument` 后删除该形状。
- PyMuPDF 旧文本提取仍保留；下一张 pipeline-switch 任务验证 MinerU 正式路径后再删除，PyMuPDF 仅保留验证、元数据和渲染。
- parser-profile routing 和 deprecated settings 字段仍保留可读；应由 pipeline-switch/API cleanup 任务迁移和删除，不能在本任务提前破坏现有 contract。
- 当前 Job 数据库、上传和生成数据未迁移；PostgreSQL/worker/queue 属于后续独立任务。
- `.superpowers/`、`frontend/`、`game/`、`images/`、`outline_mode/`、`scripts/` 仍为未跟踪延期项，本任务未修改、删除、stage 或 commit。是否清理应由 Supervisor 单独确认归属，禁止用 `git clean` 推断。

## 6. Requested Supervisor Action

请 Supervisor 审核并给出一个 verdict：`PASS` / `PASS_WITH_LIMITATIONS` / `REVISE` / `REJECT`。

Code Agent 请求：`PASS`。