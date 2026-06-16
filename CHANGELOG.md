# J-Study Changelog

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
