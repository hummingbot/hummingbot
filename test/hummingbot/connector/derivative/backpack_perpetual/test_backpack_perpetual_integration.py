import os
import time
from decimal import Decimal
from pathlib import Path

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

if not API_KEY or not API_SECRET:
    pytest.skip("BACKPACK_API_KEY/BACKPACK_API_SECRET not set", allow_module_level=True)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_perpetual_auth_headers():
    await _reset_connections_factory()
    from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_auth import BackpackPerpetualAuth

    auth = BackpackPerpetualAuth(api_key=API_KEY, api_secret=API_SECRET)
    timestamp = int(time.time() * 1000)
    headers = auth.generate_auth_headers(
        instruction="balanceQuery",
        params={"symbol": "BTC_USDC_PERP"},
        timestamp=timestamp,
        window=5000,
    )

    assert headers.get("X-API-Key") == API_KEY
    assert headers.get("X-Signature")
    assert headers.get("X-Timestamp") == str(timestamp)
    assert headers.get("X-Window") == "5000"


@pytest.mark.asyncio
async def test_perpetual_balance_retrieval():
    await _reset_connections_factory()
    from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_derivative import (
        BackpackPerpetualDerivative,
    )

    exchange = BackpackPerpetualDerivative(
        backpack_perpetual_api_key=API_KEY,
        backpack_perpetual_api_secret=API_SECRET,
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
async def test_perpetual_positions_retrieval():
    await _reset_connections_factory()
    from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_derivative import (
        BackpackPerpetualDerivative,
    )

    exchange = BackpackPerpetualDerivative(
        backpack_perpetual_api_key=API_KEY,
        backpack_perpetual_api_secret=API_SECRET,
        trading_pairs=["BTC-USDC"],
    )
    try:
        await exchange._update_positions()
        assert isinstance(exchange.account_positions, dict)
    finally:
        await exchange.stop_network()
        await exchange._web_assistants_factory.close()
