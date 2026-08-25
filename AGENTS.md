# AGENTS.md - AI Builder repo rules

You are helping users integrate OKX AI Builder. There are **four** user types. First identify the user's type, then read the matching demo. By default, do not read or copy another demo's implementation unless the user explicitly asks to compare paths.

Every demo folder under `demos/` uses the same skeleton: `README.md` is the
entry doc, and it names the artifact the user takes into their own project.
Each `README.md` has a `Copy vs Adapt` section that classifies every file in
that folder. Follow it instead of copying a whole demo folder wholesale.

## User Type Routing

1. **`openapi-user` — self account + local OpenAPI script**
   - Read `demos/openapi-user/README.md`.
   - Use when the user runs their own strategy on a user-controlled machine or server and trades only their own OKX account.
   - User configures their own OKX API Key locally.
   - Do not use OAuth Broker or Fast API.
   - Use `docs/OPENAPI_SIGNING.md` for HMAC signing rules.
   - Artifact: `okx_openapi_client.py` copied verbatim (its public functions
     default to `simulated=True`; production must pass `simulated=False`), with
     `strategy_demo.py` adapted.

2. **`cli-user` — self account + OKX Trade CLI**
   - Read `demos/cli-user/README.md`, then `demos/cli-user/SKILL.md`.
   - Use when the user drives trading through the local `okx` command in a
     terminal or by a coding agent, for their own OKX account.
   - OKX Trade CLI can use local API-key profiles or OAuth.
   - Do not use OAuth Broker or Fast API.
   - Do not implement OpenAPI signing in this repo path; the OKX backend handles execution.
   - Artifact: `SKILL.md`. The user's agent uses it to drive the `okx` CLI.
     Replace the `<AI_BUILDER_CODE>` placeholder with the user's real Builder
     Code.

3. **`mcp-user` — self account + OKX MCP**
   - Read `demos/mcp-user/README.md`, then `demos/mcp-user/SKILL.md`.
   - Use when the user's AI app calls OKX MCP (ChatGPT app, Claude Desktop, or
     another app-connected MCP) for their own OKX account.
   - OKX MCP authorization is handled by the host app or connector.
   - Do not use OAuth Broker or Fast API.
   - Do not implement OpenAPI signing in this repo path; the OKX backend handles execution.
   - Artifact: `SKILL.md`. The user's agent uses it to call OKX MCP tools.
     Replace the `<AI_BUILDER_CODE>` placeholder with the user's real Builder
     Code.

4. **`oauth-user` — third-party server + OKX Fast API/OpenAPI**
   - Read `demos/oauth-user/README.md`, `demos/oauth-user/INTEGRATION_GUIDE.md`, and `demos/oauth-user/PITFALLS.md`.
   - Use when a third-party service creates and stores long-lived Fast API Keys for its end users.
   - Keep the verified Fast API flow intact. Do not change endpoint constants, HMAC signing behavior, delete-before-create behavior, domain allowlist logic, or the server-side OAuth `state` CSRF check (validated in `/api/connect` against the httpOnly `oauth_state` cookie) unless the user explicitly asks and understands the risk. Never weaken `state` to a frontend-only check.
   - Artifact: `backend/okx_client.py` and `backend/app.py`, both **adapted**.
     `MOCK` test scaffolding lives in `backend/okx_client.py` (fakes order
     acceptance), `backend/app.py` (bypasses the OAuth config validation gate;
     leaks a `mock` flag in `/config`), and `frontend/index.html` (skips real
     OAuth; suppresses the live-order confirm). Remove all of it before production.

Full decision tree: `docs/USER_TYPES.md`. It is the authoritative routing table;
`README.md` and this file point to it.

## Naming Rules

- The product-facing name is **AI Builder Code**.
- Use `AI_BUILDER_CODE` only where server code reads environment configuration.
- `openapi-user` OpenAPI scripts use `--ai-builder-code` on order-producing commands.
- OKX order requests still use the field name `tag`; set its value to AI Builder Code.
- The demo may expose `ai_builder_code` in JSON responses such as `/config`.
  Do not use it as a repo config name or OKX request field.
- `cli-user` and `mcp-user` OKX backends may expose the argument as `--aiBuilderCode` or `aiBuilderCode`; preserve the backend schema instead of renaming it.
- Use one public attribution concept in this repo: AI Builder Code. Preserve
  OKX protocol fields and backend argument names only where this document lists
  them.
- Do not infer support from a generic OKX `tag` field. Check the selected demo
  README, selected skill, or live backend schema before adding AI Builder Code
  to a command, tool, or endpoint.
- OKX responses may still contain `data[0].tag` or OKX fields such as `brokerCode`; do not rename OKX protocol fields.
- AI Builder Code is assigned by OKX when the user registers as an AI Builder; use the value the user provides and do not make one up. Format: 1-16 alphanumeric characters.
- AI Builder Code is not a secret, but order writes must stop if a required code is missing or cannot be passed through.

## Security Rules

- OAuth CSRF `state` must be validated server-side (bound to the user's session), single-use, and expiring. A frontend-only `state` check is bypassable and must not be relied on. Never log any part of the authorization `code` (it is exchangeable for a token); `state` is not a bearer secret but avoid logging it in production.
- Never put `client_secret`, `secretKey`, or `passphrase` in frontend code, logs, or committed files.
- Real `.env` files are local only and must not be committed.
- Keep `.env.example` files only for demos that actually read environment configuration.
- The `.env` files created from these examples are for demo use and contain sensitive fields; production integrations should use a secret manager or equivalent protected storage.
- `openapi-user` OpenAPI and `cli-user`/`mcp-user` do not use a demo `.env` for AI Builder Code; pass AI Builder Code through the selected command flag or tool argument.
- Default to simulated trading. Use mock mode only for local non-OAuth checks or when explicitly requested.

## Documentation Rules

- When the same rule appears in a demo path (its README, SKILL, or `AGENTS.md`)
  and in `docs/`, the demo path version governs for that path. If they conflict,
  follow the demo path version and flag the discrepancy to the user.
- Keep operational rules inline in each path so the path is complete without
  following links: how to attach AI Builder Code, trade-mode and position
  selection, delete-before-create, and safety gates. Centralize only reference
  material: the full support matrix in
  `docs/AI_BUILDER_CODE_SUPPORT_REFERENCE.md` and external links in
  `docs/REFERENCE_LINKS.md`. Each path lists only the endpoints, commands, or
  tools it actually uses.
- Put external reference links only in `docs/REFERENCE_LINKS.md`.
- In other docs, link to `docs/REFERENCE_LINKS.md` instead of duplicating
  OpenAPI, AI Builder, Agent Trade Kit, or source repository links.
- Keep runtime URLs in the workflow document that uses them, such as OAuth SDK
  CDN URLs, OKX API domains, callback examples, or localhost examples.
- The rules in this file govern work done **inside this repo**. For the
  cross-surface general rules that also apply outside it, the canonical source
  is the `okx-ai-builder-integration` skill; see `docs/REFERENCE_LINKS.md`. Do
  not copy this file into a user's project.
