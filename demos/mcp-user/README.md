# mcp-user demo

This demo is for **mcp-user** users: the user's AI app calls **OKX MCP**
(ChatGPT app, Claude Desktop, or another app where OKX is connected as a custom
MCP app/connector) to place orders for the user's **own** OKX account.

The artifact of this demo is a single file, [SKILL.md](SKILL.md). It is an
agent-readable skill that tells an AI assistant how to call OKX MCP order tools
safely and with AI Builder Code attribution.

## What this demo shows

- Calling OKX MCP order-producing tools with `simulatedTrading: true` for the
  example workflows.
- Read-only preflight before every order: `account_get_config`,
  `account_get_balance`, `market_get_ticker`, `market_get_instruments`.
- Four verified demo order workflows: Spot Open, Spot Close, Swap Open, and
  Swap Close, with post-order verification through read-only tools.
- Passing AI Builder Code through the MCP tool argument `aiBuilderCode` on
  supported order-producing tools.
- Deriving `tdMode`, `posSide`, and sizes from live account config and
  instrument rules instead of hardcoded values.
- A mandatory connect gate before any workflow: the first read-only
  `account_get_config` preflight doubles as the check that OKX is connected and
  authorized in the host app.

Boundary — what it does **not** show:

- It does not handle authorization. The MCP host app or connector owns that.
  The skill never asks for API keys, secret keys, passphrases, or tokens.
- It does not implement OKX OpenAPI signing. For direct signed requests, use
  [../openapi-user](../openapi-user).
- It does not use OAuth Broker or Fast API. A third-party service trading
  **end users'** accounts belongs in [../oauth-user](../oauth-user).
- It covers BTC-USDT spot and linear BTC-USDT-SWAP only. Inverse USD swap
  instruments such as `BTC-USD-SWAP` are out of scope.
- It is not a complete list of every MCP tool that accepts `aiBuilderCode`. See
  [../../docs/AI_BUILDER_CODE_SUPPORT_REFERENCE.md](../../docs/AI_BUILDER_CODE_SUPPORT_REFERENCE.md).

## How to use

1. Connect OKX as an MCP app/connector in your AI app. See the Agent Trade Kit
   install guide in
   [../../docs/REFERENCE_LINKS.md](../../docs/REFERENCE_LINKS.md).
2. Read [SKILL.md](SKILL.md) — it is the demo. Give it to your AI assistant, or
   install it as a skill in your agent environment.
3. Replace the `<AI_BUILDER_CODE>` placeholder with the AI Builder Code OKX
   assigned to you. It is 1-16 alphanumeric characters and is not a secret.
4. Run the four demo workflows with `simulatedTrading: true` first, then decide
   whether to move to live trading.

```bash
cd demos/mcp-user
# Read SKILL.md for the full surface-specific workflow.
```

Authorization is handled entirely by the host app — see the connect gate in
[SKILL.md](SKILL.md) (`## Authorization and connect gate`). Do not ask for
credentials in chat.

## Copy vs Adapt

| File | Bucket | Notes |
|---|---|---|
| `SKILL.md` | **Adapt (take it, then fix 3 things)** | This is the artifact to take into your own project or agent skill directory. Your agent uses it to call OKX MCP tools. Before use you MUST (1) fill the placeholders below, (2) rewrite its relative links (`../…`, `../../docs/…`) to absolute repo URLs since they dangle once copied out of the repo, and (3) rename its frontmatter `name` to something unambiguous in your environment (the bare `mcp-user` collides easily). |
| `README.md` | **Demo scaffolding — do NOT copy** | Entry doc for this repo only. |

Placeholders you must replace in `SKILL.md` before use:

- `<AI_BUILDER_CODE>` — your real AI Builder Code assigned by OKX. Do not make
  one up, and do not leave the placeholder in a skill that places orders.

Do not rename the `aiBuilderCode` tool argument, and do not substitute
`--aiBuilderCode`, `--ai-builder-code`, or a raw `tag` argument on this surface.
Those are different surfaces' field names.

## For real integration

- **Attribution scope is per tool.** Pass `aiBuilderCode` only to
  order-producing tools whose schema exposes it. Do not add it to cancel,
  amend, query, read, leverage, stop, earn, lending, DCD, transfer, or
  configuration tools.
- **Connect gate is mandatory.** Keep the read-only `account_get_config` connect
  check before any workflow; an adapted skill must not place an order without
  confirming OKX is connected and authorized in the host.
- **`simulatedTrading` is the safety switch.** The demo workflows set it to
  `true`. Removing it means real funds; require explicit user confirmation
  before every live order write.
- **Never hardcode prices or sizes.** Real integrations must keep the preflight
  reads and honour `lotSz`, `minSz`, and `ctVal` from live instrument rules.
- **This demo is validated for OKX Global.** For another OKX site, confirm tool
  and endpoint availability first — see
  [../../docs/REFERENCE_LINKS.md](../../docs/REFERENCE_LINKS.md).
- **Tool schemas change.** If the connected MCP server's schema disagrees with
  `SKILL.md`, trust the live schema and treat the skill as out of date.

User type decision tree: [../../docs/USER_TYPES.md](../../docs/USER_TYPES.md).
