# Medicine Soul v2 A/B Experiment Design

## 1. 目标

验证当前生成质量问题主要来自哪一层：

1. 现有 `soul.md` 与 `material-package.v2` 不兼容；
2. 分页 Learning Unit 和缺少全局 Material Plan 才是主要限制；
3. 两者同时存在。

本实验只验证 Soul 的独立贡献，不修改生产代码、数据库、API、Worker、MinerU、Learning Map 或 Material Package 合同。

## 2. 已确认基线

- 当前 staging 确实加载 `/app/soul.md`。
- staging Soul 与仓库根目录 `soul.md` 的 SHA-256 均为：
  `e9f987968c513cdbf96fa57457f0ff6b12497feaee7831a4554a7b4ea765f172`。
- Soul 全文位于章节生成 system prompt 开头。
- 当前 6 页样本被规划为 6 个 Learning Unit。
- 每个章节只接收本 Learning Unit 的 evidence。
- 当前外层章节标题由后端固定为文件显示名和页码范围。

## 3. 候选方案

### 方案 A：只做 Prompt/Soul A/B

冻结同一份 evidence 和 Learning Map，分别使用现有 Soul 与 Medicine Soul v2 生成。

优点：

- 能隔离 Soul 的真实影响；
- 不重复调用 MinerU；
- 不修改产品合同；
- 成本和风险最低。

缺点：

- 无法解决分页切分、外层标题和全局叙事问题。

### 方案 B：Soul v2 与全局 Material Plan 同时测试

先对整份课件生成知识结构，再按结构生成章节。

优点：

- 更接近最终产品质量。

缺点：

- 无法判断改善来自 Soul 还是规划层；
- 会扩大本轮范围。

### 方案 C：直接重构正式生成链路

同时修改 Soul、Planner、Material Package 和 Reader。

优点：

- 可以一次接近目标架构。

缺点：

- 缺少实验依据；
- 风险和返工成本最高。

本轮采用方案 A。只有实验表明 Soul v2 有稳定收益，才进入正式接线；否则优先设计 Material Plan。

## 4. 冻结输入

实验输入使用 Task 0011 corrective Run 1 的固定快照：

- PDF SHA-256：
  `1efdbaaaaf90e407e695e8b1013a8d6e0fa22a50f1c388c7d724c9afacdbdeef`
- Job：
  `c4ee6fb95d5442bc8b45475cd9dc2202`
- Service mode：`single_courseware`
- Parser：MinerU
- Learning Units：`unit-001` 至 `unit-006`
- Evidence：`E001` 至 `E071`
- Source：`S001`

每组必须使用完全相同的：

- section id、order 和 title；
- evidence id、内容和顺序；
- source id；
- Material Package v2 格式指令；
- DeepSeek 官方 API；
- `deepseek-v4-flash`；
- temperature、token limit 和 JSON mode。

不得重新解析 PDF，不得增加检索结果，不得为 B 组提供额外事实。

## 5. A/B 组

### A 组

使用当前仓库根目录 `soul.md`，生成 3 份完整的 6 章节结果。

### B 组

使用下面的 Medicine Soul v2 候选，生成 3 份完整的 6 章节结果。

```text
你是一名医学课程学习资料编辑。你的任务不是翻译、逐页复述或扩写课件，而是把当前证据整理成学生能够理解、比较、记忆和应用的学习单元。

内容边界：
- 只陈述当前证据能够支持的事实。
- 不添加具体患者处方、剂量或缺乏证据的确定性结论。
- 证据不足时缩小表述范围，不用常识补齐缺口。

教学转化：
- 每个学习单元先确定一个中心问题或中心结论。
- 先给判断框架，再展开关键细节。
- 对机制内容使用“结论 -> 原因或机制 -> 鉴别或应用”。
- 对比较内容只使用一张信息密度高的表格；不要再用完整列表重复同一信息。
- 对流程只使用一个有序列表；不要再把相同步骤写成表格。
- 对病例使用“关键线索 -> 推理 -> 结论 -> 易错点”。
- 学习目标只保留能够指导后续学习的版本，不机械照抄。

表达要求：
- 标题直接写知识主题，不使用“本页”“课件内容”“核心定位”“必须保留的检索目标”等元话语。
- 删除不增加新信息的警告、总结和同义复述。
- 首次出现重要英文缩写时，在证据允许的范围内给出中文名称、英文全称和缩写。
- 使用准确、紧凑、自然的中文，避免把英文句子逐句翻译。
- 重点不是增加篇幅，而是提高知识之间的关系密度。

结构选择：
- 每个事实只选择最适合的一种主要表达方式。
- 表格用于横向比较，列表用于步骤或并列要点，callout 只用于真正影响判断的易错点。
- 不为了形式丰富同时生成段落、列表和表格。

质量底线：
- 保留所有关键鉴别结果、流程步骤、机制、病例结论和考试陷阱。
- 不牺牲准确性换取文风。
- 每个事实性知识块都必须紧邻有效 citation。
```

Medicine Soul v2 不包含：

- Markdown、HTML 或隐藏注释指令；
- emoji 和视觉主题；
- API、数据库或 evidence 文件格式；
- service mode 路由；
- Material Package JSON schema；
- 全文目录模板。

这些职责分别属于 renderer、mode policy 和 Material Package 合同。

## 6. 生成次数和随机化

- A 组：3 次。
- B 组：3 次。
- 每次包含 6 个章节。
- 组内使用同一冻结输入。
- 结果保存后随机映射为 `Candidate 1` 至 `Candidate 6`。
- 评分者在评分完成前不得看到 A/B 标签。

允许使用现有有界章节并发，但不得在两组之间改变并发配置。

## 7. 评分标准

### 安全底线

以下任一情况出现即判该份结果不合格：

- 关键医学事实错误；
- 无证据的具体治疗建议；
- 缺失任一 Learning Unit；
- 关键鉴别矩阵、七步流程、MRSA/D 试验或两个病例之一缺失；
- Material Package 校验失败；
- factual block 缺少有效 citation。

### 产品质量 100 分

| 维度 | 分值 |
|---|---:|
| 事实准确性与证据一致性 | 30 |
| 教学转化程度，而非复述 | 25 |
| 知识结构与叙事连贯性 | 15 |
| 信息压缩与去重 | 10 |
| 机制、比较和迁移价值 | 10 |
| 记忆与考试实用性 | 10 |

### Soul v2 成功门槛

B 组只有同时满足以下条件才算成功：

1. 三份结果均通过安全底线；
2. B 组产品质量中位数至少 80；
3. B 组中位数比 A 组至少高 8 分；
4. B 组在“教学转化 + 结构 + 去重”三项合计上至少高 6 分；
5. 两名独立评分者在至少 2/3 配对中偏好 B；
6. 事实准确性与 citation coverage 不低于 A。

## 8. 判定规则

### B 组达到成功门槛

结论：Soul 不只是已注入，而且经过合同适配后能显著改善质量。

下一步：

- 将 Medicine Soul v2 纳入正式 Soul Profile；
- 增加 `soul_profile_id`、`soul_sha256`、`prompt_version` Generation Fingerprint；
- 再单独设计知识标题和 Material Plan。

### B 组有改善但未达到门槛

结论：Soul 有贡献，但分页 Learning Unit 是主要质量上限。

下一步优先设计轻量 Material Plan，不立即替换正式 Soul。

### B 组没有稳定改善

结论：质量问题主要不在 Soul。

下一步停止 Prompt 叠加，转向：

- 知识级 Learning Unit；
- 全局 Material Plan；
- 知识标题；
- 跨章节去重和一致性。

## 9. 产物

实验完成后应保存：

- 冻结输入指纹；
- A/B 六份 Material Package 与 Markdown；
- 匿名映射；
- 两名评分者的原始评分；
- 汇总统计；
- 事实错误和重复表达清单；
- 最终结论与下一张任务卡建议。

所有实验产物存放在仓库外临时目录。仓库只提交实验设计和不含用户资料的总结报告。
