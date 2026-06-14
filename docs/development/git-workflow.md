# Git 工作流

## 仓库边界

本仓库根目录是 `J-Study`，用于当前 MVP 后端以及后续前端接入、部署脚本。上一级目录中的 `DeepTutor` 已经是独立 Git 仓库，不纳入本仓库。

## 分支

- `main`：可运行、可部署的稳定基线。
- `feature/<short-name>`：新功能，例如 `feature/frontend-mvp`。
- `fix/<short-name>`：缺陷修复，例如 `fix/evidence-scroll`。
- `deploy/<target>`：仅在需要服务器部署专用配置时使用，例如 `deploy/tencent-cloud`。

暂不引入 `develop` 分支；当前阶段直接从 `main` 拉短分支，合并前跑验证命令即可。

## 提交原则

- 每个提交只解决一个明确目标。
- 不提交密钥、本地 `.env`、`siliconflow api key.txt`、`web_jobs/`、日志、上传 PDF、RAG 生成产物。
- 后端代码改动提交前运行：

```powershell
python -m py_compile web_mvp.py mvp_runner.py apps/api/jstudy_api/app.py packages/core/jstudy_core/pipeline.py
python -m unittest discover -s tests -v
```

- 前端加入后，在本文件补充对应的 `npm`/`pnpm` 验证命令。

## 部署记录

服务器部署稳定后，用 tag 标记可回滚版本：

```powershell
git tag vYYYY.MM.DD-N
git push origin main --tags
```
