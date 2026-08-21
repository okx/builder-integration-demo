# Self Account + OKX Trade CLI/MCP Demo

This demo is for **type 2** users: the user trades their own OKX account through an OKX-provided execution backend.

The example workflows in this folder are written for the OKX Global site. For
other OKX sites, check the selected CLI or MCP surface plus the OpenAPI
Markdown docs before adapting the workflow.

Supported backends:

- **OKX Trade CLI**: local terminal/coding-agent workflows using the `okx` command.
- **OKX MCP**: ChatGPT app, Claude Desktop, or another app where OKX is connected as a custom MCP app/connector.

OKX Trade CLI can use a local API-key profile from `~/.okx/config.toml` or an
OAuth session. OKX MCP authorization is handled by the host app or connector.

## Files

- [self-account-okx-trade-cli/SKILL.md](self-account-okx-trade-cli/SKILL.md): use for local terminal/coding-agent workflows with `okx`.
- [self-account-okx-mcp/SKILL.md](self-account-okx-mcp/SKILL.md): use for ChatGPT app, Claude Desktop, or another app-connected OKX MCP workflow.

Do not store OAuth tokens or OKX account credentials in this folder. OKX Trade
CLI and OKX MCP use their own authorization flows and storage.

## Choose A Skill

| User surface | Skill |
|---|---|
| Terminal or coding agent can run `okx` commands | `self-account-okx-trade-cli` |
| ChatGPT app, Claude Desktop, or app-connected MCP | `self-account-okx-mcp` |

## AI Builder Code

AI Builder Code is an attribution value, not an OKX credential. Use 1-16 alphanumeric characters.

OKX records AI Builder Code on the final order when the selected backend supports it.

CLI and MCP support scopes are independent. Check the selected skill before
running a command or tool. For CLI, use the minimum CLI version required by the
skill. If the installed command does not expose `--aiBuilderCode`, warn the user
before placing an order and do not claim AI Builder Code attribution.

### OKX Trade CLI

Before authenticated CLI commands, run both `okx config show --json` and
`okx auth status --json`. Use API-key profiles first when configured; only use
OAuth when no API-key profile is available.

Pass AI Builder Code as `--aiBuilderCode` only on supported order-producing CLI
commands. The CLI skill includes spot/swap open-close demo workflows that show
where to place the flag.

The CLI skill starts with a version check and an AI Builder Code warning check:
record `okx --version`, compare it with the skill's minimum supported CLI
version, and inspect whether the selected order-producing command help exposes
`--aiBuilderCode`. The minimum supported CLI version is `1.4.4`.

Do not rely on setting `AI_BUILDER_CODE` only as a shell environment variable.
The final `okx` command must include the value as
`--aiBuilderCode <AI_BUILDER_CODE>`.

Do not assume other CLI commands accept AI Builder Code unless the selected
skill and installed CLI help/schema show `--aiBuilderCode`.

### OKX MCP

Pass AI Builder Code as the MCP tool argument `aiBuilderCode` on supported
order-producing tools. The MCP skill includes spot/swap open-close demo
workflows that show where to place the argument. Do not pass raw `tag` from
this demo path.

If the selected backend command or tool cannot accept AI Builder Code, use a
supported command/tool or switch to the self-account OpenAPI demo for
caller-provided attribution.

For extension candidates beyond these skills, read
[../../docs/AI_BUILDER_CODE_SUPPORT_REFERENCE.md](../../docs/AI_BUILDER_CODE_SUPPORT_REFERENCE.md).
For Agent Trade Kit installation and CLI source references, read
[../../docs/REFERENCE_LINKS.md](../../docs/REFERENCE_LINKS.md).
