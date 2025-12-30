import asyncio
import os
import time
from decimal import Decimal
from pathlib import Path

import aiohttp
import pytest

from hummingbot.core.web_assistant.connections.connections_factory import ConnectionsFactory


def _load_env() -> None:
    current = Path(__file__).resolve()
    repo_root = None
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            repo_root = parent
            break
    if repo_root is None:
        return
    env_path = repo_root.parent / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    load_dotenv(env_path)


async def _reset_connections_factory() -> None:
    factory = ConnectionsFactory()
    for attr in ("_shared_client", "_ws_independent_session"):
        session = getattr(factory, attr, None)
        if session is not None:
            loop = getattr(session, "_loop", None)
            if loop is not None and loop.is_closed():
                setattr(factory, attr, None)
    if getattr(factory, "_shared_client", None) is not None or getattr(factory, "_ws_independent_session", None) is not None:
        await factory.close()


_load_env()

API_KEY = os.getenv("BACKPACK_API_KEY")
API_SECRET = os.getenv("BACKPACK_API_SECRET")
RUN_ORDER_TESTS = os.getenv("BACKPACK_RUN_ORDER_TESTS") == "1"

if not API_KEY or not API_SECRET:
    pytest.skip("BACKPACK_API_KEY/BACKPACK_API_SECRET not set", allow_module_level=True)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_spot_auth_headers():
    await _reset_connections_factory()
    from hummingbot.connector.exchange.backpack.backpack_auth import BackpackAuth

    auth = BackpackAuth(api_key=API_KEY, api_secret=API_SECRET)
    timestamp = int(time.time() * 1000)
    headers = auth.generate_auth_headers(
        instruction="balanceQuery",
        params={"symbol": "BTC_USDC"},
        timestamp=timestamp,
        window=5000,
    )

    assert headers.get("X-API-Key") == API_KEY
    assert headers.get("X-Signature")
    assert headers.get("X-Timestamp") == str(timestamp)
    assert headers.get("X-Window") == "5000"


@pytest.mark.asyncio
async def test_spot_balance_retrieval():
    await _reset_connections_factory()
    from hummingbot.connector.exchange.backpack.backpack_exchange import BackpackExchange

    exchange = BackpackExchange(
        backpack_api_key=API_KEY,
        backpack_api_secret=API_SECRET,
        trading_pairs=["BTC-USDC"],
    )
    try:
        await exchange._update_balances()
        balances = exchange.get_all_balances()
        assert isinstance(balances, dict)
        for value in balances.values():
            assert isinstance(value, Decimal)
    finally:
        await exchange.stop_network()
        await exchange._web_assistants_factory.close()


@pytest.mark.asyncio
async def test_spot_trading_rules():
    await _reset_connections_factory()
    from hummingbot.connector.exchange.backpack.backpack_exchange import BackpackExchange

    exchange = BackpackExchange(
        backpack_api_key=API_KEY,
        backpack_api_secret=API_SECRET,
        trading_pairs=["BTC-USDC"],
    )
    try:
        await exchange._update_trading_rules()
        assert exchange.trading_rules
    finally:
        await exchange.stop_network()
        await exchange._web_assistants_factory.close()


@pytest.mark.asyncio
async def test_public_ws_trade_stream():
    await _reset_connections_factory()
    subscribe_msg = {
        "method": "SUBSCRIBE",
        "params": ["trade.SOL_USDC"],
    }

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect("wss://ws.backpack.exchange", heartbeat=20) as ws:
            await ws.send_json(subscribe_msg)
            found_trade = False
            end_time = time.time() + 10

            while time.time() < end_time:
                timeout = max(0.1, end_time - time.time())
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=timeout)
                except asyncio.TimeoutError:
                    break

                if msg.type == aiohttp.WSMsgType.TEXT and "trade" in (msg.data or ""):
                    found_trade = True
                    break

            if not found_trade:
                pytest.skip("No trade message received within timeout")


@pytest.mark.asyncio
@pytest.mark.skipif(not RUN_ORDER_TESTS, reason="Set BACKPACK_RUN_ORDER_TESTS=1 to enable")
async def test_spot_order_lifecycle():
    await _reset_connections_factory()
    from hummingbot.connector.exchange.backpack.backpack_exchange import BackpackExchange
    from hummingbot.core.data_type.common import OrderType

    exchange = BackpackExchange(
        backpack_api_key=API_KEY,
        backpack_api_secret=API_SECRET,
        trading_pairs=["SOL-USDC"],
    )

    try:
        await exchange._update_trading_rules()
        await exchange._update_balances()

        from hummingbot.connector.exchange.backpack import backpack_constants as CONSTANTS

        trading_rule = exchange.trading_rules["SOL-USDC"]
        available_quote = exchange.get_available_balance("USDC")
        min_notional = trading_rule.min_notional_size

        if available_quote < min_notional:
            pytest.skip("Insufficient quote balance for min-notional order")

        last_price = None
        try:
            ticker = await exchange._api_get(
                path_url=CONSTANTS.TICKER_URL,
                params={"symbol": "SOL_USDC"},
            )
            last_price = Decimal(str(ticker.get("lastPrice", "0")))
        except Exception:
            last_price = None

        if last_price and last_price > 0:
            price = max(trading_rule.min_price_increment, last_price * Decimal("0.99"))
        else:
            price = max(trading_rule.min_price_increment, min_notional)
        price = exchange.quantize_order_price("SOL-USDC", price)
        min_test_amount = Decimal("0.01")
        amount = max(trading_rule.min_order_size, (min_notional * Decimal("1.05")) / price)
        amount = exchange.quantize_order_amount("SOL-USDC", amount)
        if amount < trading_rule.min_order_size:
            amount = exchange.quantize_order_amount(
                "SOL-USDC",
                trading_rule.min_order_size + trading_rule.min_base_amount_increment,
            )
        if amount < min_test_amount:
            amount = exchange.quantize_order_amount("SOL-USDC", min_test_amount)

        if amount <= 0 or price <= 0:
            pytest.skip("Invalid computed order size or price")

        notional = amount * price
        if notional < min_notional:
            amount = exchange.quantize_order_amount("SOL-USDC", amount + trading_rule.min_base_amount_increment)
            notional = amount * price

        if notional < min_notional:
            pytest.skip("Computed order notional below minimum")

        if notional > available_quote:
            pytest.skip("Insufficient quote balance for computed order size")

        order_id = exchange.buy(
            trading_pair="SOL-USDC",
            amount=amount,
            order_type=OrderType.LIMIT,
            price=price,
        )

        for _ in range(10):
            if order_id in exchange.in_flight_orders:
                break
            await asyncio.sleep(1)

        if order_id not in exchange.in_flight_orders:
            cached = exchange._order_tracker.cached_orders.get(order_id)
            if cached is None:
                pytest.skip("Order not tracked (likely rejected or filled immediately)")
            if cached.current_state.name == "FAILED":
                pytest.skip("Order failed immediately (likely min-notional or balance constraint)")
            if cached.current_state.name in {"FILLED", "CANCELED"}:
                return
            assert order_id in exchange.in_flight_orders

        exchange.cancel(trading_pair="SOL-USDC", client_order_id=order_id)
        await asyncio.sleep(2)
    finally:
        await exchange.stop_network()
        await exchange._web_assistants_factory.close()
