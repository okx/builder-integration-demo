"""
HTTP calls and signing logic required by the OKX Fast API demo.

This module has two groups of calls:
  1. OAuth / Fast API management APIs with Bearer access_token auth.
     - exchange_token
     - delete_oauth_apikey
     - create_oauth_apikey
  2. Business APIs signed with the created API Key.
     - get_account_balance
     - get_account_config
     - get_positions
     - get_ticker
     - get_instruments
     - place_order
     - close_position

Security contract:
  client_secret, created secretKey, and passphrase are backend-only.
  Never return them to the frontend, log them, or hard-code them.
"""

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests


# Test-only override. MOCK=1 makes external-call helpers return canned OKX-like
# responses for automated tests; do not add it to .env or use it as a demo path.
# The environment is read at call time so tests can toggle this safely.
def _mock_enabled() -> bool:
    return os.environ.get("MOCK", "") == "1"


# OKX API paths. Real integration confirmed that token exchange uses /v5/...,
# while delete/create key endpoints use /api/v5/....
PATH_OAUTH_TOKEN  = "/v5/users/oauth/token"
PATH_OAUTH_DELETE = "/api/v5/users/oauth/delete-apikey"
PATH_OAUTH_APIKEY = "/api/v5/users/oauth/apikey"
PATH_ACCOUNT_BAL  = "/api/v5/account/balance"
PATH_ACCOUNT_CONFIG = "/api/v5/account/config"
PATH_ACCOUNT_POSITIONS = "/api/v5/account/positions"
PATH_MARKET_TICKER = "/api/v5/market/ticker"
PATH_PUBLIC_INSTRUMENTS = "/api/v5/public/instruments"
PATH_TRADE_CLOSE_POSITION = "/api/v5/trade/close-position"
PATH_TRADE_ORDER  = "/api/v5/trade/order"


def _now_iso_ms() -> str:
    """Return OKX's required ISO8601 UTC timestamp with 3-digit milliseconds."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _sign(secret_key: str, timestamp: str, method: str, request_path: str, body: str) -> str:
    """Return base64(HMAC-SHA256(secret, timestamp + method + path + body))."""
    prehash = f"{timestamp}{method.upper()}{request_path}{body}"
    digest = hmac.new(secret_key.encode(), prehash.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _parse(resp: requests.Response) -> dict:
    """
    Parse OKX responses. OKX normally returns JSON, but path, gateway, or rate-limit
    errors may return HTML/plain text. Keep those cases structured for callers.
    """
    try:
        return resp.json()
    except ValueError:
        return {"_http_status": resp.status_code, "_non_json_body": resp.text[:300]}


def _compact(obj: dict) -> dict:
    return {key: value for key, value in obj.items() if value not in (None, "", [])}


def _with_query(path: str, params: dict) -> str:
    compacted = _compact(params)
    return path + ("?" + urlencode(compacted) if compacted else "")


def _ccy_filter(ccy: str = None) -> str:
    if ccy in (None, ""):
        return None
    if not isinstance(ccy, str):
        raise ValueError("ccy must be a string")
    parts = [part.strip().upper() for part in ccy.split(",") if part.strip()]
    if not parts:
        return None
    for part in parts:
        if not part.isalnum():
            raise ValueError("ccy must be a comma-separated currency list")
    return ",".join(parts)


def _public_headers(simulated: bool = True) -> dict:
    headers = {"Content-Type": "application/json"}
    if simulated:
        headers["x-simulated-trading"] = "1"
    return headers


# Mock responses contain only placeholder data and no real credentials.

def _mock_token() -> dict:
    return {"access_token": "mock-token", "token_type": "bearer", "expires_in": 3600}


def _mock_delete() -> dict:
    return {"code": "0", "msg": "", "data": []}


def _mock_create(passphrase: str, label: str, perm: str, bind_app: bool) -> dict:
    return {
        "code": "0",
        "msg": "",
        "data": [{
            "label": label,
            "apiKey": "mock-apikey-0000111122223333",
            "secretKey": "mock-secret",
            "passphrase": passphrase or "mock-passphrase",
            "perm": perm,
            "bindApp": bind_app,
        }],
    }


def _mock_balance(ccy: str = None) -> dict:
    details = [
        {"ccy": "USDT", "eq": "1000.5", "availBal": "950.0", "frozenBal": "50.5",
         "availEq": "950.0", "cashBal": "1000.5"},
        {"ccy": "BTC", "eq": "0.02", "availBal": "0.02", "frozenBal": "0",
         "availEq": "0.02", "cashBal": "0.02"},
    ]
    if ccy:
        wanted = {c.strip().upper() for c in ccy.split(",")}
        details = [d for d in details if d["ccy"] in wanted]
    return {
        "code": "0",
        "msg": "",
        "data": [{
            "uTime": "1700000000000",
            "totalEq": "1200.0",
            "isoEq": "0",
            "adjEq": "1180.0",
            "details": details,
        }],
    }


def _mock_ticker(inst_id: str) -> dict:
    return {
        "code": "0",
        "msg": "",
        "data": [{
            "instId": inst_id,
            "last": "100000",
            "bidPx": "99999.9",
            "askPx": "100000.1",
        }],
    }


def _mock_instruments(inst_type: str, inst_id: str) -> dict:
    item = {
        "instType": inst_type,
        "instId": inst_id,
        "state": "live",
        "tickSz": "0.1",
    }
    if inst_type == "SWAP":
        item.update({
            "ctType": "linear",
            "ctVal": "0.01",
            "ctValCcy": "BTC",
            "settleCcy": "USDT",
            "minSz": "0.01",
            "lotSz": "0.01",
        })
    else:
        item.update({"minSz": "0.00001", "lotSz": "0.00000001"})
    return {"code": "0", "msg": "", "data": [item]}


def _mock_config() -> dict:
    return {"code": "0", "msg": "", "data": [{"acctLv": "3", "posMode": "long_short_mode"}]}


def _mock_positions(inst_id: str = None) -> dict:
    return {
        "code": "0",
        "msg": "",
        "data": [{
            "instId": inst_id or "BTC-USDT-SWAP",
            "posSide": "long",
            "pos": "0.01",
            "avgPx": "100000",
            "upl": "0",
        }],
    }


def _mock_order(tag: str = "") -> dict:
    return {
        "code": "0",
        "msg": "",
        "data": [{
            "clOrdId": "",
            "ordId": "mock-ord-0000111122223333",
            "tag": tag or "",
            "sCode": "0",
            "sMsg": "",
        }],
    }


def _mock_close_position(tag: str = "") -> dict:
    return {
        "code": "0",
        "msg": "",
        "data": [{
            "instId": "BTC-USDT-SWAP",
            "tag": tag or "",
            "sCode": "0",
            "sMsg": "",
        }],
    }


def exchange_token(base_url: str, client_id: str, client_secret: str, code: str) -> dict:
    """Exchange OAuth authorization code for access_token. Fast API returns no refresh_token."""
    if _mock_enabled():
        return _mock_token()
    resp = requests.post(
        base_url + PATH_OAUTH_TOKEN,
        json={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=10,
    )
    if resp.status_code == 404:
        return {"_http_status": 404, "_hint": (
            "Token exchange returned 404. Real integration confirmed PATH_OAUTH_TOKEN "
            "as '/v5/users/oauth/token'. Check site domain, Broker permission, "
            "redirect_uri, client_id, and client_secret."
        )}
    return _parse(resp)


def delete_oauth_apikey(base_url: str, access_token: str, simulated: bool = True) -> dict:
    """Delete an existing Fast API Key before create. Caller should allow 59506."""
    if _mock_enabled():
        return _mock_delete()
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    if simulated:
        headers["x-simulated-trading"] = "1"
    resp = requests.post(base_url + PATH_OAUTH_DELETE, headers=headers, timeout=10)
    return _parse(resp)


def create_oauth_apikey(base_url: str, access_token: str, passphrase: str, label: str,
                        perm: str = "read_only", bind_app: bool = True,
                        simulated: bool = True) -> dict:
    """Create a Fast API Key. Response data[0] contains apiKey, secretKey, and passphrase."""
    if _mock_enabled():
        return _mock_create(passphrase, label, perm, bind_app)
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    if simulated:
        headers["x-simulated-trading"] = "1"
    body = {"label": label, "passphrase": passphrase, "perm": perm, "bindApp": bind_app}
    resp = requests.post(base_url + PATH_OAUTH_APIKEY, headers=headers, json=body, timeout=10)
    return _parse(resp)


def get_account_balance(base_url: str, api_key: str, secret_key: str, passphrase: str,
                        ccy: str = None, simulated: bool = True) -> dict:
    """
    Example business API: GET /api/v5/account/balance.
    ccy is optional and filters by one or more comma-separated currencies.
    """
    if _mock_enabled():
        return _mock_balance(_ccy_filter(ccy))
    method = "GET"
    request_path = _with_query(PATH_ACCOUNT_BAL, {"ccy": _ccy_filter(ccy)})
    body = ""
    ts = _now_iso_ms()
    headers = {
        "OK-ACCESS-KEY": api_key,
        "OK-ACCESS-SIGN": _sign(secret_key, ts, method, request_path, body),
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": passphrase,
        "Content-Type": "application/json",
    }
    if simulated:
        headers["x-simulated-trading"] = "1"
    # Send exactly the request_path that was signed. Do not use requests params= here.
    resp = requests.get(base_url + request_path, headers=headers, timeout=10)
    return _parse(resp)


def get_account_config(base_url: str, api_key: str, secret_key: str, passphrase: str,
                       simulated: bool = True) -> dict:
    """Example business API: GET /api/v5/account/config."""
    if _mock_enabled():
        return _mock_config()
    method = "GET"
    request_path = PATH_ACCOUNT_CONFIG
    body = ""
    ts = _now_iso_ms()
    headers = {
        "OK-ACCESS-KEY": api_key,
        "OK-ACCESS-SIGN": _sign(secret_key, ts, method, request_path, body),
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": passphrase,
        "Content-Type": "application/json",
    }
    if simulated:
        headers["x-simulated-trading"] = "1"
    return _parse(requests.get(base_url + request_path, headers=headers, timeout=10))


def get_positions(base_url: str, api_key: str, secret_key: str, passphrase: str,
                  inst_type: str = None, inst_id: str = None,
                  simulated: bool = True) -> dict:
    """Example business API: GET /api/v5/account/positions."""
    if _mock_enabled():
        return _mock_positions(inst_id)
    method = "GET"
    request_path = _with_query(PATH_ACCOUNT_POSITIONS, {
        "instType": inst_type,
        "instId": inst_id,
    })
    body = ""
    ts = _now_iso_ms()
    headers = {
        "OK-ACCESS-KEY": api_key,
        "OK-ACCESS-SIGN": _sign(secret_key, ts, method, request_path, body),
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": passphrase,
        "Content-Type": "application/json",
    }
    if simulated:
        headers["x-simulated-trading"] = "1"
    return _parse(requests.get(base_url + request_path, headers=headers, timeout=10))


def get_ticker(base_url: str, inst_id: str, simulated: bool = True) -> dict:
    """Example public API: GET /api/v5/market/ticker."""
    if _mock_enabled():
        return _mock_ticker(inst_id)
    request_path = _with_query(PATH_MARKET_TICKER, {"instId": inst_id})
    return _parse(requests.get(
        base_url + request_path,
        headers=_public_headers(simulated),
        timeout=10,
    ))


def get_instruments(base_url: str, inst_type: str, inst_id: str,
                    simulated: bool = True) -> dict:
    """Example public API: GET /api/v5/public/instruments."""
    if _mock_enabled():
        return _mock_instruments(inst_type, inst_id)
    request_path = _with_query(PATH_PUBLIC_INSTRUMENTS, {
        "instType": inst_type,
        "instId": inst_id,
    })
    return _parse(requests.get(
        base_url + request_path,
        headers=_public_headers(simulated),
        timeout=10,
    ))


def place_order(base_url: str, api_key: str, secret_key: str, passphrase: str,
                inst_id: str, td_mode: str, side: str, ord_type: str, sz: str,
                px: str = None, tgt_ccy: str = None, pos_side: str = None,
                reduce_only: bool = False, tag: str = None,
                simulated: bool = True) -> dict:
    """
    Example write API: POST /api/v5/trade/order.
    tag is the AI Builder Code attribution value and must be 1-16 alphanumeric characters.
    Live trading uses real funds; validate in simulated trading first.
    """
    if _mock_enabled():
        return _mock_order(tag)
    method = "POST"
    request_path = PATH_TRADE_ORDER
    body_obj = {"instId": inst_id, "tdMode": td_mode, "side": side,
                "ordType": ord_type, "sz": sz}
    if px not in (None, ""):
        body_obj["px"] = px
    if tgt_ccy not in (None, ""):
        body_obj["tgtCcy"] = tgt_ccy
    if pos_side not in (None, ""):
        body_obj["posSide"] = pos_side
    if reduce_only:
        body_obj["reduceOnly"] = "true"
    if tag not in (None, ""):
        body_obj["tag"] = tag
    # Use the same serialized body for signing and sending.
    body = json.dumps(body_obj)
    ts = _now_iso_ms()
    headers = {
        "OK-ACCESS-KEY": api_key,
        "OK-ACCESS-SIGN": _sign(secret_key, ts, method, request_path, body),
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": passphrase,
        "Content-Type": "application/json",
    }
    if simulated:
        headers["x-simulated-trading"] = "1"
    # Send data=body so the HTTP request body exactly matches the signed body string.
    resp = requests.post(base_url + request_path, headers=headers, data=body, timeout=10)
    return _parse(resp)


def close_position(base_url: str, api_key: str, secret_key: str, passphrase: str,
                   inst_id: str, mgn_mode: str, pos_side: str = None,
                   auto_cxl: bool = True, tag: str = None,
                   simulated: bool = True) -> dict:
    """
    Example write API: POST /api/v5/trade/close-position.
    tag is the AI Builder Code attribution value for the close-position order.
    """
    if _mock_enabled():
        return _mock_close_position(tag)
    method = "POST"
    request_path = PATH_TRADE_CLOSE_POSITION
    body_obj = {"instId": inst_id, "mgnMode": mgn_mode, "autoCxl": str(auto_cxl).lower()}
    if pos_side not in (None, ""):
        body_obj["posSide"] = pos_side
    if tag not in (None, ""):
        body_obj["tag"] = tag
    body = json.dumps(body_obj)
    ts = _now_iso_ms()
    headers = {
        "OK-ACCESS-KEY": api_key,
        "OK-ACCESS-SIGN": _sign(secret_key, ts, method, request_path, body),
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": passphrase,
        "Content-Type": "application/json",
    }
    if simulated:
        headers["x-simulated-trading"] = "1"
    resp = requests.post(
        base_url + request_path,
        headers=headers,
        data=body,
        timeout=10,
    )
    return _parse(resp)
