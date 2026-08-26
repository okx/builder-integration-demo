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

Note on `simulated`:
  simulated=True sends the OKX `x-simulated-trading: 1` header. This is a real
  OKX API call against the demo-trading environment, not a mock or fake response.

Testing:
  These functions make real HTTP calls via `requests`. Tests stub the module's
  functions (or `requests`) at the test layer with monkeypatch — there is no
  in-code mock switch here.
"""

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests


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


def exchange_token(base_url: str, client_id: str, client_secret: str, code: str) -> dict:
    """Exchange OAuth authorization code for access_token. Fast API returns no refresh_token."""
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
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    if simulated:
        headers["x-simulated-trading"] = "1"
    resp = requests.post(base_url + PATH_OAUTH_DELETE, headers=headers, timeout=10)
    return _parse(resp)


def create_oauth_apikey(base_url: str, access_token: str, passphrase: str, label: str,
                        perm: str = "read_only", bind_app: bool = True,
                        simulated: bool = True) -> dict:
    """Create a Fast API Key. Response data[0] contains apiKey, secretKey, and passphrase."""
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
    request_path = _with_query(PATH_MARKET_TICKER, {"instId": inst_id})
    return _parse(requests.get(
        base_url + request_path,
        headers=_public_headers(simulated),
        timeout=10,
    ))


def get_instruments(base_url: str, inst_type: str, inst_id: str,
                    simulated: bool = True) -> dict:
    """Example public API: GET /api/v5/public/instruments."""
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
    # Default json.dumps (with spaces) is intentional; the same serialized string is signed and sent.
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
    method = "POST"
    request_path = PATH_TRADE_CLOSE_POSITION
    body_obj = {"instId": inst_id, "mgnMode": mgn_mode, "autoCxl": str(auto_cxl).lower()}
    if pos_side not in (None, ""):
        body_obj["posSide"] = pos_side
    if tag not in (None, ""):
        body_obj["tag"] = tag
    # Default json.dumps (with spaces) is intentional; the same serialized string is signed and sent.
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
