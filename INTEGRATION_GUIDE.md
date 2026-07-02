# OKX Fast API 接入指南（语言中立）

> 本文件是给 **AI 助手 / 开发者** 读的接入规范。无论你用 Python、Node、Go、Java，都按这里的流程、接口、参数实现即可；本仓库的 `backend/`（Python/Flask）只是其中一份参考实现。

## 这是什么 / 何时用 Fast API

Fast API 用于**第三方应用（Broker）为用户创建并托管一个长期有效的 OKX API Key**，之后用该 Key 代表用户持续调用 OKX 接口（如交易机器人、量化策略）。

为什么交易机器人要用它，而不是普通 OAuth：

| | OAuth 授权码 / PKCE | **Fast API** |
|---|---|---|
| 凭证 | access_token（1h）+ refresh_token（**3 天**） | **长期 API Key**（直到用户解绑/撤销） |
| 用户关闭页面后还能跑吗 | 需 3 天内活跃刷新，否则要重新授权 | ✅ 一直能跑，无需用户在场 |
| 适合 | 用户在场的即时操作 | **7×24 无人值守机器人** |

结论：**做自动交易机器人 → 用 Fast API。**

## 前置条件（接入方自己办，代码替代不了）

1. 联系 BD 申请成为 **OAuth Broker**，并**开通 Fast API 权限 + IP 白名单**（Fast API 必须先开 IP 白名单）。
2. 申请时提供：OAuth 白名单、Redirect URL、Logo、跨域域名。
3. 审核通过后邮件获得 `client_id` 与 `client_secret`。
4. 你的 `redirect_uri` 必须在 OKX 注册的白名单内，否则授权失败。

## 关键约束（务必遵守）

- **Fast API 只支持授权码模式**（`access_type=offline`），**不支持 PKCE**。
- `client_secret`、创建出的 `secretKey`/`passphrase` **只能在后端**，绝不进前端、不进日志、不进 git。
- 一个 Broker 对一个用户**只能有一个有效的 Fast API Key**（所以创建前先删）。
- access_token 仅用于"创建 Key"这一步，**有效期 1 小时、无 refresh_token**。真正长期干活的是创建出来的 API Key。

## 完整流程（6 步）

```
[前端] 1. authorize(scope=fast_api) ──跳转──> OKX 授权页
                                              用户登录授权
[前端] 2. 回跳 redirect_uri?code=...&state=...&domain=...
          校验 state；把 code(+domain) 交给后端
[后端] 3. POST 换 access_token (用 client_secret)
[后端] 4. POST 删除旧 Key（避免 50116；59506=没有，忽略）
[后端] 5. POST 创建 Fast API Key → 存后端(加密)
[后端] 6. 用 API Key 做 HMAC 签名调用业务接口（示例：查账户余额）
```

### 步骤 1：前端发起授权（OKX Web SDK）

SDK CDN（引入后存在 `window.OKEXOAuthSDK`）：
- 海外：`https://static.okx.com/cdn/assets/okfe/libs/okxOAuth/index.js`
- 国内：`https://static.coinall.ltd/cdn/assets/okfe/libs/okxOAuth/index.js`

```js
OKEXOAuthSDK.init({ requestUrl: 'https://www.okx.com' });
const state = OKEXOAuthSDK.generateState();   // 随机串，存起来防 CSRF
OKEXOAuthSDK.authorize({
  response_type: 'code',
  access_type:  'offline',          // Fast API 必须 offline
  client_id:    'YOUR_CLIENT_ID',
  redirect_uri: encodeURIComponent('https://yourapp.com/callback'),
  scope:        'fast_api',          // ★ Fast API 的关键
  state,
});
```
> 授权页若不显示"快捷 API"，多半是 `scope` 没设成 `fast_api`。

### 步骤 2：回跳与 state 校验

回跳形如：`https://yourapp.com/callback?code=...&state=...&domain=https://www.okx.com`
- **必须**校验回跳 `state == 发起时的 state`，否则丢弃。
- 若 `domain=https://eea.okx.com`，后续 REST 用该域名、WebSocket 用 `wss://wseea.okx.com`。

### 步骤 3：用授权码换 access_token（后端）

```
POST {base}/api/v5/users/oauth/token
Content-Type: application/json
{
  "grant_type": "authorization_code",
  "code": "<上一步的 code>",
  "client_id": "YOUR_CLIENT_ID",
  "client_secret": "YOUR_CLIENT_SECRET"
}
→ { "access_token": "...", "token_type": "bearer", "expires_in": 3600 }   // 无 refresh_token
```
> 路径说明：开发者文档"REST API > 获取令牌"段落写作 `/v5/users/oauth/token`，
> 而 changelog 与删/建 Key 接口均为 `/api/v5/...`。本仓库与后两者统一用 `/api/v5/...`；
> 若换 token 报 404，改用 `/v5/users/oauth/token`。

### 步骤 4：删除旧 Key（后端，幂等）

```
POST {base}/api/v5/users/oauth/delete-apikey
Authorization: Bearer <access_token>
（模拟盘需加头 x-simulated-trading: 1）
→ {"code":"0","data":[{"result":true}]}   // 或 59506=Key不存在 → 正常，继续下一步
```

### 步骤 5：创建 Fast API Key（后端）

```
POST {base}/api/v5/users/oauth/apikey
Authorization: Bearer <access_token>
（模拟盘需加头 x-simulated-trading: 1）
{
  "label": "demo",
  "passphrase": "<8-32位，含大小写+数字+特殊字符>",
  "perm": "read_only",     // 或 "trade"；无提币权限
  "bindApp": false         // true=自动绑定 Broker 预留 IP 白名单（更安全）
}
→ { "code":"0", "data":[{
      "label":"demo","apiKey":"...","secretKey":"...","passphrase":"...","perm":"read_only","bindApp":false
    }] }
```
**把 `apiKey` / `secretKey` / `passphrase` 加密存到后端**（按用户隔离）。这就是长期凭证。

### 步骤 6：用 API Key 调用业务接口（OKX 标准 HMAC 签名）

示例：`GET /api/v5/account/balance`（权限：只读，限速 10次/2s）。

签名规则：
```
timestamp   = ISO8601 毫秒 UTC，如 2020-12-08T09:08:57.715Z
prehash     = timestamp + method(大写) + requestPath(含 query) + body
OK-ACCESS-SIGN = base64( HMAC_SHA256( secretKey, prehash ) )
```
请求头：
```
OK-ACCESS-KEY:        <apiKey>
OK-ACCESS-SIGN:       <上面算出的签名>
OK-ACCESS-TIMESTAMP:  <timestamp>
OK-ACCESS-PASSPHRASE: <passphrase>
Content-Type:         application/json
x-simulated-trading:  1     # 仅模拟盘
```

**可直接粘贴的多语言签名片段（Python / Node-JS）见 [`SIGNING.md`](SIGNING.md)**，其中含 known-answer 验证向量与跨语言一致性校验方法。完整可运行实现见 `backend/okx_client.py`。

余额返回的关键字段：`data[0].totalEq`（美金总权益）、`data[0].details[].ccy/eq/availBal`（各币种）。完整字段见 OKX 账户余额接口官方文档（OKX 开发者文档，Lark Wiki）：`https://okg-block.sg.larksuite.com/wiki/XQm7wdM55in5faknWoklhva2gwb`。

## 解绑

用户解绑时，Broker 在本地删除其 API Key 即可（编辑/删除 Key 需用户自行登录 OKX 操作）。

## 端点速查

| 用途 | 方法 | 路径 | 鉴权 |
|---|---|---|---|
| 换 access_token | POST | `/api/v5/users/oauth/token` | client_secret |
| 删 Fast API Key | POST | `/api/v5/users/oauth/delete-apikey` | Bearer access_token |
| 建 Fast API Key | POST | `/api/v5/users/oauth/apikey` | Bearer access_token |
| 查账户余额(示例) | GET | `/api/v5/account/balance` | API Key HMAC 签名 |
