from decimal import Decimal

import pandas as pd
import pytest

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.backtesting.executors_simulator.position_executor_simulator import PositionExecutorSimulator
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TripleBarrierConfig
from hummingbot.strategy_v2.models.executors import CloseType


@pytest.mark.parametrize("side", [TradeType.BUY, TradeType.SELL])
@pytest.mark.parametrize("cross_before_entry", [False, True])
@pytest.mark.parametrize("cross_after_entry", [False, True])
def test_stop_loss_only_applies_after_entry(side, cross_before_entry, cross_after_entry):
    config = PositionExecutorConfig(
        timestamp=1000.0,
        connector_name="binance",
        trading_pair="ETH-USDT",
        side=side,
        entry_price=Decimal("100"),
        amount=Decimal("1"),
        triple_barrier_config=TripleBarrierConfig(stop_loss=Decimal("0.1"), time_limit=180),
    )
    is_buy = side == TradeType.BUY
    close = [110.0 if is_buy else 90.0, 100.0, 100.0, 100.0]
    low = [105.0 if is_buy else 85.0, 95.0, 95.0, 95.0]
    high = [115.0 if is_buy else 95.0, 105.0, 105.0, 105.0]
    if cross_before_entry:
        (low if is_buy else high)[0] = 80.0 if is_buy else 120.0
    if cross_after_entry:
        (low if is_buy else high)[2] = 85.0 if is_buy else 115.0
        close[2] = 85.0 if is_buy else 115.0

    df = pd.DataFrame({
        "timestamp": [1000.0, 1060.0, 1120.0, 1180.0],
        "close": close,
        "low": low,
        "high": high,
    }).set_index("timestamp", drop=False)

    simulation = PositionExecutorSimulator().simulate(df, config, trade_cost=0.001)
    expected_close = 1120.0 if cross_after_entry else 1180.0
    assert simulation.close_type == (CloseType.STOP_LOSS if cross_after_entry else CloseType.TIME_LIMIT)
    assert simulation.fill_timestamp == 1060.0
    assert simulation.executor_simulation.index[-1] == expected_close
    before_fill = simulation.get_executor_info_at_timestamp(1000.0)
    assert before_fill.is_active
    assert not before_fill.is_trading
    assert before_fill.filled_amount_quote == 0
    after_fill = simulation.get_executor_info_at_timestamp(1060.0)
    assert after_fill.is_trading
    assert after_fill.filled_amount_quote == Decimal("100")
