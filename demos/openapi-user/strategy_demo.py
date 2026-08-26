import argparse
import json
import os
import re
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_UP

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False

import okx_openapi_client as okx


AI_BUILDER_CODE_PATTERN = re.compile(r"^[A-Za-z0-9]{1,16}$")
QUOTE_AMOUNT_STEP = Decimal("0.01")

SITE_BASE_URLS = {
    "global": "https://www.okx.com",
    "eea": "https://eea.okx.com",
    "us": "https://us.okx.com",
    "tr": "https://tr.okx.com",
}

def _required_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value or value.startswith("<"):
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def _env_choice(name: str, default: str, allowed: set) -> str:
    value = os.environ.get(name, default).lower()
    if value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise SystemExit(f"{name} must be one of: {choices}")
    return value


def _base_url() -> str:
    override = os.environ.get("OKX_API_BASE_URL")
    if override and not override.startswith("<"):
        return override.rstrip("/")
    site = _env_choice("OKX_SITE", "global", set(SITE_BASE_URLS))
    return SITE_BASE_URLS[site]


def _profile_credentials(profile: str) -> tuple:
    prefix = "OKX_DEMO" if profile == "demo" else "OKX_LIVE"
    return (
        _required_env(f"{prefix}_API_KEY"),
        _required_env(f"{prefix}_SECRET_KEY"),
        _required_env(f"{prefix}_PASSPHRASE"),
    )


def _ai_builder_code(value: str) -> str:
    code = value or ""
    if not code or code.startswith("<"):
        raise SystemExit("Missing required argument: --ai-builder-code")
    if not AI_BUILDER_CODE_PATTERN.match(code):
        raise SystemExit("AI Builder Code must be 1-16 alphanumeric characters")
    return code


def _add_ai_builder_code_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--ai-builder-code",
        required=True,
        help="AI Builder Code to send as OKX order tag; 1-16 alphanumeric characters",
    )


def _print_json(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _decimal(value, name: str) -> Decimal:
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise SystemExit(f"{name} must be a number")
    if dec <= 0:
        raise SystemExit(f"{name} must be greater than 0")
    return dec


def _fmt_decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _round_down(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        raise SystemExit("instrument lotSz must be greater than 0")
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def _round_up(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        raise SystemExit("instrument lotSz must be greater than 0")
    return (value / step).to_integral_value(rounding=ROUND_UP) * step


def _first_data(resp: dict, label: str) -> dict:
    if resp.get("code") != "0":
        raise SystemExit(f"{label} failed: code={resp.get('code')} msg={resp.get('msg')}")
    data = resp.get("data") or []
    if not data:
        raise SystemExit(f"{label} returned no data")
    return data[0]


def _okx_item_ok(resp: dict) -> bool:
    if resp.get("code") != "0":
        return False
    data = resp.get("data") or []
    if not data:
        return True
    s_code = data[0].get("sCode")
    return s_code in (None, "", "0")


def _balance_detail(resp: dict, ccy: str) -> dict:
    if resp.get("code") != "0":
        raise SystemExit(f"balance failed: code={resp.get('code')} msg={resp.get('msg')}")
    wanted = ccy.upper()
    for account in resp.get("data") or []:
        for detail in account.get("details") or []:
            if str(detail.get("ccy", "")).upper() == wanted:
                return detail
    return {}


def _available_balance(resp: dict, ccy: str) -> Decimal:
    detail = _balance_detail(resp, ccy)
    for key in ("availBal", "availEq", "cashBal", "eq"):
        value = detail.get(key)
        if value not in (None, ""):
            return Decimal(str(value))
    return Decimal("0")


def _last_price(ticker: dict) -> Decimal:
    for key in ("last", "askPx", "bidPx"):
        value = ticker.get(key)
        if value not in (None, "", "0"):
            return _decimal(value, f"ticker.{key}")
    raise SystemExit("ticker did not include a usable last, askPx, or bidPx")


def _instrument_rules(instrument: dict) -> dict:
    state = instrument.get("state")
    if state and state != "live":
        raise SystemExit(f"instrument {instrument.get('instId')} state is {state}, not live")
    return {
        "minSz": _decimal(instrument.get("minSz", "0"), "instrument.minSz"),
        "lotSz": _decimal(instrument.get("lotSz", "0"), "instrument.lotSz"),
        "tickSz": _decimal(instrument.get("tickSz", "0"), "instrument.tickSz"),
        "ctVal": Decimal(str(instrument.get("ctVal") or "0")),
        "state": state,
    }


def _supported_linear_swap_settle_ccy(instrument: dict) -> str:
    ct_type = str(instrument.get("ctType") or "").lower()
    settle_ccy = str(instrument.get("settleCcy") or "").upper()
    if ct_type == "linear" and settle_ccy:
        return settle_ccy
    raise SystemExit(
        "current demo supports only linear swap instruments, "
        "such as BTC-USDT-SWAP; inverse USD swap instruments are not supported. "
        f"{instrument.get('instId')} has ctType={ct_type or '(empty)'} "
        f"and settleCcy={settle_ccy or '(empty)'}"
    )


def _spot_currencies(inst_id: str, instrument: dict) -> tuple:
    parts = inst_id.split("-")
    base_ccy = (instrument.get("baseCcy") or (parts[0] if len(parts) >= 2 else "")).upper()
    quote_ccy = (instrument.get("quoteCcy") or (parts[1] if len(parts) >= 2 else "")).upper()
    if not base_ccy or not quote_ccy:
        raise SystemExit(f"could not determine base/quote currency for spot instrument {inst_id}")
    return base_ccy, quote_ccy


def _position_mode(config_resp: dict) -> str:
    config = _first_data(config_resp, "account config")
    return config.get("posMode") or ""


def _account_level(config_resp: dict) -> str:
    config = _first_data(config_resp, "account config")
    return str(config.get("acctLv") or "")


def _required_trade_mode(value: str, name: str, allowed: set) -> str:
    if not value:
        raise SystemExit(f"{name} is required")
    value = value.strip().lower()
    if value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise SystemExit(f"{name} must be one of: {choices}")
    return value


def _default_spot_td_mode(config_resp: dict) -> str:
    acct_lv = _account_level(config_resp)
    if acct_lv in ("1", "2"):
        return "cash"
    if acct_lv in ("3", "4"):
        return "cross"
    raise SystemExit(f"unsupported or missing acctLv for spot workflow: {acct_lv or '(empty)'}")


def _spot_td_mode(value: str, config_resp: dict) -> str:
    if value:
        td_mode = _required_trade_mode(value, "--td-mode", {"cash", "cross", "isolated"})
    else:
        td_mode = _default_spot_td_mode(config_resp)
    acct_lv = _account_level(config_resp)
    if acct_lv == "1" and td_mode != "cash":
        raise SystemExit("spot account mode acctLv=1 requires --td-mode cash")
    if acct_lv in ("3", "4") and td_mode != "cross":
        raise SystemExit(f"account mode acctLv={acct_lv} requires spot --td-mode cross")
    return td_mode


def _require_swap_account_mode(config_resp: dict) -> str:
    acct_lv = _account_level(config_resp)
    if acct_lv not in ("2", "3", "4"):
        raise SystemExit(
            "swap workflows require account mode acctLv=2, 3, or 4; "
            f"current acctLv={acct_lv or '(empty)'}"
        )
    return acct_lv


def _default_swap_td_mode(config_resp: dict) -> str:
    _require_swap_account_mode(config_resp)
    return "cross"


def _swap_td_mode(value: str, config_resp: dict) -> str:
    _require_swap_account_mode(config_resp)
    if value:
        return _required_trade_mode(value, "--td-mode", {"cross", "isolated"})
    return _default_swap_td_mode(config_resp)


def _workflow_pos_side(config_resp: dict, requested: str = None) -> str:
    pos_mode = _position_mode(config_resp)
    if pos_mode == "long_short_mode":
        if requested in (None, "", "long"):
            return "long"
        raise SystemExit(
            "this demo workflow opens and closes the long side; "
            "use --pos-side long in posMode=long_short_mode"
        )
    if pos_mode == "net_mode":
        if requested in (None, "", "net"):
            return None
        raise SystemExit("posMode=net_mode uses net positions; omit --pos-side")
    raise SystemExit(f"unsupported or missing posMode for swap workflow: {pos_mode or '(empty)'}")


def _workflow_result(name: str, profile: str, simulated: bool,
                     preflight: dict, sent: dict, raw: dict) -> dict:
    return {
        "ok": _okx_item_ok(raw),
        "workflow": name,
        "profile": profile,
        "simulated": simulated,
        "sent_ai_builder_code": sent.get("tag", ""),
        "preflight": preflight,
        "sent_order": sent,
        "raw": raw,
    }


def _get_market_preflight(base_url: str, simulated: bool,
                          inst_type: str, inst_id: str) -> tuple:
    ticker = _first_data(okx.get_ticker(base_url, inst_id, simulated=simulated), "ticker")
    instrument = _first_data(
        okx.get_instruments(base_url, inst_type, inst_id, simulated=simulated),
        "instruments",
    )
    rules = _instrument_rules(instrument)
    last = _last_price(ticker)
    return ticker, instrument, rules, last


def _spot_open(args, profile: str, simulated: bool, base_url: str,
               api_key: str, secret_key: str, passphrase: str) -> dict:
    ai_builder_code = _ai_builder_code(args.ai_builder_code)
    _guard_live_order(profile, args.confirm_live_order)

    _, instrument, rules, last = _get_market_preflight(
        base_url, simulated, "SPOT", args.inst_id,
    )
    base_ccy, quote_ccy = _spot_currencies(args.inst_id, instrument)
    config = okx.get_account_config(
        base_url, api_key, secret_key, passphrase, simulated=simulated,
    )
    td_mode = _spot_td_mode(args.td_mode, config)
    min_quote = rules["minSz"] * last * Decimal("1.05")
    requested = _decimal(args.quote_amount, "--quote-amount")
    quote_amount = _round_up(max(requested, min_quote), QUOTE_AMOUNT_STEP)

    balance = okx.get_account_balance(
        base_url, api_key, secret_key, passphrase,
        simulated=simulated,
    )
    available_quote = _available_balance(balance, quote_ccy)
    if available_quote < quote_amount:
        raise SystemExit(
            f"available {quote_ccy} {available_quote} is below required quote amount "
            f"{quote_amount}"
        )

    sent = {
        "instId": args.inst_id,
        "tdMode": td_mode,
        "side": "buy",
        "ordType": "market",
        "sz": _fmt_decimal(quote_amount),
        "tgtCcy": "quote_ccy",
        "tag": ai_builder_code,
    }
    raw = okx.place_order(
        base_url, api_key, secret_key, passphrase,
        args.inst_id, td_mode, "buy", "market", sent["sz"],
        tgt_ccy="quote_ccy",
        ai_builder_code=ai_builder_code,
        simulated=simulated,
    )
    return _workflow_result("spot-open", profile, simulated, {
        "instType": "SPOT",
        "instId": args.inst_id,
        "last": _fmt_decimal(last),
        "minSz": _fmt_decimal(rules["minSz"]),
        "lotSz": _fmt_decimal(rules["lotSz"]),
        "tickSz": _fmt_decimal(rules["tickSz"]),
        "instrumentState": instrument.get("state"),
        "baseCcy": base_ccy,
        "quoteCcy": quote_ccy,
        "tdMode": td_mode,
        "acctLv": _account_level(config),
        "availableQuoteBalance": _fmt_decimal(available_quote),
        "requestedQuoteAmount": _fmt_decimal(requested),
        "finalQuoteAmount": _fmt_decimal(quote_amount),
        f"available{quote_ccy}": _fmt_decimal(available_quote),
        f"requestedQuoteAmount{quote_ccy}": _fmt_decimal(requested),
        f"finalQuoteAmount{quote_ccy}": _fmt_decimal(quote_amount),
    }, sent, raw)


def _spot_close(args, profile: str, simulated: bool, base_url: str,
                api_key: str, secret_key: str, passphrase: str) -> dict:
    ai_builder_code = _ai_builder_code(args.ai_builder_code)
    _guard_live_order(profile, args.confirm_live_order)

    _, instrument, rules, last = _get_market_preflight(
        base_url, simulated, "SPOT", args.inst_id,
    )
    base_ccy, quote_ccy = _spot_currencies(args.inst_id, instrument)
    config = okx.get_account_config(
        base_url, api_key, secret_key, passphrase, simulated=simulated,
    )
    td_mode = _spot_td_mode(args.td_mode, config)
    balance = okx.get_account_balance(
        base_url, api_key, secret_key, passphrase,
        simulated=simulated,
    )
    available_base = _round_down(_available_balance(balance, base_ccy), rules["lotSz"])
    requested_quote_amount = None
    requested_base_size = None
    if args.base_size:
        requested_base_size = _decimal(args.base_size, "--base-size")
        sell_size = _round_down(requested_base_size, rules["lotSz"])
        if sell_size > available_base:
            raise SystemExit(
                f"requested --base-size {sell_size} exceeds available "
                f"{base_ccy} {available_base}"
            )
    else:
        requested_quote_amount = _decimal(args.quote_amount, "--quote-amount")
        sell_size = _round_down(requested_quote_amount / last, rules["lotSz"])
        if sell_size < rules["minSz"]:
            sell_size = _round_up(rules["minSz"], rules["lotSz"])
        if sell_size > available_base:
            sell_size = available_base
    if sell_size < rules["minSz"]:
        raise SystemExit(
            f"available {base_ccy} {available_base} is below minimum sell size "
            f"{rules['minSz']}"
        )

    sent = {
        "instId": args.inst_id,
        "tdMode": td_mode,
        "side": "sell",
        "ordType": "market",
        "sz": _fmt_decimal(sell_size),
        "tag": ai_builder_code,
    }
    raw = okx.place_order(
        base_url, api_key, secret_key, passphrase,
        args.inst_id, td_mode, "sell", "market", sent["sz"],
        ai_builder_code=ai_builder_code,
        simulated=simulated,
    )
    return _workflow_result("spot-close", profile, simulated, {
        "instType": "SPOT",
        "instId": args.inst_id,
        "last": _fmt_decimal(last),
        "minSz": _fmt_decimal(rules["minSz"]),
        "lotSz": _fmt_decimal(rules["lotSz"]),
        "tickSz": _fmt_decimal(rules["tickSz"]),
        "instrumentState": instrument.get("state"),
        "baseCcy": base_ccy,
        "quoteCcy": quote_ccy,
        "tdMode": td_mode,
        "acctLv": _account_level(config),
        "availableBaseBalance": _fmt_decimal(available_base),
        "requestedQuoteAmount": (
            _fmt_decimal(requested_quote_amount) if requested_quote_amount else None
        ),
        "requestedBaseSize": (
            _fmt_decimal(requested_base_size) if requested_base_size else None
        ),
        f"available{base_ccy}": _fmt_decimal(available_base),
        f"requestedQuoteAmount{quote_ccy}": (
            _fmt_decimal(requested_quote_amount) if requested_quote_amount else None
        ),
    }, sent, raw)


def _swap_open(args, profile: str, simulated: bool, base_url: str,
               api_key: str, secret_key: str, passphrase: str) -> dict:
    ai_builder_code = _ai_builder_code(args.ai_builder_code)
    _guard_live_order(profile, args.confirm_live_order)

    _, instrument, rules, last = _get_market_preflight(
        base_url, simulated, "SWAP", args.inst_id,
    )
    settle_ccy = _supported_linear_swap_settle_ccy(instrument)
    if rules["ctVal"] <= 0:
        raise SystemExit(f"instrument {args.inst_id} did not include a valid ctVal")

    if args.contracts:
        contracts = _round_up(_decimal(args.contracts, "--contracts"), rules["lotSz"])
        requested_quote_amount = None
    else:
        requested_quote_amount = _decimal(args.quote_amount, "--quote-amount")
        contracts = _round_up(requested_quote_amount / (rules["ctVal"] * last), rules["lotSz"])
    if contracts < rules["minSz"]:
        contracts = _round_up(rules["minSz"], rules["lotSz"])

    config = okx.get_account_config(
        base_url, api_key, secret_key, passphrase, simulated=simulated,
    )
    td_mode = _swap_td_mode(args.td_mode, config)
    pos_side = _workflow_pos_side(config, args.pos_side)

    balance = okx.get_account_balance(
        base_url, api_key, secret_key, passphrase,
        simulated=simulated,
    )
    available_settle = _available_balance(balance, settle_ccy)
    estimated_notional = contracts * rules["ctVal"] * last
    if available_settle < estimated_notional:
        raise SystemExit(
            f"available {settle_ccy} {available_settle} is below estimated notional "
            f"{estimated_notional}"
        )

    sent = {
        "instId": args.inst_id,
        "tdMode": td_mode,
        "side": "buy",
        "ordType": "market",
        "sz": _fmt_decimal(contracts),
        "tag": ai_builder_code,
    }
    if pos_side:
        sent["posSide"] = pos_side
    raw = okx.place_order(
        base_url, api_key, secret_key, passphrase,
        args.inst_id, td_mode, "buy", "market", sent["sz"],
        pos_side=pos_side,
        ai_builder_code=ai_builder_code,
        simulated=simulated,
    )
    return _workflow_result("swap-open", profile, simulated, {
        "instType": "SWAP",
        "instId": args.inst_id,
        "last": _fmt_decimal(last),
        "ctType": instrument.get("ctType"),
        "ctVal": _fmt_decimal(rules["ctVal"]),
        "ctValCcy": instrument.get("ctValCcy"),
        "settleCcy": settle_ccy,
        "minSz": _fmt_decimal(rules["minSz"]),
        "lotSz": _fmt_decimal(rules["lotSz"]),
        "tickSz": _fmt_decimal(rules["tickSz"]),
        "instrumentState": instrument.get("state"),
        "acctLv": _account_level(config),
        "tdMode": td_mode,
        "posMode": _position_mode(config),
        "availableSettleBalance": _fmt_decimal(available_settle),
        "estimatedNotional": _fmt_decimal(estimated_notional),
        "requestedQuoteAmount": _fmt_decimal(requested_quote_amount) if requested_quote_amount else None,
        f"available{settle_ccy}": _fmt_decimal(available_settle),
        f"estimatedNotional{settle_ccy}": _fmt_decimal(estimated_notional),
        f"requestedQuoteAmount{settle_ccy}": (
            _fmt_decimal(requested_quote_amount) if requested_quote_amount else None
        ),
    }, sent, raw)


def _find_open_position(positions_resp: dict, inst_id: str,
                        pos_side: str = None, mgn_mode: str = None) -> dict:
    if positions_resp.get("code") != "0":
        raise SystemExit(
            f"positions failed: code={positions_resp.get('code')} "
            f"msg={positions_resp.get('msg')}"
        )
    for position in positions_resp.get("data") or []:
        if position.get("instId") != inst_id:
            continue
        size = Decimal(str(position.get("pos") or "0"))
        if size == 0:
            continue
        actual_side = position.get("posSide")
        if pos_side and actual_side not in (pos_side, "net", None, ""):
            continue
        actual_mgn_mode = position.get("mgnMode")
        if mgn_mode and actual_mgn_mode and actual_mgn_mode != mgn_mode:
            continue
        return position
    return {}


def _swap_close(args, profile: str, simulated: bool, base_url: str,
                api_key: str, secret_key: str, passphrase: str) -> dict:
    ai_builder_code = _ai_builder_code(args.ai_builder_code)
    _guard_live_order(profile, args.confirm_live_order)
    mgn_mode = _required_trade_mode(args.mgn_mode, "--mgn-mode",
                                    {"cross", "isolated"})
    _, instrument, _, _ = _get_market_preflight(
        base_url, simulated, "SWAP", args.inst_id,
    )
    settle_ccy = _supported_linear_swap_settle_ccy(instrument)

    config = okx.get_account_config(
        base_url, api_key, secret_key, passphrase, simulated=simulated,
    )
    _require_swap_account_mode(config)
    pos_side = _workflow_pos_side(config, args.pos_side)
    positions = okx.get_positions(
        base_url, api_key, secret_key, passphrase,
        inst_type="SWAP", inst_id=args.inst_id, simulated=simulated,
    )
    position = _find_open_position(positions, args.inst_id, pos_side, mgn_mode)
    if not position:
        raise SystemExit(f"no open {args.inst_id} position found to close")

    sent = {
        "instId": args.inst_id,
        "mgnMode": mgn_mode,
        "autoCxl": str(args.auto_cxl).lower(),
        "tag": ai_builder_code,
    }
    if pos_side:
        sent["posSide"] = pos_side
    raw = okx.close_position(
        base_url, api_key, secret_key, passphrase,
        args.inst_id, mgn_mode,
        pos_side=pos_side,
        auto_cxl=args.auto_cxl,
        ai_builder_code=ai_builder_code,
        simulated=simulated,
    )
    return _workflow_result("swap-close", profile, simulated, {
        "instType": "SWAP",
        "instId": args.inst_id,
        "ctType": instrument.get("ctType"),
        "settleCcy": settle_ccy,
        "acctLv": _account_level(config),
        "mgnMode": mgn_mode,
        "posMode": _position_mode(config),
        "position": {
            "pos": position.get("pos"),
            "posSide": position.get("posSide"),
            "mgnMode": position.get("mgnMode"),
            "avgPx": position.get("avgPx"),
            "upl": position.get("upl"),
        },
    }, sent, raw)


def _guard_live_order(profile: str, confirmed: bool) -> None:
    if profile == "live" and not confirmed:
        raise SystemExit("Refusing live order without --confirm-live-order")


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Self account OKX OpenAPI demo")
    sub = parser.add_subparsers(dest="command", required=True)

    balance = sub.add_parser("balance", help="Query account balance")
    balance.add_argument("--ccy", help="Optional currency filter, for example BTC or BTC,USDT")

    order = sub.add_parser("order", help="Place an order with AI Builder Code as OKX tag")
    order.add_argument("--inst-id", default="BTC-USDT")
    order.add_argument("--td-mode", choices=["cash", "cross", "isolated"], default="cash")
    order.add_argument("--side", choices=["buy", "sell"], default="buy")
    order.add_argument("--ord-type", choices=["market", "limit", "post_only", "fok", "ioc"],
                       default="limit")
    order.add_argument("--sz", default="0.00000001")
    order.add_argument("--px", default="1000")
    order.add_argument("--tgt-ccy", choices=["base_ccy", "quote_ccy"])
    order.add_argument("--cl-ord-id", help="Client order ID, max 32 characters")
    order.add_argument("--tp-trigger-px")
    order.add_argument("--tp-ord-px")
    order.add_argument("--tp-ord-kind", choices=["condition", "limit"])
    order.add_argument("--tp-trigger-px-type", choices=["last", "index", "mark"])
    order.add_argument("--sl-trigger-px")
    order.add_argument("--sl-ord-px")
    order.add_argument("--sl-trigger-px-type", choices=["last", "index", "mark"])
    order.add_argument("--stp-mode", choices=["cancel_maker", "cancel_taker", "cancel_both"])
    order.add_argument("--trade-quote-ccy")
    order.add_argument("--ban-amend", action="store_true")
    order.add_argument("--px-amend-type", choices=["0", "1"])
    order.add_argument("--pos-side", choices=["long", "short", "net"])
    order.add_argument("--reduce-only", action="store_true")
    _add_ai_builder_code_arg(order)
    order.add_argument("--confirm-live-order", action="store_true",
                       help="Required when OKX_PROFILE=live")

    spot_open = sub.add_parser("spot-open", help="Demo workflow: buy spot with quote currency")
    spot_open.add_argument("--inst-id", required=True)
    spot_open.add_argument("--td-mode", choices=["cash", "cross", "isolated"],
                           help="Override OKX trade mode for the spot order")
    spot_open.add_argument("--quote-amount", required=True,
                           help="Target quote-currency amount before min-size adjustment")
    _add_ai_builder_code_arg(spot_open)
    spot_open.add_argument("--confirm-live-order", action="store_true",
                           help="Required when OKX_PROFILE=live")

    spot_close = sub.add_parser("spot-close", help="Demo workflow: sell spot")
    spot_close.add_argument("--inst-id", required=True)
    spot_close.add_argument("--td-mode", choices=["cash", "cross", "isolated"],
                            help="Override OKX trade mode for the spot order")
    spot_close_size = spot_close.add_mutually_exclusive_group(required=True)
    spot_close_size.add_argument("--quote-amount",
                                 help="Target quote value to convert into base size")
    spot_close_size.add_argument("--base-size", help="Exact base-currency size to sell")
    _add_ai_builder_code_arg(spot_close)
    spot_close.add_argument("--confirm-live-order", action="store_true",
                            help="Required when OKX_PROFILE=live")

    swap_open = sub.add_parser("swap-open", help="Demo workflow: open a swap long")
    swap_open.add_argument("--inst-id", required=True)
    swap_open.add_argument("--td-mode", choices=["cross", "isolated"],
                           help="Override OKX trade mode for the swap order")
    swap_open_size = swap_open.add_mutually_exclusive_group(required=True)
    swap_open_size.add_argument("--quote-amount",
                                help="Target settlement-currency notional before contract-size adjustment")
    swap_open_size.add_argument("--contracts",
                                help="Exact contract count instead of quote amount")
    swap_open.add_argument("--pos-side", choices=["long", "short", "net"],
                           help="Defaults to long only when account posMode is long_short_mode")
    _add_ai_builder_code_arg(swap_open)
    swap_open.add_argument("--confirm-live-order", action="store_true",
                           help="Required when OKX_PROFILE=live")

    swap_close = sub.add_parser("swap-close", help="Demo workflow: close a swap long")
    swap_close.add_argument("--inst-id", required=True)
    swap_close.add_argument("--mgn-mode", choices=["cross", "isolated"], required=True,
                            help="OKX margin mode to send on close-position")
    swap_close.add_argument("--pos-side", choices=["long", "short", "net"],
                            help="Defaults to long only when account posMode is long_short_mode")
    swap_close.add_argument("--no-auto-cxl", dest="auto_cxl", action="store_false",
                            help="Do not auto-cancel outstanding orders on close-position")
    _add_ai_builder_code_arg(swap_close)
    swap_close.add_argument("--confirm-live-order", action="store_true",
                            help="Required when OKX_PROFILE=live")
    swap_close.set_defaults(auto_cxl=True)

    args = parser.parse_args()

    profile = _env_choice("OKX_PROFILE", "demo", {"demo", "live"})
    simulated = profile == "demo"
    base_url = _base_url()
    api_key, secret_key, passphrase = _profile_credentials(profile)

    if args.command == "balance":
        _print_json(okx.get_account_balance(
            base_url, api_key, secret_key, passphrase,
            ccy=args.ccy, simulated=simulated,
        ))
        return

    if args.command == "spot-open":
        _print_json(_spot_open(
            args, profile, simulated, base_url, api_key, secret_key, passphrase,
        ))
        return

    if args.command == "spot-close":
        _print_json(_spot_close(
            args, profile, simulated, base_url, api_key, secret_key, passphrase,
        ))
        return

    if args.command == "swap-open":
        _print_json(_swap_open(
            args, profile, simulated, base_url, api_key, secret_key, passphrase,
        ))
        return

    if args.command == "swap-close":
        _print_json(_swap_close(
            args, profile, simulated, base_url, api_key, secret_key, passphrase,
        ))
        return

    ai_builder_code = _ai_builder_code(args.ai_builder_code)
    _guard_live_order(profile, args.confirm_live_order)
    if args.ord_type == "market":
        args.px = None
    elif not args.px:
        raise SystemExit(f"--px is required for ordType={args.ord_type}")

    _print_json(okx.place_order(
        base_url, api_key, secret_key, passphrase,
        args.inst_id, args.td_mode, args.side, args.ord_type, args.sz,
        px=args.px,
        tgt_ccy=args.tgt_ccy,
        cl_ord_id=args.cl_ord_id,
        tp_trigger_px=args.tp_trigger_px,
        tp_ord_px=args.tp_ord_px,
        tp_ord_kind=args.tp_ord_kind,
        tp_trigger_px_type=args.tp_trigger_px_type,
        sl_trigger_px=args.sl_trigger_px,
        sl_ord_px=args.sl_ord_px,
        sl_trigger_px_type=args.sl_trigger_px_type,
        stp_mode=args.stp_mode,
        trade_quote_ccy=args.trade_quote_ccy,
        ban_amend=args.ban_amend,
        px_amend_type=args.px_amend_type,
        pos_side=None if args.pos_side == "net" else args.pos_side,
        reduce_only=args.reduce_only,
        ai_builder_code=ai_builder_code,
        simulated=simulated,
    ))


if __name__ == "__main__":
    main()
