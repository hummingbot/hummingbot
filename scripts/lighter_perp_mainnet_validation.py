import asyncio
import hashlib
import json
import os
import sys
import time
from decimal import ROUND_DOWN, Decimal
from pathlib import Path
from typing import Any, Dict, Optional

import lighter
import requests

ROOT = Path(__file__).resolve().parents[1]

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def parse_env_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def first_non_empty(env: Dict[str, str], *keys: str) -> Optional[str]:
    for key in keys:
        value = os.environ.get(key) or env.get(key)
        if value:
            return value
    return None


def quantize_down(value: Decimal, decimals: int) -> Decimal:
    quantum = Decimal(f"1e-{decimals}")
    return value.quantize(quantum, rounding=ROUND_DOWN)


def extract_tx_hash(tx_response: Any) -> Optional[str]:
    if tx_response is None:
        return None

    for attr in ("tx_hash", "transaction_hash", "hash"):
        if hasattr(tx_response, attr):
            value = getattr(tx_response, attr)
            if value:
                return str(value)

    response_obj = getattr(tx_response, "response", None)
    if isinstance(response_obj, dict):
        for key in ("tx_hash", "transaction_hash", "hash"):
            value = response_obj.get(key)
            if value:
                return str(value)

    return None


def is_int_string(value: Optional[str]) -> bool:
    if value is None:
        return False
    try:
        int(str(value))
        return True
    except Exception:
        return False


def get_rest_api_key(api_key: str, api_secret: str) -> str:
    if is_int_string(api_key):
        return api_key
    if api_secret:
        return api_secret
    return api_key


def get_api_key_index(api_key_index: Optional[str], api_key: str, api_secret: str) -> int:
    if is_int_string(api_key_index):
        return int(api_key_index)
    if is_int_string(api_key):
        return int(api_key)
    if is_int_string(api_secret):
        return int(api_secret)
    raise ValueError("Unable to resolve numeric Lighter API key index")


def get_signer_private_key(private_key: Optional[str], api_key: str, api_secret: str) -> str:
    if private_key:
        return private_key
    if api_key and not is_int_string(api_key):
        return api_key
    if api_secret and not is_int_string(api_secret):
        return api_secret
    raise ValueError("Unable to resolve signer private key")


def client_order_index_from_id(order_id: str) -> int:
    digest = hashlib.sha256(order_id.encode()).digest()
    # Lighter expects client_order_index <= 2^48-1.
    return int.from_bytes(digest[:8], byteorder="big", signed=False) & ((1 << 48) - 1)


def run() -> int:
    env_path = ROOT.parent / "hummingbot" / ".env"
    env = parse_env_file(env_path)

    api_key = first_non_empty(
        env,
        "LIGHTER_PERPETUAL_API_KEY",
        "LIGHTER_API_KEY",
        "lighter_perpetual_api_key",
        "lighter_api_key",
    )
    api_secret = first_non_empty(
        env,
        "LIGHTER_PERPETUAL_API_SECRET",
        "LIGHTER_API_SECRET",
        "lighter_perpetual_api_secret",
        "lighter_api_secret",
    )
    api_key_index_raw = first_non_empty(
        env,
        "LIGHTER_PERPETUAL_API_KEY_INDEX",
        "LIGHTER_API_KEY_INDEX",
        "lighter_perpetual_api_key_index",
        "lighter_api_key_index",
    )
    account_index = first_non_empty(
        env,
        "LIGHTER_PERPETUAL_ACCOUNT_INDEX",
        "LIGHTER_ACCOUNT_INDEX",
        "lighter_perpetual_account_index",
        "lighter_account_index",
    )
    private_key = first_non_empty(
        env,
        "LIGHTER_PERPETUAL_PRIVATE_KEY",
        "LIGHTER_PRIVATE_KEY",
        "LIGHTER_SIGNER_PRIVATE_KEY",
        "lighter_perpetual_private_key",
        "lighter_private_key",
        "lighter_signer_private_key",
    ) or ""

    steps = []

    def record(step: str, passed: bool, details: str = "", tx_hash: str = ""):
        steps.append({
            "step": step,
            "status": "PASS" if passed else "FAIL",
            "details": details,
            "tx_hash": tx_hash,
        })

    if not api_key or not account_index:
        record("config", False, "Missing lighter perp credentials in .env")
        print_table(steps)
        return 1

    if not api_secret and api_key_index_raw:
        api_secret = api_key_index_raw

    base_url = "https://mainnet.zklighter.elliot.ai/api/v1"

    # REST health checks
    try:
        order_books = requests.get(f"{base_url}/orderBooks", timeout=20)
        record("REST /orderBooks", order_books.status_code == 200, f"status={order_books.status_code}")
    except Exception as e:
        order_books = None
        record("REST /orderBooks", False, str(e))

    try:
        rest_api_key = get_rest_api_key(api_key, api_secret)
        signer_private_key = get_signer_private_key(private_key, api_key, api_secret)
        api_key_index = get_api_key_index(api_key_index_raw, api_key, api_secret)
    except Exception as e:
        record("config", False, f"Credential resolution failed: {e}")
        print_table(steps)
        return 1

    headers = {"X-Api-Key": rest_api_key}
    try:
        account_res = requests.get(
            f"{base_url}/account",
            params={"by": "index", "value": account_index},
            headers=headers,
            timeout=20,
        )
        account_json = account_res.json() if account_res.ok else {}
        ok = account_res.status_code == 200 and bool(account_json.get("data") or account_json.get("accounts"))
        record("REST /account", ok, f"status={account_res.status_code}")
    except Exception as e:
        account_json = {}
        record("REST /account", False, str(e))

    try:
        stats_res = requests.get(f"{base_url}/exchangeStats", timeout=20)
        stats_json = stats_res.json() if stats_res.ok else {}
        record("REST /exchangeStats", stats_res.status_code == 200, f"status={stats_res.status_code}")
    except Exception as e:
        stats_json = {}
        record("REST /exchangeStats", False, str(e))

    signer = None

    async def close_signer_sessions() -> None:
        if signer is None:
            return

        close_calls = []
        if hasattr(signer, "close"):
            close_calls.append(getattr(signer, "close"))

        for attr_name in ("api_client", "_api_client", "session", "client_session"):
            holder = getattr(signer, attr_name, None)
            if holder is not None and hasattr(holder, "close"):
                close_calls.append(getattr(holder, "close"))

        for close_fn in close_calls:
            try:
                result = close_fn()
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass

    # Select a perp market with available pricing.
    selected = None
    try:
        ob_data = order_books.json() if order_books is not None and order_books.ok else {}
        perp_books = [b for b in (ob_data.get("order_books") or []) if b.get("market_type") == "perp"]
        prices_map = {entry.get("symbol"): entry for entry in (stats_json.get("order_book_stats") or []) if entry.get("symbol")}

        for book in perp_books:
            symbol = book.get("symbol")
            price_entry = prices_map.get(symbol)
            if not price_entry:
                continue

            mark = Decimal(str(price_entry.get("mark") or price_entry.get("mid") or price_entry.get("last_trade_price") or "0"))
            if mark <= 0:
                continue

            selected = {
                "symbol": symbol,
                "market_id": int(book.get("market_id")),
                "size_decimals": int(book.get("supported_size_decimals", 0)),
                "price_decimals": int(book.get("supported_price_decimals", 0)),
                "min_quote": Decimal(str(book.get("min_quote_amount") or "10")),
                "min_base": Decimal(str(book.get("min_base_amount") or "0")),
                "mark": mark,
            }
            break

        if selected is None:
            record("Market selection", False, "No perp market with valid mark price found")
            print_table(steps)
            write_report(steps)
            return 1

        record("Market selection", True, f"{selected['symbol']} mark={selected['mark']}")
    except Exception as e:
        record("Market selection", False, str(e))
        print_table(steps)
        write_report(steps)
        return 1

    # Prepare and execute a post-only sell order above mark to avoid immediate fills.
    async def execute_mainnet_trade_flow() -> None:
        nonlocal signer

        limit_price = quantize_down(selected["mark"] * Decimal("1.10"), selected["price_decimals"])
        if limit_price <= 0:
            raise ValueError("Rounded limit price is zero")

        notional = max(Decimal("12"), selected["min_quote"])
        raw_amount = notional / limit_price
        amount = quantize_down(raw_amount, selected["size_decimals"])

        if amount < selected["min_base"]:
            amount = quantize_down(selected["min_base"], selected["size_decimals"])

        if amount * limit_price < selected["min_quote"]:
            required = selected["min_quote"] / limit_price
            amount = quantize_down(required, selected["size_decimals"])

        if amount < selected["min_base"]:
            amount = quantize_down(selected["min_base"], selected["size_decimals"])

        if amount <= 0:
            raise ValueError("Rounded amount is zero")

        base_amount_scaled = int((amount * Decimal(f"1e{selected['size_decimals']}")))
        price_scaled = int((limit_price * Decimal(f"1e{selected['price_decimals']}")))

        if base_amount_scaled <= 0 or price_scaled <= 0:
            raise ValueError("Scaled amount/price are non-positive")
        signer = lighter.signer_client.SignerClient(
            url="https://mainnet.zklighter.elliot.ai",
            account_index=int(account_index),
            api_private_keys={api_key_index: signer_private_key},
        )
        record("Signer init", True, "SignerClient initialized")

        client_order_id = f"HBOT-LP-{int(time.time())}"
        client_order_index = client_order_index_from_id(client_order_id)

        _, create_resp, create_err = await signer.create_order(
            market_index=selected["market_id"],
            client_order_index=client_order_index,
            base_amount=base_amount_scaled,
            price=price_scaled,
            is_ask=True,
            order_type=signer.ORDER_TYPE_LIMIT,
            time_in_force=signer.ORDER_TIME_IN_FORCE_POST_ONLY,
            reduce_only=False,
            order_expiry=signer.DEFAULT_28_DAY_ORDER_EXPIRY,
            api_key_index=api_key_index,
        )

        create_code = getattr(create_resp, "code", None)
        create_hash = extract_tx_hash(create_resp) or ""
        create_ok = create_err is None and create_code == 200
        record(
            "Perp place limit order",
            create_ok,
            f"symbol={selected['symbol']} code={create_code} error={create_err}",
            create_hash,
        )

        if create_ok:
            _, cancel_resp, cancel_err = await signer.cancel_order(
                market_index=selected["market_id"],
                order_index=client_order_index,
                api_key_index=api_key_index,
            )
            cancel_code = getattr(cancel_resp, "code", None)
            cancel_hash = extract_tx_hash(cancel_resp) or ""
            cancel_ok = cancel_err is None and cancel_code == 200
            record(
                "Perp cancel order",
                cancel_ok,
                f"order_index={client_order_index} code={cancel_code} error={cancel_err}",
                cancel_hash,
            )

    try:
        asyncio.run(execute_mainnet_trade_flow())
    except Exception as e:
        if "SignerClient initialized" not in [s["details"] for s in steps if s["step"] == "Signer init"]:
            record("Signer init", False, str(e))
        else:
            record("Perp trading flow", False, str(e))
    finally:
        try:
            asyncio.run(close_signer_sessions())
        except Exception:
            pass

    print_table(steps)
    write_report(steps)

    return 0 if all(step["status"] == "PASS" for step in steps) else 1


def print_table(steps: list[Dict[str, str]]):
    print("\n| Step | Status | Details | Tx Hash |")
    print("|---|---|---|---|")
    for step in steps:
        details = step["details"].replace("|", "/")
        tx = step["tx_hash"] or "-"
        print(f"| {step['step']} | {step['status']} | {details} | {tx} |")


def write_report(steps: list[Dict[str, str]]):
    out_path = ROOT / "scripts" / "lighter_perp_integration_report.json"
    payload = {
        "timestamp": int(time.time()),
        "results": steps,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(run())
