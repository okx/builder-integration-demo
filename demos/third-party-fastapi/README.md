# Third-party server + OKX Fast API demo

This demo is for **type 3** users: a third-party service runs trading logic on its own server for end users. It uses OKX OAuth Broker + Fast API to create and store a long-lived API Key for each authorized user.

Here **Fast API** means the OKX Fast API product capability, not the Python FastAPI web framework. The reference backend is a small Flask app.

The OAuth/Fast API flow in this demo has been verified in real integration. Keep the backend flow and OKX endpoint constants aligned with the code.

This demo workflow is written and tested for the OKX Global site. Other OKX
sites may have different endpoint availability; use the OpenAPI Markdown docs
as the source of truth before changing the site.

Before migrating this demo into another project, read [PITFALLS.md](PITFALLS.md) for the high-frequency integration issues and error-code checks.

## What This Demo Shows

- Frontend authorization with OKX Web SDK and `scope=fast_api`
- Callback `state` validation and `domain` allowlist handling
- Backend token exchange, old key deletion, new Fast API Key creation
- Backend-only storage of `secretKey` and `passphrase`
- Signed OpenAPI calls for balance and order examples
- Spot/swap open-close demo workflows
- AI Builder Code injection into OKX order `tag`

## Run

Requires Python 3.10 or newer. The commands below assume `python3` points to
Python 3.10+. Check your Python version before creating the local environment:

```bash
python3 --version
```

If your local environment uses a different Python 3.10+ binary, use that binary
in the `python3 -m venv .tmpvenv` step. The `.tmpvenv` directory is a local
disposable Python environment for this demo and isolates its dependencies from
other local Python projects.

From the repo root:

```bash
cd demos/third-party-fastapi
test -f .env || cp .env.example .env
# Edit .env with OAuth Broker credentials and APIKEY_PASSPHRASE.
test -d .tmpvenv || python3 -m venv .tmpvenv
source .tmpvenv/bin/activate
python -m pip install -r requirements.txt
python backend/app.py
# open http://localhost:8000
```

Check this folder for `.env` and `.tmpvenv`, create only the missing files or
directories shown above, install dependencies inside `.tmpvenv`, and then start
the backend from this folder.

Default settings are **simulated trading + read-only permission**. To run the
demo order workflows in simulation, set `APIKEY_PERM=trade` and configure
`AI_BUILDER_CODE` in `.env`.

Stop the server with `Ctrl+C`. To leave the local Python environment:

```bash
deactivate
```

Optional cleanup for the local demo environment you created in this folder:

```bash
rm -rf .tmpvenv
```

## Configuration

Read [.env.example](.env.example) first. It intentionally lives in the repo so the user's AI assistant can understand which values are required.

Local configuration secrets must go only into `.env` or a real secrets manager:

- `CLIENT_SECRET`
- `APIKEY_PASSPHRASE`

`AI_BUILDER_CODE` is not a secret. The backend sends it as OKX order `tag`.

## Fast API Key Storage

This demo intentionally stores the created Fast API Key only in backend process
memory, keyed by the local demo browser session. Restarting the backend clears
the demo session and requires connecting again.

In a real implementation, store each user's created `apiKey`, `secretKey`, and
`passphrase` on the backend so the service can place future orders for that user
after authorization. Treat these values as customer-sensitive credentials:
protect them from frontend exposure, logs, analytics, crash reports, and git.

## AI Builder Code Scope

This demo injects `AI_BUILDER_CODE` into the OKX `tag` field for its order
examples:

- Local backend routes: `POST /api/order`, `POST /api/spot/open`,
  `POST /api/spot/close`, `POST /api/swap/open`, `POST /api/swap/close`
- OKX endpoints: `POST /api/v5/trade/order`,
  `POST /api/v5/trade/close-position`

The demo workflow routes read market data and account state before placing
orders so the demo can use valid spot and swap sizes. For any additional
order-producing endpoint, first verify the OKX request schema, then add a
demo-specific scope note and tests before passing `tag`.
Use [../../docs/AI_BUILDER_CODE_SUPPORT_REFERENCE.md](../../docs/AI_BUILDER_CODE_SUPPORT_REFERENCE.md)
as the extension reference.
To adapt this demo to another OKX site, check that site's endpoint availability
and request schemas in the OpenAPI Markdown docs first.

The demo creates Fast API Keys with `bindApp=true`, matching the backend code. This requires the Broker IP allowlist to be enabled by OKX.

## Verified Endpoints

| Purpose | Method | Path |
|---|---|---|
| Exchange code for access token | POST | `/v5/users/oauth/token` |
| Delete existing Fast API Key | POST | `/api/v5/users/oauth/delete-apikey` |
| Create Fast API Key | POST | `/api/v5/users/oauth/apikey` |
| Account balance example | GET | `/api/v5/account/balance` |
| Order example | POST | `/api/v5/trade/order` |
| Swap close example | POST | `/api/v5/trade/close-position` |

Do not change the token path; the demo uses the path verified in real integration.

## Demo Order Workflows

After connecting OKX, the page exposes `Fill Demo Fields` plus four order
workflow actions. `Fill Demo Fields` is read-only. The four order workflow
buttons require a Fast API Key created with `APIKEY_PERM=trade` and a configured
`AI_BUILDER_CODE`:

| Button | Local route | OKX order endpoint carrying AI Builder Code |
|---|---|---|
| Spot Open | `POST /api/spot/open` | `POST /api/v5/trade/order` |
| Spot Close | `POST /api/spot/close` | `POST /api/v5/trade/order` |
| Swap Open | `POST /api/swap/open` | `POST /api/v5/trade/order` |
| Swap Close | `POST /api/swap/close` | `POST /api/v5/trade/close-position` |

The `Fill Demo Fields` button calls `GET /api/demo-workflow-fields`, which reads
the connected account's current `account/config` through the backend and fills
the visible manual-test fields. It does not place an order. It can run with a
read-only Fast API Key, but order workflow buttons remain disabled unless the
created key has trade permission and `AI_BUILDER_CODE` is configured. If the
user changes instrument, trade mode, margin mode, or position side after filling
the fields, fill them again before running an order workflow. Changing quote
amount only changes sizing and does not require refilling. If the connected
account supports spot but not swap, the helper still fills spot fields and keeps
swap workflow buttons disabled with an unavailable reason in the helper result.

The frontend sends instrument, sizing, trade-mode, margin-mode, and position-side
inputs for the workflows. For
spot workflows, `quoteAmount` is denominated in the instrument quote currency:
`BTC-USDT` uses USDT, while another spot pair uses that pair's quote currency
for sizing and balance checks. Spot preflight output includes `baseCcy` and
`quoteCcy` so callers do not need to infer currencies from dynamic balance field
names. The backend performs ticker, instrument-rule, account-config, and balance
reads. Spot workflows default `tdMode` from
`acctLv`: `cash` for account modes `1` and `2`, `cross` for account modes `3`
and `4`. The backend rejects spot trade modes that conflict with account mode:
`acctLv=1` requires `cash`, while `acctLv=3` and `4` require `cross`. Swap open
requires a swap-capable account mode (`acctLv=2`, `3`, or `4`) and defaults
`tdMode` to `cross`. Swap workflows also read `posMode` to decide whether to
send `posSide`: in `long_short_mode`, this demo opens and closes the long side;
in `net_mode`, the UI displays `net` and the backend omits `posSide` in the OKX
request. Swap open converts `quoteAmount` to contract count for linear swap
instruments and checks balance with the instrument `settleCcy`. Inverse USD swap
instruments such as `BTC-USD-SWAP` use different sizing and settlement rules and
fail before order placement. The response includes `preflight`, `sent_order`,
and the raw OKX response.

Example request bodies:

```text
POST /api/spot/open
{"instId":"BTC-USDT","quoteAmount":"10"}
{"instId":"BTC-USDT","quoteAmount":"10","tdMode":"cross"}

POST /api/spot/close
{"instId":"BTC-USDT","quoteAmount":"10"}
{"instId":"BTC-USDT","quoteAmount":"10","tdMode":"cross"}

POST /api/swap/open
{"instId":"BTC-USDT-SWAP","quoteAmount":"10"}
{"instId":"BTC-USDT-SWAP","quoteAmount":"10","tdMode":"cross","posSide":"long"}

POST /api/swap/close
{"instId":"BTC-USDT-SWAP","mgnMode":"cross","posSide":"long"}
```

For swap close, use the margin mode and position side of the position being
closed. In `net_mode`, send `posSide=net` or omit `posSide`; the backend omits
the OKX `posSide` request field.

## Files

```text
demos/third-party-fastapi/
+-- README.md
+-- .env.example
+-- INTEGRATION_GUIDE.md
+-- PITFALLS.md
+-- SIGNING.md
+-- TESTING.md
+-- AGENTS.md
+-- backend/
|   +-- app.py
|   +-- okx_client.py
+-- frontend/
|   +-- index.html
+-- tests/
```

## Tests

```bash
cd demos/third-party-fastapi
test -d .tmpvenv || python3 -m venv .tmpvenv
source .tmpvenv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
node tests/verify_frontend_workflow_state.js
node tests/verify_js_sign.js
```

See [TESTING.md](TESTING.md) for local automated tests and real integration checks, and [PITFALLS.md](PITFALLS.md) for migration pitfalls and error-code checks.
