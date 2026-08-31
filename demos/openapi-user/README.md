# openapi-user demo

This demo is for **openapi-user** users: the user runs strategy code on a machine or server they control and trades only their own OKX account.

It does not use OAuth Broker or Fast API. The user's own API Key stays local.

This demo workflow is written and tested for the OKX Global site. Other OKX
sites may have different endpoint availability; use the OpenAPI Markdown docs
as the source of truth before changing the site.

## What this demo shows

- OKX OpenAPI HMAC signing done correctly, including the demo-trading header
  `x-simulated-trading: 1`.
- Demo/live profile selection from `.env`, with a hard gate
  (`--confirm-live-order`) on every live order write.
- Four verified order workflows — Spot Open, Spot Close, Swap Open, Swap
  Close — that read ticker, instrument rules, account config, and balances
  before sizing an order.
- AI Builder Code attribution: the `--ai-builder-code` value is sent as OKX
  request field `tag`, and order writes are refused without it.

Boundary — what it does **not** show:

- No OAuth Broker, no Fast API, no end-user accounts. A third-party service
  trading **end users'** accounts belongs in [../oauth-user](../oauth-user).
- No `okx` CLI and no MCP. Those surfaces are
  [../cli-user](../cli-user) and [../mcp-user](../mcp-user).
- Linear swap instruments only. Inverse USD swap instruments such as
  `BTC-USD-SWAP` use different sizing and settlement rules and fail before
  order placement.
- Not a complete OKX API client: it implements the handful of endpoints these
  workflows need, not every endpoint that supports `tag`.
- No persistence, retry, rate-limit handling, position tracking, or risk
  management. This is a single-shot demo script.

## How to use

### Run with OKX demo trading

```bash
cd demos/openapi-user
test -f .env || cp .env.example .env
test -d .tmpvenv || python3 -m venv .tmpvenv
source .tmpvenv/bin/activate
python -m pip install -r requirements.txt
```

Fill the demo trading credentials in `.env`:

```env
OKX_PROFILE=demo
OKX_DEMO_API_KEY=...
OKX_DEMO_SECRET_KEY=...
OKX_DEMO_PASSPHRASE=...
```

Then run:

```bash
python strategy_demo.py balance
python strategy_demo.py spot-open --inst-id BTC-USDT --quote-amount 10 --ai-builder-code <AI_BUILDER_CODE>
python strategy_demo.py spot-close --inst-id BTC-USDT --quote-amount 10 --ai-builder-code <AI_BUILDER_CODE>
python strategy_demo.py swap-open --inst-id BTC-USDT-SWAP --quote-amount 10 --ai-builder-code <AI_BUILDER_CODE>
python strategy_demo.py swap-close --inst-id BTC-USDT-SWAP --mgn-mode cross --ai-builder-code <AI_BUILDER_CODE>
```

`OKX_PROFILE=demo` sends real OKX demo trading requests and automatically adds `x-simulated-trading: 1`, so it does not trade with real funds.

Demo trading uses the **same host as live** (`https://www.okx.com` by default; override via `OKX_SITE` / `OKX_API_BASE_URL`), switched only by the `x-simulated-trading: 1` header — there is no separate "simulated host". OKX also documents the Global REST host as `openapi.okx.com`; both work for Global. Change the base host only for your registered site (e.g. US/AU → `us.okx.com`, EU → `eea.okx.com`; supported sites are selected via `OKX_SITE`), not because a docs page shows a different host.

### Demo order workflows

The four workflow commands use public ticker and instrument rules before
placing orders. They compute valid demo sizes instead of relying on hardcoded
price or size values.

| Command | Action | OKX endpoint carrying AI Builder Code |
|---|---|---|
| `python strategy_demo.py spot-open --inst-id BTC-USDT --quote-amount 10 --ai-builder-code <AI_BUILDER_CODE>` | Buy a small BTC-USDT spot amount with USDT | `POST /api/v5/trade/order` |
| `python strategy_demo.py spot-close --inst-id BTC-USDT --quote-amount 10 --ai-builder-code <AI_BUILDER_CODE>` | Sell a small BTC-USDT spot amount | `POST /api/v5/trade/order` |
| `python strategy_demo.py swap-open --inst-id BTC-USDT-SWAP --quote-amount 10 --ai-builder-code <AI_BUILDER_CODE>` | Open a small BTC-USDT-SWAP long from a target settlement-currency notional | `POST /api/v5/trade/order` |
| `python strategy_demo.py swap-close --inst-id BTC-USDT-SWAP --mgn-mode cross --ai-builder-code <AI_BUILDER_CODE>` | Close the BTC-USDT-SWAP position | `POST /api/v5/trade/close-position` |

Each order-producing workflow requires `--ai-builder-code` and sends that value
as OKX request field `tag`. The command output includes `preflight`,
`sent_order`, and the raw OKX response so a user or AI assistant can inspect
what was sent. The demo passes the AI Builder Code as an explicit
`--ai-builder-code` argument rather than reading it from an environment variable,
because an env var can be overridden by the deployment environment and silently
attribute orders to the wrong value. When you adapt this you may source the value
however you like (hard-coded, config, or env), but a missing or invalid value
must fail loudly — never default silently.
For spot workflows, `--quote-amount` is denominated in the instrument quote
currency: `BTC-USDT` uses USDT, while another spot pair uses that pair's quote
currency for sizing and balance checks. Spot preflight output includes
`baseCcy` and `quoteCcy` so callers do not need to infer currencies from dynamic
balance field names.

Useful options:

```bash
python strategy_demo.py spot-open --inst-id BTC-USDT --quote-amount 10 --ai-builder-code <AI_BUILDER_CODE>
python strategy_demo.py spot-open --inst-id BTC-USDT --quote-amount 10 --td-mode cross --ai-builder-code <AI_BUILDER_CODE>
python strategy_demo.py spot-close --inst-id BTC-USDT --quote-amount 10 --ai-builder-code <AI_BUILDER_CODE>
python strategy_demo.py spot-close --inst-id BTC-USDT --base-size 0.0001 --ai-builder-code <AI_BUILDER_CODE>
python strategy_demo.py swap-open --inst-id BTC-USDT-SWAP --quote-amount 10 --ai-builder-code <AI_BUILDER_CODE>
python strategy_demo.py swap-open --inst-id BTC-USDT-SWAP --contracts 0.01 --ai-builder-code <AI_BUILDER_CODE>
python strategy_demo.py swap-open --inst-id BTC-USDT-SWAP --quote-amount 10 --td-mode isolated --ai-builder-code <AI_BUILDER_CODE>
python strategy_demo.py swap-close --inst-id BTC-USDT-SWAP --mgn-mode cross --no-auto-cxl --ai-builder-code <AI_BUILDER_CODE>
```

Spot workflows read account config and choose the default `--td-mode` from
`acctLv`: `cash` for account modes `1` and `2`, `cross` for account modes `3`
and `4`. The workflow rejects spot trade modes that conflict with account mode:
`acctLv=1` requires `cash`, while `acctLv=3` and `4` require `cross`. For
`acctLv=2`, pass `--td-mode cross` or `--td-mode isolated` only when the user
intentionally uses margin spot.
`swap-open` reads account config, requires a swap-capable account mode
(`acctLv=2`, `3`, or `4`), and defaults `--td-mode` to `cross`; pass
`--td-mode isolated` only when the user intends isolated margin. `swap-open`
only sends `posSide=long` when `posMode=long_short_mode`. `swap-close` still
requires `--mgn-mode` because OKX `close-position` requires `mgnMode`.
For `swap-open`, `--quote-amount` is converted to a contract count with current
ticker price and `ctVal`; balance checks use the swap instrument `settleCcy`.
The current demo supports linear swap instruments only. Inverse USD swap
instruments such as `BTC-USD-SWAP` use different sizing and settlement rules and
fail before order placement. `--contracts` is an advanced override when the
caller wants an exact contract count.

### Run with live trading

1. Create `.env` with `test -f .env || cp .env.example .env`.
2. Fill `OKX_LIVE_API_KEY`, `OKX_LIVE_SECRET_KEY`, and `OKX_LIVE_PASSPHRASE`.
3. Set `OKX_PROFILE=live`.

```bash
python strategy_demo.py balance --ccy USDT
python strategy_demo.py spot-open --inst-id BTC-USDT --quote-amount 10 --ai-builder-code <AI_BUILDER_CODE> --confirm-live-order
python strategy_demo.py spot-close --inst-id BTC-USDT --quote-amount 10 --ai-builder-code <AI_BUILDER_CODE> --confirm-live-order
python strategy_demo.py swap-open --inst-id BTC-USDT-SWAP --quote-amount 10 --ai-builder-code <AI_BUILDER_CODE> --confirm-live-order
python strategy_demo.py swap-close --inst-id BTC-USDT-SWAP --mgn-mode cross --ai-builder-code <AI_BUILDER_CODE> --confirm-live-order
```

Live orders use the live API key and do not send the simulated trading header.
Every live order-producing command requires `--confirm-live-order`.
Run the demo sequence first with the same instruments and quote amounts. If you
open swap with `--td-mode isolated`, close it with `--mgn-mode isolated`.

### Order fields

The order command maps to `POST /api/v5/trade/order`. The minimal demo order uses:

- `instId`
- `tdMode`
- `side`
- `ordType`
- `sz`
- `px` for non-market orders
- `tag`, populated from `--ai-builder-code`

Optional fields aligned with OKX Trade MCP spot order placement are also exposed:

- `tgtCcy`
- `clOrdId`
- `tpTriggerPx`, `tpOrdPx`, `tpOrdKind`, `tpTriggerPxType`
- `slTriggerPx`, `slOrdPx`, `slTriggerPxType`
- `stpMode`
- `tradeQuoteCcy`
- `banAmend`
- `pxAmendType`
- `posSide`
- `reduceOnly`

Example with attached TP/SL:

```bash
python strategy_demo.py order --inst-id BTC-USDT --side buy --ord-type limit --px 60000 --sz 0.001 --ai-builder-code <AI_BUILDER_CODE> \
  --tp-trigger-px 70000 --tp-ord-px -1 --sl-trigger-px 55000 --sl-ord-px -1
```

### Tests

```bash
cd demos/openapi-user
test -d .tmpvenv || python3 -m venv .tmpvenv
source .tmpvenv/bin/activate
python -m pip install -r requirements.txt
python3 -m unittest test_strategy_demo.py
```

The tests cover demo/live profile selection, AI Builder Code validation, simulated trading headers, order body fields, and known-answer OpenAPI signing vectors.

See [TESTING.md](TESTING.md) for the two test layers and the real demo-trading integration checklist.

## Copy vs Adapt

Every file in this folder falls into exactly one bucket.

| File | Bucket | Notes |
|---|---|---|
| `okx_openapi_client.py` | **Copy verbatim** | The signing client. Take it into your project unchanged — do not re-implement HMAC signing by hand. **Note: its public functions default to `simulated=True`; pass `simulated=False` for production.** Keep the OKX request field name `tag`. |
| `strategy_demo.py` | **Adapt** | Example CLI and strategy logic. Keep the safety gates (AI Builder Code validation, `--confirm-live-order`, preflight reads, account-mode checks) and replace the workflow bodies with your own strategy. |
| `test_strategy_demo.py` | **Scaffolding (file) — but copy the signing vectors** | Do not copy the test harness wholesale, but **do copy its known-answer signing vectors** (`test_known_answer_signing_vectors`) and the "signature is computed over the body actually sent" assertion into your own signing regression test — they are the only regression net on the signing client you copied verbatim. |
| `.env.example` | **Demo scaffolding — do NOT copy** | Shows which configuration fields the demo needs. Production integrations should read credentials from a secret manager, not a `.env` file. |
| `requirements.txt` | **Demo scaffolding — do NOT copy** | Demo pins (`requests`, `python-dotenv`). Use your own project's dependency management. |
| `README.md` | **Demo scaffolding — do NOT copy** | Entry doc for this repo only. |
| `TESTING.md` | **Demo scaffolding — do NOT copy** | Local automated tests + the real demo-trading integration checklist. |

## For real integration

This demo is a verified simple example, not a production system. Before it
becomes real code:

- **Switch off the simulated default.** `okx_openapi_client.py` defaults
  `simulated=True` on every public function. Production callers must pass
  `simulated=False` explicitly, and must use a live API key.
- **Keep secrets out of the process.** Do not commit `.env`. Do not put API
  secrets into frontend code or logs. Use separate OKX API keys for demo
  trading and live trading, and move real values into a secret manager.
- **AI Builder Code** is assigned by OKX when you register as an AI Builder; use
  the value you were given and do not make one up. Format: 1-16 alphanumeric
  characters; it is not a secret.
- **Keep attribution mandatory.** This demo's order-producing commands must
  require `--ai-builder-code` and send that value as OKX `tag` on
  `POST /api/v5/trade/order` and `POST /api/v5/trade/close-position`. The OKX
  field name is `tag`; do not rename it to `ai_builder_code`.
- **Add what a demo omits**: error-code handling, rate limits, retries and
  idempotency (`clOrdId`), order-state reconciliation, and position/risk
  management.
- To extend this demo to another OpenAPI endpoint, read
  [../../docs/AI_BUILDER_CODE_SUPPORT_REFERENCE.md](../../docs/AI_BUILDER_CODE_SUPPORT_REFERENCE.md).
- To adapt this demo to another OKX site, check that site's endpoint
  availability and request schemas in the OpenAPI Markdown docs first.

Signing notes: [../../docs/OPENAPI_SIGNING.md](../../docs/OPENAPI_SIGNING.md).
External OpenAPI references: [../../docs/REFERENCE_LINKS.md](../../docs/REFERENCE_LINKS.md).
User type decision tree: [../../docs/USER_TYPES.md](../../docs/USER_TYPES.md).
