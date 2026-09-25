from decimal import Decimal
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, model_validator

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase
from hummingbot.strategy_v2.executors.position_executor.data_types import TripleBarrierConfig
from hummingbot.strategy_v2.executors.validation import (
    require_at_least,
    require_directional_side,
    require_lower_than,
    require_non_empty,
    require_non_negative,
    require_positive,
    require_stop_price,
    require_trading_pair,
)
from hummingbot.strategy_v2.models.executors import TrackedOrder


class GridExecutorConfig(ExecutorConfigBase):
    type: Literal["grid_executor"] = "grid_executor"
    # Boundaries
    connector_name: str
    trading_pair: str
    # start_price is always the bottom of the grid and end_price the top, for both sides.
    start_price: Decimal
    end_price: Decimal
    # Stop-out price for the whole grid, beyond the losing edge of the range. 0 disables it.
    limit_price: Decimal
    side: TradeType = TradeType.BUY
    # Profiling
    total_amount_quote: Decimal
    min_spread_between_orders: Decimal = Decimal("0.0005")
    min_order_amount_quote: Decimal = Decimal("5")
    # Execution
    max_open_orders: int = 5
    max_orders_per_batch: Optional[int] = None
    order_frequency: int = 0
    activation_bounds: Optional[Decimal] = None
    safe_extra_spread: Decimal = Decimal("0.0001")
    # Risk Management
    triple_barrier_config: TripleBarrierConfig
    leverage: int = 20
    level_id: Optional[str] = None
    deduct_base_fees: bool = False
    keep_position: bool = False
    coerce_tp_to_step: bool = False

    @model_validator(mode="after")
    def validate_grid(self):
        require_non_empty("connector_name", self.connector_name)
        require_trading_pair("trading_pair", self.trading_pair)
        require_directional_side(self.side)
        # The levels are distributed from start_price to end_price and the step is derived from
        # (end_price - start_price) / start_price, so an inverted range silently collapses the
        # grid into a single level at the midpoint.
        require_positive("start_price", self.start_price)
        require_lower_than("start_price", self.start_price, "end_price", self.end_price)
        require_non_negative("limit_price", self.limit_price)
        if self.limit_price > 0:
            require_stop_price(self.side, "limit_price", self.limit_price,
                               [("start_price", self.start_price), ("end_price", self.end_price)])
        require_positive("total_amount_quote", self.total_amount_quote)
        require_positive("min_spread_between_orders", self.min_spread_between_orders)
        require_positive("min_order_amount_quote", self.min_order_amount_quote)
        require_at_least("max_open_orders", self.max_open_orders, 1)
        require_at_least("max_orders_per_batch", self.max_orders_per_batch, 1)
        require_non_negative("order_frequency", self.order_frequency)
        require_positive("activation_bounds", self.activation_bounds)
        require_non_negative("safe_extra_spread", self.safe_extra_spread)
        require_at_least("leverage", self.leverage, 1)
        return self


class GridLevelStates(Enum):
    NOT_ACTIVE = "NOT_ACTIVE"
    OPEN_ORDER_PLACED = "OPEN_ORDER_PLACED"
    OPEN_ORDER_FILLED = "OPEN_ORDER_FILLED"
    CLOSE_ORDER_PLACED = "CLOSE_ORDER_PLACED"
    COMPLETE = "COMPLETE"


class GridLevel(BaseModel):
    id: str
    price: Decimal
    amount_quote: Decimal
    take_profit: Decimal
    side: TradeType
    open_order_type: OrderType
    take_profit_order_type: OrderType
    active_open_order: Optional[TrackedOrder] = None
    active_close_order: Optional[TrackedOrder] = None
    state: GridLevelStates = GridLevelStates.NOT_ACTIVE
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def update_state(self):
        if self.active_open_order is None:
            self.state = GridLevelStates.NOT_ACTIVE
        elif self.active_open_order.is_filled:
            self.state = GridLevelStates.OPEN_ORDER_FILLED
        else:
            self.state = GridLevelStates.OPEN_ORDER_PLACED
        if self.active_close_order is not None:
            if self.active_close_order.is_filled:
                self.state = GridLevelStates.COMPLETE
            else:
                self.state = GridLevelStates.CLOSE_ORDER_PLACED

    def reset_open_order(self):
        self.active_open_order = None
        self.state = GridLevelStates.NOT_ACTIVE

    def reset_close_order(self):
        self.active_close_order = None
        self.state = GridLevelStates.OPEN_ORDER_FILLED

    def reset_level(self):
        self.active_open_order = None
        self.active_close_order = None
        self.state = GridLevelStates.NOT_ACTIVE
