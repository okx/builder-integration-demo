import io
import json
import os
import sys
import unittest
from unittest.mock import Mock, patch

import okx_openapi_client as client
import strategy_demo


AI_BUILDER_CODE = "ABC123"
AI_BUILDER_ARG = ["--ai-builder-code", AI_BUILDER_CODE]


class FakeResponse:
    status_code = 200
    text = "{}"

    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


def demo_env():
    return {
        "OKX_PROFILE": "demo",
        "OKX_DEMO_API_KEY": "demo-ak",
        "OKX_DEMO_SECRET_KEY": "demo-sk",
        "OKX_DEMO_PASSPHRASE": "demo-pp",
    }


def balance_response(ccy, available):
    return {
        "code": "0",
        "data": [{
            "details": [{
                "ccy": ccy,
                "availBal": str(available),
                "availEq": str(available),
                "cashBal": str(available),
                "eq": str(available),
            }],
        }],
    }


def ticker_response(last="100000", inst_id="BTC-USDT"):
    return {"code": "0", "data": [{"instId": inst_id, "last": last}]}


def instrument_response(inst_type="SPOT", inst_id=None, ct_type="linear", settle_ccy="USDT"):
    item = {
        "instId": inst_id or ("BTC-USDT" if inst_type == "SPOT" else "BTC-USDT-SWAP"),
        "state": "live",
        "minSz": "0.00001" if inst_type == "SPOT" else "0.01",
        "lotSz": "0.00000001" if inst_type == "SPOT" else "0.01",
        "tickSz": "0.1",
    }
    if inst_type == "SWAP":
        item["ctVal"] = "0.01"
        item["ctType"] = ct_type
        item["ctValCcy"] = "BTC"
        item["settleCcy"] = settle_ccy
    return {"code": "0", "data": [item]}


def account_config_response(pos_mode="net_mode", acct_lv="3"):
    return {"code": "0", "data": [{"posMode": pos_mode, "acctLv": acct_lv}]}


class OpenApiClientTest(unittest.TestCase):
    def test_known_answer_signing_vectors(self):
        secret = "mock-secret"
        timestamp = "2020-12-08T09:08:57.715Z"
        path = "/api/v5/account/balance"

        self.assertEqual(
            client._sign(secret, timestamp, "GET", path, ""),
            "tpQYvXdaAfU8ae6zI1rJ2xVcyMIk9BKWK/fysaanweQ=",
        )
        self.assertEqual(
            client._sign(secret, timestamp, "GET", path + "?ccy=BTC", ""),
            "pS6nHuBl6Qc9S0h+soCkCVHaVHZzS19KqFpeI/doTlE=",
        )

    def test_demo_order_body_tag_and_signature_use_sent_body(self):
        captured = {}

        def fake_post(url, headers=None, data=None, timeout=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["body"] = data
            return FakeResponse({"code": "0", "data": [{"ordId": "1"}]})

        timestamp = "2026-08-06T00:00:00.000Z"
        with patch.object(client, "_now_iso_ms", return_value=timestamp):
            with patch.object(client.requests, "post", side_effect=fake_post):
                result = client.place_order(
                    "https://www.okx.com",
                    "demo-key",
                    "demo-secret",
                    "demo-pass",
                    "BTC-USDT",
                    "cash",
                    "buy",
                    "limit",
                    "0.001",
                    px="60000",
                    tgt_ccy="base_ccy",
                    cl_ord_id="client123",
                    tp_trigger_px="70000",
                    tp_ord_px="-1",
                    sl_trigger_px="55000",
                    sl_ord_px="-1",
                    stp_mode="cancel_maker",
                    trade_quote_ccy="USDT",
                    ban_amend=True,
                    px_amend_type="1",
                    ai_builder_code="ABC123",
                    simulated=True,
                )

        sent_body = json.loads(captured["body"])
        self.assertEqual(result["code"], "0")
        self.assertEqual(captured["url"], "https://www.okx.com/api/v5/trade/order")
        self.assertEqual(captured["headers"]["x-simulated-trading"], "1")
        self.assertEqual(captured["headers"]["OK-ACCESS-KEY"], "demo-key")
        self.assertEqual(sent_body["tag"], "ABC123")
        self.assertEqual(sent_body["tgtCcy"], "base_ccy")
        self.assertEqual(sent_body["clOrdId"], "client123")
        self.assertEqual(sent_body["banAmend"], "true")
        self.assertEqual(sent_body["attachAlgoOrds"], [{
            "tpTriggerPx": "70000",
            "tpOrdPx": "-1",
            "slTriggerPx": "55000",
            "slOrdPx": "-1",
        }])
        expected_sign = client._sign(
            "demo-secret",
            timestamp,
            "POST",
            client.PATH_TRADE_ORDER,
            captured["body"],
        )
        self.assertEqual(captured["headers"]["OK-ACCESS-SIGN"], expected_sign)

    def test_order_without_tpsl_omits_attach_algo_ords(self):
        captured = {}

        def fake_post(url, headers=None, data=None, timeout=None):
            captured["body"] = data
            captured["headers"] = headers
            return FakeResponse({"code": "0"})

        with patch.object(client.requests, "post", side_effect=fake_post):
            client.place_order(
                "https://www.okx.com",
                "live-key",
                "live-secret",
                "live-pass",
                "BTC-USDT",
                "cash",
                "buy",
                "market",
                "100",
                ai_builder_code="ABC123",
                simulated=False,
            )

        sent_body = json.loads(captured["body"])
        self.assertNotIn("attachAlgoOrds", sent_body)
        self.assertNotIn("px", sent_body)
        self.assertNotIn("x-simulated-trading", captured["headers"])

    def test_place_order_requires_ai_builder_code_before_network_call(self):
        with patch.object(client.requests, "post") as post:
            with self.assertRaises(ValueError) as raised:
                client.place_order(
                    "https://www.okx.com",
                    "live-key",
                    "live-secret",
                    "live-pass",
                    "BTC-USDT",
                    "cash",
                    "buy",
                    "market",
                    "100",
                )

        self.assertIn("AI Builder Code", str(raised.exception))
        post.assert_not_called()

    def test_swap_order_body_includes_pos_side_and_reduce_only(self):
        captured = {}

        def fake_post(url, headers=None, data=None, timeout=None):
            captured["body"] = data
            return FakeResponse({"code": "0"})

        with patch.object(client.requests, "post", side_effect=fake_post):
            client.place_order(
                "https://www.okx.com",
                "key",
                "secret",
                "pass",
                "BTC-USDT-SWAP",
                "cross",
                "sell",
                "market",
                "0.01",
                pos_side="long",
                reduce_only=True,
                ai_builder_code="ABC123",
                simulated=True,
            )

        sent_body = json.loads(captured["body"])
        self.assertEqual(sent_body["posSide"], "long")
        self.assertEqual(sent_body["reduceOnly"], "true")
        self.assertEqual(sent_body["tag"], "ABC123")

    def test_close_position_body_includes_tag(self):
        captured = {}

        def fake_post(url, headers=None, data=None, timeout=None):
            captured["url"] = url
            captured["body"] = data
            return FakeResponse({"code": "0"})

        with patch.object(client.requests, "post", side_effect=fake_post):
            client.close_position(
                "https://www.okx.com",
                "key",
                "secret",
                "pass",
                "BTC-USDT-SWAP",
                "cross",
                pos_side="long",
                auto_cxl=True,
                ai_builder_code="ABC123",
                simulated=True,
            )

        sent_body = json.loads(captured["body"])
        self.assertEqual(captured["url"], "https://www.okx.com/api/v5/trade/close-position")
        self.assertEqual(sent_body["posSide"], "long")
        self.assertEqual(sent_body["autoCxl"], "true")
        self.assertEqual(sent_body["tag"], "ABC123")

    def test_close_position_rejects_invalid_ai_builder_code_before_network_call(self):
        with patch.object(client.requests, "post") as post:
            with self.assertRaises(ValueError) as raised:
                client.close_position(
                    "https://www.okx.com",
                    "key",
                    "secret",
                    "pass",
                    "BTC-USDT-SWAP",
                    "cross",
                    ai_builder_code="bad-code!",
                )

        self.assertIn("AI Builder Code", str(raised.exception))
        post.assert_not_called()


class StrategyDemoTest(unittest.TestCase):
    def run_main(self, argv, env, place_order=None):
        if place_order is None:
            place_order = Mock(return_value={"code": "0", "data": []})
        with patch.dict(os.environ, env, clear=True):
            with patch.object(strategy_demo, "load_dotenv", return_value=False):
                with patch.object(strategy_demo.okx, "place_order", place_order):
                    with patch.object(sys, "argv", ["strategy_demo.py"] + argv):
                        with patch("sys.stdout", new_callable=io.StringIO):
                            strategy_demo.main()
        return place_order

    def test_spot_td_mode_defaults_by_account_mode(self):
        cases = [("1", "cash"), ("2", "cash"), ("3", "cross"), ("4", "cross")]
        for acct_lv, expected in cases:
            with self.subTest(acct_lv=acct_lv):
                self.assertEqual(
                    strategy_demo._spot_td_mode(None, account_config_response(acct_lv=acct_lv)),
                    expected,
                )

    def test_swap_td_mode_accepts_only_swap_capable_account_modes(self):
        for acct_lv in ("2", "3", "4"):
            with self.subTest(acct_lv=acct_lv):
                self.assertEqual(
                    strategy_demo._swap_td_mode(None, account_config_response(acct_lv=acct_lv)),
                    "cross",
                )
        with self.assertRaises(SystemExit):
            strategy_demo._swap_td_mode(None, account_config_response(acct_lv="1"))

    def test_demo_profile_uses_demo_credentials_site_and_simulated_header(self):
        place_order = self.run_main(
            [
                "order", "--td-mode", "cash", "--ord-type", "market", "--sz", "100",
                *AI_BUILDER_ARG,
            ],
            {
                "OKX_PROFILE": "demo",
                "OKX_SITE": "us",
                "OKX_DEMO_API_KEY": "demo-ak",
                "OKX_DEMO_SECRET_KEY": "demo-sk",
                "OKX_DEMO_PASSPHRASE": "demo-pp",
            },
        )

        args, kwargs = place_order.call_args
        self.assertEqual(args[0], "https://us.okx.com")
        self.assertEqual(args[1], "demo-ak")
        self.assertEqual(args[2], "demo-sk")
        self.assertEqual(args[3], "demo-pp")
        self.assertIsNone(kwargs["px"])
        self.assertEqual(kwargs["ai_builder_code"], "ABC123")
        self.assertTrue(kwargs["simulated"])

    def test_live_order_requires_explicit_confirmation_before_network_call(self):
        place_order = Mock(return_value={"code": "0"})
        with self.assertRaises(SystemExit) as raised:
            self.run_main(
                ["order", "--td-mode", "cash", *AI_BUILDER_ARG],
                {
                    "OKX_PROFILE": "live",
                    "OKX_LIVE_API_KEY": "live-ak",
                    "OKX_LIVE_SECRET_KEY": "live-sk",
                    "OKX_LIVE_PASSPHRASE": "live-pp",
                },
                place_order=place_order,
            )

        self.assertIn("--confirm-live-order", str(raised.exception))
        place_order.assert_not_called()

    def test_invalid_ai_builder_code_stops_before_network_call(self):
        place_order = Mock(return_value={"code": "0"})
        with self.assertRaises(SystemExit) as raised:
            self.run_main(
                ["order", "--td-mode", "cash", "--ai-builder-code", "bad-code!"],
                {
                    "OKX_PROFILE": "demo",
                    "OKX_DEMO_API_KEY": "demo-ak",
                    "OKX_DEMO_SECRET_KEY": "demo-sk",
                    "OKX_DEMO_PASSPHRASE": "demo-pp",
                },
                place_order=place_order,
            )

        self.assertIn("AI Builder Code", str(raised.exception))
        place_order.assert_not_called()

    def test_missing_ai_builder_code_stops_before_network_call(self):
        place_order = Mock(return_value={"code": "0"})
        with patch("sys.stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                self.run_main(
                    ["order", "--td-mode", "cash"],
                    demo_env(),
                    place_order=place_order,
                )

        place_order.assert_not_called()

    def test_ai_builder_code_argument_overrides_stale_environment_value(self):
        place_order = self.run_main(
            [
                "order", "--td-mode", "cash", "--ord-type", "market", "--sz", "100",
                "--ai-builder-code", "NEW123",
            ],
            {
                **demo_env(),
                "AI_BUILDER_CODE": "OLD123",
            },
        )

        _, kwargs = place_order.call_args
        self.assertEqual(kwargs["ai_builder_code"], "NEW123")

    def test_spot_open_workflow_uses_quote_amount_and_ai_builder_code(self):
        place_order = Mock(return_value={"code": "0", "data": [{"sCode": "0"}]})
        get_account_balance = Mock(return_value=balance_response("USDT", "1000"))
        config = account_config_response(acct_lv="3")
        with patch.dict(os.environ, demo_env(), clear=True):
            with patch.object(strategy_demo, "load_dotenv", return_value=False):
                with patch.object(strategy_demo.okx, "get_ticker", return_value=ticker_response()):
                    with patch.object(strategy_demo.okx, "get_instruments",
                                      return_value=instrument_response("SPOT")):
                        with patch.object(strategy_demo.okx, "get_account_config",
                                          return_value=config):
                            with patch.object(strategy_demo.okx, "get_account_balance",
                                              get_account_balance):
                                with patch.object(strategy_demo.okx, "place_order", place_order):
                                    with patch.object(sys, "argv", [
                                        "strategy_demo.py", "spot-open",
                                        "--inst-id", "ETH-USDT", "--quote-amount", "25",
                                        *AI_BUILDER_ARG,
                                    ]):
                                        with patch("sys.stdout", new_callable=io.StringIO):
                                            strategy_demo.main()

        args, kwargs = place_order.call_args
        self.assertEqual(args[4], "ETH-USDT")
        self.assertEqual(args[5], "cross")
        self.assertEqual(args[6], "buy")
        self.assertEqual(args[7], "market")
        self.assertEqual(args[8], "25")
        self.assertEqual(kwargs["tgt_ccy"], "quote_ccy")
        self.assertEqual(kwargs["ai_builder_code"], "ABC123")
        self.assertTrue(kwargs["simulated"])
        self.assertNotIn("ccy", get_account_balance.call_args.kwargs)

    def test_spot_open_defaults_to_cash_for_spot_account_mode(self):
        place_order = Mock(return_value={"code": "0", "data": [{"sCode": "0"}]})
        config = account_config_response(acct_lv="1")
        with patch.dict(os.environ, demo_env(), clear=True):
            with patch.object(strategy_demo, "load_dotenv", return_value=False):
                with patch.object(strategy_demo.okx, "get_ticker", return_value=ticker_response()):
                    with patch.object(strategy_demo.okx, "get_instruments",
                                      return_value=instrument_response("SPOT")):
                        with patch.object(strategy_demo.okx, "get_account_config",
                                          return_value=config):
                            with patch.object(strategy_demo.okx, "get_account_balance",
                                              return_value=balance_response("USDT", "1000")):
                                with patch.object(strategy_demo.okx, "place_order", place_order):
                                    with patch.object(sys, "argv", [
                                        "strategy_demo.py", "spot-open",
                                        "--inst-id", "BTC-USDT", "--quote-amount", "10",
                                        *AI_BUILDER_ARG,
                                    ]):
                                        with patch("sys.stdout", new_callable=io.StringIO):
                                            strategy_demo.main()

        args, _ = place_order.call_args
        self.assertEqual(args[5], "cash")

    def test_spot_open_uses_quote_currency_from_inst_id(self):
        place_order = Mock(return_value={"code": "0", "data": [{"sCode": "0"}]})
        with patch.dict(os.environ, demo_env(), clear=True):
            with patch.object(strategy_demo, "load_dotenv", return_value=False):
                with patch.object(strategy_demo.okx, "get_ticker", return_value=ticker_response()):
                    with patch.object(strategy_demo.okx, "get_instruments",
                                      return_value=instrument_response("SPOT")):
                        with patch.object(strategy_demo.okx, "get_account_config",
                                          return_value=account_config_response(acct_lv="3")):
                            with patch.object(strategy_demo.okx, "get_account_balance",
                                              return_value=balance_response("USDC", "1000")):
                                with patch.object(strategy_demo.okx, "place_order", place_order):
                                    with patch.object(sys, "argv", [
                                        "strategy_demo.py", "spot-open",
                                        "--inst-id", "ETH-USDC", "--quote-amount", "25",
                                        *AI_BUILDER_ARG,
                                    ]):
                                        with patch("sys.stdout", new_callable=io.StringIO) as stdout:
                                            strategy_demo.main()

        body = json.loads(stdout.getvalue())
        args, _ = place_order.call_args
        self.assertEqual(args[4], "ETH-USDC")
        self.assertEqual(body["preflight"]["baseCcy"], "ETH")
        self.assertEqual(body["preflight"]["quoteCcy"], "USDC")
        self.assertEqual(body["preflight"]["availableQuoteBalance"], "1000")
        self.assertEqual(body["preflight"]["requestedQuoteAmount"], "25")
        self.assertEqual(body["preflight"]["availableUSDC"], "1000")
        self.assertEqual(body["preflight"]["requestedQuoteAmountUSDC"], "25")

    def test_spot_open_workflow_uses_cli_td_mode_override(self):
        place_order = Mock(return_value={"code": "0", "data": [{"sCode": "0"}]})
        with patch.dict(os.environ, demo_env(), clear=True):
            with patch.object(strategy_demo, "load_dotenv", return_value=False):
                with patch.object(strategy_demo.okx, "get_ticker", return_value=ticker_response()):
                    with patch.object(strategy_demo.okx, "get_instruments",
                                      return_value=instrument_response("SPOT")):
                        with patch.object(strategy_demo.okx, "get_account_config",
                                          return_value=account_config_response(acct_lv="2")):
                            with patch.object(strategy_demo.okx, "get_account_balance",
                                              return_value=balance_response("USDT", "1000")):
                                with patch.object(strategy_demo.okx, "place_order", place_order):
                                    with patch.object(sys, "argv", [
                                        "strategy_demo.py", "spot-open",
                                        "--inst-id", "BTC-USDT", "--quote-amount", "10",
                                        "--td-mode", "cross",
                                        *AI_BUILDER_ARG,
                                    ]):
                                        with patch("sys.stdout", new_callable=io.StringIO):
                                            strategy_demo.main()

        args, _ = place_order.call_args
        self.assertEqual(args[5], "cross")

    def test_spot_open_rejects_account_mode_incompatible_td_mode(self):
        place_order = Mock(return_value={"code": "0", "data": [{"sCode": "0"}]})
        with patch.dict(os.environ, demo_env(), clear=True):
            with patch.object(strategy_demo, "load_dotenv", return_value=False):
                with patch.object(strategy_demo.okx, "get_ticker", return_value=ticker_response()):
                    with patch.object(strategy_demo.okx, "get_instruments",
                                      return_value=instrument_response("SPOT")):
                        with patch.object(strategy_demo.okx, "get_account_config",
                                          return_value=account_config_response(acct_lv="3")):
                            with patch.object(strategy_demo.okx, "place_order", place_order):
                                with patch.object(sys, "argv", [
                                    "strategy_demo.py", "spot-open",
                                    "--inst-id", "BTC-USDT", "--quote-amount", "10",
                                    "--td-mode", "cash",
                                    *AI_BUILDER_ARG,
                                ]):
                                    with self.assertRaises(SystemExit) as raised:
                                        strategy_demo.main()

        self.assertIn("acctLv=3", str(raised.exception))
        place_order.assert_not_called()

    def test_spot_close_workflow_sells_valid_base_size(self):
        place_order = Mock(return_value={"code": "0", "data": [{"sCode": "0"}]})
        with patch.dict(os.environ, demo_env(), clear=True):
            with patch.object(strategy_demo, "load_dotenv", return_value=False):
                with patch.object(strategy_demo.okx, "get_ticker", return_value=ticker_response()):
                    with patch.object(strategy_demo.okx, "get_instruments",
                                      return_value=instrument_response("SPOT")):
                        with patch.object(strategy_demo.okx, "get_account_config",
                                          return_value=account_config_response(acct_lv="3")):
                            with patch.object(strategy_demo.okx, "get_account_balance",
                                              return_value=balance_response("BTC", "0.00012")):
                                with patch.object(strategy_demo.okx, "place_order", place_order):
                                    with patch.object(sys, "argv", [
                                        "strategy_demo.py", "spot-close",
                                        "--inst-id", "BTC-USDT", "--quote-amount", "10",
                                        *AI_BUILDER_ARG,
                                    ]):
                                        with patch("sys.stdout", new_callable=io.StringIO):
                                            strategy_demo.main()

        args, kwargs = place_order.call_args
        self.assertEqual(args[4], "BTC-USDT")
        self.assertEqual(args[5], "cross")
        self.assertEqual(args[6], "sell")
        self.assertEqual(args[7], "market")
        self.assertEqual(args[8], "0.0001")
        self.assertEqual(kwargs["ai_builder_code"], "ABC123")

    def test_spot_close_rejects_base_size_above_available_balance(self):
        place_order = Mock(return_value={"code": "0", "data": [{"sCode": "0"}]})
        with patch.dict(os.environ, demo_env(), clear=True):
            with patch.object(strategy_demo, "load_dotenv", return_value=False):
                with patch.object(strategy_demo.okx, "get_ticker", return_value=ticker_response()):
                    with patch.object(strategy_demo.okx, "get_instruments",
                                      return_value=instrument_response("SPOT")):
                        with patch.object(strategy_demo.okx, "get_account_config",
                                          return_value=account_config_response(acct_lv="3")):
                            with patch.object(strategy_demo.okx, "get_account_balance",
                                              return_value=balance_response("BTC", "0.00012")):
                                with patch.object(strategy_demo.okx, "place_order", place_order):
                                    with patch.object(sys, "argv", [
                                        "strategy_demo.py", "spot-close",
                                        "--inst-id", "BTC-USDT", "--base-size", "1",
                                        *AI_BUILDER_ARG,
                                    ]):
                                        with self.assertRaises(SystemExit) as raised:
                                            strategy_demo.main()
        self.assertIn("exceeds available BTC", str(raised.exception))
        place_order.assert_not_called()

    def test_swap_open_workflow_uses_contracts_and_pos_side(self):
        place_order = Mock(return_value={"code": "0", "data": [{"sCode": "0"}]})
        config = account_config_response("long_short_mode")
        with patch.dict(os.environ, demo_env(), clear=True):
            with patch.object(strategy_demo, "load_dotenv", return_value=False):
                with patch.object(strategy_demo.okx, "get_ticker", return_value=ticker_response()):
                    with patch.object(strategy_demo.okx, "get_instruments",
                                      return_value=instrument_response("SWAP")):
                        with patch.object(strategy_demo.okx, "get_account_config", return_value=config):
                            with patch.object(strategy_demo.okx, "get_account_balance",
                                              return_value=balance_response("USDT", "1000")):
                                with patch.object(strategy_demo.okx, "place_order", place_order):
                                    with patch.object(sys, "argv", [
                                        "strategy_demo.py", "swap-open",
                                        "--inst-id", "BTC-USDT-SWAP", "--quote-amount", "10",
                                        *AI_BUILDER_ARG,
                                    ]):
                                        with patch("sys.stdout", new_callable=io.StringIO):
                                            strategy_demo.main()

        args, kwargs = place_order.call_args
        self.assertEqual(args[4], "BTC-USDT-SWAP")
        self.assertEqual(args[5], "cross")
        self.assertEqual(args[6], "buy")
        self.assertEqual(args[7], "market")
        self.assertEqual(args[8], "0.01")
        self.assertEqual(kwargs["pos_side"], "long")
        self.assertEqual(kwargs["ai_builder_code"], "ABC123")

    def test_swap_open_quote_amount_converts_to_contracts(self):
        place_order = Mock(return_value={"code": "0", "data": [{"sCode": "0"}]})
        config = account_config_response("long_short_mode")
        with patch.dict(os.environ, demo_env(), clear=True):
            with patch.object(strategy_demo, "load_dotenv", return_value=False):
                with patch.object(strategy_demo.okx, "get_ticker", return_value=ticker_response()):
                    with patch.object(strategy_demo.okx, "get_instruments",
                                      return_value=instrument_response("SWAP")):
                        with patch.object(strategy_demo.okx, "get_account_config", return_value=config):
                            with patch.object(strategy_demo.okx, "get_account_balance",
                                              return_value=balance_response("USDT", "1000")):
                                with patch.object(strategy_demo.okx, "place_order", place_order):
                                    with patch.object(sys, "argv", [
                                        "strategy_demo.py", "swap-open",
                                        "--inst-id", "BTC-USDT-SWAP", "--quote-amount", "25",
                                        "--td-mode", "cross",
                                        *AI_BUILDER_ARG,
                                    ]):
                                        with patch("sys.stdout", new_callable=io.StringIO):
                                            strategy_demo.main()

        args, kwargs = place_order.call_args
        self.assertEqual(args[8], "0.03")
        self.assertEqual(kwargs["ai_builder_code"], "ABC123")

    def test_swap_open_uses_settlement_currency_balance_for_linear_swap(self):
        place_order = Mock(return_value={"code": "0", "data": [{"sCode": "0"}]})
        config = account_config_response("long_short_mode")
        instrument = instrument_response(
            "SWAP", inst_id="SYNTH-LINEAR-SWAP", ct_type="linear", settle_ccy="SETTLE",
        )
        with patch.dict(os.environ, demo_env(), clear=True):
            with patch.object(strategy_demo, "load_dotenv", return_value=False):
                with patch.object(
                    strategy_demo.okx, "get_ticker",
                    return_value=ticker_response(inst_id="SYNTH-LINEAR-SWAP"),
                ):
                    with patch.object(strategy_demo.okx, "get_instruments", return_value=instrument):
                        with patch.object(strategy_demo.okx, "get_account_config", return_value=config):
                            with patch.object(strategy_demo.okx, "get_account_balance",
                                              return_value=balance_response("SETTLE", "1000")):
                                with patch.object(strategy_demo.okx, "place_order", place_order):
                                    with patch.object(sys, "argv", [
                                        "strategy_demo.py", "swap-open",
                                        "--inst-id", "SYNTH-LINEAR-SWAP", "--quote-amount", "25",
                                        *AI_BUILDER_ARG,
                                    ]):
                                        with patch("sys.stdout", new_callable=io.StringIO) as stdout:
                                            strategy_demo.main()

        body = json.loads(stdout.getvalue())
        self.assertEqual(body["preflight"]["settleCcy"], "SETTLE")
        self.assertEqual(body["preflight"]["requestedQuoteAmount"], "25")
        self.assertEqual(body["preflight"]["requestedQuoteAmountSETTLE"], "25")
        self.assertEqual(body["preflight"]["availableSETTLE"], "1000")
        self.assertEqual(body["preflight"]["estimatedNotionalSETTLE"], "30")
        place_order.assert_called_once()

    def test_swap_open_rejects_inverse_swap_instrument(self):
        place_order = Mock(return_value={"code": "0", "data": [{"sCode": "0"}]})
        instrument = instrument_response(
            "SWAP", inst_id="BTC-USD-SWAP", ct_type="inverse", settle_ccy="BTC",
        )
        with patch.dict(os.environ, demo_env(), clear=True):
            with patch.object(strategy_demo, "load_dotenv", return_value=False):
                with patch.object(
                    strategy_demo.okx, "get_ticker",
                    return_value=ticker_response(inst_id="BTC-USD-SWAP"),
                ):
                    with patch.object(strategy_demo.okx, "get_instruments", return_value=instrument):
                        with patch.object(sys, "argv", [
                            "strategy_demo.py", "swap-open",
                            "--inst-id", "BTC-USD-SWAP", "--quote-amount", "10",
                            *AI_BUILDER_ARG,
                        ]):
                            with self.assertRaises(SystemExit) as raised:
                                strategy_demo.main()

        self.assertIn("only linear swap instruments", str(raised.exception))
        self.assertIn("inverse USD swap instruments are not supported", str(raised.exception))
        place_order.assert_not_called()

    def test_swap_open_net_mode_omits_pos_side(self):
        place_order = Mock(return_value={"code": "0", "data": [{"sCode": "0"}]})
        config = account_config_response("net_mode")
        with patch.dict(os.environ, demo_env(), clear=True):
            with patch.object(strategy_demo, "load_dotenv", return_value=False):
                with patch.object(strategy_demo.okx, "get_ticker", return_value=ticker_response()):
                    with patch.object(strategy_demo.okx, "get_instruments",
                                      return_value=instrument_response("SWAP")):
                        with patch.object(strategy_demo.okx, "get_account_config", return_value=config):
                            with patch.object(strategy_demo.okx, "get_account_balance",
                                              return_value=balance_response("USDT", "1000")):
                                with patch.object(strategy_demo.okx, "place_order", place_order):
                                    with patch.object(sys, "argv", [
                                        "strategy_demo.py", "swap-open",
                                        "--inst-id", "BTC-USDT-SWAP", "--quote-amount", "10",
                                        "--td-mode", "cross",
                                        *AI_BUILDER_ARG,
                                    ]):
                                        with patch("sys.stdout", new_callable=io.StringIO):
                                            strategy_demo.main()

        _, kwargs = place_order.call_args
        self.assertIsNone(kwargs["pos_side"])
        self.assertEqual(kwargs["ai_builder_code"], "ABC123")

    def test_swap_open_rejects_pos_side_in_net_mode(self):
        place_order = Mock(return_value={"code": "0", "data": [{"sCode": "0"}]})
        config = account_config_response("net_mode")
        with patch.dict(os.environ, demo_env(), clear=True):
            with patch.object(strategy_demo, "load_dotenv", return_value=False):
                with patch.object(strategy_demo.okx, "get_ticker", return_value=ticker_response()):
                    with patch.object(strategy_demo.okx, "get_instruments",
                                      return_value=instrument_response("SWAP")):
                        with patch.object(strategy_demo.okx, "get_account_config", return_value=config):
                            with patch.object(strategy_demo.okx, "place_order", place_order):
                                with patch.object(sys, "argv", [
                                    "strategy_demo.py", "swap-open",
                                    "--inst-id", "BTC-USDT-SWAP", "--quote-amount", "10",
                                    "--pos-side", "long",
                                    *AI_BUILDER_ARG,
                                ]):
                                    with self.assertRaises(SystemExit) as raised:
                                        strategy_demo.main()

        self.assertIn("posMode=net_mode", str(raised.exception))
        place_order.assert_not_called()

    def test_swap_open_rejects_short_pos_side_for_long_workflow(self):
        place_order = Mock(return_value={"code": "0", "data": [{"sCode": "0"}]})
        config = account_config_response("long_short_mode")
        with patch.dict(os.environ, demo_env(), clear=True):
            with patch.object(strategy_demo, "load_dotenv", return_value=False):
                with patch.object(strategy_demo.okx, "get_ticker", return_value=ticker_response()):
                    with patch.object(strategy_demo.okx, "get_instruments",
                                      return_value=instrument_response("SWAP")):
                        with patch.object(strategy_demo.okx, "get_account_config", return_value=config):
                            with patch.object(strategy_demo.okx, "place_order", place_order):
                                with patch.object(sys, "argv", [
                                    "strategy_demo.py", "swap-open",
                                    "--inst-id", "BTC-USDT-SWAP", "--quote-amount", "10",
                                    "--pos-side", "short",
                                    *AI_BUILDER_ARG,
                                ]):
                                    with self.assertRaises(SystemExit) as raised:
                                        strategy_demo.main()

        self.assertIn("--pos-side long", str(raised.exception))
        place_order.assert_not_called()

    def test_swap_open_rejects_spot_account_mode(self):
        place_order = Mock(return_value={"code": "0", "data": [{"sCode": "0"}]})
        config = account_config_response("net_mode", acct_lv="1")
        with patch.dict(os.environ, demo_env(), clear=True):
            with patch.object(strategy_demo, "load_dotenv", return_value=False):
                with patch.object(strategy_demo.okx, "get_ticker", return_value=ticker_response()):
                    with patch.object(strategy_demo.okx, "get_instruments",
                                      return_value=instrument_response("SWAP")):
                        with patch.object(strategy_demo.okx, "get_account_config", return_value=config):
                            with patch.object(strategy_demo.okx, "place_order", place_order):
                                with patch.object(sys, "argv", [
                                    "strategy_demo.py", "swap-open",
                                    "--inst-id", "BTC-USDT-SWAP", "--quote-amount", "10",
                                    *AI_BUILDER_ARG,
                                ]):
                                    with self.assertRaises(SystemExit) as raised:
                                        strategy_demo.main()

        self.assertIn("acctLv=2, 3, or 4", str(raised.exception))
        place_order.assert_not_called()

    def test_swap_close_workflow_uses_close_position_with_tag(self):
        close_position = Mock(return_value={"code": "0", "data": [{"sCode": "0"}]})
        config = account_config_response("long_short_mode")
        positions = {
            "code": "0",
            "data": [{"instId": "BTC-USDT-SWAP", "posSide": "long", "pos": "0.01"}],
        }
        with patch.dict(os.environ, demo_env(), clear=True):
            with patch.object(strategy_demo, "load_dotenv", return_value=False):
                with patch.object(strategy_demo.okx, "get_ticker", return_value=ticker_response()):
                    with patch.object(strategy_demo.okx, "get_instruments",
                                      return_value=instrument_response("SWAP")):
                        with patch.object(strategy_demo.okx, "get_account_config", return_value=config):
                            with patch.object(strategy_demo.okx, "get_positions", return_value=positions):
                                with patch.object(strategy_demo.okx, "close_position", close_position):
                                    with patch.object(sys, "argv", [
                                        "strategy_demo.py", "swap-close",
                                        "--inst-id", "BTC-USDT-SWAP",
                                        "--mgn-mode", "cross",
                                        *AI_BUILDER_ARG,
                                    ]):
                                        with patch("sys.stdout", new_callable=io.StringIO):
                                            strategy_demo.main()

        args, kwargs = close_position.call_args
        self.assertEqual(args[4], "BTC-USDT-SWAP")
        self.assertEqual(args[5], "cross")
        self.assertEqual(kwargs["pos_side"], "long")
        self.assertTrue(kwargs["auto_cxl"])
        self.assertEqual(kwargs["ai_builder_code"], "ABC123")

    def test_swap_close_finds_position_matching_margin_mode(self):
        positions = {
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
        }

        position = strategy_demo._find_open_position(
            positions, "BTC-USDT-SWAP", pos_side="long", mgn_mode="cross",
        )

        self.assertEqual(position["mgnMode"], "cross")
        self.assertEqual(position["pos"], "0.02")

    def test_swap_close_net_mode_omits_pos_side(self):
        close_position = Mock(return_value={"code": "0", "data": [{"sCode": "0"}]})
        config = account_config_response("net_mode")
        positions = {
            "code": "0",
            "data": [{"instId": "BTC-USDT-SWAP", "posSide": "net", "pos": "0.01"}],
        }
        with patch.dict(os.environ, demo_env(), clear=True):
            with patch.object(strategy_demo, "load_dotenv", return_value=False):
                with patch.object(strategy_demo.okx, "get_ticker", return_value=ticker_response()):
                    with patch.object(strategy_demo.okx, "get_instruments",
                                      return_value=instrument_response("SWAP")):
                        with patch.object(strategy_demo.okx, "get_account_config", return_value=config):
                            with patch.object(strategy_demo.okx, "get_positions", return_value=positions):
                                with patch.object(strategy_demo.okx, "close_position", close_position):
                                    with patch.object(sys, "argv", [
                                        "strategy_demo.py", "swap-close",
                                        "--inst-id", "BTC-USDT-SWAP",
                                        "--mgn-mode", "cross",
                                        *AI_BUILDER_ARG,
                                    ]):
                                        with patch("sys.stdout", new_callable=io.StringIO):
                                            strategy_demo.main()

        _, kwargs = close_position.call_args
        self.assertIsNone(kwargs["pos_side"])
        self.assertTrue(kwargs["auto_cxl"])
        self.assertEqual(kwargs["ai_builder_code"], "ABC123")

    def test_swap_close_rejects_pos_side_in_net_mode(self):
        close_position = Mock(return_value={"code": "0", "data": [{"sCode": "0"}]})
        config = account_config_response("net_mode")
        with patch.dict(os.environ, demo_env(), clear=True):
            with patch.object(strategy_demo, "load_dotenv", return_value=False):
                with patch.object(strategy_demo.okx, "get_ticker", return_value=ticker_response()):
                    with patch.object(strategy_demo.okx, "get_instruments",
                                      return_value=instrument_response("SWAP")):
                        with patch.object(strategy_demo.okx, "get_account_config", return_value=config):
                            with patch.object(strategy_demo.okx, "close_position", close_position):
                                with patch.object(sys, "argv", [
                                    "strategy_demo.py", "swap-close",
                                    "--inst-id", "BTC-USDT-SWAP",
                                    "--mgn-mode", "cross", "--pos-side", "long",
                                    *AI_BUILDER_ARG,
                                ]):
                                    with self.assertRaises(SystemExit) as raised:
                                        strategy_demo.main()

        self.assertIn("posMode=net_mode", str(raised.exception))
        close_position.assert_not_called()

    def test_swap_close_rejects_short_pos_side_for_long_workflow(self):
        close_position = Mock(return_value={"code": "0", "data": [{"sCode": "0"}]})
        config = account_config_response("long_short_mode")
        with patch.dict(os.environ, demo_env(), clear=True):
            with patch.object(strategy_demo, "load_dotenv", return_value=False):
                with patch.object(strategy_demo.okx, "get_ticker", return_value=ticker_response()):
                    with patch.object(strategy_demo.okx, "get_instruments",
                                      return_value=instrument_response("SWAP")):
                        with patch.object(strategy_demo.okx, "get_account_config", return_value=config):
                            with patch.object(strategy_demo.okx, "close_position", close_position):
                                with patch.object(sys, "argv", [
                                    "strategy_demo.py", "swap-close",
                                    "--inst-id", "BTC-USDT-SWAP",
                                    "--mgn-mode", "cross", "--pos-side", "short",
                                    *AI_BUILDER_ARG,
                                ]):
                                    with self.assertRaises(SystemExit) as raised:
                                        strategy_demo.main()

        self.assertIn("--pos-side long", str(raised.exception))
        close_position.assert_not_called()

    def test_swap_close_rejects_inverse_swap_instrument(self):
        close_position = Mock(return_value={"code": "0", "data": [{"sCode": "0"}]})
        instrument = instrument_response(
            "SWAP", inst_id="BTC-USD-SWAP", ct_type="inverse", settle_ccy="BTC",
        )
        with patch.dict(os.environ, demo_env(), clear=True):
            with patch.object(strategy_demo, "load_dotenv", return_value=False):
                with patch.object(
                    strategy_demo.okx, "get_ticker",
                    return_value=ticker_response(inst_id="BTC-USD-SWAP"),
                ):
                    with patch.object(strategy_demo.okx, "get_instruments", return_value=instrument):
                        with patch.object(sys, "argv", [
                            "strategy_demo.py", "swap-close",
                            "--inst-id", "BTC-USD-SWAP", "--mgn-mode", "cross",
                            *AI_BUILDER_ARG,
                        ]):
                            with self.assertRaises(SystemExit) as raised:
                                strategy_demo.main()

        self.assertIn("only linear swap instruments", str(raised.exception))
        self.assertIn("inverse USD swap instruments are not supported", str(raised.exception))
        close_position.assert_not_called()

    def test_swap_close_requires_mgn_mode(self):
        close_position = Mock(return_value={"code": "0", "data": [{"sCode": "0"}]})
        with patch.object(strategy_demo, "load_dotenv", return_value=False):
            with patch.object(strategy_demo.okx, "close_position", close_position):
                with patch.object(sys, "argv", [
                    "strategy_demo.py", "swap-close", "--inst-id", "BTC-USDT-SWAP",
                    *AI_BUILDER_ARG,
                ]):
                    with patch("sys.stderr", new_callable=io.StringIO):
                        with self.assertRaises(SystemExit) as raised:
                            strategy_demo.main()

        self.assertEqual(raised.exception.code, 2)
        close_position.assert_not_called()


if __name__ == "__main__":
    unittest.main()
