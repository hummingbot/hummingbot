from decimal import Decimal

import pandas as pd
import pytest

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.backtesting.executors_simulator.dca_executor_simulator import DCAExecutorSimulator
from hummingbot.strategy_v2.executors.dca_executor.data_types import DCAExecutorConfig
from hummingbot.strategy_v2.models.executors import CloseType

TIMESTAMPS = [1000.0, 1001.0, 1002.0, 1003.0]


def _simulate(side, prices, close):
    df = pd.DataFrame({
        "timestamp": TIMESTAMPS,
        "open": close,
        "high": [price + 1 for price in close],
        "low": [price - 1 for price in close],
        "close": close,
        "volume": [1.0] * len(TIMESTAMPS),
    }, index=TIMESTAMPS)
    config = DCAExecutorConfig(
        id="no-sl",
        timestamp=TIMESTAMPS[0],
        connector_name="binance",
        trading_pair="ETH-USDT",
        side=side,
        amounts_quote=[Decimal("10")] * len(prices),
        prices=[Decimal(price) for price in prices],
    )
    return DCAExecutorSimulator().simulate(df, config, trade_cost=0)


@pytest.mark.parametrize("side, close", [
    (TradeType.BUY, [100.0, 100.0, 99.0, 98.0]),
    (TradeType.SELL, [100.0, 100.0, 101.0, 102.0]),
])
def test_single_level_without_stop_loss_runs_to_the_end_of_the_data(side, close):
    simulation = _simulate(side, prices=["100"], close=close)

    assert simulation.close_type == CloseType.TIME_LIMIT
    assert simulation.executor_simulation.index[-1] == TIMESTAMPS[-1]
    assert simulation.executor_simulation.loc[TIMESTAMPS[0], "filled_amount_quote_0"] == 10.0


@pytest.mark.parametrize("side, prices, close", [
    (TradeType.BUY, ["100", "95"], [100.0, 99.0, 95.0, 96.0]),
    (TradeType.SELL, ["100", "105"], [100.0, 101.0, 105.0, 104.0]),
])
def test_last_entered_level_without_stop_loss_runs_to_the_end_of_the_data(side, prices, close):
    simulation = _simulate(side, prices=prices, close=close)

    assert simulation.close_type == CloseType.TIME_LIMIT
    assert simulation.executor_simulation.index[-1] == TIMESTAMPS[-1]
    assert simulation.executor_simulation.loc[TIMESTAMPS[1], "filled_amount_quote_1"] == 0.0
    assert simulation.executor_simulation.loc[TIMESTAMPS[2], "filled_amount_quote_1"] == 10.0
