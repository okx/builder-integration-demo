# openapi-user Testing Guide

This demo has two test layers: local automated tests (no network, no real keys),
and a real integration checklist against OKX demo trading (simulated funds).

The checklist is written for the OKX Global site. For another OKX site, check
endpoint availability and request schemas in the OpenAPI Markdown docs first.

- (a) Local automated tests: no network; verify demo/live profile selection, AI
  Builder Code validation, the `x-simulated-trading` header, order-body fields,
  and known-answer OpenAPI signing vectors.
- (b) Real integration checklist: with an OKX demo-trading API key in `.env`
  (`OKX_PROFILE=demo`), run the four order workflows on simulated funds and
  confirm attribution.

Security note: automated tests use no real secrets and run no network at test
time. Never commit `.env`; keep `secretKey` / `passphrase` out of prompts, logs,
and git. Use a **read + trade** key (never withdrawal), and separate keys for
demo vs live.

## A. Local Automated Tests

```bash
cd demos/openapi-user
test -d .tmpvenv || python3 -m venv .tmpvenv
source .tmpvenv/bin/activate
python -m pip install -r requirements.txt
python3 -m unittest test_strategy_demo.py
```

Covers: demo/live profile selection; AI Builder Code validation (order writes
refused without `--ai-builder-code`); the `x-simulated-trading: 1` header on the
demo profile; order-body fields; and known-answer HMAC signing vectors
(`test_known_answer_signing_vectors`) — the regression net for the copy-verbatim
signing client `okx_openapi_client.py`.

**Pass:** all tests green.

## B. Real Integration Checklist (OKX demo trading)

Prerequisites:
- OKX **demo-trading** API key with **read + trade only, no withdrawal**.
- `.env` with `OKX_PROFILE=demo` + `OKX_DEMO_API_KEY` / `OKX_DEMO_SECRET_KEY` / `OKX_DEMO_PASSPHRASE`.
- Your AI Builder Code.

`OKX_PROFILE=demo` adds `x-simulated-trading: 1` automatically — no real funds.

| Step | Command | Pass criteria |
|---|---|---|
| Balance | `python strategy_demo.py balance` | Returns demo account balances; no error |
| Spot open | `python strategy_demo.py spot-open --inst-id BTC-USDT --quote-amount 10 --ai-builder-code <CODE>` | Order submitted; `sent_order` carries `tag == <CODE>`; size derived from ticker/instrument rules |
| Spot close | `python strategy_demo.py spot-close --inst-id BTC-USDT --quote-amount 10 --ai-builder-code <CODE>` | Holding reduced; `tag == <CODE>` |
| Swap open | `python strategy_demo.py swap-open --inst-id BTC-USDT-SWAP --quote-amount 10 --ai-builder-code <CODE>` | Long opened; `tag == <CODE>`; `tdMode` / `posSide` derived from account config |
| Swap close | `python strategy_demo.py swap-close --inst-id BTC-USDT-SWAP --mgn-mode cross --ai-builder-code <CODE>` | Position closed; `tag == <CODE>` |

> Note: closing the same quote amount as Spot Open can exceed the available base
> balance after fees/price movement — lower the amount, or use `--base-size`.

**Attribution check:** command output includes `preflight`, `sent_order`, and the
raw OKX response — confirm `sent_order` carries `tag == <your Builder Code>`
(the top-level `sent_ai_builder_code` field also echoes it).

**Negative checks:**
- Omit `--ai-builder-code` → the command must refuse to place the order.
- Live profile (`OKX_PROFILE=live`): every order-producing command additionally
  requires `--confirm-live-order`. Do not use real funds for this demo's testing —
  keep to the demo profile.

Integration pitfalls and OKX field details: see the demo README's
**For real integration** section and
[../../docs/AI_BUILDER_CODE_SUPPORT_REFERENCE.md](../../docs/AI_BUILDER_CODE_SUPPORT_REFERENCE.md).
