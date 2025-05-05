from decimal import Decimal
from typing import Union

import pandas as pd
from pydantic import BaseModel, ConfigDict, field_validator

from hummingbot.strategy_v2.executors.dca_executor.data_types import DCAExecutorConfig
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


class ExecutorSimulation(BaseModel):
    config: Union[PositionExecutorConfig, DCAExecutorConfig]
    executor_simulation: pd.DataFrame
    close_type: CloseType
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator('executor_simulation', mode="before")
    @classmethod
    def validate_dataframe(cls, v):
        if not isinstance(v, pd.DataFrame):
            raise ValueError("executor_simulation must be a pandas DataFrame")
        return v

    def get_executor_info_at_timestamp(self, timestamp: float) -> ExecutorInfo:
        # Initialize tracking of last lookup
        if not hasattr(self, '_max_timestamp'):
            self._max_timestamp = self.executor_simulation.index.max()

        pos = self.executor_simulation.index.searchsorted(timestamp, side='right') - 1
        if pos < 0:
            # Very rare.
            return self._empty_executor_info()

        last_entry = self.executor_simulation.iloc[pos]
        is_active = last_entry.name < self._max_timestamp
        return ExecutorInfo(
            id=self.config.id,
            timestamp=self.config.timestamp,
            type=self.config.type,
            close_timestamp=None if is_active else float(last_entry.name),
            close_type=None if is_active else self.close_type,
            status=RunnableStatus.RUNNING if is_active else RunnableStatus.TERMINATED,
            config=self.config,
            net_pnl_pct=Decimal(last_entry['net_pnl_pct']),
            net_pnl_quote=Decimal(last_entry['net_pnl_quote']),
            cum_fees_quote=Decimal(last_entry['cum_fees_quote']),
            filled_amount_quote=Decimal(last_entry['filled_amount_quote']),
            is_active=is_active,
            is_trading=last_entry['filled_amount_quote'] > 0 and is_active,
            custom_info=self.get_custom_info(last_entry)
        )

    def _empty_executor_info(self):
        # Helper method to create an empty ExecutorInfo
        return ExecutorInfo(
            id=self.config.id,
            timestamp=self.config.timestamp,
            type=self.config.type,
            status=RunnableStatus.TERMINATED,
            config=self.config,
            net_pnl_pct=Decimal(0),
            net_pnl_quote=Decimal(0),
            cum_fees_quote=Decimal(0),
            filled_amount_quote=Decimal(0),
            is_active=False,
            is_trading=False,
            custom_info={}
        )

    def get_custom_info(self, last_entry: pd.Series) -> dict:
        current_position_average_price = last_entry['current_position_average_price'] if "current_position_average_price" in last_entry else None
        return {
            "close_price": last_entry['close'],
            "level_id": self.config.level_id,
            "side": self.config.side,
            "current_position_average_price": current_position_average_price
        }


class ExecutorSimulatorBase:
    """Base class for trading simulators."""

    def simulate(self, df: pd.DataFrame, config, trade_cost: float) -> ExecutorSimulation:
        """Simulates trading based on provided configuration and market data."""
        # This method should be generic enough to handle various trading strategies.
        raise NotImplementedError
