# 前端依赖风险登记

更新时间：2026-07-31

## 当前结论

在 `apps/web` 中执行：

```powershell
npm audit --omit=dev
```

结果为 `found 0 vulnerabilities`。生产安装路径当前没有 npm 已知漏洞。

完整执行 `npm audit` 仍报告 9 个 high。这里的“9 个”是 npm 按受影响包统计的条目数，不等同于 9 个独立 CVE；它们全部来自 ESLint 开发工具链，不进入 `npm ci --omit=dev` 的生产安装结果。

## 已修复的生产依赖

| 依赖链 | 处理 |
| --- | --- |
| `next` | 从 `16.2.10` 升级到 `16.2.12` |
| `next > postcss` | 使用 npm override 固定到首个不受当前公告影响的 `8.5.18` |
| `next > sharp` | 使用 npm override 固定到 Next 同代 preview 已采用的 `0.35.3` |

稳定版 `next@16.2.12` 仍声明了受影响的 `postcss@8.4.31` 和 `sharp@^0.34.5`，因此仅升级 Next 不能使生产审计归零。覆盖版本保持在相同主要 API 代际，并由 lint、类型检查、单元测试、生产构建和浏览器测试共同验证。

## 暂时接受的开发依赖风险

| npm 条目 | 直接依赖 | 风险链 |
| --- | --- | --- |
| `@eslint/config-array` | 否 | `minimatch` |
| `@eslint/eslintrc` | 否 | `minimatch` |
| `brace-expansion` | 否 | 无界展开可能造成进程内存耗尽 |
| `eslint` | 是 | `@eslint/config-array`、`@eslint/eslintrc`、`minimatch` |
| `eslint-config-next` | 是 | `eslint-plugin-import`、`eslint-plugin-jsx-a11y`、`eslint-plugin-react` |
| `eslint-plugin-import` | 否 | `minimatch` |
| `eslint-plugin-jsx-a11y` | 否 | `minimatch` |
| `eslint-plugin-react` | 否 | `minimatch` |
| `minimatch` | 否 | `brace-expansion` |

当前暴露边界：

- 这些包只用于本地或 CI 的 lint，不属于生产运行时依赖。
- 风险仍可能由恶意仓库内容或 lint 配置触发，因此开发和 CI 环境只处理可信代码。
- npm 当前建议升级 `eslint@10.8.0`，或对 `eslint-config-next` 做不合理的主版本降级；两者都超出本次生产依赖修复范围。

复查触发条件：

- ESLint 10 与当前 Next 配置完成兼容性验证；
- `eslint-config-next` 发布不需要降级的安全修复；
- 上线前的下一次依赖安全审计；
- 开发或 CI 环境开始处理外部不可信源码。

## 复核命令

```powershell
npm audit --omit=dev
npm audit
npm ls next postcss sharp
```
