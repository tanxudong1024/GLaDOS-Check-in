# GLaDOS 自动签到

通过 GitHub Actions 每天定时调用 GLaDOS 的签到接口。

## 配置

`Settings → Secrets and variables → Actions`：

| 类型 | 名称 | 说明 |
| --- | --- | --- |
| Secret | `GLADOS_COOKIE` | 浏览器完整 Cookie，多个账号用 `&&` 分隔 |
| Secret / Variable | `GLADOS_UA` | 取 Cookie 的那个浏览器的 User-Agent，必须与 Cookie 来自同一浏览器 |
| Variable | `GLADOS_ORIGIN` | 可选，站点根地址，默认 `https://glados.rocks` |

### 1. 获取 Cookie

在浏览器登录站点（例如 <https://glados.rocks>）后，打开 F12 → Network → 任意请求 → Request Headers → `Cookie`，
复制**完整四段**，2026-09 起必须包含 `gld:sess` 与 `gld:sess.sig`：

```
koa:sess=...; koa:sess.sig=...; gld:sess=...; gld:sess.sig=...
```

> 只复制旧的 `koa:` 两段会返回 `code: -2, message: 没有权限`。
> 也支持 Cookie-Editor 导出的 JSON 数组，或带 `Cookie: ` 前缀的整行。

### 2. 获取 User-Agent

在**同一个浏览器**的控制台执行：

```js
navigator.userAgent
```

把输出原样填入 `GLADOS_UA`。GLaDOS 会校验签到请求的 UA 是否与登录浏览器一致，
不一致时返回 `code: 4 / device-mismatch`（浏览器升级后 UA 变化也需要同步更新）。

## 排障

| 日志 | 原因 | 处理 |
| --- | --- | --- |
| `没有权限` / `code: -2` | Cookie 失效或缺少 `gld:` 段 | 重新登录取完整 Cookie |
| `device-mismatch` / `code: 4` | UA 与登录浏览器不一致 | 更新 `GLADOS_UA` |
| `Automated check-in detected` | 被判定为自动化请求 | 更新 `GLADOS_UA` 为重登录取 Cookie 的浏览器 UA |
| `今日已签到（code: 1）` | 当天已签过 | 正常，不算失败 |

## 说明

- 定时任务为 `5 16 * * *`（UTC），即每天北京时间 00:05。
- GitHub 会在仓库 60 天无提交后自动停用定时工作流，Actions 页面点击 `Enable workflow` 即可恢复。
