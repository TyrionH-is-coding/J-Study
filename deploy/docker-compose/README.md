# 后端 Docker Compose 运行手册

该 Compose 文件提供 pilot 阶段的三服务拓扑：

- `postgres`：持久化 Job、source、section、artifact、transition 以及认证数据。
- `jstudy-api`：接收和校验上传、创建 durable Job、提供轮询与 artifact API；不在 API 进程内执行生成。
- `jstudy-worker`：认领 Job、续租、调用现有 pipeline、登记 artifact，并执行 Job retention 清理。worker 不暴露端口。

API 与 worker 使用同一 `jstudy-backend:pilot` 镜像、同一数据库配置，并以读写方式挂载同一个 jobs volume 和 settings volume。

## 启动

在仓库根目录准备 `.env`，不要把真实密钥提交到 Git。`JSTUDY_DATABASE_URL` 是首选数据库变量；旧 `DATABASE_URL` 仍作为兼容 fallback。

```powershell
Copy-Item .env.example .env
docker compose -f deploy/docker-compose/api.compose.yml config
docker compose -f deploy/docker-compose/api.compose.yml up -d --build
```

生产使用前至少替换以下开发默认值：

```text
POSTGRES_PASSWORD=
JSTUDY_DATABASE_URL=postgresql+psycopg://jstudy:<url-encoded-password>@postgres:5432/jstudy
JSTUDY_SESSION_SECRET=
JSTUDY_COOKIE_SECURE=true
```

数据库 URL 中的数据库名、用户和密码必须与 `POSTGRES_DB`、`POSTGRES_USER`、`POSTGRES_PASSWORD` 一致；密码包含保留字符时需要 URL 编码。

## 日志与停止

查看全部服务日志：

```powershell
docker compose -f deploy/docker-compose/api.compose.yml logs -f
```

分别查看 API 或 worker：

```powershell
docker compose -f deploy/docker-compose/api.compose.yml logs -f jstudy-api
docker compose -f deploy/docker-compose/api.compose.yml logs -f jstudy-worker
```

停止服务但保留持久数据：

```powershell
docker compose -f deploy/docker-compose/api.compose.yml down
```

不要在有保留价值的数据上使用 `down -v`。

## 健康检查

`GET /api/health` 是 liveness，只确认 API 进程存活，供容器和反向代理使用：

```powershell
curl http://127.0.0.1:8765/api/health
```

`GET /api/readiness` 是 readiness，还会检查 Job 目录、运行文件、provider 配置和数据库连接；只有 ready 后才应接收用户提交：

```powershell
curl http://127.0.0.1:8765/api/readiness
```

部署阶段可显式探测 SiliconFlow：

```powershell
curl "http://127.0.0.1:8765/api/readiness?probe_provider=true"
```

worker 没有 HTTP liveness endpoint，也没有 `ports` 映射；其运行状态通过容器状态、日志以及 Job lease/transition 观测。

## 持久化与清理

- PostgreSQL 数据挂载在 `data/postgres`。
- 上传和生成 artifact 挂载在 `data/jobs`。
- 管理员运行设置挂载在 `data/settings`。
- Compose 不注入模型、provider key、parser、Soul/content pack、
  `max_pdf_bytes` 或 retention 的环境覆盖值；这些可热更新字段以
  `data/settings` 为准，使新 submission 和新 claim 无需重启即可读取更新。
- `JSTUDY_JOB_RETENTION_HOURS` 为正数时，retention 由 worker 执行；API 不负责删除 Job。
- 旧 `jobs.json` 实现仍保留为 compatibility boundary，但 production API/worker 不 import 或写入它。

当前 API 和 worker 会通过 SQLModel `create_all()` 建表。这只适用于数据可丢弃的 disposable pilot。开始保存持久用户数据前，必须先引入 versioned migrations，并编写迁移、回滚、备份与恢复 runbook；不能把 `create_all()` 当作生产 schema migration。

当前 pipeline 继续输出 Markdown 和 `material_package` v1，也继续使用既有 parser 默认行为。本 Compose 变更不实施 HTML，也不切换 MinerU pipeline。
