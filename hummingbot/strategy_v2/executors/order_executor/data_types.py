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
    require_not_above,
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

    # Slippage, and how far this executor may widen it across retries. Gateway swaps
    # only: a CEX order has a price and a book, and nothing to be tolerant about. On a
    # Gateway connector the order is a swap against a pool, and before this there was no
    # slippage setting at any executor level — the request omitted slippagePct entirely,
    # so every attempt used the connector's configured value and every retry sent the
    # identical request.
    #
    # The ramp starts deliberately tight and widens by `slippage_multiplier` on each
    # failure Gateway attributed to slippage, never past `max_slippage_pct`:
    # 0.05, 0.25, 1.25, 5. A failure of any other kind does not widen it — a wrong tick
    # or an insufficient balance says nothing about the tolerance, and loosening one that
    # was never too tight pays more for the same trade.
    slippage_pct: Decimal = Decimal("0.05")
    slippage_multiplier: Decimal = Decimal("5")
    max_slippage_pct: Decimal = Decimal("5")

    @model_validator(mode="after")
    def validate_order(self):
        require_non_empty("connector_name", self.connector_name)
        require_trading_pair("trading_pair", self.trading_pair)
        require_directional_side(self.side)
        require_positive("amount", self.amount)
        require_positive("price", self.price)
        require_at_least("leverage", self.leverage, 1)
        require_positive("slippage_pct", self.slippage_pct)
        require_positive("max_slippage_pct", self.max_slippage_pct)
        require_not_above("slippage_pct", self.slippage_pct, "max_slippage_pct", self.max_slippage_pct)
        # A multiplier of 1 or less never widens, which makes max_slippage_pct a promise
        # the ramp cannot keep.
        if self.slippage_multiplier <= 1:
            raise ValueError(f"slippage_multiplier must be greater than 1, got {self.slippage_multiplier}")
        if self.execution_strategy in [ExecutionStrategy.LIMIT, ExecutionStrategy.LIMIT_MAKER]:
            if self.price is None:
                raise ValueError("price is required for LIMIT and LIMIT_MAKER execution strategies")
        elif self.execution_strategy == ExecutionStrategy.LIMIT_CHASER:
            if self.chaser_config is None:
                raise ValueError("chaser_config is required for LIMIT_CHASER execution strategy")
        return self
