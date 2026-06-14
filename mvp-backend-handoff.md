# J Study MVP 后端交接说明

本文档用于前端部署测试前快速理解当前 MVP 后端。当前后端仍是单机 MVP，不是生产后端。

## 1. 后端范围

当前 MVP 目标：

1. 用户上传单个课件 PDF，可选上传课程大纲。
2. 后端解析 PDF 文本，构建课件 RAG。
3. 后端从 `mnemonics.md` 检索关联口诀。
4. 后端按 `soul.md` 的学习资料模板生成 Markdown。
5. 后端生成 evidence / citation 映射，前端点击“依据 E001”后跳到 PDF 对应页。

当前不包含：

1. 用户系统、权限、计费、任务队列。
2. 云存储、数据库、持久 job 状态。
3. 多文件大纲版完整工作流。
4. 生产级 CORS、限流、文件大小限制、任务清理。

## 2. 核心文件

| 文件 | 作用 |
| :-- | :-- |
| `web_mvp.py` | FastAPI 服务入口，提供上传、任务状态、产物读取、PDF 页面 PNG 接口，同时内置当前测试前端页面。 |
| `mvp_runner.py` | 单课件 RAG + LLM 生成流水线。可被 CLI 调用，也被 `web_mvp.py` 作为 runner 调用。 |
| `soul.md` | 输出风格与学习资料格式规则。 |
| `mnemonics.md` | 测试口诀库。 |
| `rag-config.example.json` | RAG 参数示例。 |
| `siliconflow api key.txt` | 本地 API key 文件。不要提交、不要暴露到前端。 |
| `tests/` | 当前后端与渲染合约测试。 |
| `web_jobs/` | Web 任务输入、输出、embedding cache 的本地存储目录。 |

## 3. 本地运行

在 `D:\大二下\deep tutor\J study` 下运行：

```powershell
python -m uvicorn web_mvp:app --host 127.0.0.1 --port 8765
```

访问：

```text
http://127.0.0.1:8765/
```

当前默认模型：

| 类型 | 默认值 |
| :-- | :-- |
| LLM | `deepseek-ai/DeepSeek-V4-Pro` |
| Embedding | `BAAI/bge-m3` |
| API Base | `https://api.siliconflow.cn/v1` |

CLI 也可以直接跑：

```powershell
python mvp_runner.py --pdf "12-球菌.pdf" --output-prefix mvp-v2
```

## 4. Python 依赖

当前代码直接依赖：

| 包 | 用途 |
| :-- | :-- |
| `fastapi` | API 服务 |
| `uvicorn` | 本地 ASGI server |
| `python-multipart` | FastAPI 文件上传 |
| `PyMuPDF` / `fitz` | PDF 文本解析、PDF 页面渲染 PNG |
| `httpx` | 测试中的 FastAPI TestClient 依赖 |

当前目录还没有正式 `requirements.txt`，前端部署测试前建议补一个独立依赖文件。

## 5. 后端处理流程

`web_mvp.py` 的 `/api/generate` 收到上传后，会创建一个本地 job：

```text
web_jobs/{job_id}/
├── input/
│   ├── uploaded.pdf
│   └── outline.md   # 可选
└── output/
    ├── result-chunks.json
    ├── result-retrieval_trace.json
    ├── result-evidence.json
    ├── result-evidence_links.json
    ├── result-output.md
    └── result-quality.json
```

`mvp_runner.py` 的核心流程：

```text
PDF
↓
PyMuPDF 提取逐页文本
↓
按页切 chunk
↓
SiliconFlow embedding，写入本地 cache
↓
多查询 + hybrid reciprocal-rank fusion 检索 evidence chunks
↓
从 mnemonics.md 检索关联口诀
↓
用 soul.md + evidence + 口诀 + 可选大纲构造 prompt
↓
调用 LLM 生成 Markdown
↓
生成 evidence_links 和 quality report
```

## 6. API 合约

### 6.1 创建生成任务

```http
POST /api/generate
Content-Type: multipart/form-data
```

字段：

| 字段 | 必填 | 类型 | 说明 |
| :-- | :-- | :-- | :-- |
| `pdf` | 是 | file | 课件 PDF |
| `outline` | 否 | file | 课程大纲，当前接受 `.md/.txt/.pdf`，但大纲内容按文本读取 |

响应：

```json
{
  "job_id": "a11a47d34f50",
  "status": "queued",
  "status_url": "/api/jobs/a11a47d34f50"
}
```

### 6.2 查询任务状态

```http
GET /api/jobs/{job_id}
```

响应：

```json
{
  "job_id": "a11a47d34f50",
  "status": "completed",
  "error": "",
  "quality": {
    "status": "pass"
  },
  "output_url": "/api/jobs/a11a47d34f50/output",
  "evidence_url": "/api/jobs/a11a47d34f50/evidence",
  "evidence_links_url": "/api/jobs/a11a47d34f50/evidence-links",
  "pdf_url": "/api/jobs/a11a47d34f50/pdf",
  "pdf_info_url": "/api/jobs/a11a47d34f50/pdf-info",
  "pdf_page_url_template": "/api/jobs/a11a47d34f50/pdf-page/{page}.png"
}
```

状态值：

| status | 含义 |
| :-- | :-- |
| `queued` | 已创建，等待后台任务 |
| `running` | 生成中 |
| `completed` | 已完成 |
| `failed` | 失败，查看 `error` |

### 6.3 获取学习资料 Markdown

```http
GET /api/jobs/{job_id}/output
```

响应：

```json
{
  "markdown": "# 学习资料..."
}
```

Markdown 中会包含隐藏 evidence 注释：

```markdown
葡萄球菌为革兰阳性球菌。<!-- evidence: E003 -->
```

前端需要把这些注释渲染成“依据 E003”按钮。隐藏注释本身不应显示给用户。

### 6.4 获取 evidence 与 citation 映射

```http
GET /api/jobs/{job_id}/evidence
```

响应：

```json
{
  "evidence": [
    {
      "id": "E001",
      "source_file": "12-球菌.pdf",
      "page": 2,
      "chunk_id": "C002",
      "score": 0.0492,
      "excerpt": "病原性球菌 又称为化脓性球菌...",
      "query_id": "overview",
      "query_title": "体系概览",
      "retrieval_method": "hybrid_rrf"
    }
  ],
  "evidence_links": [
    {
      "ref_id": "E001",
      "occurrence": 1,
      "comment_index": 1,
      "target": {
        "source_file": "12-球菌.pdf",
        "page": 2,
        "chunk_id": "C002",
        "quote": "病原性球菌 又称为化脓性球菌..."
      }
    }
  ]
}
```

也可以只取映射：

```http
GET /api/jobs/{job_id}/evidence-links
```

### 6.5 获取 PDF 原文件

```http
GET /api/jobs/{job_id}/pdf
```

返回 `application/pdf`。

### 6.6 获取 PDF 页信息

```http
GET /api/jobs/{job_id}/pdf-info
```

响应：

```json
{
  "page_count": 42,
  "pages": [
    {
      "page": 1,
      "width": 960.0,
      "height": 540.0
    }
  ]
}
```

### 6.7 获取 PDF 单页 PNG 预览

```http
GET /api/jobs/{job_id}/pdf-page/{page}.png
```

返回 `image/png`。当前用 PyMuPDF 按 `1.6x` matrix 渲染。

## 7. 前端接入建议

前端部署测试推荐流程：

```text
1. FormData 上传 pdf + outline
2. 从 /api/generate 拿 job_id/status_url
3. 轮询 /api/jobs/{job_id}
4. status=completed 后并发请求：
   - output_url
   - evidence_url
   - pdf_info_url
5. 渲染 Markdown
6. 根据 Markdown 中的 evidence 注释生成按钮
7. 根据 evidence_links 把按钮映射到 PDF page
8. 用 /pdf-page/{page}.png 渲染右侧逐页 PDF 预览
```

当前已验证的交互规则：

1. 学习资料区域和 PDF 预览区域应是两个独立滚动模块。
2. 点击学习资料里的“依据 E001”按钮时，只滚动右侧 PDF 预览容器。
3. 不要对 PDF 页元素调用 `target.scrollIntoView()`，否则浏览器可能滚动外层页面。
4. 应该只滚动 PDF 容器本身，例如 `pdfPages.scrollTo(...)`。

## 8. 部署测试注意事项

### CORS

当前 `web_mvp.py` 没有配置 CORS。

如果前端和后端不是同源，例如：

```text
frontend: http://localhost:3000
backend:  http://127.0.0.1:8765
```

需要二选一：

1. 前端 dev server 配代理，把 `/api/*` 代理到后端。
2. 在 FastAPI 加 `CORSMiddleware`，限制允许的前端 origin。

### Job 状态

当前 job 状态存在 `web_mvp.py` 进程内存里：

```python
jobs: dict[str, dict[str, Any]] = {}
```

服务重启后：

1. `web_jobs/{job_id}/output` 文件仍在磁盘。
2. 但 `/api/jobs/{job_id}` 会找不到内存状态。

前端部署测试阶段可以接受；生产化需要数据库或任务表。

### 本地文件存储

当前上传 PDF、输出 Markdown、evidence、PDF 页渲染都走本地磁盘。

生产化需要考虑：

1. 上传文件大小限制。
2. 文件清理策略。
3. 对象存储或持久卷。
4. 用户隔离。

### API Key

当前从本地文件读取：

```text
siliconflow api key.txt
```

部署时应改为环境变量或密钥管理，不要让前端知道 key。

### 并发

当前生成任务通过 FastAPI `BackgroundTasks` 在同一进程中执行。生成时间较长，且 LLM/embedding 调用会占用后端进程资源。

生产化建议：

1. 单独任务队列。
2. worker 进程。
3. 任务超时与取消。
4. 失败重试。

## 9. 当前验证命令

```powershell
python -m py_compile "D:\大二下\deep tutor\J study\web_mvp.py"
python -m unittest discover -s "D:\大二下\deep tutor\J study\tests" -v
```

当前测试覆盖：

1. RAG chunk / retrieval / evidence / quality audit。
2. evidence links 到 PDF 页码的映射。
3. Web API 任务创建、输出、evidence、PDF info、PDF page PNG。
4. 前端 HTML 中的 Markdown 渲染、PDF 页预览、独立滚动相关合约。

## 10. 前端部署测试前的最小检查清单

1. 后端能启动：`python -m uvicorn web_mvp:app --host 127.0.0.1 --port 8765`
2. `GET /` 返回 200。
3. `POST /api/generate` 能返回 `job_id`。
4. 轮询到 `completed`。
5. `GET /output` 返回 Markdown。
6. `GET /evidence` 返回 evidence 和 evidence_links。
7. `GET /pdf-info` 返回页数。
8. `GET /pdf-page/1.png` 返回 PNG。
9. 前端点击 evidence 按钮后只滚动 PDF 容器，不滚动学习资料区域。
10. 前端部署若跨域，先处理代理或 CORS。
