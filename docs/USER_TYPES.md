# AI Builder user types

This document is the authoritative routing table and full decision tree for
user-type selection.

Use this document to choose the correct integration path before writing code.
There are **four** user types, each with its own demo folder under `demos/`.
For the external AI Builder integration introduction and other reference links,
see [REFERENCE_LINKS.md](REFERENCE_LINKS.md).

| User type | Use when | Whose account | Demo |
|---|---|---|---|
| `openapi-user` | Strategy code runs on a machine/server the user controls and signs OKX OpenAPI requests directly | User's own OKX account | [../demos/openapi-user](../demos/openapi-user) |
| `cli-user` | The user drives trading through the **OKX Trade CLI** (`okx` command) in a terminal or coding agent | User's own OKX account | [../demos/cli-user](../demos/cli-user) |
| `mcp-user` | The user drives trading through **OKX MCP** (ChatGPT app, Claude Desktop, or another app-connected MCP) | User's own OKX account | [../demos/mcp-user](../demos/mcp-user) |
| `oauth-user` | A third-party service runs trading logic on its own server for end users, via OAuth Broker + Fast API | End users' OKX accounts | [../demos/oauth-user](../demos/oauth-user) |

## openapi-user — Self Account + Local OpenAPI Script

Use when the user runs strategy code on a machine or server they control and trades only their own OKX account.

- Requires the user's own OKX API Key, secret key, and passphrase.
- Does not require OAuth Broker.
- Does not require Fast API.
- The strategy signs OKX OpenAPI requests directly.
- Every supported order-producing OpenAPI request must set OKX `tag` from the
  command's `--ai-builder-code` value.

If the user owns the OKX account and runs the bot on their laptop, VPS, or internal server, this is still `openapi-user`.

Demo: [../demos/openapi-user](../demos/openapi-user)

## cli-user — Self Account + OKX Trade CLI

Use when the user's assistant or workflow places orders for the user's own
account through the **OKX Trade CLI** — the `okx` command run in a terminal or by
a coding agent.

- OKX Trade CLI can use a local API-key profile (`~/.okx/config.toml`) or an OAuth session.
- Does not require OAuth Broker. Does not require Fast API.
- The skill must require an AI Builder Code value for attributed order-producing actions.
- OKX Trade CLI exposes the code through `--aiBuilderCode` on supported order-producing commands.
- The OKX backend maps AI Builder Code to the final OKX order `tag`.

Demo: [../demos/cli-user](../demos/cli-user)

## mcp-user — Self Account + OKX MCP

Use when the user's AI app calls **OKX MCP** (ChatGPT app, Claude Desktop, or
another app where OKX is connected as a custom MCP app/connector) to place orders
for the user's own account.

- OKX MCP authorization is handled by the host app or connector.
- Does not require OAuth Broker. Does not require Fast API.
- The skill must require an AI Builder Code value for attributed order-producing actions.
- OKX MCP exposes the code through `aiBuilderCode` on supported order-producing tools.
- The OKX backend maps AI Builder Code to the final OKX order `tag`.

Demo: [../demos/mcp-user](../demos/mcp-user)

## oauth-user — Third-party Server + OKX Fast API/OpenAPI

Use when a third-party service runs trading logic on its own server for end users' OKX accounts.

- Requires OAuth Broker.
- Requires Fast API permission and IP allowlist.
- Users authorize with OKX OAuth.
- The server creates and stores a long-lived Fast API Key per user.
- The server signs OpenAPI requests with that user's key.
- The demo order endpoint must set OKX `tag` to `AI_BUILDER_CODE`.

Do not choose this path merely because a bot runs on a server. If the bot trades only the operator's own OKX account, choose `openapi-user`, `cli-user`, or `mcp-user`.

Demo: [../demos/oauth-user](../demos/oauth-user)

## Not Supported In This Phase

- Third-party server + CLI order placement.
- Third-party server + MCP order placement.
