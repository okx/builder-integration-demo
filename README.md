# OKX AI Builder integration demos

This repo keeps its existing name and covers three AI Builder integration paths. Start by choosing the user type, then read only the matching demo.

These demos are written and tested for the OKX Global site
(`https://www.okx.com`). For other OKX sites, check endpoint availability and
request schemas in the OpenAPI Markdown docs before adapting the demo.

## Choose Your Path

| User type | Runs where | Uses whose account | Recommended demo |
|---|---|---|---|
| 1. Self account + local OpenAPI script | User-controlled machine or server | User's own OKX account | [demos/self-account-openapi](demos/self-account-openapi) |
| 2. Self account + OKX Trade CLI/MCP | User machine or AI app | User's own OKX account | [demos/self-account-cli-mcp](demos/self-account-cli-mcp) |
| 3. Third-party server + OKX Fast API/OpenAPI | Third-party service server | End users' OKX accounts | [demos/third-party-fastapi](demos/third-party-fastapi) |

See [docs/USER_TYPES.md](docs/USER_TYPES.md) for the full decision tree. See
[docs/REFERENCE_LINKS.md](docs/REFERENCE_LINKS.md) for external references. For
Type 3 implementation work, read the demo README,
`INTEGRATION_GUIDE.md`, and `PITFALLS.md` before editing code.

## AI Builder Code

Supported order-producing paths must attach **AI Builder Code** through the
selected surface's supported attribution field or argument.

- Type 1 OpenAPI commands pass AI Builder Code as `--ai-builder-code`.
- Type 3 server code reads `AI_BUILDER_CODE` from server environment
  configuration.
- For direct OpenAPI requests, keep the OKX request field name as `tag`.
- For OKX Trade CLI/MCP paths, use `--aiBuilderCode` or `aiBuilderCode` only
  when the selected command or tool supports it.
- Each demo README and skill defines the support scope for that demo. This repo
  is not a complete reference for every OKX API that supports `tag`.

Details: [docs/AI_BUILDER_CODE.md](docs/AI_BUILDER_CODE.md).
Extension reference: [docs/AI_BUILDER_CODE_SUPPORT_REFERENCE.md](docs/AI_BUILDER_CODE_SUPPORT_REFERENCE.md).
Reference links: [docs/REFERENCE_LINKS.md](docs/REFERENCE_LINKS.md).

## Repo Layout

```text
okx-fastapi-broker-demo/
+-- README.md
+-- AGENTS.md
+-- docs/
|   +-- USER_TYPES.md
|   +-- AI_BUILDER_CODE.md
|   +-- AI_BUILDER_CODE_SUPPORT_REFERENCE.md
|   +-- OPENAPI_SIGNING.md
|   +-- REFERENCE_LINKS.md
+-- demos/
    +-- self-account-openapi/
    +-- self-account-cli-mcp/
    |   +-- self-account-okx-trade-cli/
    |   +-- self-account-okx-mcp/
    +-- third-party-fastapi/
```

Type 1 and Type 3 keep `.env.example` files in the repo so a user's AI assistant can read the required configuration fields and generate the right local setup.
The `.env` files created from these examples are for demo use only. They contain sensitive configuration fields, so production implementations should keep real values in a secure secret manager or equivalent protected storage.
Type 2 CLI/MCP skills do not use a demo `.env` file; pass AI Builder Code directly through the supported CLI flag or MCP tool argument.

## Quick Starts

Self account + OpenAPI script:

```bash
cd demos/self-account-openapi
test -f .env || cp .env.example .env
# Edit .env with OKX demo trading credentials.
test -d .tmpvenv || python3 -m venv .tmpvenv
source .tmpvenv/bin/activate
python -m pip install -r requirements.txt
python strategy_demo.py balance
python strategy_demo.py spot-open --inst-id BTC-USDT --quote-amount 10 --ai-builder-code <AI_BUILDER_CODE>
python strategy_demo.py spot-close --inst-id BTC-USDT --quote-amount 10 --ai-builder-code <AI_BUILDER_CODE>
python strategy_demo.py swap-open --inst-id BTC-USDT-SWAP --quote-amount 10 --ai-builder-code <AI_BUILDER_CODE>
python strategy_demo.py swap-close --inst-id BTC-USDT-SWAP --mgn-mode cross --ai-builder-code <AI_BUILDER_CODE>
```

Self account + OKX Trade CLI/MCP skills:

```bash
cd demos/self-account-cli-mcp
# Read README.md, then choose self-account-okx-trade-cli or self-account-okx-mcp.
```

Third-party server + Fast API:

```bash
cd demos/third-party-fastapi
test -f .env || cp .env.example .env
# Edit .env with OAuth Broker credentials, passphrase, and AI_BUILDER_CODE if placing orders.
test -d .tmpvenv || python3 -m venv .tmpvenv
source .tmpvenv/bin/activate
python -m pip install -r requirements.txt
python backend/app.py
```

After connecting through the browser, fill the spot/swap instrument and quote
amount fields, then use the four demo workflow buttons: Spot Open, Spot Close,
Swap Open, and Swap Close.
