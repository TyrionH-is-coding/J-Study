# J-Study — `eric/user-modes` 分支

> 基于 `feature/backend-frontend-mvp`（`d3cffd6`）分叉
> 本地开发分支，不推远程

---

## 分支方向

**后端完善 × 用户模式自由度 × 通用学科支持**

当前后端已经能跑完整管线（PDF → RAG → LLM → 学习资料），但用户只有一种输出模式，且领域包只有医学。这个分支的目标是：

### 1. 用户模式（输出自由度）

给用户选择生成「什么类型」的学习资料：

| 模式 | 说明 |
|------|------|
| **考前速记** | 浓缩要点、口诀、易混对比表 |
| **总结** | 结构化梳理，章节按大纲组织 |
| **改写** | 用自己的话重述课件内容 |
| **（更多）** | 按需扩展 |

实现方式：通过 `soul_profile_id` 路由不同 soul.md 模板 + 不同的提示词/输出规则组合，已有基础设施支持，需补充 profile 定义和 UI 暴露。

### 2. 通用学科支持

目前只有 `packages/domains/medicine.py`，新增 `general` 领域包：

- 通用查询规划器（从 PDF 提取主题，而非硬编码球菌查询）
- 通用提示词模板（不绑定医学风格）
- 可选的学科包注册机制

远程新代码已支持 `build_study_queries(source_text, outline)` 动态生成查询，这步可以复用。

### 3. 本地开发环境固化

我们已做的改动（不推远程）：

- `embed_api_key` 独立环境变量（LLM 用 DeepSeek key，Embedding 用 DashScope key）
- `batch_size=24→10`（DashScope embedding 上限）
- `model_catalog.json` 使用 DeepSeek + DashScope 配置
- Nginx 直连 + Let's Encrypt HTTPS，不走 Cloudflare Tunnel
- API key 隔离在 `~/jstudy/start_dev.sh`，仓库外

---

## Dev 服务器

| 项目 | 值 |
|------|-----|
| 网址 | https://jstudy.shuttlescope.org |
| 启动 | `bash ~/jstudy/start_dev.sh` |
| 后端 | uvicorn :8887（无 --reload，节省 CPU） |
| 反向代理 | Nginx :80/:443 → :8887，100MB 上传限制 |
| API Key | `~/jstudy/start_dev.sh`（不在仓库内） |

### 启动命令

```bash
bash ~/jstudy/start_dev.sh
```

---

## 本地改动清单

与上游 `feature/backend-frontend-mvp` 的差异：

| 文件 | 改动 |
|------|------|
| `apps/api/jstudy_api/app.py` | `run_job()` 中传 `embed_api_key` 到管线 |
| `packages/core/jstudy_core/pipeline.py` | `run_mvp()` 接受 `embed_api_key` 参数，embedding 调用使用独立的 `resolved_embed_key` |
| `packages/core/jstudy_core/providers.py` | `batch_size=24→10` |
| `data/settings/model_catalog.json` | DeepSeek LLM + DashScope Embedding（不在版本控制） |

---

## 建议的下一步

```
Phase 0: 后端配置 - 模型路由、API key 分离  ✅
Phase 1: soul profile 前端选项展示           📝
Phase 2: general 领域包 + 动态查询优化        📝
Phase 3: 更多用户模式（速记/总结/改写）       📝
Phase 4: 本地前端调试集成                     📝
```
