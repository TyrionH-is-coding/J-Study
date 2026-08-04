# J-Study Web Foundation

`apps/web` 是 J-Study 的基础前端框架。当前只包含技术底座、公共路由壳、统一 API 请求边界和自动化验证；认证、上传、任务轮询、资料阅读和正式视觉设计尚未接入。

## 本地运行

```powershell
npm ci
npm run dev
```

打开 `http://127.0.0.1:3000`。

## 验证

```powershell
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
```

## 边界

- 浏览器 API 请求统一使用相对 `/api/*` 路径和 `credentials: "include"`。
- `JSTUDY_API_ORIGIN` 默认是 `http://127.0.0.1:8000`。
- 当前页面是明确的功能空状态，不代表业务流程已经完成。
- 正式颜色、字体、圆角、卡片和页面密度规则将在独立视觉任务中确定。
