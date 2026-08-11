# AI Builder Code Support Reference

This document is an extension reference for AI assistants. It does not mean
every listed endpoint, command, or tool is already implemented by the demos.

Use it when extending beyond the implemented demo coverage:

- Type 1 implements `POST /api/v5/trade/order` and
  `POST /api/v5/trade/close-position`.
- Type 2 delegates execution details to the selected CLI or MCP skill.
- Type 3 implements `POST /api/order`, `POST /api/spot/open`,
  `POST /api/spot/close`, `POST /api/swap/open`, and `POST /api/swap/close`,
  which route to `POST /api/v5/trade/order` or
  `POST /api/v5/trade/close-position`.

Before extending any demo, update the selected demo README or skill with the new
scope and add tests for AI Builder Code attribution.

Reference links for OpenAPI docs, Agent Trade Kit setup, and CLI source checks
live in [REFERENCE_LINKS.md](REFERENCE_LINKS.md).

## Verification Rules

- OpenAPI sends AI Builder Code as request field `tag`.
- OKX Trade CLI sends AI Builder Code as `--aiBuilderCode`.
- OKX MCP sends AI Builder Code as tool argument `aiBuilderCode`.
- Use 1-16 alphanumeric characters.
- Do not pass raw `tag` through CLI or MCP demo workflows.
- OpenAPI request schemas and installed CLI help are the final source of truth
  for those surfaces. OKX MCP support is defined by the connector tool list
  below.
- Do not treat response-only `tag` fields, history filters, address memo tags,
  or unrelated metadata fields as AI Builder Code support.

## OpenAPI Extension Reference

These REST endpoints are candidates for direct OpenAPI extensions because their
request schema supports order attribution through `tag`.

| Area | Method | Endpoint | Notes |
|---|---:|---|---|
| Block trading | POST | `/api/v5/rfq/create-rfq` | RFQ tag. Associated block trade uses the same tag. |
| Block trading | POST | `/api/v5/rfq/create-quote` | Quote tag. Associated block trade uses the same tag. |
| Convert | POST | `/api/v5/asset/convert/estimate-quote` | Order tag, applicable to broker user. |
| Convert | POST | `/api/v5/asset/convert/trade` | Order tag, applicable to broker user. |
| Trade | POST | `/api/v5/trade/order` | Order tag. Used by the Type 1 and Type 3 spot/swap open workflows and spot close workflow. |
| Trade | POST | `/api/v5/trade/batch-orders` | Order tag per placed order. |
| Trade | POST | `/api/v5/trade/order-algo` | Algo order tag. |
| Trade | POST | `/api/v5/trade/close-position` | Close-position order tag. Used by the Type 1 and Type 3 swap close workflows. |
| Trade | POST | `/api/v5/trade/cancel-all-after` | Cancel-All-After timer can be scoped by tag. Not an order placement endpoint. |
| Spread trading | POST | `/api/v5/sprd/order` | Spread order tag. |
| Copy trading | POST | `/api/v5/copytrading/algo-order` | Lead stop order tag. |
| Copy trading | POST | `/api/v5/copytrading/close-subposition` | Lead position close tag. |
| Copy trading | POST | `/api/v5/copytrading/first-copy-settings` | Copy setting order tag. Settings endpoint, not individual order placement. |
| Copy trading | POST | `/api/v5/copytrading/amend-copy-settings` | Copy setting order tag. Settings endpoint, not individual order placement. |
| Trading bot | POST | `/api/v5/tradingBot/grid/order-algo` | Grid bot order tag. |
| Trading bot | POST | `/api/v5/tradingBot/grid/copy-order-algo` | Copy grid bot order tag. |
| Trading bot | POST | `/api/v5/tradingBot/dca/create` | DCA bot order tag. |
| Trading bot | POST | `/api/v5/tradingBot/recurring/order-algo` | Recurring buy order tag. |
| Earn | POST | `/api/v5/finance/staking-defi/purchase` | Order tag. |

Not counted as OpenAPI attribution support:

- `GET /api/v5/asset/convert/history` request `tag`, because it filters history.
- Read, list, and history endpoints that only return `tag`.
- Deposit and withdrawal `tag` fields, because they are address memo/tag fields.
- Prediction market `tag` fields, because they are sports/outcome metadata.
- Cancel, amend, read, leverage, and stop endpoints unless their request schema
  explicitly accepts `tag`.

## WebSocket Extension Reference

The demos are REST-only. If a future demo covers WebSocket trading, verify the
WebSocket schema first. Request-side `tag` operations include:

| Channel | Operation | Notes |
|---|---|---|
| `/ws/v5/private` | `order` | Order tag in `args`. |
| `/ws/v5/private` | `batch-orders` | Order tag in each item in `args`. |
| `/ws/v5/business` | `sprd-order` | Spread order tag in `args`. |

## OKX Trade CLI Extension Reference

OKX Trade CLI uses `--aiBuilderCode <code>`. The CLI skill shows a simple demo
order:
[../demos/self-account-cli-mcp/self-account-okx-trade-cli/SKILL.md](../demos/self-account-cli-mcp/self-account-okx-trade-cli/SKILL.md).
Use a CLI version whose command help exposes `--aiBuilderCode` on the selected
command. If the flag is absent, upgrade before placing an attributed order
through the CLI path.

Supported CLI command forms:

- `okx spot place ... --aiBuilderCode <code>`
- `okx spot batch --action place --orders '<json>' --aiBuilderCode <code>`
- `okx spot algo place ... --aiBuilderCode <code>`
- `okx spot algo trail ... --aiBuilderCode <code>`
- `okx swap place ... --aiBuilderCode <code>`
- `okx swap close ... --aiBuilderCode <code>`
- `okx swap batch --action place --orders '<json>' --aiBuilderCode <code>`
- `okx swap algo place ... --aiBuilderCode <code>`
- `okx swap algo trail ... --aiBuilderCode <code>`
- `okx futures place ... --aiBuilderCode <code>`
- `okx futures close ... --aiBuilderCode <code>`
- `okx futures batch --action place --orders '<json>' --aiBuilderCode <code>`
- `okx futures algo place ... --aiBuilderCode <code>`
- `okx futures algo trail ... --aiBuilderCode <code>`
- `okx option place ... --aiBuilderCode <code>`
- `okx option algo place ... --aiBuilderCode <code>`
- `okx bot grid create ... --aiBuilderCode <code>`
- `okx bot dca create ... --aiBuilderCode <code>`
- `okx event place ... --aiBuilderCode <code>`

For batch commands, `--aiBuilderCode` is supported only with `--action place`.
Do not use it with batch amend or cancel actions.

Do not add `--aiBuilderCode` to other CLI commands unless that command exposes
the flag. In particular, do not add it to cancel, amend, query/read, leverage,
stop, earn/lending/DCD, transfer, configuration, diagnostic, upgrade, or
outcome commands unless support is explicitly exposed.

Earn on-chain purchase has a raw `tag` parameter in the underlying surface. This
demo does not use that parameter as AI Builder Code in CLI or MCP workflows.

## OKX MCP Extension Reference

OKX MCP uses tool argument `aiBuilderCode` on supported order-producing tools.
For this repo's Type 2 demo, pass `aiBuilderCode` explicitly for attributed
orders and do not rely on backend defaults. When provided and valid,
`aiBuilderCode` becomes the final OKX request `tag`. The MCP skill shows a
simple demo tool call:
[../demos/self-account-cli-mcp/self-account-okx-mcp/SKILL.md](../demos/self-account-cli-mcp/self-account-okx-mcp/SKILL.md).

Supported MCP tools:

- `spot_place_order`
- `swap_place_order`
- `futures_place_order`
- `option_place_order`
- `spot_place_algo_order`
- `swap_place_algo_order`
- `futures_place_algo_order`
- `option_place_algo_order`
- `spot_batch_orders` with `action=place`
- `swap_batch_orders` with `action=place`
- `futures_batch_orders`
- `swap_close_position`
- `futures_close_position`
- `event_place_order`
- `grid_create_order`
- `dca_create_order`

For `spot_batch_orders` and `swap_batch_orders`, `aiBuilderCode` is supported
only when `action=place`; batch cancel and amend actions are not attributed.
For `futures_batch_orders`, the tool is a batch place-order tool.
Move-stop attribution uses the `*_place_algo_order` tools with
`ordType=move_order_stop`; do not add `aiBuilderCode` to
`swap_place_move_stop_order` or `futures_place_move_stop_order`.

Do not pass raw `tag` through MCP demo workflows. Do not add `aiBuilderCode` to
cancel, amend, query, read, leverage, stop, earn, lending, DCD, transfer, or
configuration tools unless their tool schema explicitly exposes attribution
support.
