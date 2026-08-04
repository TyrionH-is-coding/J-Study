# Task 0010 腾讯云隔离 staging 部署脚手架报告

## 基线与范围

- 分支：`feature/backend-frontend-mvp`
- 起始 SHA：`b89fb75c2e59adc4be40722a07cb34f5edc8aeb7`
- Compose 合同提交：
  `ec4336e7108fc1a96c7633c260431d5e4ea86a44`
- 最终 SHA：由包含本报告的中文提交生成，以 Code Agent 回报为准。
- 任务只修改任务卡允许的 6 个文件。
- 未读取本地凭据，未 SSH，未访问腾讯云，未操作 Cloudflare、Nginx、
  DNS、证书、服务器或旧 `/opt/jstudy/app` 部署。

## 实施结果

Compose 保留原有三服务名、内部端口、相对数据挂载、数据库 hostname、
healthcheck、Worker command 和运行时配置优先级，同时增加以下插值合同：

| 变量 | 默认值 |
|---|---|
| `JSTUDY_IMAGE_NAME` | `jstudy-backend:pilot` |
| `JSTUDY_API_CONTAINER_NAME` | `jstudy-api` |
| `JSTUDY_WORKER_CONTAINER_NAME` | `jstudy-worker` |
| `JSTUDY_POSTGRES_CONTAINER_NAME` | `jstudy-postgres` |
| `JSTUDY_API_BIND_ADDRESS` | `0.0.0.0` |
| `JSTUDY_API_PORT` | `8765` |

staging 示例解析为：

```text
image=jstudy-backend:staging-test
api container=jstudy-staging-api
worker container=jstudy-staging-worker
postgres container=jstudy-staging-postgres
published API=127.0.0.1:8766
services=postgres,jstudy-api,jstudy-worker
```

运维文档补充了独立 checkout、独立 `.env`、独立数据目录和
`jstudy-staging` Compose project 的启动、状态、日志、验收、备份与回滚流程。
文档明确禁止提交 `.env`、Token、上传文件和生成产物，禁止复用旧数据库目录，
禁止执行 `down -v`，也禁止 staging 命令操作旧 `jstudy` 容器与数据。

## TDD 证据

### Compose 合同

RED：

```powershell
python -m unittest tests.test_deployment_files -v
```

新增测试首次出现 3 个预期失败：

- staging image 仍解析为 `jstudy-backend:pilot`；
- 默认端口缺少显式 `host_ip=0.0.0.0`；
- 静态合同未找到镜像插值表达式。

GREEN：增加最小 Compose 插值后，部署测试 `10/10` 通过，服务列表保持：

```text
postgres
jstudy-api
jstudy-worker
```

### 运维文档合同

RED：

```powershell
python -m unittest tests.test_deployment_files.DeploymentFilesTest.test_staging_environment_and_runbooks_cover_safe_operations -v
```

首次失败原因为 `.env.example` 缺少
`JSTUDY_IMAGE_NAME=jstudy-backend:pilot`。

GREEN：补充变量、staging 命令与安全边界后，目标测试 `1/1`、部署测试
`11/11` 通过。

## 完整验证

```text
python -m compileall -q apps packages
PASS

python -m unittest discover -s tests -v
385/385 PASS

docker compose -f deploy/docker-compose/api.compose.yml config --services
postgres
jstudy-api
jstudy-worker

git diff --check
PASS
```

第一次全量测试与一个已超时的前序测试进程发生重叠，
`test_total_upload_size_is_limited_and_cleans_up` 出现一次非稳定失败。
该测试单独连续运行 `5/5` 通过；确认无残留 unittest 进程后，完整套件
`385/385` 通过。未因此修改任何 `apps/**`、`packages/**` 或 JobService 代码。

## 精确文件

1. `.env.example`
2. `deploy/docker-compose/api.compose.yml`
3. `deploy/docker-compose/README.md`
4. `docs/deployment/server-runbook.md`
5. `tests/test_deployment_files.py`
6. `multi-agent/jstudy-product-build/reports/0010-tencent-staging-deployment-report.md`

## 残余风险

- 未执行真实腾讯云、Nginx、DNS、TLS、PostgreSQL 容器或 Provider smoke。
- staging 反向代理、证书、真实凭据和随机密钥仍须由 Supervisor 在审核后配置。
- 当前相对 `data/` 挂载依赖 staging 使用独立 checkout；若错误地在旧 checkout
  启动，容器名和端口虽隔离，宿主数据目录仍不会自动隔离。
- 本任务没有引入 Alembic；真实持久化部署仍受现有 disposable DB 边界约束。

## 请求验收

请求 Supervisor verdict：`PASS`。
