"""
Unit tests for okx_client signing and timestamp helpers. No network calls.

Focus:
  - _sign known-answer regression.
  - Prehash order: timestamp + METHOD + requestPathWithQuery + body.
  - Valid base64(HMAC-SHA256).
  - GET query string must be included in the signed path.
  - _now_iso_ms returns ISO8601 UTC with 3-digit milliseconds and trailing Z.
"""
import base64
import hashlib
import hmac
import re

import okx_client as okx


SECRET = "mock-secret"
TS = "2020-12-08T09:08:57.715Z"
PATH = "/api/v5/account/balance"

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
    sig = okx._sign(SECRET, TS, "GET", PATH + "?ccy=BTC", "")
    assert sig == KNOWN_SIG_WITH_QUERY
    assert sig != KNOWN_SIG_NO_QUERY


def test_sign_prehash_order_and_base64():
    body = '{"a":1}'
    sig = okx._sign(SECRET, TS, "post", PATH, body)
    assert sig == _expected(SECRET, TS, "POST", PATH, body)
    assert len(base64.b64decode(sig)) == 32


def test_sign_method_uppercased():
    assert okx._sign(SECRET, TS, "get", PATH, "") == okx._sign(SECRET, TS, "GET", PATH, "")


def test_sign_changes_with_each_field():
    base = okx._sign(SECRET, TS, "GET", PATH, "")
    assert okx._sign("other-secret", TS, "GET", PATH, "") != base
    assert okx._sign(SECRET, "2021-01-01T00:00:00.000Z", "GET", PATH, "") != base
    assert okx._sign(SECRET, TS, "GET", PATH, '{"x":1}') != base


def test_now_iso_ms_format():
    ts = okx._now_iso_ms()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", ts), ts
    assert ts.endswith("Z")
    assert len(ts.split(".")[1]) == 4
