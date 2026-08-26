# Reference Links

This document points humans and AI assistants to external references used with
this demo repo.

This is the only public index for external reference links. Other repo docs
should link here instead of duplicating external documentation links. Runtime
URLs used by a demo, such as SDK CDN URLs, OKX API domains, callback examples,
or localhost URLs, may stay in the workflow document where they are used.

## Links

| Reference | Link | Use when |
|---|---|---|
| OpenAPI global site | `https://www.okx.com/docs-v5/en/#overview` | Reading OKX Global OpenAPI docs in a browser. |
| OpenAPI Markdown repository | `https://github.com/okx/ai-builder-openapi-md` | Letting an AI assistant check site support, request schemas, parameter tables, and examples. |
| `okx-ai-builder-integration` guide skill | `https://github.com/okx/ai-builder-openapi-md` | The AI-installable integration guide skill that routes users to this demo repo. It is the canonical source for the cross-surface general rules; this repo is the canonical source for demo code and per-path caveats. |
| AI Builder integration introduction | `https://www.okx.com/help/ai-builder-program-integration-guide` | Understanding the four user types before choosing a demo path. |
| Agent Trade Kit install guide | `https://www.okx.com/agent-tradekit` | Installing or connecting the OKX Trade CLI and OKX MCP surfaces. |
| OKX Trade CLI docs | `https://www.okx.com/docs-v5/agent_en/#cli` | Command and usage reference for the `okx` CLI (installation is via the Agent Trade Kit install guide). |
| Agent Trade Kit code repository | `https://github.com/okx/agent-trade-kit` | CLI implementation reference for `aiBuilderCode` support. |

## How To Use These References

- Start with [USER_TYPES.md](USER_TYPES.md) and the AI Builder integration
  introduction when deciding `openapi-user`, `cli-user`, `mcp-user`, or `oauth-user`.
- The `okx-ai-builder-integration` guide skill routes users to this repo. This
  repo works without it; use it when you want an AI assistant to pick the path
  and read the general rules before touching demo code.
- For `openapi-user` and `oauth-user` OpenAPI extensions, verify the request schema in the
  OpenAPI global site or Markdown repository before adding `tag`.
- These demos are validated for OKX Global. For another OKX site, use the
  OpenAPI Markdown repository to check site availability first, then read the
  exact endpoint document for that site. Do not infer other-site support from
  the Global demo.
- For `cli-user` setup, install via the Agent Trade Kit install guide, then use
  the OKX Trade CLI docs for command/usage reference before using the CLI
  example skill.
- For `mcp-user` setup, connect OKX in the host app per the Agent Trade Kit
  install guide before using the MCP example skill.
- For `cli-user` CLI capability checks, use installed CLI help first. Use the Agent
  Trade Kit CLI code repository when the installed behavior is unclear.
- For AI Builder Code support planning, use
  [AI_BUILDER_CODE_SUPPORT_REFERENCE.md](AI_BUILDER_CODE_SUPPORT_REFERENCE.md)
  as the local extension reference.
