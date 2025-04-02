from decimal import Decimal
from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, model_validator

from hummingbot.core.data_type.common import PositionAction, TradeType
from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase


class ExecutionStrategy(Enum):
    LIMIT = "LIMIT"
    LIMIT_MAKER = "LIMIT_MAKER"
    MARKET = "MARKET"
    LIMIT_CHASER = "LIMIT_CHASER"


class LimitChaserConfig(BaseModel):
    distance: Decimal
    refresh_threshold: Decimal


class OrderExecutorConfig(ExecutorConfigBase):
    type: str = "order_executor"
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
    def validate_execution_strategy(self, values: Dict):
        execution_strategy = values.get("execution_strategy")
        if execution_strategy in [ExecutionStrategy.LIMIT, ExecutionStrategy.LIMIT_MAKER]:
            if values.get('price') is None:
                raise ValueError("Price is required for LIMIT and LIMIT_MAKER execution strategies")
        elif execution_strategy == ExecutionStrategy.LIMIT_CHASER:
            if values.get('chaser_config') is None:
                raise ValueError("Chaser config is required for LIMIT_CHASER execution strategy")
        return self
