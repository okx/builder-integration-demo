# OKX API Key 签名（HMAC）· 多语言片段

> 拿到 Fast API Key（`apiKey` / `secretKey` / `passphrase`）后，调用 OKX 业务接口要用 **OKX 标准 HMAC 签名**。
> 本文是可直接粘贴的多语言签名片段。接入流程见 `INTEGRATION_GUIDE.md`，完整可运行实现见 `backend/okx_client.py`。

## 签名规则

```
timestamp      = ISO8601 毫秒 UTC，如 2020-12-08T09:08:57.715Z
prehash        = timestamp + method(大写) + requestPath(含 query) + body
OK-ACCESS-SIGN = base64( HMAC_SHA256( secretKey, prehash ) )
```

请求头：
```
OK-ACCESS-KEY:        <apiKey>
OK-ACCESS-SIGN:       <上面算出的签名>
OK-ACCESS-TIMESTAMP:  <timestamp>
OK-ACCESS-PASSPHRASE: <passphrase>
Content-Type:         application/json
x-simulated-trading:  1     # 仅模拟盘需要
```

**最容易写错的三点：**
- `timestamp` 必须是毫秒 3 位 + `Z` 结尾，且与请求头里的值**完全一致**（同一个变量，别算两次）。
- prehash 顺序严格为 `timestamp + METHOD(大写) + requestPath + body`；GET 的 `body` 用空字符串。
- 带 query 时 `requestPath` 必须含 `?ccy=...`，且与实际发出的请求**逐字一致**——不要用 HTTP 库的自动 `params` 拼接（顺序/编码可能与签名串不同，导致 50113 签名失败）。

---

## Python

```python
import base64, hmac, hashlib
from datetime import datetime, timezone

def sign(secret, ts, method, path, body=""):
    msg = f"{ts}{method.upper()}{path}{body}"
    return base64.b64encode(hmac.new(secret.encode(), msg.encode(), hashlib.sha256).digest()).decode()

now = datetime.now(timezone.utc)   # 只取一次，避免整秒边界跨秒竞态
ts = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond//1000:03d}Z"
```

## Node / JS

```js
const crypto = require('crypto');
function sign(secret, ts, method, path, body = '') {
  return crypto.createHmac('sha256', secret).update(ts + method.toUpperCase() + path + body).digest('base64');
}
const ts = new Date().toISOString();   // 形如 2020-12-08T09:08:57.715Z（始终毫秒 3 位 + Z）
```

---

## 正确性验证（known-answer 交叉校验）

所有语言的片段都用**同一组固定向量**校验，保证彼此**算法等价**，而非靠肉眼 review。基准如下：

```
SECRET = "mock-secret"
TS     = "2020-12-08T09:08:57.715Z"
GET  /api/v5/account/balance            body=""   → tpQYvXdaAfU8ae6zI1rJ2xVcyMIk9BKWK/fysaanweQ=
GET  /api/v5/account/balance?ccy=BTC    body=""   → pS6nHuBl6Qc9S0h+soCkCVHaVHZzS19KqFpeI/doTlE=
```

- **Python**：`pytest`（见 `tests/test_sign.py`，`KNOWN_SIG_*`）。
- **Node/JS**：`node tests/verify_js_sign.js`。

**新增任何语言的片段时**，请用上面同一组向量自测，输出必须等于上述期望值，否则即为实现有误。

> 这套校验只证明各语言**算法等价**；算法本身是否被 OKX 服务端接受，需真机验证（见 `TESTING.md` 的 (c)）。
> 验证链：真机验证 Python 有效 → known-answer 钉死 Python 基准 → 其它语言比对一致 → 即正确。
