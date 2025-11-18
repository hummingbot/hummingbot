from unittest.mock import AsyncMock, MagicMock

import pytest

try:
    from hummingbot.client.config.client_config_map import ClientConfigMap
    from hummingbot.core.trading_core import TradingCore
except ModuleNotFoundError:  # pragma: no cover - compiled extensions missing
    pytest.skip("Skipping TradingCore event-driven tests because hummingbot extensions are unavailable.", allow_module_level=True)


@pytest.mark.asyncio
async def test_event_driven_strategy_bypasses_clock():
    config = ClientConfigMap()
    trading_core = TradingCore(config)
    trading_core.initialize_markets_recorder = MagicMock()
    trading_core.markets_recorder = MagicMock()
    trading_core.start_clock = AsyncMock()
    trading_core.clock = MagicMock()
    trading_core.client_config_map.kill_switch_mode.model_config["title"] = "kill_switch_disabled"

    strategy = MagicMock()
    strategy.is_event_driven = True
    strategy.start_event_driven = AsyncMock()
    trading_core.strategy = strategy
    trading_core.strategy_name = "dummy"

    await trading_core._start_strategy_execution()

    strategy.start_event_driven.assert_awaited()
    trading_core.clock.add_iterator.assert_not_called()


@pytest.mark.asyncio
async def test_non_event_driven_strategy_added_to_clock():
    config = ClientConfigMap()
    trading_core = TradingCore(config)
    trading_core.initialize_markets_recorder = MagicMock()
    trading_core.markets_recorder = MagicMock()
    trading_core.start_clock = AsyncMock()
    mock_clock = MagicMock()
    trading_core.clock = mock_clock
    trading_core.client_config_map.kill_switch_mode.model_config["title"] = "kill_switch_disabled"

    strategy = MagicMock()
    strategy.is_event_driven = False
    trading_core.strategy = strategy
    trading_core.strategy_name = "legacy"

    await trading_core._start_strategy_execution()

    mock_clock.add_iterator.assert_called_once_with(strategy)


@pytest.mark.asyncio
async def test_stop_strategy_waits_for_event_driven_shutdown():
    config = ClientConfigMap()
    trading_core = TradingCore(config)
    trading_core.clock = MagicMock()
    strategy = MagicMock()
    strategy.is_event_driven = True
    strategy.stop_event_driven = AsyncMock()
    trading_core.strategy = strategy
    trading_core._strategy_running = True

    result = await trading_core.stop_strategy()

    assert result
    strategy.stop_event_driven.assert_awaited()
