"""
test_sign.py — okx_client 签名与时间戳的单元测试（不发网络）。

重点：
  - _sign 的 known-answer 回归（固定 secret/ts/method/path/body → 固定签名）
  - prehash 拼接顺序：timestamp + METHOD(大写) + requestPath(含 query) + body
  - base64(HMAC-SHA256) 正确
  - GET 带 query 时 path 必须含 query（影响签名）
  - _now_iso_ms 为 ISO8601 毫秒 UTC，以 Z 结尾
"""
import base64
import hashlib
import hmac
import re

import okx_client as okx

# ---- 固定测试向量（与生产无关的占位值）----
SECRET = "mock-secret"
TS = "2020-12-08T09:08:57.715Z"
PATH = "/api/v5/account/balance"

# 由 base64(HMAC-SHA256(secret, ts+"GET"+path+"")) 离线算出，作为回归基准
KNOWN_SIG_NO_QUERY = "tpQYvXdaAfU8ae6zI1rJ2xVcyMIk9BKWK/fysaanweQ="
KNOWN_SIG_WITH_QUERY = "pS6nHuBl6Qc9S0h+soCkCVHaVHZzS19KqFpeI/doTlE="


def _expected(secret, ts, method, path, body):
    prehash = f"{ts}{method}{path}{body}"
    return base64.b64encode(
        hmac.new(secret.encode(), prehash.encode(), hashlib.sha256).digest()
    ).decode()


def test_sign_known_answer_no_query():
    sig = okx._sign(SECRET, TS, "GET", PATH, "")
    assert sig == KNOWN_SIG_NO_QUERY


def test_sign_known_answer_with_query():
    # 带 query 时 path 必须含 ?ccy=BTC，签名因此不同于不带 query
    sig = okx._sign(SECRET, TS, "GET", PATH + "?ccy=BTC", "")
    assert sig == KNOWN_SIG_WITH_QUERY
    assert sig != KNOWN_SIG_NO_QUERY


def test_sign_prehash_order_and_base64():
    # 与独立实现逐项比对，确认拼接顺序 timestamp+METHOD+path+body 与 base64 编码
    body = '{"a":1}'
    sig = okx._sign(SECRET, TS, "post", PATH, body)  # 传小写 post 验证内部 upper()
    assert sig == _expected(SECRET, TS, "POST", PATH, body)
    # 结果是合法 base64，且解码后为 32 字节（SHA256 摘要）
    assert len(base64.b64decode(sig)) == 32


def test_sign_method_uppercased():
    # method 大小写不影响结果（内部强制大写）
    assert okx._sign(SECRET, TS, "get", PATH, "") == okx._sign(SECRET, TS, "GET", PATH, "")


def test_sign_changes_with_each_field():
    base = okx._sign(SECRET, TS, "GET", PATH, "")
    assert okx._sign("other-secret", TS, "GET", PATH, "") != base
    assert okx._sign(SECRET, "2021-01-01T00:00:00.000Z", "GET", PATH, "") != base
    assert okx._sign(SECRET, TS, "GET", PATH, '{"x":1}') != base


def test_now_iso_ms_format():
    ts = okx._now_iso_ms()
    # 形如 2020-12-08T09:08:57.715Z：毫秒 3 位，以 Z 结尾
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", ts), ts
    assert ts.endswith("Z")
    # 小数点后是「3 位毫秒 + 结尾 Z」共 4 个字符（如 "715Z"）
    assert len(ts.split(".")[1]) == 4
