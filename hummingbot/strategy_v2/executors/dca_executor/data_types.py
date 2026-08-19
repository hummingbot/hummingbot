from decimal import Decimal
from enum import Enum
from typing import List, Literal, Optional

from pydantic import model_validator

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase
from hummingbot.strategy_v2.executors.position_executor.data_types import TrailingStop
from hummingbot.strategy_v2.executors.validation import (
    require_all_positive,
    require_at_least,
    require_directional_side,
    require_non_empty,
    require_positive,
    require_trading_pair,
)


class DCAMode(Enum):
    MAKER = "MAKER"
    TAKER = "TAKER"


class DCAExecutorConfig(ExecutorConfigBase):
    type: Literal["dca_executor"] = "dca_executor"
    connector_name: str
    trading_pair: str
    side: TradeType
    leverage: int = 1
    amounts_quote: List[Decimal]
    prices: List[Decimal]
    take_profit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    trailing_stop: Optional[TrailingStop] = None
    time_limit: Optional[int] = None
    mode: DCAMode = DCAMode.MAKER
    activation_bounds: Optional[List[Decimal]] = None
    level_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_dca(self):
        require_non_empty("connector_name", self.connector_name)
        require_trading_pair("trading_pair", self.trading_pair)
        require_directional_side(self.side)
        require_at_least("leverage", self.leverage, 1)
        # Every level is an (amount, price) pair, so the two lists have to line up.
        if len(self.amounts_quote) != len(self.prices):
            raise ValueError(f"amounts_quote ({len(self.amounts_quote)} levels) and prices "
                             f"({len(self.prices)} levels) must have the same length")
        if len(self.prices) == 0:
            raise ValueError("prices must define at least one level")
        require_all_positive("amounts_quote", self.amounts_quote)
        require_all_positive("prices", self.prices)
        require_positive("take_profit", self.take_profit)
        require_positive("stop_loss", self.stop_loss)
        require_positive("time_limit", self.time_limit)
        require_all_positive("activation_bounds", self.activation_bounds)
        return self
