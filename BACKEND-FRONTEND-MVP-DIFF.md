# J-Study: vs `feature/backend-frontend-mvp` 差异总览

> 从上游 `feature/backend-frontend-mvp`（基点 `d3cffd6`）分叉以来的全部变更。
> 分支路径：`feature/backend-frontend-mvp` → `feat/multi-domain-modes` → `feat/frontend-polish-katex`
> 总计 **36 个 commit**，**18 个文件变更（+2834 / -331 行）**

---

## 一、全局架构变更

### 1.1 领域包系统

上游只有 `medicine.py`（硬编码 `from medicine import ...`）。我们新增：

| 文件 | 作用 |
|------|------|
| `packages/domains/general.py` | 通用领域 — 5 个检索查询 + 质量审计，无学科偏见 |
| `packages/domains/engineering.py` | 工科领域 — 6 个工科查询（定义/定理/推导/算法/应用/陷阱） |
| `packages/core/jstudy_core/pipeline.py` | **重构为动态领域路由**，根据 `scenario_domain_rules` 自动加载 domain 模块 |
| `data/settings/content_pack.json` | 场景配置中心 — 定义 pack → scenario → soul_profile + domain_rules 的映射 |

### 1.2 Mode 路由系统

上游无 mode 概念。我们新增三模式：

| Mode | 目的 | 嵌入方式 |
|------|------|----------|
| **Default (总结)** | 标准学习资料，含解释、关键概念、小结 | soul 内嵌 `当前模式：{mode}` 段落 |
| **Exam Quick (考前速记)** | 提炼各概念的一句话记忆公式/结论 | 同上 |
| **Rewrite (改写重述)** | 换用比喻/类比/示例重述，帮助理解 | 同上 |

**路由链路**：`form → job metadata → pipeline → domain.build_generation_prompt(mode) → soul.md {mode} 替换`

### 1.3 Soul 文件体系

上游仅有单文件 `soul.md`。我们扩展为场景+模式矩阵：

| 文件 | 状态 | 说明 |
|------|------|------|
| `soul.md` | **修改** | 嵌入考前速记 + 改写模式章节，`{mode}` 占位符 |
| `soul-general.md` | **新增** | 通用学科 soul — 总结/考前速记/改写三模式 |
| `soul-engineering.md` | **新增** | 工科 soul — 公式+流程+设计决策导向 |
| `soul-exam-quick.md` | **新增**（已废弃） | 旧方案：独立 soul + MODE_SOUL_MAP 映射 |
| `soul-rewrite.md` | **新增**（已废弃） | 同上 |

**进化路径**：Phase 1 用独立 soul 文件 + MODE_SOUL_MAP → Phase 2 改为 scenario-aware 嵌入 soul

---

## 二、前端重构（`apps/api/jstudy_api/ui.py`）

### 2.1 CSS 翻新（Linear 风格）
- 完整的浅色主题重写（Inter 字体、蓝紫色系、圆角卡片、blockquote/表格/代码块统一样式）
- 响应式布局，四宫格侧栏/内容/引用/PDF

### 2.2 卡片+pill 选择器
- **场景选择**：下拉框 → 垂直卡片（icon + 学科名 + 描述），Gradient 背景色
- **模式选择**：下拉框 → 横向 pill 按钮，蓝底白字选中态
- 保持 `<input type="hidden">` 兼容原有 FormData 提交

### 2.3 可拖拽面板
- 左/中/右三栏 + 引用↔PDF 纵向，全部可拖拽调整宽度/高度
- 5 列 grid（side | handle | content | handle | pdf）+ 横向/竖向 resize handles

### 2.4 KaTeX 公式渲染
- CDN 加载 KaTeX，`$...$` / `$$...$$` 渲染为 LaTeX
- 解决 KaTeX HTML 被 `escapeHtml` 转义的 bug（占位符方案）
- 解决 KaTeX 与 Markdown 加粗 `**` 冲突的问题

### 2.5 历史记录 + 导出
- 侧栏 `📋 历史记录`，按时间倒序，点击加载之前生成的内容
- 下载按钮 `⬇ 下载 .md`（`GET /api/jobs/{id}/export`）

### 2.6 进度 + 质量
- 生成过程三级状态：解析课件 → 检索证据 → 生成学习资料
- 输出顶部质量徽章 ✅ / ❌
- 状态栏显示 job_id 方便调试

### 2.7 引用文本清洗
- **源头清洗**：新增 `clean_quote()` 函数在 `citations.py` 层去除 PDF 提取错误字符（Tamil/Odia/Telugu/Malayalam/Sinhala/Hebrew/Ethiopic/私用区）
- **前端分段过滤**：字符级分类 TEXT/FORMULA/SPACE，仅保留自然语言片段，跳过公式符号（数学斜体/运算符/箭头/上下标等 Unicode 范围）
- **全量清理**：25 个已存在 job 的 evidence_links.json

---

## 三、后端改动

### 3.1 `apps/api/jstudy_api/app.py`
- 新增 `GET /api/jobs` 历史记录 endpoint（按 owner_user_id 过滤）
- 新增 `GET /api/jobs/{id}/export` 导出 endpoint
- mode 表单字段 → job metadata → pipeline 透传
- 移除旧 MODE_SOUL_MAP 硬编码

### 3.2 `packages/core/jstudy_core/jobs.py`
- 新增 `list_completed()` 方法

### 3.3 `packages/core/jstudy_core/citations.py`
- 新增 `clean_quote()` 函数清洗 PDF 提取垃圾字符
- 70+ 行垃圾脚本 Unicode 范围删除器

### 3.4 `packages/core/jstudy_core/pipeline.py`
- 从硬编码 `from medicine import ...` → 动态 `_resolve_domain(routing_metadata)`
- `generation_mode` 参数透传

### 3.5 `packages/core/jstudy_core/providers.py`
- 小修（详情见 git diff）

---

## 四、Bug 修复

| 来源 | 问题 | 修复 |
|------|------|------|
| 上游 | `_is_topic_term()` 无英文停词过滤，PDF 页眉（the, of, a）污染检索关键词 | 三个 domain 模块均加入 ~80 英文停词 |
| 上游 | `audit_output_quality()` engineering_terms 含"工程"，导致所有工科输出 quality:fail | 移除"工程"误判项 |
| 上游 | 引用文本含 PDF 字体编码垃圾字符（Tamil/Odia/私用区） | 后台 clean_quote + 前端 3 层正则 + 全量清理 |
| 自产 | JS 正则反斜杠加倍 `\\s` → `\s` 导致语法错误 | 修复 6 处 |
| 自产 | `renderInlineMarkdown` 不在 `renderMarkdown` 闭包内，拿不到 `latexPlaceholders` | 移入闭包 |
| 自产 | KaTeX HTML 被 `escapeHtml` 转义 | 占位符方案 |
| 自产 | 含 LaTeX 的行中 `**加粗**` 不渲染 | 统一走 renderInlineMarkdown |
| 自产 | 横向 resize 方向反了 / CSS var 未定义导致 NaN | 改为 inline `offsetWidth` 方案 |
| 自产 | vertical resize 方向反了 | `startY - e.clientY` → `e.clientY - startY` |
| 自产 | 登录/注册表单缺 `method=POST` + `action` | 补齐 |

---

## 五、文件变更清单

### 新增文件（10 个）

```
BRANCH-README.md                          — 分支说明文档
CHANGELOG.md                              — 变更日志
data/settings/content_pack.json           — 场景配置中心
packages/domains/engineering.py           — 工科领域包 (336 行)
packages/domains/general.py               — 通用领域包 (336 行)
soul-engineering.md                       — 工科 soul (192 行)
soul-exam-quick.md                        — 考前速记 soul（废弃）(126 行)
soul-general.md                           — 通用 soul (145 行)
soul-rewrite.md                           — 改写 soul（废弃）(142 行)
ideas/痛点-现状对照.md                     — 产品方向记录
```

### 修改文件（8 个）

```
apps/api/jstudy_api/app.py                — 历史/导出/mode 路由
apps/api/jstudy_api/ui.py                 — 前端全面重写 (+1137/-469)
packages/core/jstudy_core/citations.py    — + 70 行 clean_quote
packages/core/jstudy_core/jobs.py         — + list_completed()
packages/core/jstudy_core/pipeline.py     — + 动态领域路由 + mode
packages/core/jstudy_core/providers.py    — 小幅修改
packages/domains/medicine.py              — + build_generation_prompt(mode)
soul.md                                   — + 考前速记 + 改写模式章节
```

---

## 六、上游 `feature/backend-frontend-mvp` 的基线功能

分叉时上游已有的核心能力（未改变）：

- FastAPI MVP（web_mvp.py → web_mvp:app）
- 用户认证（注册/登录，invite code 机制）
- PDF 上传 → 文字提取（pymupdf）
- 分块 + 混合检索
- LLM 生成（DeepSeek）+ 引用嵌入
- 基础 UI（上传表单、PDF 预览、引用列表）
- Medicine domain（基本检索 + 生成）
- soul.md（医学风格基础版）
- Job 存储 + 状态轮询
- CRLF→LF 自动转换
