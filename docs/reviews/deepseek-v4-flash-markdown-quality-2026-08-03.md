# DeepSeek V4 Flash Markdown 生成质量验收

日期：2026-08-03

当前结论：**修复后本地复测 92/100，腾讯云 staging 纵向复测 91/100，内容质量通过；上线状态为 `PASS_WITH_LIMITATIONS`。**

初次 staging 结果为 2/100。该分数记录修复前的真实故障，不再代表当前本地代码。

## 1. 验收目标

本次验收只回答一个问题：

> 当前 J-Study 正式生成链路使用 `deepseek-ai/DeepSeek-V4-Flash` 时，能否从医学课件生成可交付的 Markdown 学习资料？

本次不测试 HTML，也不把结果解释为对 DeepSeek V4 Flash 医学能力的完整评价。测试覆盖的是 J-Study 当前的 MinerU 解析、顺序规划、结构化资料生成、引用和 Markdown 导出整条链路。

## 2. 测试基线

| 项目 | 值 |
|---|---|
| Job ID | `dcd2f63f520b491085e8e16fd4e3a04f` |
| Service mode | `single_courseware` |
| Chat model | `deepseek-ai/DeepSeek-V4-Flash` |
| Parser | `mineru` |
| Generation strategy | `sequence-first` |
| Scenario | `medicine-default` |
| 输入 PDF | 6 页医学微生物学合成测试课件 |
| 输入大小 | 20,964 bytes |
| 输入 SHA-256 | `1efdbaaaaf90e407e695e8b1013a8d6e0fa22a50f1c388c7d724c9afacdbdeef` |

测试课件包含革兰阳性球菌鉴别表、金黄色葡萄球菌毒力因子、诊断流程图、MRSA 检测与治疗原则、病例和考试易错点。它同时覆盖普通文本、表格、流程图和医学事实，适合作为第一轮固定质量样本。

生成完成后，所有评分均基于已经下载到本地的只读产物进行，没有再次修改服务器配置或提交新 Job。

## 3. 修复前最终 Markdown（历史基线）

最终 Markdown 只有总标题和六个页级章节标题，没有任何正文、表格、知识点、病例、引用或复习内容：

```markdown
# 完整学习资料

## jstudy-quality-deepseek-v4-flash 第 1-1 页

## jstudy-quality-deepseek-v4-flash 第 2-2 页

## jstudy-quality-deepseek-v4-flash 第 3-3 页

## jstudy-quality-deepseek-v4-flash 第 4-4 页

## jstudy-quality-deepseek-v4-flash 第 5-5 页

## jstudy-quality-deepseek-v4-flash 第 6-6 页
```

`result-output.md` 只有 315 bytes。该结果不能作为学习资料交付。

## 4. 修复前评分

评分门槛为 80/100。出现关键医学错误、引用失效或整体无正文时直接判定关键失败。

| 维度 | 权重 | 得分 | 判断 |
|---|---:|---:|---|
| 事实准确性 | 30 | 0 | 没有正文事实可供核验；在产品质量评分中不能因“没有错误”获得分数 |
| 课件覆盖 | 20 | 0 | 课件内容未进入最终资料 |
| 证据与引用 | 20 | 0 | 71 条 evidence 全部未引用，citation coverage 为 0 |
| 学习设计 | 15 | 0 | 没有解释、关联、病例、总结或复习结构 |
| 结构与可读性 | 10 | 2 | 只保留了六个顺序正确的页级标题 |
| 考试实用性 | 5 | 0 | 没有高频考点、易错点或自测内容 |
| **总分** | **100** | **2** | **关键失败** |

## 5. 分阶段判断

### 5.1 MinerU 解析：通过

- 识别出 71 个 usable blocks。
- 71 个 blocks 全部进入 Learning Map。
- 第 2 页鉴别表被保留为结构化 HTML table。
- 第 3 页 Protein A、凝固酶、剥脱毒素等医学文本提取正确。
- 第 4 页流程图同时保留了图像和文本块。
- 第 5、6 页 MRSA、病例和考试易错点均可在 evidence 中找到。

因此，本次失败不是由“PDF 没有解析出来”造成的。

### 5.2 顺序规划：通过

Coverage Ledger 显示：

- `coverage_rate = 1.0`
- `usable_block_count = 71`
- `used_block_count = 71`
- `ignored_block_count = 0`
- `large_jump_count = 0`
- `remote_reference_ratio = 0.0`

六个 Learning Unit 按第 1 页到第 6 页排列，sequence-first 主顺序符合当前产品设计。

### 5.3 结构化章节生成：失败

`material-package.v2` 中：

- section count：6
- generated section count：0
- failed section count：6
- block count：0
- evidence count：71
- referenced evidence count：0

当前实现会对每个章节最多调用两次结构化生成。第一次结果解析或验证失败后，第二次会携带安全的验证摘要修复；第二次仍失败时，系统返回空的 `failed` section。本次六章全部进入该分支。

### 5.4 Markdown 渲染：机制正常，产品结果失败

Markdown 渲染器忠实地把六个空章节渲染成了六个标题，因此渲染器本身没有制造额外错误。但其输入资料包没有正文，所以最终 Markdown 仍然不可用。

### 5.5 Job 终态：不合理

该 Job 最终进入 `completed`，但质量报告同时给出：

- `status = fail`
- `generated_section_count = 0`
- 六个 `failed_section`

“全部章节失败但 Job completed”会让前端和用户误以为资料生成成功，应视为后端产品语义缺陷。

## 6. 修复前的事实与原因边界

以下判断记录的是本地最小复现完成之前的证据边界。第 10 节的受控复现已经进一步确认根因，因此本节中的“尚不能确认”不代表当前仍未知。

### 已确认

1. 模型 ID 确实是 `deepseek-ai/DeepSeek-V4-Flash`。
2. MinerU 已正确提取课件主要内容。
3. Learning Map 已完整、连续地覆盖 71 个 blocks。
4. 六次章节生成最终都没有产生合法 `MaterialSection`。
5. 每章最多一次修复仍未恢复。
6. 当前公开产物没有保存具体的模型输出错误类别或最终验证摘要。

### 尚不能确认

无法仅凭现有产物判断每章失败的精确原因。可能原因包括：

- 模型返回的内容不是合法 JSON object；
- JSON 可以解析，但不满足严格 `MaterialSection` schema；
- section、source、evidence 或 citation identity 与冻结合同不一致；
- 模型输出被截断或包含当前校验器拒绝的字段。

这些是候选解释，不是已经证明的根因。由于缺少安全的逐次失败诊断，不应把本次结果简单归因于模型医学知识不足。

## 7. 修复前提出的上线阻断项

初次故障后提出了以下修复要求。当前完成状态如下：

1. 安全诊断 artifact：未完成，仍是生产可观测性缺口。
2. 全章节失败时 Job 失败：已完成。
3. V4 Flash 最小单章节 live contract probe：已完成。
4. 根据真实失败码调整 prompt 和生成合同：已完成。
5. 同一资料和 rubric 的 V4 Flash 复测：已完成；V4 Pro 对照尚未执行。

复测最低要求：

- 6/6 sections 产生正文；
- failed sections 为 0；
- citation coverage 不低于 0.85；
- 必考知识覆盖率不低于 90%；
- 不存在关键医学错误或无依据治疗建议；
- 总分不低于 80/100。

## 8. 产物校验

| 产物 | Bytes | SHA-256 |
|---|---:|---|
| `result-output.md` | 315 | `0e615deff2d85566cc72721ac470f87502bfd95d9612d5083c5bbbefd0c980e9` |
| `result-package.json` | 3,952 | `a40467e4ecf12f07145cb626b1731ba428c79b3d3abf74ffebf5c89d4ae2470d` |
| `result-quality.json` | 1,879 | `52a6cd0f7f3d8dc7c7630972bed240c49a64848a0c9736b00a774de8c27dedcf` |
| `result-coverage-ledger.json` | 14,608 | `b6a840c029e5bb6d742a2e52f211ad3a5cd7ea8787a62ddd0905dc29b576ae86` |
| `result-retrieval_trace.json` | 1,466 | `e7913db5018216b167f37c07cd88b7d0d7403e7bd9d5dc123e694e78b1ec5959` |

## 9. 修复前初始决策（已被本地复测更新）

修复前的决策是：**不能批准 DeepSeek V4 Flash 作为 J-Study 的生产默认生成模型。**

这次测试证明 MinerU 和 sequence-first 规划链路已经工作，但尚未证明 V4 Flash 能通过 J-Study 当前的严格结构化生成合同。下一步应先修复可观测性和 Job 终态语义，再重跑质量对照测试。

第 12、13 节记录修复后的新结论。HTML 按本次要求未测试。

## 10. 根因复现

后续使用用户明确授权的 DeepSeek 官方 Key 进行本地最小复现。Key 仅从仓库外文件读取，没有写入仓库、测试日志或报告。

官方 `/models` 返回：

- `deepseek-v4-flash`
- `deepseek-v4-pro`

对原 Job 第一章节使用当前生产 Prompt：

- API 正常结束；
- JSON 语法合法；
- 顶层字段为 `blocks/order/section_id/title`；
- 后端实际要求 `id/order/title/status/quality/source_ids/evidence_ids/blocks`；
- block 使用直觉性的 `content` 字段，而严格合同要求 `id/runs`。

第一次稳定错误包括：

- `id:missing`
- `status:missing`
- `quality:missing`
- `source_ids:missing`
- `evidence_ids:missing`
- `blocks.*.id:missing`
- `blocks.*.runs:missing`
- `blocks.*.content:extra_forbidden`

第二次修复请求补出部分顶层字段，但仍不知道完整 block 结构，因此再次失败。根因是 Prompt 合同与真实 Pydantic 合同不一致，不是模型医学能力不足。

进一步检查发现第二个独立缺陷：表格 evidence `E013` 被 `clean_quote(..., 500)` 截断为恰好 500 字符，并停在 `S. pyogenes` 行中部。`S. agalactiae`、A 群/PYR 和 B 群/CAMP 的完整内容没有发送给模型。

## 11. 修复内容

1. 模型只负责生成 `blocks`，不再生成服务端已有的 section identity、status、quality、source ids 和 evidence ids。
2. Prompt 提供完整 block/run 形状及合法 JSON 示例。
3. 服务端根据冻结的 Learning Unit 和 evidence 确定性构造最终 `MaterialSection`。
4. DeepSeek 官方 V4 JSON 请求关闭默认 thinking mode；SiliconFlow 路径不受影响。
5. 用户可见 evidence excerpt 继续限制为 500 字符，生成专用 content 独立限制为 4,000 字符。
6. 表格 Prompt 明确要求保留全部行/流程步骤并附带 citation run。
7. 所有章节均失败时，Worker 将 Job 标记为 `failed / invalid_job_output`，不再发布普通 `completed`。

## 12. 修复后本地复测

### 12.1 运行结果

| 指标 | 修复前 | 修复后 |
|---|---:|---:|
| generated sections | 0/6 | 6/6 |
| failed sections | 6/6 | 0/6 |
| Markdown bytes | 315 | 9,550 |
| material blocks | 0 | 52 |
| raw referenced evidence | 0/71 | 55/71 |
| quality status | fail | pass |
| 六章节生成耗时 | 约 29 分钟 | 52.22 秒 |

原始 55/71 引用率包含不应强制引用的结构块。16 条未引用 evidence 中有 9 个标题、6 个流程图图片块和 1 个结构标题。事实文本和表格内容均已进入最终资料并带引用。

修复后 Markdown：

- 本地路径：`C:\Users\15694\AppData\Local\Temp\jstudy-v4-flash-quality-repro\fixed-final-output.md`
- SHA-256：`5f006820a30c9fc7183e56776bca1013bbdd144c0304a47981b073d4b3ad7ca6`

完整表格 content 进入 Prompt 后，V4 Flash 保留了：

- 5/5 个菌种；
- 化脓性链球菌 A 群和 PYR 阳性；
- 无乳链球菌 B 群和 CAMP 阳性；
- 表格来源引用 E013。

### 12.2 修复后评分

| 维度 | 权重 | 得分 | 判断 |
|---|---:|---:|---|
| 事实准确性 | 30 | 29 | 未发现关键医学错误或无依据治疗建议 |
| 课件覆盖 | 20 | 19 | 核心表格、流程、耐药机制、病例和易错点均保留 |
| 证据与引用 | 20 | 17 | 事实内容均可追溯；全局 raw 指标仍需区分结构块 |
| 学习设计 | 15 | 14 | 有矩阵、流程、病例、警示和考试陷阱 |
| 结构与可读性 | 10 | 8 | 整体清晰，页级标题和部分表现形式仍可继续优化 |
| 考试实用性 | 5 | 5 | 高频鉴别点和常见陷阱明确 |
| **总分** | **100** | **92** | **通过** |

## 13. 当前决策

DeepSeek V4 Flash 的模型能力可以满足本样本。修复后的本地生成合同和 Markdown 内容质量通过。

当前仍为 `PASS_WITH_LIMITATIONS`，原因是：

1. LLM 与 Embedding 运行时仍共用一套有效凭据。官方 DeepSeek Chat 与 SiliconFlow Embedding 不能长期配置为不同 Key，因此 staging 验收后已恢复原 SiliconFlow V4 Pro 配置。
2. 全局 citation coverage 仍把标题和图片块计入分母，指标语义需要单独修正。
3. 少数 callout 或流程内容存在重复表达；不影响事实正确性，但需要后续确定性归一化或去重。
4. 本次按要求未测试 HTML。

## 14. 腾讯云 Staging 纵向复测

### 14.1 部署基线

| 项目 | 值 |
|---|---|
| Git SHA | `01dc49e0141736d3a1654718d1d740114ea521a5` |
| Image | `jstudy-backend:staging-01dc49e` |
| Image ID | `sha256:86667c6461da563562b7f36236c4ee255932a6942521a8178e68299402667300` |
| URL | `https://staging.jstudy.online` |
| Parser | MinerU |
| Chat provider | DeepSeek official API |
| Chat model | `deepseek-v4-flash` |

部署前备份：

`/opt/jstudy-staging/backups/pre-01dc49e-20260803-150245`

备份包含 `.env`、settings、PostgreSQL dump、原 Git SHA、原镜像信息和 SHA-256 清单，全部校验通过。

### 14.2 配置优先级故障记录

首个复测 Job：

`17cb913d2998459fb9429511e65b753f`

该 Job 在 `generating` 阶段两次收到 401，最终正确进入 `failed / worker_error`，没有发布 artifact。原因不是 DeepSeek Key 失效，而是重建容器的 Bash 进程此前 source 了旧 `.env`；父进程中的旧 SiliconFlow Key 和 V4 Pro 模型覆盖了刚写入的 `--env-file`。

从干净 shell 重建后：

- Worker Key 指纹与本地授权 Key 一致；
- Worker 读取 `deepseek-v4-flash`；
- Worker 容器内最小 JSON 探针通过。

### 14.3 成功 Job

成功 Job：

`ad08a441b88741acb01f26379f17604c`

状态变化：

```text
queued -> parsing -> retrieving -> generating -> packaging -> completed
```

结果：

| 指标 | 结果 |
|---|---:|
| attempt | 1 |
| Job completed | 57.1 秒 |
| 客户端完成全部 artifact 下载 | 62.1 秒 |
| sections | 6/6 generated |
| material blocks | 52 |
| citation runs | 74 |
| unique referenced evidence | 53/71 |
| coverage ledger | 71/71 used |
| Markdown artifact | 8,876 bytes |
| Worker quality | pass |

18 条未引用 evidence 由 12 个结构标题和 6 个流程图图片块组成；事实文本和表格 evidence 均已引用。第 2 页鉴别表完整保留 5 个菌种、A 群/PYR、B 群/CAMP 和 `E013` 引用。

Package、Markdown、Evidence、Evidence Links、Trace、Manifest、Learning Map 和 Coverage 等公开 endpoint 全部返回 200。数据库登记的 10 个 artifact 文件大小和 SHA-256 为 `10/10` 一致，公开下载产物未发现 Key、Token、Authorization header、签名 URL 或服务器绝对路径。

### 14.4 Staging 人工评分

| 维度 | 权重 | 得分 | 判断 |
|---|---:|---:|---|
| 事实准确性 | 30 | 29 | 未发现关键医学错误或无依据治疗建议 |
| 课件覆盖 | 20 | 19 | 表格、毒力、流程、耐药、病例和易错点均保留 |
| 证据与引用 | 20 | 17 | 事实证据完整可追溯；全局 raw 分母仍包含结构块 |
| 学习设计 | 15 | 13 | 有矩阵、流程、病例和警示，但部分内容重复 |
| 结构与可读性 | 10 | 8 | 整体清晰；第 4 页七步流程同时用段落、列表、表格表达 |
| 考试实用性 | 5 | 5 | 高频鉴别点和考试陷阱明确 |
| **总分** | **100** | **91** | **通过** |

### 14.5 验收后状态

验收完成后：

- staging 保留新代码镜像 `staging-01dc49e`；
- API、Worker、PostgreSQL 健康；
- 原 SiliconFlow V4 Pro 配置已从备份恢复；
- `/api/readiness?probe_provider=true` 返回 ready；
- 官方 DeepSeek 临时 Key 文件已删除；
- 成功和失败 Job 均保留作验收证据。
