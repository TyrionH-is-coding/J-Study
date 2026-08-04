# Medicine Soul v2 A/B 对照实验结果

日期：2026-08-04
分支：`feature/backend-frontend-mvp`
实验代码基线：`e2ab5be11d1aebc5d89bc3277f11c10bf088c498`

## 1. 结论

本轮结论为：

> **Soul v2 对教学转化、结构和去重有明确帮助，但当前版本不能进入生产。主要质量上限仍是页级 Learning Unit、缺少全局 Material Plan，以及单节模型在建立知识关联时越过证据边界。**

Medicine Soul v2 达到了“教学转化 + 结构 + 去重”提高 6 分的专项门槛，但没有达到正式替换条件：

- 双评共识总分中位数仅从 `80.0` 提高到 `80.5`，增幅 `+0.5`，未达到 `+8`；
- B 组三份候选均未通过双评安全门禁；
- 事实与证据维度中位数从 `29` 降至 `21`；
- 两位评分者没有同时在至少 2/3 配对中偏好 B；
- citation coverage 没有下降，但 citation 存在不等于邻近结论得到证据支持。

因此：

1. 当前 `soul.md` 确实已注入，质量问题不是“没有 Soul”；
2. Medicine Soul v2 证明 Soul Profile 能改变成品风格；
3. Medicine Soul v2 不能直接替换生产 Soul；
4. 下一步不应继续增加 Prompt，而应先建立轻量 Material Plan 和更严格的证据关系边界。

## 2. 实验输入

正式实验冻结以下输入：

| 项目 | 值 |
|---|---|
| Source Job | `c4ee6fb95d5442bc8b45475cd9dc2202` |
| PDF SHA-256 | `1efdbaaaaf90e407e695e8b1013a8d6e0fa22a50f1c388c7d724c9afacdbdeef` |
| Service mode | `single_courseware` |
| Parser | MinerU |
| Source | `S001` |
| Learning Units | `unit-001` 至 `unit-006` |
| Evidence | `E001` 至 `E071` |
| Model | DeepSeek official API / `deepseek-v4-flash` |
| Section concurrency | `4` |

A、B 两组使用完全相同的：

- Manifest、Learning Map 和完整 MinerU block；
- section id、order、title 和 source id；
- evidence id、内容、页码、block id 和顺序；
- Material Package v2 格式合同；
- 模型、API、并发和调用次数。

唯一变量是 Soul 文本：

- A 组：当前仓库根目录 `soul.md`；
- B 组：实验设计中的 Medicine Soul v2。

## 3. 被废弃的首轮实验

首轮回放错误地把公开 `evidence.json` 中最多 500 字符的 `excerpt` 当成了 Worker 生成时使用的完整 evidence `content`。

该问题在盲评前复核时被发现：

- `E013` 的公开 excerpt 长度为 500；
- 对应 MinerU 原始表格 block 长度为 685；
- 截断部分包含 `S. pyogenes` 的完整线索和 `S. agalactiae` 整行；
- 首轮候选因此不能代表真实生成链路。

处理结果：

- 立即暂停独立评分；
- 评分者确认未读取分组映射、未保存评分；
- 首轮六份候选全部判为无效，不进入任何统计；
- 从原 Job 私有 MinerU `content_list.json` 只读恢复 71 个完整 block；
- 重建后的 block id、source、page、kind 与 `result-chunks.json` 逐项完全一致；
- 重建后的公开 excerpt 与原 Job `evidence.json` 逐项完全一致；
- 正式 A/B 使用 Worker 实际的 4000 字符 generation content 上限。

这一检查也说明：后续回放生成实验不能只保存公开 citation excerpt，必须保存可验证的 generation input fingerprint。

## 4. 生成结果

六份正式候选均满足：

- 6/6 sections；
- 0 failed sections；
- 每节一次 Provider 调用，共 6 次；
- strict `material-package.v2` 校验通过；
- citation、source 和 section identity 校验通过；
- 未在实验产物中发现 API key。

| 组别 | 重复 | 时长 |
|---|---:|---:|
| A | 1 | 14.039 s |
| A | 2 | 14.198 s |
| A | 3 | 12.336 s |
| B | 1 | 20.379 s |
| B | 2 | 11.322 s |
| B | 3 | 15.335 s |

A 组时长中位数为 `14.039 s`，B 组为 `15.335 s`。本轮没有发现 Soul v2 带来不可接受的性能回归，但它也没有形成性能收益。

## 5. 盲评方法

六份 Markdown 随机匿名为 `candidate-1` 至 `candidate-6`。Supervisor 和独立评分者在完成评分前均未读取：

- A/B 分组映射；
- 两份 Soul；
- raw candidate 目录；
- 对方评分；
- 预期赢家。

评分维度：

| 维度 | 分值 |
|---|---:|
| 事实准确性与证据一致性 | 30 |
| 教学转化 | 25 |
| 知识结构与叙事连贯性 | 15 |
| 信息压缩与去重 | 10 |
| 机制、比较与迁移价值 | 10 |
| 记忆与考试实用性 | 10 |

安全门禁独立于总分。高可读性不能抵消事实错误、证据越界或 citation 不支持邻近结论。

## 6. 解盲结果

| 匿名候选 | 分组 | Supervisor | 独立评分 | 双评均值 | 双评安全通过 |
|---|---|---:|---:|---:|---|
| candidate-1 | A1 | 79 | 81 | 80.0 | 是 |
| candidate-2 | A2 | 76 | 79 | 77.5 | 否 |
| candidate-3 | A3 | 82 | 84 | 83.0 | 是 |
| candidate-4 | B1 | 76 | 73 | 74.5 | 否 |
| candidate-6 | B2 | 85 | 76 | 80.5 | 否 |
| candidate-5 | B3 | 84 | 78 | 81.0 | 否 |

### 6.1 分组统计

| 指标 | A 组 | B 组 | B - A |
|---|---:|---:|---:|
| 双评候选均值的组内中位数 | 80.0 | 80.5 | +0.5 |
| 教学转化 + 结构 + 去重中位数 | 35 | 41 | +6 |
| 事实与证据中位数 | 29 | 21 | -8 |
| citation coverage 中位数 | 71.83% | 71.83% | 0 |
| 非空白字符中位数 | 3672 | 4406 | +734 |
| 生成时长中位数 | 14.039 s | 15.335 s | +1.296 s |

Supervisor 对 A/B 的总分中位数分别为 `79/84`，在 2/3 配对中偏好 B。独立评分者的中位数分别为 `81/76`，在 0/3 配对中偏好 B。

这不是简单的评分分歧。两份评审都观察到 B 组更强的教材化组织，但独立评分者对“citation 存在但不能支持新增结论”的处罚更严格。

## 7. 门槛判定

| 预设门槛 | 结果 |
|---|---|
| B 组三份均通过安全门禁 | 未通过 |
| B 组共识中位数至少 80 | 通过，80.5 |
| B 组比 A 组至少提高 8 分 | 未通过，仅 +0.5 |
| 教学转化 + 结构 + 去重至少提高 6 分 | 通过，+6 |
| 两位评分者均在至少 2/3 配对中偏好 B | 未通过 |
| 事实准确性不低于 A | 未通过，-8 |
| citation coverage 不低于 A | 通过，持平 |

Medicine Soul v2 未达到生产替换门槛。

## 8. 主要质量发现

### 8.1 Soul v2 的真实收益

B 组更稳定地出现：

- 知识主题式小标题；
- 中心问题和判断框架；
- 病例的“线索 -> 推理 -> 结论”组织；
- 流程只使用一个有序列表；
- 更少的列表与表格完全重复；
- 首次出现缩写时更完整的术语展开。

这证明 Soul Profile 是有效的产品质量控制层，不应被删除。

### 8.2 Soul v2 的主要风险

Soul v2 要求模型建立机制、鉴别和应用之间的联系，但当前每节只看到一个页级 Learning Unit。模型为了满足教学要求，加入了证据没有明确陈述的关系，例如：

- 将 Protein A 直接对应为“增强侵袭性”；
- 将凝固酶直接对应为“脓肿形成”或“局部感染灶形成”；
- 增加课件没有提供的金黄色葡萄球菌新生霉素结论；
- 把 `single bottle` 扩写为更宽泛的“单次阳性血培养”；
- 把病例级判断扩展为普遍的检验能力结论。

这些内容不一定都是医学常识错误，但违反 J-Study 当前的产品合同：**只能把上传资料能够支持的事实写成确定性结论。**

### 8.3 当前 Soul 也不是完全安全

A2 被独立评分者判定为安全失败，因为它把凝固酶描述为“经典教学模型中的致病性标志”，而邻近 evidence 只支持纤维蛋白形成。

因此不能得出“保留旧 Soul 即可”的结论。当前生成链路仍需要更强的 claim-to-evidence 校验。

### 8.4 共同架构上限

所有六份候选都有以下共同问题：

- 外层章节标题仍是文件名加页码；
- 六页被固定为六个页级章节；
- 缺少一份覆盖全文的 Material Plan；
- 无法在生成前决定哪些知识应合并、前置或只出现一次；
- `E071` 是“最终资料应保留哪些内容”的源文档元指令，却被所有候选当成正文输出为“必须保留的检索目标”；
- citation coverage 只能证明引用了多少 evidence，不能证明 citation 支持邻近结论。

这些问题无法仅通过 Soul 解决。

## 9. 下一步建议

下一张后端任务应聚焦一条轻量主线：

### 9.1 Evidence Role

为 Parsed Block / Evidence 增加最小角色分类：

- `learning_content`
- `source_metadata`
- `author_instruction`

`author_instruction` 可参与覆盖审计，但默认不得作为学习资料正文。当前样本的 `E071` 应进入该角色。

### 9.2 Material Plan v1

在 section generation 前生成并冻结一份轻量 Material Plan：

- knowledge-level section title；
- section objective；
- ordered evidence ids；
- primary source/page span；
- expression policy：paragraph、table、ordered list 或 case；
- repetition owner：某个知识点由哪一节负责完整解释；
- allowed relations：哪些机制到临床结果的关系得到证据支持。

Material Plan 不应改变稳定 `source_id`，也不能让 embedding 重新控制正文顺序。

### 9.3 Grounding Gate

在 Material Package 完成前增加 claim-to-evidence 质量门：

- citation 存在但不支持邻近 claim 时失败；
- 机制到临床后果的新增关系必须有直接 evidence；
- 禁止把病例条件扩展成一般规律；
- 对无法确定支持关系的内容缩小表述，而不是依赖常识补齐。

第一版可以只针对高风险关系和表格新增列做确定性检查，不需要立即引入第二个大模型评审链。

### 9.4 Soul v2.1

保留 Medicine Soul v2 中已验证有效的部分：

- 判断框架；
- 单一主要表达方式；
- 病例推理；
- 去重；
- 知识主题标题。

删除或收紧会迫使模型补全关系的要求。明确规定：

> 只有 evidence 直接支持时，才能把机制映射为具体疾病、结局或临床应用；否则只陈述机制本身。

在 Material Plan 和 Grounding Gate 完成前，不切换生产 Soul。

## 10. 实验产物

完整实验产物保存在仓库外：

`C:\Users\15694\AppData\Local\Temp\jstudy-medicine-soul-v2-ab-full-20260804-154825`

其中包含：

- 冻结 PDF、Manifest、Learning Map、MinerU content list 和完整 generation evidence；
- 六份 strict Material Package v2 与 Markdown；
- 匿名映射；
- Supervisor 与独立评分原始 JSON；
- 客观指标和汇总统计。

仓库不提交上传 PDF、生成资料、API key 或匿名映射。
