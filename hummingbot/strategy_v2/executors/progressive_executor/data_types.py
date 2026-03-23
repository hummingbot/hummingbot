from decimal import Decimal
from typing import Literal, Tuple

from pydantic import BaseModel

from hummingbot.core.data_type.common import OrderType
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TripleBarrierConfig


class LadderedTrailingStop(BaseModel):
    activation_pnl_pct: Decimal
    trailing_pct: Decimal
    take_profit_table: Tuple[Tuple[Decimal, Decimal], ...]


class YieldTripleBarrierConfig(TripleBarrierConfig):
    """
    Triple Barrier Configuration extended with APR yield and laddered trailing stops.

    :param apr_yield: The APR yield of the strategy.
    :param trailing_stop: The configuration of the laddered trailing stop.
    :param trailing_stop_order_type: The order type of the trailing stop.
    """

    apr_yield: Decimal | None = None
    trailing_stop: LadderedTrailingStop | None = None
    trailing_stop_order_type: OrderType = OrderType.LIMIT

    def new_instance_with_adjusted_volatility(self, volatility_factor: float) -> "YieldTripleBarrierConfig":
        new_trailing_stop = None
        if self.trailing_stop is not None:
            new_trailing_stop = LadderedTrailingStop(
                activation_pnl_pct=self.trailing_stop.activation_pnl_pct * Decimal(volatility_factor),
                trailing_pct=self.trailing_stop.trailing_pct * Decimal(volatility_factor),
                take_profit_table=self.trailing_stop.take_profit_table,
            )

        return YieldTripleBarrierConfig(
            stop_loss=self.stop_loss * Decimal(volatility_factor) if self.stop_loss is not None else None,
            apr_yield=self.apr_yield,
            time_limit=self.time_limit,
            trailing_stop=new_trailing_stop,
            open_order_type=self.open_order_type,
            trailing_stop_order_type=self.trailing_stop_order_type,
            stop_loss_order_type=self.stop_loss_order_type,
            time_limit_order_type=self.time_limit_order_type,
        )


class ProgressiveExecutorConfig(PositionExecutorConfig):
    type: Literal["progressive_executor"] = "progressive_executor"
    triple_barrier_config: YieldTripleBarrierConfig


class ProgressiveExecutorUpdates(BaseModel):
    volatility: Decimal
