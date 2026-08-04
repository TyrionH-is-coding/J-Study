# J-Study 生成延迟与可靠性设计

## 1. 背景

2026-08-03 的腾讯云纵向验收使用 6 页测试课件，客户端从提交到完成约
57.1 秒，服务端从创建 Job 到完成约 51.4 秒。阶段耗时为：

- MinerU 解析约 6.6 秒；
- 检索与规划约 0.02 秒；
- 6 个 Learning Unit 串行生成约 44.5 秒；
- 打包约 0.03 秒。

纵向链路和单样本内容质量已经通过，但性能门禁没有通过。瓶颈是独立章节
逐个调用模型，不是 MinerU、检索或打包。

## 2. 本轮目标

在不改变公开 API、Learning Map、Evidence、Material Package v2 和章节顺序
语义的前提下，将独立章节改为有界并发生成，并记录可审计的生成耗时。

本轮只解决首次生成的主要串行瓶颈，并为真实 staging 复验提供测量数据。

## 3. 方案选择

### 方案 A：现有章节有界并发，推荐

每个 Learning Unit 仍对应一个 `MaterialSection` 和一次模型调用。Worker 的单个
Job 最多同时执行 3 个章节调用，结果按原始 `order` 排列后再打包。

优点：

- 不改变模型输出 schema；
- 不改变 Material Package、citation 和 section identity；
- 失败语义与当前 Worker 重试边界保持一致；
- 预计可以把 6 次调用从 6 个串行波次降低为 2 个并发波次。

缺点：

- 模型调用总次数和费用不下降；
- Provider 限流时需要降低并发度；
- 首次生成仍没有跨重试缓存。

### 方案 B：多个章节合并为一次模型调用

该方案能进一步减少请求次数，但会放大截断、JSON 修复和整批失败风险，还需要
新增批量输出 schema。本轮不采用。

### 方案 C：先做 Generation Fingerprint 和章节缓存

该方案主要优化重试和重复生成，不能解决首次 6 页生成的 44.5 秒串行延迟。
保留为独立后续任务。

## 4. 运行合同

新增 `generation_max_concurrency` 运行配置：

- 环境变量：`JSTUDY_GENERATION_MAX_CONCURRENCY`；
- 默认值：`3`；
- 合法范围：`1..4`；
- `1` 明确保留串行行为，便于降级和对照；
- 配置随 Worker claim 的不可变 settings snapshot 传入 runner；
- 单个 Job 的活动模型调用不得超过该值。

当前只运行一个 Worker 时，默认最多有 3 个并发章节调用。未来增加 Worker 副本
前，必须重新核算 Provider 的全局并发和速率限制。

## 5. 调度边界

新增独立章节调度模块，不把线程池逻辑继续堆进 `pipeline.py`。

调度输入包含：

- section id、order、title；
- evidence 和 source ids；
- 调用现有 `SectionGenerator` 所需的不可变参数。

调度输出包含：

- 按 `order` 排列的 `MaterialSection`；
- 总生成耗时；
- 每章节耗时与最终状态；
- 实际配置的最大并发数。

线程完成顺序不能改变最终章节顺序。不得共享或修改 evidence、Manifest、
Learning Map、Coverage Ledger。不得在日志或 trace 中记录 API Key、完整 prompt
或课件正文。

## 6. 错误语义

- 现有受控 JSON/schema 失败继续由 `generate_material_section()` 返回
  `failed` section；
- Provider transport、认证或限流异常继续抛给 Worker，由现有 retry/permanent
  分类处理；
- 一个 future 抛出未处理异常后，取消尚未开始的 future，等待已经开始的调用
  安全结束，再抛出原异常；
- Runner 失败时不发布 package、sections 或 completed 状态；
- 不在本轮引入部分章节数据库提交或渐进发布。

## 7. 可观测性

`result-trace.json` 增加不含正文的 `generation_metrics`：

```json
{
  "max_concurrency": 3,
  "section_count": 6,
  "total_duration_ms": 15123,
  "sections": [
    {
      "section_id": "unit-001",
      "order": 1,
      "status": "generated",
      "duration_ms": 7210
    }
  ]
}
```

所有 duration 使用 `time.perf_counter()` 测量。数值只用于运行诊断，不进入
Material Package 的内容身份或质量判断。

## 8. 内容质量约束

根据纵向验收中的重复问题，生成提示增加一条窄规则：

> 同一流程或知识点不要同时完整改写为段落、列表和表格；选择最适合学习的一个
> 主表达形式，只有补充信息确有新增价值时才使用第二种形式。

除此之外不重写 Soul、不改变 block schema、不引入新的自动删改器。

## 9. 验收

自动化验收必须证明：

1. 6 个阻塞式 fake section calls 在并发配置为 3 时，确实同时启动 3 个；
2. 活动调用数从不超过配置；
3. future 完成顺序被打乱时，最终 sections 仍按 `order` 排列；
4. 配置为 1 时行为与旧串行语义一致；
5. Provider 异常不会产生部分公开 artifacts 或 completed Job；
6. trace 只包含安全 timing metadata；
7. 所有现有后端和前端回归保持通过。

代码合并后由 Supervisor 使用同一 6 页测试资料执行 3 次真实 staging 复验：

- created-to-completed 中位数不高于 25 秒；
- 单次不高于 35 秒；
- 6/6 sections 生成；
- 内容质量评分不低于 85/100；
- artifact integrity 全部通过。

真实 staging 未复验前，本任务最高只能获得 `PASS_WITH_LIMITATIONS`。

## 10. 明确不做

- 不实现多章节单请求；
- 不实现渐进式 section 发布；
- 不实现 Generation Fingerprint 或跨重试缓存；
- 不拆分 LLM 与 Embedding credential；
- 不修改 MinerU、Learning Map 或 Evidence 算法；
- 不修改正式前端、HTML/PDF 导出或数据库 schema；
- 不访问真实凭据、腾讯云、Cloudflare 或生产环境。
