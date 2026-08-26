---
name: mcp-user
description: OKX MCP order placement tool for the user's own OKX account in ChatGPT, Claude Desktop, or another MCP-capable app. Use supported OKX MCP order-producing tools with AI Builder Code attribution through the `aiBuilderCode` tool argument.
---

# OKX MCP Self Account

Use this skill when the user is working through OKX MCP in the selected app.

For local terminal use with the `okx` command, use the `cli-user` skill
([../cli-user/SKILL.md](../cli-user/SKILL.md)) instead.

## AI Builder Code

For supported order-producing MCP tools, require an AI Builder Code value:

```text
<AI_BUILDER_CODE>
```

The value must be 1-16 alphanumeric characters. This is not an OKX credential.
Pass it as the MCP tool argument `aiBuilderCode`. OKX records it on the final
order for tracking and attribution.

Pass `aiBuilderCode` only to supported OKX MCP order-producing tools.

## Authorization and connect gate

OKX authorization is handled by the MCP host app. Do not ask for OKX API keys,
secret keys, passphrases, OAuth tokens, or refresh tokens.

Before running any workflow, confirm OKX is connected. The first read-only
preflight in each workflow (`account_get_config` with `{"simulatedTrading":
true}`) is also the connect check: if it is unavailable or returns a
missing/expired-authorization error, stop and ask the user to connect or
reauthorize OKX in the app before continuing.

## Demo Order Workflows

Use `simulatedTrading: true` for the example workflows. Read market data and
instrument rules before placing orders; do not use hardcoded price or size
values for order acceptance.

### Spot Open

Buy a small BTC-USDT spot amount with USDT.

Read-only preflight:

```json
[
  {"tool": "account_get_config", "arguments": {"simulatedTrading": true}},
  {"tool": "account_get_balance", "arguments": {"ccy": "USDT", "simulatedTrading": true}},
  {"tool": "market_get_ticker", "arguments": {"instId": "BTC-USDT"}},
  {"tool": "market_get_instruments", "arguments": {"instType": "SPOT", "instId": "BTC-USDT"}}
]
```

Order tool call:

```json
{
  "tool": "spot_place_order",
  "arguments": {
    "instId": "BTC-USDT",
    "tdMode": "<SPOT_TD_MODE>",
    "side": "buy",
    "ordType": "market",
    "sz": "<QUOTE_USDT>",
    "tgtCcy": "quote_ccy",
    "aiBuilderCode": "<AI_BUILDER_CODE>",
    "simulatedTrading": true
  }
}
```

Set `<QUOTE_USDT>` to a small amount above the instrument minimum and covered
by trading-account USDT balance.
Set `<SPOT_TD_MODE>` from account config `acctLv`: use `"cash"` for account
modes `"1"` and `"2"`, and `"cross"` for account modes `"3"` and `"4"`. In
account mode `"2"`, use `"cross"` or `"isolated"` only when the user explicitly
intends margin spot. The MCP tool schema requires the field, so include it
explicitly.

### Spot Close

Sell the BTC amount opened by the demo.

Read-only preflight:

```json
[
  {"tool": "account_get_config", "arguments": {"simulatedTrading": true}},
  {"tool": "account_get_balance", "arguments": {"ccy": "BTC", "simulatedTrading": true}},
  {"tool": "market_get_ticker", "arguments": {"instId": "BTC-USDT"}},
  {"tool": "market_get_instruments", "arguments": {"instType": "SPOT", "instId": "BTC-USDT"}}
]
```

Order tool call:

```json
{
  "tool": "spot_place_order",
  "arguments": {
    "instId": "BTC-USDT",
    "tdMode": "<SPOT_TD_MODE>",
    "side": "sell",
    "ordType": "market",
    "sz": "<VALID_BTC_SIZE>",
    "aiBuilderCode": "<AI_BUILDER_CODE>",
    "simulatedTrading": true
  }
}
```

Set `<VALID_BTC_SIZE>` to the BTC amount represented by the same small quote
amount used for Spot Open, rounded down to `lotSz` and capped at available BTC.
Do not go below `minSz`. Do not default to selling the user's entire BTC
balance unless the user explicitly asks for a full spot close.
Set `<SPOT_TD_MODE>` from account config `acctLv`: use `"cash"` for account
modes `"1"` and `"2"`, and `"cross"` for account modes `"3"` and `"4"`. In
account mode `"2"`, use `"cross"` or `"isolated"` only when the user explicitly
intends margin spot. The MCP tool schema requires the field, so include it
explicitly.

### Swap Open

Open a small BTC-USDT-SWAP long in demo trading from a target USDT notional.
Use this workflow for linear swap instruments. Do not reuse it for
inverse USD swap instruments such as `BTC-USD-SWAP`; those instruments have
different sizing and settlement rules.

Read-only preflight:

```json
[
  {"tool": "account_get_config", "arguments": {"simulatedTrading": true}},
  {"tool": "account_get_balance", "arguments": {"ccy": "USDT", "simulatedTrading": true}},
  {"tool": "market_get_ticker", "arguments": {"instId": "BTC-USDT-SWAP"}},
  {"tool": "market_get_instruments", "arguments": {"instType": "SWAP", "instId": "BTC-USDT-SWAP"}}
]
```

Order tool call — first read account config: if `acctLv="1"` **stop** (spot-mode
account, swap not supported); the `tdMode` below (`cross`) is for acctLv 2/3/4; add
`"posSide": "long"` only when `posMode=long_short_mode` (else omit it):

```json
{
  "tool": "swap_place_order",
  "arguments": {
    "instId": "BTC-USDT-SWAP",
    "tdMode": "cross",
    "side": "buy",
    "ordType": "market",
    "sz": "<QUOTE_USDT>",
    "tgtCcy": "quote_ccy",
    "aiBuilderCode": "<AI_BUILDER_CODE>",
    "simulatedTrading": true
  }
}
```

If account config returns `acctLv="1"`, stop: the account is in spot mode and
this swap workflow is not supported. If account config returns
`posMode=long_short_mode`, add `"posSide": "long"`; otherwise omit `posSide`.
The MCP tool schema requires explicit `tdMode`; use `"cross"` for account modes
`"2"`, `"3"`, and `"4"`, or use `"isolated"` when the user intends isolated
margin.
Set `<QUOTE_USDT>` to a small target notional, such as `10`, that is covered by
trading-account USDT balance. Send it as `"sz"` with `"tgtCcy": "quote_ccy"`, and
the MCP backend converts the USDT notional to a valid contract count (using
`ctVal`, ticker price, `minSz`, and `lotSz`) before placing the order. The
preflight `market_get_ticker` and `market_get_instruments` reads are only for
showing the user an approximate contract count before the order write.

Verify:

```json
{"tool": "swap_get_positions", "arguments": {"instId": "BTC-USDT-SWAP", "simulatedTrading": true}}
```

### Swap Close

Close the BTC-USDT-SWAP long opened by the demo.

Read-only preflight:

```json
[
  {"tool": "account_get_config", "arguments": {"simulatedTrading": true}},
  {"tool": "swap_get_positions", "arguments": {"instId": "BTC-USDT-SWAP", "simulatedTrading": true}}
]
```

Close tool call:

```json
{
  "tool": "swap_close_position",
  "arguments": {
    "instId": "BTC-USDT-SWAP",
    "mgnMode": "<SWAP_MGN_MODE>",
    "autoCxl": true,
    "aiBuilderCode": "<AI_BUILDER_CODE>",
    "simulatedTrading": true
  }
}
```

Set `<SWAP_MGN_MODE>` from the position's margin mode, usually `"cross"` or
`"isolated"`. If account config returns `acctLv="1"`, stop because there should
be no swap position for this workflow. If account config returns
`posMode=long_short_mode`, add `"posSide": "long"`; otherwise omit `posSide`.
Verify with `swap_get_positions`.

Use this as the pattern for supported MCP order-producing tools. For the broader
supported tool reference, read
[../../docs/AI_BUILDER_CODE_SUPPORT_REFERENCE.md](../../docs/AI_BUILDER_CODE_SUPPORT_REFERENCE.md).
Do not invent alternate field names or pass raw `tag`. Do not add `aiBuilderCode` to
cancel, amend, query, read, leverage, stop, earn, lending, DCD, transfer, or
configuration tools unless their tool schema explicitly exposes attribution
support.

## Workflow

1. Confirm the user wants the MCP path, then run the connect gate (see
   **Authorization and connect gate** above).
2. Select a supported OKX MCP order-producing tool.
3. For supported order-producing tools, validate the AI Builder Code value and pass `aiBuilderCode`.
4. Before any order write, summarize the final order parameters and wait for explicit confirmation.
5. After an order write, verify with a read-only OKX MCP tool.
