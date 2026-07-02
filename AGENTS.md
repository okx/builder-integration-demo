# AGENTS.md — 给 AI 编程助手的接入说明

你正在帮用户把 **OKX Fast API** 接入到他们自己的项目（通常是交易机器人 / 量化策略）。本仓库是参考实现，请据此帮用户改写到他们的技术栈。先读 `INTEGRATION_GUIDE.md`（语言中立规范），代码参考 `backend/` 与 `frontend/`。

## 必须遵守的硬规则

1. **绝不把 `client_secret`、`secretKey`、`passphrase` 放到前端**（HTML/JS/移动端），也不写进日志、不提交到 git。它们只能在后端使用。
2. **不要凭空编造接口**。只用 `INTEGRATION_GUIDE.md`「端点速查」中列出的路径与参数。不确定时让用户核对官方开发者文档，不要猜。
3. **Fast API 只支持授权码模式**（`access_type=offline`、`scope=fast_api`），**不要**用 PKCE 实现 Fast API。
4. **创建 Key 前必须先调删除接口**（避免 50116）；删除报 `59506`（不存在）属正常，忽略并继续。
5. **passphrase 由用户提供**，不要替用户生成/硬编码口令。要求：8-32 位，含大写+小写+数字+特殊字符各至少一个。
6. **默认安全档位**：`perm=read_only`、`SIMULATED=1`（模拟盘）。只有用户明确要下单/上实盘时才改 `trade` / `SIMULATED=0`，并提示风险。
7. **API Key 要加密落库、按用户隔离**。参考实现用进程内内存仅为演示，生产不可照搬。

## 帮用户接入时的标准步骤

1. 确认前置：用户是否已从 BD 拿到 `client_id`/`client_secret`，是否开通 Fast API + IP 白名单，`redirect_uri` 是否在白名单内。
2. 前端：引入 OKX Web SDK，`init` → `generateState`（存起来）→ `authorize({scope:'fast_api', access_type:'offline', ...})`。
3. 回调页：**校验 state**，把 `code`(+`domain`) 交后端。
4. 后端：换 token → 删 Key → 建 Key → 加密存储。
5. 业务调用：用 API Key 按 OKX 标准 HMAC 签名（`OK-ACCESS-*` 头）调接口；示例为 `GET /api/v5/account/balance`。

## 容易踩的坑

- 授权页没显示"快捷 API" → `scope` 没设成 `fast_api`。
- 换 token 报 404 → 路径在 `/api/v5/users/oauth/token` 与 `/v5/users/oauth/token` 之间切换试。
- 回跳 `domain=https://eea.okx.com` → 后续 REST 必须用该域名，WS 用 `wss://wseea.okx.com`。
- 创建 Key 报 50118 → 需 Broker 提供 IP 白名单后才能 `bindApp`。
- 签名失败（401/50113 等）→ 检查 timestamp 格式（ISO8601 毫秒 UTC）、prehash 拼接顺序、模拟盘是否漏带 `x-simulated-trading: 1`。
- 前端授权用错站点 → 前端发起授权的 `requestUrl` 也要按站点（全球 / 土耳其 / EEA）切换，不是只在后端处理回跳 `domain`。前后端站点不一致会导致授权或后续调用失败。
- 业务接口 query 与签名不一致（如 50113）→ 调业务接口时 query（如 `?ccy=BTC`）必须与 HMAC 签名用的 `requestPath` **逐字一致**：不要用 HTTP 库的自动 params 拼接（顺序 / 编码可能与签名串不同），应手动拼好 path 再同时用于签名和请求，否则签名校验失败。

更多错误码见 `errors.md`。
