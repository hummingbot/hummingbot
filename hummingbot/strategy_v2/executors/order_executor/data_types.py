from decimal import Decimal
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, model_validator

from hummingbot.core.data_type.common import PositionAction, TradeType
from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase
from hummingbot.strategy_v2.executors.validation import (
    require_at_least,
    require_directional_side,
    require_non_empty,
    require_positive,
    require_trading_pair,
)


class ExecutionStrategy(Enum):
    LIMIT = "LIMIT"
    LIMIT_MAKER = "LIMIT_MAKER"
    MARKET = "MARKET"
    LIMIT_CHASER = "LIMIT_CHASER"


class LimitChaserConfig(BaseModel):
    distance: Decimal
    refresh_threshold: Decimal

    @model_validator(mode="after")
    def validate_chaser(self):
        require_positive("chaser_config.distance", self.distance)
        require_positive("chaser_config.refresh_threshold", self.refresh_threshold)
        return self


class OrderExecutorConfig(ExecutorConfigBase):
    type: Literal["order_executor"] = "order_executor"
    trading_pair: str
    connector_name: str
    side: TradeType
    amount: Decimal
    position_action: PositionAction = PositionAction.OPEN
    price: Optional[Decimal] = None  # Required for LIMIT and LIMIT_MAKER
    chaser_config: Optional[LimitChaserConfig] = None  # Required for LIMIT_CHASER
    execution_strategy: ExecutionStrategy
    leverage: int = 1
    level_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_order(self):
        require_non_empty("connector_name", self.connector_name)
        require_trading_pair("trading_pair", self.trading_pair)
        require_directional_side(self.side)
        require_positive("amount", self.amount)
        require_positive("price", self.price)
        require_at_least("leverage", self.leverage, 1)
        if self.execution_strategy in [ExecutionStrategy.LIMIT, ExecutionStrategy.LIMIT_MAKER]:
            if self.price is None:
                raise ValueError("price is required for LIMIT and LIMIT_MAKER execution strategies")
        elif self.execution_strategy == ExecutionStrategy.LIMIT_CHASER:
            if self.chaser_config is None:
                raise ValueError("chaser_config is required for LIMIT_CHASER execution strategy")
        return self
