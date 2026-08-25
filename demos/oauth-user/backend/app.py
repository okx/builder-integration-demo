"""
Reference Flask backend for the OKX Fast API demo.

Flow:
  Browser authorizes with scope=fast_api -> callback includes code
    -> backend exchanges code for access_token with client_secret
    -> backend deletes old Fast API Key to avoid 50116
    -> backend creates a Fast API Key and stores it server-side
    -> backend signs OKX OpenAPI requests with the created API Key.

Run from demos/oauth-user:
  test -f .env || cp .env.example .env
  test -d .tmpvenv || python3 -m venv .tmpvenv
  source .tmpvenv/bin/activate
  python -m pip install -r requirements.txt
  python backend/app.py
  open http://localhost:8000
"""

import os
import re
import secrets
import uuid
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_UP

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

import okx_client as okx

if os.environ.get("OKX_FASTAPI_DEMO_SKIP_DOTENV") != "1":
    load_dotenv()

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
app = Flask(__name__, static_folder=None)

# Configuration comes only from environment variables. Never hard-code secrets.
CLIENT_ID         = os.environ.get("CLIENT_ID", "")
CLIENT_SECRET     = os.environ.get("CLIENT_SECRET", "")
REDIRECT_URI      = os.environ.get("REDIRECT_URI", "http://localhost:8000/")
SCOPE             = "fast_api"
OKX_BASE_URL      = (os.environ.get("OKX_BASE_URL", "https://www.okx.com") or "https://www.okx.com").rstrip("/")
SIMULATED         = os.environ.get("SIMULATED", "1") == "1"        # Safe default.
MOCK              = os.environ.get("MOCK", "") == "1"              # Test-only; not a demo config.
APIKEY_PASSPHRASE = os.environ.get("APIKEY_PASSPHRASE", "")
APIKEY_LABEL      = os.environ.get("APIKEY_LABEL", "demo")
APIKEY_PERM       = os.environ.get("APIKEY_PERM", "read_only")     # Safe default.
AI_BUILDER_CODE   = os.environ.get("AI_BUILDER_CODE", "")          # Sent as OKX order tag.
AI_BUILDER_CODE_PATTERN = re.compile(r"^[A-Za-z0-9]{1,16}$")
QUOTE_AMOUNT_STEP = Decimal("0.01")
DEMO_SPOT_INST_ID = "BTC-USDT"
DEMO_SWAP_INST_ID = "BTC-USDT-SWAP"
DEMO_QUOTE_AMOUNT = "10"
DEMO_SWAP_CLOSE_MGN_MODE = "cross"

# Callback domain is external input. Allowlist it before using it as a base URL;
# otherwise an attacker could redirect backend token/API requests to another host.
ALLOWED_DOMAINS = {"https://www.okx.com", "https://tr.okx.com", "https://eea.okx.com"}

# DEMO ONLY: process-memory storage keyed by browser session.
# Production must store API Keys encrypted at rest and isolated per user.
_CREDS = {}  # {session_id: {"api_key","secret_key","passphrase","base"}}


def _get_or_create_sid() -> str:
    return request.cookies.get("demo_sid") or uuid.uuid4().hex


def _json_error(message: str, status: int = 400, **extra):
    body = {"ok": False, "error": message}
    body.update(extra)
    return jsonify(body), status


def _session_creds():
    return _CREDS.get(request.cookies.get("demo_sid", ""))


def _clear_session_creds() -> None:
    sid = request.cookies.get("demo_sid", "")
    if sid:
        _CREDS.pop(sid, None)


def _has_trade_permission(creds: dict) -> bool:
    perm_parts = str(creds.get("perm") or "").lower().split(",")
    return "trade" in {part.strip() for part in perm_parts if part.strip()}


def _require_trade_permission(creds: dict) -> None:
    if not _has_trade_permission(creds):
        raise ValueError("created API Key does not have trade permission")


def _require_ai_builder_code() -> str:
    if not AI_BUILDER_CODE or AI_BUILDER_CODE.startswith("<"):
        raise ValueError("missing AI_BUILDER_CODE")
    if not AI_BUILDER_CODE_PATTERN.match(AI_BUILDER_CODE):
        raise ValueError("AI_BUILDER_CODE must be 1-16 alphanumeric characters")
    return AI_BUILDER_CODE


def _validate_apikey_passphrase(passphrase: str) -> str:
    value = (passphrase or "").strip()
    if not value or value.startswith("<"):
        raise ValueError("APIKEY_PASSPHRASE must be configured before connecting")
    if len(value) < 8 or len(value) > 32:
        raise ValueError("APIKEY_PASSPHRASE must be 8-32 characters")
    if not re.search(r"[A-Z]", value):
        raise ValueError("APIKEY_PASSPHRASE must include an uppercase letter")
    if not re.search(r"[a-z]", value):
        raise ValueError("APIKEY_PASSPHRASE must include a lowercase letter")
    if not re.search(r"\d", value):
        raise ValueError("APIKEY_PASSPHRASE must include a number")
    if not re.search(r"[^A-Za-z0-9]", value):
        raise ValueError("APIKEY_PASSPHRASE must include a special character")
    return value


def _validate_apikey_label(label: str) -> str:
    value = (label or "").strip()
    if not value or value.startswith("<"):
        raise ValueError("APIKEY_LABEL must be non-empty")
    return value


def _validate_apikey_perm(perm: str) -> str:
    value = (perm or "").strip().lower()
    if value not in {"read_only", "trade"}:
        raise ValueError("APIKEY_PERM must be read_only or trade")
    return value


def _validated_apikey_config() -> dict:
    return {
        "passphrase": _validate_apikey_passphrase(APIKEY_PASSPHRASE),
        "label": _validate_apikey_label(APIKEY_LABEL),
        "perm": _validate_apikey_perm(APIKEY_PERM),
    }


def _validate_oauth_config() -> None:
    if MOCK:
        return
    client_id = CLIENT_ID.strip()
    client_secret = CLIENT_SECRET.strip()
    if not client_id or client_id.lower() in {"your_client_id", "..."} or client_id.startswith("<"):
        raise ValueError("CLIENT_ID must be configured before real OAuth connect")
    if not client_secret or client_secret.lower() in {"your_client_secret", "..."} or client_secret.startswith("<"):
        raise ValueError("CLIENT_SECRET must be configured before real OAuth connect")


def _callback_base_url(domain: str) -> str:
    if not domain:
        base = OKX_BASE_URL
    else:
        base = str(domain).strip().rstrip("/")
    if base not in ALLOWED_DOMAINS:
        if domain:
            raise ValueError(f"callback domain is not allowlisted: {domain}")
        raise ValueError(f"OKX_BASE_URL is not allowlisted: {OKX_BASE_URL}")
    return base


def _bool_arg(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("1", "true", "yes", "y", "on"):
            return True
        if lowered in ("0", "false", "no", "n", "off", ""):
            return False
    raise ValueError(f"invalid boolean value: {value}")


def _guard_live_workflow(data: dict) -> None:
    if not SIMULATED and not _bool_arg(data.get("confirmLiveOrder"), False):
        raise ValueError("live workflow requires confirmLiveOrder=true")


def _decimal(value, name: str) -> Decimal:
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{name} must be a number")
    if not dec.is_finite():
        raise ValueError(f"{name} must be a finite number")
    if dec <= 0:
        raise ValueError(f"{name} must be greater than 0")
    return dec


def _required_order_text(data: dict, name: str) -> str:
    value = data.get(name)
    if value is None or str(value).strip() == "":
        raise ValueError(f"missing {name}")
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value.strip()


def _optional_order_text(value, name: str) -> str:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    value = value.strip()
    return value or None


def _required_order_enum(data: dict, name: str, allowed: set, default: str = None) -> str:
    value = data.get(name)
    if value in (None, ""):
        if default is None:
            raise ValueError(f"missing {name}")
        value = default
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    value = value.strip().lower()
    if value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(f"{name} must be one of: {choices}")
    return value


def _required_text(data: dict, name: str) -> str:
    value = data.get(name)
    if value is None or str(value).strip() == "":
        raise ValueError(f"missing {name}")
    return str(value).strip()


def _optional_text(value, name: str) -> str:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    value = value.strip()
    return value or None


def _fmt_decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _round_down(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        raise ValueError("instrument lotSz must be greater than 0")
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def _round_up(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        raise ValueError("instrument lotSz must be greater than 0")
    return (value / step).to_integral_value(rounding=ROUND_UP) * step


def _first_data(resp: dict, label: str) -> dict:
    if resp.get("code") != "0":
        raise ValueError(f"{label} failed: code={resp.get('code')} msg={resp.get('msg')}")
    data = resp.get("data") or []
    if not data:
        raise ValueError(f"{label} returned no data")
    return data[0]


def _okx_item_ok(resp: dict) -> bool:
    if resp.get("code") != "0":
        return False
    data = resp.get("data") or []
    if not data:
        return True
    return data[0].get("sCode") in (None, "", "0")


def _balance_detail(resp: dict, ccy: str) -> dict:
    if resp.get("code") != "0":
        raise ValueError(f"balance failed: code={resp.get('code')} msg={resp.get('msg')}")
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
    raise ValueError("ticker did not include a usable last, askPx, or bidPx")


def _instrument_rules(instrument: dict) -> dict:
    state = instrument.get("state")
    if state and state != "live":
        raise ValueError(f"instrument {instrument.get('instId')} state is {state}, not live")
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
    raise ValueError(
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
        raise ValueError(f"could not determine base/quote currency for spot instrument {inst_id}")
    return base_ccy, quote_ccy


def _position_mode(config_resp: dict) -> str:
    return _first_data(config_resp, "account config").get("posMode") or ""


def _account_level(config_resp: dict) -> str:
    return str(_first_data(config_resp, "account config").get("acctLv") or "")


def _required_trade_mode(value: str, name: str, allowed: set, default: str = None) -> str:
    if value is None or value == "":
        if default is None:
            raise ValueError(f"missing {name}")
        value = default
    elif not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    value = value.strip().lower()
    if not value:
        if default is None:
            raise ValueError(f"missing {name}")
        value = default
    if value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(f"{name} must be one of: {choices}")
    return value


def _default_spot_td_mode(config_resp: dict) -> str:
    acct_lv = _account_level(config_resp)
    if acct_lv in ("1", "2"):
        return "cash"
    if acct_lv in ("3", "4"):
        return "cross"
    raise ValueError(f"unsupported or missing acctLv for spot workflow: {acct_lv or '(empty)'}")


def _spot_td_mode(value: str, config_resp: dict) -> str:
    if value is not None and value != "":
        td_mode = _required_trade_mode(value, "tdMode", {"cash", "cross", "isolated"})
    else:
        td_mode = _default_spot_td_mode(config_resp)
    acct_lv = _account_level(config_resp)
    if acct_lv == "1" and td_mode != "cash":
        raise ValueError("spot account mode acctLv=1 requires tdMode=cash")
    if acct_lv in ("3", "4") and td_mode != "cross":
        raise ValueError(f"account mode acctLv={acct_lv} requires spot tdMode=cross")
    return td_mode


def _require_swap_account_mode(config_resp: dict) -> str:
    acct_lv = _account_level(config_resp)
    if acct_lv not in ("2", "3", "4"):
        raise ValueError(
            "swap workflows require account mode acctLv=2, 3, or 4; "
            f"current acctLv={acct_lv or '(empty)'}"
        )
    return acct_lv


def _default_swap_td_mode(config_resp: dict) -> str:
    _require_swap_account_mode(config_resp)
    return "cross"


def _swap_td_mode(value: str, config_resp: dict) -> str:
    _require_swap_account_mode(config_resp)
    if value is not None and value != "":
        return _required_trade_mode(value, "tdMode", {"cross", "isolated"})
    return _default_swap_td_mode(config_resp)


def _workflow_pos_side(config_resp: dict, requested=None) -> str:
    requested = _optional_text(requested, "posSide")
    if requested and requested not in {"long", "short", "net"}:
        raise ValueError("posSide must be one of: long, net, short")
    pos_mode = _position_mode(config_resp)
    if pos_mode == "long_short_mode":
        if requested in (None, "long"):
            return "long"
        raise ValueError(
            "this demo workflow opens and closes the long side; "
            "use posSide=long in posMode=long_short_mode"
        )
    if pos_mode == "net_mode":
        if requested in (None, "net"):
            return None
        raise ValueError("posMode=net_mode uses net positions; omit posSide")
    raise ValueError(f"unsupported or missing posMode for swap workflow: {pos_mode or '(empty)'}")


def _workflow_pos_side_field(config_resp: dict) -> str:
    return _workflow_pos_side(config_resp) or "net"


def _demo_workflow_fields(config_resp: dict) -> dict:
    spot_td_mode = _spot_td_mode(None, config_resp)
    acct_lv = _account_level(config_resp)
    pos_mode = _position_mode(config_resp)
    swap = {
        "available": False,
        "instId": DEMO_SWAP_INST_ID,
        "quoteAmount": DEMO_QUOTE_AMOUNT,
        "tdMode": "cross",
        "mgnMode": DEMO_SWAP_CLOSE_MGN_MODE,
        "posSide": "net",
    }
    try:
        swap["tdMode"] = _swap_td_mode(None, config_resp)
        swap["posSide"] = _workflow_pos_side_field(config_resp)
        swap["available"] = True
    except ValueError as exc:
        swap["unavailableReason"] = str(exc)
    return {
        "account": {
            "acctLv": acct_lv,
            "posMode": pos_mode,
        },
        "fields": {
            "spot": {
                "available": True,
                "instId": DEMO_SPOT_INST_ID,
                "quoteAmount": DEMO_QUOTE_AMOUNT,
                "tdMode": spot_td_mode,
            },
            "swap": swap,
        },
    }


def _get_market_preflight(base_url: str, inst_type: str, inst_id: str) -> tuple:
    ticker = _first_data(okx.get_ticker(base_url, inst_id, simulated=SIMULATED), "ticker")
    instrument = _first_data(
        okx.get_instruments(base_url, inst_type, inst_id, simulated=SIMULATED),
        "instruments",
    )
    rules = _instrument_rules(instrument)
    last = _last_price(ticker)
    return instrument, rules, last


def _workflow_result(name: str, preflight: dict, sent: dict, raw: dict) -> dict:
    return {
        "ok": _okx_item_ok(raw),
        "workflow": name,
        "simulated": SIMULATED,
        "sent_ai_builder_code": sent.get("tag", ""),
        "preflight": preflight,
        "sent_order": sent,
        "raw": raw,
    }


def _spot_open_workflow(creds: dict, data: dict) -> dict:
    _guard_live_workflow(data)
    ai_builder_code = _require_ai_builder_code()
    inst_id = _required_text(data, "instId")
    instrument, rules, last = _get_market_preflight(creds["base"], "SPOT", inst_id)
    base_ccy, quote_ccy = _spot_currencies(inst_id, instrument)
    config = okx.get_account_config(
        creds["base"], creds["api_key"], creds["secret_key"], creds["passphrase"],
        simulated=SIMULATED,
    )
    td_mode = _spot_td_mode(data.get("tdMode"), config)

    min_quote = rules["minSz"] * last * Decimal("1.05")
    requested = _decimal(_required_text(data, "quoteAmount"), "quoteAmount")
    quote_amount = _round_up(max(requested, min_quote), QUOTE_AMOUNT_STEP)

    balance = okx.get_account_balance(
        creds["base"], creds["api_key"], creds["secret_key"], creds["passphrase"],
        simulated=SIMULATED,
    )
    available_quote = _available_balance(balance, quote_ccy)
    if available_quote < quote_amount:
        raise ValueError(
            f"available {quote_ccy} {available_quote} is below required quote amount "
            f"{quote_amount}"
        )

    sent = {
        "instId": inst_id,
        "tdMode": td_mode,
        "side": "buy",
        "ordType": "market",
        "sz": _fmt_decimal(quote_amount),
        "tgtCcy": "quote_ccy",
        "tag": ai_builder_code,
    }
    raw = okx.place_order(
        creds["base"], creds["api_key"], creds["secret_key"], creds["passphrase"],
        inst_id, td_mode, "buy", "market", sent["sz"],
        tgt_ccy="quote_ccy", tag=ai_builder_code, simulated=SIMULATED,
    )
    return _workflow_result("spot-open", {
        "instType": "SPOT",
        "instId": inst_id,
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


def _spot_close_workflow(creds: dict, data: dict) -> dict:
    _guard_live_workflow(data)
    ai_builder_code = _require_ai_builder_code()
    inst_id = _required_text(data, "instId")
    instrument, rules, last = _get_market_preflight(creds["base"], "SPOT", inst_id)
    base_ccy, quote_ccy = _spot_currencies(inst_id, instrument)
    config = okx.get_account_config(
        creds["base"], creds["api_key"], creds["secret_key"], creds["passphrase"],
        simulated=SIMULATED,
    )
    td_mode = _spot_td_mode(data.get("tdMode"), config)

    balance = okx.get_account_balance(
        creds["base"], creds["api_key"], creds["secret_key"], creds["passphrase"],
        simulated=SIMULATED,
    )
    available_base = _round_down(_available_balance(balance, base_ccy), rules["lotSz"])
    requested_quote_amount = None
    requested_base_size = None
    if data.get("baseSize"):
        requested_base_size = _decimal(data["baseSize"], "baseSize")
        sell_size = _round_down(requested_base_size, rules["lotSz"])
        if sell_size > available_base:
            raise ValueError(
                f"requested baseSize {sell_size} exceeds available {base_ccy} {available_base}"
            )
    else:
        requested_quote_amount = _decimal(_required_text(data, "quoteAmount"), "quoteAmount")
        sell_size = _round_down(requested_quote_amount / last, rules["lotSz"])
        if sell_size < rules["minSz"]:
            sell_size = _round_up(rules["minSz"], rules["lotSz"])
        if sell_size > available_base:
            sell_size = available_base
    if sell_size < rules["minSz"]:
        raise ValueError(
            f"available {base_ccy} {available_base} is below minimum sell size {rules['minSz']}"
        )

    sent = {
        "instId": inst_id,
        "tdMode": td_mode,
        "side": "sell",
        "ordType": "market",
        "sz": _fmt_decimal(sell_size),
        "tag": ai_builder_code,
    }
    raw = okx.place_order(
        creds["base"], creds["api_key"], creds["secret_key"], creds["passphrase"],
        inst_id, td_mode, "sell", "market", sent["sz"],
        tag=ai_builder_code, simulated=SIMULATED,
    )
    return _workflow_result("spot-close", {
        "instType": "SPOT",
        "instId": inst_id,
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


def _swap_open_workflow(creds: dict, data: dict) -> dict:
    _guard_live_workflow(data)
    ai_builder_code = _require_ai_builder_code()
    inst_id = _required_text(data, "instId")
    instrument, rules, last = _get_market_preflight(creds["base"], "SWAP", inst_id)
    settle_ccy = _supported_linear_swap_settle_ccy(instrument)
    if rules["ctVal"] <= 0:
        raise ValueError(f"instrument {inst_id} did not include a valid ctVal")

    if data.get("contracts"):
        contracts = _round_up(_decimal(data["contracts"], "contracts"), rules["lotSz"])
        requested_quote_amount = None
    else:
        requested_quote_amount = _decimal(_required_text(data, "quoteAmount"), "quoteAmount")
        contracts = _round_up(requested_quote_amount / (rules["ctVal"] * last), rules["lotSz"])
    if contracts < rules["minSz"]:
        contracts = _round_up(rules["minSz"], rules["lotSz"])

    config = okx.get_account_config(
        creds["base"], creds["api_key"], creds["secret_key"], creds["passphrase"],
        simulated=SIMULATED,
    )
    td_mode = _swap_td_mode(data.get("tdMode"), config)
    pos_side = _workflow_pos_side(config, data.get("posSide"))
    balance = okx.get_account_balance(
        creds["base"], creds["api_key"], creds["secret_key"], creds["passphrase"],
        simulated=SIMULATED,
    )
    available_settle = _available_balance(balance, settle_ccy)
    estimated_notional = contracts * rules["ctVal"] * last
    if available_settle < estimated_notional:
        raise ValueError(
            f"available {settle_ccy} {available_settle} is below estimated notional "
            f"{estimated_notional}"
        )

    sent = {
        "instId": inst_id,
        "tdMode": td_mode,
        "side": "buy",
        "ordType": "market",
        "sz": _fmt_decimal(contracts),
        "tag": ai_builder_code,
    }
    if pos_side:
        sent["posSide"] = pos_side
    raw = okx.place_order(
        creds["base"], creds["api_key"], creds["secret_key"], creds["passphrase"],
        inst_id, td_mode, "buy", "market", sent["sz"],
        pos_side=pos_side, tag=ai_builder_code, simulated=SIMULATED,
    )
    return _workflow_result("swap-open", {
        "instType": "SWAP",
        "instId": inst_id,
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
        raise ValueError(
            f"positions failed: code={positions_resp.get('code')} msg={positions_resp.get('msg')}"
        )
    for position in positions_resp.get("data") or []:
        if position.get("instId") != inst_id:
            continue
        if Decimal(str(position.get("pos") or "0")) == 0:
            continue
        actual_side = position.get("posSide")
        if pos_side and actual_side not in (pos_side, "net", None, ""):
            continue
        actual_mgn_mode = position.get("mgnMode")
        if mgn_mode and actual_mgn_mode and actual_mgn_mode != mgn_mode:
            continue
        return position
    return {}


def _swap_close_workflow(creds: dict, data: dict) -> dict:
    _guard_live_workflow(data)
    ai_builder_code = _require_ai_builder_code()
    inst_id = _required_text(data, "instId")
    mgn_mode = _required_trade_mode(
        data.get("mgnMode"), "mgnMode", {"cross", "isolated"},
    )
    auto_cxl = _bool_arg(data.get("autoCxl"), True)
    instrument, _, _ = _get_market_preflight(creds["base"], "SWAP", inst_id)
    settle_ccy = _supported_linear_swap_settle_ccy(instrument)

    config = okx.get_account_config(
        creds["base"], creds["api_key"], creds["secret_key"], creds["passphrase"],
        simulated=SIMULATED,
    )
    _require_swap_account_mode(config)
    pos_side = _workflow_pos_side(config, data.get("posSide"))
    positions = okx.get_positions(
        creds["base"], creds["api_key"], creds["secret_key"], creds["passphrase"],
        inst_type="SWAP", inst_id=inst_id, simulated=SIMULATED,
    )
    position = _find_open_position(positions, inst_id, pos_side, mgn_mode)
    if not position:
        raise ValueError(f"no open {inst_id} position found to close")

    sent = {
        "instId": inst_id,
        "mgnMode": mgn_mode,
        "autoCxl": str(auto_cxl).lower(),
        "tag": ai_builder_code,
    }
    if pos_side:
        sent["posSide"] = pos_side
    raw = okx.close_position(
        creds["base"], creds["api_key"], creds["secret_key"], creds["passphrase"],
        inst_id, mgn_mode,
        pos_side=pos_side, auto_cxl=auto_cxl,
        tag=ai_builder_code, simulated=SIMULATED,
    )
    return _workflow_result("swap-close", {
        "instType": "SWAP",
        "instId": inst_id,
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


def _run_workflow(handler):
    creds = _session_creds()
    if not creds:
        return _json_error("not connected yet")
    data = request.get_json(silent=True) or {}
    try:
        _require_trade_permission(creds)
        return jsonify(handler(creds, data))
    except ValueError as exc:
        return _json_error(str(exc))


@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/config")
def config():
    """Return public frontend config. client_id is public; client_secret is never returned."""
    # OAuth CSRF `state`: minted server-side and bound to an httpOnly cookie, then
    # verified at /api/connect (the frontend echoes it back but cannot read/forge
    # the cookie). Reuse an existing cookie so the value survives the
    # authorize -> callback full-page reload; a fresh one is minted after it is
    # consumed at /api/connect.
    state = request.cookies.get("oauth_state") or secrets.token_urlsafe(24)
    resp = jsonify({
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "okx_base_url": OKX_BASE_URL,
        "simulated": SIMULATED,
        "mock": MOCK,
        "ai_builder_code": AI_BUILDER_CODE,   # Public attribution value, not a secret.
        "state": state,
    })
    # httpOnly: page JS never reads it; SameSite=Lax so it rides the top-level OAuth
    # callback redirect. Production on HTTPS should also set Secure.
    resp.set_cookie("oauth_state", state, httponly=True, samesite="Lax", max_age=1800)
    return resp


@app.post("/api/connect")
def connect():
    """
    Receive OAuth callback code, exchange token, delete old key, create key, and store it.
    secretKey/passphrase are never returned to the frontend.
    """
    data = request.get_json(force=True) or {}
    code = data.get("code")
    domain = data.get("domain")
    state = data.get("state")
    if not code:
        return jsonify({"ok": False, "error": "missing code"}), 400

    # Server-side OAuth CSRF check: the echoed `state` must equal the httpOnly
    # cookie minted by /config. This is the real defense — the frontend check is
    # advisory and bypassable by posting here directly. Rejecting BEFORE the token
    # exchange (and before touching the existing session) prevents
    # authorization-code injection binding a foreign account to this session.
    # Compare as bytes: secrets.compare_digest rejects non-ASCII str (would 500).
    cookie_state = request.cookies.get("oauth_state")
    if (not state or not cookie_state
            or not secrets.compare_digest(str(state).encode("utf-8"),
                                          str(cookie_state).encode("utf-8"))):
        return jsonify({"ok": False, "error": "state validation failed (CSRF check)",
                        "step": "validate_state"}), 400

    # CSRF passed: a new connect replaces the prior session connection. (Done
    # AFTER the state gate so a rejected/forged attempt cannot drop a working
    # session.) A later failure must not leave stale credentials behind.
    _clear_session_creds()

    try:
        key_config = _validated_apikey_config()
        _validate_oauth_config()
        base = _callback_base_url(domain)
    except ValueError as exc:
        return _json_error(str(exc), step="validate_config")

    # 1. Exchange authorization code for access_token.
    tok = okx.exchange_token(base, CLIENT_ID, CLIENT_SECRET, code)
    access_token = tok.get("access_token")
    if not access_token:
        return jsonify({"ok": False, "step": "exchange_token",
                        "code": tok.get("code"), "msg": tok.get("msg"),
                        "hint": tok.get("_hint"), "http": tok.get("_http_status")}), 400

    # 2. Delete old key. code=0 and 59506 are both safe to continue.
    deleted = okx.delete_oauth_apikey(base, access_token, simulated=SIMULATED)
    if deleted.get("code") not in ("0", "59506"):
        return jsonify({"ok": False, "step": "delete_apikey",
                        "code": deleted.get("code"), "msg": deleted.get("msg")}), 400

    # 3. Create Fast API Key.
    created = okx.create_oauth_apikey(
        base, access_token, key_config["passphrase"], key_config["label"],
        perm=key_config["perm"], bind_app=True, simulated=SIMULATED,
    )
    if created.get("code") != "0" or not created.get("data"):
        return jsonify({"ok": False, "step": "create_apikey",
                        "code": created.get("code"), "msg": created.get("msg")}), 400

    k = created["data"][0]
    # 4. Store per-session credentials in memory for demo purposes only.
    sid = _get_or_create_sid()
    _CREDS[sid] = {
        "api_key":    k["apiKey"],
        "secret_key": k["secretKey"],
        "passphrase": k.get("passphrase") or key_config["passphrase"],
        "base":       base,
        "perm":       k.get("perm") or key_config["perm"],
    }

    masked = k["apiKey"][:4] + "****" + k["apiKey"][-4:]
    resp = jsonify({"ok": True, "api_key_masked": masked,
                    "perm": k.get("perm"), "simulated": SIMULATED})
    # Local demo cookie only. Production should add Secure on HTTPS.
    resp.set_cookie("demo_sid", sid, httponly=True, samesite="Lax")
    # Consume the CSRF state so it cannot be replayed; /config mints a fresh one.
    resp.delete_cookie("oauth_state")
    return resp


@app.get("/api/balance")
def balance():
    """Sign and call the account balance example with the current session API Key."""
    creds = _CREDS.get(request.cookies.get("demo_sid", ""))
    if not creds:
        return jsonify({"ok": False, "error": "not connected yet"}), 400
    ccy = request.args.get("ccy")
    try:
        res = okx.get_account_balance(
            creds["base"], creds["api_key"], creds["secret_key"],
            creds["passphrase"], ccy=ccy, simulated=SIMULATED,
        )
    except ValueError as exc:
        return _json_error(str(exc))
    # Demo returns the full balance payload. Production should whitelist fields as needed.
    return jsonify({"ok": res.get("code") == "0", "raw": res})


@app.get("/api/demo-workflow-fields")
def demo_workflow_fields():
    """
    Return recommended manual-test fields based on the current account config.
    This is read-only and mirrors the `openapi-user` OpenAPI workflow defaults.
    """
    creds = _session_creds()
    if not creds:
        return _json_error("not connected yet")
    try:
        config_resp = okx.get_account_config(
            creds["base"], creds["api_key"], creds["secret_key"],
            creds["passphrase"], simulated=SIMULATED,
        )
        result = _demo_workflow_fields(config_resp)
    except ValueError as exc:
        return _json_error(str(exc), step="demo_workflow_fields")
    return jsonify({"ok": True, "simulated": SIMULATED, **result})


@app.post("/api/order")
def order():
    """
    Sign and place an example order with the current session API Key.
    Requires a key with trade permission. Live trading uses real funds.
    """
    creds = _session_creds()
    if not creds:
        return jsonify({"ok": False, "error": "not connected yet"}), 400
    data = request.get_json(force=True) or {}
    try:
        _require_trade_permission(creds)
        _guard_live_workflow(data)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    try:
        inst_id = _required_order_text(data, "instId")
        td_mode = _required_trade_mode(data.get("tdMode"), "tdMode",
                                       {"cash", "cross", "isolated"}, default="cash")
        side = _required_order_enum(data, "side", {"buy", "sell"})
        ord_type = _required_order_enum(data, "ordType", {"limit", "market"}, default="limit")
        sz = _fmt_decimal(_decimal(_required_order_text(data, "sz"), "sz"))
        px = None
        if ord_type == "limit":
            px = _fmt_decimal(_decimal(_required_order_text(data, "px"), "px"))
        else:
            px = _optional_order_text(data.get("px"), "px")
            if px:
                px = _fmt_decimal(_decimal(px, "px"))
        tgt_ccy = _optional_order_text(data.get("tgtCcy"), "tgtCcy")
        pos_side = _optional_order_text(data.get("posSide"), "posSide")
        if pos_side and pos_side not in {"long", "short", "net"}:
            raise ValueError("posSide must be one of: long, net, short")
        reduce_only = _bool_arg(data.get("reduceOnly"), False)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    if not AI_BUILDER_CODE or AI_BUILDER_CODE.startswith("<"):
        return jsonify({"ok": False, "error": "missing AI_BUILDER_CODE"}), 400
    if not AI_BUILDER_CODE_PATTERN.match(AI_BUILDER_CODE):
        return jsonify({"ok": False, "error": "AI_BUILDER_CODE must be 1-16 alphanumeric characters"}), 400
    # Inject AI Builder Code into OKX tag on the server side.
    res = okx.place_order(
        creds["base"], creds["api_key"], creds["secret_key"], creds["passphrase"],
        inst_id, td_mode, side, ord_type, sz,
        px=px, tgt_ccy=tgt_ccy, pos_side=pos_side, reduce_only=reduce_only,
        tag=AI_BUILDER_CODE, simulated=SIMULATED,
    )
    return jsonify({"ok": res.get("code") == "0", "sent_ai_builder_code": AI_BUILDER_CODE, "raw": res})


@app.post("/api/spot/open")
def spot_open():
    """Run the demo workflow: buy BTC-USDT spot with USDT."""
    return _run_workflow(_spot_open_workflow)


@app.post("/api/spot/close")
def spot_close():
    """Run the demo workflow: sell BTC-USDT spot."""
    return _run_workflow(_spot_close_workflow)


@app.post("/api/swap/open")
def swap_open():
    """Run the demo workflow: open a BTC-USDT-SWAP long."""
    return _run_workflow(_swap_open_workflow)


@app.post("/api/swap/close")
def swap_close():
    """Run the demo workflow: close a BTC-USDT-SWAP long."""
    return _run_workflow(_swap_close_workflow)


if __name__ == "__main__":
    # Debug is off by default. Enable only for local debugging with FLASK_DEBUG=1;
    # never enable it in production (the Werkzeug debugger allows code execution).
    # For production, serve with a WSGI server such as gunicorn instead of app.run().
    debug = os.environ.get("FLASK_DEBUG", "") == "1"
    app.run(host="127.0.0.1", port=8000, debug=debug)
