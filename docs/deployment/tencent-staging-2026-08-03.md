# 腾讯云 Staging 部署记录（2026-08-03）

## 结论

J-Study 后端已部署到隔离的腾讯云 staging 环境：

- URL: `https://staging.jstudy.online`
- Git SHA: `1c0404c6e62780d53785283bde2501a910b693b7`
- Compose project: `jstudy-staging`
- Remote checkout: `/opt/jstudy-staging/app`
- API upstream: `127.0.0.1:8766`
- Public topology: Nginx + HTTPS -> FastAPI -> PostgreSQL + Worker

现有 `jstudy.online`、`/opt/jstudy/app`、`jstudy-api`、`jstudy-postgres`
及其数据未修改。staging 使用独立镜像、容器名、数据库目录、Job 目录、
settings 目录和 Session Cookie 名。

## Release Manifest

| Item | Value |
|---|---|
| Git SHA | `1c0404c6e62780d53785283bde2501a910b693b7` |
| Backend image | `jstudy-backend:staging-1c0404c` |
| Image ID | `sha256:c55583ec9832d896b4cb756355c338eb7edacb1cd1834b04b7dbe242a61e1913` |
| `.env` SHA-256 | `7126aeda9bed576b9fe57ba3f72390ed44b11c9c95851df56d32314f377ddd01` |
| Resolved Compose SHA-256 | `c6d1cc66e7831f50b1a76d6c935b5d14ee997a508cece189164577d4705495f8` |
| Nginx config SHA-256 | `f0b0dd09964351f647fa990208ca3cca02da4be4b629418fb6a36b8b70ea74ea` |
| TLS certificate expiry | `2026-11-01 11:37:36 UTC` |
| Database schema mechanism | `SQLModel.metadata.create_all()`; no Alembic migration yet |

哈希用于识别部署基线，不公开 `.env` 内容。服务器 `.env` 权限为 `0600`。
MinerU Token 的临时传输文件在写入 `.env` 后已删除。

## Runtime Status

部署完成后的容器状态：

| Service | Container | State |
|---|---|---|
| PostgreSQL | `jstudy-staging-postgres` | running / healthy |
| FastAPI | `jstudy-staging-api` | running / healthy |
| Worker | `jstudy-staging-worker` | running |

API 仅绑定 `127.0.0.1:8766`，不直接暴露公网端口。Nginx 是唯一公网入口。
服务器根分区部署后为 `30G / 59G`，使用率 `52%`。

## Verification

### Configuration

- `/api/health`: `200`, `status=ok`
- `/api/readiness`: `200`, `status=ready`
- `/api/readiness?probe_provider=true`: `200`, provider connectivity `ok`
- MinerU configured: `true`
- invite requirement: `false`
- session cookie: Secure
- HTTPS: 本机与服务器均通过

### Synthetic End-to-End Smoke

使用一页纯合成微生物学 PDF，不包含真实用户资料：

1. 注册临时测试账号；
2. 验证 HTTP-only session flow 和 Secure Cookie；
3. 提交 `single_courseware` Job；
4. Worker 真实调用 MinerU 与 SiliconFlow；
5. Job 从运行态进入 `completed`；
6. 读取所有核心公开工件。

Smoke Job:

```text
2fd166cb0b6248ebafaba52e68530dc4
```

Artifact results:

| Endpoint | Result |
|---|---|
| Material Package | `200`, `material-package.v2` |
| Manifest | `200`, `courseware-manifest.v1` |
| Learning Map | `200`, `learning-map.v1` |
| Coverage | `200`, `coverage-ledger.v1` |
| Evidence | `200` |
| Markdown export | `200` |

API、Worker 和 PostgreSQL 最近 300 行日志中未发现 traceback、exception、
error、fatal 或 panic 标记。

## DNS And TLS

- Cloudflare record: `staging.jstudy.online -> 43.157.84.138`
- Record mode: DNS only
- Certificate: Let's Encrypt
- Renewal: existing Certbot system task
- HTTP: redirected to HTTPS

本次未启用 Cloudflare proxy，便于直接验证源站证书和 Nginx 行为。正式上线前
可以单独评估是否启用 proxy，不应在未验证上传限制和长请求行为时直接切换。

## Current Limitations

1. 这是后端 production-like staging，不代表正式前端已完成。
2. 当前数据库仍使用 `create_all()`；在保存正式持久数据前必须引入 Alembic。
3. staging 复用了现有 SiliconFlow 模型配置，但使用独立随机数据库密码、
   Session Secret 和管理员 Token。
4. Cloudflare 当前为 DNS only，尚未验证 proxy 模式下的大文件上传和长任务。
5. 尚未执行 Course Outline 和 Multi Courseware 的 live 多 PDF smoke。
6. 尚未配置外部对象存储、远端数据库备份和自动磁盘告警。

## Operations

Status:

```bash
cd /opt/jstudy-staging/app
docker compose -p jstudy-staging --env-file .env \
  -f deploy/docker-compose/api.compose.yml ps
```

Logs:

```bash
cd /opt/jstudy-staging/app
docker compose -p jstudy-staging --env-file .env \
  -f deploy/docker-compose/api.compose.yml \
  logs --tail 200 jstudy-api jstudy-worker
```

Stop staging without deleting data:

```bash
cd /opt/jstudy-staging/app
docker compose -p jstudy-staging --env-file .env \
  -f deploy/docker-compose/api.compose.yml down
```

Do not use `down -v`. Do not operate on the old `jstudy` Compose project,
old containers, `/opt/jstudy/app`, or the old database during staging rollback.

## Rollback Point

Rollback is isolated to staging:

1. stop the `jstudy-staging` Compose project without `-v`;
2. disable `/etc/nginx/sites-enabled/staging.jstudy.online`;
3. reload Nginx after `nginx -t`;
4. leave `jstudy.online` and the old containers unchanged;
5. retain `/opt/jstudy-staging/app/.env` and `data/` until the rollback decision
   is confirmed.
