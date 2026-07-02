"""
app.py — OKX Fast API 接入参考后端（Flask）。

完整链路：
  浏览器授权(scope=fast_api) → 回调带 code → 后端用 client_secret 换 access_token
    → 删除旧 Key(避免 50116) → 创建 Fast API Key(存后端)
    → 用 API Key 做 OKX 标准签名调用 GET /api/v5/account/balance 查余额

运行：
  cp .env.example .env        # 填 CLIENT_ID / CLIENT_SECRET / REDIRECT_URI / APIKEY_PASSPHRASE
  pip install -r requirements.txt
  python backend/app.py       # 从仓库根目录运行（不要用 python -m）
  浏览器打开 http://localhost:8000
"""

import os
import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

import okx_client as okx

load_dotenv()

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
app = Flask(__name__, static_folder=None)

# ---- 配置：全部来自环境变量，禁止在代码里硬编码密钥 ----
CLIENT_ID         = os.environ.get("CLIENT_ID", "")
CLIENT_SECRET     = os.environ.get("CLIENT_SECRET", "")
REDIRECT_URI      = os.environ.get("REDIRECT_URI", "http://localhost:8000/")
SCOPE             = os.environ.get("SCOPE", "fast_api")
OKX_BASE_URL      = os.environ.get("OKX_BASE_URL", "https://www.okx.com")
SIMULATED         = os.environ.get("SIMULATED", "1") == "1"        # 默认模拟盘，安全
MOCK              = os.environ.get("MOCK", "") == "1"              # MOCK=1：不发真实 HTTP，走假响应
APIKEY_PASSPHRASE = os.environ.get("APIKEY_PASSPHRASE", "")
APIKEY_LABEL      = os.environ.get("APIKEY_LABEL", "demo")
APIKEY_PERM       = os.environ.get("APIKEY_PERM", "read_only")     # 默认只读，安全

# OKX 合法域名白名单。回跳 URL 里的 domain 来自外部输入，必须校验后才能当 base_url，
# 否则攻击者可诱导后端把 access_token / 请求发往任意服务器（SSRF / 凭证外泄）。
ALLOWED_DOMAINS = {"https://www.okx.com", "https://tr.okx.com", "https://eea.okx.com"}

# ---- DEMO ONLY：进程内、按浏览器 session 隔离地存储 API Key ----
# ⚠️ 这只是演示：生产必须按用户加密落库；进程重启即丢失。
#    用 session 隔离（而非单个全局变量）是为了避免多用户/多标签页互相覆盖、查到别人余额。
_CREDS = {}  # {session_id: {"api_key","secret_key","passphrase","base"}}


def _get_or_create_sid() -> str:
    return request.cookies.get("demo_sid") or uuid.uuid4().hex


@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/config")
def config():
    """给前端授权页用的公开配置。client_id 属公开信息可入前端；secret 永不下发。"""
    return jsonify({
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "simulated": SIMULATED,
        "mock": MOCK,
    })


@app.post("/api/connect")
def connect():
    """
    收前端回调拿到的 code，完成：换 token → 删旧 Key → 建 Key → 存后端。
    安全：secretKey / passphrase 不返回前端；失败时只回 code/msg/hint，不透传上游原始响应。
    """
    data = request.get_json(force=True) or {}
    code = data.get("code")
    domain = data.get("domain")  # 回调可能返回 https://eea.okx.com，需用该域名后续调用
    if not code:
        return jsonify({"ok": False, "error": "missing code"}), 400

    # 域名白名单校验：非法 domain 一律回退到配置的默认站点
    base = domain if domain in ALLOWED_DOMAINS else OKX_BASE_URL

    # 1) 授权码换 access_token
    tok = okx.exchange_token(base, CLIENT_ID, CLIENT_SECRET, code)
    access_token = tok.get("access_token")
    if not access_token:
        return jsonify({"ok": False, "step": "exchange_token",
                        "code": tok.get("code"), "msg": tok.get("msg"),
                        "hint": tok.get("_hint"), "http": tok.get("_http_status")}), 400

    # 2) 删除旧 Key（避免 50116）。code=0 删除成功 / 59506 不存在 → 均放行；其它错误中断。
    deleted = okx.delete_oauth_apikey(base, access_token, simulated=SIMULATED)
    if deleted.get("code") not in ("0", "59506"):
        return jsonify({"ok": False, "step": "delete_apikey",
                        "code": deleted.get("code"), "msg": deleted.get("msg")}), 400

    # 3) 创建 Fast API Key
    created = okx.create_oauth_apikey(
        base, access_token, APIKEY_PASSPHRASE, APIKEY_LABEL,
        perm=APIKEY_PERM, bind_app=False, simulated=SIMULATED,
    )
    if created.get("code") != "0" or not created.get("data"):
        return jsonify({"ok": False, "step": "create_apikey",
                        "code": created.get("code"), "msg": created.get("msg")}), 400

    k = created["data"][0]
    # 4) 按 session 存后端（DEMO 用内存；生产请加密落库、按用户隔离）
    sid = _get_or_create_sid()
    _CREDS[sid] = {
        "api_key":    k["apiKey"],
        "secret_key": k["secretKey"],
        "passphrase": k.get("passphrase") or APIKEY_PASSPHRASE,
        "base":       base,
    }

    masked = k["apiKey"][:4] + "****" + k["apiKey"][-4:]
    resp = jsonify({"ok": True, "api_key_masked": masked,
                    "perm": k.get("perm"), "simulated": SIMULATED})
    # httponly cookie 仅作 demo 的 session 标识；本地 http 未加 Secure，生产应加 Secure。
    resp.set_cookie("demo_sid", sid, httponly=True, samesite="Lax")
    return resp


@app.get("/api/balance")
def balance():
    """用当前 session 已存的 API Key 签名调用账户余额接口（示例业务调用）。"""
    creds = _CREDS.get(request.cookies.get("demo_sid", ""))
    if not creds:
        return jsonify({"ok": False, "error": "not connected yet"}), 400
    ccy = request.args.get("ccy")  # 可选，按币种过滤
    res = okx.get_account_balance(
        creds["base"], creds["api_key"], creds["secret_key"],
        creds["passphrase"], ccy=ccy, simulated=SIMULATED,
    )
    # 余额是用户自己的数据，这里整体返回便于 demo 展示；生产按需做字段白名单。
    return jsonify({"ok": res.get("code") == "0", "raw": res})


if __name__ == "__main__":
    # debug=True 仅本地用：会暴露交互式调试器，生产务必关闭。
    app.run(host="127.0.0.1", port=8000, debug=True)
