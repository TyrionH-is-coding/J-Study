# Tencent Staging Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不影响现有 `jstudy.online` 和旧容器的前提下，为 J-Study 建立可重复、可回滚的腾讯云隔离 staging 部署。

**Architecture:** 复用现有 PostgreSQL + FastAPI + Worker Compose 拓扑，仅将镜像名、容器名和 API 绑定地址参数化。staging 使用独立 checkout、独立数据目录、独立容器名、独立数据库和 `127.0.0.1:8766`，由 Nginx 将 `staging.jstudy.online` 反向代理到该端口。

**Tech Stack:** Docker Compose、FastAPI、PostgreSQL 16、Nginx、Let's Encrypt、Cloudflare DNS、Python unittest。

---

## File Structure

- Modify `deploy/docker-compose/api.compose.yml`: 保留现有默认值，增加 staging 所需的环境变量插值。
- Modify `.env.example`: 记录镜像、容器名、绑定地址和端口变量。
- Modify `deploy/docker-compose/README.md`: 记录默认部署与隔离 staging 命令。
- Modify `docs/deployment/server-runbook.md`: 记录 staging 目录、域名、回滚和真实 Job 验收。
- Modify `tests/test_deployment_files.py`: 通过 `docker compose config --format json` 验证默认值和隔离值。
- Create `multi-agent/jstudy-product-build/reports/0010-tencent-staging-deployment-report.md`: 记录 Code Agent 实施结果；不得包含任何密钥。

### Task 1: Compose Isolation Contract

**Files:**
- Modify: `tests/test_deployment_files.py`
- Modify: `deploy/docker-compose/api.compose.yml`

- [ ] **Step 1: Write failing tests for default and staging values**

新增测试并通过 `docker compose config --format json` 断言：

```python
expected = {
    "JSTUDY_IMAGE_NAME": "jstudy-backend:staging-test",
    "JSTUDY_API_CONTAINER_NAME": "jstudy-staging-api",
    "JSTUDY_WORKER_CONTAINER_NAME": "jstudy-staging-worker",
    "JSTUDY_POSTGRES_CONTAINER_NAME": "jstudy-staging-postgres",
    "JSTUDY_API_BIND_ADDRESS": "127.0.0.1",
    "JSTUDY_API_PORT": "8766",
}
```

测试必须同时确认无变量时仍解析为：

```text
jstudy-backend:pilot
jstudy-api
jstudy-worker
jstudy-postgres
0.0.0.0:8765
```

- [ ] **Step 2: Run focused test and confirm RED**

```powershell
python -m unittest tests.test_deployment_files -v
```

Expected: 新 staging 参数断言失败。

- [ ] **Step 3: Add minimal Compose interpolation**

使用以下合同，不改变服务名和现有默认行为：

```yaml
image: ${JSTUDY_IMAGE_NAME:-jstudy-backend:pilot}
container_name: ${JSTUDY_API_CONTAINER_NAME:-jstudy-api}
container_name: ${JSTUDY_WORKER_CONTAINER_NAME:-jstudy-worker}
container_name: ${JSTUDY_POSTGRES_CONTAINER_NAME:-jstudy-postgres}
ports:
  - "${JSTUDY_API_BIND_ADDRESS:-0.0.0.0}:${JSTUDY_API_PORT:-8765}:8765"
```

- [ ] **Step 4: Run focused test and confirm GREEN**

```powershell
python -m unittest tests.test_deployment_files -v
docker compose -f deploy/docker-compose/api.compose.yml config --services
```

Expected: tests pass; services remain `postgres`, `jstudy-api`, `jstudy-worker`.

- [ ] **Step 5: Commit**

```powershell
git add deploy/docker-compose/api.compose.yml tests/test_deployment_files.py
git commit -m "部署：支持隔离的 staging 容器拓扑"
```

### Task 2: Operator Documentation

**Files:**
- Modify: `.env.example`
- Modify: `deploy/docker-compose/README.md`
- Modify: `docs/deployment/server-runbook.md`
- Create: `multi-agent/jstudy-product-build/reports/0010-tencent-staging-deployment-report.md`

- [ ] **Step 1: Document non-secret staging variables**

`.env.example` 只添加空值或非敏感默认值：

```dotenv
JSTUDY_IMAGE_NAME=jstudy-backend:pilot
JSTUDY_API_CONTAINER_NAME=jstudy-api
JSTUDY_WORKER_CONTAINER_NAME=jstudy-worker
JSTUDY_POSTGRES_CONTAINER_NAME=jstudy-postgres
JSTUDY_API_BIND_ADDRESS=0.0.0.0
JSTUDY_API_PORT=8765
```

- [ ] **Step 2: Document isolated staging commands**

Runbook 必须明确：

```powershell
docker compose -p jstudy-staging --env-file .env -f deploy/docker-compose/api.compose.yml up -d --build
docker compose -p jstudy-staging --env-file .env -f deploy/docker-compose/api.compose.yml ps
docker compose -p jstudy-staging --env-file .env -f deploy/docker-compose/api.compose.yml logs --tail 200 jstudy-api jstudy-worker
```

并明确禁止对旧部署执行 `down -v`，禁止复用旧数据库目录，禁止把 `.env`、Token、上传文件和生成产物提交 Git。

- [ ] **Step 3: Define staging acceptance and rollback**

验收至少包括：

```text
/api/health
/api/readiness
/api/readiness?probe_provider=true
注册/登录 Cookie
一个合成 PDF Job 从 queued 离开并进入 completed 或有明确 failed 原因
Worker、Manifest、Learning Map、Coverage、Package v2 读取
HTTPS 与 Secure Cookie
```

回滚只停止 `jstudy-staging` Compose 项目并恢复 staging Nginx 配置，不操作旧 `jstudy` 容器和数据。

- [ ] **Step 4: Run full deployment checks**

```powershell
python -m unittest tests.test_deployment_files -v
python -m compileall -q apps packages
python -m unittest discover -s tests -v
docker compose -f deploy/docker-compose/api.compose.yml config --services
git diff --check
```

- [ ] **Step 5: Commit**

```powershell
git add .env.example deploy/docker-compose/README.md docs/deployment/server-runbook.md multi-agent/jstudy-product-build/reports/0010-tencent-staging-deployment-report.md
git commit -m "文档：补充腾讯云 staging 部署与回滚流程"
```

## Supervisor-Only Remote Execution

Code Agent 不执行以下操作：

1. 读取或传输本地 MinerU、Cloudflare、SiliconFlow 凭据。
2. SSH 修改腾讯云、Nginx、DNS 或证书。
3. 覆盖 `/opt/jstudy/app`、旧 `.env`、旧 PostgreSQL 或 `jstudy.online`。
4. 执行真实 Provider 请求。

Supervisor 审核 Task 0010 后才执行：

```text
GitHub checkpoint -> /opt/jstudy-staging/app
独立 .env 与随机密钥 -> jstudy-staging Compose
127.0.0.1:8766 -> staging.jstudy.online
真实 PostgreSQL/API/Worker/MinerU synthetic smoke
部署报告与回滚点
```
