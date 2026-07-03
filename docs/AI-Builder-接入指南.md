# OKX AI Builder 接入指南（鉴权 + 下单）

> **读者对象**：外部 AI Builder 接入方——你有自己的交易平台、自己的用户、自己的前后端服务，希望：
> ① 替你的用户向 OKX 下单（AI 交易机器人 / 量化策略 / Copy-trading 等）；
> ② 每一笔订单都归属到你的经纪商标识（BrokerCode），从而**赚取交易手续费反佣**。
>
> 本文告诉你：**把哪些改动加进你自己的前端和后端**（鉴权部分），以及**每类交易场景的下单请求怎么发**（下单部分）。
> 本文是自包含的、**不限编程语言的**：HTTP 规格与签名规则是标准，文中的 Python / Node / Java / Flask / HTML 代码只是参考实现；任何语言/框架都能按第 0 节的用法与 4.0 的「移植五步法」落地。

---

## 目录

0. [怎么用这份指南（开发者 & AI 编程助手）](#0-怎么用这份指南开发者--ai-编程助手)
1. [总览：两条主线](#1-总览两条主线)
2. [前置申请（人工步骤，代码替代不了）](#2-前置申请人工步骤代码替代不了)
3. [第一部分：鉴权流程集成（前后端改造）](#3-第一部分鉴权流程集成前后端改造)
   - 3.1 [前端改造清单](#31-前端改造清单3-处改动)
   - 3.2 [后端改造清单](#32-后端改造清单1-个新接口--凭证存储)
   - 3.3 [凭证有效期与安全红线](#33-凭证有效期与安全红线)
4. [第二部分：下单流程集成（按场景 Demo）](#4-第二部分下单流程集成按场景-demo)
   - 4.0 [通用：签名客户端与 tag 规则](#40-通用签名客户端与-tag-规则)
   - 场景 1～7：现货 / 合约 / 期权与事件合约 / 条件单 / 批量 / 网格 / 定投
5. [反佣验证与对账](#5-反佣验证与对账)
6. [常见错误码与排查](#6-常见错误码与排查)
7. [上线前检查清单](#7-上线前检查清单)
8. [附录：完整可运行参考实现（前端 + 后端）](#8-附录完整可运行参考实现前端--后端)

---

## 0. 怎么用这份指南（开发者 & AI 编程助手）

**分层约定**：本文的 **HTTP 规格与签名规则是标准（normative）**——端点、请求体、请求头、判定逻辑、签名算法以文字规格为准；文中所有代码（Python / Node / Java / Flask / HTML）都是**参考实现（informative）**。用什么语言、什么框架由你决定，正确性由规范与自验证关卡锁住。

**两种用法**：

- **人来写**：按第 3、4 节的规格直接实现；语言差异看 4.0 的「移植五步法」与生态坑位表。
- **交给 AI 写（推荐）**：把本文整篇交给你的 AI 编程助手（Cursor / Claude Code / Copilot 等），并说明技术栈，例如：「按这份指南，用 Spring Boot 在我的项目里接入 OKX 鉴权和现货下单」。

**AI 编程助手必守规则**（人工 review 时也按这 8 条把关）：

1. 先实现 4.0 的签名函数并通过 known-answer 向量自测，**向量全对之前不写任何业务代码**；
2. `client_secret` / `secretKey` / `passphrase` 只经环境变量或密钥管理服务注入——不硬编码、不打日志、不进前端；
3. 签名的字符串与实际发送的字符串必须是**同一个**（sign-what-you-send），不得交给 HTTP 框架二次序列化；
4. 每个下单请求体由**服务端配置**注入 `tag=BROKER_CODE`（批量单逐元素注入），不依赖调用方传入；
5. 默认模拟盘（请求头 `x-simulated-trading: 1`）；切实盘必须是显式的配置变更，不得写成默认值；
6. 鉴权四步（换 token → 删旧 Key → 建 Key → 落库）的顺序与幂等判定（`59506` 放行）不得改动或省略；
7. 回跳 `domain` 白名单校验（3.2 第 0 步）不得省略；
8. 不得发明本文与 OKX 官方文档中不存在的端点、参数、错误码；有歧义时以本文 HTTP 规格为准，其次官方文档。

---

## 1. 总览：两条主线

接入 = **鉴权（一次性）** + **下单（持续）** 两条主线：

```
┌────────────────── 主线 A：鉴权（每个用户做一次） ──────────────────┐
│                                                                    │
│ 用户浏览器          你的前端            你的后端              OKX   │
│    │ 点「连接 OKX」    │                   │                    │   │
│    │─────────────────>│ authorize(...)    │                    │   │
│    │<── 跳转 OKX 授权页│                   │                    │   │
│    │────────── 登录并授权（勾选"快捷 API"）─────────────────────>│   │
│    │<──────── 302 回跳 redirect_uri?code=…&state=…&domain=… ────│   │
│    │─────────────────>│ 校验 state        │                    │   │
│    │                  │─POST {code,domain}>│                   │   │
│    │                  │                   │ ①code 换 token ───>│   │
│    │                  │                   │ ②删旧 Key ────────>│   │
│    │                  │                   │ ③建 Fast API Key ─>│   │
│    │                  │                   │ ④加密落库(按用户)   │   │
│    │                  │<── {ok, 打码 key} ─│                    │   │
└────────────────────────────────────────────────────────────────────┘

┌────────────────── 主线 B：下单（7×24 持续） ───────────────────────┐
│                                                                    │
│ 你的后端（策略引擎 / 定时任务 / 用户触发）                            │
│    │ 取出该用户的 API Key 三件套（apiKey/secretKey/passphrase）      │
│    │ 组装请求体，并把 tag = BrokerCode 写进去   ←← 反佣的关键        │
│    │ OKX 标准 HMAC 签名                                             │
│    │──POST /api/v5/trade/order 等──────────────────────────> OKX   │
│    │<─────── data[0].ordId / sCode / tag（回显）────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

为什么鉴权用 **Fast API** 而不是普通 OAuth token：交易机器人要在用户不在场时持续运行，普通 OAuth 的 refresh_token 只有 3 天，用户几天不来授权链路就断了；Fast API 让用户**一次授权**，你就替他创建一个**长期有效的 API Key**（直到用户解绑/撤销），机器人可 7×24 运行。

为什么下单必须带 **tag**：OKX 官方 Broker 文档 <https://www.okx.com/docs-v5/broker_en>（见「Broker guide → Get rebate guide」与「OAuth Broker → Preparation before Integration → 2. OAuth Rebate settings」两节，页面右上角可切换中文）明确要求——**OAuth Broker 下单时必须把 BrokerCode 填入请求的 `tag` 字段，OKX 依据该 tag 计算返佣**；凡请求参数里有 `tag` 的接口都要填。不带 tag 的订单不计入你的返佣。

---

## 2. 前置申请（人工步骤，代码替代不了）

1. 注册 OKX 账号，在官网申请成为 **OAuth Broker**（Broker 首页 → Click to apply），审核约 2 个工作日。
2. 申请时提供 / 开通：
   - **第三方服务器 IP 白名单**（Fast API 必须先开）
   - **Redirect URL**（授权回跳地址，必须与你前端实际使用的完全一致）
   - Logo、跨域域名（Cross Domain Name）
   - **Fast API 权限**
3. 审核通过后，你会收到邮件，内含 `client_id` 与 `client_secret`。`client_secret` 妥善保管，只放后端。
4. 在 **Broker Dashboard** 查看你的专属 **BrokerCode**（1–16 位字母数字，区分大小写）。这是下单 `tag` 要填的值。

> 以上任一项缺失的典型报错：`53017`（Fast API 权限未开通）、`53016`（redirect_uri 非法）、`50118`（bindApp 需要 IP 白名单）、`50117`（非 API 经纪商）。

---

## 3. 第一部分：鉴权流程集成（前后端改造）

目标：用户在**你的产品里**点一个「连接 OKX」按钮，完成一次授权后，你的后端替他持有一个长期 API Key。

### 3.1 前端改造清单（3 处改动）

以下示例为原生 JS，逻辑可平移到 React / Vue 等任意框架；拼装好的完整页面见[附录 A](#附录-a前端完整示例页单文件-html)。

#### 改动 ①：引入 OKX Web SDK

```html
<!-- 海外站点；引入成功后存在全局对象 window.OKEXOAuthSDK -->
<script src="https://static.okx.com/cdn/assets/okfe/libs/okxOAuth/index.js"></script>
```

```js
OKEXOAuthSDK.init({ requestUrl: 'https://www.okx.com' });
// 若要支持多站点（tr.okx.com / eea.okx.com），requestUrl 需按用户站点参数化
```

#### 改动 ②：加「连接 OKX」按钮，发起授权

```js
document.getElementById('btn-connect-okx').addEventListener('click', () => {
  const state = OKEXOAuthSDK.generateState();   // 随机串，防 CSRF
  // 用 localStorage（回跳可能落在新标签页，sessionStorage 会取不到）
  localStorage.setItem('okx_oauth_state', state);
  OKEXOAuthSDK.authorize({
    response_type: 'code',
    access_type:  'offline',                    // Fast API 走授权码模式，不支持 PKCE
    client_id:    YOUR_CLIENT_ID,               // 公开信息，可由后端配置接口下发
    redirect_uri: encodeURIComponent(YOUR_REDIRECT_URI),
    scope:        'fast_api',                   // ★ 关键：授权页出现「快捷 API」全靠它
    state,
  });
});
```

两个易踩的坑：

- **`scope` 必须是 `fast_api`**——授权页不显示「快捷 API」选项，九成是这里没写对。
- **`redirect_uri` 双重编码**：`redirect_uri` 在授权 URL 里必须**恰好被 URL 编码一次**。`encodeURIComponent('https://yourapp.com/cb')` 会把 `://` 编成 `%3A%2F%2F`——这是正常的一次编码；但若 SDK 拼授权 URL 时**又**编码一次，`%` 本身会被编成 `%25`，值就变成 `%253A%252F%252F`。OKX 服务端只解码一次，看到的是 `https%3A%2F%2Fyourapp.com/cb` 这个字面字符串，与你登记的白名单地址对不上——后果就是授权页报 redirect_uri 不匹配（`53016`）或授权完成后回跳丢失。
  **自查**：跳转后打开浏览器 Network，看实际授权 URL 里 `redirect_uri=` 的值：出现 `%253A` = 编码了两次，去掉你这层 `encodeURIComponent(...)` 直接传原始字符串；出现裸的 `://` = 一次都没编，需要加上。目标形态是恰好一次编码的 `%3A%2F%2F`。

#### 改动 ③：回调路由处理（校验 state → 把 code 交给后端）

用户授权后 OKX 会 302 回跳到 `redirect_uri`，URL 形如：

```
https://yourapp.com/callback?code=xxx&state=yyy&domain=https://www.okx.com
```

在该路由（或检测到 URL 带 `code` 的页面）里：

```js
const params = new URLSearchParams(location.search);
const code   = params.get('code');
if (code) {
  const state      = params.get('state');
  const domain     = params.get('domain');      // 用户可能来自 eea.okx.com 等站点
  const savedState = localStorage.getItem('okx_oauth_state');

  // 1) 防 CSRF：回跳 state 必须等于发起时保存的 state，不一致直接丢弃
  if (!savedState || savedState !== state) {
    history.replaceState({}, '', location.pathname);  // 清掉旧 code，避免刷新死循环
    return showError('state 校验失败，请重新发起授权');
  }
  localStorage.removeItem('okx_oauth_state');
  history.replaceState({}, '', location.pathname);    // 2) 清掉 URL 上的 code

  // 3) 交给你自己的后端（带上你产品的登录态，让后端知道这是哪个用户）
  await fetch('/api/okx/connect', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code, domain }),
  });
}
```

> 前端**只**经手 `code`（10 分钟有效、一次性）。`client_secret`、换到的 token、创建出的 Key 全程不进前端。

### 3.2 后端改造清单（1 个新接口 + 凭证存储）

你需要在自己的后端加一个「OKX 连接」接口，内部按顺序做 4 件事。本节给出 HTTP 级规格（语言中立）；完整可运行的 Python/Flask 版本见[附录 B](#附录-b后端完整参考实现python--flask-单文件)。

#### 第 0 步：校验回跳 domain（安全，别省）

`domain` 来自外部输入。必须白名单校验后才能当 base_url，否则攻击者可诱导你的后端把 `access_token` 发往任意服务器（SSRF / 凭证外泄）：

```python
ALLOWED_DOMAINS = {"https://www.okx.com", "https://tr.okx.com", "https://eea.okx.com"}
base = domain if domain in ALLOWED_DOMAINS else "https://www.okx.com"
```

> 若 `domain=https://eea.okx.com`，该用户后续所有 REST 调用都用这个域名（WebSocket 用 `wss://wseea.okx.com`）。建议把 `base` 与凭证一起落库。

#### 第 1 步：授权码换 access_token

```
POST {base}/v5/users/oauth/token
Content-Type: application/json

{
  "grant_type": "authorization_code",
  "code": "<回调拿到的 code>",
  "client_id": "<YOUR_CLIENT_ID>",
  "client_secret": "<YOUR_CLIENT_SECRET>"
}

→ { "access_token": "…", "token_type": "bearer", "expires_in": 3600 }   // 无 refresh_token
```

> **路径说明（真机踩过的坑）**：经真机联调确认，换 token 用 `/v5/users/oauth/token`（`/api/v5/...` 会 404）；而下面删/建 Key 接口是 `/api/v5/...`。若你的环境换 token 报 404，在两个路径间切换重试。

这个 access_token **只有 1 小时、没有 refresh_token**，它唯一的用途是接下来两步（删旧 Key、建新 Key）。真正长期干活的是创建出来的 API Key。

#### 第 2 步：删除旧 Key（幂等，避免 50116）

平台约束：**一个 Broker 对一个用户只能有一个有效的 Fast API Key**，所以创建前先删：

```
POST {base}/api/v5/users/oauth/delete-apikey
Authorization: Bearer <access_token>
（模拟盘需加请求头 x-simulated-trading: 1）

→ {"code":"0", …}        // 删除成功
→ {"code":"59506", …}    // Key 本来就不存在 —— 属正常，放行继续
```

判定逻辑：`code` 不在 `("0", "59506")` 内才算失败中断。

#### 第 3 步：创建 Fast API Key

```
POST {base}/api/v5/users/oauth/apikey
Authorization: Bearer <access_token>
（模拟盘需加请求头 x-simulated-trading: 1）

{
  "label": "your-app-name",
  "passphrase": "<8-32位，须含大写+小写+数字+特殊字符>",
  "perm": "trade",          // ★ 要下单必须 trade；read_only 只能查询。均无提币权限
  "bindApp": true           // true=绑定你预留的 IP 白名单，仅白名单服务器可用此 Key（推荐）
}

→ { "code":"0", "data":[{
      "label":"…", "apiKey":"…", "secretKey":"…", "passphrase":"…",
      "perm":"trade", "bindApp":true
   }] }
```

#### 第 4 步：凭证加密落库（按用户隔离）

`data[0]` 里的 `apiKey / secretKey / passphrase` 就是该用户的长期凭证，建议存储结构：

| 字段 | 说明 |
|---|---|
| `user_id` | 你产品内的用户 ID（主键/唯一索引） |
| `api_key` | OKX apiKey |
| `secret_key` | **加密存储**（KMS / 信封加密） |
| `passphrase` | **加密存储** |
| `base_url` | 该用户的站点域名（第 0 步的 `base`） |
| `perm` / `created_at` | 权限、创建时间 |

给前端的响应**最多回打码后的 apiKey**（如 `ab12****cd34`）；`secretKey / passphrase` 绝不下发、绝不打日志。

> 附录 B 的参考实现用进程内字典存储，**仅为联调演示**（重启即丢、无加密）；生产必须换成上表的加密落库。
> 用户解绑：在你产品内删除该用户的 Key 记录即可（用户也可自行登录 OKX 撤销授权，届时该 Key 失效）。

#### 鉴权部分端点速查

| 用途 | 方法 | 路径 | 鉴权方式 |
|---|---|---|---|
| 换 access_token | POST | `/v5/users/oauth/token`（404 时试 `/api/v5/...`） | client_id + client_secret |
| 删 Fast API Key | POST | `/api/v5/users/oauth/delete-apikey` | `Authorization: Bearer <access_token>` |
| 建 Fast API Key | POST | `/api/v5/users/oauth/apikey` | `Authorization: Bearer <access_token>` |

### 3.3 凭证有效期与安全红线

| 凭证 | 有效期 | 存放位置 |
|---|---|---|
| 授权码 `code` | 10 分钟（一次性） | 前端 → 后端，用完即弃 |
| `access_token` | 1 小时（Fast API 无 refresh_token） | 仅后端内存，用于删/建 Key |
| **Fast API Key 三件套** | **长期**，直到用户解绑/撤销 | 后端加密落库 |
| `client_id` | — | 公开信息，可进前端 |
| `client_secret` | — | **仅后端**，环境变量 / 密钥管理服务 |

**安全红线**：`client_secret`、`secretKey`、`passphrase` 只能待在后端——不进前端、不进日志、不进 git；全部经环境变量或密钥管理服务注入，代码中零硬编码。

---

## 4. 第二部分：下单流程集成（按场景 Demo）

拿到用户的 Fast API Key 后，你的后端就可以替用户调用 OKX OpenAPI v5 的私有接口下单。**所有场景的请求体都要带 `tag: BROKER_CODE`**——这是返佣归属的唯一依据。

### 4.0 通用：签名客户端与 tag 规则

所有下单接口都是**同一套 HMAC 签名**（OKX 标准）：

```
timestamp      = ISO8601 UTC，毫秒恰好 3 位 + "Z"，如 2020-12-08T09:08:57.715Z
prehash        = timestamp + method(大写) + requestPath(含 query) + body（GET 为空串）
OK-ACCESS-SIGN = base64( HMAC_SHA256( secretKey, prehash ) )
不变式：签名用的字符串（timestamp、path、body）必须与实际发送的逐字节相同
```

请求头：`OK-ACCESS-KEY`（apiKey）、`OK-ACCESS-SIGN`、`OK-ACCESS-TIMESTAMP`、`OK-ACCESS-PASSPHRASE`、`Content-Type: application/json`；模拟盘另加 `x-simulated-trading: 1`（实盘不要带）。

先封装一个通用请求函数，后面每个场景只换 `path` 和 `body`。以下 **Python / Node / Java** 三份实现等价，任选其一；其它语言按本节末尾的「移植五步法」自行实现：

**Python**：

```python
import base64, hashlib, hmac, json
from datetime import datetime, timezone
import requests

def _ts():
    now = datetime.now(timezone.utc)   # 只取一次，避免跨秒竞态
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"

def okx_request(creds: dict, method: str, path: str, body_obj: dict | list | None = None,
                simulated: bool = True) -> dict:
    """creds: 从你的库里取出的该用户凭证 {api_key, secret_key, passphrase, base_url}"""
    body = json.dumps(body_obj) if body_obj is not None else ""
    ts = _ts()
    prehash = f"{ts}{method.upper()}{path}{body}"
    sign = base64.b64encode(
        hmac.new(creds["secret_key"].encode(), prehash.encode(), hashlib.sha256).digest()
    ).decode()
    headers = {
        "OK-ACCESS-KEY":        creds["api_key"],
        "OK-ACCESS-SIGN":       sign,
        "OK-ACCESS-TIMESTAMP":  ts,
        "OK-ACCESS-PASSPHRASE": creds["passphrase"],
        "Content-Type":         "application/json",
    }
    if simulated:
        headers["x-simulated-trading"] = "1"
    # ⚠️ 必须用 data=body 发送与签名完全相同的字符串（勿用 json= 让库重新序列化）；
    #    GET 带 query 时，path 必须含 ?k=v 且与实际请求逐字一致（勿用库的 params=）。
    resp = requests.request(method, creds["base_url"] + path,
                            headers=headers, data=body or None, timeout=10)
    try:
        return resp.json()
    except ValueError:
        return {"_http_status": resp.status_code, "_non_json_body": resp.text[:300]}
```

**Node / JS**：

```js
const crypto = require('crypto');

function ts() { return new Date().toISOString(); }  // 天然毫秒3位+Z

async function okxRequest(creds, method, path, bodyObj = null, simulated = true) {
  const body = bodyObj ? JSON.stringify(bodyObj) : '';
  const t = ts();
  const sign = crypto.createHmac('sha256', creds.secretKey)
    .update(t + method.toUpperCase() + path + body).digest('base64');
  const headers = {
    'OK-ACCESS-KEY': creds.apiKey,
    'OK-ACCESS-SIGN': sign,
    'OK-ACCESS-TIMESTAMP': t,
    'OK-ACCESS-PASSPHRASE': creds.passphrase,
    'Content-Type': 'application/json',
  };
  if (simulated) headers['x-simulated-trading'] = '1';
  const resp = await fetch(creds.baseUrl + path, { method, headers, body: body || undefined });
  return resp.json();
}
```

**Java**（JDK 11+，仅用标准库，无第三方依赖；已编译并通过下方向量自测）：

```java
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Base64;

public class OkxClient {

    /** 该用户的凭证（从你的库里取出；secretKey / passphrase 生产必须加密存储） */
    public static class Creds {
        public final String apiKey, secretKey, passphrase, baseUrl;
        public Creds(String apiKey, String secretKey, String passphrase, String baseUrl) {
            this.apiKey = apiKey; this.secretKey = secretKey;
            this.passphrase = passphrase; this.baseUrl = baseUrl;
        }
    }

    // ⚠️ 勿用 Instant.now().toString()：小数位数不固定（0/3/6/9 位都可能）；签名要求恰好 3 位毫秒 + Z
    private static final DateTimeFormatter TS_FMT =
            DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'").withZone(ZoneOffset.UTC);

    private static final HttpClient HTTP = HttpClient.newHttpClient();

    /** 通用签名请求：bodyJson 传"已序列化好的 JSON 字符串"（GET 传 null），签名与发送用同一字符串 */
    public static String okxRequest(Creds creds, String method, String path,
                                    String bodyJson, boolean simulated) throws Exception {
        String body = bodyJson == null ? "" : bodyJson;
        String ts = TS_FMT.format(ZonedDateTime.now(ZoneOffset.UTC));
        String prehash = ts + method.toUpperCase() + path + body;

        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(creds.secretKey.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
        String sign = Base64.getEncoder().encodeToString(mac.doFinal(prehash.getBytes(StandardCharsets.UTF_8)));

        HttpRequest.Builder req = HttpRequest.newBuilder()
                .uri(URI.create(creds.baseUrl + path))
                .header("OK-ACCESS-KEY", creds.apiKey)
                .header("OK-ACCESS-SIGN", sign)
                .header("OK-ACCESS-TIMESTAMP", ts)
                .header("OK-ACCESS-PASSPHRASE", creds.passphrase)
                .header("Content-Type", "application/json")
                .method(method.toUpperCase(), body.isEmpty()
                        ? HttpRequest.BodyPublishers.noBody()
                        : HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8));
        if (simulated) req.header("x-simulated-trading", "1");

        return HTTP.send(req.build(), HttpResponse.BodyHandlers.ofString()).body();
    }

    // 用法示例（对应场景 1 现货限价单）。生产用 Jackson：objectMapper.writeValueAsString(orderMap)
    public static void main(String[] args) throws Exception {
        Creds creds = new Creds(System.getenv("OKX_API_KEY"), System.getenv("OKX_SECRET_KEY"),
                System.getenv("OKX_PASSPHRASE"), "https://www.okx.com");
        String body = "{\"instId\":\"BTC-USDT\",\"tdMode\":\"cash\",\"side\":\"buy\","
                    + "\"ordType\":\"limit\",\"px\":\"60000\",\"sz\":\"0.001\","
                    + "\"tag\":\"" + System.getenv("BROKER_CODE") + "\"}";
        System.out.println(okxRequest(creds, "POST", "/api/v5/trade/order", body, true));
    }
}
```

**第一道关卡（强制）**：无论用哪种语言，签名函数写好后，先用下面这组固定向量自测——两条期望签名**全部逐字符相等**后，再写业务代码。这也是把本文交给 AI 时，检验其生成代码正确性的客观依据（无需真机、无需凭证）：

```
secretKey = "mock-secret"                    ← 占位测试值，非真实密钥
timestamp = "2020-12-08T09:08:57.715Z"

GET /api/v5/account/balance           body=""  → 期望签名 tpQYvXdaAfU8ae6zI1rJ2xVcyMIk9BKWK/fysaanweQ=
GET /api/v5/account/balance?ccy=BTC   body=""  → 期望签名 pS6nHuBl6Qc9S0h+soCkCVHaVHZzS19KqFpeI/doTlE=
```

> 签名最易错三点：① 时间戳与请求头必须是**同一个值**；② prehash 顺序严格为 `ts+METHOD+path+body`，GET 的 body 为空串；③ 带 query 的 path 必须与实际请求逐字一致。

#### 移植到任意语言：五步法

Go / C# / PHP / Rust……任何语言按此顺序移植，每一步都有客观判定，不依赖肉眼 review：

1. 实现签名函数（HMAC-SHA256 → Base64；prehash = `ts + METHOD + path + body`）；
2. 用上面的 known-answer 向量自测，两条期望签名**全部逐字符相等**才继续；
3. 实现通用请求函数：同一个字符串既参与签名、又作为请求体**原样**发送；
4. 模拟盘调 `GET /api/v5/account/balance`，返回顶层 `code=0` 即鉴权与签名链路打通；
5. 按 5.1 的超小 sz 拒单法验证下单与 tag 回显。

各生态最常见的坑：

| 生态 | 坑 | 规避 |
|---|---|---|
| Java | `Instant.now().toString()` 小数位数不固定（0/3/6/9 位都可能）→ **间歇性**签名失败，时对时错难排查 | 用 `DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'")` 钉死 3 位毫秒（见上方 Java 实现） |
| Java | Spring RestTemplate / Feign / WebClient 把对象交给框架序列化 → 签名串 ≠ 发送串（50113） | 先 `objectMapper.writeValueAsString(...)` 得到 String，签名它，再以**该字符串**为 body 发送 |
| Go | `time.Format` 布局写 `.999` 会丢尾零（毫秒不足 3 位） | 布局用 `2006-01-02T15:04:05.000Z`（`.000` 强制 3 位） |
| 通用 | HTTP 库的 query 构造器（`params=`、UriComponentsBuilder 等）会重排/重编码参数 | query 手工拼进 path，签名与发送用同一个 path 字符串 |

**tag（BrokerCode）规则**——反佣归属的核心，适用于下面所有场景：

- `tag` 值 = 你在 Broker Dashboard 看到的 **BrokerCode**（1–16 位字母数字，区分大小写）。
- 官方规则：**凡请求参数中有 `tag` 字段的接口，一律填入 BrokerCode**；OKX 据此把订单关联到你并计算返佣、在 Dashboard 统计交易数据。
- 建议 BrokerCode 由服务端配置统一注入（环境变量），不要依赖调用方传入，确保**每一单都带**（漏带的订单不计返佣，事后无法补）。
- 官方明确支持 `tag` 的下单类接口：普通下单、批量下单、平仓、策略委托（algo）、网格、定投（Recurring Buy），以及大宗/价差交易与闪兑等。

以下按场景给出请求示例。**端点是复用的**：所有普通单（现货/合约/期权/事件）都打到 `POST /api/v5/trade/order`，靠 `instId / tdMode / ordType` 区分；条件单同理复用 `POST /api/v5/trade/order-algo`。

> 场景示例统一以 Python 展示；**规范是 path + JSON body 本身**——其它语言（Java/Go/…）用你已通过向量自测的通用请求函数，按相同的 path 与 body 构造即可（Java 即 `okxRequest(creds, "POST", path, bodyJson, simulated)`）。

---

### 场景 1：现货限价 / 市价单 → `POST /api/v5/trade/order`

```python
BROKER_CODE = os.environ["BROKER_CODE"]   # 服务端配置，统一注入

# 限价买入 0.001 BTC @ 60000 USDT
okx_request(creds, "POST", "/api/v5/trade/order", {
    "instId":  "BTC-USDT",
    "tdMode":  "cash",         # 现货固定 cash
    "side":    "buy",
    "ordType": "limit",        # 亦支持 post_only / fok / ioc
    "px":      "60000",
    "sz":      "0.001",        # 限价单 sz 按交易币（BTC）
    "tag":     BROKER_CODE,    # ★ 反佣归属
})

# 市价买入价值 100 USDT 的 BTC
okx_request(creds, "POST", "/api/v5/trade/order", {
    "instId":  "BTC-USDT",
    "tdMode":  "cash",
    "side":    "buy",
    "ordType": "market",       # 市价单不传 px
    "sz":      "100",          # ⚠️ 市价买单 sz 默认按计价币（USDT 金额）
    "tgtCcy":  "quote_ccy",    #    显式声明更稳妥；市价卖单则按交易币数量
    "tag":     BROKER_CODE,
})
```

成功响应（所有 `/trade/order` 场景通用）：

```json
{ "code": "0", "data": [
    { "ordId": "1234567890", "clOrdId": "", "tag": "<你的BrokerCode>", "sCode": "0", "sMsg": "" }
] }
```

- 顶层 `code=0` 且 `data[0].sCode=0` 才是下单成功；`sCode≠0` 时看 `sMsg`。
- `data[0].tag` 会**回显**你上送的 tag——联调时用它确认反佣标识已带上（见第 5 节）。

### 场景 2：合约（永续 / 交割）→ `POST /api/v5/trade/order`

```python
# 永续：全仓限价开多 1 张 BTC-USDT-SWAP
okx_request(creds, "POST", "/api/v5/trade/order", {
    "instId":  "BTC-USDT-SWAP",   # 交割合约形如 BTC-USDT-260327
    "tdMode":  "cross",           # cross 全仓 / isolated 逐仓
    "side":    "buy",
    "posSide": "long",            # 双向持仓模式必填 long|short；单向(net)模式省略
    "ordType": "limit",
    "px":      "60000",
    "sz":      "1",               # ⚠️ 合约 sz 单位是"张"，1 张 = ctVal 个标的
    "tag":     BROKER_CODE,
})

# 市价平仓（减仓）：单向持仓模式用 reduceOnly
okx_request(creds, "POST", "/api/v5/trade/order", {
    "instId": "BTC-USDT-SWAP", "tdMode": "cross",
    "side": "sell", "ordType": "market", "sz": "1",
    "reduceOnly": True,
    "tag": BROKER_CODE,
})
```

配套要点：

- **杠杆**在下单前单独设置：`POST /api/v5/account/set-leverage`，body `{"instId":"BTC-USDT-SWAP","lever":"5","mgnMode":"cross"}`。
- **一键全平**也支持 tag：`POST /api/v5/trade/close-position`，body `{"instId":"BTC-USDT-SWAP","mgnMode":"cross","tag":BROKER_CODE}`（双向持仓加 `posSide`）。
- 每张合约的面值 `ctVal`、最小下单张数等，用公共接口 `GET /api/v5/public/instruments?instType=SWAP` 查询。

### 场景 3：期权 / 预测（事件）合约 → `POST /api/v5/trade/order`

仍是同一端点，换 `instId`：

```python
# 期权：买入 1 张 BTC 看涨期权（期权按张，逐仓）
okx_request(creds, "POST", "/api/v5/trade/order", {
    "instId":  "BTC-USD-260327-100000-C",   # 标的-币种-到期日-行权价-C/P
    "tdMode":  "isolated",
    "side":    "buy",
    "ordType": "limit",
    "px":      "0.05",
    "sz":      "1",
    "tag":     BROKER_CODE,
})
```

预测/事件合约（event）同样复用 `/api/v5/trade/order`，把 `instId` 换成对应事件合约 ID 即可；可交易的事件合约列表与参数细节以 OKX 官方文档为准。

### 场景 4：条件单 / 策略委托 → `POST /api/v5/trade/order-algo`

一个端点覆盖四种玩法，靠 `ordType` 区分（现货、合约通用；合约场景按需加 `posSide` / `reduceOnly`）：

```python
# ① 止盈止损单（conditional：单向；oco：止盈+止损双向择一触发）
okx_request(creds, "POST", "/api/v5/trade/order-algo", {
    "instId": "BTC-USDT-SWAP", "tdMode": "cross", "side": "sell",
    "ordType": "oco",
    "sz": "1",
    "tpTriggerPx": "70000", "tpOrdPx": "-1",   # 触发后市价止盈（-1=市价）
    "slTriggerPx": "55000", "slOrdPx": "-1",   # 触发后市价止损
    "tag": BROKER_CODE,
})

# ② 计划委托（trigger）：价格触达 triggerPx 后，按 orderPx 挂单
okx_request(creds, "POST", "/api/v5/trade/order-algo", {
    "instId": "BTC-USDT", "tdMode": "cash", "side": "buy",
    "ordType": "trigger",
    "sz": "0.001",
    "triggerPx": "58000",
    "orderPx": "-1",                            # -1=触发后市价；也可给具体限价
    "tag": BROKER_CODE,
})

# ③ 移动止损（move_order_stop）：回撤 1% 触发
okx_request(creds, "POST", "/api/v5/trade/order-algo", {
    "instId": "BTC-USDT-SWAP", "tdMode": "cross", "side": "sell",
    "ordType": "move_order_stop",
    "sz": "1",
    "callbackRatio": "0.01",     # 回撤比例；与 callbackSpread(回撤价距) 二选一
    "activePx": "65000",         # 可选：到达该价才激活追踪
    "reduceOnly": True,
    "tag": BROKER_CODE,
})
```

响应返回 `data[0].algoId`（策略委托单号），后续用它查询/撤销策略单。

### 场景 5：批量下单 → `POST /api/v5/trade/batch-orders`

一次最多 **20 笔**；每个元素与场景 1/2 的单笔请求体同构，**每一笔都要各自带 `tag`**：

```python
okx_request(creds, "POST", "/api/v5/trade/batch-orders", [
    {"instId": "BTC-USDT", "tdMode": "cash", "side": "buy",
     "ordType": "limit", "px": "60000", "sz": "0.001", "tag": BROKER_CODE},
    {"instId": "ETH-USDT", "tdMode": "cash", "side": "buy",
     "ordType": "limit", "px": "2500",  "sz": "0.01",  "tag": BROKER_CODE},
])
```

> 注意请求体是**数组**。返回 `data[]` 与请求逐一对应，需**逐条**检查每笔的 `sCode`（部分成功很常见）。

### 场景 6：网格机器人 → `POST /api/v5/tradingBot/grid/order-algo`

```python
# 现货网格：60000–70000 分 20 格，投入 1000 USDT
okx_request(creds, "POST", "/api/v5/tradingBot/grid/order-algo", {
    "instId":      "BTC-USDT",
    "algoOrdType": "grid",          # 现货网格
    "maxPx":       "70000",
    "minPx":       "60000",
    "gridNum":     "20",
    "runType":     "1",             # 1=等差 2=等比
    "quoteSz":     "1000",          # 投入计价币金额（与 baseSz 二选一）
    "tag":         BROKER_CODE,
})

# 合约网格：做多，5 倍杠杆，投入 500 USDT 保证金
okx_request(creds, "POST", "/api/v5/tradingBot/grid/order-algo", {
    "instId":      "BTC-USDT-SWAP",
    "algoOrdType": "contract_grid",
    "maxPx":       "70000",
    "minPx":       "60000",
    "gridNum":     "20",
    "runType":     "1",
    "sz":          "500",           # 保证金（USDT）
    "direction":   "long",          # long | short | neutral
    "lever":       "5",
    "tag":         BROKER_CODE,
})
```

网格属于官方 Broker 文档明确列出的支持 `tag` 的接口（Grid trading → Place grid algo order），机器人后续产生的每笔成交都归属你的 BrokerCode。

### 场景速查表

| 场景 | 端点（均为 POST） | 关键参数 | tag 位置 |
|---|---|---|---|
| 现货限价/市价 | `/api/v5/trade/order` | `tdMode=cash`，市价买 sz 按计价币 | 请求体 `tag` |
| 永续/交割 | `/api/v5/trade/order` | `tdMode=cross\|isolated`、`sz` 按张、双向持仓填 `posSide` | 请求体 `tag` |
| 期权/事件合约 | `/api/v5/trade/order` | 换 `instId` | 请求体 `tag` |
| 止盈止损/计划/移动止损 | `/api/v5/trade/order-algo` | `ordType=conditional\|oco\|trigger\|move_order_stop` | 请求体 `tag` |
| 批量下单 | `/api/v5/trade/batch-orders` | 数组 ≤20 笔，逐笔查 `sCode` | **每个元素**各带 `tag` |
| 一键平仓 | `/api/v5/trade/close-position` | `instId`+`mgnMode` | 请求体 `tag` |
| 网格机器人 | `/api/v5/tradingBot/grid/order-algo` | `algoOrdType=grid\|contract_grid` | 请求体 `tag` |
| 定投/DCA 机器人 | `/api/v5/tradingBot/dca/create` | `algoOrdType=spot_dca\|contract_dca` | 以官方文档为准 |

---

## 5. 反佣验证与对账

### 5.1 联调期：零风险验证 tag 是否带上（推荐先做）

不想在验证阶段产生真实成交？用一个**低于最小下单量的超小 `sz`**（如现货 `0.00000001`）下单：订单必被 OKX 拒绝——不成交、不占资金，但响应仍能验证两件事：

1. **链路已打通**：返回了单条业务结果 `data[0].sCode`（而不是鉴权/签名错误）；
2. **tag 已上送**：`data[0].tag` 回显值 == 你发送的 BrokerCode。

验证脚本（复用 4.0 的 `okx_request`；模拟盘同样适用，全程无真金风险）：

```python
res = okx_request(creds, "POST", "/api/v5/trade/order", {
    "instId": "BTC-USDT", "tdMode": "cash", "side": "buy",
    "ordType": "limit", "px": "1000",
    "sz": "0.00000001",                # 远低于最小下单量 → 必被拒：不成交、不占资金
    "tag": BROKER_CODE,
})
d0 = (res.get("data") or [{}])[0]
print("① 链路打通：", "sCode" in d0)                     # True=已到下单逻辑，而非签名/鉴权错
print("② tag 回显：", d0.get("tag") == BROKER_CODE)      # True=反佣标识已随订单上送
print("   拒单原因（符合预期）：", d0.get("sCode"), d0.get("sMsg"))
```

### 5.2 用户维度：确认该用户能贡献返佣

用**你 Broker 主账号自己的 API Key**（非用户 Key）签名调用：

```
GET /api/v5/broker/fd/if-rebate?apiKey=<用户的apiKey>&brokerType=oauth

→ { "code":"0", "data":[{ "type":"0", "brokerCode":"…", "affiliated":false, … }] }
```

`type=0` 表示该用户满足返佣条件（其余取值含义：1=经纪商身份过期、2=VIP5/6 当月返佣达上限、3=VIP7 及以上、4=MSA 不参与返佣）。

### 5.3 结算维度：下载返佣明细对账

同样用 Broker 主账号 API Key 调用（两步）：

```
① POST /api/v5/broker/fd/rebate-per-orders          // 生成明细（限速 1 次/60 分钟）
   { "begin":"20260601", "end":"20260630", "brokerType":"oauth" }

② GET  /api/v5/broker/fd/rebate-per-orders?type=false&begin=20260601&end=20260630
   → data[0].fileHref                                // 下载链接（限速 2 次/分钟，链接 2 小时有效）
```

CSV 明细字段含：`brokerCode`（订单打的 tag）、`uid`、`instId`、`ordId`、`fee`、`brokerRebate`（你的返佣额）、`userRebate` 等——按 `ordId` 与你的订单流水对账，即可核对每一笔返佣归属。

---

## 6. 常见错误码与排查

### 鉴权 / Fast API 阶段

| 错误码 | 含义 | 处理 |
|---|---|---|
| 50116 | Fast API 只能创建一个 API Key | 创建前先调 delete-apikey（本指南第 3.2 节第 2 步） |
| 50117 | 只有 API 经纪商能用 Fast API | 联系 BD 确认已开通 Fast API 权限 |
| 50118 | bindApp 需要 Broker 提供 IP 白名单 | 先开通 IP 白名单，再用 `bindApp=true` |
| 59506 | API Key 不存在 | 删除步骤遇到属正常，忽略并继续 |
| 53012 | 授权码过期 | code 只有 10 分钟且一次性；重新发起授权。注意站点域名要与授权时一致 |
| 53016 | redirect_uri 非法 | 与 OKX 侧登记的白名单逐字符比对（含协议、端口、结尾斜杠） |
| 53017 | Fast API 权限未开通 | 联系 BD 开通 |
| 53002 / 53003 | token 过期 / 已撤销 | access_token 仅 1 小时；重新走授权 |
| 53014 | Invalid IP | 请求来源 IP 不在你登记的白名单内 |
| 53018 | 未获得 my.okx.com 站点授权 | 从 BD 获得该站点授权 |

授权页问题：不显示「快捷 API」→ 查 `scope=fast_api`；跳转报 redirect_uri 不匹配 → 查双重编码（3.1 节改动②）；回跳 state 不一致 → 按 CSRF 丢弃，重新发起。

### 签名 / 下单阶段

| 现象 | 排查 |
|---|---|
| 50113 / 401 签名无效 | ① 时间戳是否 ISO8601 毫秒 UTC 且与请求头同值；② prehash 顺序 `ts+METHOD+path+body`；③ GET 的 body 为空串、query 与 path 逐字一致；④ 发送体与签名体是否同一字符串（勿让 HTTP 库重新序列化）；⑤ passphrase 是否为创建 Key 时那个 |
| 50102 时间戳过期 | 服务器时钟漂移，做 NTP 校时 |
| 模拟盘/实盘串环境 | 模拟盘必须带 `x-simulated-trading: 1`，实盘必须不带；Key 也分环境 |
| 顶层 code=0 但 `data[0].sCode≠0` | 下单业务错误：看 `sMsg`（常见：51000 参数错误、51008 余额/保证金不足、数量低于最小下单量等） |
| 下单报权限不足 | 创建 Key 时 `perm` 是 `read_only`；需引导用户重新授权，以 `perm=trade` 重建 Key |
| tag 未回显 | 请求体里没带 `tag` 或字段名拼错；BrokerCode 需 1–16 位字母数字 |

---

## 7. 上线前检查清单

**鉴权链路**

- [ ] `scope=fast_api`、`access_type=offline`；授权页能看到「快捷 API」
- [ ] state 生成、保存、回跳校验、用后清除，全链路闭环
- [ ] 回跳 `domain` 白名单校验（www / tr / eea），并随凭证落库
- [ ] 换 token → 删旧 Key（59506 放行）→ 建 Key（`perm=trade`、`bindApp=true`）全链路在**模拟盘**跑通
- [ ] 凭证按用户隔离、加密落库；前端只见打码 apiKey
- [ ] `client_secret / secretKey / passphrase` 不出现在前端、日志、git 中

**下单链路**

- [ ] 签名函数通过 4.0 的 known-answer 向量自测（换语言/换库/升级依赖后需重跑）
- [ ] 所有下单代码路径统一从服务端配置注入 `tag=BrokerCode`（含批量单的每个元素）
- [ ] 超小 sz 拒单法验证：`data[0].tag` 回显 == BrokerCode
- [ ] `GET /api/v5/broker/fd/if-rebate` 确认测试用户 `type=0`
- [ ] 模拟盘全场景回归后，再切实盘（去掉 `x-simulated-trading` 头）；实盘首单用最小金额验证
- [ ] 批量下单逐条检查 `sCode`；限速与重试策略就绪（下单接口限速以官方文档为准）
- [ ] 返佣对账任务接入 `rebate-per-orders` 明细下载

---

## 8. 附录：完整可运行参考实现（前端 + 后端）

正文 3.1 / 3.2 / 4.0 的代码片段，拼装成两个可直接运行的文件。**本附录是参考实现之一，不是标准**：后端恰好用了 Python/Flask，Java / Go 等其它语言按正文的 HTTP 规格与「移植五步法」对应实现即可——保持逻辑与顺序不变，逐段对照翻译也可以。

**运行方式**：

```bash
pip install flask requests
export CLIENT_ID=...  CLIENT_SECRET=...  BROKER_CODE=...        # BD 邮件 / Broker Dashboard 获取
export REDIRECT_URI=http://localhost:8000/                      # 必须在 OKX 侧白名单内
export APIKEY_PASSPHRASE=...                                    # 自设强口令：8-32位，含大小写+数字+特殊字符
export SIMULATED=1                                              # 1=模拟盘（默认，安全）；0=实盘
python okx_broker_backend.py                                    # 打开 http://localhost:8000
```

### 附录 A：前端完整示例页（单文件 HTML）

保存为 `index.html`，与附录 B 后端同目录（由后端直接托管，保证同源）：

```html
<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8" />
  <title>连接 OKX（鉴权参考页）</title>
  <!-- OKX Web SDK：引入成功后存在全局对象 window.OKEXOAuthSDK -->
  <script src="https://static.okx.com/cdn/assets/okfe/libs/okxOAuth/index.js"></script>
</head>
<body>
  <button id="btn-connect-okx">授权并连接 OKX</button>
  <pre id="result"></pre>

<script>
let CONFIG = {};
const show = (obj) => document.getElementById('result').textContent =
  typeof obj === 'string' ? obj : JSON.stringify(obj, null, 2);

async function init() {
  // 后端下发公开配置：{client_id, redirect_uri, scope:'fast_api'}（client_secret 永不下发）
  CONFIG = await (await fetch('/config')).json();
  OKEXOAuthSDK.init({ requestUrl: 'https://www.okx.com' });  // 多站点需按用户站点参数化

  // 授权回跳：URL 带 code 时自动进入连接流程
  const params = new URLSearchParams(location.search);
  const code = params.get('code');
  if (!code) return;
  const state  = params.get('state');
  const domain = params.get('domain');
  const saved  = localStorage.getItem('okx_oauth_state');

  if (!saved || saved !== state) {                    // 防 CSRF：state 不一致直接丢弃
    history.replaceState({}, '', location.pathname);  // 清掉旧 code，避免刷新死循环
    return show('state 校验失败，请重新发起授权');
  }
  localStorage.removeItem('okx_oauth_state');
  history.replaceState({}, '', location.pathname);    // 清掉 URL 上的 code

  // 交给你的后端换 token、创建并保存 Key（生产：此请求需携带你产品的登录态）
  const res = await (await fetch('/api/okx/connect', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code, domain }),
  })).json();
  show(res);   // 成功时仅含打码 apiKey
}

document.getElementById('btn-connect-okx').addEventListener('click', () => {
  const state = OKEXOAuthSDK.generateState();         // 随机 state，防 CSRF
  localStorage.setItem('okx_oauth_state', state);     // 回跳可能落在新标签页，故用 localStorage
  OKEXOAuthSDK.authorize({
    response_type: 'code',
    access_type:  'offline',                          // Fast API 走授权码模式，不支持 PKCE
    client_id:    CONFIG.client_id,
    redirect_uri: encodeURIComponent(CONFIG.redirect_uri),  // 双重编码坑见 3.1 改动②
    scope:        'fast_api',                         // ★ 授权页出现「快捷 API」全靠它
    state,
  });
});

init();
</script>
</body>
</html>
```

### 附录 B：后端完整参考实现（Python / Flask 单文件）

保存为 `okx_broker_backend.py`（与上面 `index.html` 同目录）：

```python
"""okx_broker_backend.py — OKX AI Builder 鉴权 + 下单最小参考（单文件）。
链路：/api/okx/connect（换 token → 删旧 Key → 建 Key → 落库）；/api/okx/order（签名下单，服务端注入 tag）。
"""
import base64, hashlib, hmac, json, os
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder=None)

# ---- 配置全部来自环境变量，禁止硬编码密钥 ----
CLIENT_ID         = os.environ["CLIENT_ID"]
CLIENT_SECRET     = os.environ["CLIENT_SECRET"]        # 仅后端
REDIRECT_URI      = os.environ["REDIRECT_URI"]
BROKER_CODE       = os.environ["BROKER_CODE"]          # 反佣归属标识（Broker Dashboard 查看）
APIKEY_PASSPHRASE = os.environ["APIKEY_PASSPHRASE"]    # 8-32位，含大小写+数字+特殊字符
SIMULATED         = os.environ.get("SIMULATED", "1") == "1"   # 默认模拟盘

ALLOWED_DOMAINS = {"https://www.okx.com", "https://tr.okx.com", "https://eea.okx.com"}
DEFAULT_BASE    = "https://www.okx.com"

# ⚠️ 联调演示用进程内存储；生产必须按 user_id 加密落库（见正文 3.2 第 4 步表结构）
_CREDS = {}   # {user_id: {"api_key","secret_key","passphrase","base_url"}}


def _current_user_id() -> str:
    """TODO: 替换为你产品的登录态解析（session / JWT），返回你系统内的用户 ID。"""
    return request.headers.get("X-Demo-User", "demo-user")


# ============ 通用：OKX 标准 HMAC 签名请求（同正文 4.0） ============

def _ts() -> str:
    now = datetime.now(timezone.utc)   # 只取一次，避免跨秒竞态
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def okx_request(creds: dict, method: str, path: str, body_obj=None,
                simulated: bool = SIMULATED) -> dict:
    body = json.dumps(body_obj) if body_obj is not None else ""
    ts = _ts()
    prehash = f"{ts}{method.upper()}{path}{body}"
    sign = base64.b64encode(
        hmac.new(creds["secret_key"].encode(), prehash.encode(), hashlib.sha256).digest()
    ).decode()
    headers = {
        "OK-ACCESS-KEY":        creds["api_key"],
        "OK-ACCESS-SIGN":       sign,
        "OK-ACCESS-TIMESTAMP":  ts,
        "OK-ACCESS-PASSPHRASE": creds["passphrase"],
        "Content-Type":         "application/json",
    }
    if simulated:
        headers["x-simulated-trading"] = "1"
    resp = requests.request(method, creds["base_url"] + path,
                            headers=headers, data=body or None, timeout=10)
    try:
        return resp.json()
    except ValueError:   # 404/429/502 可能返回非 JSON，兜底成结构化错误
        return {"_http_status": resp.status_code, "_non_json_body": resp.text[:300]}


def _bearer_headers(access_token: str) -> dict:
    h = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    if SIMULATED:
        h["x-simulated-trading"] = "1"
    return h


# ============ 页面与公开配置 ============

@app.get("/")
def index():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), "index.html")


@app.get("/config")
def config():
    """给前端的公开配置。client_id 是公开信息；client_secret 永不下发。"""
    return jsonify({"client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI, "scope": "fast_api"})


# ============ 鉴权：换 token → 删旧 Key → 建 Key → 落库（正文 3.2） ============

@app.post("/api/okx/connect")
def okx_connect():
    data = request.get_json(force=True) or {}
    code, domain = data.get("code"), data.get("domain")
    if not code:
        return jsonify({"ok": False, "error": "missing code"}), 400
    # 第 0 步：domain 白名单校验（防 SSRF / 凭证外泄）
    base = domain if domain in ALLOWED_DOMAINS else DEFAULT_BASE

    # 第 1 步：授权码换 access_token（1 小时、无 refresh_token；404 时把路径换成 /api/v5/...）
    tok = requests.post(base + "/v5/users/oauth/token", json={
        "grant_type": "authorization_code", "code": code,
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
    }, timeout=10).json()
    access_token = tok.get("access_token")
    if not access_token:
        return jsonify({"ok": False, "step": "exchange_token",
                        "code": tok.get("code"), "msg": tok.get("msg")}), 400

    # 第 2 步：删旧 Key（一个 Broker 对一个用户仅一个 Key；59506=本就不存在，放行）
    deleted = requests.post(base + "/api/v5/users/oauth/delete-apikey",
                            headers=_bearer_headers(access_token), timeout=10).json()
    if deleted.get("code") not in ("0", "59506"):
        return jsonify({"ok": False, "step": "delete_apikey",
                        "code": deleted.get("code"), "msg": deleted.get("msg")}), 400

    # 第 3 步：创建 Fast API Key（下单必须 perm=trade；bindApp=true 绑定 IP 白名单）
    created = requests.post(base + "/api/v5/users/oauth/apikey",
                            headers=_bearer_headers(access_token), json={
                                "label": "your-app-name", "passphrase": APIKEY_PASSPHRASE,
                                "perm": "trade", "bindApp": True,
                            }, timeout=10).json()
    if created.get("code") != "0" or not created.get("data"):
        return jsonify({"ok": False, "step": "create_apikey",
                        "code": created.get("code"), "msg": created.get("msg")}), 400

    # 第 4 步：按用户落库（生产：secret_key / passphrase 加密存储）
    k = created["data"][0]
    _CREDS[_current_user_id()] = {
        "api_key":    k["apiKey"],
        "secret_key": k["secretKey"],
        "passphrase": k.get("passphrase") or APIKEY_PASSPHRASE,
        "base_url":   base,
    }
    masked = k["apiKey"][:4] + "****" + k["apiKey"][-4:]
    return jsonify({"ok": True, "api_key_masked": masked, "perm": k.get("perm")})


# ============ 下单：服务端统一注入 tag=BROKER_CODE（正文第 4 节场景任选） ============

@app.post("/api/okx/order")
def okx_order():
    creds = _CREDS.get(_current_user_id())
    if not creds:
        return jsonify({"ok": False, "error": "user not connected"}), 400
    # 生产：按你的产品/策略逻辑构造并校验订单参数（风控、品种白名单等），勿直接透传前端请求体
    body = request.get_json(force=True) or {}
    body["tag"] = BROKER_CODE   # ★ 每一单都由服务端打上反佣标识，不依赖调用方
    res = okx_request(creds, "POST", "/api/v5/trade/order", body)
    return jsonify({"ok": res.get("code") == "0", "sent_tag": BROKER_CODE, "raw": res})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
```

> 建议接入顺序：**模拟盘联调鉴权链路 → 超小 sz 拒单法验证 tag（5.1 节）→ 按场景接入你需要的下单接口 → 实盘小额灰度**。
