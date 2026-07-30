# J-Study 前端基础框架重建设计

## 状态

本设计的非视觉部分已获得用户批准。目标是删除并重建 `apps/web/**`，产出一个可运行、可构建、可测试的基础前端框架。此次重建不实现认证、上传、任务轮询、资料阅读或 PDF 引用跳转等完整业务流程。产品视觉方向暂不冻结，后续通过独立设计任务确定。

## 目标

- 保留 J-Study 已确定的正式前端技术方向。
- 用最小代码建立稳定的路由、布局、设计变量、API 边界和验证链路。
- 为后续业务功能提供清晰模块边界，不提前引入业务状态和复杂抽象。
- 让医学作为首个应用方向，但不让平台框架绑定单一学科。

## 变更边界

本次允许删除并重建：

```text
apps/web/**
```

本次不修改：

- `apps/api/**`
- `apps/worker/**`
- `packages/**`
- 后端 API 合同
- 部署配置
- `frontend/`、`game/`、`images/`、`outline_mode/` 等其他实验目录
- 与前端重建无关的未提交文件

## 技术栈

- Next.js App Router
- React
- TypeScript
- Tailwind CSS
- shadcn/ui 基础配置与少量必要组件
- TanStack Query，仅提供统一 Provider，不预建业务查询
- Vitest 与 React Testing Library
- Playwright
- npm 与 `apps/web/package-lock.json`

版本沿用当前 `apps/web` 已锁定且可审计的依赖基线。重建不以追逐最新版本为目标。

## 路由

基础框架提供以下可直接访问的路由：

```text
/                     基础状态与导航入口
/login                登录功能空状态
/register             注册功能空状态
/modes                学习模式入口空状态
/modes/course-outline 课程大纲模式空状态
/jobs/[jobId]         任务工作区空状态
```

这些页面不提交表单、不调用业务 API，也不展示伪造数据。每个页面清楚说明框架已经就绪以及尚未接入的能力。

## 模块边界

```text
apps/web/src/app/
  路由、根布局和全局 Provider

apps/web/src/components/ui/
  无业务状态的基础 UI 组件

apps/web/src/components/shell/
  J-Study 品牌、导航、页面框架和空状态

apps/web/src/lib/api/
  相对 /api 路径的统一请求客户端与错误类型

apps/web/src/styles/
  最小可用性变量、样式重置和响应式基础

apps/web/src/test/
  Vitest 与 Testing Library 测试支持

apps/web/e2e/
  真实 Next.js URL 的基础浏览器验收
```

`components/ui` 不包含 J-Study 业务逻辑。`lib/api` 不包含 UI 状态。业务功能后续按 feature 目录独立加入，不在基础框架阶段建立空抽象。

## 暂定的可用性基线

本任务不确定产品视觉语言，不冻结颜色、字体组合、品牌质感、圆角体系、卡片风格或页面密度。

为了让技术框架能够验收，仅保留下列非审美要求：

- 使用语义化 HTML 和可见的键盘焦点。
- 支持 `prefers-reduced-motion`。
- 页面在 `390x844`、`768x1024`、`1440x900` 下不得出现应用外壳横向溢出。
- 路由、导航和空状态在三个视口下均可读取和操作。
- 品牌文案保持多学科中立，不把平台命名或导航固化为医学专用产品。

基础页面只使用中性的临时样式保证结构可读。后续视觉任务可以替换全部视觉变量和表现层，不需要改动路由、Provider、API 客户端或测试基础设施。

## 数据流

基础阶段仅建立以下基础数据路径：

1. 根布局加载全局样式和 `AppProviders`。
2. `AppProviders` 创建单一 `QueryClient`。
3. 路由页面复用公共 `AppShell` 与 `FeaturePlaceholder`。
4. 后续功能通过 `lib/api` 的相对 `/api/...` 客户端接入后端。

本阶段不调用认证、任务或文档接口，不缓存伪造响应，也不写入 `localStorage`。

## API 边界

`lib/api` 只提供最小客户端：

- 自动请求相对 `/api` 路径。
- 默认使用 `credentials: "include"`，为后续 HTTP-only cookie 认证保留正确行为。
- 统一解析成功响应。
- 非成功状态抛出包含 HTTP 状态和安全错误消息的类型化异常。
- 不记录令牌、Cookie、上传内容或响应正文。

本阶段不定义尚未消费的完整后端类型，也不复制认证、任务、来源或证据结构。

## 错误与空状态

- 路由壳使用明确的功能空状态，不使用不可操作的假表单。
- API 客户端对空响应和 JSON 响应分别处理。
- API 客户端遇到非 JSON 错误时使用通用安全消息。
- 全局样式支持键盘焦点和 `prefers-reduced-motion`。
- 动态任务路由只显示经过页面转义的 `jobId`，不把它当作可信业务数据。

## 测试与验收

### 单元测试

- Provider 可以挂载页面内容。
- 公共框架正确渲染品牌、导航和页面标题。
- 功能空状态不会渲染可提交表单。
- API 客户端使用相对 `/api` 路径和 `credentials: "include"`。
- API 客户端对成功、空响应和失败响应行为稳定。

### 构建验证

必须通过：

```powershell
npm ci
npm run lint
npm run typecheck
npm test
npm run build
```

### 浏览器验收

Playwright 启动真实 production 或 development Next.js URL，并在以下视口运行：

```text
390x844
768x1024
1440x900
```

验收内容：

- 六个路由可直接打开。
- 公共导航链接可用。
- 动态任务路由能显示当前 `jobId`。
- 主应用外壳满足 `clientWidth === scrollWidth`。
- 浏览器控制台没有意外错误。

## 不在本次范围内

- 认证与路由守卫
- 注册邀请机制
- 课程大纲和 PDF 上传
- 任务提交与轮询
- Markdown 资料阅读器
- PDF 页面预览与引用跳转
- 管理后台
- PWA、i18n、Redux、Zustand
- 通用文件查看器
- 后端或部署变更
- 正式品牌视觉、颜色、字体、圆角、卡片和页面密度规则

## 成功标准

完成后，`apps/web` 是一个干净、可理解、可扩展的 J-Study 基础框架：依赖可复现安装，所有基础路由可访问，模块边界明确，表现层可在后续独立替换，lint、类型检查、单元测试、生产构建和三个视口的浏览器验收全部通过。
