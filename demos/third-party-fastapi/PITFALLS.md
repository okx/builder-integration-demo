# Fast API Pitfalls And Error Checks

This is the short Type 3 troubleshooting entry for AI assistants. Read it before changing OAuth, Fast API Key creation, signing, or order placement code.

This demo has already passed real integration. Treat these notes as guardrails when migrating it into another project.

## High-Impact Pitfalls

1. **Token endpoint path**
   - The verified token exchange endpoint is `POST /v5/users/oauth/token`.
   - Delete/create Fast API Key endpoints still use `/api/v5/...`.
   - If token exchange returns 404, first check site domain, Broker permission, `redirect_uri`, `client_id`, and `client_secret`; do not add an `/api` prefix to the token path.

2. **`redirect_uri` double encoding**
   - This demo uses `redirect_uri: encodeURIComponent(CONFIG.redirect_uri)` and has passed real integration.
   - When migrating to another frontend framework or SDK wrapper, inspect the final authorization URL in browser Network.
   - Normal encoding usually contains `%3A` / `%2F`. Double encoding often contains `%253A` / `%252F`.
   - The final authorization URL should contain exactly one encoded `redirect_uri` value.

3. **`bindApp=true` requires IP allowlist**
   - The backend creates Fast API Keys with `bindApp=true`.
   - Error `50118` means OKX needs the Broker IP allowlist before bound keys can be created.
   - Do not bypass this by silently creating unbound keys.

4. **Delete before create**
   - A Broker can have only one active Fast API Key for one user.
   - Always call `delete-apikey` before creating a new key.
   - Error `59506` means the key does not exist. Ignore it during delete-before-create and continue.

5. **Simulated trading header**
   - Simulated trading requests must include `x-simulated-trading: 1`.
   - Live trading requests must not include this header.
   - Keep demo and live API Keys separate.

6. **Domain consistency**
   - This demo checklist is written for OKX Global.
   - When adapting to another OKX site, the OAuth callback `domain`, frontend
     authorization `requestUrl`, backend REST domain, and endpoint availability
     must be checked together.
   - Use the OpenAPI Markdown docs as the source of truth for other-site
     endpoint availability.

7. **OpenAPI signing exactness**
   - Use the root signing rules in [../../docs/OPENAPI_SIGNING.md](../../docs/OPENAPI_SIGNING.md).
   - Sign `timestamp + METHOD + requestPathWithQuery + body`.
   - GET body is an empty string.
   - The signed query/body must exactly match the HTTP request that is sent.
   - Do not let the HTTP client rebuild `params` or reorder JSON after signing.

8. **AI Builder Code attribution**
   - Every order request implemented by this demo must put `AI_BUILDER_CODE` into the OKX request field `tag`.
   - `AI_BUILDER_CODE` is not a secret, but missing it means the order cannot be attributed to AI Builder.

## Error Codes

| Code | Meaning | What to do |
|---|---|---|
| 50116 | Fast API can create only one API Key | Delete the old key first; this demo already does that. |
| 50117 | Only API Brokers can create Fast API Keys | Confirm Fast API permission with BD. |
| 50118 | Bound API Key requires Broker IP allowlist | Enable the IP allowlist, then create with `bindApp=true`. |
| 59506 | API Key does not exist | Treat as normal during delete-before-create and continue. |
| 53018 | Site authorization is missing for `my.okx.com` | Ask BD to enable the required site authorization. |

## Quick Checks By Symptom

- Authorization page does not show Fast API permission: check `scope=fast_api`.
- Authorization or callback fails: compare `redirect_uri` against the OKX whitelist byte for byte, then check for double encoding.
- Callback `state` mismatch: discard the callback and start OAuth again.
- Token exchange 404: keep `/v5/users/oauth/token`; check domain and Broker configuration.
- Signing error such as 401 or 50113: check timestamp format, prehash order, query string, sent body, passphrase, and simulated trading header.
- Order succeeds without attribution: check that the final OKX request body contains `tag`.
