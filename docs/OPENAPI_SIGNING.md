# OKX OpenAPI signing

Private OKX OpenAPI requests use the same HMAC signing rule in the `openapi-user` and `oauth-user` demos.

This document applies to:

- `openapi-user` local OpenAPI scripts, where the user's own API Key signs requests.
- `oauth-user` third-party Fast API/OpenAPI server code, where the server signs requests with each end user's created Fast API Key.

It does not apply to the `cli-user` and `mcp-user` skills in this repo; those paths use the OKX-provided execution backend.

```text
timestamp      = ISO8601 UTC with 3-digit milliseconds, for example 2020-12-08T09:08:57.715Z
prehash        = timestamp + method.upper() + request_path_with_query + body
OK-ACCESS-SIGN = base64(HMAC_SHA256(secret_key, prehash))
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

Rules that prevent most signing bugs:

- Use one timestamp variable for both the prehash and request header.
- GET body is an empty string.
- Include query parameters in `request_path` before signing, for example `/api/v5/account/balance?ccy=BTC`.
- Sign exactly the same POST body string that you send over HTTP.
- Do not let an HTTP client rebuild query params or JSON after signing.

## Known-Answer Vectors

Use these fixed vectors to verify any implementation before real integration:

```text
SECRET = "mock-secret"
TS     = "2020-12-08T09:08:57.715Z"
GET  /api/v5/account/balance            body=""   -> tpQYvXdaAfU8ae6zI1rJ2xVcyMIk9BKWK/fysaanweQ=
GET  /api/v5/account/balance?ccy=BTC    body=""   -> pS6nHuBl6Qc9S0h+soCkCVHaVHZzS19KqFpeI/doTlE=
```

Tests and snippets:

- `openapi-user` Python test: [../demos/openapi-user/test_strategy_demo.py](../demos/openapi-user/test_strategy_demo.py)
- `oauth-user` Python test: [../demos/oauth-user/tests/test_sign.py](../demos/oauth-user/tests/test_sign.py)
- `oauth-user` JavaScript check: [../demos/oauth-user/tests/verify_js_sign.js](../demos/oauth-user/tests/verify_js_sign.js)
- `oauth-user` language snippets appendix: [../demos/oauth-user/SIGNING.md](../demos/oauth-user/SIGNING.md)
