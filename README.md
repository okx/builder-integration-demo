# OKX AI Builder integration demos

This repo covers **four** AI Builder integration paths. Start by choosing the user type, then read only the matching demo.

An AI-installable guide skill named **`okx-ai-builder-integration`** routes users
here; it lives in the public OpenAPI Markdown repo
`https://github.com/okx/ai-builder-openapi-md`. If you arrived through that
skill, this repo is the code side of the same guide. If you arrived here first,
you do not need the skill — the demos are self-contained.

These demos are written and tested for the OKX Global site
(`https://www.okx.com`). For other OKX sites, check endpoint availability and
request schemas in the OpenAPI Markdown docs before adapting the demo.

## Choose Your Path

| User type | Runs where | Whose account | Demo |
|---|---|---|---|
| `openapi-user` | User-controlled machine or server | User's own OKX account | [demos/openapi-user](demos/openapi-user) |
| `cli-user` | Terminal / coding agent running the `okx` command | User's own OKX account | [demos/cli-user](demos/cli-user) |
| `mcp-user` | AI app with OKX connected as an MCP app/connector | User's own OKX account | [demos/mcp-user](demos/mcp-user) |
| `oauth-user` | Third-party service server | End users' OKX accounts | [demos/oauth-user](demos/oauth-user) |

[docs/USER_TYPES.md](docs/USER_TYPES.md) is the authoritative routing table and
full decision tree; the table above is a short index into it. See
[docs/REFERENCE_LINKS.md](docs/REFERENCE_LINKS.md) for external references. For
`oauth-user` implementation work, read the demo README,
`INTEGRATION_GUIDE.md`, and `PITFALLS.md` before editing code.

## AI Builder Code

Supported order-producing paths must attach **AI Builder Code** through the
selected surface's supported attribution field or argument.

- `openapi-user` OpenAPI commands pass AI Builder Code as `--ai-builder-code`.
- `oauth-user` server code reads `AI_BUILDER_CODE` from server environment
  configuration.
- For direct OpenAPI requests, keep the OKX request field name as `tag`.
- For `cli-user`/`mcp-user` paths, use `--aiBuilderCode` or `aiBuilderCode` only
  when the selected command or tool supports it.
- Each demo README and skill defines the support scope for that demo. This repo
  is not a complete reference for every OKX API that supports `tag`.

Details: [docs/AI_BUILDER_CODE.md](docs/AI_BUILDER_CODE.md).
Extension reference: [docs/AI_BUILDER_CODE_SUPPORT_REFERENCE.md](docs/AI_BUILDER_CODE_SUPPORT_REFERENCE.md).
Reference links: [docs/REFERENCE_LINKS.md](docs/REFERENCE_LINKS.md).

## Repo Layout

```text
.
+-- README.md
+-- AGENTS.md
+-- docs/
|   +-- USER_TYPES.md
|   +-- AI_BUILDER_CODE.md
|   +-- AI_BUILDER_CODE_SUPPORT_REFERENCE.md
|   +-- OPENAPI_SIGNING.md
|   +-- REFERENCE_LINKS.md
+-- demos/
    +-- openapi-user/    # self account + local OpenAPI script
    +-- cli-user/        # self account + OKX Trade CLI (okx command)
    +-- mcp-user/        # self account + OKX MCP (app connector)
    +-- oauth-user/      # third-party server + OAuth Broker + Fast API
```

Every demo folder uses the same skeleton: `README.md` is the entry doc, and it
states what the demo shows, how to use it, which files to copy versus adapt, and
what changes for a real integration. The artifact you take into your own project
is code for `openapi-user` and `oauth-user`, and `SKILL.md` for `cli-user` and
`mcp-user`. Read each demo's `Copy vs Adapt` section instead of copying a whole
folder.

`openapi-user` and `oauth-user` keep `.env.example` files in the repo so a user's AI assistant can read the required configuration fields and generate the right local setup.
The `.env` files created from these examples are for demo use only. They contain sensitive configuration fields, so production implementations should keep real values in a secure secret manager or equivalent protected storage.
`cli-user` and `mcp-user` skills do not use a demo `.env` file; pass AI Builder Code directly through the supported CLI flag or MCP tool argument.

## Quick Starts

Self account + OpenAPI script (`openapi-user`):

```bash
cd demos/openapi-user
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

Self account + OKX Trade CLI (`cli-user`) or OKX MCP (`mcp-user`):

```bash
cd demos/cli-user   # or: cd demos/mcp-user
# Read README.md first, then SKILL.md for the surface-specific workflow.
```

Third-party server + Fast API (`oauth-user`):

```bash
cd demos/oauth-user
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
