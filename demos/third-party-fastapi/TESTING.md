# Testing Guide

This demo has three test layers, from local checks without Broker credentials to real integration with a test Broker.

- (a) Unit tests: no network; verify signing and timestamp logic with known-answer vectors.
- (b) Mock mode: no real HTTP; use canned OKX-like responses to run the frontend/backend flow locally.
- (c) Real integration checklist: after receiving test Broker credentials, validate the simulated trading flow step by step. Integration pitfalls and error codes are centralized in [PITFALLS.md](PITFALLS.md).

Security note: tests and mock mode do not use real secrets. `mock-secret` is a placeholder string, not a credential. `secretKey` and `passphrase` must never appear in frontend responses, logs, or git.

## (a) Unit Tests

Install dev dependencies and run:

```bash
cd demos/third-party-fastapi
test -d .tmpvenv || python3 -m venv .tmpvenv
source .tmpvenv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
```

Expected result: all tests pass.

What the tests cover:

- `tests/test_sign.py`
  - `_sign` known-answer regression with fixed `secret/timestamp/method/path/body`.
  - Strict prehash order: `timestamp + METHOD + requestPathWithQuery + body`.
  - GET with query signs a path containing `?ccy=...`, so its signature differs from the no-query path.
  - Signature is valid `base64(HMAC-SHA256)` and decodes to 32 bytes.
  - `_now_iso_ms` returns ISO8601 UTC with 3-digit milliseconds and a trailing `Z`.
- `tests/test_mock_flow.py`
  - Uses Flask test client for `/api/connect`, `/api/balance`, `/api/order`,
    and the demo workflow routes.
  - Asserts `ok=True`, masked `apiKey`, AI Builder Code echoed as OKX `tag`,
    and no leaked `secretKey` or `passphrase`.

`tests/conftest.py` adds `backend/` to `sys.path`, so running `python -m pytest` from this demo directory is enough.

## Multi-Language Signing Check

`SIGNING.md` includes Python and Node.js snippets. They use the same known-answer vectors as `tests/test_sign.py`.

```bash
node tests/verify_js_sign.js
```

Expected result: the Node.js signatures match the Python baseline and the command exits with code 0.

This only proves the language snippets are algorithmically equivalent. The Python demo has passed real integration; a migrated implementation should still run the real integration checklist below.

## (b) Mock Mode

Start the backend with `MOCK=1`. In this mode, `exchange_token`, `delete_oauth_apikey`, `create_oauth_apikey`, and `get_account_balance` do not send real HTTP. They return canned OKX-like responses.

```bash
cd demos/third-party-fastapi
test -d .tmpvenv || python3 -m venv .tmpvenv
source .tmpvenv/bin/activate
python -m pip install -r requirements.txt
APIKEY_PASSPHRASE=MockPassphrase1! APIKEY_PERM=trade AI_BUILDER_CODE=ABCD1234 MOCK=1 python backend/app.py
# open http://localhost:8000
```

The page header shows `MOCK` in this mode.

The page still references the OKX SDK CDN, but MOCK mode bypasses real OAuth.
For a fully local backend flow, call the backend directly:

```bash
# 1. Connect with any fake code.
curl -s -c cookies.txt -X POST http://localhost:8000/api/connect \
     -H 'Content-Type: application/json' -d '{"code":"mock-code"}'

# 2. Query balance with the session cookie.
curl -s -b cookies.txt http://localhost:8000/api/balance

# 3. Verify the demo workflow routes inject AI Builder Code as OKX tag.
curl -s -b cookies.txt -X POST http://localhost:8000/api/spot/open \
     -H 'Content-Type: application/json' \
     -d '{"instId":"BTC-USDT","quoteAmount":"10"}'
curl -s -b cookies.txt -X POST http://localhost:8000/api/spot/close \
     -H 'Content-Type: application/json' \
     -d '{"instId":"BTC-USDT","quoteAmount":"10"}'
curl -s -b cookies.txt -X POST http://localhost:8000/api/swap/open \
     -H 'Content-Type: application/json' \
     -d '{"instId":"BTC-USDT-SWAP","quoteAmount":"10"}'
curl -s -b cookies.txt -X POST http://localhost:8000/api/swap/close \
     -H 'Content-Type: application/json' \
     -d '{"instId":"BTC-USDT-SWAP","mgnMode":"cross"}'
```

In mock mode, each response should have `ok=true`, `sent_order.tag=ABCD1234`,
and `raw.data[0].tag=ABCD1234`.

The swap workflow examples use `BTC-USDT-SWAP`. The demo supports
linear swap instruments only; inverse USD swap instruments such as
`BTC-USD-SWAP` should return a clear unsupported-instrument error before order
placement.

For real OAuth integration, leave `MOCK` unset. Use `MOCK=1` only for local
backend checks without real OAuth.

## (c) Real Integration Checklist

Prerequisites:

- BD has provided `client_id` and `client_secret`.
- Fast API permission and Broker IP allowlist are enabled.
- `redirect_uri` is registered in the OKX whitelist.
- Start with simulated trading: `SIMULATED=1`.

Configure `.env` locally. Do not commit it:

```env
CLIENT_ID=...
CLIENT_SECRET=...
REDIRECT_URI=http://localhost:8000/
APIKEY_PASSPHRASE=...
SIMULATED=1
APIKEY_PERM=read_only
AI_BUILDER_CODE=
```

Use `APIKEY_PERM=read_only` for balance-only smoke testing. If you plan to run
the demo order workflows in the same pass, set `APIKEY_PERM=trade` before the
first connect so `/api/connect` creates a trade-permission Fast API Key, and
set `AI_BUILDER_CODE=<AI_BUILDER_CODE>` before order workflow tests.

Checklist:

1. [ ] Authorization page opens and shows Fast API permission. If not, check `scope=fast_api`.
2. [ ] Callback returns with `code`; the UI logs `Detected OAuth callback: code=...`.
3. [ ] State validation passes; no `state validation failed` message appears.
4. [ ] Token exchange succeeds; `/api/connect` has no `step=exchange_token` error.
5. [ ] Delete old key is accepted; `code=0` or `59506` are both valid.
6. [ ] New key is created; UI shows masked `apiKey`, `perm` matching
   `APIKEY_PERM`, and `simulated=true`.
7. [ ] Balance query succeeds with `code=0` and fields such as `totalEq` and `details[]`.
8. [ ] To test order attribution in simulation after a read-only connect, stop
   the backend, set `APIKEY_PERM=trade`, start it again, and reconnect so the old
   key is deleted and a new trade-permission Fast API Key is created. Keep
   `SIMULATED=1`, configure `AI_BUILDER_CODE`, fill the page's spot/swap
   instrument and quote amount fields, and run the demo workflow buttons:
   Spot Open, Spot Close, Swap Open, Swap Close. The final OKX order request
   body must contain `tag`.
9. [ ] No sensitive field is leaked in browser responses or backend logs.
10. [ ] For 50116, 50117, 50118, 53018, or signing errors, follow [PITFALLS.md](PITFALLS.md).

After simulated read-only works, change `APIKEY_PERM` or `SIMULATED` only when needed and with explicit trading risk review.

## Verified Integration Pitfall To Recheck When Migrating

This demo has passed real browser authorization. When migrating to another frontend framework, SDK wrapper, or OKX site, recheck high-frequency issues in [PITFALLS.md](PITFALLS.md), especially `redirect_uri` encoding:

- This demo: `frontend/index.html` passes `redirect_uri: encodeURIComponent(CONFIG.redirect_uri)`.
- If authorization reports `redirect_uri` mismatch or callback is lost, inspect the actual authorization URL in browser Network.
- Normal encoding contains `http%3A%2F%2Flocalhost%3A8000%2F`.
- Double encoding contains `%253A` or `%252F`.
- The migrated implementation should make the final authorization URL contain exactly one encoded `redirect_uri`.

## Endpoints Verified By Real Integration

| Purpose | Method | Path |
|---|---|---|
| Exchange access token | POST | `/v5/users/oauth/token` |
| Delete Fast API Key | POST | `/api/v5/users/oauth/delete-apikey` |
| Create Fast API Key | POST | `/api/v5/users/oauth/apikey` |
| Account balance example | GET | `/api/v5/account/balance` |
| Order example | POST | `/api/v5/trade/order` |

The demo workflows also use these OKX endpoints and should be validated during
the next real integration pass:

| Purpose | Method | Path |
|---|---|---|
| Market ticker preflight | GET | `/api/v5/market/ticker` |
| Instrument rules preflight | GET | `/api/v5/public/instruments` |
| Account config for swap position mode | GET | `/api/v5/account/config` |
| Swap position verification | GET | `/api/v5/account/positions` |
| Swap close example | POST | `/api/v5/trade/close-position` |
