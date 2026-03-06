import asyncio
import logging
from decimal import Decimal
from typing import Dict, Optional, Union

from hummingbot.connector.gateway.gateway_lp import AMMPoolInfo, CLMMPoolInfo
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.strategy_v2_base import StrategyV2Base
from hummingbot.strategy_v2.executors.executor_base import ExecutorBase
from hummingbot.strategy_v2.executors.lp_executor.data_types import LPExecutorConfig, LPExecutorState, LPExecutorStates
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType, TrackedOrder


class LPExecutor(ExecutorBase):
    """
    Executor for a single LP position lifecycle.

    - Opens position on start (direct await, no events)
    - Monitors and reports state (IN_RANGE, OUT_OF_RANGE)
    - Tracks out_of_range_since timestamp for rebalancing decisions
    - Closes position when stopped (unless keep_position=True)

    Rebalancing is handled by Controller (stops this executor, creates new one).

    Note: This executor directly awaits gateway operations instead of using
    the fire-and-forget pattern with events. This makes it work in environments
    without the Clock/tick mechanism (like hummingbot-api).
    """
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(
        self,
        strategy: StrategyV2Base,
        config: LPExecutorConfig,
        update_interval: float = 1.0,
        max_retries: int = 10,
    ):
        # Extract connector names from config for ExecutorBase
        connectors = [config.connector_name]
        super().__init__(strategy, connectors, config, update_interval)
        self.config: LPExecutorConfig = config
        self.lp_position_state = LPExecutorState()
        self._pool_info: Optional[Union[CLMMPoolInfo, AMMPoolInfo]] = None
        self._current_price: Optional[Decimal] = None  # Updated from pool_info or position_info
        self._max_retries = max_retries
        self._current_retries = 0
        self._max_retries_reached = False  # True when max retries reached, requires intervention
        self._last_attempted_signature: Optional[str] = None  # Track for retry logging

    async def on_start(self):
        """Start executor - will create position in first control_task"""
        await super().on_start()

    async def control_task(self):
        """Main control loop - simple state machine with direct await operations"""
        current_time = self._strategy.current_timestamp

        # Fetch position info when position exists (includes current price)
        # This avoids redundant pool_info call since position_info has price
        if self.lp_position_state.position_address:
            await self._update_position_info()
        else:
            # Only fetch pool info when no position exists (for price during creation)
            await self.update_pool_info()

        current_price = self._current_price
        self.lp_position_state.update_state(current_price, current_time)

        match self.lp_position_state.state:
            case LPExecutorStates.NOT_ACTIVE:
                # Start opening position
                self.lp_position_state.state = LPExecutorStates.OPENING
                await self._create_position()

            case LPExecutorStates.OPENING:
                # Position creation in progress or retrying after failure
                if not self._max_retries_reached:
                    await self._create_position()
                # If max retries reached, stay in OPENING state waiting for intervention

            case LPExecutorStates.CLOSING:
                # Position close in progress or retrying after failure
                if not self._max_retries_reached:
                    await self._close_position()
                # If max retries reached, stay in CLOSING state waiting for intervention

            case LPExecutorStates.IN_RANGE:
                # Position active and in range - just monitor
                pass

            case LPExecutorStates.OUT_OF_RANGE:
                # Position active but out of range
                # Auto-close if configured and duration exceeded (directional)
                if self._current_price is not None:
                    out_of_range_seconds = self.lp_position_state.get_out_of_range_seconds(current_time)
                    auto_close_seconds = None

                    # Check if price is above range (>= upper_price)
                    if self._current_price >= self.lp_position_state.upper_price:
                        auto_close_seconds = self.config.auto_close_above_range_seconds
                    # Check if price is below range (<= lower_price)
                    elif self._current_price <= self.lp_position_state.lower_price:
                        auto_close_seconds = self.config.auto_close_below_range_seconds

                    if auto_close_seconds is not None and out_of_range_seconds and out_of_range_seconds >= auto_close_seconds:
                        direction = "above" if self._current_price >= self.lp_position_state.upper_price else "below"
                        self.logger().info(
                            f"Position {direction} range for {out_of_range_seconds}s >= {auto_close_seconds}s, closing"
                        )
                        self.close_type = CloseType.EARLY_STOP
                        self.lp_position_state.state = LPExecutorStates.CLOSING

            case LPExecutorStates.COMPLETE:
                # Position closed - close_type already set by early_stop()
                self.stop()

    async def _update_position_info(self):
        """Fetch current position info from connector to update amounts and fees"""
        if not self.lp_position_state.position_address:
            return

        connector = self.connectors.get(self.config.connector_name)
        if connector is None:
            return

        try:
            position_info = await connector.get_position_info(
                trading_pair=self.config.trading_pair,
                position_address=self.lp_position_state.position_address
            )

            if position_info:
                # Update amounts and fees from live position data
                self.lp_position_state.base_amount = Decimal(str(position_info.base_token_amount))
                self.lp_position_state.quote_amount = Decimal(str(position_info.quote_token_amount))
                self.lp_position_state.base_fee = Decimal(str(position_info.base_fee_amount))
                self.lp_position_state.quote_fee = Decimal(str(position_info.quote_fee_amount))
                # Update price bounds from actual position (may differ slightly from config)
                self.lp_position_state.lower_price = Decimal(str(position_info.lower_price))
                self.lp_position_state.upper_price = Decimal(str(position_info.upper_price))
                # Update current price from position_info (avoids separate pool_info call)
                self._current_price = Decimal(str(position_info.price))
            else:
                self.logger().warning(f"get_position_info returned None for {self.lp_position_state.position_address}")
        except Exception as e:
            # Gateway returns HttpError with message patterns:
            # - "Position closed: {addr}" (404) - position was closed on-chain
            # - "Position not found: {addr}" (404) - position never existed
            # - "Position not found or closed: {addr}" (404) - combined check
            error_msg = str(e).lower()
            if "position closed" in error_msg:
                self.logger().info(
                    f"Position {self.lp_position_state.position_address} confirmed closed on-chain"
                )
                self._emit_already_closed_event()
                self.lp_position_state.state = LPExecutorStates.COMPLETE
                self.lp_position_state.active_close_order = None
                return
            elif "not found" in error_msg:
                self.logger().error(
                    f"Position {self.lp_position_state.position_address} not found - "
                    "position may never have been created. Check position tracking."
                )
                return
            self.logger().warning(f"Error fetching position info: {e}")

    async def _create_position(self):
        """
        Create position by directly awaiting the gateway operation.
        No events needed - result is available immediately after await.

        Uses the price bounds provided in config directly.
        """
        connector = self.connectors.get(self.config.connector_name)
        if connector is None:
            self.logger().error(f"Connector {self.config.connector_name} not found")
            return

        # Use config bounds directly
        lower_price = self.config.lower_price
        upper_price = self.config.upper_price
        mid_price = (lower_price + upper_price) / Decimal("2")

        self.logger().info(f"Creating position with bounds: [{lower_price:.6f} - {upper_price:.6f}]")

        # Generate order_id (same as add_liquidity does internally)
        order_id = connector.create_market_order_id(TradeType.RANGE, self.config.trading_pair)
        self.lp_position_state.active_open_order = TrackedOrder(order_id=order_id)

        try:
            # Directly await the async operation instead of fire-and-forget
            self.logger().info(f"Calling gateway to open position with order_id={order_id}")
            signature = await connector._clmm_add_liquidity(
                trade_type=TradeType.RANGE,
                order_id=order_id,
                trading_pair=self.config.trading_pair,
                price=float(mid_price),
                lower_price=float(lower_price),
                upper_price=float(upper_price),
                base_token_amount=float(self.config.base_amount),
                quote_token_amount=float(self.config.quote_amount),
                pool_address=self.config.pool_address,
                extra_params=self.config.extra_params,
            )
            # Note: If operation fails, connector now re-raises the exception
            # so it will be caught by the except block below with the actual error

            self.logger().info(f"Gateway returned signature={signature}")

            # Extract position_address from connector's metadata
            # Gateway response: {"signature": "...", "data": {"positionAddress": "...", ...}}
            metadata = connector._lp_orders_metadata.get(order_id, {})
            position_address = metadata.get("position_address", "")

            if not position_address:
                self.logger().error(f"No position_address in metadata: {metadata}")
                await self._handle_create_failure(ValueError("Position creation failed - no position address in response"))
                return

            # Store position address, rent, and tx_fee from transaction response
            self.lp_position_state.position_address = position_address
            self.lp_position_state.position_rent = metadata.get("position_rent", Decimal("0"))
            self.lp_position_state.tx_fee = metadata.get("tx_fee", Decimal("0"))

            # Position is created - clear open order and reset retries
            self.lp_position_state.active_open_order = None
            self._current_retries = 0

            # Clean up connector metadata
            if order_id in connector._lp_orders_metadata:
                del connector._lp_orders_metadata[order_id]

            # Fetch full position info from chain to get actual amounts and bounds
            position_info = await connector.get_position_info(
                trading_pair=self.config.trading_pair,
                position_address=position_address
            )

            if position_info:
                self.lp_position_state.base_amount = Decimal(str(position_info.base_token_amount))
                self.lp_position_state.quote_amount = Decimal(str(position_info.quote_token_amount))
                self.lp_position_state.lower_price = Decimal(str(position_info.lower_price))
                self.lp_position_state.upper_price = Decimal(str(position_info.upper_price))
                self.lp_position_state.base_fee = Decimal(str(position_info.base_fee_amount))
                self.lp_position_state.quote_fee = Decimal(str(position_info.quote_fee_amount))
                # Store initial amounts for accurate P&L calculation (these don't change as price moves)
                self.lp_position_state.initial_base_amount = self.lp_position_state.base_amount
                self.lp_position_state.initial_quote_amount = self.lp_position_state.quote_amount
                # Use price from position_info (avoids separate pool_info call)
                current_price = Decimal(str(position_info.price))
                self._current_price = current_price
                self.lp_position_state.add_mid_price = current_price
            else:
                # Fallback to config values if position_info fetch failed (e.g., rate limit)
                self.logger().warning("Position info fetch failed, using config values as fallback")
                self.lp_position_state.base_amount = self.config.base_amount
                self.lp_position_state.quote_amount = self.config.quote_amount
                self.lp_position_state.lower_price = lower_price
                self.lp_position_state.upper_price = upper_price
                self.lp_position_state.initial_base_amount = self.config.base_amount
                self.lp_position_state.initial_quote_amount = self.config.quote_amount
                current_price = mid_price
                self._current_price = current_price
                self.lp_position_state.add_mid_price = current_price

            self.logger().info(
                f"Position created: {position_address}, "
                f"rent: {self.lp_position_state.position_rent} SOL, "
                f"base: {self.lp_position_state.base_amount}, quote: {self.lp_position_state.quote_amount}, "
                f"bounds: [{self.lp_position_state.lower_price} - {self.lp_position_state.upper_price}]"
            )

            # Trigger event for database recording (lphistory command)
            # Note: mid_price is the current MARKET price, not the position range midpoint
            # Create trade_fee with tx_fee in native currency for proper tracking
            native_currency = getattr(connector, '_native_currency', 'SOL') or 'SOL'
            trade_fee = TradeFeeBase.new_spot_fee(
                fee_schema=connector.trade_fee_schema(),
                trade_type=TradeType.RANGE,
                flat_fees=[TokenAmount(amount=self.lp_position_state.tx_fee, token=native_currency)]
            )
            connector._trigger_add_liquidity_event(
                order_id=order_id,
                exchange_order_id=signature,
                trading_pair=self.config.trading_pair,
                lower_price=self.lp_position_state.lower_price,
                upper_price=self.lp_position_state.upper_price,
                amount=self.lp_position_state.base_amount + self.lp_position_state.quote_amount / current_price,
                fee_tier=self.config.pool_address,
                creation_timestamp=self._strategy.current_timestamp,
                trade_fee=trade_fee,
                position_address=position_address,
                base_amount=self.lp_position_state.base_amount,
                quote_amount=self.lp_position_state.quote_amount,
                mid_price=current_price,
                position_rent=self.lp_position_state.position_rent,
            )

            # Update state immediately (don't wait for next tick)
            self.lp_position_state.update_state(current_price, self._strategy.current_timestamp)

        except Exception as e:
            # Try to get signature from connector metadata (gateway may have stored it before timeout)
            sig = None
            if connector:
                metadata = connector._lp_orders_metadata.get(order_id, {})
                sig = metadata.get("signature")
            await self._handle_create_failure(e, signature=sig)

    async def _handle_create_failure(self, error: Exception, signature: Optional[str] = None):
        """Handle position creation failure with retry logic."""
        error_str = str(error)
        sig_info = f" [sig: {signature}]" if signature else ""

        # Check if this is a "price moved" error - position bounds need shifting
        is_price_moved = "Price has moved" in error_str or "Position would require" in error_str

        if is_price_moved and self.config.side != 0:
            # Fetch current pool price and shift bounds
            await self._shift_bounds_for_price_move()
            # Don't count as retry - this is a recoverable adjustment
            self.lp_position_state.active_open_order = None
            return

        self._current_retries += 1
        max_retries = self._max_retries

        # Check if this is a timeout error (retryable)
        is_timeout = "TRANSACTION_TIMEOUT" in error_str

        if self._current_retries >= max_retries:
            msg = (
                f"LP OPEN FAILED after {max_retries} retries for {self.config.trading_pair}.{sig_info} "
                f"Manual intervention required. Error: {error}"
            )
            self.logger().error(msg)
            self._strategy.notify_hb_app_with_timestamp(msg)
            self._max_retries_reached = True
            # Keep state as OPENING - don't shut down, wait for user intervention
            self.lp_position_state.active_open_order = None
            return

        if is_timeout:
            self.logger().warning(
                f"LP open timeout (retry {self._current_retries}/{max_retries}).{sig_info} "
                "Chain may be congested. Retrying..."
            )
        else:
            self.logger().warning(
                f"LP open failed (retry {self._current_retries}/{max_retries}): {error}"
            )

        # Clear open order to allow retry - state stays OPENING
        self.lp_position_state.active_open_order = None

    async def _shift_bounds_for_price_move(self):
        """
        Shift position bounds when price moved into range during creation.
        Keeps the same width, shifts by actual price difference to get out of range.
        """
        # Fetch current pool price with retry (may fail due to rate limits)
        for attempt in range(self._max_retries):
            await self.update_pool_info()
            if self._current_price:
                break
            if attempt < self._max_retries - 1:
                self.logger().warning(f"Pool price fetch failed, retry {attempt + 1}/{self._max_retries}...")
                await asyncio.sleep(1)

        if not self._current_price:
            self.logger().warning("Cannot shift bounds - pool price unavailable after retries")
            return

        current_price = self._current_price
        old_lower = self.config.lower_price
        old_upper = self.config.upper_price

        # Use same offset as controller for recovery shift
        offset = self.config.position_offset_pct / Decimal("100")

        # Calculate width_pct from existing bounds (multiplicative, matching controller)
        if self.config.side == 1:  # BUY
            # Controller: lower = upper * (1 - width), so width = 1 - (lower/upper)
            width_pct = Decimal("1") - (old_lower / old_upper) if old_upper > 0 else Decimal("0.005")
            # Same as controller: upper = current * (1 - offset), lower = upper * (1 - width)
            new_upper = current_price * (Decimal("1") - offset)
            new_lower = new_upper * (Decimal("1") - width_pct)
        elif self.config.side == 2:  # SELL
            # Controller: upper = lower * (1 + width), so width = (upper/lower) - 1
            width_pct = (old_upper / old_lower) - Decimal("1") if old_lower > 0 else Decimal("0.005")
            # Same as controller: lower = current * (1 + offset), upper = lower * (1 + width)
            new_lower = current_price * (Decimal("1") + offset)
            new_upper = new_lower * (Decimal("1") + width_pct)
        else:
            return  # Side 0 (BOTH) doesn't need shifting

        # Update config bounds (Pydantic models are mutable)
        self.config.lower_price = new_lower
        self.config.upper_price = new_upper

        self.logger().info(
            f"Price moved - shifting bounds: [{old_lower:.4f}-{old_upper:.4f}] -> "
            f"[{new_lower:.4f}-{new_upper:.4f}] (price: {current_price:.4f}, offset: {offset:.4f})"
        )

    async def _close_position(self):
        """
        Close position by directly awaiting the gateway operation.
        No events needed - result is available immediately after await.
        """
        connector = self.connectors.get(self.config.connector_name)
        if connector is None:
            self.logger().error(f"Connector {self.config.connector_name} not found")
            return

        # Verify position still exists before trying to close (handles timeout-but-succeeded case)
        try:
            position_info = await connector.get_position_info(
                trading_pair=self.config.trading_pair,
                position_address=self.lp_position_state.position_address
            )
            if position_info is None:
                self.logger().info(
                    f"Position {self.lp_position_state.position_address} already closed - skipping close"
                )
                self._emit_already_closed_event()
                self.lp_position_state.state = LPExecutorStates.COMPLETE
                return
        except Exception as e:
            # Gateway returns HttpError with message patterns (see _update_position_info)
            error_msg = str(e).lower()
            if "position closed" in error_msg:
                self.logger().info(
                    f"Position {self.lp_position_state.position_address} already closed - skipping"
                )
                self._emit_already_closed_event()
                self.lp_position_state.state = LPExecutorStates.COMPLETE
                return
            elif "not found" in error_msg:
                self.logger().error(
                    f"Position {self.lp_position_state.position_address} not found - "
                    "marking complete to avoid retry loop"
                )
                self._emit_already_closed_event()
                self.lp_position_state.state = LPExecutorStates.COMPLETE
                return
            # Other errors - proceed with close attempt

        # Generate order_id for tracking
        order_id = connector.create_market_order_id(TradeType.RANGE, self.config.trading_pair)
        self.lp_position_state.active_close_order = TrackedOrder(order_id=order_id)

        try:
            # Directly await the async operation
            signature = await connector._clmm_close_position(
                trade_type=TradeType.RANGE,
                order_id=order_id,
                trading_pair=self.config.trading_pair,
                position_address=self.lp_position_state.position_address,
            )
            # Note: If operation fails, connector now re-raises the exception
            # so it will be caught by the except block below with the actual error

            self.logger().info(f"Position close confirmed, signature={signature}")

            # Success - extract close data from connector's metadata
            metadata = connector._lp_orders_metadata.get(order_id, {})
            self.lp_position_state.position_rent_refunded = metadata.get("position_rent_refunded", Decimal("0"))
            self.lp_position_state.base_amount = metadata.get("base_amount", Decimal("0"))
            self.lp_position_state.quote_amount = metadata.get("quote_amount", Decimal("0"))
            self.lp_position_state.base_fee = metadata.get("base_fee", Decimal("0"))
            self.lp_position_state.quote_fee = metadata.get("quote_fee", Decimal("0"))
            # Add close tx_fee to cumulative total (open tx_fee + close tx_fee)
            close_tx_fee = metadata.get("tx_fee", Decimal("0"))
            self.lp_position_state.tx_fee += close_tx_fee

            # Clean up connector metadata
            if order_id in connector._lp_orders_metadata:
                del connector._lp_orders_metadata[order_id]

            self.logger().info(
                f"Position closed: {self.lp_position_state.position_address}, "
                f"rent refunded: {self.lp_position_state.position_rent_refunded} SOL, "
                f"base: {self.lp_position_state.base_amount}, quote: {self.lp_position_state.quote_amount}, "
                f"fees: {self.lp_position_state.base_fee} base / {self.lp_position_state.quote_fee} quote"
            )

            # Trigger event for database recording (lphistory command)
            # Note: mid_price is the current MARKET price, not the position range midpoint
            current_price = Decimal(str(self._pool_info.price)) if self._pool_info else Decimal("0")
            # Create trade_fee with close tx_fee in native currency for proper tracking
            native_currency = getattr(connector, '_native_currency', 'SOL') or 'SOL'
            trade_fee = TradeFeeBase.new_spot_fee(
                fee_schema=connector.trade_fee_schema(),
                trade_type=TradeType.RANGE,
                flat_fees=[TokenAmount(amount=close_tx_fee, token=native_currency)]
            )
            connector._trigger_remove_liquidity_event(
                order_id=order_id,
                exchange_order_id=signature,
                trading_pair=self.config.trading_pair,
                token_id="0",
                creation_timestamp=self._strategy.current_timestamp,
                trade_fee=trade_fee,
                position_address=self.lp_position_state.position_address,
                lower_price=self.lp_position_state.lower_price,
                upper_price=self.lp_position_state.upper_price,
                mid_price=current_price,
                base_amount=self.lp_position_state.base_amount,
                quote_amount=self.lp_position_state.quote_amount,
                base_fee=self.lp_position_state.base_fee,
                quote_fee=self.lp_position_state.quote_fee,
                position_rent_refunded=self.lp_position_state.position_rent_refunded,
            )

            self.lp_position_state.active_close_order = None
            self.lp_position_state.position_address = None
            self.lp_position_state.state = LPExecutorStates.COMPLETE
            self._current_retries = 0

        except Exception as e:
            # Try to get signature from connector metadata (gateway may have stored it before timeout)
            sig = None
            if connector:
                metadata = connector._lp_orders_metadata.get(order_id, {})
                sig = metadata.get("signature")
            self._handle_close_failure(e, signature=sig)

    def _handle_close_failure(self, error: Exception, signature: Optional[str] = None):
        """Handle position close failure with retry logic."""
        self._current_retries += 1
        max_retries = self._max_retries

        # Check if this is a timeout error (retryable)
        error_str = str(error)
        is_timeout = "TRANSACTION_TIMEOUT" in error_str

        # Format signature for logging
        sig_info = f" [sig: {signature}]" if signature else ""

        if self._current_retries >= max_retries:
            msg = (
                f"LP CLOSE FAILED after {max_retries} retries for {self.config.trading_pair}.{sig_info} "
                f"Position {self.lp_position_state.position_address} may need manual close. Error: {error}"
            )
            self.logger().error(msg)
            self._strategy.notify_hb_app_with_timestamp(msg)
            self._max_retries_reached = True
            # Keep state as CLOSING - don't shut down, wait for user intervention
            self.lp_position_state.active_close_order = None
            return

        if is_timeout:
            self.logger().warning(
                f"LP close timeout (retry {self._current_retries}/{max_retries}).{sig_info} "
                "Chain may be congested. Retrying..."
            )
        else:
            self.logger().warning(
                f"LP close failed (retry {self._current_retries}/{max_retries}): {error}"
            )

        # Clear active order - state stays CLOSING for retry in next control_task
        self.lp_position_state.active_close_order = None

    def _emit_already_closed_event(self):
        """
        Emit a synthetic RangePositionLiquidityRemovedEvent for positions that were
        closed on-chain but we didn't receive the confirmation (e.g., timeout-but-succeeded).
        Uses last known position data. This ensures the database is updated.
        """
        connector = self.connectors.get(self.config.connector_name)
        if connector is None:
            return

        # Generate a synthetic order_id for this event
        order_id = connector.create_market_order_id(TradeType.RANGE, self.config.trading_pair)
        # Note: mid_price is the current MARKET price, not the position range midpoint
        current_price = Decimal(str(self._pool_info.price)) if self._pool_info else Decimal("0")

        self.logger().info(
            f"Emitting synthetic close event for already-closed position: "
            f"{self.lp_position_state.position_address}, "
            f"base: {self.lp_position_state.base_amount}, quote: {self.lp_position_state.quote_amount}, "
            f"fees: {self.lp_position_state.base_fee} base / {self.lp_position_state.quote_fee} quote"
        )

        # For synthetic events, we don't have the actual close tx_fee, so use 0
        native_currency = getattr(connector, '_native_currency', 'SOL') or 'SOL'
        trade_fee = TradeFeeBase.new_spot_fee(
            fee_schema=connector.trade_fee_schema(),
            trade_type=TradeType.RANGE,
            flat_fees=[TokenAmount(amount=Decimal("0"), token=native_currency)]
        )
        connector._trigger_remove_liquidity_event(
            order_id=order_id,
            exchange_order_id="already-closed",
            trading_pair=self.config.trading_pair,
            token_id="0",
            creation_timestamp=self._strategy.current_timestamp,
            trade_fee=trade_fee,
            position_address=self.lp_position_state.position_address,
            lower_price=self.lp_position_state.lower_price,
            upper_price=self.lp_position_state.upper_price,
            mid_price=current_price,
            base_amount=self.lp_position_state.base_amount,
            quote_amount=self.lp_position_state.quote_amount,
            base_fee=self.lp_position_state.base_fee,
            quote_fee=self.lp_position_state.quote_fee,
            position_rent_refunded=self.lp_position_state.position_rent,
        )

    def early_stop(self, keep_position: bool = False):
        """Stop executor - transitions to CLOSING state, control_task handles the close"""
        self._status = RunnableStatus.SHUTTING_DOWN
        self.close_type = CloseType.POSITION_HOLD if keep_position or self.config.keep_position else CloseType.EARLY_STOP

        # Transition to CLOSING state if we have a position and not keeping it
        if not keep_position and not self.config.keep_position:
            if self.lp_position_state.state in [LPExecutorStates.IN_RANGE, LPExecutorStates.OUT_OF_RANGE]:
                self.lp_position_state.state = LPExecutorStates.CLOSING
            elif self.lp_position_state.state == LPExecutorStates.NOT_ACTIVE:
                # No position was created, just complete
                self.lp_position_state.state = LPExecutorStates.COMPLETE

    def _get_quote_to_global_rate(self) -> Decimal:
        """
        Get conversion rate from pool quote currency to USDT.

        For pools like COIN-SOL, the quote is SOL. This method returns the
        SOL-USDT rate to convert values to USD for consistent P&L reporting.

        Returns Decimal("1") if rate is not available.
        """
        _, quote_token = split_hb_trading_pair(self.config.trading_pair)

        try:
            rate = RateOracle.get_instance().get_pair_rate(f"{quote_token}-USDT")
            if rate is not None and rate > 0:
                return rate
        except Exception as e:
            self.logger().debug(f"Could not get rate for {quote_token}-USDT: {e}")

        return Decimal("1")  # Fallback to no conversion

    def _get_native_to_quote_rate(self) -> Decimal:
        """
        Get conversion rate from native currency (SOL) to pool quote currency.

        Used to convert transaction fees (paid in native currency) to quote.

        Returns Decimal("1") if rate is not available.
        """
        connector = self.connectors.get(self.config.connector_name)
        native_currency = getattr(connector, '_native_currency', 'SOL') or 'SOL'
        _, quote_token = split_hb_trading_pair(self.config.trading_pair)

        # If native currency is the quote token, no conversion needed
        if native_currency == quote_token:
            return Decimal("1")

        try:
            rate = RateOracle.get_instance().get_pair_rate(f"{native_currency}-{quote_token}")
            if rate is not None and rate > 0:
                return rate
        except Exception as e:
            self.logger().debug(f"Could not get rate for {native_currency}-{quote_token}: {e}")

        return Decimal("1")  # Fallback to no conversion

    @property
    def filled_amount_quote(self) -> Decimal:
        """Returns initial investment value in global token (USD).

        For LP positions, this represents the capital deployed (initial deposit),
        NOT the current position value. This ensures volume_traded in performance
        reports reflects actual trading activity, not price fluctuations.

        Uses stored initial amounts valued at deposit time price.
        """
        # Use stored add_mid_price, fall back to current price if not set
        add_price = self.lp_position_state.add_mid_price
        if add_price <= 0:
            add_price = self._current_price if self._current_price else Decimal("0")

        if add_price == 0:
            return Decimal("0")

        # Use stored initial amounts (actual deposited), fall back to config if not set
        initial_base = (self.lp_position_state.initial_base_amount
                        if self.lp_position_state.initial_base_amount > 0
                        else self.config.base_amount)
        initial_quote = (self.lp_position_state.initial_quote_amount
                         if self.lp_position_state.initial_quote_amount > 0
                         else self.config.quote_amount)

        # Initial investment value in pool quote currency
        initial_value = initial_base * add_price + initial_quote

        # Convert to global token (USD)
        return initial_value * self._get_quote_to_global_rate()

    def get_custom_info(self) -> Dict:
        """Report LP position state to controller"""
        price_float = float(self._current_price) if self._current_price else 0.0
        current_time = self._strategy.current_timestamp

        # Calculate total value in quote
        total_value = (
            float(self.lp_position_state.base_amount) * price_float +
            float(self.lp_position_state.quote_amount)
        )

        # Calculate fees earned in quote
        fees_earned = (
            float(self.lp_position_state.base_fee) * price_float +
            float(self.lp_position_state.quote_fee)
        )

        return {
            "side": self.config.side,
            "state": self.lp_position_state.state.value,
            "position_address": self.lp_position_state.position_address,
            "current_price": price_float if self._current_price else None,
            "lower_price": float(self.lp_position_state.lower_price),
            "upper_price": float(self.lp_position_state.upper_price),
            "base_amount": float(self.lp_position_state.base_amount),
            "quote_amount": float(self.lp_position_state.quote_amount),
            "base_fee": float(self.lp_position_state.base_fee),
            "quote_fee": float(self.lp_position_state.quote_fee),
            "fees_earned_quote": fees_earned,
            "total_value_quote": total_value,
            "unrealized_pnl_quote": float(self.get_net_pnl_quote()),
            "position_rent": float(self.lp_position_state.position_rent),
            "position_rent_refunded": float(self.lp_position_state.position_rent_refunded),
            "tx_fee": float(self.lp_position_state.tx_fee),
            "out_of_range_seconds": self.lp_position_state.get_out_of_range_seconds(current_time),
            "max_retries_reached": self._max_retries_reached,
            # Initial amounts (actual deposited) for inventory tracking; fall back to config if not set
            "initial_base_amount": float(self.lp_position_state.initial_base_amount
                                         if self.lp_position_state.initial_base_amount > 0
                                         else self.config.base_amount),
            "initial_quote_amount": float(self.lp_position_state.initial_quote_amount
                                          if self.lp_position_state.initial_quote_amount > 0
                                          else self.config.quote_amount),
        }

    # Required abstract methods from ExecutorBase
    async def validate_sufficient_balance(self):
        """Validate sufficient balance for LP position. ExecutorBase calls this in on_start()."""
        # LP connector handles balance validation during add_liquidity
        pass

    def get_net_pnl_quote(self) -> Decimal:
        """
        Returns net P&L in global token (USD).

        P&L = (current_position_value + fees_earned) - initial_value

        Calculates P&L in pool quote currency, then converts to global token
        for consistent reporting across different pools. Uses stored initial
        amounts and add_mid_price for accurate calculation matching lphistory.
        Works for both open positions and closed positions (using final returned amounts).
        """
        if self._current_price is None or self._current_price == 0:
            return Decimal("0")
        current_price = self._current_price

        # Use stored add_mid_price for initial value, fall back to current price if not set
        add_price = self.lp_position_state.add_mid_price if self.lp_position_state.add_mid_price > 0 else current_price

        # Use stored initial amounts (actual deposited), fall back to config if not set
        initial_base = (self.lp_position_state.initial_base_amount
                        if self.lp_position_state.initial_base_amount > 0
                        else self.config.base_amount)
        initial_quote = (self.lp_position_state.initial_quote_amount
                         if self.lp_position_state.initial_quote_amount > 0
                         else self.config.quote_amount)

        # Initial value (actual deposited amounts, valued at ADD time price)
        initial_value = initial_base * add_price + initial_quote

        # Current position value (tokens in position, valued at current price)
        current_value = (
            self.lp_position_state.base_amount * current_price +
            self.lp_position_state.quote_amount
        )

        # Fees earned (LP swap fees, not transaction costs)
        fees_earned = (
            self.lp_position_state.base_fee * current_price +
            self.lp_position_state.quote_fee
        )

        # P&L in pool quote currency (before tx fees)
        pnl_in_quote = current_value + fees_earned - initial_value

        # Subtract transaction fees (tx_fee is in native currency, convert to quote)
        tx_fee_quote = self.lp_position_state.tx_fee * self._get_native_to_quote_rate()
        net_pnl_quote = pnl_in_quote - tx_fee_quote

        # Convert to global token (USD)
        return net_pnl_quote * self._get_quote_to_global_rate()

    def get_net_pnl_pct(self) -> Decimal:
        """Returns net P&L as percentage of initial investment.

        Both P&L and initial value are converted to global token (USD) for
        consistent percentage calculation across different pools.
        """
        pnl_global = self.get_net_pnl_quote()  # Already in global token (USD)
        if pnl_global == Decimal("0"):
            return Decimal("0")

        if self._current_price is None or self._current_price == 0:
            return Decimal("0")
        current_price = self._current_price

        # Use stored add_mid_price for initial value to match get_net_pnl_quote()
        add_price = self.lp_position_state.add_mid_price if self.lp_position_state.add_mid_price > 0 else current_price

        # Use stored initial amounts (actual deposited), fall back to config if not set
        initial_base = (self.lp_position_state.initial_base_amount
                        if self.lp_position_state.initial_base_amount > 0
                        else self.config.base_amount)
        initial_quote = (self.lp_position_state.initial_quote_amount
                         if self.lp_position_state.initial_quote_amount > 0
                         else self.config.quote_amount)

        # Initial value in pool quote currency
        initial_value_quote = initial_base * add_price + initial_quote

        if initial_value_quote == Decimal("0"):
            return Decimal("0")

        # Convert to global token (USD) for consistent percentage
        initial_value_global = initial_value_quote * self._get_quote_to_global_rate()

        return (pnl_global / initial_value_global) * Decimal("100")

    def get_cum_fees_quote(self) -> Decimal:
        """
        Returns cumulative transaction costs in quote currency.

        NOTE: This is for transaction/gas costs, NOT LP fees earned.
        LP fees earned are included in get_net_pnl_quote() calculation.
        Transaction fees are paid in native currency (SOL) and converted to quote.
        """
        return self.lp_position_state.tx_fee * self._get_native_to_quote_rate()

    async def update_pool_info(self):
        """Fetch and store current pool info"""
        connector = self.connectors.get(self.config.connector_name)
        if connector is None:
            return

        try:
            self._pool_info = await connector.get_pool_info_by_address(self.config.pool_address)
            if self._pool_info:
                self._current_price = Decimal(str(self._pool_info.price))
        except Exception as e:
            self.logger().warning(f"Error fetching pool info: {e}")
