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
| AI Builder integration introduction | `https://www.okx.com/help/ai-builder-program-integration-guide` | Understanding the three user types before choosing a demo path. |
| Agent Trade Kit install guide | `https://www.okx.com/agent-tradekit` | Installing or connecting the OKX Trade CLI and OKX MCP surfaces. |
| Agent Trade Kit code repository | `https://github.com/okx/agent-trade-kit` | CLI implementation reference for `aiBuilderCode` support. |

## How To Use These References

- Start with [USER_TYPES.md](USER_TYPES.md) and the AI Builder integration
  introduction when deciding Type 1, Type 2, or Type 3.
- For Type 1 and Type 3 OpenAPI extensions, verify the request schema in the
  OpenAPI global site or Markdown repository before adding `tag`.
- These demos are validated for OKX Global. For another OKX site, use the
  OpenAPI Markdown repository to check site availability first, then read the
  exact endpoint document for that site. Do not infer other-site support from
  the Global demo.
- For Type 2 CLI/MCP setup, use the Agent Trade Kit install guide before using
  the CLI or MCP example skills.
- For Type 2 CLI capability checks, use installed CLI help first. Use the Agent
  Trade Kit CLI code repository when the installed behavior is unclear.
- For AI Builder Code support planning, use
  [AI_BUILDER_CODE_SUPPORT_REFERENCE.md](AI_BUILDER_CODE_SUPPORT_REFERENCE.md)
  as the local extension reference.
