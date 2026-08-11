# AI Builder user types

Use this document to choose the correct integration path before writing code.
For the external AI Builder integration introduction and other reference links,
see [REFERENCE_LINKS.md](REFERENCE_LINKS.md).

## Type 1: Self Account + Local OpenAPI Script

Use when the user runs strategy code on a machine or server they control and trades only their own OKX account.

- Requires the user's own OKX API Key, secret key, and passphrase.
- Does not require OAuth Broker.
- Does not require Fast API.
- The strategy signs OKX OpenAPI requests directly.
- Every supported order-producing OpenAPI request must set OKX `tag` from the
  command's `--ai-builder-code` value.

If the user owns the OKX account and runs the bot on their laptop, VPS, or internal server, this is still Type 1.

Demo: [../demos/self-account-openapi](../demos/self-account-openapi)

## Type 2: Self Account + OKX Trade CLI/MCP

Use when the user's AI assistant or app calls an OKX-provided execution backend to place orders for the user's own account.

- Supported backends are OKX Trade CLI and OKX MCP.
- OKX Trade CLI can use local API-key profiles or OAuth.
- OKX MCP authorization is handled by the host app or connector.
- Does not require OAuth Broker.
- Does not require Fast API.
- The skill must require an AI Builder Code value for attributed order-producing actions.
- OKX Trade CLI exposes the code through `--aiBuilderCode` on supported order-producing commands.
- OKX MCP exposes the code through `aiBuilderCode` on supported order-producing tools.
- The OKX backend maps AI Builder Code to the final OKX order `tag`.

Demo: [../demos/self-account-cli-mcp](../demos/self-account-cli-mcp)

Skills:

- `self-account-okx-trade-cli`
- `self-account-okx-mcp`

## Type 3: Third-party Server + OKX Fast API/OpenAPI

Use when a third-party service runs trading logic on its own server for end users' OKX accounts.

- Requires OAuth Broker.
- Requires Fast API permission and IP allowlist.
- Users authorize with OKX OAuth.
- The server creates and stores a long-lived Fast API Key per user.
- The server signs OpenAPI requests with that user's key.
- The demo order endpoint must set OKX `tag` to `AI_BUILDER_CODE`.

Do not choose this path merely because a bot runs on a server. If the bot trades only the operator's own OKX account, choose Type 1 or Type 2.

Demo: [../demos/third-party-fastapi](../demos/third-party-fastapi)

## Not Supported In This Phase

- Third-party server + CLI order placement.
- Third-party server + MCP order placement.
