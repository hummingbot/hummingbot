import logging
from decimal import Decimal
from typing import List, Optional

from pydantic import Field, field_validator, model_validator

from hummingbot.core.data_type.common import MarketDict
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.executors.lp_executor.data_types import LPExecutorConfig, LPExecutorStates
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction, StopExecutorAction
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


class LPRebalancerConfig(ControllerConfigBase):
    """
    Configuration for LP Rebalancer Controller.

    Uses total_amount_quote and side for position sizing.
    Implements KEEP vs REBALANCE logic based on price limits.
    """
    controller_type: str = "generic"
    controller_name: str = "lp_rebalancer"
    candles_config: List[CandlesConfig] = []

    # Pool configuration (required)
    connector_name: str = "meteora/clmm"
    network: str = "solana-mainnet-beta"
    trading_pair: str = ""
    pool_address: str = ""

    # Position parameters
    total_amount_quote: Decimal = Field(default=Decimal("50"), json_schema_extra={"is_updatable": True})
    side: int = Field(default=1, json_schema_extra={"is_updatable": True})  # 0=BOTH, 1=BUY, 2=SELL
    position_width_pct: Decimal = Field(default=Decimal("0.5"), json_schema_extra={"is_updatable": True})
    position_offset_pct: Decimal = Field(
        default=Decimal("0.01"),
        json_schema_extra={"is_updatable": True},
        description="Offset from current price to ensure single-sided positions start out-of-range (e.g., 0.1 = 0.1%)"
    )

    # Rebalancing
    rebalance_seconds: int = Field(default=60, json_schema_extra={"is_updatable": True})
    rebalance_threshold_pct: Decimal = Field(
        default=Decimal("0.1"),
        json_schema_extra={"is_updatable": True},
        description="Price must be this % out of range before rebalance timer starts (e.g., 0.1 = 0.1%, 2 = 2%)"
    )

    # Price limits - overlapping grids for sell and buy ranges
    # Sell range: [sell_price_min, sell_price_max]
    # Buy range: [buy_price_min, buy_price_max]
    sell_price_max: Optional[Decimal] = Field(default=None, json_schema_extra={"is_updatable": True})
    sell_price_min: Optional[Decimal] = Field(default=None, json_schema_extra={"is_updatable": True})
    buy_price_max: Optional[Decimal] = Field(default=None, json_schema_extra={"is_updatable": True})
    buy_price_min: Optional[Decimal] = Field(default=None, json_schema_extra={"is_updatable": True})

    # Connector-specific params (optional)
    strategy_type: Optional[int] = Field(default=None, json_schema_extra={"is_updatable": True})

    @field_validator("sell_price_min", "sell_price_max", "buy_price_min", "buy_price_max", mode="before")
    @classmethod
    def validate_price_limits(cls, v):
        """Allow null/None values for price limits."""
        if v is None:
            return None
        return Decimal(str(v))

    @field_validator("side", mode="before")
    @classmethod
    def validate_side(cls, v):
        """Validate side is 0, 1, or 2."""
        v = int(v)
        if v not in (0, 1, 2):
            raise ValueError("side must be 0 (BOTH), 1 (BUY), or 2 (SELL)")
        return v

    @model_validator(mode="after")
    def validate_price_limit_ranges(self):
        """Validate that price limit ranges are valid."""
        if self.buy_price_max is not None and self.buy_price_min is not None:
            if self.buy_price_max < self.buy_price_min:
                raise ValueError("buy_price_max must be >= buy_price_min")
        if self.sell_price_max is not None and self.sell_price_min is not None:
            if self.sell_price_max < self.sell_price_min:
                raise ValueError("sell_price_max must be >= sell_price_min")
        return self

    def update_markets(self, markets: MarketDict) -> MarketDict:
        """Register the LP connector with trading pair"""
        return markets.add_or_update(self.connector_name, self.trading_pair)


class LPRebalancer(ControllerBase):
    """
    Controller for LP position management with smart rebalancing.

    Key features:
    - Uses total_amount_quote for all positions (initial and rebalance)
    - Derives rebalance side from price vs last executor's range
    - KEEP position when already at limit, REBALANCE when not
    - Validates bounds before creating positions
    """

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, config: LPRebalancerConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config: LPRebalancerConfig = config

        # Parse token symbols from trading pair
        parts = config.trading_pair.split("-")
        self._base_token: str = parts[0] if len(parts) >= 2 else ""
        self._quote_token: str = parts[1] if len(parts) >= 2 else ""

        # Rebalance tracking
        self._pending_rebalance: bool = False
        self._pending_rebalance_side: Optional[int] = None  # Side for pending rebalance

        # Track the executor we created
        self._current_executor_id: Optional[str] = None

        # Track amounts from last closed position (for rebalance sizing)
        self._last_closed_base_amount: Optional[Decimal] = None
        self._last_closed_quote_amount: Optional[Decimal] = None
        self._last_closed_base_fee: Optional[Decimal] = None
        self._last_closed_quote_fee: Optional[Decimal] = None

        # Track initial balances for comparison
        self._initial_base_balance: Optional[Decimal] = None
        self._initial_quote_balance: Optional[Decimal] = None

        # Flag to trigger balance update after position creation
        self._pending_balance_update: bool = False

        # Cached pool price (updated in update_processed_data)
        self._pool_price: Optional[Decimal] = None

        # Initialize rate sources
        self.market_data_provider.initialize_rate_sources([
            ConnectorPair(
                connector_name=self.config.connector_name,
                trading_pair=self.config.trading_pair
            )
        ])

    def active_executor(self) -> Optional[ExecutorInfo]:
        """Get current active executor (should be 0 or 1)"""
        active = [e for e in self.executors_info if e.is_active]
        return active[0] if active else None

    def get_tracked_executor(self) -> Optional[ExecutorInfo]:
        """Get the executor we're currently tracking (by ID)"""
        if not self._current_executor_id:
            return None
        for e in self.executors_info:
            if e.id == self._current_executor_id:
                return e
        return None

    def is_tracked_executor_terminated(self) -> bool:
        """Check if the executor we created has terminated"""
        from hummingbot.strategy_v2.models.base import RunnableStatus
        if not self._current_executor_id:
            return True
        executor = self.get_tracked_executor()
        if executor is None:
            return True
        return executor.status == RunnableStatus.TERMINATED

    def _trigger_balance_update(self):
        """Trigger a balance update on the connector after position changes."""
        try:
            connector = self.market_data_provider.get_connector(self.config.connector_name)
            if hasattr(connector, 'update_balances'):
                safe_ensure_future(connector.update_balances())
                self.logger().info("Triggered balance update after position creation")
        except Exception as e:
            self.logger().debug(f"Could not trigger balance update: {e}")

    def determine_executor_actions(self) -> List[ExecutorAction]:
        """Decide whether to create/stop executors"""
        # Capture initial balances on first run
        if self._initial_base_balance is None:
            try:
                self._initial_base_balance = self.market_data_provider.get_balance(
                    self.config.connector_name, self._base_token
                )
                self._initial_quote_balance = self.market_data_provider.get_balance(
                    self.config.connector_name, self._quote_token
                )
            except Exception as e:
                self.logger().debug(f"Could not capture initial balances: {e}")

        actions = []
        executor = self.active_executor()

        # Track the active executor's ID if we don't have one yet
        if executor and not self._current_executor_id:
            self._current_executor_id = executor.id
            self.logger().info(f"Tracking executor: {executor.id}")

        # No active executor - check if we should create one
        if executor is None:
            if not self.is_tracked_executor_terminated():
                tracked = self.get_tracked_executor()
                self.logger().debug(
                    f"Waiting for executor {self._current_executor_id} to terminate "
                    f"(status: {tracked.status if tracked else 'not found'})"
                )
                return actions

            # Previous executor terminated - capture final amounts for rebalance sizing
            terminated_executor = self.get_tracked_executor()
            if terminated_executor and self._pending_rebalance:
                self._last_closed_base_amount = Decimal(str(terminated_executor.custom_info.get("base_amount", 0)))
                self._last_closed_quote_amount = Decimal(str(terminated_executor.custom_info.get("quote_amount", 0)))
                self._last_closed_base_fee = Decimal(str(terminated_executor.custom_info.get("base_fee", 0)))
                self._last_closed_quote_fee = Decimal(str(terminated_executor.custom_info.get("quote_fee", 0)))
                self.logger().info(
                    f"Captured closed position amounts: base={self._last_closed_base_amount}, "
                    f"quote={self._last_closed_quote_amount}, base_fee={self._last_closed_base_fee}, "
                    f"quote_fee={self._last_closed_quote_fee}"
                )

            # Clear tracking
            self._current_executor_id = None

            # Determine side for new position
            if self._pending_rebalance and self._pending_rebalance_side is not None:
                side = self._pending_rebalance_side
                self._pending_rebalance = False
                self._pending_rebalance_side = None
            else:
                side = self.config.side

            # Create executor config with calculated bounds
            executor_config = self._create_executor_config(side)
            if executor_config is None:
                self.logger().warning("Skipping position creation - invalid bounds")
                return actions

            actions.append(CreateExecutorAction(
                controller_id=self.config.id,
                executor_config=executor_config
            ))
            self._pending_balance_update = True
            return actions

        # Trigger balance update after position is created
        if self._pending_balance_update:
            state = executor.custom_info.get("state")
            if state in ("IN_RANGE", "OUT_OF_RANGE"):
                self._pending_balance_update = False
                self._trigger_balance_update()

        # Check executor state
        state = executor.custom_info.get("state")

        # Don't take action while executor is in transition states
        if state in [LPExecutorStates.OPENING.value, LPExecutorStates.CLOSING.value]:
            return actions

        # Check for rebalancing when out of range
        if state == LPExecutorStates.OUT_OF_RANGE.value:
            # Check if price is beyond threshold before considering timer
            if self._is_beyond_rebalance_threshold(executor):
                out_of_range_seconds = executor.custom_info.get("out_of_range_seconds")
                if out_of_range_seconds is not None and out_of_range_seconds >= self.config.rebalance_seconds:
                    rebalance_action = self._handle_rebalance(executor)
                    if rebalance_action:
                        actions.append(rebalance_action)

        return actions

    def _handle_rebalance(self, executor: ExecutorInfo) -> Optional[StopExecutorAction]:
        """
        Handle rebalancing logic.

        Returns StopExecutorAction if rebalance needed, None if KEEP.
        """
        current_price = executor.custom_info.get("current_price")
        lower_price = executor.custom_info.get("lower_price")
        upper_price = executor.custom_info.get("upper_price")

        if current_price is None or lower_price is None or upper_price is None:
            return None

        current_price = Decimal(str(current_price))
        lower_price = Decimal(str(lower_price))
        upper_price = Decimal(str(upper_price))

        # Step 1: Determine side from price direction (using [lower, upper) convention)
        if current_price >= upper_price:
            new_side = 1  # BUY - price at or above range
        elif current_price < lower_price:
            new_side = 2  # SELL - price below range
        else:
            # Price is in range, shouldn't happen in OUT_OF_RANGE state
            self.logger().warning(f"Price {current_price} appears in range [{lower_price}, {upper_price})")
            return None

        # Step 2: Check if new position would be valid (price within limits)
        if not self._is_price_within_limits(current_price, new_side):
            # Don't log repeatedly - this is checked every tick
            return None

        # Step 4: Initiate rebalance
        self._pending_rebalance = True
        self._pending_rebalance_side = new_side
        self.logger().info(
            f"REBALANCE initiated (side={new_side}, price={current_price}, "
            f"old_bounds=[{lower_price}, {upper_price}])"
        )

        return StopExecutorAction(
            controller_id=self.config.id,
            executor_id=executor.id,
            keep_position=False,
        )

    def _is_beyond_rebalance_threshold(self, executor: ExecutorInfo) -> bool:
        """
        Check if price is beyond the rebalance threshold.

        Price must be this % out of range before rebalance timer is considered.
        """
        current_price = executor.custom_info.get("current_price")
        lower_price = executor.custom_info.get("lower_price")
        upper_price = executor.custom_info.get("upper_price")

        if current_price is None or lower_price is None or upper_price is None:
            return False

        threshold = self.config.rebalance_threshold_pct / Decimal("100")

        # Check if price is beyond threshold above upper or below lower
        if current_price > upper_price:
            deviation_pct = (current_price - upper_price) / upper_price
            return deviation_pct >= threshold
        elif current_price < lower_price:
            deviation_pct = (lower_price - current_price) / lower_price
            return deviation_pct >= threshold

        return False  # Price is in range

    def _create_executor_config(self, side: int) -> Optional[LPExecutorConfig]:
        """
        Create executor config for the given side.

        Returns None if bounds are invalid.
        """
        # Use pool price (fetched in update_processed_data every tick)
        current_price = self._pool_price
        if current_price is None or current_price == 0:
            self.logger().warning("No pool price available - waiting for update_processed_data")
            return None

        # Calculate amounts based on side
        base_amt, quote_amt = self._calculate_amounts(side, current_price)

        # Calculate bounds
        lower_price, upper_price = self._calculate_price_bounds(side, current_price)

        # Validate bounds
        if lower_price >= upper_price:
            self.logger().warning(f"Invalid bounds [{lower_price}, {upper_price}] - skipping position")
            return None

        # Build extra params (connector-specific)
        extra_params = {}
        if self.config.strategy_type is not None:
            extra_params["strategyType"] = self.config.strategy_type

        # Check if bounds were clamped by price limits
        clamped = []
        if side == 1:  # BUY
            if self.config.buy_price_max and upper_price == self.config.buy_price_max:
                clamped.append(f"upper=buy_price_max({self.config.buy_price_max})")
            if self.config.buy_price_min and lower_price == self.config.buy_price_min:
                clamped.append(f"lower=buy_price_min({self.config.buy_price_min})")
        elif side == 2:  # SELL
            if self.config.sell_price_min and lower_price == self.config.sell_price_min:
                clamped.append(f"lower=sell_price_min({self.config.sell_price_min})")
            if self.config.sell_price_max and upper_price == self.config.sell_price_max:
                clamped.append(f"upper=sell_price_max({self.config.sell_price_max})")

        clamped_info = f", clamped: {', '.join(clamped)}" if clamped else ""
        offset_pct = self.config.position_offset_pct
        self.logger().info(
            f"Creating position: side={side}, pool_price={current_price:.2f}, "
            f"bounds=[{lower_price:.4f}, {upper_price:.4f}], offset_pct={offset_pct}, "
            f"base={base_amt:.4f}, quote={quote_amt:.4f}{clamped_info}"
        )

        return LPExecutorConfig(
            timestamp=self.market_data_provider.time(),
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            pool_address=self.config.pool_address,
            lower_price=lower_price,
            upper_price=upper_price,
            base_amount=base_amt,
            quote_amount=quote_amt,
            side=side,
            position_offset_pct=self.config.position_offset_pct,
            extra_params=extra_params if extra_params else None,
            keep_position=False,
        )

    def _calculate_amounts(self, side: int, current_price: Decimal) -> tuple:
        """
        Calculate base and quote amounts based on side and total_amount_quote.

        For rebalances, clamps to the actual amounts returned from the closed position
        to avoid order failures when balance is less than configured total (due to
        impermanent loss, fees, or price movement).

        Side 0 (BOTH): split 50/50
        Side 1 (BUY): all quote - clamp to closed position's quote + quote_fee
        Side 2 (SELL): all base - clamp to closed position's base + base_fee
        """
        total = self.config.total_amount_quote

        # For rebalances, clamp to actual amounts from closed position
        # Check if we have captured amounts (indicates this is a rebalance)
        has_closed_amounts = (self._last_closed_base_amount is not None or
                              self._last_closed_quote_amount is not None)
        if has_closed_amounts:
            if side == 1:  # BUY - needs quote token
                if self._last_closed_quote_amount is not None:
                    # Total available = position amount + fees earned
                    available_quote = self._last_closed_quote_amount
                    if self._last_closed_quote_fee:
                        available_quote += self._last_closed_quote_fee
                    if available_quote < total:
                        self.logger().info(
                            f"Clamping quote amount from {total} to {available_quote} {self._quote_token} "
                            f"(closed position returned {self._last_closed_quote_amount} + {self._last_closed_quote_fee} fees)"
                        )
                        total = available_quote
            elif side == 2:  # SELL - needs base token
                if self._last_closed_base_amount is not None:
                    # Total available = position amount + fees earned
                    available_base = self._last_closed_base_amount
                    if self._last_closed_base_fee:
                        available_base += self._last_closed_base_fee
                    available_as_quote = available_base * current_price
                    if available_as_quote < total:
                        self.logger().info(
                            f"Clamping total from {total} to {available_as_quote:.4f} "
                            f"{self._quote_token} (closed: {self._last_closed_base_amount} + "
                            f"{self._last_closed_base_fee} fees {self._base_token})"
                        )
                        total = available_as_quote

            # Clear the cached amounts after use
            self._last_closed_base_amount = None
            self._last_closed_quote_amount = None
            self._last_closed_base_fee = None
            self._last_closed_quote_fee = None

        if side == 0:  # BOTH
            quote_amt = total / Decimal("2")
            base_amt = quote_amt / current_price
        elif side == 1:  # BUY
            base_amt = Decimal("0")
            quote_amt = total
        else:  # SELL
            base_amt = total / current_price
            quote_amt = Decimal("0")

        return base_amt, quote_amt

    def _calculate_price_bounds(self, side: int, current_price: Decimal) -> tuple:
        """
        Calculate position bounds based on side and price limits.

        Side 0 (BOTH): centered on current price, clamped to [buy_min, sell_max]
        Side 1 (BUY): upper = min(current, buy_price_max) * (1 - offset), lower extends width below
        Side 2 (SELL): lower = max(current, sell_price_min) * (1 + offset), upper extends width above

        The offset ensures single-sided positions start out-of-range so they only
        require one token (SOL for SELL, USDC for BUY).
        """
        width = self.config.position_width_pct / Decimal("100")
        offset = self.config.position_offset_pct / Decimal("100")

        if side == 0:  # BOTH
            half_width = width / Decimal("2")
            lower_price = current_price * (Decimal("1") - half_width)
            upper_price = current_price * (Decimal("1") + half_width)
            # Clamp to limits
            if self.config.buy_price_min:
                lower_price = max(lower_price, self.config.buy_price_min)
            if self.config.sell_price_max:
                upper_price = min(upper_price, self.config.sell_price_max)

        elif side == 1:  # BUY
            # Position BELOW current price so we only need quote token (USDC)
            if self.config.buy_price_max:
                upper_price = min(current_price, self.config.buy_price_max)
            else:
                upper_price = current_price
            # Apply offset to decrease upper bound (ensures out-of-range)
            upper_price = upper_price * (Decimal("1") - offset)
            lower_price = upper_price * (Decimal("1") - width)
            # Clamp lower to floor
            if self.config.buy_price_min:
                lower_price = max(lower_price, self.config.buy_price_min)

        else:  # SELL
            # Position ABOVE current price so we only need base token (SOL)
            if self.config.sell_price_min:
                lower_price = max(current_price, self.config.sell_price_min)
            else:
                lower_price = current_price
            # Apply offset to increase lower bound (ensures out-of-range)
            lower_price = lower_price * (Decimal("1") + offset)
            upper_price = lower_price * (Decimal("1") + width)
            # Clamp upper to ceiling
            if self.config.sell_price_max:
                upper_price = min(upper_price, self.config.sell_price_max)

        return lower_price, upper_price

    def _is_price_within_limits(self, price: Decimal, side: int) -> bool:
        """
        Check if price is within configured limits for the position type.

        Price must be within the range to create a position that's IN_RANGE:
        - BUY: price must be within [buy_price_min, buy_price_max]
        - SELL: price must be within [sell_price_min, sell_price_max]
        - BOTH: price must be within the intersection of both ranges

        If price is outside the range, the position would be immediately OUT_OF_RANGE.
        """
        if side == 2:  # SELL
            if self.config.sell_price_min and price < self.config.sell_price_min:
                return False
            if self.config.sell_price_max and price > self.config.sell_price_max:
                return False
        elif side == 1:  # BUY
            if self.config.buy_price_min and price < self.config.buy_price_min:
                return False
            if self.config.buy_price_max and price > self.config.buy_price_max:
                return False
        else:  # BOTH - must be within intersection of ranges
            # Check buy range
            if self.config.buy_price_min and price < self.config.buy_price_min:
                return False
            if self.config.buy_price_max and price > self.config.buy_price_max:
                return False
            # Check sell range
            if self.config.sell_price_min and price < self.config.sell_price_min:
                return False
            if self.config.sell_price_max and price > self.config.sell_price_max:
                return False
        return True

    async def update_processed_data(self):
        """Called every tick - always fetch fresh pool price for accurate position creation."""
        try:
            connector = self.market_data_provider.get_connector(self.config.connector_name)
            if hasattr(connector, 'get_pool_info_by_address'):
                pool_info = await connector.get_pool_info_by_address(self.config.pool_address)
                if pool_info and pool_info.price:
                    self._pool_price = Decimal(str(pool_info.price))
        except Exception as e:
            self.logger().debug(f"Could not fetch pool price: {e}")

    def to_format_status(self) -> List[str]:
        """Format status for display."""
        status = []
        box_width = 100
        price_decimals = 8  # For small-value tokens like memecoins

        # Header
        status.append("+" + "-" * box_width + "+")
        header = f"| LP Rebalancer: {self.config.trading_pair} on {self.config.connector_name}"
        status.append(header + " " * (box_width - len(header) + 1) + "|")
        status.append("+" + "-" * box_width + "+")

        # Network, connector, pool
        line = f"| Network: {self.config.network}"
        status.append(line + " " * (box_width - len(line) + 1) + "|")

        line = f"| Pool: {self.config.pool_address}"
        status.append(line + " " * (box_width - len(line) + 1) + "|")

        # Position info from current executor (active or transitioning)
        executor = self.active_executor() or self.get_tracked_executor()
        if executor and not executor.is_done:
            position_address = executor.custom_info.get("position_address", "N/A")
            line = f"| Position: {position_address}"
            status.append(line + " " * (box_width - len(line) + 1) + "|")

        # Config summary
        side_names = {0: "BOTH", 1: "BUY", 2: "SELL"}
        side_str = side_names.get(self.config.side, '?')
        amt = self.config.total_amount_quote
        width = self.config.position_width_pct
        rebal = self.config.rebalance_seconds
        line = f"| Config: side={side_str}, amount={amt} {self._quote_token}, width={width}%, rebal={rebal}s"
        status.append(line + " " * (box_width - len(line) + 1) + "|")

        # Position fees and assets
        if executor and not executor.is_done:
            custom = executor.custom_info

            # Fees row: base_fee + quote_fee = total
            base_fee = Decimal(str(custom.get("base_fee", 0)))
            quote_fee = Decimal(str(custom.get("quote_fee", 0)))
            fees_earned_quote = Decimal(str(custom.get("fees_earned_quote", 0)))
            line = (
                f"| Fees: {float(base_fee):.6f} {self._base_token} + "
                f"{float(quote_fee):.6f} {self._quote_token} = {float(fees_earned_quote):.6f}"
            )
            status.append(line + " " * (box_width - len(line) + 1) + "|")

            # Value row: base_amount + quote_amount = total value
            base_amount = Decimal(str(custom.get("base_amount", 0)))
            quote_amount = Decimal(str(custom.get("quote_amount", 0)))
            total_value_quote = Decimal(str(custom.get("total_value_quote", 0)))
            line = (
                f"| Value: {float(base_amount):.6f} {self._base_token} + "
                f"{float(quote_amount):.6f} {self._quote_token} = {float(total_value_quote):.4f}"
            )
            status.append(line + " " * (box_width - len(line) + 1) + "|")

            # Position range visualization
            lower_price = executor.custom_info.get("lower_price")
            upper_price = executor.custom_info.get("upper_price")

            if lower_price and upper_price and self._pool_price:
                # Show rebalance thresholds (convert % to decimal)
                # Takes into account price limits - rebalance only happens within limits
                threshold = self.config.rebalance_threshold_pct / Decimal("100")
                lower_threshold = Decimal(str(lower_price)) * (Decimal("1") - threshold)
                upper_threshold = Decimal(str(upper_price)) * (Decimal("1") + threshold)

                # Lower threshold triggers SELL - check sell_price_min
                if self.config.sell_price_min and lower_threshold < self.config.sell_price_min:
                    lower_str = "N/A"  # Below sell limit, no rebalance possible
                else:
                    lower_str = f"{float(lower_threshold):.{price_decimals}f}"

                # Upper threshold triggers BUY - check buy_price_max
                if self.config.buy_price_max and upper_threshold > self.config.buy_price_max:
                    upper_str = "N/A"  # Above buy limit, no rebalance possible
                else:
                    upper_str = f"{float(upper_threshold):.{price_decimals}f}"

                line = f"| Price: {float(self._pool_price):.{price_decimals}f}  |  Rebalance if: <{lower_str} or >{upper_str}"
                status.append(line + " " * (box_width - len(line) + 1) + "|")

                state = executor.custom_info.get("state", "UNKNOWN")
                state_icons = {
                    "IN_RANGE": "●",
                    "OUT_OF_RANGE": "○",
                    "OPENING": "◐",
                    "CLOSING": "◑",
                    "COMPLETE": "◌",
                    "NOT_ACTIVE": "○",
                }
                state_icon = state_icons.get(state, "?")

                status.append("|" + " " * box_width + "|")
                line = f"| Position Status: [{state_icon} {state}]"
                status.append(line + " " * (box_width - len(line) + 1) + "|")

                range_viz = self._create_price_range_visualization(
                    Decimal(str(lower_price)),
                    self._pool_price,
                    Decimal(str(upper_price))
                )
                for viz_line in range_viz.split('\n'):
                    line = f"| {viz_line}"
                    status.append(line + " " * (box_width - len(line) + 1) + "|")

                # Show rebalance timer if out of range
                out_of_range_seconds = executor.custom_info.get("out_of_range_seconds")
                if out_of_range_seconds is not None:
                    # Check if beyond threshold
                    beyond_threshold = self._is_beyond_rebalance_threshold(executor)
                    if beyond_threshold:
                        line = f"| Rebalance: {out_of_range_seconds}s / {self.config.rebalance_seconds}s"
                    else:
                        line = f"| Rebalance: waiting (below {float(self.config.rebalance_threshold_pct):.2f}% threshold)"
                    status.append(line + " " * (box_width - len(line) + 1) + "|")

        # Price limits visualization
        has_limits = any([
            self.config.sell_price_min, self.config.sell_price_max,
            self.config.buy_price_min, self.config.buy_price_max
        ])
        if has_limits and self._pool_price:
            # Get position bounds if available
            pos_lower = None
            pos_upper = None
            if executor:
                pos_lower = executor.custom_info.get("lower_price")
                pos_upper = executor.custom_info.get("upper_price")
                if pos_lower:
                    pos_lower = Decimal(str(pos_lower))
                if pos_upper:
                    pos_upper = Decimal(str(pos_upper))

            status.append("|" + " " * box_width + "|")
            limits_viz = self._create_price_limits_visualization(
                self._pool_price, pos_lower, pos_upper, price_decimals
            )
            if limits_viz:
                for viz_line in limits_viz.split('\n'):
                    line = f"| {viz_line}"
                    status.append(line + " " * (box_width - len(line) + 1) + "|")

        # Balance comparison table (formatted like main balance table)
        status.append("|" + " " * box_width + "|")
        try:
            current_base = self.market_data_provider.get_balance(
                self.config.connector_name, self._base_token
            )
            current_quote = self.market_data_provider.get_balance(
                self.config.connector_name, self._quote_token
            )

            line = "| Balances:"
            status.append(line + " " * (box_width - len(line) + 1) + "|")

            # Table header
            header = f"|   {'Asset':<12} {'Initial':>14} {'Current':>14} {'Change':>16}"
            status.append(header + " " * (box_width - len(header) + 1) + "|")

            # Base token row
            if self._initial_base_balance is not None:
                base_change = current_base - self._initial_base_balance
                init_b = float(self._initial_base_balance)
                curr_b = float(current_base)
                chg_b = float(base_change)
                line = f"|   {self._base_token:<12} {init_b:>14.6f} {curr_b:>14.6f} {chg_b:>+16.6f}"
            else:
                curr_b = float(current_base)
                line = f"|   {self._base_token:<12} {'N/A':>14} {curr_b:>14.6f} {'N/A':>16}"
            status.append(line + " " * (box_width - len(line) + 1) + "|")

            # Quote token row
            if self._initial_quote_balance is not None:
                quote_change = current_quote - self._initial_quote_balance
                init_q = float(self._initial_quote_balance)
                curr_q = float(current_quote)
                chg_q = float(quote_change)
                line = f"|   {self._quote_token:<12} {init_q:>14.6f} {curr_q:>14.6f} {chg_q:>+16.6f}"
            else:
                curr_q = float(current_quote)
                line = f"|   {self._quote_token:<12} {'N/A':>14} {curr_q:>14.6f} {'N/A':>16}"
            status.append(line + " " * (box_width - len(line) + 1) + "|")
        except Exception as e:
            line = f"| Balances: Error fetching ({e})"
            status.append(line + " " * (box_width - len(line) + 1) + "|")

        # Closed positions summary
        status.append("|" + " " * box_width + "|")

        closed = [e for e in self.executors_info if e.is_done]

        # Count closed by side (config.side: 0=both, 1=buy, 2=sell)
        both_count = len([e for e in closed if getattr(e.config, "side", None) == 0])
        buy_count = len([e for e in closed if getattr(e.config, "side", None) == 1])
        sell_count = len([e for e in closed if getattr(e.config, "side", None) == 2])

        # Calculate fees from closed positions
        total_fees_base = Decimal("0")
        total_fees_quote = Decimal("0")

        for e in closed:
            total_fees_base += Decimal(str(e.custom_info.get("base_fee", 0)))
            total_fees_quote += Decimal(str(e.custom_info.get("quote_fee", 0)))

        pool_price = self._pool_price or Decimal("0")
        total_fees_value = total_fees_base * pool_price + total_fees_quote

        line = f"| Closed: {len(closed)} (both:{both_count} buy:{buy_count} sell:{sell_count})"
        status.append(line + " " * (box_width - len(line) + 1) + "|")
        fb = float(total_fees_base)
        fq = float(total_fees_quote)
        fv = float(total_fees_value)
        line = f"| Fees Collected: {fb:.6f} {self._base_token} + {fq:.6f} {self._quote_token} = {fv:.6f}"
        status.append(line + " " * (box_width - len(line) + 1) + "|")

        status.append("+" + "-" * box_width + "+")
        return status

    def _create_price_range_visualization(self, lower_price: Decimal, current_price: Decimal,
                                          upper_price: Decimal) -> str:
        """Create visual representation of price range with current price marker"""
        price_range = upper_price - lower_price
        if price_range == 0:
            return f"[{float(lower_price):.6f}] (zero width)"

        current_position = (current_price - lower_price) / price_range
        bar_width = 50
        current_pos = int(current_position * bar_width)

        range_bar = ['─'] * bar_width
        range_bar[0] = '├'
        range_bar[-1] = '┤'

        if current_pos < 0:
            marker_line = '● ' + ''.join(range_bar)
        elif current_pos >= bar_width:
            marker_line = ''.join(range_bar) + ' ●'
        else:
            range_bar[current_pos] = '●'
            marker_line = ''.join(range_bar)

        viz_lines = []
        viz_lines.append(marker_line)
        lower_str = f'{float(lower_price):.6f}'
        upper_str = f'{float(upper_price):.6f}'
        viz_lines.append(lower_str + ' ' * (bar_width - len(lower_str) - len(upper_str)) + upper_str)

        return '\n'.join(viz_lines)

    def _create_price_limits_visualization(
        self,
        current_price: Decimal,
        pos_lower: Optional[Decimal] = None,
        pos_upper: Optional[Decimal] = None,
        price_decimals: int = 8
    ) -> Optional[str]:
        """Create visualization of sell/buy price limits on unified scale."""
        viz_lines = []

        bar_width = 50

        # Collect all price points to determine unified scale
        prices = [current_price]
        if self.config.sell_price_min:
            prices.append(self.config.sell_price_min)
        if self.config.sell_price_max:
            prices.append(self.config.sell_price_max)
        if self.config.buy_price_min:
            prices.append(self.config.buy_price_min)
        if self.config.buy_price_max:
            prices.append(self.config.buy_price_max)
        if pos_lower:
            prices.append(pos_lower)
        if pos_upper:
            prices.append(pos_upper)

        scale_min = min(prices)
        scale_max = max(prices)
        scale_range = scale_max - scale_min

        if scale_range <= 0:
            return None

        def pos_to_idx(price: Decimal) -> int:
            return int((price - scale_min) / scale_range * (bar_width - 1))

        # Get position marker index
        price_idx = pos_to_idx(current_price)

        # Helper to create a range bar on unified scale with position marker
        def make_range_bar(range_min: Optional[Decimal], range_max: Optional[Decimal],
                           label: str, fill_char: str = '═', show_position: bool = False) -> str:
            if range_min is None or range_max is None:
                return ""

            bar = [' '] * bar_width
            start_idx = max(0, pos_to_idx(range_min))
            end_idx = min(bar_width - 1, pos_to_idx(range_max))

            # Fill the range
            for i in range(start_idx, end_idx + 1):
                bar[i] = fill_char
            # Mark boundaries
            if 0 <= start_idx < bar_width:
                bar[start_idx] = '['
            if 0 <= end_idx < bar_width:
                bar[end_idx] = ']'

            # Add position marker if requested
            if show_position and 0 <= price_idx < bar_width:
                bar[price_idx] = '●'

            return f"  {label}: {''.join(bar)}"

        # Build visualization with aligned bars
        viz_lines.append("Price Limits:")

        # Create labels with price ranges
        if self.config.sell_price_min and self.config.sell_price_max:
            s_min = float(self.config.sell_price_min)
            s_max = float(self.config.sell_price_max)
            sell_label = f"Sell [{s_min:.{price_decimals}f}-{s_max:.{price_decimals}f}]"
        else:
            sell_label = "Sell"
        if self.config.buy_price_min and self.config.buy_price_max:
            b_min = float(self.config.buy_price_min)
            b_max = float(self.config.buy_price_max)
            buy_label = f"Buy  [{b_min:.{price_decimals}f}-{b_max:.{price_decimals}f}]"
        else:
            buy_label = "Buy "

        # Find max label length for alignment
        max_label_len = max(len(sell_label), len(buy_label))

        # Sell range (with position marker)
        if self.config.sell_price_min and self.config.sell_price_max:
            viz_lines.append(make_range_bar(
                self.config.sell_price_min, self.config.sell_price_max,
                sell_label.ljust(max_label_len), '═', show_position=True
            ))
        else:
            viz_lines.append("  Sell: No limits set")

        # Buy range (with position marker)
        if self.config.buy_price_min and self.config.buy_price_max:
            viz_lines.append(make_range_bar(
                self.config.buy_price_min, self.config.buy_price_max,
                buy_label.ljust(max_label_len), '─', show_position=True
            ))
        else:
            viz_lines.append("  Buy : No limits set")

        # Scale line (aligned with bar start)
        min_str = f'{float(scale_min):.{price_decimals}f}'
        max_str = f'{float(scale_max):.{price_decimals}f}'
        label_padding = max_label_len + 4  # "  " prefix + ": " suffix
        viz_lines.append(f"{' ' * label_padding}{min_str}{' ' * (bar_width - len(min_str) - len(max_str))}{max_str}")

        return '\n'.join(viz_lines)
