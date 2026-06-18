# 章节级分片生成 — 设计文档

> 分支: `feat/sectional-generation`
> 基于: `feat/frontend-polish-katex`
> 作者: Hermes
> 日期: 2026-06-18

---

## 问题

当前 `run_mvp()` 一次 prompt 塞所有证据 + soul 规则，一次生成全部内容：

```python
messages = domain.build_generation_prompt(soul, evidence, ...)    # 全部证据
markdown = providers.generate_markdown(messages, ...)              # 一次生成
```

瓶颈：

| 问题 | 原因 |
|------|------|
| 输出长度受限 | `max_tokens=6000`，实际 ~4000 中文字 |
| 大文件质量下降 | 30+ 证据 chunks 让 LLM 丢失焦点，生成趋于概括 |
| 无法分章节展开 | 没有机制让 LLM 对每个章节深入 |
| 无迭代修正 | 一次生成完，没有二次润色或补漏 |

## 方案：outline 驱动的分片生成

### 核心思路

利用 outline 作为天然的分片依据，对每个章节单独生成，再合并。

无 outline 时回退到当前单次生成模式。

### 流程图

```
输入：PDF + outline (可选)
  │
  ├── [有 outline]
  │     ├── 解析 outline → 章节列表
  │     └── 逐节生成 + 合并
  │
  └── [无 outline]
        ├── LLM 从课件文本推断章节（一次小调用, max_tokens=400）
        ├── ≥2 章节 → 逐节生成 + 合并（LLM 推断路径）
        └── <2 章节 → 当前单次生成（回退路径）
```

### 需要改的文件

| 文件 | 改动 |
|------|------|
| `packages/core/jstudy_core/pipeline.py` | `run_mvp()` 增加分片分支：解析 outline → 循环生成 → 合并 |
| `packages/core/jstudy_core/providers.py` | 新增 `generate_markdown_for_section(title, evidence, soul)`，或复用 `generate_markdown` |
| `packages/domains/*.py` | `build_generation_prompt()` 可能需要接受 `section_title` 参数，返回聚焦 prompt |
| `packages/core/jstudy_core/citations.py` | `build_evidence_links()` 需要处理分段合并后的引用 |
| `apps/api/jstudy_api/app.py` | 生成参数可能需要新增 `max_sections` 等控制参数（可选） |

### 关键设计决策

**1. 证据分片策略**

当前证据是所有 chunks 中选出的 top-K。分片后，对每个章节需要重新筛选相关证据。

方案：对每个章节标题做一次 embedding 查询，取与该章节最相关的 top-M 个 chunks。

```python
chapter_evidence = select_chapters_evidence(chapter_title, chunks, chunk_embeddings, top_k=8)
```

**2. Prompt 模板改造**

当前 soul.md 包含一个完整的输出模板。分片后，需要让 LLM 知道"你只生成这个章节，不做全文总结"。

改法：在 `build_generation_prompt()` 中增加 `section_title` 参数，prompt 头部加指令：

```
你现在正在生成学习资料的「{section_title}」部分。
请只专注于这个章节的内容，使用以下证据。
不要写全书总结，不要写"上一篇/下一篇"。
```

**3. 合并策略**

最简单的：按 outline 顺序拼接章节，加目录。

进阶：拼完后让 LLM 做一次"润色"（第二轮调用），处理章节间的过渡和重复内容。

**4. 质量审计适配**

当前 `audit_output_quality()` 跑在完整输出上。分片后：
- 每个章节单独跑 quality audit（提前发现有问题的小节）
- 合并后跑全量 audit（证据引用完整性检查）

**5. 引用编号**

当前证据 ID 是全局的 (E001-E999)。分片生成时引用编号需要跨章节唯一。

做法不变——证据编号在分片前已经确定，各章节只引用已分配的 ID。

### 风险与缓解

| 风险 | 缓解 |
|------|------|
| 章节间内容重复 | 合并后加第二轮润色去重；或在 prompt 中提示"不要重复其他章节已写的内容" |
| 分片边界生硬 | 章节间加过渡段（LLM 或规则生成"上一章讲了 X，本章将深入 Y"） |
| API 调用次数增加 = 耗时增加 | 各章节可并行调用（通过 AsyncIO 或 concurrent.futures） |
| 无 outline 时退化 | 保持当前单次生成路径作为 fallback |

### 验证标准

1. 有 outline 时，输出按 outline 章节组织，每章内容充实
2. 无 outline 时，行为和当前完全一致
3. 同一 PDF 有/无 outline 的输出质量可对比（outline 版本章节细致、非 outline 版本篇幅更短）

---

## 未纳入的范围

- 自动从 PDF 提取标题（OCR 级别的结构识别）— 后续可以加，第一步先依赖用户提供的 outline
- 多文件 batch 模式 — 那是 Phase 5.25 的事情
- Agent 自动规划 — 当前是"outline 引导的模板式分割"，不是 Agent 自主分解
