# cli-user demo

This demo is for **cli-user** users: the user's assistant or workflow places
orders for the user's **own** OKX account through the **OKX Trade CLI** — the
`okx` command run in a terminal or by a coding agent.

The artifact of this demo is a single file, [SKILL.md](SKILL.md). It is an
agent-readable skill that tells an AI assistant how to drive the `okx` command
safely and with AI Builder Code attribution.

## What this demo shows

- Verifying the installed CLI: `which okx`, `okx --version`, and per-command
  help checks before any order write.
- Choosing between a local API-key profile (`~/.okx/config.toml`) and an OAuth
  session, using `okx config show --json` and `okx auth status --json`.
- Selecting the right mode flags for demo trading versus live trading.
- Four verified demo order workflows: Spot Open, Spot Close, Swap Open, and
  Swap Close, each with read-only preflight and post-order verification.
- Passing AI Builder Code through the CLI flag `--aiBuilderCode` on supported
  order-producing commands.

Boundary — what it does **not** show:

- It does not implement OKX OpenAPI signing. The OKX backend executes the order
  and maps AI Builder Code to the final order `tag`. If the user needs to sign
  requests directly, use [../openapi-user](../openapi-user) instead.
- It does not use OAuth Broker or Fast API. A third-party service trading
  **end users'** accounts belongs in [../oauth-user](../oauth-user).
- It covers BTC-USDT spot and linear BTC-USDT-SWAP only. Inverse USD swap
  instruments such as `BTC-USD-SWAP` are out of scope.
- It is not a complete list of every CLI command that accepts
  `--aiBuilderCode`. See
  [../../docs/AI_BUILDER_CODE_SUPPORT_REFERENCE.md](../../docs/AI_BUILDER_CODE_SUPPORT_REFERENCE.md).

## How to use

1. Install the OKX Trade CLI. See the Agent Trade Kit install guide in
   [../../docs/REFERENCE_LINKS.md](../../docs/REFERENCE_LINKS.md).
2. Read [SKILL.md](SKILL.md) — it is the demo. Give it to your AI assistant, or
   install it as a skill in your agent environment.
3. Replace the `<AI_BUILDER_CODE>` placeholder with the AI Builder Code OKX
   assigned to you. It is 1-16 alphanumeric characters and is not a secret.
4. Run the four demo workflows in demo mode first, then decide whether to move
   to live trading.

```bash
cd demos/cli-user
# Read SKILL.md for the full surface-specific workflow.
which okx && okx --version
okx --demo account balance USDT
```

Do not paste OKX API keys, secret keys, passphrases, OAuth tokens, or refresh
tokens into chat. The CLI reads them from local configuration or an OAuth
session.

## Copy vs Adapt

| File | Bucket | Notes |
|---|---|---|
| `SKILL.md` | **Adapt (take it, then fix 3 things)** | This is the artifact to take into your own project or agent skill directory. Your agent uses it to drive the `okx` CLI. Before use you MUST (1) fill the placeholders below, (2) rewrite its relative links (`../…`, `../../docs/…`) to absolute repo URLs since they dangle once copied out of the repo, and (3) rename its frontmatter `name` to something unambiguous in your environment (the bare `cli-user` collides easily). |
| `README.md` | **Demo scaffolding — do NOT copy** | Entry doc for this repo only. |

Placeholders you must replace in `SKILL.md` before use:

- `<AI_BUILDER_CODE>` — your real AI Builder Code assigned by OKX. Do not make
  one up, and do not leave the placeholder in a skill that places orders.
- `<demo-profile>` / `<live-profile>` — your local CLI profile names, if you use
  API-key mode.

Do not rename `--aiBuilderCode`, and do not substitute `--ai-builder-code` or a
raw `tag` argument on this surface. Those are different surfaces' field names.

## For real integration

- **Version gate is real.** The published minimum CLI version in `SKILL.md` is a
  hard gate; the `--aiBuilderCode` help check is a warning gate. Keep both when
  you adapt the skill, and re-check the minimum version against the installed
  CLI rather than trusting the number in this file forever.
- **Attribution is not guaranteed by hope.** If the selected command's help does
  not expose `--aiBuilderCode`, warn the user and do not claim the order was
  attributed. Never invent an alternate flag.
- **Demo mode is the default.** Live trading requires explicit user
  confirmation before every order write. Keep that gate.
- **This demo is validated for OKX Global.** For another OKX site, confirm
  command and endpoint availability first — see
  [../../docs/REFERENCE_LINKS.md](../../docs/REFERENCE_LINKS.md).
- **Beyond the four workflows**, verify the command's own help or the backend
  schema before adding AI Builder Code to it. Do not infer support from a
  generic OKX `tag` field.

User type decision tree: [../../docs/USER_TYPES.md](../../docs/USER_TYPES.md).
