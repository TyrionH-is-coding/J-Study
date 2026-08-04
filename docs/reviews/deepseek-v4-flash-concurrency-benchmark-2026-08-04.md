# DeepSeek V4 Flash 并发生成验收

日期：2026-08-04

结论：**Task 0011 自动化测试通过，但真实 staging 性能与可靠性门禁未通过，Supervisor verdict 为 `REVISE`。**

## 1. 验收范围

本次验收使用同一份 6 页医学微生物学合成课件，连续提交三个独立 `single_courseware` Job，检查：

- MinerU、Worker、DeepSeek 官方 API 的完整链路；
- `JSTUDY_GENERATION_MAX_CONCURRENCY=3` 是否真实生效；
- 三次 created-to-finished 中位数是否不超过 25 秒；
- 每次是否不超过 35 秒；
- 每次是否生成 6/6 章节；
- Markdown 内容评分是否不低于 85/100；
- PostgreSQL 中登记的全部 Artifact SHA-256 是否与实际文件一致。

HTML 不在本次范围。

## 2. 基线与安全边界

| 项目 | 值 |
|---|---|
| Git SHA | `9926f2a664761a068adf1ba9fe1c0e2e377c0f09` |
| Image | `jstudy-backend:staging-9926f2a` |
| URL | `https://staging.jstudy.online` |
| Parser | MinerU |
| Chat provider | DeepSeek official API |
| Chat model | `deepseek-v4-flash` |
| Generation concurrency | 3 |
| 输入大小 | 20,964 bytes |
| 输入 SHA-256 | `1efdbaaaaf90e407e695e8b1013a8d6e0fa22a50f1c388c7d724c9afacdbdeef` |

部署前备份：

`/opt/jstudy-staging/backups/pre-9926f2a-20260804-110545`

备份包含 `.env`、settings、PostgreSQL dump、Git SHA、API/Worker 镜像信息和 SHA-256 清单。所有校验和通过，PostgreSQL dump 可被 `pg_restore -l` 正常读取。

DeepSeek Key 只从仓库外授权文件读取，没有写入 Git、报告或测试日志。临时远端 Key 文件已删除。验收后 staging 已恢复为 SiliconFlow `deepseek-ai/DeepSeek-V4-Pro`，保留新镜像和并发上限 3。

## 3. 自动化回归

部署前本地验证：

- focused backend：`140/140`；
- backend full：`398/398`；
- `python -m compileall -q apps packages`：通过；
- frontend lint、typecheck、production build：通过；
- Vitest：`5/5`；
- Playwright：`6/6`；
- Compose services：`postgres`、`jstudy-api`、`jstudy-worker`；
- `git diff --check 1a68bc1..9926f2a`：通过。

这些结果证明实现没有破坏现有合同，但不能替代真实 Provider 和服务器验收。

## 4. 三轮真实结果

| Run | Job ID | 服务端总耗时 | MinerU | 生成 | 章节 | Quality | 人工评分 | Artifact |
|---:|---|---:|---:|---:|---:|---|---:|---:|
| 1 | `dde6226ff8e942cf944f29db8a52e1b9` | 34.701 s | 6.171 s | 27.567 s | 5/6 | fail | 79/100 | 10/10 |
| 2 | `304bf541099b4fee8d42d21d264ec8f5` | 36.046 s | 11.246 s | 24.024 s | 6/6 | pass | 92/100 | 10/10 |
| 3 | `d3fc0d529e734acba8d749f7c47b0fdf` | 25.892 s | 5.687 s | 19.929 s | 6/6 | pass | 90/100 | 10/10 |

客户端 submit-to-terminal 分别为：

- 35.437 秒；
- 37.079 秒；
- 26.719 秒。

服务端 created-to-finished：

- 中位数：34.701 秒；
- 最大值：36.046 秒；
- 相较上一轮约 51.4 秒的服务端耗时，中位数缩短约 32.5%。

生成 Trace 明确记录 `max_concurrency=3`。三轮六章节串行耗时之和均明显高于实际生成总耗时，因此并发调度确实生效。

## 5. 质量评分

评分沿用事实准确性 30、课件覆盖 20、证据与引用 20、学习设计 15、结构与可读性 10、考试实用性 5 的 100 分制。

### Run 1：79/100，关键失败

- 第 3 页 `unit-003` 在两次受控结构化生成后仍失败，最终章节为空；
- 仅生成 5/6 章节，Job quality 为 fail；
- referenced evidence 为 38/71；
- 其余章节未发现关键医学错误，但缺失完整的葡萄球菌毒力因子章节；
- 第 4 页七步流程同时以列表和表格重复表达。

即使其余内容可读，也不能把缺失完整章节的资料作为合格结果交付。

### Run 2：92/100，通过

- 6/6 章节全部生成；
- 5 种菌鉴别表、A 群/PYR、B 群/CAMP、毒力因子、七步流程、MRSA、D 试验和两个病例均保留；
- 未发现关键医学错误或无依据治疗建议；
- facts 均带 evidence 引用，raw referenced evidence 为 52/71；
- 病例正文和病例表存在少量重复，但不影响交付。

### Run 3：90/100，通过

- 6/6 章节全部生成；
- 核心医学内容和引用完整；
- raw referenced evidence 为 52/71；
- 第 4 页完整七步流程先以列表、再以表格重复一次；部分警告框也重复相邻事实；
- 内容仍达到交付水平，但证明仅靠 Prompt 不能稳定消除重复表达。

本次三轮只有 2/3 同时满足 6/6 章节和 85 分内容门槛。

## 6. Artifact 完整性

每个 Job 均持久化 10 类 Artifact：

- chunks；
- trace；
- evidence；
- evidence links；
- Markdown；
- quality；
- material package；
- manifest；
- learning map；
- coverage ledger。

PostgreSQL 中记录的 byte size 和 SHA-256 与 job-owned output root 的实际文件逐项比较，结果为 `30/30` 全部一致。

## 7. 门禁判断

| 门禁 | 要求 | 结果 | 判定 |
|---|---:|---:|---|
| 服务端中位耗时 | <= 25 s | 34.701 s | FAIL |
| 单次最大耗时 | 每次 <= 35 s | Run 2 为 36.046 s | FAIL |
| 章节完整性 | 每次 6/6 | Run 1 为 5/6 | FAIL |
| 内容质量 | 每次 >= 85 | 79、92、90 | FAIL |
| Artifact 哈希 | 全部匹配 | 30/30 | PASS |
| 自动化回归 | 全绿 | 全绿 | PASS |

## 8. 已确认与未知边界

已确认：

1. 有界并发调度在真实 Provider 上工作；
2. 生成阶段由约 44.5 秒下降到 19.9 至 27.6 秒；
3. MinerU 单次解析波动为 5.7 至 11.2 秒；
4. 一个章节在两次结构化尝试后仍进入 `failed` fallback；
5. 当前 Trace 没有记录该章节最终的安全 validation code，因此不能从公开产物确定失败属于 JSON syntax、schema 还是 citation identity；
6. Prompt 级防重复规则没有稳定消除列表与表格的整段重复。

不得直接推断：

- 不能把 Run 1 失败简单归因于模型医学能力；
- 不能仅凭三次样本声称 DeepSeek 官方 API 的长期延迟分布；
- 不能因为 Job terminal 为 completed 就认为所有章节成功。

## 9. REVISE 要求

1. 在不记录 Prompt、正文或 Provider 原始响应的前提下，为每章节 Trace 增加安全的最终失败类型和尝试次数。
2. 对格式失败章节实现有界的定向恢复策略，保证一次局部失败不会直接留下空章节；仍失败时继续保留部分资料语义，不伪装成 6/6 成功。
3. 重新评估默认并发 3 与可用的并发 4，结合单 Worker、Provider 限流和真实延迟做选择；不得只修改门槛。
4. 将总耗时优化目标覆盖 MinerU 与生成阶段，重新连续运行同一样本三次。
5. 增加针对“同一 evidence 集合被完整列表和完整表格重复表达”的确定性测试；避免只依赖 Prompt。
6. 修复后必须重新满足：三次中位数不超过 25 秒、每次不超过 35 秒、每次 6/6、每次至少 85 分、Artifact 全匹配。

## 10. 恢复结果

验收结束后：

- staging 运行 `jstudy-backend:staging-9926f2a`；
- Chat model 恢复为 `deepseek-ai/DeepSeek-V4-Pro`；
- Chat base URL 恢复为 `https://api.siliconflow.cn/v1`；
- `JSTUDY_GENERATION_MAX_CONCURRENCY=3`；
- API healthy；
- readiness ready；
- PostgreSQL/API/Worker 正常；
- active Job 数为 0；
- API/Worker 重启后错误日志为空。
