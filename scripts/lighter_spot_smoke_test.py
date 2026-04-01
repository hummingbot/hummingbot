"""
Lighter Spot Connector — Live Smoke Test
=========================================
Runs a real spot place/cancel on a funded market and verifies the lifecycle
through account state changes.

Verification criteria:
1. `check_client()` succeeds
2. `create_order()` returns code 200
3. quote-asset `locked_balance` increases after create
4. `cancel_order()` returns code 200
5. quote-asset `locked_balance` returns to baseline after cancel
6. `total_order_count` returns to baseline after cancel
"""
import asyncio
import hashlib
import os
import sys
import time
from decimal import ROUND_UP, Decimal
from pathlib import Path
from typing import Dict, List, Tuple

LIGHTER_PY_ROOT = Path(__file__).parents[3] / "lighter-ts" / "lighter-python"
if LIGHTER_PY_ROOT.exists() and str(LIGHTER_PY_ROOT) not in sys.path:
    sys.path.insert(0, str(LIGHTER_PY_ROOT))

import aiohttp
import lighter

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

for env_path in [
    Path(__file__).parents[1] / ".env",
    Path(__file__).parents[2] / "hummingbot" / ".env",
    Path(__file__).parents[2] / ".env",
    Path(__file__).parent / ".env",
]:
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                k, v = s.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
        break

BASE_URL = "https://mainnet.zklighter.elliot.ai"
REST_BASE = f"{BASE_URL}/api/v1"
API_KEY_IDX = int(os.environ["lighter_perpetual_api_key_index"])
PRIVATE_KEY = os.environ.get("lighter_perpetual_private_key", "").strip() or os.environ["lighter_perpetual_api_key"].strip()
ACCT_INDEX = int(os.environ["lighter_perpetual_account_index"])

# Safe low bids far below market to avoid fills while still satisfying min_quote.
SAFE_BID_PRICE_BY_SYMBOL: Dict[str, Decimal] = {
    "LIT/USDC": Decimal("0.0010"),
}


def client_order_index_from_order_id(tag: str) -> int:
    digest = hashlib.sha256(tag.encode()).digest()
    return int.from_bytes(digest[:6], byteorder="big", signed=False) & 0xFFFFFFFFFFFF


async def get_account(session: aiohttp.ClientSession) -> Dict:
    async with session.get(
        f"{REST_BASE}/account",
        params={"by": "index", "value": str(ACCT_INDEX)},
        headers={"X-Api-Key": str(API_KEY_IDX)},
    ) as resp:
        payload = await resp.json()
    accounts = payload.get("accounts") or []
    if not accounts:
        raise RuntimeError(f"No account data returned: {payload}")
    return accounts[0]


async def get_spot_books(session: aiohttp.ClientSession) -> List[Dict]:
    async with session.get(f"{REST_BASE}/orderBooks") as resp:
        payload = await resp.json()
    return [
        book
        for book in (payload.get("order_books") or payload.get("data") or [])
        if str(book.get("market_type") or "").lower() == "spot"
    ]


def asset_balances(account: Dict) -> Dict[str, Tuple[Decimal, Decimal]]:
    balances: Dict[str, Tuple[Decimal, Decimal]] = {}
    for asset in account.get("assets", []):
        symbol = str(asset.get("symbol") or "")
        balances[symbol] = (
            Decimal(str(asset.get("balance") or "0")),
            Decimal(str(asset.get("locked_balance") or "0")),
        )
    return balances


def select_market(account: Dict, books: List[Dict]) -> Tuple[Dict, Decimal]:
    balances = asset_balances(account)
    candidates = []
    for book in books:
        symbol = str(book.get("symbol") or "")
        if symbol not in SAFE_BID_PRICE_BY_SYMBOL:
            continue
        quote = symbol.split("/")[-1]
        quote_balance = balances.get(quote, (Decimal("0"), Decimal("0")))[0]
        min_quote = Decimal(str(book.get("min_quote_amount") or "0"))
        if quote_balance >= min_quote:
            candidates.append((min_quote, symbol, book, SAFE_BID_PRICE_BY_SYMBOL[symbol]))

    if not candidates:
        balances_text = ", ".join(f"{k}={v[0]}" for k, v in balances.items()) or "none"
        raise RuntimeError(f"No viable funded spot market found. Balances: {balances_text}")

    _, symbol, book, price = min(candidates, key=lambda row: row[0])
    return book, price


def compute_order_amounts(book: Dict, bid_price: Decimal) -> Tuple[int, int]:
    size_dec = int(book.get("supported_size_decimals") or 0)
    price_dec = int(book.get("supported_price_decimals") or 0)
    min_base = Decimal(str(book.get("min_base_amount") or "0"))
    min_quote = Decimal(str(book.get("min_quote_amount") or "0"))

    size_scale = Decimal(f"1e{size_dec}")
    price_scale = Decimal(f"1e{price_dec}")

    min_base_units = (min_base * size_scale).to_integral_value(rounding=ROUND_UP)
    base_from_quote_units = ((min_quote / bid_price) * size_scale).to_integral_value(rounding=ROUND_UP)
    base_amount = int(max(min_base_units, base_from_quote_units))
    price_scaled = int((bid_price * price_scale).to_integral_value(rounding=ROUND_UP))
    return base_amount, price_scaled


async def main():
    timeout = aiohttp.ClientTimeout(total=30)
    connector = aiohttp.TCPConnector(family=2)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        before = await get_account(session)
        books = await get_spot_books(session)
        book, bid_price = select_market(before, books)

        market_id = int(book["market_id"])
        symbol = str(book["symbol"])
        quote_asset = symbol.split("/")[-1]
        size_dec = int(book.get("supported_size_decimals") or 0)
        base_amount, price_scaled = compute_order_amounts(book=book, bid_price=bid_price)
        client_order_index = client_order_index_from_order_id(f"live-smoke-{symbol}-{int(time.time())}")

        before_balances = asset_balances(before)
        before_locked = before_balances.get(quote_asset, (Decimal("0"), Decimal("0")))[1]
        before_orders = int(before.get("total_order_count") or 0)

        print(f"[1] selected market={symbol} market_id={market_id} bid_price={bid_price}")
        print(f"[2] before: total_order_count={before_orders} {quote_asset}.locked={before_locked}")

        signer = lighter.SignerClient(
            url=BASE_URL,
            account_index=ACCT_INDEX,
            api_private_keys={API_KEY_IDX: PRIVATE_KEY},
        )
        err = signer.check_client()
        if err is not None:
            raise RuntimeError(f"check_client failed: {err}")
        print(f"[3] signer check OK account_index={ACCT_INDEX}")

        api_key_index, nonce = signer.nonce_manager.next_nonce()
        _, create_resp, create_err = await signer.create_order(
            market_index=market_id,
            client_order_index=client_order_index,
            base_amount=base_amount,
            price=price_scaled,
            is_ask=False,
            order_type=signer.ORDER_TYPE_LIMIT,
            time_in_force=signer.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
            reduce_only=False,
            trigger_price=0,
            nonce=nonce,
            api_key_index=api_key_index,
        )
        if create_err is not None:
            raise RuntimeError(f"create_order failed: {create_err}")
        if getattr(create_resp, "code", None) != 200:
            raise RuntimeError(f"create_order returned non-200: {create_resp}")
        print(f"[4] create OK client_order_index={client_order_index} code={create_resp.code}")

        await asyncio.sleep(3)
        during = await get_account(session)
        during_balances = asset_balances(during)
        during_locked = during_balances.get(quote_asset, (Decimal("0"), Decimal("0")))[1]
        during_orders = int(during.get("total_order_count") or 0)
        print(f"[5] after create: total_order_count={during_orders} {quote_asset}.locked={during_locked}")

        if during_locked <= before_locked:
            raise RuntimeError(
                f"Locked {quote_asset} did not increase after create: before={before_locked} after={during_locked}"
            )

        api_key_index, nonce = signer.nonce_manager.next_nonce(api_key_index)
        _, cancel_resp, cancel_err = await signer.cancel_order(
            market_index=market_id,
            order_index=client_order_index,
            nonce=nonce,
            api_key_index=api_key_index,
        )
        if cancel_err is not None:
            raise RuntimeError(f"cancel_order failed: {cancel_err}")
        if getattr(cancel_resp, "code", None) != 200:
            raise RuntimeError(f"cancel_order returned non-200: {cancel_resp}")
        print(f"[6] cancel OK order_index={client_order_index} code={cancel_resp.code}")

        await asyncio.sleep(3)
        after = await get_account(session)
        after_balances = asset_balances(after)
        after_locked = after_balances.get(quote_asset, (Decimal("0"), Decimal("0")))[1]
        after_orders = int(after.get("total_order_count") or 0)
        print(f"[7] after cancel: total_order_count={after_orders} {quote_asset}.locked={after_locked}")

        await signer.close()

    if after_locked != before_locked:
        raise RuntimeError(f"Locked {quote_asset} did not return to baseline: before={before_locked} after={after_locked}")
    if after_orders != before_orders:
        raise RuntimeError(f"total_order_count did not return to baseline: before={before_orders} after={after_orders}")

    print("\n✓ LIVE SPOT PLACE/CANCEL PASSED")


if __name__ == "__main__":
    asyncio.run(main())
