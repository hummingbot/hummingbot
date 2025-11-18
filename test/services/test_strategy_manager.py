from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from services.models import StrategyJobSpec
from services.strategy_manager import StrategyManager


@pytest.mark.asyncio
async def test_strategy_manager_creates_and_starts_strategy():
    registry = AsyncMock()
    engine = AsyncMock()
    registry.get_or_start.return_value = engine
    store = AsyncMock()
    manager = StrategyManager(registry, store)

    job = StrategyJobSpec(
        user_id="user-1",
        account_id="acct",
        strategy_type="ema_atr",
        params={
            "connector_name": "hyperliquid_perpetual",
            "trading_pair": "BTC-PERP",
            "timeframe": "1m",
            "fast_ema": 12,
            "slow_ema": 26,
            "atr_period": 14,
            "atr_threshold": Decimal("1"),
            "risk_pct_per_trade": Decimal("0.01"),
        },
    )

    config = await manager.create_and_start(job)

    engine.start_ema_atr_strategy.assert_awaited()
    store.update_strategy_config.assert_awaited()
    assert config.status == "running"
