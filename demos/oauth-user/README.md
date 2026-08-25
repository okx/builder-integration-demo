# oauth-user demo

This demo is for **oauth-user** users: a third-party service runs trading logic on its own server for end users. It uses OKX OAuth Broker + Fast API to create and store a long-lived API Key for each authorized user.

Here **Fast API** means the OKX Fast API product capability, not the Python FastAPI web framework. The reference backend is a small Flask app.

The OAuth/Fast API flow in this demo has been verified in real integration. Keep the backend flow and OKX endpoint constants aligned with the code.

This demo workflow is written and tested for the OKX Global site. Other OKX
sites may have different endpoint availability; use the OpenAPI Markdown docs
as the source of truth before changing the site.

Before migrating this demo into another project, read [PITFALLS.md](PITFALLS.md) for the high-frequency integration issues and error-code checks.

## What this demo shows

- Frontend authorization with OKX Web SDK and `scope=fast_api`
- Callback `state` validation and `domain` allowlist handling
- Backend token exchange, old key deletion, new Fast API Key creation
- Backend-only storage of `secretKey` and `passphrase`
- Signed OpenAPI calls for balance and order examples
- Spot/swap open-close demo workflows
- AI Builder Code injection into OKX order `tag`

Boundary — what it does **not** show:

- No durable storage. Created Fast API Keys live in backend process memory only.
- No user accounts, sessions, authentication, or multi-tenancy beyond one local
  demo browser session.
- Linear swap instruments only. Inverse USD swap instruments such as
  `BTC-USD-SWAP` fail before order placement.
- If the operator trades only their **own** OKX account — even from their own
  server — this is the wrong path. Use [../openapi-user](../openapi-user),
  [../cli-user](../cli-user), or [../mcp-user](../mcp-user).

## How to use

### Run

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
cd demos/oauth-user
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

Default settings are **simulated trading + read-only permission**. User-facing
tests should use real OKX OAuth/Fast API integration with `SIMULATED=1`, not
canned responses. To run the demo order workflows in simulation, set
`APIKEY_PERM=trade` and configure `AI_BUILDER_CODE` in `.env`.

Stop the server with `Ctrl+C`. To leave the local Python environment:

```bash
deactivate
```

Optional cleanup for the local demo environment you created in this folder:

```bash
rm -rf .tmpvenv
```

### Configuration

Read [.env.example](.env.example) first. It intentionally lives in the repo so the user's AI assistant can understand which values are required.

You configure OAuth & Fast API in the AI Builder workbench
(`https://www.okx.com/agent-tradekit/builder` → Settings); after you confirm your
email, OKX sends `CLIENT_ID` and `CLIENT_SECRET` to you **by email**.

Local configuration secrets must go only into `.env` or a real secrets manager:

- `CLIENT_SECRET`
- `APIKEY_PASSPHRASE`

`AI_BUILDER_CODE` is not a secret. The backend sends it as OKX order `tag`.
`AI_BUILDER_CODE` is assigned by OKX when you register as an AI Builder; use the
value you were given and do not make one up. It is 1-16 alphanumeric characters.

### AI Builder Code scope

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

### Verified endpoints

| Purpose | Method | Path |
|---|---|---|
| Exchange code for access token | POST | `/v5/users/oauth/token` |
| Delete existing Fast API Key | POST | `/api/v5/users/oauth/delete-apikey` |
| Create Fast API Key | POST | `/api/v5/users/oauth/apikey` |
| Account balance example | GET | `/api/v5/account/balance` |
| Order example | POST | `/api/v5/trade/order` |
| Swap close example | POST | `/api/v5/trade/close-position` |

Do not change the token path; the demo uses the path verified in real integration.

### Demo order workflows

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

### Files

```text
demos/oauth-user/
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

### Tests

```bash
cd demos/oauth-user
test -d .tmpvenv || python3 -m venv .tmpvenv
source .tmpvenv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
node tests/verify_frontend_workflow_state.js
node tests/verify_js_sign.js
```

See [TESTING.md](TESTING.md) for local automated tests and real integration checks, and [PITFALLS.md](PITFALLS.md) for migration pitfalls and error-code checks.

## Copy vs Adapt

Every file in this folder falls into exactly one bucket.

| File | Bucket | Notes |
|---|---|---|
| `backend/okx_client.py` | **Adapt — you MUST remove the `MOCK` / `_mock_*` test scaffolding before production** | The OAuth + Fast API + signing helpers are the valuable part, but this file also carries a test-only `MOCK=1` environment switch: `_mock_enabled()` short-circuits `exchange_token`, key create/delete, balance, config, positions, ticker, instruments, `place_order`, and `close_position` and returns canned OKX-like responses. Left in place, a stray `MOCK=1` in the environment means orders are **never actually sent** while the API reports success. Delete `_mock_enabled()`, every `_mock_*` helper, and every `if _mock_enabled():` branch before production. Keep `_sign` and `_now_iso_ms` behaviour byte-for-byte. |
| `backend/app.py` | **Adapt — also strip the `MOCK` switch** | Example Flask routes and the demo workflow orchestration. Keep the verified pieces (domain allowlist, delete-before-create, **server-side OAuth `state` validation** in `/api/connect`) and the AI Builder Code gate; replace process-memory session storage, route shapes, and workflow bodies with your own. Do not remove or weaken the `state` check (see "For real integration"). **Delete the `MOCK` scaffolding before production:** the `MOCK` env var (defined near the top), the `if MOCK: return` early-exit that **bypasses the OAuth config validation gate** in `_validate_oauth_config()`, and the `"mock": MOCK` key served in `GET /config`. |
| `frontend/index.html` | **Adapt — also strip the `MOCK` branch** | Example single-page UI and OKX Web SDK wiring. Reuse the authorization call shape and `state` handling; rebuild the UI in your own stack. Never move `client_secret`, `secretKey`, or `passphrase` into it. **Delete the `MOCK` scaffolding:** the `CONFIG.mock` fake-code connect branch (which skips real OAuth) and the `&& !CONFIG.mock` term in the live-order confirm guard — never let a config flag suppress the live-trading confirmation. |
| `tests/test_sign.py` | **Scaffolding (file) — but copy the signing vectors** | Do not copy the test harness wholesale, but **do copy its known-answer signing vectors and prehash-order assertions** into your own signing regression test — they are the regression net on the signing code you adapt. |
| `tests/test_mock_flow.py` | **Demo scaffolding — do NOT copy** | Exercises the `MOCK=1` path that you are removing. |
| `tests/conftest.py` | **Demo scaffolding — do NOT copy** | Wires `sys.path` to this demo's `backend/` directory. |
| `tests/verify_js_sign.js` | **Demo scaffolding — do NOT copy** | Reference only: checks the Node.js snippet in `SIGNING.md` against the Python vectors. |
| `tests/verify_frontend_workflow_state.js` | **Demo scaffolding — do NOT copy** | Reference only: asserts the demo page's button-enable state machine. |
| `requirements.txt`, `requirements-dev.txt` | **Demo scaffolding — do NOT copy** | Demo pins. Use your own project's dependency management. |
| `.env.example` | **Demo scaffolding — do NOT copy** | Shows which configuration fields the demo needs. Production integrations must use a secret manager. |
| `AGENTS.md` | **Demo scaffolding — do NOT copy** | Rules for AI assistants working **inside this repo**. Do not copy it into a user project. |
| `README.md`, `INTEGRATION_GUIDE.md`, `PITFALLS.md`, `SIGNING.md`, `TESTING.md` | **Demo scaffolding — do NOT copy** | Read them, do not vendor them. `PITFALLS.md` and `INTEGRATION_GUIDE.md` are required reading before you adapt the code. |

## For real integration

This demo is a verified simple example, not a production system. Before it
becomes real code:

- **Keep the server-side OAuth `state` check.** This demo validates the CSRF
  `state` **server-side**: `/config` mints it, binds it to an httpOnly
  `oauth_state` cookie, and `/api/connect` verifies the echoed `state` against
  that cookie (via `secrets.compare_digest`) **before** the token exchange, then
  consumes it (single-use). The frontend `localStorage` check is only
  defense-in-depth. When you adapt this: keep state server-side, bind it to the
  user's session, keep it single-use + expiring, and keep the negative tests
  (missing / mismatched / replayed). **Do not** weaken it to a frontend-only
  check — that is bypassable by posting to the token endpoint directly.
  Production hardening beyond this demo: make the cookie tamper-evident (a signed
  Flask session or `state = HMAC(server_secret, nonce)`, so a cookie an attacker
  wrote on a sibling origin can't be adopted), and on HTTPS use a `Secure` +
  `__Host-` cookie prefix.
- **Remove the mock switch — from all three files.** `MOCK` scaffolding lives in
  `backend/okx_client.py` (fakes order acceptance), `backend/app.py` (bypasses the
  OAuth config validation gate + leaks a `mock` flag in `/config`), and
  `frontend/index.html` (skips real OAuth and suppresses the live-order confirm).
  See the Copy vs Adapt notes above for each. A production build must not contain
  any code path that fakes order acceptance or is gated on a `MOCK`/`mock` flag.
- **Fast API Key storage.** This demo intentionally stores the created Fast API
  Key only in backend process memory, keyed by the local demo browser session.
  Restarting the backend clears the demo session and requires connecting again.
  In a real implementation, store each user's created `apiKey`, `secretKey`, and
  `passphrase` on the backend so the service can place future orders for that
  user after authorization. Treat these values as customer-sensitive
  credentials: store them **encrypted and isolated per user**, and keep them out
  of frontend code, prompts, logs, analytics, crash reports, and git.
- **Keep the verified flow intact.** Do not change the token path, the
  delete-before-create sequence, the HMAC signing behaviour, or the domain
  allowlist logic unless you understand the consequence.
- **Keep the safe defaults deliberate.** `SIMULATED=1` and
  `APIKEY_PERM=read_only` are the defaults; moving to live trading and `trade`
  permission is an explicit decision, per authorized user.
- **Keep attribution mandatory.** Order-producing endpoints must require
  `AI_BUILDER_CODE` and send it as OKX request field `tag`. Stop order writes if
  the code is missing. Do not rename the OKX `tag` field.
- **Add what a demo omits**: per-user isolation, durable encrypted storage, key
  rotation, error-code handling, rate limits, retries and idempotency,
  reconciliation, and audit logging.
- **This demo is validated for OKX Global.** For another OKX site, check
  endpoint availability and request schemas first — see
  [../../docs/REFERENCE_LINKS.md](../../docs/REFERENCE_LINKS.md).

Deeper caveats: [PITFALLS.md](PITFALLS.md), [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md),
[SIGNING.md](SIGNING.md), [TESTING.md](TESTING.md).
User type decision tree: [../../docs/USER_TYPES.md](../../docs/USER_TYPES.md).
