# J-Study Changelog

## 2026-06-18 — 管理面板合并：Job详情 + 反馈面板

### 新增
- `serve_feedback_admin.py` 升级为统一管理面板，支持标签页切换：📋 作业 / 💬 反馈
- ⚠ 反馈标签页保持不变（兼容）

### 作业标签页
- job 表格：Job ID、状态、生成路径、章节数、学科、耗时、质量、反馈数、创建时间
- 状态/路径/学科三栏过滤器 + 实时刷新
- 顶部统计栏：总作业、已完成、失败、多轮生成数

### 作业详情展开（点击行）
- 生成路径标识 → `single-pass` / `sectional-outline` / `sectional-inferred`
- 章节列表（多轮生成时显示所有章节标题）
- 质量审计详情：证据数、引用数、章节覆盖率、问题列表
- 关联反馈列表（该 job 下的所有反馈记录）
- 元信息：模型、解析器、耗时、错误

### 新 API
- `GET /api/admin/jobs` — 所有 job 列表（含 trace/质量/反馈聚合）
- `GET /api/admin/jobs/{job_id}` — 单 job 详情（含完整反馈和 trace 摘要）

## 2026-06-18 — LLM 推断大纲：无 outline 时自动分章生成

### 新增
- `pipeline.py`: 新增 `infer_sections_from_chunks()` — 无用户 outline 时，用一次极低成本 LLM 调用（max_tokens=400）从课件文本推断章节列表
- 无 outline 路径现在自动触发 LLM 推断：>=2 章节 → 分章生成；<2 章节或 LLM 失败 → 回退单次生成（零变化）
- trace 新增 `generation_path` 字段：`"single-pass"` / `"sectional-outline"` / `"sectional-inferred"`
- trace 新增 `sections` 字段：章节标题列表（分章路径）或空数组（单次路径）
- `result-sections.json` 始终写入：分章时包含章节元数据，单次时为空数组 `[]`

### 阈值设计
- 不分硬编码章节数阈值。LLM prompt 中明确指令："如果内容没有清晰的章节或主题划分，返回空数组 []"
- 短章节也被保留："如果一个章节标题在课文中明显存在但该章节内容仅很短，仍然保留并返回"
- 视觉验证：可通过 `GET /api/jobs/{id}/trace` 看到 `generation_path` + `sections` 字段，或查看 `result-sections.json`

### 修复
- 测试 `test_run_mvp_uses_runtime_api_key_and_base_urls`: `generate_markdown` 调用从 1 次调整为 2 次（首次是 LLM 推断章节，第二次是主生成）

## 2026-06-18 — Sectional Generation: outline-driven分片生成

### 新功能
- `pipeline.py`: 新增 outline-driven 章节级分片生成路径。有 outline 时自动解析章节列表，每章独立做 evidence 检索 + 聚焦 prompt 生成，最后合并。无 outline 时回退单次生成。
- `parse_outline_sections()`: 解析 markdown 标题和中文编号为章节列表
- per-section 输出: `output/sections/{i}-{slug}/markdown.md` + `evidence.json` 独立保存
- 合并输出包含目录和逐节内容，`result-sections.json` 记录章节元数据

### 变更
- `storage.py`: 无变更（节输出利用子目录，不改变 OutputPaths 接口）
- `providers.py`: `generate_markdown()` 新增 `max_tokens` 参数（默认 6000，章节生成用 4000）
- `medicine.py`, `general.py`, `engineering.py`: `build_generation_prompt()` 新增 `section_title` 参数 + `_section_block()` 辅助函数
- `citations.py`: 无变更（全局证据 ID E001-E999 跨节唯一，合并后 `build_evidence_links` 正常工作）
- `pipeline.py`: 新增 `StudyQuery`、`build_study_queries`、`extract_evidence_refs` 等 facade 层 re-export

### 修复
- `test_mvp_runner.py`: mock 目标从 `pipeline.build_study_queries` 改为 `medicine.build_study_queries`（动态路由重构后的正确路径）

### 新增测试
- `tests/test_parse_outline_sections.py`: 7 个单元测试覆盖 markdown 标题、中文编号、混合格式、空 outline 等场景

## 2026-06-18 — 修复: 反馈端点 500（missing import json）+ widget 重置

### 修复
- `app.py`: 新增 `import json`（此前遗漏，导致 `json.dumps()` 抛出 `NameError`）
- `app.py`: 反馈端点 `submit_feedback` 加 try-except 兜底 + `scenario` 字段安全解析
- `ui.py`: `showFeedbackArea()` 重置按钮显示状态和 label 文字

## 2026-06-18 — 新增: 用户反馈系统

### 新增
- `app.py`: 新增 `POST /api/jobs/{job_id}/feedback` 端点，接收 `rating`(up/down) + 可选 `comment`
- `ui.py`: 生成完成后在输出底部显示反馈 widget（👍/👎 按钮 + 评论框），localStorage 防重复提交
- `serve_feedback_admin.py`: 独立反馈管理站（`:8888`），统计头栏 + 筛选 + 表格显示全部反馈日志

### 架构
- 反馈存储路径: `web_jobs/feedback/feedback_{job_id}_{uuid}.json`
- 每条含: user_id, user_email, job_id, rating, comment, scenario_id, mode, build_commit, created_at
- 管理站使用相同 `JSTUDY_ADMIN_TOKEN` 鉴权（可配合 Cloudflare Access）

## 2026-06-17 — 修复: PDF 引用文本乱码

### 修复
- `citations.py`: 添加 `clean_quote()` 函数，源头清洗 PDF 提取产生的垃圾字符（Odia/Tamil/Telugu/Malayalam/Sinhala/私用区等编码错误）
- `ui.py`: 扩展前端 `cleanQuote` 正则覆盖更多 Unicode 垃圾范围，作为旧 job 的兜底处理
- 全量清理 25 个已存在 job 的 evidence_links.json 文件

### 改进
- `ui.py`: 引用文本改为字符级分段过滤——仅保留自然语言片段，跳过公式符号（数学斜体/运算符/箭头等 Unicode 范围），引用不再被公式字符污染

## 2026-06-16 — Phase 2: 通用学科 + 工科领域包

### 新增

- **soul.md (更新)**: 嵌入考前速记 + 改写模式章节，通过 `{mode}` 占位符由 build_generation_prompt 替换
- **soul-general.md**: 通用学科 soul，含总结/考前速记/改写三模式，零学科偏见
- **soul-engineering.md**: 工科 soul，公式+流程+设计决策导向，含三模式
- **packages/domains/general.py**: 通用领域包 — 5 个通用检索查询 + 通用生成 prompt + 质量审计
- **packages/domains/engineering.py**: 工科领域包 — 6 个工科检索查询（定义/定理/推导/算法/应用/陷阱）+ 工程 prompt
- **pipeline.py (重构)**: 动态领域路由 — 根据 scenario domain_rules 自动加载对应 domain module；`generation_mode` 参数透传到 `build_generation_prompt`
- **content_pack.json**: General / Engineering scenario 激活，各指向独立 soul_profile + domain_rules

### 架构变更

| 变更 | 说明 |
|:--|:--|
| 领域选择 | pipeline.py 从 `from medicine import ...` → `_resolve_domain(routing_metadata)` 动态加载 |
| 模式路由 | mode 从 form → job metadata → pipeline → domain.build_generation_prompt → soul `{mode}` 替换 |
| soul 文件 | 每份 soul 内含 3 个模式章节，由 `当前模式：{mode}` 指示 LLM 遵守哪套规则 |

### 文件变更

| 文件 | 变更 |
|:--|:--|
| `soul.md` | 新增考前速记 + 改写模式章节；末尾 `{mode}` 占位 |
| `soul-general.md` | 新建 |
| `soul-engineering.md` | 新建 |
| `packages/domains/general.py` | 新建 |
| `packages/domains/engineering.py` | 新建 |
| `packages/core/jstudy_core/pipeline.py` | 重构为动态领域路由 + generation_mode |
| `packages/domains/medicine.py` | build_generation_prompt 接受 mode 参数 |
| `apps/api/jstudy_api/app.py` | run_job 传 generation_mode |
| `data/settings/content_pack.json` | 新增 General/Engineering 场景 |
| `apps/api/jstudy_api/app.py` | 移除旧 mode → soul_path 映射，改为 scenario-aware 嵌入 soul |
| `apps/api/jstudy_api/ui.py` | 状态栏显示 job_id，方便调试定位 |

## 2026-06-16 — Phase 2 patch: mode 路由修复 + job_id 显示

### 修复
- **mode 路由改为 scenario-aware**: 移除 mode→单独 soul 文件的硬编码映射，mode 仅控制 soul 文本中的 `{mode}` 占位符。各 scenario 使用自身 soul 文件的嵌入模式章节
- **前端状态栏显示 job_id**: `状态：completed (b853fddac4cd)` 格式，方便调试和对比

### 验证效果
Engineering/exam-quick 输出对比改前改后：LaTeX 公式密度提升、⭐⭐⭐ 被 🔑 替换、陷阱从段落式改为"出错原因+正确做法+示例"结构、新增符号速查表 — soul-engineering.md 规则生效。

## 2026-06-16 — Frontend: CSS 翻新 + KaTeX 公式渲染

### 改动
- **CSS 重写**：Inter 字体 + 更干净的浅色主题（Linear 启发配色），按钮/输入框/表格统一样式
- **KaTeX 公式渲染**：引入 KaTeX CDN，`$...$` 和 `$$...$$` 在生成内容中渲染为 LaTeX 公式
- **证据按钮样式**：更新为蓝紫色系，更适配新主题
- **PDF 预览面板**：重新命名 class 避免冲突，微调间距
- **状态栏**：保持 job_id 显示
| **输出区域** | 新增 blockquote / 列表 / 代码块样式 |

## 2026-06-16 — Bug fix: topic 提取停用词 + quality 误判

### 修复
- **`_is_topic_term()` 英文停用词过滤**: 三个 domain 模块（medicine/general/engineering）均加入约 80 个英文停用词过滤（the, of, a, figure, page 等），防止 PDF 页眉/页脚内容污染检索关键词。该 bug 源自上游 `feature/backend-frontend-mvp` 的 `packages/domains/medicine.py`，仅英文 PDF 复现。
- **`audit_output_quality()` 移除 "工程" 误判**: `engineering_terms` 从 `["MVP", "根据证据片段", "证据片段", "工程"]` 改为 `["MVP", "根据证据片段", "证据片段"]`。originates from 上游 `feature/backend-frontend-mvp`。工科输出必然包含"工程注意事项"等合法内容，导致所有工科 output quality:fail。

## 2026-06-16 — 卡片选择器 UI

### 改动
- **学科选择器**: 下拉框改为垂直卡片（带 icon + 学科名 + 描述文字），选中蓝边高亮
- **模式选择器**: 下拉框改为横向 pill 按钮（总结/考前速记/改写重述），选中蓝底白字
- **后端兼容**: 使用 `<input type="hidden">` 保持 FormData 提交格式不变
- **学科图标**: Medicine 粉色、General 蓝色、Engineering 紫色背景

## 2026-06-16 — 修复：含 LaTeX 的行中加粗不渲染

### 修复
- `renderMarkdown` 中，当一行同时包含 `$...$` 和 `**加粗**` 时，`hasLatex` 分支直接推了 KaTeX 渲染结果，跳过了 `renderInlineMarkdown`，导致 `**` 原文显示。现已统一走 `renderInlineMarkdown` 后再渲染 KaTeX。

## 2026-06-16 — 修复：KaTeX HTML 被 escapeHtml 转义

### 修复
- `renderInlineMarkdown` 中的 `escapeHtml` 把 KaTeX 渲染后的 `<span class="katex">` 转成了 `&lt;span&gt;`。现已将 KaTeX HTML 先提取为占位符，完成 escaping 后再恢复。

## 2026-06-16 — 导出 + 质量徽章 + 进度阶段

### 新增
- **导出 endpoint**: `GET /api/jobs/{id}/export` 返回 .md 文件下载
- **质量徽章**: 输出顶部显示 ✅ 通过 / ❌ 未通过
- **进度阶段**: 生成过程中显示"解析课件→检索证据→生成学习资料"三级状态
- **下载按钮**: PDF 面板头部新增 ⬇ 下载 .md，生成完成后可见

## 2026-06-16 — 历史记录列表

### 新增
- **后端 `GET /api/jobs`**: 返回当前用户的已完成 job 列表（scenario / mode / 质量 / PDF 名）
- **前端侧栏历史**: 登录后显示"📋 历史记录"，按时间倒序排列，点击即可加载之前生成的内容（含质量徽章和下载按钮）
- **JobStore.list_completed()**: 新增方法用于按创建时间排序遍历已完成 job
