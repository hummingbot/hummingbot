from decimal import Decimal

import pandas as pd

from hummingbot.strategy_v2.backtesting.backtesting_engine_base import BacktestingEngineBase


class MarketMakingBacktesting(BacktestingEngineBase):
    def update_processed_data(self, row: pd.Series):
        self.controller.processed_data["reference_price"] = Decimal(row["reference_price"])
        self.controller.processed_data["spread_multiplier"] = Decimal(row["spread_multiplier"])
