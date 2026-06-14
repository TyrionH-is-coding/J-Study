# DeepTutor RAG 架构笔记（MVP v2）

## 参照的 DeepTutor 源码

- `DeepTutor/deeptutor/services/rag/pipelines/llamaindex/retrievers.py`
  - `build_retriever()` 默认使用 hybrid profile。
  - hybrid = vector retriever + BM25 retriever + `QueryFusionRetriever`。
  - fusion mode 使用 reciprocal rank。
  - BM25 不可用时 fallback 到 vector retrieval。
- `DeepTutor/deeptutor/services/rag/pipelines/llamaindex/config.py`
  - 默认 profile 是 `hybrid`。
  - 子 retriever 会用 top_k multiplier 扩大候选，再融合回目标 top_k。
- `DeepTutor/deeptutor/services/rag/pipelines/llamaindex/pipeline.py`
  - `search()` 返回文本内容和 `sources`。
  - `_nodes_to_result()` 提供 `title/source/page/chunk_id/score`。
- `DeepTutor/deeptutor/services/rag/pipelines/llamaindex/ingestion.py`
  - ingestion 使用 LlamaIndex `SentenceSplitter`。
- `DeepTutor/deeptutor/services/rag/pipelines/llamaindex/embedding_adapter.py`
  - 默认 chunk size = 512，chunk overlap = 50。

## v1 的问题

v1 为了快速验证产品路线，使用了单 query + 纯向量 cosine 检索：

```text
PDF page text
→ fixed chunk
→ embedding
→ one broad query
→ top 22 chunks
→ evidence.json
→ LLM 生成 output.md
```

问题：

- 单 query 会偏向“总体相关”，不能保证每个菌种/学习模块都有足够证据。
- 纯向量检索对“凝固酶、ASO、Optochin、SSSS”等精确关键词不如 hybrid 稳。
- 低价值标题 chunk 可能进入 evidence。
- evidence 没有模块归属，生成时容易把证据挪去支撑不相关小节。

## v2 的改进

MVP v2 不直接接入完整 DeepTutor KB 配置系统，而是在本地 runner 中复刻最关键的检索思想：

```text
PDF page text
→ chunk_size 512 / overlap 50
→ embedding
→ 多个学习模块 query
→ vector score + BM25 score
→ reciprocal rank fusion
→ 过滤标题型/过短/重复 chunk
→ 每个 query 保留少量 evidence
→ evidence 按学习模块分组
→ LLM 生成 output-v2.md
```

## 暂不直接复用完整 DeepTutor KB 的原因

- DeepTutor 的 KB 路径、embedding catalog、版本化 index 和用户资源访问是为完整应用服务的。
- 当前目标是本地验证“医学学习资料生成层”是否可行，不需要先承担完整 Web/多用户配置复杂度。
- v2 先对齐 DeepTutor 的 RAG 设计思想；下一步 Web 化时，再把 runner 的检索层替换为 DeepTutor `RAGService.search()` 或等价服务接口。

## 后续迁移方向

最终架构应为：

```text
课件 KB（DeepTutor/LlamaIndex hybrid RAG）
+ 口诀 KB（可复用社区资料）
→ 医学学习资料 Query Planner
→ Evidence Filter
→ soul.md Prompt Layer
→ output.md + evidence.json
→ Web UI 右侧 PDF/PPT 证据跳转
```
