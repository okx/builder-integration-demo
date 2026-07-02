"""
okx_client.py — OKX Fast API 接入所需的全部 HTTP 调用与签名逻辑。

分两类调用：
  1) OAuth / Fast API 管理接口（用 access_token 的 Bearer 鉴权）
       - exchange_token        用授权码换 access_token
       - delete_oauth_apikey   删除已存在的 Fast API Key（避免 50116）
       - create_oauth_apikey   为用户创建 Fast API Key
  2) 业务接口（用创建出来的 API Key 做 OKX 标准 HMAC 签名鉴权）
       - get_account_balance   GET /api/v5/account/balance 查询账户余额（只读）

安全约定：
  - client_secret、创建出来的 secretKey/passphrase 仅在后端使用，
    绝不返回前端、绝不写日志、绝不硬编码（全部来自环境变量 / 运行时存储）。
"""

import base64
import hashlib
import hmac
import os
from datetime import datetime, timezone

import requests

# ---- Mock 模式开关 ----
# MOCK=1 时，下面四个对外接口不发真实 HTTP，直接返回预置的 OKX 假响应，
# 让没有 Broker 凭证的人也能把整条前端流程跑通看效果。
# 注意：仅当函数被调用时实时读取 os.environ（而非模块加载时固化），
#       这样测试 / 运行时可动态设置，且对真实路径零侵入。
def _mock_enabled() -> bool:
    return os.environ.get("MOCK", "") == "1"

# ---- OKX 标准 API 路径（已与开发者文档核对）----
PATH_OAUTH_TOKEN  = "/api/v5/users/oauth/token"          # 换取 access_token（授权码模式）
PATH_OAUTH_DELETE = "/api/v5/users/oauth/delete-apikey"  # 删除 Fast API Key
PATH_OAUTH_APIKEY = "/api/v5/users/oauth/apikey"         # 创建 Fast API Key
PATH_ACCOUNT_BAL  = "/api/v5/account/balance"            # 示例业务接口：查询账户余额
# 注：开发者文档 “REST API > 获取令牌” 段落写的是 /v5/users/oauth/token，
#     而 changelog 与 删/建 Key 接口均为 /api/v5/...。这里与后两者保持一致（默认值）。
#     若联调换 token 时报 404，把上面 PATH_OAUTH_TOKEN 改成 "/v5/users/oauth/token" 再试。
#     （exchange_token 已对 404 给出指向性提示，不做静默自动重试，避免掩盖真实错误。）


def _now_iso_ms() -> str:
    """OKX 签名要求的 ISO8601 毫秒时间戳，如 2020-12-08T09:08:57.715Z"""
    now = datetime.now(timezone.utc)  # 只取一次，避免整秒边界跨秒竞态
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _sign(secret_key: str, timestamp: str, method: str, request_path: str, body: str) -> str:
    """OKX 标准签名：base64( HMAC-SHA256( secret, timestamp + method + path + body ) )"""
    prehash = f"{timestamp}{method.upper()}{request_path}{body}"
    digest = hmac.new(secret_key.encode(), prehash.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _parse(resp: requests.Response) -> dict:
    """
    统一解析 OKX 响应。OKX 正常返回 JSON；但 404(路径错)、502(网关)、429(限速)
    等可能返回 HTML/纯文本，直接 .json() 会抛 JSONDecodeError 造成静默 500。
    这里兜底成结构化错误，让上层能看到 HTTP 状态与片段。
    """
    try:
        return resp.json()
    except ValueError:
        return {"_http_status": resp.status_code, "_non_json_body": resp.text[:300]}


# ============ Mock 响应（仅 MOCK=1 时使用，结构贴合真实 OKX 返回） ============
# 这些都是写死的假占位数据，不含任何真实凭证。"mock-secret" 是占位字符串，不是密钥。

def _mock_token() -> dict:
    # 真实换 token 返回结构（Fast API 无 refresh_token）
    return {"access_token": "mock-token", "token_type": "bearer", "expires_in": 3600}


def _mock_delete() -> dict:
    # 真实删除成功返回 code=0；若 Key 不存在则 59506。这里固定返回成功。
    return {"code": "0", "msg": "", "data": []}


def _mock_create(passphrase: str, label: str, perm: str, bind_app: bool) -> dict:
    # 真实创建返回 data[0] 含 apiKey / secretKey / passphrase / perm / bindApp。
    # secretKey 用假占位字符串，绝非真实凭证。
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
    # 贴合 GET /api/v5/account/balance 真实结构（已精简，字段名与官方一致）。
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


# ============ 1) OAuth / Fast API 管理接口（Bearer 鉴权） ============

def exchange_token(base_url: str, client_id: str, client_secret: str, code: str) -> dict:
    """步骤三：用授权码换取 access_token。Fast API 返回结果无 refresh_token。"""
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
        # 已知文档路径不一致点：直接告诉调用方改哪一行，而不是静默换路径重试
        return {"_http_status": 404, "_hint": (
            "换 token 返回 404。请把 okx_client.py 的 PATH_OAUTH_TOKEN 在 "
            "'/api/v5/users/oauth/token' 与 '/v5/users/oauth/token' 之间切换后重试。"
        )}
    # 返回示例：{"access_token": "...", "token_type": "bearer", "expires_in": 3600}（无 refresh_token）
    return _parse(resp)


def delete_oauth_apikey(base_url: str, access_token: str, simulated: bool = True) -> dict:
    """步骤四：删除已有 Fast API Key，避免 50116。报 59506(不存在) 属正常，由调用方放行。"""
    if _mock_enabled():
        return _mock_delete()
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    if simulated:
        headers["x-simulated-trading"] = "1"
    resp = requests.post(base_url + PATH_OAUTH_DELETE, headers=headers, timeout=10)
    return _parse(resp)


def create_oauth_apikey(base_url: str, access_token: str, passphrase: str, label: str,
                        perm: str = "read_only", bind_app: bool = False,
                        simulated: bool = True) -> dict:
    """步骤五：为用户创建 Fast API Key。返回 data[0] 含 apiKey / secretKey / passphrase。"""
    if _mock_enabled():
        return _mock_create(passphrase, label, perm, bind_app)
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    if simulated:
        headers["x-simulated-trading"] = "1"
    body = {"label": label, "passphrase": passphrase, "perm": perm, "bindApp": bind_app}
    resp = requests.post(base_url + PATH_OAUTH_APIKEY, headers=headers, json=body, timeout=10)
    return _parse(resp)


# ============ 2) 业务接口（API Key HMAC 签名鉴权） ============

def get_account_balance(base_url: str, api_key: str, secret_key: str, passphrase: str,
                        ccy: str = None, simulated: bool = True) -> dict:
    """
    示例业务接口：GET /api/v5/account/balance 查询交易账户余额（权限：只读）。
    演示如何用创建出来的 API Key 做 OKX 标准签名调用。
    ccy: 可选，按币种过滤（多个用半角逗号，不超过 20 个）。
    """
    if _mock_enabled():
        return _mock_balance(ccy)
    method = "GET"
    request_path = PATH_ACCOUNT_BAL
    if ccy:
        request_path += f"?ccy={ccy}"
    body = ""  # GET 请求 body 用空字符串参与签名
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
    # ⚠️ 必须用 base_url + request_path 直接发，不要改用 requests 的 params=！
    #    query（如 ?ccy=BTC）必须与上面签名用的 request_path 逐字一致，
    #    否则 requests 自行拼接/编码会导致签名串不匹配 → 签名校验失败(如 50113)。
    resp = requests.get(base_url + request_path, headers=headers, timeout=10)
    return _parse(resp)
