from decimal import Decimal
from typing import Literal, Optional

from pydantic import field_validator

from hummingbot.core.data_type.common import PositionAction, TradeType
from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase


class BestPriceExecutorConfig(ExecutorConfigBase):
    type: Literal["best_price_executor"] = "best_price_executor"
    trading_pair: str
    connector_name: str
    side: TradeType
    amount: Decimal
    position_action: PositionAction = PositionAction.OPEN
    price_diff: Decimal
    leverage: int = 1
    level_id: Optional[str] = None
    update_interval: Optional[float] = 0.5

    @field_validator("price_diff")
    @classmethod
    def validate_price_diff(cls, value):
        if value is None:
            raise ValueError("price_diff is required for BestPrice execution strategy")
        if value < 0:
            raise ValueError("price_diff must be non-negative")
        return value
