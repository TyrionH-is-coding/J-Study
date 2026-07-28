# J-Study Web

`apps/web` 是 J-Study 的正式 Next.js 前端。当前完成的第一条产品流程是 Course Outline Mode：登录或注册、选择服务模式、上传课程大纲和多个 PDF、轮询任务、按 section 阅读 material package、查看 source-specific PDF 页，并从引用跳转到对应 `source_id + page`。

## 本地运行

先从仓库根目录启动 FastAPI：

```powershell
python -m uvicorn apps.api.jstudy_api.app:app --host 127.0.0.1 --port 8000
```

再启动前端：

```powershell
cd apps/web
npm install
npm run dev
```

浏览器打开 `http://127.0.0.1:3000`。前端只请求相对 `/api/*`；`next.config.ts` 默认把这些请求转发到 `http://127.0.0.1:8000`。需要其他后端地址时，设置服务端环境变量：

```powershell
$env:JSTUDY_API_ORIGIN = "http://127.0.0.1:8765"
npm run dev
```

## 验证

```powershell
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
```

`test:e2e` 会启动真实 Next.js URL 和复用现有 FastAPI `create_app()` 的确定性测试服务，覆盖 `390x844`、`768x1024`、`1440x900`。测试服务只注入 runner，不增加或修改后端 route。

## 边界

- auth、job、source、evidence、package 类型统一位于 `src/lib/api`。
- source identity 一律使用 `source_id`；文件名只用于显示。
- `mode` 仍是后端 metadata，本前端不发送也不用于推断 `service_mode`。
- 当前不提供 Batch Courseware、General、Engineering、Law、PWA、i18n 或通用文件查看器。
