from decimal import Decimal
from enum import Enum
from typing import Literal, Optional

from pydantic import model_validator

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase
from hummingbot.strategy_v2.executors.validation import (
    require_at_least,
    require_directional_side,
    require_non_empty,
    require_non_negative,
    require_positive,
    require_trading_pair,
)


class TWAPMode(Enum):
    MAKER = "MAKER"
    TAKER = "TAKER"


class TWAPExecutorConfig(ExecutorConfigBase):
    type: Literal["twap_executor"] = "twap_executor"
    connector_name: str
    trading_pair: str
    side: TradeType
    leverage: int = 1
    total_amount_quote: Decimal
    total_duration: int
    order_interval: int
    mode: TWAPMode = TWAPMode.TAKER

    # MAKER mode specific parameters
    limit_order_buffer: Optional[Decimal] = None
    order_resubmission_time: Optional[int] = None

    @model_validator(mode="after")
    def validate_twap(self):
        require_non_empty("connector_name", self.connector_name)
        require_trading_pair("trading_pair", self.trading_pair)
        require_directional_side(self.side)
        require_at_least("leverage", self.leverage, 1)
        require_positive("total_amount_quote", self.total_amount_quote)
        require_positive("total_duration", self.total_duration)
        # number_of_orders divides the duration by the interval, so a non positive interval
        # either raises ZeroDivisionError or yields a negative number of orders.
        require_positive("order_interval", self.order_interval)
        if self.is_maker:
            if self.limit_order_buffer is None:
                raise ValueError("limit_order_buffer is required for MAKER mode")
            require_non_negative("limit_order_buffer", self.limit_order_buffer)
            require_positive("order_resubmission_time", self.order_resubmission_time)
        return self

    @property
    def is_maker(self) -> bool:
        return self.mode == TWAPMode.MAKER

    @property
    def number_of_orders(self) -> int:
        return (self.total_duration // self.order_interval) + 1

    @property
    def order_amount_quote(self) -> Decimal:
        return self.total_amount_quote / self.number_of_orders

    @property
    def order_type(self) -> OrderType:
        return OrderType.LIMIT if self.is_maker else OrderType.MARKET
