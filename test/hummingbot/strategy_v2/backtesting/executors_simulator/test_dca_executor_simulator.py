from decimal import Decimal
from pathlib import Path
import sys
import types

import pandas as pd

from hummingbot.core.data_type.common import TradeType

# The backtesting package's public initializer imports the full client runtime,
# including optional Cython extensions. The simulator itself only depends on the
# backtesting submodules, so expose that package path without initializing the
# client runtime for this focused unit test.
backtesting_package = "hummingbot.strategy_v2.backtesting"
if backtesting_package not in sys.modules:
    module = types.ModuleType(backtesting_package)
    module.__path__ = [str(Path(__file__).parents[5] / "hummingbot" / "strategy_v2" / "backtesting")]
    sys.modules[backtesting_package] = module

from hummingbot.strategy_v2.backtesting.executors_simulator.dca_executor_simulator import DCAExecutorSimulator
from hummingbot.strategy_v2.executors.dca_executor.data_types import DCAExecutorConfig


def test_dca_simulator_uses_each_stage_entry_timestamp():
    config = DCAExecutorConfig(
        id="test",
        timestamp=100,
        side=TradeType.BUY,
        connector_name="binance",
        trading_pair="ETH-USDT",
        amounts_quote=[Decimal("10"), Decimal("20")],
        prices=[Decimal("100"), Decimal("90")],
    )
    candles = pd.DataFrame(
        {
            "timestamp": [100, 200, 300],
            "close": [100.0, 90.0, 95.0],
            "low": [100.0, 90.0, 95.0],
            "high": [100.0, 90.0, 95.0],
        }
    ).set_index("timestamp", drop=False)

    simulation = DCAExecutorSimulator().simulate(candles, config, trade_cost=0)

    assert simulation.executor_simulation.loc[100, "filled_amount_quote"] == 10
    assert simulation.executor_simulation.loc[200, "filled_amount_quote"] == 30
