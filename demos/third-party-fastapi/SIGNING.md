# OKX API Key Signing Snippets

> After you create a Fast API Key (`apiKey`, `secretKey`, `passphrase`), private OKX business API calls use standard OKX HMAC signing.
> This file is the Type 3 demo's copyable snippet appendix. The canonical signing rules live in [../../docs/OPENAPI_SIGNING.md](../../docs/OPENAPI_SIGNING.md), the integration flow lives in [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md), and the runnable Python implementation is `backend/okx_client.py`.

## Signing Rule

```text
timestamp      = ISO8601 UTC with 3-digit milliseconds, for example 2020-12-08T09:08:57.715Z
prehash        = timestamp + method.upper() + requestPathWithQuery + body
OK-ACCESS-SIGN = base64(HMAC_SHA256(secretKey, prehash))
```

Headers:

```text
OK-ACCESS-KEY:        <apiKey>
OK-ACCESS-SIGN:       <signature>
OK-ACCESS-TIMESTAMP:  <timestamp>
OK-ACCESS-PASSPHRASE: <passphrase>
Content-Type:         application/json
x-simulated-trading:  1   # simulated trading only
```

The three most common mistakes:

- `timestamp` must use 3-digit milliseconds and end with `Z`; reuse the same value in the prehash and request header.
- The prehash order is exactly `timestamp + METHOD + requestPath + body`; GET body is an empty string.
- When a query string exists, `requestPath` must include it, for example `?ccy=BTC`, and it must match the sent request byte for byte. Do not let an HTTP client rebuild `params` after signing.

## Python

```python
import base64
import hashlib
import hmac
from datetime import datetime, timezone

def sign(secret, ts, method, path, body=""):
    msg = f"{ts}{method.upper()}{path}{body}"
    return base64.b64encode(hmac.new(secret.encode(), msg.encode(), hashlib.sha256).digest()).decode()

now = datetime.now(timezone.utc)
ts = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond//1000:03d}Z"
```

## Node.js

```js
const crypto = require('crypto');

function sign(secret, ts, method, path, body = '') {
  return crypto.createHmac('sha256', secret).update(ts + method.toUpperCase() + path + body).digest('base64');
}

const ts = new Date().toISOString();
```

## Known-Answer Checks

All language snippets should pass the same fixed vectors:

```text
SECRET = "mock-secret"
TS     = "2020-12-08T09:08:57.715Z"
GET  /api/v5/account/balance            body=""   -> tpQYvXdaAfU8ae6zI1rJ2xVcyMIk9BKWK/fysaanweQ=
GET  /api/v5/account/balance?ccy=BTC    body=""   -> pS6nHuBl6Qc9S0h+soCkCVHaVHZzS19KqFpeI/doTlE=
```

- Python: `pytest` checks `tests/test_sign.py`.
- Node.js: `node tests/verify_js_sign.js`.

When adding another language snippet, run it against these vectors first. The Python demo has passed real integration; language ports should still run known-answer checks and then an end-to-end test environment check.
