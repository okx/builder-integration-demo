# OKX Fast API Integration Guide

> This is the Type 3 implementation guide for AI assistants and developers. Type 3 means a third-party service uses OKX OAuth Broker + Fast API to create and store long-lived API Keys for end users. The flow and parameters are language-neutral; the `backend/` folder is only one Python/Flask reference implementation.
>
> If the user is trading only their own OKX account, even from their own VPS or server, go back to `../../docs/USER_TYPES.md` and choose Type 1 or Type 2.
>
> Before implementing against a real environment, read [PITFALLS.md](PITFALLS.md). It centralizes token path, `redirect_uri` encoding, `bindApp`, site domain, signing, and error-code checks.
>
> For external OpenAPI references and AI Builder introduction links, read [../../docs/REFERENCE_LINKS.md](../../docs/REFERENCE_LINKS.md).

## What Fast API Is For

Fast API is for a third-party Broker application that creates and stores a long-lived OKX API Key for an end user, then uses that key to call OKX OpenAPI on behalf of that user.

Why a third-party service uses Fast API instead of plain OAuth:

| | OAuth authorization code / PKCE | Fast API |
|---|---|---|
| Credential | access_token, 1 hour; refresh_token, 3 days | Long-lived API Key until the user unbinds or revokes it |
| Works after user leaves the page | Only while tokens can still be refreshed | Yes, no user presence required |
| Best fit | User-present interactive actions | Third-party hosted user strategies or bots |

Conclusion: use Type 3 Fast API when a third-party service needs long-lived trading ability for end users. Do not choose Type 3 just because a self-account bot runs on a server.

## Prerequisites

These prerequisites are handled by the integrating party, not by code:

1. Contact BD to become an OAuth Broker and enable Fast API permission plus the Broker IP allowlist.
2. Provide the OAuth whitelist, redirect URL, logo, and CORS domains during application.
3. After approval, get `client_id` and `client_secret` by email.
4. Register the exact `redirect_uri` with OKX; otherwise authorization fails.

## Hard Constraints

- Fast API supports authorization code mode only: `access_type=offline`, `scope=fast_api`. Do not implement Fast API with PKCE.
- `client_secret`, created `apiKey`, created `secretKey`, and `passphrase` are backend-only customer-sensitive credentials. Never put them in frontend code, logs, analytics, crash reports, or git.
- One Broker can have only one active Fast API Key for one user. Delete the old key before creating a new one.
- `access_token` is used only to create the Fast API Key. It lasts 1 hour and has no refresh token. The created API Key is the long-lived credential.

## Full Flow

```text
[Frontend] 1. authorize(scope=fast_api) -> OKX authorization page
             User signs in and authorizes
[Frontend] 2. Callback redirect_uri?code=...&state=...&domain=...
             Validate state; send code and optional domain to backend
[Backend]  3. POST exchange code for access_token with client_secret
[Backend]  4. POST delete old Fast API Key, ignore 59506
[Backend]  5. POST create Fast API Key and store it encrypted on backend
[Backend]  6. Use that API Key to sign OpenAPI business requests
```

### Step 1: Start Authorization In Frontend

OKX Web SDK CDN:

- Global: `https://static.okx.com/cdn/assets/okfe/libs/okxOAuth/index.js`
- China: `https://static.coinall.ltd/cdn/assets/okfe/libs/okxOAuth/index.js`

```js
OKEXOAuthSDK.init({ requestUrl: 'https://www.okx.com' });
const state = OKEXOAuthSDK.generateState(); // Store this random value for CSRF protection.
OKEXOAuthSDK.authorize({
  response_type: 'code',
  access_type:  'offline',          // Fast API requires offline.
  client_id:    'YOUR_CLIENT_ID',
  redirect_uri: encodeURIComponent('https://yourapp.com/callback'),
  scope:        'fast_api',          // Required for Fast API.
  state,
});
```

If the authorization page does not show Fast API permission, `scope` is usually not set to `fast_api`.

Integration pitfall: this demo has passed real integration with `redirect_uri: encodeURIComponent(CONFIG.redirect_uri)`. When migrating to another frontend wrapper, make sure the final authorization URL contains exactly one encoded `redirect_uri`; see [PITFALLS.md](PITFALLS.md).

### Step 2: Callback And State Validation

The callback looks like:

```text
https://yourapp.com/callback?code=...&state=...&domain=https://www.okx.com
```

- Always validate callback `state` against the stored outbound `state`. Discard the callback on mismatch.
- If `domain=https://eea.okx.com`, use that domain for subsequent REST calls and `wss://wseea.okx.com` for WebSocket.

### Step 3: Exchange Authorization Code For Access Token

```text
POST {base}/v5/users/oauth/token
Content-Type: application/json
{
  "grant_type": "authorization_code",
  "code": "<code from callback>",
  "client_id": "YOUR_CLIENT_ID",
  "client_secret": "YOUR_CLIENT_SECRET"
}
-> { "access_token": "...", "token_type": "bearer", "expires_in": 3600 }
```

Endpoint note: the token path verified by real integration is `/v5/users/oauth/token`. Delete and create key endpoints still use `/api/v5/...`. If token exchange returns 404, first check site domain, Broker permission, `redirect_uri`, `client_id`, and `client_secret`; do not add an `/api` prefix to the token path.

### Step 4: Delete Old Fast API Key

```text
POST {base}/api/v5/users/oauth/delete-apikey
Authorization: Bearer <access_token>
x-simulated-trading: 1   # simulated trading only
-> {"code":"0","data":[{"result":true}]}
```

If OKX returns `59506`, the key does not exist. Treat it as normal and continue.

### Step 5: Create Fast API Key

```text
POST {base}/api/v5/users/oauth/apikey
Authorization: Bearer <access_token>
x-simulated-trading: 1   # simulated trading only
{
  "label": "demo",
  "passphrase": "<8-32 chars with uppercase, lowercase, number, special char>",
  "perm": "read_only",
  "bindApp": true
}
-> { "code":"0", "data":[{
      "label":"demo","apiKey":"...","secretKey":"...","passphrase":"...","perm":"read_only","bindApp":true
    }] }
```

This reference implementation intentionally stores the created `apiKey`,
`secretKey`, and `passphrase` only in backend process memory for local demo use.
Restarting the backend clears the demo session.

In a real implementation, store each user's created `apiKey`, `secretKey`, and
`passphrase` on the backend so the service can place future orders for that user
after authorization. Treat them as customer-sensitive credentials: isolate them
per user and protect them from frontend exposure, logs, analytics, crash
reports, and git.

`bindApp=true` requires the Broker IP allowlist to be enabled by OKX. If key creation returns `50118`, fix the allowlist permission instead of bypassing bound-key creation.

### Step 6: Call OKX Business APIs With HMAC Signing

Example: `GET /api/v5/account/balance` with read-only permission.

The canonical signing rules live in [../../docs/OPENAPI_SIGNING.md](../../docs/OPENAPI_SIGNING.md). Copyable Python and Node.js snippets live in [SIGNING.md](SIGNING.md). The runnable Python implementation is `backend/okx_client.py`.

Simulated trading requests must include `x-simulated-trading: 1`. Live trading requests must not include this header.

Key balance response fields:

- `data[0].totalEq`: total equity in USD terms
- `data[0].details[].ccy/eq/availBal`: per-currency details

### Order Workflows And AI Builder Code

This demo's order routes sign and send OKX order requests with the created Fast
API Key. They must require `AI_BUILDER_CODE` and send it as the OKX request
field `tag`.

Implemented local routes:

- `POST /api/order`
- `POST /api/spot/open`
- `POST /api/spot/close`
- `POST /api/swap/open`
- `POST /api/swap/close`

Implemented OKX order endpoints:

- `POST /api/v5/trade/order`
- `POST /api/v5/trade/close-position`

`POST /api/v5/trade/order` body fields used by this demo:

- `instId`
- `tdMode`; spot workflows default from account config `acctLv` (`cash` for
  `1`/`2`, `cross` for `3`/`4`) unless the request body provides an explicit
  account-compatible spot trade mode; swap-open requires `acctLv=2`, `3`, or
  `4` and defaults to `cross` unless the request body provides `isolated`
- `side`
- `ordType`
- `sz`
- `tgtCcy=quote_ccy` for spot market buy quote-sized orders
- `px` for non-market orders
- `posSide` only when swap account config returns `posMode=long_short_mode`
- `tag`, populated from `AI_BUILDER_CODE`

`POST /api/v5/trade/close-position` body fields used by this demo:

- `instId`
- `mgnMode`
- `posSide` only when swap account config returns `posMode=long_short_mode`
- `autoCxl`
- `tag`, populated from `AI_BUILDER_CODE`

For any additional order-producing endpoint, first verify the OKX request
schema, then add a demo-specific scope note and tests before passing `tag`.

The demo workflow routes accept explicit business inputs. If `tdMode` is
omitted for spot, the backend reads account config and chooses the OKX
documented default for the current `acctLv`:

- `acctLv=1`: spot `tdMode` must be `cash`.
- `acctLv=2`: spot defaults to `cash`; use `cross` or `isolated` only for
  intentional margin spot.
- `acctLv=3` or `4`: spot `tdMode` must be `cross`.

For spot workflows, `quoteAmount` is denominated in the instrument quote
currency. `BTC-USDT` uses USDT; another spot pair uses that pair's quote
currency for sizing and balance checks. Spot preflight output includes
`baseCcy` and `quoteCcy` so callers do not need to infer currencies from dynamic
balance field names.

```text
POST /api/spot/open
{"instId":"BTC-USDT","quoteAmount":"10"}
{"instId":"BTC-USDT","quoteAmount":"10","tdMode":"cross"}

POST /api/spot/close
{"instId":"BTC-USDT","quoteAmount":"10"}
{"instId":"BTC-USDT","quoteAmount":"10","tdMode":"cross"}

POST /api/swap/open
{"instId":"BTC-USDT-SWAP","quoteAmount":"10"}
{"instId":"BTC-USDT-SWAP","quoteAmount":"10","tdMode":"isolated"}

POST /api/swap/close
{"instId":"BTC-USDT-SWAP","mgnMode":"cross"}
{"instId":"BTC-USDT-SWAP","mgnMode":"isolated"}
```

For swap open, the backend converts `quoteAmount` to contract count with current
ticker price, `ctVal`, `minSz`, and `lotSz` before calling
`POST /api/v5/trade/order`. The current demo supports linear swap instruments
only and checks balance with the instrument `settleCcy`. Inverse USD swap
instruments such as `BTC-USD-SWAP` use different sizing and settlement rules and
fail before order placement.
For swap close, use the margin mode of the position being closed. If swap open
uses `tdMode=isolated`, close that position with `mgnMode=isolated`.

## Unbinding

When a user unbinds, the Broker can delete the locally stored API Key. Editing or deleting keys on OKX itself requires the user to log in to OKX.

## Endpoint Quick Reference

| Purpose | Method | Path | Auth |
|---|---|---|---|
| Exchange access token | POST | `/v5/users/oauth/token` | client_secret |
| Delete Fast API Key | POST | `/api/v5/users/oauth/delete-apikey` | Bearer access_token |
| Create Fast API Key | POST | `/api/v5/users/oauth/apikey` | Bearer access_token |
| Account balance example | GET | `/api/v5/account/balance` | API Key HMAC signing |
| Order example | POST | `/api/v5/trade/order` | API Key HMAC signing |
| Swap close example | POST | `/api/v5/trade/close-position` | API Key HMAC signing |
