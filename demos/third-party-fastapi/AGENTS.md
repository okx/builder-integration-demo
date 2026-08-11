# AGENTS.md - Type 3 Fast API rules for AI assistants

You are helping a user integrate **OKX Fast API** into a third-party service. The service creates and stores long-lived Fast API Keys for end users, then calls OKX OpenAPI on behalf of those users.

Fast API here means the OKX product capability, not the Python FastAPI framework. This repo is a reference implementation. Read `INTEGRATION_GUIDE.md` first; use `backend/` and `frontend/` as code references.

If the user is trading only their own OKX account, even from their own server, do not use this folder. Go back to `../../docs/USER_TYPES.md` and choose Type 1 or Type 2.

## Hard Rules

1. Never put `client_secret`, created `apiKey`, created `secretKey`, or `passphrase` in frontend code, mobile code, logs, analytics, crash reports, or git. They are backend-only customer-sensitive credentials.
2. Do not invent endpoints. Use the demo README's AI Builder Code Scope for attribution scope, and use `INTEGRATION_GUIDE.md` for Fast API flow paths and parameters. If uncertain, ask the user to confirm the relevant OKX docs.
3. Fast API supports authorization code mode only: `access_type=offline`, `scope=fast_api`. Do not implement Fast API with PKCE.
4. Delete the old Fast API Key before creating a new one. Error `59506` means the key does not exist; ignore it and continue.
5. The passphrase is provided by the user. Do not generate or hard-code it. It must be 8-32 characters and include uppercase, lowercase, number, and special character.
6. Default to safe settings: `perm=read_only` and `SIMULATED=1`. Use `trade` or `SIMULATED=0` only when the user explicitly asks and understands the risk.
7. Process-memory Fast API Key storage is intentional for this local demo. In a real implementation, store each user's `apiKey`, `secretKey`, and `passphrase` on the backend, isolate them per user, and protect them from frontend exposure, logs, analytics, crash reports, and git.
8. Key creation defaults to `bindApp=true`, matching the backend code. This depends on the OKX Broker IP allowlist. If `50118` occurs, fix the allowlist permission instead of bypassing binding.
9. Order-producing endpoints implemented or extended in this demo must require `AI_BUILDER_CODE` and send it as OKX request `tag`. Stop order writes if the code is missing.

## Standard Integration Steps

1. Confirm prerequisites: `client_id`, `client_secret`, Fast API permission, IP allowlist, and whitelisted `redirect_uri`.
2. Frontend: load OKX Web SDK, call `init`, generate and store `state`, then call `authorize({scope:'fast_api', access_type:'offline', ...})`.
3. Callback page: validate `state`, then send `code` and optional `domain` to the backend.
4. Backend: exchange token, delete old key, create new key. Keep process-memory storage for this demo; use protected backend storage in a real implementation.
5. Business calls: use the created API Key with OKX HMAC signing. The demo examples are `GET /api/v5/account/balance`, `POST /api/v5/trade/order`, and `POST /api/v5/trade/close-position`.

## Pitfalls To Check First

Full pitfalls and error-code checks live in `PITFALLS.md`. These are the highest-priority code review checks:

- Authorization page does not show Fast API permission: check `scope=fast_api`.
- Token exchange path is verified as `/v5/users/oauth/token`. If it returns 404, check domain, Broker permission, `redirect_uri`, `client_id`, and `client_secret`; do not add an `/api` prefix.
- Callback `domain=https://eea.okx.com` means subsequent REST calls must use that domain and WebSocket should use `wss://wseea.okx.com`.
- Key creation `50118` means the Broker IP allowlist is required before using `bindApp=true`.
- Signing failures such as 401 or 50113 usually mean timestamp format, prehash order, query/body exactness, or simulated trading header is wrong.
- Frontend authorization site and backend REST domain must represent the same OKX site.
- Business API query strings must match the signed `requestPath` byte for byte. Do not let an HTTP client rebuild `params` after signing.

See `PITFALLS.md` for more error-code checks.
