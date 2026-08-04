# J-Study 认证闭环实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在正式 Next.js 前端中完成“注册 → 登录 → 恢复会话 → 模式选择 → 退出”的真实 FastAPI 认证闭环。

**Architecture:** 浏览器始终请求同源 `/api/auth/*`，由 Next.js rewrite 转发到 FastAPI；FastAPI 设置 HTTP-only Cookie。TanStack Query 以 `["auth", "me"]` 作为会话单一事实源，注册和登录成功后写入该缓存，退出后清空。`/modes/**` 由客户端守卫保护，根路由根据恢复出的会话跳转。

**Tech Stack:** Next.js App Router、React、TypeScript、TanStack Query、Vitest、Testing Library、Playwright、FastAPI。

---

## 验收卡

### 用户目标

新用户能够注册；已有用户能够登录；刷新页面后 Cookie 会话仍然有效；未登录用户不能进入模式页；用户可以退出并回到登录页。

### 路由

```text
/          根据会话跳转到 /login 或 /modes
/register  注册
/login     登录
/modes     受保护的模式选择
```

### 后端接口

```text
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

请求与响应：

```ts
type AuthUser = {
  id: string;
  email: string;
  email_verified: boolean;
};

type RegisterInput = {
  email: string;
  password: string;
  invite_code: string;
};

type LoginInput = {
  email: string;
  password: string;
};
```

### 状态

- loading：恢复会话或提交表单。
- empty：未登录，守卫跳转到 `/login`。
- error：错误显示在表单或会话区域，不只使用 Toast。
- success：注册或登录后进入 `/modes`；退出后进入 `/login`。

### 不允许出现

- 忘记密码。
- 社交登录。
- 邮箱验证流程。
- 用户角色和资料设置。
- localStorage 令牌。
- 后端不存在的历史、取消或重试功能。

### 响应式

- `390x844`：认证表单单列；模式列表单列。
- `768x1024`：认证表单单列；模式列表保持可读。
- `1440x900`：认证表单居中；模式页使用宽屏纵向对比行。

### 完成标准

- Vitest 覆盖 API、表单、守卫和会话状态。
- Playwright 连接真实 FastAPI，完成注册、退出、登录、刷新恢复、再次退出和守卫跳转。
- `lint`、`typecheck`、`test`、`build`、Playwright 均通过。
- 三个视口无横向溢出、无意外控制台错误。

## 文件结构

```text
apps/web/src/features/auth/api.ts
  认证请求、用户类型和面向用户的错误映射。

apps/web/src/features/auth/api.test.ts
  认证 API 路径、请求体、401 会话恢复和错误映射测试。

apps/web/src/features/auth/use-auth.ts
  TanStack Query 会话查询、注册、登录和退出动作。

apps/web/src/features/auth/auth-forms.tsx
  登录和注册表单；只管理字段与提交状态。

apps/web/src/features/auth/auth-forms.test.tsx
  表单输入、校验、提交和错误显示测试。

apps/web/src/features/auth/auth-guard.tsx
  受保护页面的 loading、error、anonymous 和 authenticated 状态。

apps/web/src/features/auth/auth-guard.test.tsx
  守卫四种状态与跳转测试。

apps/web/src/features/auth/logout-button.tsx
  退出动作和跳转。

apps/web/src/app/login/page.tsx
apps/web/src/app/register/page.tsx
  认证页入口。

apps/web/src/app/modes/layout.tsx
  保护 `/modes/**`。

apps/web/src/app/modes/page.tsx
  已批准的模式选择简版布局。

apps/web/src/app/page.tsx
  根路由会话跳转。

apps/web/src/components/shell/app-shell.tsx
  认证页独立壳层、学生顶栏和账号信息。

apps/web/src/app/layout.tsx
  中文页面语言。

apps/web/src/styles/globals.css
  认证页、模式页和三个视口的结构样式。

apps/web/e2e/auth-flow.spec.ts
  真实后端认证闭环。

apps/web/playwright.auth.config.ts
  同时启动 FastAPI 与 Next.js 的真实认证测试配置。

apps/web/package.json
  新增真实认证 E2E 命令。

apps/web/README.md
  更新本地启动和验证说明。
```

### Task 1: 认证 API 与会话查询

**Files:**
- Create: `apps/web/src/features/auth/api.test.ts`
- Create: `apps/web/src/features/auth/api.ts`
- Create: `apps/web/src/features/auth/use-auth.ts`

- [ ] **Step 1: 写认证 API 失败测试**

测试必须断言：

```ts
await register({
  email: "student@example.com",
  password: "password123",
  invite_code: "MED-PILOT",
});

expect(fetch).toHaveBeenCalledWith(
  "/api/auth/register",
  expect.objectContaining({
    method: "POST",
    credentials: "include",
    body: JSON.stringify({
      email: "student@example.com",
      password: "password123",
      invite_code: "MED-PILOT",
    }),
  }),
);
```

并覆盖：

```ts
expect(await getCurrentUser()).toBeNull(); // /me 返回 401
expect(authErrorMessage(new ApiError(409, ""))).toBe("该邮箱已注册。");
expect(authErrorMessage(new ApiError(401, ""))).toBe("邮箱或密码错误。");
```

- [ ] **Step 2: 运行测试并确认正确失败**

Run:

```powershell
npm test -- src/features/auth/api.test.ts
```

Expected: FAIL，因为 `@/features/auth/api` 尚不存在。

- [ ] **Step 3: 实现最小认证 API**

`api.ts` 导出：

```ts
export type AuthUser = {
  id: string;
  email: string;
  email_verified: boolean;
};

export type RegisterInput = {
  email: string;
  password: string;
  invite_code: string;
};

export type LoginInput = {
  email: string;
  password: string;
};

export function register(input: RegisterInput): Promise<AuthUser>;
export function login(input: LoginInput): Promise<AuthUser>;
export function logout(): Promise<{ status: string }>;
export function getCurrentUser(): Promise<AuthUser | null>;
export function authErrorMessage(error: unknown, action: "login" | "register" | "session"): string;
```

所有 POST 请求使用 `content-type: application/json`，所有请求继续通过 `apiRequest` 使用 `credentials: "include"`。`getCurrentUser` 只把 `401` 转成 `null`，其他错误继续抛出。

`use-auth.ts` 导出：

```ts
export const currentUserQueryKey = ["auth", "me"] as const;
export function useCurrentUser();
export function useLogin();
export function useRegister();
export function useLogout();
```

注册和登录成功后调用 `queryClient.setQueryData(currentUserQueryKey, user)`；退出成功后写入 `null`。

- [ ] **Step 4: 运行测试并确认通过**

Run:

```powershell
npm test -- src/features/auth/api.test.ts
```

Expected: PASS。

### Task 2: 登录与注册表单

**Files:**
- Create: `apps/web/src/features/auth/auth-forms.test.tsx`
- Create: `apps/web/src/features/auth/auth-forms.tsx`
- Modify: `apps/web/src/app/login/page.tsx`
- Modify: `apps/web/src/app/register/page.tsx`

- [ ] **Step 1: 写表单失败测试**

登录表单测试：

```ts
await user.type(screen.getByLabelText("邮箱"), "student@example.com");
await user.type(screen.getByLabelText("密码"), "password123");
await user.click(screen.getByRole("button", { name: "登录" }));

expect(onSubmit).toHaveBeenCalledWith({
  email: "student@example.com",
  password: "password123",
});
```

注册表单测试：

```ts
await user.type(screen.getByLabelText("确认密码"), "different-password");
await user.click(screen.getByRole("button", { name: "创建账号" }));

expect(screen.getByRole("alert")).toHaveTextContent("两次输入的密码不一致。");
expect(onSubmit).not.toHaveBeenCalled();
```

另测 `pending=true` 时按钮禁用，`error` 在表单内以 `role="alert"` 显示。

- [ ] **Step 2: 运行测试并确认正确失败**

Run:

```powershell
npm test -- src/features/auth/auth-forms.test.tsx
```

Expected: FAIL，因为表单组件尚不存在。

- [ ] **Step 3: 实现表单与页面容器**

`auth-forms.tsx` 导出：

```ts
export function LoginForm(props: {
  pending: boolean;
  error: string | null;
  onSubmit: (input: LoginInput) => Promise<void> | void;
});

export function RegisterForm(props: {
  pending: boolean;
  error: string | null;
  onSubmit: (input: RegisterInput) => Promise<void> | void;
});
```

字段：

- 登录：邮箱、密码。
- 注册：邮箱、密码、确认密码、邀请码。
- 密码最少 8 位。
- 邀请码字段可填写但不使用 HTML `required`，因为后端允许 `JSTUDY_INVITE_REQUIRED=false`。

页面组件使用对应 mutation；成功后 `router.replace("/modes")`。认证页不显示学生工作台顶栏。

- [ ] **Step 4: 运行表单测试**

Run:

```powershell
npm test -- src/features/auth/auth-forms.test.tsx
```

Expected: PASS。

### Task 3: 会话守卫、根路由与退出

**Files:**
- Create: `apps/web/src/features/auth/auth-guard.test.tsx`
- Create: `apps/web/src/features/auth/auth-guard.tsx`
- Create: `apps/web/src/features/auth/logout-button.tsx`
- Create: `apps/web/src/app/modes/layout.tsx`
- Modify: `apps/web/src/app/page.tsx`
- Modify: `apps/web/src/components/shell/app-shell.tsx`
- Modify: `apps/web/src/components/shell/app-shell.test.tsx`
- Modify: `apps/web/src/app/layout.tsx`

- [ ] **Step 1: 写守卫失败测试**

通过 mock `useCurrentUser` 与 `next/navigation` 覆盖：

```ts
loading     -> 显示“正在恢复会话”
error       -> 显示“无法恢复会话”与重试按钮
data=null   -> router.replace("/login")，不渲染受保护内容
data=user   -> 渲染受保护内容
```

Shell 测试覆盖：

```ts
/login     -> 不显示学生导航
/modes     -> 显示 J-Study、当前邮箱与“退出”
```

- [ ] **Step 2: 运行测试并确认正确失败**

Run:

```powershell
npm test -- src/features/auth/auth-guard.test.tsx src/components/shell/app-shell.test.tsx
```

Expected: FAIL，因为守卫和新 Shell 行为尚不存在。

- [ ] **Step 3: 实现守卫和会话壳层**

`AuthGuard`：

```tsx
if (query.isPending) return <SessionState title="正在恢复会话" />;
if (query.isError) return <SessionState title="无法恢复会话" action={query.refetch} />;
if (!query.data) {
  router.replace("/login");
  return <SessionState title="正在前往登录页" />;
}
return children;
```

跳转放在 `useEffect` 中，不在 render 阶段调用 router。

`/modes/layout.tsx` 使用 `<AuthGuard>{children}</AuthGuard>`。根页面恢复会话后，已登录跳转 `/modes`，未登录跳转 `/login`。

`LogoutButton` 调用 `useLogout`，成功后 `router.replace("/login")`；失败时在按钮旁显示可见错误。

Root layout 将 `<html lang="en">` 改为 `<html lang="zh-CN">`。

- [ ] **Step 4: 运行守卫与 Shell 测试**

Run:

```powershell
npm test -- src/features/auth/auth-guard.test.tsx src/components/shell/app-shell.test.tsx
```

Expected: PASS。

### Task 4: 模式选择页与响应式结构

**Files:**
- Modify: `apps/web/src/app/modes/page.tsx`
- Modify: `apps/web/src/styles/globals.css`

- [ ] **Step 1: 写模式页结构失败测试**

在 Shell 测试文件或新页面测试中断言：

```ts
expect(screen.getByRole("heading", { name: "选择本次学习任务" })).toBeVisible();
expect(screen.getByText("课程大纲")).toBeVisible();
expect(screen.getByText("单课件")).toBeVisible();
expect(screen.getByText("批量课件")).toBeVisible();
expect(screen.getByRole("button", { name: "暂未开放" })).toBeDisabled();
```

- [ ] **Step 2: 运行测试并确认正确失败**

Run:

```powershell
npm test -- src/components/shell/app-shell.test.tsx
```

Expected: FAIL，因为当前模式页仍是英文占位。

- [ ] **Step 3: 实现模式页和结构样式**

使用批准的纵向对比行：

```text
课程大纲  主要模式  下一阶段接入
单课件    可用模式  下一阶段接入
批量课件  暂未开放  禁用
```

本切片不把课程大纲和单课件按钮做成可工作的假入口。页面样式只确定布局、间距、边界和三个视口适配，不冻结最终视觉令牌。

- [ ] **Step 4: 运行组件测试**

Run:

```powershell
npm test
```

Expected: 所有 Vitest 测试 PASS。

### Task 5: 真实 FastAPI 浏览器闭环

**Files:**
- Create: `apps/web/playwright.auth.config.ts`
- Create: `apps/web/e2e/auth-flow.spec.ts`
- Modify: `apps/web/e2e/foundation.spec.ts`
- Modify: `apps/web/package.json`

- [ ] **Step 1: 写真实认证 E2E**

测试使用唯一邮箱并执行：

```text
打开 /register
填写邮箱、密码、确认密码
提交后到 /modes
退出到 /login
使用相同账号登录
到 /modes
刷新页面
仍在 /modes 且显示邮箱
退出
直接打开 /modes
被守卫送回 /login
```

每个测试记录 console error 与 pageerror，并断言 HTML 没有横向溢出。

- [ ] **Step 2: 配置真实后端并确认 E2E 在实现完成前失败**

`playwright.auth.config.ts` 同时启动：

```text
python -m uvicorn apps.api.jstudy_api.app:app --app-dir ../.. --host 127.0.0.1 --port 8000
npm run dev -- --hostname 127.0.0.1
```

后端测试环境：

```ts
const databasePath = path
  .resolve(process.cwd(), "test-results", "auth-flow.db")
  .replaceAll("\\", "/");

const backendEnvironment = {
  JSTUDY_INVITE_REQUIRED: "false",
  JSTUDY_COOKIE_SECURE: "false",
  JSTUDY_DATABASE_URL: `sqlite:///${databasePath}`,
};
```

Run:

```powershell
npm run test:e2e:auth -- --project=desktop
```

Expected: 在认证 UI 完成前 FAIL；完成后进入 GREEN。

- [ ] **Step 3: 更新基础 E2E**

基础路由测试只直接检查公开路由；受保护 `/modes` 的行为由认证 E2E 负责。保留：

- 三个视口。
- console error。
- pageerror。
- 横向溢出。
- `trace: "retain-on-failure"`。

- [ ] **Step 4: 运行真实认证闭环**

Run:

```powershell
npm run test:e2e:auth
```

Expected: mobile、tablet、desktop 全部 PASS。

### Task 6: 文档、全量验证和本地交付

**Files:**
- Modify: `apps/web/README.md`

- [ ] **Step 1: 更新中文运行说明**

README 记录：

```powershell
# Terminal 1
python -m uvicorn apps.api.jstudy_api.app:app --host 127.0.0.1 --port 8000

# Terminal 2
cd apps/web
npm run dev -- --hostname 127.0.0.1
```

并说明：

- `JSTUDY_API_ORIGIN` 默认指向 `http://127.0.0.1:8000`。
- 注册默认需要后端已创建的邀请码。
- 私人本地测试可临时设置 `JSTUDY_INVITE_REQUIRED=false`。

- [ ] **Step 2: 运行完整前端验证**

Run:

```powershell
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
npm run test:e2e:auth
```

Expected: 全部退出码为 0。

- [ ] **Step 3: 启动真实本地服务并人工检查**

启动 FastAPI 与 Next.js，创建一个新的本地测试账号，在浏览器检查：

- 注册 Cookie。
- 登录错误。
- 刷新恢复。
- `/modes` 守卫。
- 退出。
- `390x844`、`768x1024`、`1440x900`。

- [ ] **Step 4: 检查改动边界**

Run:

```powershell
git diff --check
git status --short
```

Expected: 没有空白错误；只暂存本计划和 `apps/web/**` 的认证闭环文件，不包含用户已有的无关改动。
