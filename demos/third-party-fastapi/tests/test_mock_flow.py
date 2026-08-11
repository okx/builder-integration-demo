"""
Smoke tests for the full MOCK flow without real HTTP.

Uses Flask test client for /config -> /api/connect -> /api/balance and verifies:
  - MOCK=1 works without real Broker credentials.
  - Successful connect returns ok=True and a masked apiKey.
  - secretKey and passphrase do not appear in any response.
  - Balance response includes totalEq and details.
  - Demo spot/swap workflow routes inject AI Builder Code as OKX tag.
"""
import json
import importlib
from unittest.mock import Mock

import pytest


def _set_common_env(monkeypatch, ai_builder_code="ABCD1234", simulated="1",
                    api_key_perm="read_only", mock="1"):
    if mock is None:
        monkeypatch.delenv("MOCK", raising=False)
    else:
        monkeypatch.setenv("MOCK", mock)
    if ai_builder_code is None:
        # Keep local .env values from leaking into tests after app.load_dotenv().
        monkeypatch.setenv("AI_BUILDER_CODE", "")
    else:
        monkeypatch.setenv("AI_BUILDER_CODE", ai_builder_code)
    monkeypatch.setenv("SIMULATED", simulated)
    monkeypatch.setenv("APIKEY_PERM", api_key_perm)
    monkeypatch.setenv("OKX_BASE_URL", "https://www.okx.com")
    monkeypatch.setenv("CLIENT_ID", "")
    monkeypatch.setenv("CLIENT_SECRET", "")
    monkeypatch.setenv("APIKEY_LABEL", "demo")
    monkeypatch.setenv("APIKEY_PASSPHRASE", "MockPassphrase1!")


@pytest.fixture()
def client(monkeypatch):
    _set_common_env(monkeypatch, api_key_perm="trade")
    # app.py reads environment variables at import time, so reload after setting env.
    import app as app_module
    importlib.reload(app_module)
    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture()
def read_only_client(monkeypatch):
    _set_common_env(monkeypatch, api_key_perm="read_only")
    # app.py reads environment variables at import time, so reload after setting env.
    import app as app_module
    importlib.reload(app_module)
    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture()
def client_without_ai_builder_code(monkeypatch):
    _set_common_env(monkeypatch, ai_builder_code=None, api_key_perm="trade")
    import app as app_module
    importlib.reload(app_module)
    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture()
def client_with_invalid_ai_builder_code(monkeypatch):
    _set_common_env(monkeypatch, ai_builder_code="bad-code!", api_key_perm="trade")
    import app as app_module
    importlib.reload(app_module)
    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture()
def live_client(monkeypatch):
    _set_common_env(monkeypatch, simulated="0", api_key_perm="trade")
    import app as app_module
    importlib.reload(app_module)
    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as c:
        yield c


def test_config_reports_mock(client):
    cfg = client.get("/config").get_json()
    assert cfg["mock"] is True
    assert cfg["simulated"] is True
    assert cfg["okx_base_url"] == "https://www.okx.com"
    assert cfg["ai_builder_code"] == "ABCD1234"


def test_full_mock_flow_and_no_secret_leak(read_only_client):
    connect = read_only_client.post("/api/connect", json={"code": "mock-code"})
    body = connect.get_json()
    assert connect.status_code == 200
    assert body["ok"] is True
    assert body["perm"] == "read_only"
    assert body["simulated"] is True
    assert "****" in body["api_key_masked"]

    raw = connect.get_data(as_text=True)
    assert "mock-secret" not in raw
    assert "secretKey" not in raw
    assert "passphrase" not in raw

    bal = read_only_client.get("/api/balance")
    bal_body = bal.get_json()
    assert bal.status_code == 200
    assert bal_body["ok"] is True
    data = bal_body["raw"]["data"][0]
    assert "totalEq" in data
    assert any(d["ccy"] == "USDT" for d in data["details"])

    assert "mock-secret" not in bal.get_data(as_text=True)


def test_balance_requires_connect_first(read_only_client):
    fresh = read_only_client.get("/api/balance")
    assert fresh.status_code == 400
    assert fresh.get_json()["ok"] is False


def test_connect_rejects_placeholder_passphrase_before_external_calls(monkeypatch):
    _set_common_env(monkeypatch, api_key_perm="trade")
    monkeypatch.setenv("APIKEY_PASSPHRASE", "<SET_A_STRONG_PASSPHRASE>")

    import app as app_module
    importlib.reload(app_module)

    exchange_token = Mock(side_effect=AssertionError("exchange_token should not be called"))
    delete_apikey = Mock(side_effect=AssertionError("delete_oauth_apikey should not be called"))
    create_apikey = Mock(side_effect=AssertionError("create_oauth_apikey should not be called"))
    monkeypatch.setattr(app_module.okx, "exchange_token", exchange_token)
    monkeypatch.setattr(app_module.okx, "delete_oauth_apikey", delete_apikey)
    monkeypatch.setattr(app_module.okx, "create_oauth_apikey", create_apikey)
    app_module.app.config.update(TESTING=True)

    with app_module.app.test_client() as c:
        response = c.post("/api/connect", json={"code": "mock-code"})

    body = response.get_json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert body["step"] == "validate_config"
    assert "APIKEY_PASSPHRASE" in body["error"]
    exchange_token.assert_not_called()
    delete_apikey.assert_not_called()
    create_apikey.assert_not_called()


def test_connect_rejects_unknown_callback_domain_before_external_calls(monkeypatch):
    _set_common_env(monkeypatch, api_key_perm="trade")

    import app as app_module
    importlib.reload(app_module)

    exchange_token = Mock(side_effect=AssertionError("exchange_token should not be called"))
    monkeypatch.setattr(app_module.okx, "exchange_token", exchange_token)
    app_module.app.config.update(TESTING=True)

    with app_module.app.test_client() as c:
        response = c.post("/api/connect", json={
            "code": "mock-code",
            "domain": "https://evil.example",
        })

    body = response.get_json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert body["step"] == "validate_config"
    assert body["error"] == "callback domain is not allowlisted: https://evil.example"
    exchange_token.assert_not_called()


def test_connect_rejects_invalid_default_base_url_before_external_calls(monkeypatch):
    _set_common_env(monkeypatch, api_key_perm="trade")
    monkeypatch.setenv("OKX_BASE_URL", "https://evil.example")

    import app as app_module
    importlib.reload(app_module)

    exchange_token = Mock(side_effect=AssertionError("exchange_token should not be called"))
    monkeypatch.setattr(app_module.okx, "exchange_token", exchange_token)
    app_module.app.config.update(TESTING=True)

    with app_module.app.test_client() as c:
        response = c.post("/api/connect", json={"code": "mock-code"})

    body = response.get_json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert body["step"] == "validate_config"
    assert body["error"] == "OKX_BASE_URL is not allowlisted: https://evil.example"
    exchange_token.assert_not_called()


def test_real_connect_requires_oauth_credentials_before_external_calls(monkeypatch):
    _set_common_env(monkeypatch, api_key_perm="trade", mock=None)

    import app as app_module
    importlib.reload(app_module)

    exchange_token = Mock(side_effect=AssertionError("exchange_token should not be called"))
    monkeypatch.setattr(app_module.okx, "exchange_token", exchange_token)
    app_module.app.config.update(TESTING=True)

    with app_module.app.test_client() as c:
        response = c.post("/api/connect", json={"code": "real-code"})

    body = response.get_json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert body["step"] == "validate_config"
    assert body["error"] == "CLIENT_ID must be configured before real OAuth connect"
    exchange_token.assert_not_called()


def test_real_connect_rejects_uppercase_oauth_placeholders_before_external_calls(monkeypatch):
    _set_common_env(monkeypatch, api_key_perm="trade", mock=None)
    monkeypatch.setenv("CLIENT_ID", "YOUR_CLIENT_ID")
    monkeypatch.setenv("CLIENT_SECRET", "YOUR_CLIENT_SECRET")

    import app as app_module
    importlib.reload(app_module)

    exchange_token = Mock(side_effect=AssertionError("exchange_token should not be called"))
    monkeypatch.setattr(app_module.okx, "exchange_token", exchange_token)
    app_module.app.config.update(TESTING=True)

    with app_module.app.test_client() as c:
        response = c.post("/api/connect", json={"code": "real-code"})

    body = response.get_json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert body["step"] == "validate_config"
    assert body["error"] == "CLIENT_ID must be configured before real OAuth connect"
    exchange_token.assert_not_called()


def test_connect_accepts_allowlisted_callback_domain_with_trailing_slash(client):
    connect = client.post("/api/connect", json={
        "code": "mock-code",
        "domain": "https://www.okx.com/",
    })
    body = connect.get_json()
    assert connect.status_code == 200
    assert body["ok"] is True


def test_balance_ccy_filter(read_only_client):
    read_only_client.post("/api/connect", json={"code": "mock-code"})
    bal = read_only_client.get("/api/balance?ccy=BTC").get_json()
    details = bal["raw"]["data"][0]["details"]
    assert [d["ccy"] for d in details] == ["BTC"]


def test_workflow_rejects_read_only_key(read_only_client):
    read_only_client.post("/api/connect", json={"code": "mock-code"})
    response = read_only_client.post("/api/spot/open", json={
        "instId": "BTC-USDT",
        "quoteAmount": "10",
    })
    body = response.get_json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert body["error"] == "created API Key does not have trade permission"


def test_trade_mode_helpers_cover_account_mode_matrix(client):
    import app as app_module

    assert app_module._spot_td_mode(None, {"code": "0", "data": [{"acctLv": "1"}]}) == "cash"
    assert app_module._spot_td_mode(None, {"code": "0", "data": [{"acctLv": "2"}]}) == "cash"
    assert app_module._spot_td_mode(None, {"code": "0", "data": [{"acctLv": "3"}]}) == "cross"
    assert app_module._spot_td_mode(None, {"code": "0", "data": [{"acctLv": "4"}]}) == "cross"
    assert app_module._swap_td_mode(None, {"code": "0", "data": [{"acctLv": "2"}]}) == "cross"
    assert app_module._swap_td_mode(None, {"code": "0", "data": [{"acctLv": "4"}]}) == "cross"
    with pytest.raises(ValueError):
        app_module._swap_td_mode(None, {"code": "0", "data": [{"acctLv": "1"}]})


def test_order_injects_ai_builder_code_as_tag(client):
    client.post("/api/connect", json={"code": "mock-code"})
    order = client.post("/api/order", json={
        "instId": "BTC-USDT",
        "side": "buy",
        "ordType": "limit",
        "px": "1000",
        "sz": "0.00000001",
    })
    body = order.get_json()
    assert order.status_code == 200
    assert body["sent_ai_builder_code"] == "ABCD1234"
    assert body["raw"]["data"][0]["tag"] == "ABCD1234"


def test_order_parses_false_reduce_only(client, monkeypatch):
    client.post("/api/connect", json={"code": "mock-code"})
    import app as app_module

    captured = {}

    def fake_place_order(*args, **kwargs):
        captured.update(kwargs)
        return {"code": "0", "data": [{"tag": kwargs.get("tag")}]}

    monkeypatch.setattr(app_module.okx, "place_order", fake_place_order)
    order = client.post("/api/order", json={
        "instId": "BTC-USDT-SWAP",
        "tdMode": "cross",
        "side": "sell",
        "ordType": "market",
        "sz": "1",
        "reduceOnly": "false",
    })
    assert order.status_code == 200
    assert captured["reduce_only"] is False


def test_live_order_requires_confirmation(live_client, monkeypatch):
    live_client.post("/api/connect", json={"code": "mock-code"})
    import app as app_module

    def fail_place_order(*args, **kwargs):
        raise AssertionError("place_order should not be called without live confirmation")

    monkeypatch.setattr(app_module.okx, "place_order", fail_place_order)
    order = live_client.post("/api/order", json={
        "instId": "BTC-USDT",
        "side": "buy",
        "ordType": "market",
        "sz": "1",
    })
    body = order.get_json()
    assert order.status_code == 400
    assert body["ok"] is False
    assert body["error"] == "live workflow requires confirmLiveOrder=true"


def test_okx_client_place_order_serializes_tag_and_optional_fields(monkeypatch):
    import okx_client as okx

    monkeypatch.delenv("MOCK", raising=False)
    monkeypatch.setattr(okx, "_now_iso_ms", lambda: "2020-01-01T00:00:00.000Z")
    captured = {}

    class FakeResponse:
        status_code = 200
        text = '{"code":"0","data":[{"sCode":"0"}]}'

        def json(self):
            return {"code": "0", "data": [{"sCode": "0"}]}

    def fake_post(url, headers=None, data=None, timeout=None, **kwargs):
        captured.update({"url": url, "headers": headers, "data": data, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr(okx.requests, "post", fake_post)
    okx.place_order(
        "https://www.okx.com", "api", "secret", "pass",
        "BTC-USDT-SWAP", "cross", "sell", "market", "1",
        tgt_ccy="quote_ccy", pos_side="long", reduce_only=True,
        tag="ABCD1234", simulated=True,
    )

    body = json.loads(captured["data"])
    assert body["tag"] == "ABCD1234"
    assert body["tgtCcy"] == "quote_ccy"
    assert body["posSide"] == "long"
    assert body["reduceOnly"] == "true"
    assert captured["headers"]["x-simulated-trading"] == "1"


def test_okx_client_close_position_serializes_tag_and_optional_fields(monkeypatch):
    import okx_client as okx

    monkeypatch.delenv("MOCK", raising=False)
    monkeypatch.setattr(okx, "_now_iso_ms", lambda: "2020-01-01T00:00:00.000Z")
    captured = {}

    class FakeResponse:
        status_code = 200
        text = '{"code":"0","data":[{}]}'

        def json(self):
            return {"code": "0", "data": [{}]}

    def fake_post(url, headers=None, data=None, timeout=None, **kwargs):
        captured.update({"url": url, "headers": headers, "data": data, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr(okx.requests, "post", fake_post)
    okx.close_position(
        "https://www.okx.com", "api", "secret", "pass",
        "BTC-USDT-SWAP", "cross",
        pos_side="long", auto_cxl=False, tag="ABCD1234", simulated=True,
    )

    body = json.loads(captured["data"])
    assert captured["url"] == "https://www.okx.com/api/v5/trade/close-position"
    assert body["tag"] == "ABCD1234"
    assert body["posSide"] == "long"
    assert body["autoCxl"] == "false"
    assert captured["headers"]["x-simulated-trading"] == "1"


@pytest.mark.parametrize("path,workflow,payload", [
    ("/api/spot/open", "spot-open", {
        "instId": "BTC-USDT", "quoteAmount": "10",
    }),
    ("/api/spot/close", "spot-close", {
        "instId": "BTC-USDT", "quoteAmount": "10",
    }),
    ("/api/swap/open", "swap-open", {
        "instId": "BTC-USDT-SWAP", "quoteAmount": "10",
    }),
    ("/api/swap/close", "swap-close", {"instId": "BTC-USDT-SWAP", "mgnMode": "cross"}),
])
def test_demo_workflow_routes_inject_ai_builder_code(client, path, workflow, payload):
    client.post("/api/connect", json={"code": "mock-code"})
    response = client.post(path, json=payload)
    body = response.get_json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["workflow"] == workflow
    assert body["simulated"] is True
    assert body["sent_ai_builder_code"] == "ABCD1234"
    assert body["sent_order"]["tag"] == "ABCD1234"
    assert body["raw"]["data"][0]["tag"] == "ABCD1234"


def test_spot_open_uses_explicit_inst_id_and_quote_amount(client):
    client.post("/api/connect", json={"code": "mock-code"})
    response = client.post("/api/spot/open", json={
        "instId": "ETH-USDT",
        "quoteAmount": "25",
        "tdMode": "cross",
    })
    body = response.get_json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["sent_order"]["instId"] == "ETH-USDT"
    assert body["sent_order"]["tdMode"] == "cross"
    assert body["sent_order"]["sz"] == "25"
    assert body["preflight"]["requestedQuoteAmountUSDT"] == "25"


def test_spot_open_defaults_td_mode_from_account_level(client):
    client.post("/api/connect", json={"code": "mock-code"})

    response = client.post("/api/spot/open", json={
        "instId": "BTC-USDT",
        "quoteAmount": "10",
    })
    body = response.get_json()
    assert response.status_code == 200
    assert body["sent_order"]["tdMode"] == "cross"
    assert body["preflight"]["acctLv"] == "3"


def test_spot_open_defaults_cash_for_spot_account_mode(client, monkeypatch):
    client.post("/api/connect", json={"code": "mock-code"})
    import app as app_module

    monkeypatch.setattr(
        app_module.okx,
        "get_account_config",
        lambda *args, **kwargs: {"code": "0", "data": [{"acctLv": "1", "posMode": "net_mode"}]},
    )

    response = client.post("/api/spot/open", json={
        "instId": "BTC-USDT",
        "quoteAmount": "10",
    })
    body = response.get_json()
    assert response.status_code == 200
    assert body["sent_order"]["tdMode"] == "cash"
    assert body["preflight"]["acctLv"] == "1"


def test_spot_open_rejects_account_mode_incompatible_td_mode(client):
    client.post("/api/connect", json={"code": "mock-code"})
    response = client.post("/api/spot/open", json={
        "instId": "BTC-USDT",
        "quoteAmount": "10",
        "tdMode": "cash",
    })
    body = response.get_json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert "acctLv=3" in body["error"]


def test_spot_open_rejects_non_string_td_mode(client):
    client.post("/api/connect", json={"code": "mock-code"})
    response = client.post("/api/spot/open", json={
        "instId": "BTC-USDT",
        "quoteAmount": "10",
        "tdMode": 0,
    })
    body = response.get_json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert body["error"] == "tdMode must be a string"


def test_spot_open_preflight_reads_full_balance(client, monkeypatch):
    client.post("/api/connect", json={"code": "mock-code"})
    import app as app_module

    captured = {}
    original = app_module.okx.get_account_balance

    def wrapped_get_account_balance(*args, **kwargs):
        captured.update(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(app_module.okx, "get_account_balance", wrapped_get_account_balance)
    response = client.post("/api/spot/open", json={
        "instId": "BTC-USDT",
        "quoteAmount": "10",
    })
    assert response.status_code == 200
    assert "ccy" not in captured


def test_spot_open_uses_instrument_quote_currency(client, monkeypatch):
    client.post("/api/connect", json={"code": "mock-code"})
    import app as app_module

    monkeypatch.setattr(
        app_module.okx,
        "get_account_balance",
        lambda *args, **kwargs: {
            "code": "0",
            "data": [{"details": [{"ccy": "USDC", "availBal": "1000"}]}],
        },
    )

    response = client.post("/api/spot/open", json={
        "instId": "ETH-USDC",
        "quoteAmount": "25",
    })
    body = response.get_json()
    assert response.status_code == 200
    assert body["sent_order"]["instId"] == "ETH-USDC"
    assert body["preflight"]["baseCcy"] == "ETH"
    assert body["preflight"]["quoteCcy"] == "USDC"
    assert body["preflight"]["availableQuoteBalance"] == "1000"
    assert body["preflight"]["requestedQuoteAmount"] == "25"
    assert body["preflight"]["availableUSDC"] == "1000"
    assert body["preflight"]["requestedQuoteAmountUSDC"] == "25"


def test_spot_close_rejects_base_size_above_available_balance(client):
    client.post("/api/connect", json={"code": "mock-code"})
    response = client.post("/api/spot/close", json={
        "instId": "BTC-USDT",
        "baseSize": "1",
    })
    body = response.get_json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert "exceeds available BTC" in body["error"]


def test_spot_close_uses_request_td_mode(client):
    client.post("/api/connect", json={"code": "mock-code"})
    response = client.post("/api/spot/close", json={
        "instId": "BTC-USDT",
        "quoteAmount": "10",
        "tdMode": "cross",
    })
    body = response.get_json()
    assert response.status_code == 200
    assert body["sent_order"]["tdMode"] == "cross"


def test_swap_open_quote_amount_converts_to_contracts(client):
    client.post("/api/connect", json={"code": "mock-code"})
    response = client.post("/api/swap/open", json={
        "instId": "BTC-USDT-SWAP",
        "quoteAmount": "25",
    })
    body = response.get_json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["sent_order"]["tdMode"] == "cross"
    assert body["sent_order"]["sz"] == "0.03"
    assert body["preflight"]["requestedQuoteAmountUSDT"] == "25"


def test_swap_open_uses_settlement_currency_balance_for_linear_swap(client, monkeypatch):
    client.post("/api/connect", json={"code": "mock-code"})
    import app as app_module

    monkeypatch.setattr(
        app_module.okx,
        "get_instruments",
        lambda *args, **kwargs: {
            "code": "0",
            "data": [{
                "instType": "SWAP",
                "instId": "SYNTH-LINEAR-SWAP",
                "state": "live",
                "ctType": "linear",
                "ctVal": "0.01",
                "ctValCcy": "BASE",
                "settleCcy": "SETTLE",
                "minSz": "0.01",
                "lotSz": "0.01",
                "tickSz": "0.1",
            }],
        },
    )
    monkeypatch.setattr(
        app_module.okx,
        "get_account_balance",
        lambda *args, **kwargs: {
            "code": "0",
            "data": [{"details": [{
                "ccy": "SETTLE",
                "availBal": "1000",
                "availEq": "1000",
                "cashBal": "1000",
                "eq": "1000",
            }]}],
        },
    )

    response = client.post("/api/swap/open", json={
        "instId": "SYNTH-LINEAR-SWAP",
        "quoteAmount": "25",
    })
    body = response.get_json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["preflight"]["settleCcy"] == "SETTLE"
    assert body["preflight"]["requestedQuoteAmount"] == "25"
    assert body["preflight"]["requestedQuoteAmountSETTLE"] == "25"
    assert body["preflight"]["availableSETTLE"] == "1000"
    assert body["preflight"]["estimatedNotionalSETTLE"] == "30"


def test_swap_open_rejects_inverse_swap_instrument(client, monkeypatch):
    client.post("/api/connect", json={"code": "mock-code"})
    import app as app_module
    get_account_config = Mock()
    get_account_balance = Mock()
    place_order = Mock()

    monkeypatch.setattr(
        app_module.okx,
        "get_instruments",
        lambda *args, **kwargs: {
            "code": "0",
            "data": [{
                "instType": "SWAP",
                "instId": "BTC-USD-SWAP",
                "state": "live",
                "ctType": "inverse",
                "ctVal": "100",
                "ctValCcy": "USD",
                "settleCcy": "BTC",
                "minSz": "0.1",
                "lotSz": "0.1",
                "tickSz": "0.1",
            }],
        },
    )
    monkeypatch.setattr(app_module.okx, "get_account_config", get_account_config)
    monkeypatch.setattr(app_module.okx, "get_account_balance", get_account_balance)
    monkeypatch.setattr(app_module.okx, "place_order", place_order)

    response = client.post("/api/swap/open", json={
        "instId": "BTC-USD-SWAP",
        "quoteAmount": "10",
    })
    body = response.get_json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert "only linear swap instruments" in body["error"]
    assert "inverse USD swap instruments are not supported" in body["error"]
    get_account_config.assert_not_called()
    get_account_balance.assert_not_called()
    place_order.assert_not_called()


def test_swap_open_net_mode_omits_pos_side(client, monkeypatch):
    client.post("/api/connect", json={"code": "mock-code"})
    import app as app_module

    monkeypatch.setattr(
        app_module.okx,
        "get_account_config",
        lambda *args, **kwargs: {"code": "0", "data": [{"acctLv": "3", "posMode": "net_mode"}]},
    )

    response = client.post("/api/swap/open", json={
        "instId": "BTC-USDT-SWAP",
        "quoteAmount": "10",
        "tdMode": "cross",
    })
    body = response.get_json()
    assert response.status_code == 200
    assert body["preflight"]["posMode"] == "net_mode"
    assert "posSide" not in body["sent_order"]


def test_swap_open_accepts_account_modes_two_and_four(client, monkeypatch):
    client.post("/api/connect", json={"code": "mock-code"})
    import app as app_module

    for acct_lv in ("2", "4"):
        monkeypatch.setattr(
            app_module.okx,
            "get_account_config",
            lambda *args, acct_lv=acct_lv, **kwargs: {
                "code": "0",
                "data": [{"acctLv": acct_lv, "posMode": "net_mode"}],
            },
        )
        response = client.post("/api/swap/open", json={
            "instId": "BTC-USDT-SWAP",
            "quoteAmount": "10",
        })
        body = response.get_json()
        assert response.status_code == 200
        assert body["sent_order"]["tdMode"] == "cross"
        assert body["preflight"]["acctLv"] == acct_lv


def test_swap_open_rejects_non_string_td_mode(client):
    client.post("/api/connect", json={"code": "mock-code"})
    response = client.post("/api/swap/open", json={
        "instId": "BTC-USDT-SWAP",
        "quoteAmount": "10",
        "tdMode": 0,
    })
    body = response.get_json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert body["error"] == "tdMode must be a string"


def test_swap_open_rejects_pos_side_in_net_mode(client, monkeypatch):
    client.post("/api/connect", json={"code": "mock-code"})
    import app as app_module

    monkeypatch.setattr(
        app_module.okx,
        "get_account_config",
        lambda *args, **kwargs: {"code": "0", "data": [{"acctLv": "3", "posMode": "net_mode"}]},
    )

    response = client.post("/api/swap/open", json={
        "instId": "BTC-USDT-SWAP",
        "quoteAmount": "10",
        "posSide": "long",
    })
    body = response.get_json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert "posMode=net_mode" in body["error"]


def test_swap_open_rejects_short_pos_side_for_long_workflow(client):
    client.post("/api/connect", json={"code": "mock-code"})
    response = client.post("/api/swap/open", json={
        "instId": "BTC-USDT-SWAP",
        "quoteAmount": "10",
        "posSide": "short",
    })
    body = response.get_json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert "posSide=long" in body["error"]


def test_swap_open_rejects_non_string_pos_side(client):
    client.post("/api/connect", json={"code": "mock-code"})
    response = client.post("/api/swap/open", json={
        "instId": "BTC-USDT-SWAP",
        "quoteAmount": "10",
        "posSide": {"side": "long"},
    })
    body = response.get_json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert body["error"] == "posSide must be a string"


def test_swap_open_rejects_spot_account_mode(client, monkeypatch):
    client.post("/api/connect", json={"code": "mock-code"})
    import app as app_module

    monkeypatch.setattr(
        app_module.okx,
        "get_account_config",
        lambda *args, **kwargs: {"code": "0", "data": [{"acctLv": "1", "posMode": "net_mode"}]},
    )

    response = client.post("/api/swap/open", json={
        "instId": "BTC-USDT-SWAP",
        "quoteAmount": "10",
    })
    body = response.get_json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert "acctLv=2, 3, or 4" in body["error"]


def test_swap_close_net_mode_omits_pos_side(client, monkeypatch):
    client.post("/api/connect", json={"code": "mock-code"})
    import app as app_module

    monkeypatch.setattr(
        app_module.okx,
        "get_account_config",
        lambda *args, **kwargs: {"code": "0", "data": [{"acctLv": "3", "posMode": "net_mode"}]},
    )

    response = client.post("/api/swap/close", json={
        "instId": "BTC-USDT-SWAP",
        "mgnMode": "cross",
    })
    body = response.get_json()
    assert response.status_code == 200
    assert body["preflight"]["posMode"] == "net_mode"
    assert "posSide" not in body["sent_order"]


def test_swap_close_uses_position_matching_margin_mode(client, monkeypatch):
    client.post("/api/connect", json={"code": "mock-code"})
    import app as app_module

    monkeypatch.setattr(
        app_module.okx,
        "get_positions",
        lambda *args, **kwargs: {
            "code": "0",
            "data": [
                {
                    "instId": "BTC-USDT-SWAP",
                    "posSide": "long",
                    "mgnMode": "isolated",
                    "pos": "0.01",
                },
                {
                    "instId": "BTC-USDT-SWAP",
                    "posSide": "long",
                    "mgnMode": "cross",
                    "pos": "0.02",
                },
            ],
        },
    )

    response = client.post("/api/swap/close", json={
        "instId": "BTC-USDT-SWAP",
        "mgnMode": "cross",
    })
    body = response.get_json()
    assert response.status_code == 200
    assert body["preflight"]["position"]["mgnMode"] == "cross"
    assert body["preflight"]["position"]["pos"] == "0.02"


def test_swap_close_rejects_spot_account_mode(client, monkeypatch):
    client.post("/api/connect", json={"code": "mock-code"})
    import app as app_module

    monkeypatch.setattr(
        app_module.okx,
        "get_account_config",
        lambda *args, **kwargs: {"code": "0", "data": [{"acctLv": "1", "posMode": "net_mode"}]},
    )

    response = client.post("/api/swap/close", json={
        "instId": "BTC-USDT-SWAP",
        "mgnMode": "cross",
    })
    body = response.get_json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert "acctLv=2, 3, or 4" in body["error"]


def test_swap_close_rejects_pos_side_in_net_mode(client, monkeypatch):
    client.post("/api/connect", json={"code": "mock-code"})
    import app as app_module

    monkeypatch.setattr(
        app_module.okx,
        "get_account_config",
        lambda *args, **kwargs: {"code": "0", "data": [{"acctLv": "3", "posMode": "net_mode"}]},
    )

    response = client.post("/api/swap/close", json={
        "instId": "BTC-USDT-SWAP",
        "mgnMode": "cross",
        "posSide": "long",
    })
    body = response.get_json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert "posMode=net_mode" in body["error"]


def test_swap_close_rejects_short_pos_side_for_long_workflow(client):
    client.post("/api/connect", json={"code": "mock-code"})
    response = client.post("/api/swap/close", json={
        "instId": "BTC-USDT-SWAP",
        "mgnMode": "cross",
        "posSide": "short",
    })
    body = response.get_json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert "posSide=long" in body["error"]


def test_swap_close_rejects_inverse_swap_instrument(client, monkeypatch):
    client.post("/api/connect", json={"code": "mock-code"})
    import app as app_module
    get_account_config = Mock()
    get_positions = Mock()
    close_position = Mock()

    monkeypatch.setattr(
        app_module.okx,
        "get_instruments",
        lambda *args, **kwargs: {
            "code": "0",
            "data": [{
                "instType": "SWAP",
                "instId": "BTC-USD-SWAP",
                "state": "live",
                "ctType": "inverse",
                "ctVal": "100",
                "ctValCcy": "USD",
                "settleCcy": "BTC",
                "minSz": "0.1",
                "lotSz": "0.1",
                "tickSz": "0.1",
            }],
        },
    )
    monkeypatch.setattr(app_module.okx, "get_account_config", get_account_config)
    monkeypatch.setattr(app_module.okx, "get_positions", get_positions)
    monkeypatch.setattr(app_module.okx, "close_position", close_position)

    response = client.post("/api/swap/close", json={
        "instId": "BTC-USD-SWAP",
        "mgnMode": "cross",
    })
    body = response.get_json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert "only linear swap instruments" in body["error"]
    assert "inverse USD swap instruments are not supported" in body["error"]
    get_account_config.assert_not_called()
    get_positions.assert_not_called()
    close_position.assert_not_called()


def test_swap_close_rejects_non_string_mgn_mode(client):
    client.post("/api/connect", json={"code": "mock-code"})
    response = client.post("/api/swap/close", json={
        "instId": "BTC-USDT-SWAP",
        "mgnMode": 0,
    })
    body = response.get_json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert body["error"] == "mgnMode must be a string"


def test_swap_close_rejects_non_string_pos_side(client):
    client.post("/api/connect", json={"code": "mock-code"})
    response = client.post("/api/swap/close", json={
        "instId": "BTC-USDT-SWAP",
        "mgnMode": "cross",
        "posSide": {"side": "long"},
    })
    body = response.get_json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert body["error"] == "posSide must be a string"


def test_swap_close_requires_mgn_mode(client):
    client.post("/api/connect", json={"code": "mock-code"})
    response = client.post("/api/swap/close", json={
        "instId": "BTC-USDT-SWAP",
    })
    body = response.get_json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert body["error"] == "missing mgnMode"


def test_order_requires_ai_builder_code(client_without_ai_builder_code):
    client_without_ai_builder_code.post("/api/connect", json={"code": "mock-code"})
    order = client_without_ai_builder_code.post("/api/order", json={
        "instId": "BTC-USDT",
        "side": "buy",
        "ordType": "limit",
        "px": "1000",
        "sz": "0.00000001",
    })
    body = order.get_json()
    assert order.status_code == 400
    assert body["ok"] is False
    assert body["error"] == "missing AI_BUILDER_CODE"


def test_order_rejects_invalid_ai_builder_code(client_with_invalid_ai_builder_code):
    client_with_invalid_ai_builder_code.post("/api/connect", json={"code": "mock-code"})
    order = client_with_invalid_ai_builder_code.post("/api/order", json={
        "instId": "BTC-USDT",
        "side": "buy",
        "ordType": "limit",
        "px": "1000",
        "sz": "0.00000001",
    })
    body = order.get_json()
    assert order.status_code == 400
    assert body["ok"] is False
    assert body["error"] == "AI_BUILDER_CODE must be 1-16 alphanumeric characters"


def test_demo_workflow_requires_ai_builder_code(client_without_ai_builder_code):
    client_without_ai_builder_code.post("/api/connect", json={"code": "mock-code"})
    response = client_without_ai_builder_code.post("/api/spot/open", json={
        "instId": "BTC-USDT",
        "quoteAmount": "10",
    })
    body = response.get_json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert body["error"] == "missing AI_BUILDER_CODE"
