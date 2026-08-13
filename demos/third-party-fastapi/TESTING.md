# Third-party Fast API Testing Guide

This demo has two test layers: local automated checks without Broker
credentials, and real integration with a test Broker.

The real integration checklist is written for the OKX Global site. For another
OKX site, check endpoint availability and request schemas in the OpenAPI
Markdown docs before adapting the checklist.

- (a) Local automated tests: no network; verify signing, backend routes, frontend
  workflow state, and canned OKX-like responses through pytest and Node checks.
- (b) Real integration checklist: after receiving test Broker credentials,
  validate the simulated trading flow step by step. Integration pitfalls and
  error codes are centralized in [PITFALLS.md](PITFALLS.md).

Security note: automated tests do not use real secrets. `mock-secret` is a
placeholder string, not a credential. `secretKey` and `passphrase` must never
appear in frontend responses, logs, or git.

## A. Local Automated Tests

Install dev dependencies and run:

```bash
cd demos/third-party-fastapi
test -d .tmpvenv || python3 -m venv .tmpvenv
source .tmpvenv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
node tests/verify_frontend_workflow_state.js
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
- `tests/verify_frontend_workflow_state.js`
  - Loads the frontend script with a minimal DOM mock.
  - Verifies `Fill Demo Fields` enables only available workflow buttons,
    read-only keys can fill fields but cannot run orders, quote amount edits do
    not require refilling, and structural field edits disable order workflows
    until fields are filled again.

`tests/conftest.py` adds `backend/` to `sys.path`, so running `python -m pytest` from this demo directory is enough.

### Multi-Language Signing Check

`SIGNING.md` includes Python and Node.js snippets. They use the same known-answer vectors as `tests/test_sign.py`.

```bash
node tests/verify_js_sign.js
```

Expected result: the Node.js signatures match the Python baseline and the command exits with code 0.

This only proves the language snippets are algorithmically equivalent. The Python demo has passed real integration; a migrated implementation should still run the real integration checklist below.

## B. Real OAuth Integration Checklist

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
OKX_BASE_URL=https://www.okx.com
APIKEY_PASSPHRASE=<8-32 chars with uppercase, lowercase, number, and special char>
SIMULATED=1
APIKEY_PERM=read_only
AI_BUILDER_CODE=
```

Use `APIKEY_PERM=read_only` for balance-only smoke testing. If you plan to run
the demo order workflows in the same pass, set `APIKEY_PERM=trade` before the
first connect so `/api/connect` creates a trade-permission Fast API Key, and
set `AI_BUILDER_CODE=<AI_BUILDER_CODE>` before order workflow tests. Keep
`OKX_BASE_URL=https://www.okx.com` for this demo checklist.

### TC-1: OAuth Connect

1. [ ] Authorization page opens and shows Fast API permission. If not, check `scope=fast_api`.
2. [ ] Callback returns with `code`; the UI logs `Detected OAuth callback: code=...`.
3. [ ] State validation passes; no `state validation failed` message appears.
4. [ ] Token exchange succeeds; `/api/connect` has no `step=exchange_token` error.
5. [ ] Delete old key is accepted; `code=0` or `59506` are both valid.
6. [ ] New key is created; UI shows masked `apiKey`, `perm` matching
   `APIKEY_PERM`, and `simulated=true`.
7. [ ] No sensitive field is leaked in browser responses or backend logs.

### TC-2: Read-Only Account Query

1. [ ] Use `APIKEY_PERM=read_only` and `SIMULATED=1`.
2. [ ] Connect through OAuth.
3. [ ] Click `Query Balance`.
4. [ ] Balance query succeeds with `code=0` and fields such as `totalEq` and `details[]`.
5. [ ] Click `Fill Demo Fields`.
6. [ ] The helper result shows the current `acctLv` and `posMode`, and fills:
   `Spot instId=BTC-USDT`, `Spot quote amount=10`, `Spot trade mode` from
   account config, `Swap instId=BTC-USDT-SWAP`, `Swap quote amount=10`,
   `Swap open trade mode=cross`, `Swap close margin mode=cross`, and
   `Swap position side=long` in `long_short_mode` or `net` in `net_mode`.
7. [ ] If the connected account supports spot but not swap, spot fields are
   still filled and swap workflows show an unavailable reason.
8. [ ] Order workflow buttons remain disabled because the Fast API Key is read-only.

### TC-3: Simulated Order Attribution

1. [ ] Set `APIKEY_PERM=trade`, keep `SIMULATED=1`, configure `AI_BUILDER_CODE`,
   restart the backend, and reconnect so the old key is deleted and a new
   trade-permission Fast API Key is created.
2. [ ] Click `Fill Demo Fields`.
3. [ ] If the account is in `long_short_mode`, verify the filled swap position
   side is `long`; this demo opens and closes the long-side workflow only.
4. [ ] Optionally adjust `Spot quote amount` or `Swap quote amount`; quote amount
   changes do not require clicking `Fill Demo Fields` again.
5. [ ] If instrument, trade mode, margin mode, or position side is edited, order
   workflow buttons are disabled until `Fill Demo Fields` is clicked again.
6. [ ] Run `Spot Open`, `Spot Close`, `Swap Open`, and `Swap Close`.
7. [ ] Each final OKX order request body contains `tag`.
8. [ ] If the account had no base asset before Spot Open, lower the spot quote
   amount before Spot Close; fees or price movement can make closing the same
   quote notional exceed the available base balance.

For 50116, 50117, 50118, 53018, or signing errors, follow [PITFALLS.md](PITFALLS.md).

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

The demo workflows also use these OKX endpoints and are covered by the real
integration checklist above:

| Purpose | Method | Path |
|---|---|---|
| Market ticker preflight | GET | `/api/v5/market/ticker` |
| Instrument rules preflight | GET | `/api/v5/public/instruments` |
| Account config for swap position mode | GET | `/api/v5/account/config` |
| Swap position verification | GET | `/api/v5/account/positions` |
| Swap close example | POST | `/api/v5/trade/close-position` |
