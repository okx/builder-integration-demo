# OKX OpenAPI signing

Private OKX OpenAPI requests use the same HMAC signing rule in Type 1 and Type 3 demos.

This document applies to:

- Type 1 local OpenAPI scripts, where the user's own API Key signs requests.
- Type 3 third-party Fast API/OpenAPI server code, where the server signs requests with each end user's created Fast API Key.

It does not apply to Type 2 CLI/MCP skills in this repo; those paths use the OKX-provided execution backend.

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

- Type 1 Python test: [../demos/self-account-openapi/test_strategy_demo.py](../demos/self-account-openapi/test_strategy_demo.py)
- Type 3 Python test: [../demos/third-party-fastapi/tests/test_sign.py](../demos/third-party-fastapi/tests/test_sign.py)
- Type 3 JavaScript check: [../demos/third-party-fastapi/tests/verify_js_sign.js](../demos/third-party-fastapi/tests/verify_js_sign.js)
- Type 3 language snippets appendix: [../demos/third-party-fastapi/SIGNING.md](../demos/third-party-fastapi/SIGNING.md)
