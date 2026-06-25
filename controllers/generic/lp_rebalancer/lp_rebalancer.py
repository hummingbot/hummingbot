import logging
from decimal import Decimal
from typing import List, Optional

from pydantic import Field, field_validator, model_validator

from hummingbot.core.data_type.common import MarketDict, TradeType
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.executors.gateway_utils import parse_provider
from hummingbot.strategy_v2.executors.lp_executor.data_types import LPExecutorConfig
from hummingbot.strategy_v2.executors.order_executor.data_types import ExecutionStrategy, OrderExecutorConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction
from hummingbot.strategy_v2.models.executors import CloseType
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


class LPRebalancerConfig(ControllerConfigBase):
    """
    Configuration for LP Rebalancer Controller.

    This controller uses LP executor's upper_limit_price/lower_limit_price feature
    to automatically close positions when price exceeds thresholds, eliminating
    manual rebalancing monitoring.

    Key features:
    - No rebalance_seconds timer - uses rebalance_threshold_pct to set executor limit prices
    - LP executor auto-closes when price exceeds limits
    - Controller just monitors for completion and re-opens if within price bounds
    - Uses keep_position=True - controller handles position tracking via position_hold

    Provider Architecture:
    - connector_name: The network identifier (e.g., "solana-mainnet-beta")
    - lp_provider: LP provider in format "dex/trading_type" (e.g., "meteora/clmm")
    - autoswap uses network's configured swapProvider (via Gateway)
    """
    controller_type: str = "generic"
    controller_name: str = "lp_rebalancer"
    candles_config: List[CandlesConfig] = []

    # Network connector - e.g., "solana-mainnet-beta"
    connector_name: str = "solana-mainnet-beta"

    # LP provider (required) - format: "dex/trading_type"
    # Examples: "meteora/clmm", "orca/clmm", "raydium/clmm"
    lp_provider: str = "orca/clmm"

    # Pool configuration (required)
    trading_pair: str
    pool_address: str

    # Position parameters
    total_amount_quote: Decimal = Field(default=Decimal("50"), json_schema_extra={"is_updatable": True})
    side: TradeType = Field(default=TradeType.BUY, json_schema_extra={"is_updatable": True})  # BUY, SELL, or RANGE
    position_width_pct: Decimal = Field(default=Decimal("0.5"), json_schema_extra={"is_updatable": True})
    position_offset_pct: Decimal = Field(
        default=Decimal("0.01"),
        json_schema_extra={"is_updatable": True},
        description="Offset from current price. Positive = out-of-range (single-sided). Negative = in-range (needs both tokens, autoswap will convert |offset|%)"
    )

    # Rebalance threshold - used to set LP executor's limit prices
    # When price moves this % beyond position bounds, executor auto-closes
    rebalance_threshold_pct: Decimal = Field(
        default=Decimal("1"),
        json_schema_extra={"is_updatable": True},
        description="Price threshold % beyond position bounds that triggers auto-close (e.g., 1 = 1%)"
    )

    # Price limits - controller-level limits for deciding whether to re-open
    # Sell range: [sell_price_min, sell_price_max]
    # Buy range: [buy_price_min, buy_price_max]
    sell_price_max: Optional[Decimal] = Field(default=None, json_schema_extra={"is_updatable": True})
    sell_price_min: Optional[Decimal] = Field(default=None, json_schema_extra={"is_updatable": True})
    buy_price_max: Optional[Decimal] = Field(default=None, json_schema_extra={"is_updatable": True})
    buy_price_min: Optional[Decimal] = Field(default=None, json_schema_extra={"is_updatable": True})

    # Connector-specific params (optional)
    strategy_type: Optional[int] = Field(default=None, json_schema_extra={"is_updatable": True})

    # Auto-swap feature: swap tokens if balance insufficient for position
    autoswap: bool = Field(
        default=False,
        json_schema_extra={"is_updatable": True},
        description="Automatically swap tokens if balance is insufficient for position. Uses network's swapProvider."
    )
    swap_buffer_pct: Decimal = Field(
        default=Decimal("0.01"),
        json_schema_extra={"is_updatable": True},
        description="Extra % to swap beyond deficit to account for slippage (e.g., 0.01 = 0.01%)"
    )

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
        """Validate and convert side to TradeType enum."""
        if isinstance(v, TradeType):
            return v
        if isinstance(v, str):
            v = v.upper()
            if v in ("BUY", "1"):
                return TradeType.BUY
            elif v in ("SELL", "2"):
                return TradeType.SELL
            elif v in ("RANGE", "3"):
                return TradeType.RANGE
            raise ValueError(f"Invalid side '{v}'. Must be BUY, SELL, or RANGE")
        if isinstance(v, int):
            if v == 1:
                return TradeType.BUY
            elif v == 2:
                return TradeType.SELL
            elif v == 3:
                return TradeType.RANGE
            raise ValueError(f"Invalid side {v}. Must be 1 (BUY), 2 (SELL), or 3 (RANGE)")
        raise ValueError(f"Invalid side type {type(v)}. Must be TradeType, str, or int")

    @model_validator(mode="after")
    def validate_price_limit_ranges(self):
        """Validate that price limit ranges are valid."""
        if self.buy_price_max is not None and self.buy_price_min is not None:
            if self.buy_price_max < self.buy_price_min:
                raise ValueError("buy_price_max must be >= buy_price_min")
        if self.sell_price_max is not None and self.sell_price_min is not None:
            if self.sell_price_max < self.sell_price_min:
                raise ValueError("sell_price_max must be >= sell_price_min")
        # For negative offset (in-range), offset magnitude must not exceed width
        if self.position_offset_pct < 0:
            if abs(self.position_offset_pct) > self.position_width_pct:
                raise ValueError(
                    f"For in-range positions, |position_offset_pct| ({abs(self.position_offset_pct)}) "
                    f"must not exceed position_width_pct ({self.position_width_pct})"
                )
        return self

    def update_markets(self, markets: MarketDict) -> MarketDict:
        """Register the LP connector with trading pair"""
        markets = markets.add_or_update(self.connector_name, self.trading_pair)
        return markets


class LPRebalancer(ControllerBase):
    """
    Controller for LP position management using executor-level auto-close.

    Key features:
    - Uses LP executor's upper_limit_price/lower_limit_price for auto-closing
    - No manual rebalancing timer - executor handles position close
    - Controller monitors for completion and re-opens within price limits
    - Uses keep_position=True for position tracking via position_hold
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

        # Parse lp_provider into dex_name and trading_type for gateway calls
        self.lp_dex_name, self.lp_trading_type = parse_provider(
            config.lp_provider, default_trading_type="clmm"
        )

        # Parse token symbols from trading pair
        parts = config.trading_pair.split("-")
        self._base_token: str = parts[0] if len(parts) >= 2 else ""
        self._quote_token: str = parts[1] if len(parts) >= 2 else ""

        # Track the executor we created
        self._current_executor_id: Optional[str] = None

        # Track amounts from last closed position (for autoswap sizing)
        self._last_closed_base_amount: Optional[Decimal] = None
        self._last_closed_quote_amount: Optional[Decimal] = None
        self._last_closed_base_fee: Optional[Decimal] = None
        self._last_closed_quote_fee: Optional[Decimal] = None

        # Track initial balances for comparison (wallet balance at controller start)
        self._initial_base_balance: Optional[Decimal] = None
        self._initial_quote_balance: Optional[Decimal] = None

        # Position hold: cumulative net position from closed LP executors
        # Tracks net change = (returned + fees) - initial_deposited
        self._position_hold_base: Decimal = Decimal("0")
        self._position_hold_quote: Decimal = Decimal("0")

        # Flag to trigger balance update after position creation
        self._pending_balance_update: bool = False

        # Cached pool price (updated in update_processed_data)
        self._pool_price: Optional[Decimal] = None

        # Order executor tracking (for autoswap feature)
        self._swap_executor_id: Optional[str] = None
        self._pending_swap_side: Optional[TradeType] = None  # LP side to create after swap completes

        # Track if initial position has been created (after that, always use side 1 or 2)
        self._initial_position_created: bool = False

        # Initialize rate sources
        self.market_data_provider.initialize_rate_sources([
            ConnectorPair(
                connector_name=self.config.connector_name,
                trading_pair=self.config.trading_pair
            )
        ])

    def active_executor(self) -> Optional[ExecutorInfo]:
        """Get current active LP executor (should be 0 or 1)"""
        active = [e for e in self.executors_info
                  if e.is_active and getattr(e.config, "type", None) == "lp_executor"]
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

    def get_swap_executor(self) -> Optional[ExecutorInfo]:
        """Get the order executor we're tracking for autoswap"""
        if not self._swap_executor_id:
            return None
        for e in self.executors_info:
            if e.id == self._swap_executor_id:
                return e
        return None

    def is_swap_executor_done(self) -> bool:
        """Check if order executor has completed (success or failure)"""
        if not self._swap_executor_id:
            return True
        swap_executor = self.get_swap_executor()
        if swap_executor is None:
            return True
        return swap_executor.is_done

    def _check_autoswap_needed(self, side: TradeType, current_price: Decimal) -> Optional[OrderExecutorConfig]:
        """
        Check if autoswap is needed and return order config if so.

        Returns OrderExecutorConfig if swap is needed, None otherwise.
        Uses network's configured swapProvider via Gateway connector.
        """
        if not self.config.autoswap:
            return None

        # Capture closed position amounts BEFORE creating LP position
        closed_base = self._last_closed_base_amount or Decimal("0")
        closed_quote = self._last_closed_quote_amount or Decimal("0")
        closed_base_fee = self._last_closed_base_fee or Decimal("0")
        closed_quote_fee = self._last_closed_quote_fee or Decimal("0")

        # Calculate required amounts
        base_amt, quote_amt = self._calculate_amounts(side, current_price)

        # Get current wallet balances
        try:
            base_balance = self.market_data_provider.get_balance(
                self.config.connector_name, self._base_token
            )
            quote_balance = self.market_data_provider.get_balance(
                self.config.connector_name, self._quote_token
            )
        except Exception as e:
            self.logger().warning(f"Could not fetch balances for autoswap check: {e}")
            return None

        # For rebalances, add closed position amounts to available balance
        if closed_base > 0 or closed_quote > 0:
            base_balance += closed_base + closed_base_fee
            quote_balance += closed_quote + closed_quote_fee
            self.logger().info(
                f"Autoswap: including closed position amounts in balance: "
                f"+{closed_base + closed_base_fee:.6f} {self._base_token}, "
                f"+{closed_quote + closed_quote_fee:.6f} {self._quote_token}"
            )

        # Calculate deficit from raw amounts
        base_deficit = base_amt - base_balance
        quote_deficit = quote_amt - quote_balance

        # Add native currency buffer for rent and transaction fees when native currency is involved
        # Get native currency and buffer from connector (chain-specific values)
        connector = self.market_data_provider.get_connector(self.config.connector_name)
        native_currency = (getattr(connector, 'native_currency', None) or "").upper()
        native_buffer = getattr(connector, 'get_native_currency_buffer', lambda: Decimal("0.005"))()
        if native_currency and self._base_token.upper() == native_currency:
            base_deficit += native_buffer
        if native_currency and self._quote_token.upper() == native_currency:
            quote_deficit += native_buffer

        self.logger().info(
            f"Autoswap check: need base={base_amt:.6f}, have={base_balance:.6f}, deficit={base_deficit:.6f} | "
            f"need quote={quote_amt:.6f}, have={quote_balance:.6f}, deficit={quote_deficit:.6f}"
        )

        # Buffer multiplier only applied to swap amount
        buffer_multiplier = Decimal("1") + (self.config.swap_buffer_pct / Decimal("100"))

        # If any deficit, swap
        if base_deficit > 0 and quote_deficit <= 0:
            # Need more base, have enough quote - BUY base with quote
            swap_amount = base_deficit * buffer_multiplier
            required_quote = swap_amount * current_price * Decimal("1.02")
            if quote_balance >= required_quote:
                self.logger().info(
                    f"Autoswap: BUY {swap_amount:.6f} {self._base_token} "
                    f"(deficit={base_deficit:.6f} + {self.config.swap_buffer_pct}% buffer)"
                )
                return OrderExecutorConfig(
                    timestamp=self.market_data_provider.time(),
                    connector_name=self.config.connector_name,
                    trading_pair=self.config.trading_pair,
                    side=TradeType.BUY,
                    amount=swap_amount,
                    execution_strategy=ExecutionStrategy.MARKET,
                )
            else:
                self.logger().warning(
                    f"Autoswap: insufficient quote ({quote_balance:.6f}) to buy {swap_amount:.6f} base"
                )
                return None

        elif quote_deficit > 0 and base_deficit <= 0:
            # Need more quote, have enough base - SELL base for quote
            swap_amount = (quote_deficit / current_price) * buffer_multiplier
            if base_balance >= swap_amount * Decimal("1.02"):
                self.logger().info(
                    f"Autoswap: SELL {swap_amount:.6f} {self._base_token} for ~{quote_deficit:.6f} {self._quote_token}"
                )
                return OrderExecutorConfig(
                    timestamp=self.market_data_provider.time(),
                    connector_name=self.config.connector_name,
                    trading_pair=self.config.trading_pair,
                    side=TradeType.SELL,
                    amount=swap_amount,
                    execution_strategy=ExecutionStrategy.MARKET,
                )
            else:
                self.logger().warning(
                    f"Autoswap: insufficient base ({base_balance:.6f}) to sell for {quote_deficit:.6f} quote"
                )
                return None

        elif base_deficit > 0 and quote_deficit > 0:
            total_deficit_quote = base_deficit * current_price + quote_deficit
            self.logger().warning(
                f"Autoswap: cannot swap - both tokens in deficit (side=RANGE). "
                f"Total deficit: {total_deficit_quote:.2f} {self._quote_token}"
            )
            return None

        # No swap needed
        return None

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
        """
        Decide whether to create executors.

        Simplified logic:
        - No active executor: check if we should create one (price within limits)
        - Active executor: just wait for it to auto-close via limit prices
        - No manual OUT_OF_RANGE monitoring or timer logic needed
        """
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

        # Handle order executor tracking and completion (for autoswap)
        if self._pending_swap_side is not None:
            if not self._swap_executor_id:
                for e in self.executors_info:
                    if e.config.type == "order_executor" and e.is_active:
                        self._swap_executor_id = e.id
                        self.logger().info(f"Tracking order executor for swap: {e.id}")
                        break

            if not self._swap_executor_id:
                self.logger().debug("Waiting for order executor to appear in executors_info")
                return actions

        if self._swap_executor_id:
            if not self.is_swap_executor_done():
                swap_executor = self.get_swap_executor()
                self.logger().debug("Waiting for order executor to complete swap")
                return actions

            # Order executor completed
            swap_executor = self.get_swap_executor()
            pending_side = self._pending_swap_side

            # Clear swap tracking
            self._swap_executor_id = None
            self._pending_swap_side = None

            # Check if swap succeeded (not FAILED close type)
            swap_succeeded = swap_executor and swap_executor.close_type != CloseType.FAILED
            if swap_succeeded:
                self.logger().info("Autoswap completed successfully, proceeding to LP position")
                self._trigger_balance_update()

                # Update position_hold with swap's inventory change
                if swap_executor:
                    custom = swap_executor.custom_info
                    swap_side = custom.get("side")  # TradeType enum or string
                    swap_side_str = swap_side.name if hasattr(swap_side, 'name') else str(swap_side)
                    executed_amount = Decimal(str(custom.get("executed_amount_base", 0)))
                    executed_price = Decimal(str(custom.get("average_executed_price", 0)))
                    quote_amount = executed_amount * executed_price

                    if swap_side_str == "BUY":
                        # BUY swap: gained base, spent quote
                        self._position_hold_base += executed_amount
                        self._position_hold_quote -= quote_amount
                    else:
                        # SELL swap: spent base, gained quote
                        self._position_hold_base -= executed_amount
                        self._position_hold_quote += quote_amount

                    self.logger().info(
                        f"Swap {swap_side_str} {executed_amount:.6f} {self._base_token} @ {executed_price:.4f}. "
                        f"Position hold: base={self._position_hold_base:+.6f}, quote={self._position_hold_quote:+.6f}"
                    )

                if pending_side is not None:
                    executor_config = self._create_executor_config(pending_side)
                    if executor_config:
                        actions.append(CreateExecutorAction(
                            controller_id=self.config.id,
                            executor_config=executor_config
                        ))
                        self._initial_position_created = True
                        self._pending_balance_update = True
            else:
                close_type = swap_executor.close_type if swap_executor else "unknown"
                self.logger().error(
                    f"Autoswap FAILED (close_type: {close_type}). Will retry on next cycle."
                )

            return actions

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

            # Previous executor terminated - capture final amounts and update position_hold
            terminated_executor = self.get_tracked_executor()
            if terminated_executor:
                # Skip position_hold update if executor failed (no tokens were actually deposited/returned)
                if terminated_executor.close_type == CloseType.FAILED:
                    self.logger().warning(
                        f"Executor {terminated_executor.id} FAILED - skipping position_hold update"
                    )
                else:
                    self._last_closed_base_amount = Decimal(str(terminated_executor.custom_info.get("base_amount", 0)))
                    self._last_closed_quote_amount = Decimal(str(terminated_executor.custom_info.get("quote_amount", 0)))
                    self._last_closed_base_fee = Decimal(str(terminated_executor.custom_info.get("base_fee", 0)))
                    self._last_closed_quote_fee = Decimal(str(terminated_executor.custom_info.get("quote_fee", 0)))

                    # Get initial amounts deposited
                    initial_base = Decimal(str(terminated_executor.custom_info.get("initial_base_amount", 0)))
                    initial_quote = Decimal(str(terminated_executor.custom_info.get("initial_quote_amount", 0)))

                    # Update position_hold with NET change from this executor
                    # Net = (returned + fees) - initial_deposited
                    base_net = (self._last_closed_base_amount + self._last_closed_base_fee) - initial_base
                    quote_net = (self._last_closed_quote_amount + self._last_closed_quote_fee) - initial_quote
                    self._position_hold_base += base_net
                    self._position_hold_quote += quote_net

                    self.logger().info(
                        f"Executor completed. Initial: base={initial_base}, quote={initial_quote}. "
                        f"Returned: base={self._last_closed_base_amount}+{self._last_closed_base_fee}, "
                        f"quote={self._last_closed_quote_amount}+{self._last_closed_quote_fee}. "
                        f"Net change: base={base_net:+}, quote={quote_net:+}. "
                        f"Position hold total: base={self._position_hold_base}, quote={self._position_hold_quote}"
                    )

            # Check if executor FAILED - retry with same side from executor's config
            executor_failed = terminated_executor and terminated_executor.close_type == CloseType.FAILED
            failed_executor_side = None
            if executor_failed:
                failed_executor_side = terminated_executor.custom_info.get("side")

            # Capture closed position bounds for side determination (only for successful closes)
            closed_lower_price = None
            closed_upper_price = None
            if terminated_executor and not executor_failed:
                closed_lower_price = Decimal(str(terminated_executor.custom_info.get("lower_price", 0)))
                closed_upper_price = Decimal(str(terminated_executor.custom_info.get("upper_price", 0)))

            # Clear tracking
            self._current_executor_id = None

            # Determine side for new position
            if executor_failed and failed_executor_side is not None:
                # Retry with same side on failure
                side = failed_executor_side
                self.logger().info(f"Retrying with same side={side} after executor failure")
            elif not self._initial_position_created:
                # Initial position: use configured side
                side = self.config.side
            elif closed_lower_price and closed_upper_price and self._pool_price:
                # After position close: determine side from price direction relative to closed bounds
                # If price >= upper_price: price went UP → BUY (use USDC we got)
                # If price < lower_price: price went DOWN → SELL (use SOL we got)
                if self._pool_price >= closed_upper_price:
                    side = TradeType.BUY  # price above range
                    self.logger().info(f"Price {self._pool_price} >= upper {closed_upper_price} → side=BUY")
                elif self._pool_price < closed_lower_price:
                    side = TradeType.SELL  # price below range
                    self.logger().info(f"Price {self._pool_price} < lower {closed_lower_price} → side=SELL")
                else:
                    # Price is within old bounds (shouldn't happen with limit-price auto-close)
                    side = self._determine_side_from_price(self._pool_price)
                    self.logger().info(f"Price {self._pool_price} in range [{closed_lower_price}, {closed_upper_price}] → side={side} from limits")
            else:
                # Fallback to price limits
                if not self._pool_price:
                    self.logger().info("Waiting for pool price to determine side")
                    return actions
                side = self._determine_side_from_price(self._pool_price)

            # Check if price is within limits before creating position
            if self._pool_price and not self._is_price_within_limits(self._pool_price, side):
                self.logger().debug(f"Price {self._pool_price} outside limits for side={side}, waiting")
                return actions

            # Check if autoswap is needed before creating LP position
            if self.config.autoswap:
                if not self._pool_price:
                    self.logger().info("Autoswap: waiting for pool price")
                    return actions
                swap_config = self._check_autoswap_needed(side, self._pool_price)
                if swap_config:
                    self._pending_swap_side = side
                    actions.append(CreateExecutorAction(
                        controller_id=self.config.id,
                        executor_config=swap_config
                    ))
                    return actions
                else:
                    self.logger().info("Autoswap: no swap needed, balances sufficient")

            # Create executor config with limit prices
            executor_config = self._create_executor_config(side)
            if executor_config is None:
                self.logger().warning("Skipping position creation - invalid bounds")
                return actions

            actions.append(CreateExecutorAction(
                controller_id=self.config.id,
                executor_config=executor_config
            ))
            self._initial_position_created = True
            self._pending_balance_update = True

            # Clear closed position amounts after LP position is created
            self._last_closed_base_amount = None
            self._last_closed_quote_amount = None
            self._last_closed_base_fee = None
            self._last_closed_quote_fee = None

            return actions

        # Active executor exists - trigger balance update when position becomes active
        if self._pending_balance_update:
            state = executor.custom_info.get("state")
            if state in ("IN_RANGE", "OUT_OF_RANGE"):
                self._pending_balance_update = False
                self._trigger_balance_update()

        # No action needed - executor will auto-close via limit prices
        return actions

    def _create_executor_config(self, side: TradeType) -> Optional[LPExecutorConfig]:
        """
        Create executor config with limit prices for auto-close.

        Sets upper_limit_price and lower_limit_price based on rebalance_threshold_pct.
        """
        current_price = self._pool_price
        if current_price is None or current_price == 0:
            self.logger().warning("No pool price available - waiting for update_processed_data")
            return None

        # Calculate position bounds for requested side
        lower_price, upper_price = self._calculate_price_bounds(side, current_price)

        # Check bounds against price limits - clamp if one exceeds, try opposite if both exceed
        lower_price, upper_price, side = self._validate_and_clamp_bounds(
            lower_price, upper_price, side, current_price
        )
        if lower_price is None:
            return None

        # Validate bounds after clamping
        if lower_price >= upper_price:
            self.logger().warning(f"Invalid bounds [{lower_price}, {upper_price}] - skipping")
            return None

        # Calculate amounts based on final side
        base_amt, quote_amt = self._calculate_amounts(side, current_price)

        # Calculate limit prices for auto-close
        threshold = self.config.rebalance_threshold_pct / Decimal("100")
        upper_limit_price = upper_price * (Decimal("1") + threshold)
        lower_limit_price = lower_price * (Decimal("1") - threshold)

        # Build extra params (connector-specific)
        extra_params = {}
        if self.config.strategy_type is not None:
            extra_params["strategyType"] = self.config.strategy_type

        self.logger().info(
            f"Creating position: side={side.name}, pool_price={current_price:.6f}, "
            f"bounds=[{lower_price:.6f}, {upper_price:.6f}], "
            f"limits=[{lower_limit_price:.6f}, {upper_limit_price:.6f}], "
            f"base={base_amt:.6f}, quote={quote_amt:.6f}"
        )

        return LPExecutorConfig(
            timestamp=self.market_data_provider.time(),
            connector_name=self.config.connector_name,
            lp_provider=self.config.lp_provider,
            trading_pair=self.config.trading_pair,
            pool_address=self.config.pool_address,
            lower_price=lower_price,
            upper_price=upper_price,
            base_amount=base_amt,
            quote_amount=quote_amt,
            side=side,
            extra_params=extra_params if extra_params else None,
            # Key difference: set limit prices for auto-close
            upper_limit_price=upper_limit_price,
            lower_limit_price=lower_limit_price,
            # Use keep_position=True - controller handles position tracking
            keep_position=True,
        )

    def _calculate_amounts(self, side: TradeType, current_price: Decimal) -> tuple:
        """
        Calculate base and quote amounts based on side, offset, and total_amount_quote.
        """
        total = self.config.total_amount_quote
        offset = self.config.position_offset_pct

        if side == TradeType.RANGE:
            quote_amt = total / Decimal("2")
            base_amt = quote_amt / current_price
        elif offset >= 0:
            # Out-of-range: single-sided allocation
            if side == TradeType.BUY:  # BUY - all quote
                base_amt = Decimal("0")
                quote_amt = total
            else:  # SELL - all base
                base_amt = total / current_price
                quote_amt = Decimal("0")
        else:
            # In-range (offset < 0): proportional split
            lower_price, upper_price = self._calculate_price_bounds(side, current_price)
            price_range = upper_price - lower_price

            if price_range <= 0 or current_price <= lower_price:
                if side == TradeType.BUY:
                    base_amt = Decimal("0")
                    quote_amt = total
                else:
                    base_amt = total / current_price
                    quote_amt = Decimal("0")
            elif current_price >= upper_price:
                if side == TradeType.SELL:
                    base_amt = total / current_price
                    quote_amt = Decimal("0")
                else:
                    base_amt = Decimal("0")
                    quote_amt = total
            else:
                price_ratio = (current_price - lower_price) / price_range
                quote_pct = price_ratio
                base_pct = Decimal("1") - price_ratio
                quote_amt = total * quote_pct
                base_amt = (total * base_pct) / current_price

        return base_amt, quote_amt

    def _calculate_price_bounds(self, side: TradeType, current_price: Decimal) -> tuple:
        """
        Calculate position bounds based on side and price limits.
        """
        width = self.config.position_width_pct / Decimal("100")
        offset = self.config.position_offset_pct / Decimal("100")

        if side == TradeType.RANGE:
            # Centered on current price
            half_width = width / Decimal("2")
            lower_price = current_price * (Decimal("1") - half_width)
            upper_price = current_price * (Decimal("1") + half_width)

        elif side == TradeType.BUY:
            # Anchor at buy_price_max if set, otherwise at current price
            if self.config.buy_price_max:
                upper_price = min(current_price, self.config.buy_price_max)
            else:
                upper_price = current_price
            upper_price = upper_price * (Decimal("1") - offset)
            lower_price = upper_price * (Decimal("1") - width)

        else:  # SELL
            # Anchor at sell_price_min if set, otherwise at current price
            if self.config.sell_price_min:
                lower_price = max(current_price, self.config.sell_price_min)
            else:
                lower_price = current_price
            lower_price = lower_price * (Decimal("1") + offset)
            upper_price = lower_price * (Decimal("1") + width)

        return lower_price, upper_price

    def _is_price_within_limits(self, price: Decimal, side: TradeType) -> bool:
        """
        Check if price is within configured limits for the position type.
        """
        if side == TradeType.SELL:
            if self.config.sell_price_min and price < self.config.sell_price_min:
                return False
            if self.config.sell_price_max and price > self.config.sell_price_max:
                return False
        elif side == TradeType.BUY:
            if self.config.buy_price_min and price < self.config.buy_price_min:
                return False
            if self.config.buy_price_max and price > self.config.buy_price_max:
                return False
        else:  # RANGE
            if self.config.buy_price_min and price < self.config.buy_price_min:
                return False
            if self.config.buy_price_max and price > self.config.buy_price_max:
                return False
            if self.config.sell_price_min and price < self.config.sell_price_min:
                return False
            if self.config.sell_price_max and price > self.config.sell_price_max:
                return False
        return True

    def _validate_and_clamp_bounds(
        self, lower_price: Decimal, upper_price: Decimal, side: TradeType, current_price: Decimal
    ) -> tuple:
        """
        Validate bounds against price limits. Clamp if one bound exceeds, try opposite side if both exceed.

        Returns: (lower_price, upper_price, side) or (None, None, None) if no valid position possible.

        Note: RANGE positions skip price limit checks entirely.
        """
        # RANGE positions skip price limit checks
        if side == TradeType.RANGE:
            return lower_price, upper_price, side

        # Get limits for this side
        if side == TradeType.BUY:
            min_limit = self.config.buy_price_min
            max_limit = self.config.buy_price_max
        else:  # SELL
            min_limit = self.config.sell_price_min
            max_limit = self.config.sell_price_max

        # Check how many bounds exceed limits
        lower_exceeds = min_limit and lower_price < min_limit
        upper_exceeds = max_limit and upper_price > max_limit

        if not lower_exceeds and not upper_exceeds:
            # Both bounds within limits
            return lower_price, upper_price, side

        if lower_exceeds and upper_exceeds:
            # Both bounds exceed - try opposite side
            opposite_side = TradeType.SELL if side == TradeType.BUY else TradeType.BUY
            opp_lower, opp_upper = self._calculate_price_bounds(opposite_side, current_price)

            # Check opposite side limits
            if opposite_side == TradeType.BUY:
                opp_min = self.config.buy_price_min
                opp_max = self.config.buy_price_max
            else:
                opp_min = self.config.sell_price_min
                opp_max = self.config.sell_price_max

            opp_lower_exceeds = opp_min and opp_lower < opp_min
            opp_upper_exceeds = opp_max and opp_upper > opp_max

            if not opp_lower_exceeds and not opp_upper_exceeds:
                self.logger().info(f"Side {side.name} out of limits, using {opposite_side.name}")
                return opp_lower, opp_upper, opposite_side
            elif opp_lower_exceeds and not opp_upper_exceeds:
                # Clamp lower on opposite side
                self.logger().info(f"Side {side.name} out of limits, using {opposite_side.name} (clamped lower)")
                return opp_min, opp_upper, opposite_side
            elif not opp_lower_exceeds and opp_upper_exceeds:
                # Clamp upper on opposite side
                self.logger().info(f"Side {side.name} out of limits, using {opposite_side.name} (clamped upper)")
                return opp_lower, opp_max, opposite_side
            else:
                # Both sides completely out of limits
                self.logger().info("Both sides out of price limits - waiting")
                return None, None, None

        # Only one bound exceeds - clamp it
        if lower_exceeds:
            self.logger().debug(f"Clamping lower from {lower_price} to {min_limit}")
            return min_limit, upper_price, side
        else:  # upper_exceeds
            self.logger().debug(f"Clamping upper from {upper_price} to {max_limit}")
            return lower_price, max_limit, side

    def _determine_side_from_price(self, current_price: Decimal) -> TradeType:
        """
        Determine side (BUY or SELL) based on current price vs price limits.
        """
        buy_mid = None
        sell_mid = None

        if self.config.buy_price_min and self.config.buy_price_max:
            buy_mid = (self.config.buy_price_min + self.config.buy_price_max) / 2
        if self.config.sell_price_min and self.config.sell_price_max:
            sell_mid = (self.config.sell_price_min + self.config.sell_price_max) / 2

        if buy_mid and sell_mid:
            if current_price <= buy_mid:
                return TradeType.BUY
            elif current_price >= sell_mid:
                return TradeType.SELL
            else:
                return TradeType.BUY if (current_price - buy_mid) < (sell_mid - current_price) else TradeType.SELL

        if buy_mid:
            return TradeType.BUY
        if sell_mid:
            return TradeType.SELL

        return TradeType.BUY  # Default to BUY

    async def update_processed_data(self):
        """Called every tick - fetch pool price."""
        try:
            connector = self.market_data_provider.get_connector(self.config.connector_name)
            if hasattr(connector, 'get_pool_info_by_address'):
                pool_info = await connector.get_pool_info_by_address(
                    self.config.pool_address,
                    dex_name=self.lp_dex_name,
                    trading_type=self.lp_trading_type,
                )
                if pool_info and pool_info.price:
                    self._pool_price = Decimal(str(pool_info.price))
        except Exception as e:
            self.logger().debug(f"Could not fetch pool price: {e}")

    def to_format_status(self) -> List[str]:
        """Format status for display."""
        status = []
        box_width = 100
        price_decimals = 6

        # Header
        status.append("+" + "-" * box_width + "+")
        header = f"| LP Rebalancer: {self.config.trading_pair} on {self.config.connector_name}"
        status.append(header + " " * (box_width - len(header) + 1) + "|")
        status.append("+" + "-" * box_width + "+")

        # Config summary
        line = f"| Network: {self.config.connector_name} | LP: {self.config.lp_provider}"
        status.append(line + " " * (box_width - len(line) + 1) + "|")

        line = f"| Pool: {self.config.pool_address}"
        status.append(line + " " * (box_width - len(line) + 1) + "|")

        side_str = self.config.side.name
        amt = self.config.total_amount_quote
        width = self.config.position_width_pct
        offset = self.config.position_offset_pct
        threshold = self.config.rebalance_threshold_pct
        line = f"| Config: side={side_str}, amount={amt} {self._quote_token}, width={width}%, offset={offset}%, threshold={threshold}%"
        status.append(line + " " * (box_width - len(line) + 1) + "|")

        status.append("|" + " " * box_width + "|")

        # Position section
        executor = self.active_executor() or self.get_tracked_executor()
        pos_base_amount = Decimal("0")
        pos_quote_amount = Decimal("0")

        if executor and not executor.is_done:
            custom = executor.custom_info

            position_address = custom.get("position_address", "N/A")
            line = f"| Position: {position_address}"
            status.append(line + " " * (box_width - len(line) + 1) + "|")

            pos_base_amount = Decimal(str(custom.get("base_amount", 0)))
            pos_quote_amount = Decimal(str(custom.get("quote_amount", 0)))
            total_value_quote = Decimal(str(custom.get("total_value_quote", 0)))
            line = (
                f"| Assets: {float(pos_base_amount):.6f} {self._base_token} + "
                f"{float(pos_quote_amount):.6f} {self._quote_token} = {float(total_value_quote):.4f} {self._quote_token}"
            )
            status.append(line + " " * (box_width - len(line) + 1) + "|")

            base_fee = Decimal(str(custom.get("base_fee", 0)))
            quote_fee = Decimal(str(custom.get("quote_fee", 0)))
            fees_earned_quote = Decimal(str(custom.get("fees_earned_quote", 0)))
            line = (
                f"| Fees: {float(base_fee):.6f} {self._base_token} + "
                f"{float(quote_fee):.6f} {self._quote_token} = {float(fees_earned_quote):.6f} {self._quote_token}"
            )
            status.append(line + " " * (box_width - len(line) + 1) + "|")

            lower_price = custom.get("lower_price")
            upper_price = custom.get("upper_price")

            if lower_price is not None and upper_price is not None and self._pool_price:
                # Show limit prices (auto-close thresholds)
                threshold_pct = self.config.rebalance_threshold_pct / Decimal("100")
                lower_limit = Decimal(str(lower_price)) * (Decimal("1") - threshold_pct)
                upper_limit = Decimal(str(upper_price)) * (Decimal("1") + threshold_pct)

                line = f"| Price: {float(self._pool_price):.{price_decimals}f}  |  Auto-close if: <{float(lower_limit):.{price_decimals}f} or >{float(upper_limit):.{price_decimals}f}"
                status.append(line + " " * (box_width - len(line) + 1) + "|")

                state = custom.get("state", "UNKNOWN")
                state_icons = {
                    "IN_RANGE": "[in]",
                    "OUT_OF_RANGE": "[out]",
                    "OPENING": "[...]",
                    "CLOSING": "[x]",
                    "COMPLETE": "[done]",
                    "NOT_ACTIVE": "[-]",
                }
                state_icon = state_icons.get(state, "[?]")

                status.append("|" + " " * box_width + "|")
                line = f"| Status: {state_icon} {state}"
                status.append(line + " " * (box_width - len(line) + 1) + "|")

                # Range visualization
                range_viz = self._create_price_range_visualization(
                    Decimal(str(lower_price)),
                    self._pool_price,
                    Decimal(str(upper_price)),
                    lower_limit,
                    upper_limit
                )
                for viz_line in range_viz.split('\n'):
                    line = f"| {viz_line}"
                    status.append(line + " " * (box_width - len(line) + 1) + "|")
        else:
            line = "| Position: None"
            status.append(line + " " * (box_width - len(line) + 1) + "|")

        # Price limits visualization
        has_limits = any([
            self.config.sell_price_min, self.config.sell_price_max,
            self.config.buy_price_min, self.config.buy_price_max
        ])
        if has_limits and self._pool_price:
            pos_lower = None
            pos_upper = None
            if executor and not executor.is_done:
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

        # Closed positions summary
        status.append("|" + " " * box_width + "|")
        closed_lp = [e for e in self.executors_info
                     if e.is_done and getattr(e.config, "type", None) == "lp_executor"]
        closed_swaps = [e for e in self.executors_info
                        if e.is_done and getattr(e.config, "type", None) == "order_executor"]

        buy_count = len([e for e in closed_lp if getattr(e.config, "side", None) == TradeType.BUY])
        sell_count = len([e for e in closed_lp if getattr(e.config, "side", None) == TradeType.SELL])
        range_count = len([e for e in closed_lp if getattr(e.config, "side", None) == TradeType.RANGE])

        total_fees_base = Decimal("0")
        total_fees_quote = Decimal("0")
        for e in closed_lp:
            total_fees_base += Decimal(str(e.custom_info.get("base_fee", 0)))
            total_fees_quote += Decimal(str(e.custom_info.get("quote_fee", 0)))

        pool_price = self._pool_price or Decimal("0")
        total_fees_value = total_fees_base * pool_price + total_fees_quote

        line = f"| Closed Positions: {len(closed_lp)} (buy:{buy_count} sell:{sell_count} range:{range_count})"
        status.append(line + " " * (box_width - len(line) + 1) + "|")

        if closed_swaps:
            line = f"| Swaps Executed: {len(closed_swaps)}"
            status.append(line + " " * (box_width - len(line) + 1) + "|")

        line = f"| Fees Collected: {float(total_fees_base):.6f} {self._base_token} + {float(total_fees_quote):.6f} {self._quote_token} = {float(total_fees_value):.6f} {self._quote_token}"
        status.append(line + " " * (box_width - len(line) + 1) + "|")

        status.append("+" + "-" * box_width + "+")
        return status

    def _create_price_range_visualization(self, lower_price: Decimal, current_price: Decimal,
                                          upper_price: Decimal, lower_limit: Decimal,
                                          upper_limit: Decimal) -> str:
        """
        Create visual representation of price range with current price marker.

        Shows: R for rebalance limits, | for position limits, * for current price
        Example: R----|---*--------------------------------|----R
        """
        total_range = upper_limit - lower_limit
        if total_range == 0:
            return f"[{float(lower_price):.6f}] (zero width)"

        bar_width = 50

        def price_to_pos(price: Decimal) -> int:
            return int(((price - lower_limit) / total_range) * bar_width)

        # Calculate positions
        lower_pos = price_to_pos(lower_price)
        upper_pos = price_to_pos(upper_price)
        current_pos = price_to_pos(current_price)

        # Build bar (R at edges for rebalance limits)
        range_bar = ['-'] * bar_width
        range_bar[0] = 'R'
        range_bar[-1] = 'R'

        # Place position limits (|)
        if 0 < lower_pos < bar_width:
            range_bar[lower_pos] = '|'
        if 0 < upper_pos < bar_width:
            range_bar[upper_pos] = '|'

        # Place current price marker (*)
        if current_pos < 0:
            marker_line = '* ' + ''.join(range_bar)
        elif current_pos >= bar_width:
            marker_line = ''.join(range_bar) + ' *'
        else:
            range_bar[current_pos] = '*'
            marker_line = ''.join(range_bar)

        viz_lines = []
        viz_lines.append(marker_line)

        # Price labels: show all four prices
        lower_limit_str = f'{float(lower_limit):.6f}'
        lower_str = f'{float(lower_price):.6f}'
        upper_str = f'{float(upper_price):.6f}'
        upper_limit_str = f'{float(upper_limit):.6f}'

        # Build price label line with proper spacing
        label_line = lower_limit_str
        spacing1 = max(1, lower_pos - len(lower_limit_str))
        label_line += ' ' * spacing1 + lower_str
        spacing2 = max(1, upper_pos - lower_pos - len(lower_str))
        label_line += ' ' * spacing2 + upper_str
        spacing3 = max(1, bar_width - upper_pos - len(upper_str))
        label_line += ' ' * spacing3 + upper_limit_str

        viz_lines.append(label_line)

        return '\n'.join(viz_lines)

    def _create_price_limits_visualization(
        self,
        current_price: Decimal,
        pos_lower: Optional[Decimal] = None,
        pos_upper: Optional[Decimal] = None,
        price_decimals: int = 6
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
