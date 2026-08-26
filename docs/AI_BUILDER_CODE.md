# AI Builder Code

**AI Builder Code** is the product-facing name for the order attribution code assigned by OKX. In OpenAPI order requests, it is sent as the OKX `tag` field.

## Naming

| Layer | Name |
|---|---|
| Product/documentation | AI Builder Code |
| Environment variable, when server code reads env config | `AI_BUILDER_CODE` |
| `openapi-user` OpenAPI script argument | `--ai-builder-code` |
| Demo JSON response key | `ai_builder_code` |
| OKX Trade CLI argument | `--aiBuilderCode` |
| OKX MCP tool argument | `aiBuilderCode` |
| OKX order request field | `tag` |

Use one public attribution concept in this repo: AI Builder Code. Use
`AI_BUILDER_CODE` only for `oauth-user` server environment configuration. `openapi-user`
OpenAPI scripts, `cli-user` CLI skills, and `mcp-user` MCP skills pass the value
directly through the selected command flag or tool argument instead of reading a
demo `.env` file. Code may use language-native variable names internally.
The `ai_builder_code` key appears only in demo JSON responses such as
`/config`; do not use it as a repo config name or OKX request field.

## Rules

- It is not a secret.
- It is case-sensitive.
- It must be 1-16 alphanumeric characters: `A-Z`, `a-z`, `0-9`.
- Supported order-producing requests, tools, and commands must attach it. If the
  selected backend surface cannot pass AI Builder Code for that action, use a
  supported surface or stop before placing an attributed order.
- This file defines naming and common rules only. The selected demo README and
  skill define which commands, tools, or endpoints are supported in this repo.
- To extend beyond the implemented demo coverage, read
  [AI_BUILDER_CODE_SUPPORT_REFERENCE.md](AI_BUILDER_CODE_SUPPORT_REFERENCE.md).

OpenAPI order requests that support attribution must set:

```json
{
  "tag": "<AI_BUILDER_CODE>"
}
```

Do not rename the OKX field to `ai_builder_code`; OKX expects the field name `tag`.

## Where It Appears

- `openapi-user` local OpenAPI scripts pass AI Builder Code through the required
  `--ai-builder-code` command argument on order-producing commands.
- `cli-user` OKX Trade CLI skills pass AI Builder Code through `--aiBuilderCode`
  only on supported order-producing CLI commands.
- `mcp-user` OKX MCP skills pass AI Builder Code through the `aiBuilderCode` tool
  argument on supported order-producing MCP tools.
- `oauth-user` Fast API server code reads `AI_BUILDER_CODE` from server `.env` and
  injects it into the order-producing requests implemented by that demo.
