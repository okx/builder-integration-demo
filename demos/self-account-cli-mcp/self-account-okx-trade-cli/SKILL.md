---
name: self-account-okx-trade-cli
description: OKX Trade CLI order tool for the user's own OKX account through the local `okx` command. Use when a terminal or coding agent can run supported OKX order-producing commands with AI Builder Code attribution.
---

# OKX Trade CLI Self Account

Use this skill when the user is working through the local OKX Trade CLI `okx` command.

For OKX MCP in ChatGPT, Claude Desktop, or another MCP host, use `self-account-okx-mcp` instead.

## AI Builder Code

For supported order-producing commands, require an AI Builder Code value:

```text
<AI_BUILDER_CODE>
```

The value must be 1-16 alphanumeric characters. This is not an OKX credential.
Pass the current skill's value directly to OKX Trade CLI as
`--aiBuilderCode <AI_BUILDER_CODE>`. OKX records it on the final order for
tracking and attribution. Do not set it only as a shell environment variable:
the CLI reads the command flag, and another skill or terminal session may use a
different AI Builder Code.

## CLI Version And AI Builder Code Check

Before any credential check or order workflow, verify the installed CLI:

```bash
which okx
okx --version
okx spot place --help
okx swap place --help
okx swap close --help
```

Minimum CLI version for this skill:

```text
<OKX_TRADE_CLI_MIN_VERSION_FOR_THIS_SKILL>
```

This version is a placeholder until the OKX Trade CLI release is published.
After the release, replace it with the first CLI version that supports all
features required by these workflows, including `--aiBuilderCode` on the
required order-producing commands.

Use both checks, with different severity:

- Version check is required. Record `okx --version` and compare it with the
  published minimum version.
- AI Builder Code check is a warning check. For the selected workflow, inspect
  whether the target order-producing command's help exposes `--aiBuilderCode`.

If `okx` is missing, stop and ask the user to install OKX Trade CLI. If the
installed CLI is older than the published minimum version, stop before placing
an order and ask the user to upgrade the CLI.

If the selected command help does not expose `--aiBuilderCode`, warn the user
before placing an order. Do not claim that the order will be attributed through
AI Builder Code unless the command accepts the flag. If the user chooses to
continue with that CLI command anyway, do not invent another flag or pass raw
`tag`.

## Demo Order Workflows

Use demo mode for the example workflows:

```bash
okx --demo account balance USDT
```

If the credential check below resolves to API Key mode, replace `--demo` with
the selected demo profile flags, for example `--profile <demo-profile>`. If the
user explicitly asks for live trading, use the selected live profile flags, for
example `--profile <live-profile> --live`, and require explicit confirmation
before any order write.

### Spot Open

Buy a small BTC-USDT spot amount with USDT.

```bash
okx --demo account config --json
okx --demo account balance USDT
okx --demo market ticker BTC-USDT --json
okx --demo market instruments --instType SPOT --instId BTC-USDT --json

okx --demo spot place \
  --instId BTC-USDT \
  --tdMode <SPOT_TD_MODE> \
  --side buy \
  --ordType market \
  --sz <QUOTE_USDT> \
  --tgtCcy quote_ccy \
  --aiBuilderCode <AI_BUILDER_CODE>
```

Set `<QUOTE_USDT>` to a small amount that is above the instrument minimum and
covered by trading-account USDT balance.
Set `<SPOT_TD_MODE>` from account config `acctLv`: use `cash` for account modes
`1` and `2`, and `cross` for account modes `3` and `4`. In account mode `2`,
use `cross` or `isolated` only when the user explicitly intends margin spot.

Verify:

```bash
okx --demo spot fills --instId BTC-USDT
okx --demo account balance BTC
```

### Spot Close

Sell the BTC amount opened by the demo.

```bash
okx --demo account config --json
okx --demo account balance BTC
okx --demo market ticker BTC-USDT --json
okx --demo market instruments --instType SPOT --instId BTC-USDT --json

okx --demo spot place \
  --instId BTC-USDT \
  --tdMode <SPOT_TD_MODE> \
  --side sell \
  --ordType market \
  --sz <VALID_BTC_SIZE> \
  --aiBuilderCode <AI_BUILDER_CODE>
```

Set `<VALID_BTC_SIZE>` to the BTC amount represented by the same small quote
amount used for Spot Open, rounded down to `lotSz` and capped at available BTC.
Do not go below `minSz`. Do not default to selling the user's entire BTC
balance unless the user explicitly asks for a full spot close.
Set `<SPOT_TD_MODE>` from account config `acctLv`: use `cash` for account modes
`1` and `2`, and `cross` for account modes `3` and `4`. In account mode `2`,
use `cross` or `isolated` only when the user explicitly intends margin spot.

### Swap Open

Open a small BTC-USDT-SWAP long in demo trading from a target USDT notional.
Use this workflow for linear swap instruments. Do not reuse it for
inverse USD swap instruments such as `BTC-USD-SWAP`; those instruments have
different sizing and settlement rules.

```bash
okx --demo account config --json
okx --demo account balance USDT
okx --demo market ticker BTC-USDT-SWAP --json
okx --demo market instruments --instType SWAP --instId BTC-USDT-SWAP --json

okx --demo swap place \
  --instId BTC-USDT-SWAP \
  --side buy \
  --ordType market \
  --sz <QUOTE_USDT> \
  --tgtCcy quote_ccy \
  --aiBuilderCode <AI_BUILDER_CODE>
```

If account config returns `acctLv=1`, stop: the account is in spot mode and
this swap workflow is not supported. If account config returns
`posMode=long_short_mode`, add `--posSide long`; otherwise omit `--posSide`.
For swap open in `acctLv=2`, `3`, or `4`, omit `--tdMode` for the OKX Trade CLI
default `cross`. Add `--tdMode isolated` only when the user intends isolated
margin.
Set `<QUOTE_USDT>` to a small target notional, such as `10`, that is covered by
trading-account USDT balance. In this OKX Trade CLI path, `--tgtCcy quote_ccy`
makes `--sz` a USDT notional value; the Trade Kit converts it to a valid contract
count before sending the raw OpenAPI request. Use `ctVal`, ticker price, `minSz`,
and `lotSz` to show the approximate contract count before placing the order.

Verify:

```bash
okx --demo swap positions BTC-USDT-SWAP --json
```

### Swap Close

Close the BTC-USDT-SWAP long opened by the demo.

```bash
okx --demo account config --json
okx --demo swap positions BTC-USDT-SWAP --json

okx --demo swap close \
  --instId BTC-USDT-SWAP \
  --mgnMode <SWAP_MGN_MODE> \
  --autoCxl \
  --aiBuilderCode <AI_BUILDER_CODE>
```

Set `<SWAP_MGN_MODE>` from the position's margin mode, usually `cross` or
`isolated`. If account config returns `acctLv=1`, stop because there should be
no swap position for this workflow. If account config returns
`posMode=long_short_mode`, add `--posSide long`; otherwise omit `--posSide`.

Verify:

```bash
okx --demo swap positions BTC-USDT-SWAP --json
```

Use these as the patterns for supported order-producing CLI commands. For
the broader supported command reference, read
[../../../docs/AI_BUILDER_CODE_SUPPORT_REFERENCE.md](../../../docs/AI_BUILDER_CODE_SUPPORT_REFERENCE.md).
Do not add AI Builder Code to other CLI commands unless the command exposes
`--aiBuilderCode`. Do not invent alternate field names or flag names such as
`--ai-builder-code`.

## Credential And Profile Check

OKX Trade CLI can use either a local API-key profile from `~/.okx/config.toml`
or an OAuth session. Do not ask the user to paste OKX API keys, secret keys,
passphrases, OAuth tokens, or refresh tokens into chat.

Before any authenticated command, run both checks:

```bash
okx config show --json
okx auth status --json
```

Apply the first matching rule:

- If `okx config show --json` has any profile with a non-empty `api_key`, use
  **API Key mode**. Do not start OAuth just because `okx auth status --json`
  is not logged in.
- If there is no API-key profile and `okx auth status --json` returns
  `logged_in`, use **OAuth mode**.
- If there is no API-key profile and OAuth status is `pending`, wait for the
  login to complete before placing orders.
- If there is no API-key profile and OAuth status is `not_logged_in`, ask the
  user for the OKX site, then run:

```bash
okx auth login --manual --site <global|eea|us|tr>
```

Show the verification URL and user code, then continue after the user confirms
authorization.

Mode flags depend on the auth method:

| Auth method | Demo trading | Live trading |
|---|---|---|
| API Key profile | `--profile <demo-profile>` | `--profile <live-profile> --live` |
| OAuth session | `--demo` | no profile flag |

For API Key mode, discover available profile names and their `demo` settings
from `okx config show --json`. If multiple profiles match the requested mode,
ask the user which profile to use. If the selected API-key profile fails with a
401 authentication error, stop and ask the user to fix local CLI configuration;
OAuth login does not override a broken API-key profile.

## Workflow

1. Confirm the user wants the CLI path.
2. Run the CLI version and AI Builder Code check above.
3. If the CLI is missing or older than the published minimum version, ask the
   user before installing or upgrading it.
4. Run the credential and profile check above and choose mode flags.
5. For order-producing commands that expose `--aiBuilderCode`, validate the
   current skill's AI Builder Code and pass it explicitly with
   `--aiBuilderCode`.
6. If the selected CLI command does not expose `--aiBuilderCode`, warn the user
   that this CLI command cannot guarantee AI Builder Code attribution; do not
   pass raw `tag` or any alternate flag.
7. Use demo mode unless the user explicitly requests live trading.
8. Before any order write, summarize the final order parameters and wait for explicit confirmation.
9. After an order write, verify with a read-only CLI command such as orders, fills, or positions.
