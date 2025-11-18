from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.models import ConnectorConfig, StrategyConfig
from services.user_engine import UserEngine


class FakeTradingCore:
    def __init__(self, *_):
        self._connectors = {}
        self.connector_manager = SimpleNamespace(connectors=self._connectors)
        self.clock = None

    @property
    def connectors(self):
        return self._connectors

    async def create_connector(self, connector_name, trading_pairs, trading_required=True, api_keys=None):
        connector = MagicMock()
        connector.name = connector_name
        connector.trading_pairs = trading_pairs
        self._connectors[connector_name] = connector
        return connector

    async def start_clock(self):
        self.clock = MagicMock()

    async def stop_clock(self):
        self.clock = None


@pytest.mark.asyncio
@patch("services.user_engine.EmaAtrStrategy")
async def test_user_engine_starts_strategy(mock_strategy_cls):
    strategy_instance = MagicMock()
    strategy_instance.start_event_driven = AsyncMock()
    strategy_instance.stop_event_driven = AsyncMock()
    strategy_instance.bind_market_data_bus = MagicMock()
    mock_strategy_cls.return_value = strategy_instance
    mock_strategy_cls.init_markets = MagicMock()

    connector_cfg = ConnectorConfig(name="hyperliquid_perpetual", trading_pairs=["BTC-PERP"], api_keys={"key": "v"})
    bus = MagicMock()
    fake_core = FakeTradingCore()
    engine = UserEngine(
        "user-1",
        {"hyperliquid_perpetual": connector_cfg},
        bus=bus,
        trading_core=fake_core,
        client_config=object(),
    )
    config = StrategyConfig(
        user_id="user-1",
        account_id="acct",
        strategy_type="ema_atr",
        connector_name="hyperliquid_perpetual",
        trading_pair="BTC-PERP",
        timeframe="1m",
        fast_ema=12,
        slow_ema=26,
        atr_period=14,
        atr_threshold=Decimal("1"),
        risk_pct_per_trade=Decimal("0.01"),
    )

    strategy_id = await engine.start_ema_atr_strategy(config)

    assert strategy_id is not None
    mock_strategy_cls.init_markets.assert_called_once()
    strategy_instance.bind_market_data_bus.assert_called_once_with(bus)
    strategy_instance.start_event_driven.assert_awaited()
