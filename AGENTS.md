# AGENTS.md - AI Builder repo rules

You are helping users integrate OKX AI Builder. First identify the user's type, then read the matching demo. By default, do not read or copy another demo's implementation unless the user explicitly asks to compare paths.

## User Type Routing

1. **Self account + local OpenAPI script**
   - Read `demos/self-account-openapi/README.md`.
   - Use when the user runs their own strategy on a user-controlled machine or server and trades only their own OKX account.
   - User configures their own OKX API Key locally.
   - Do not use OAuth Broker or Fast API.
   - Use `docs/OPENAPI_SIGNING.md` for HMAC signing rules.

2. **Self account + OKX Trade CLI/MCP**
   - Read `demos/self-account-cli-mcp/README.md`.
   - Use `demos/self-account-cli-mcp/self-account-okx-trade-cli/SKILL.md` for local `okx` command workflows.
   - Use `demos/self-account-cli-mcp/self-account-okx-mcp/SKILL.md` for app-connected MCP workflows.
   - Use only OKX Trade CLI or OKX MCP as the execution backend.
   - OKX Trade CLI can use local API-key profiles or OAuth. OKX MCP uses host
     app or connector authorization.
   - Do not use OAuth Broker or Fast API.
   - Do not implement OpenAPI signing in this repo path; the OKX backend handles execution.

3. **Third-party server + OKX Fast API/OpenAPI**
   - Read `demos/third-party-fastapi/README.md`, `demos/third-party-fastapi/INTEGRATION_GUIDE.md`, and `demos/third-party-fastapi/PITFALLS.md`.
   - Use when a third-party service creates and stores long-lived Fast API Keys for its end users.
   - Keep the verified Fast API flow intact. Do not change endpoint constants, HMAC signing behavior, delete-before-create behavior, or domain allowlist logic unless the user explicitly asks and understands the risk.

## Naming Rules

- The product-facing name is **AI Builder Code**.
- Use `AI_BUILDER_CODE` only where server code reads environment configuration.
- Type 1 OpenAPI scripts use `--ai-builder-code` on order-producing commands.
- OKX order requests still use the field name `tag`; set its value to AI Builder Code.
- The demo may expose `ai_builder_code` in JSON responses such as `/config`.
  Do not use it as a repo config name or OKX request field.
- Type 2 OKX backends may expose the argument as `--aiBuilderCode` or `aiBuilderCode`; preserve the backend schema instead of renaming it.
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

- Never put `client_secret`, `secretKey`, or `passphrase` in frontend code, logs, or committed files.
- Real `.env` files are local only and must not be committed.
- Keep `.env.example` files only for demos that actually read environment configuration.
- The `.env` files created from these examples are for demo use and contain sensitive fields; production integrations should use a secret manager or equivalent protected storage.
- Type 1 OpenAPI and Type 2 CLI/MCP do not use a demo `.env` for AI Builder Code; pass AI Builder Code through the selected command flag or tool argument.
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
