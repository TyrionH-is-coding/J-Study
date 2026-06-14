# DeepTutor 医学学习资料 MVP 后续工作计划

## 当前状态

已经跑通单课件 MVP：

```text
PDF 课件
→ 解析文本
→ chunk
→ embedding
→ 多 query hybrid 检索
→ evidence 过滤
→ 口诀库命中
→ 按 soul.md 生成 output.md + evidence.json
```

当前最重要的基线文件：

- `mvp-v2-output.md`
- `mvp-v2-evidence.json`
- `mvp-v2-retrieval_trace.json`
- `soul.md`
- `mnemonics.md`

---

## 阶段一：稳定本地 MVP

目标：让单课件生成结果稳定、可复现、可调试。

要做：

1. 增加 embedding 缓存。
   - 同一 PDF 内容不重复 embed。
   - 缓存 key 使用文件 hash + embedding model。
   - 预期效果：二次运行明显提速。

2. 把检索参数配置化。
   - `chunk_size`
   - `chunk_overlap`
   - 每个 query 保留 evidence 数
   - query 列表
   - required terms

3. 增加输出后处理检查。
   - evidence id 是否都存在。
   - 是否有未引用 evidence。
   - 是否出现禁用表达。
   - 是否包含表格 / Directory tree / 竖向流程箭头。
   - 是否出现证据外高风险扩展词。

4. 建立小型回归样例。
   - 当前 `12-球菌.pdf` 作为第一份固定样例。
   - 后续再加 1 份不同医学课程课件，验证泛化。

验收标准：

- 单课件二次运行不重复 embedding。
- `mvp-output.md`、`mvp-evidence.json`、`retrieval_trace.json` 稳定生成。
- 自动质量检查无阻断项。

---

## 阶段二：接近 DeepTutor 正式 RAG 架构

目标：从本地复刻版 RAG 迁移到 DeepTutor/LlamaIndex 正式 KB 服务。

要做：

1. 梳理 DeepTutor KB 创建和检索接口。
   - `deeptutor.services.rag.RAGService`
   - `deeptutor.tools.rag_tool.rag_search`
   - `deeptutor.services.rag.pipelines.llamaindex`

2. 做一个 `DeepTutorRagAdapter`。
   - 输入：PDF 文件、query 列表。
   - 输出：标准化 evidence 候选。
   - 保留字段：source file、page、chunk_id、score、excerpt。

3. 替换本地 hybrid 检索。
   - 当前本地 BM25/vector RRF 作为 fallback。
   - 正式路径优先调用 DeepTutor RAG。

4. 保留医学学习资料专用层。
   - query planner
   - evidence filter
   - mnemonics retrieval
   - soul.md prompt layer

验收标准：

- 使用 DeepTutor 正式 KB 能生成与 v2 同等或更好的 evidence。
- `evidence.json` 字段可直接支持后续 PDF 跳转。
- 本地 fallback 仍可运行。

---

## 阶段三：证据跳转与右侧课件侧栏

目标：实现“正文小按钮 → 右侧 PDF/PPT 跳转到对应页面”的核心体验。

要做：

1. 扩展 `evidence.json`。
   - page
   - source file
   - excerpt
   - chunk_id
   - 未来可选：bounding box / text span

2. 定义正文 evidence 标记规范。
   - 正文保留隐藏注释：`<!-- evidence: E001 E002 -->`
   - Web 渲染时转成小按钮。

3. 做最小 Web 原型。
   - 左侧：Markdown 学习资料。
   - 右侧：PDF 预览。
   - 点击 evidence 按钮后跳转到对应页。

4. 验证用户体验。
   - 按钮不干扰阅读。
   - 右侧侧栏可收起。
   - 多 evidence 可展开列表。

验收标准：

- 点击正文 evidence 能跳到对应 PDF 页。
- 页面刷新后仍能定位。
- 移动端至少能退化为“打开证据列表”。

---

## 阶段四：Web 服务化 MVP

目标：把 DeepTutor 从“用户部署项目”收敛成“用户上传课件即可生成学习资料”的服务。

要做：

1. 文件上传。
   - PDF / PPT / PPTX。
   - 单课件优先。
   - 大纲版后置。

2. 后台任务队列。
   - 上传后异步解析、embedding、生成。
   - 前端展示任务状态。

3. 服务端模型配置。
   - 用户不提供 LLM key。
   - 用户不提供 embedding key。
   - 服务端统一使用硅基流动或后续自建模型服务。

4. 输出管理。
   - 生成 Markdown。
   - 保存 evidence。
   - 支持重新生成。
   - 支持导出 Markdown。

5. 安全与成本控制。
   - 文件大小限制。
   - 页数限制。
   - token 预算。
   - embedding 缓存。

验收标准：

- 用户只上传课件，即可生成学习资料。
- 不暴露 LLM / embedding API key。
- 单课件流程稳定。

---

## 阶段五：大纲严格模式

目标：从单课件 MVP 扩展到“大纲 + 多课件”。

要做：

1. 解析大纲。
   - 提取章节、学习目标、掌握/熟悉/了解。

2. 根据大纲生成 query plan。
   - 每个大纲点独立检索。
   - 多课件 evidence 聚合。

3. 生成章节目录树。
   - 严格按大纲顺序。
   - 课件内容按大纲重新组织。

4. 检查覆盖率。
   - 哪些大纲点已覆盖。
   - 哪些大纲点 evidence 不足。

验收标准：

- 输出顺序严格跟随大纲。
- 每个大纲点能看到 evidence 覆盖情况。
- evidence 不足时不强行编写。

---

## 阶段六：质量评估体系

目标：让“生成得好不好”可评估，而不是只靠主观感觉。

评估维度：

| 维度 | 检查点 |
| :-- | :-- |
| 证据性 | 关键知识点是否有 evidence 支撑 |
| 完整性 | 是否覆盖主要章节/菌种/检查方法 |
| 学习性 | 是否使用表格、分类树、竖向流程箭头 |
| 准确性 | 是否有证据外扩展、医学错误、缩写未解释 |
| 体验感 | emoji 是否克制有效，重点是否清晰 |
| 口诀质量 | 是否相关，是否标注来源，是否解释对应关系 |

验收标准：

- 每次生成后自动产出质量报告。
- 高风险问题能被标记出来给人工审核。

---

## 推荐下一步

优先做阶段一：

```text
embedding 缓存
→ 检索配置化
→ 自动质量检查
→ 再跑 12-球菌.pdf
```

原因：这一步能直接降低运行时间，并让后续接 DeepTutor 正式 RAG 时有稳定对照。
