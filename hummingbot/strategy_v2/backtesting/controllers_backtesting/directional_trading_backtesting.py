import pandas as pd

from hummingbot.strategy_v2.backtesting.backtesting_engine_base import BacktestingEngineBase


class DirectionalTradingBacktesting(BacktestingEngineBase):
    async def update_processed_data(self, row: pd.Series):
        self.controller.processed_data["signal"] = row["signal"]
