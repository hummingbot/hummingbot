import logging
from decimal import Decimal
from typing import Dict, List, Optional, Union

from hummingbot.connector.gateway.gateway import AMMPoolInfo, CLMMPoolInfo
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.event.events import RangePositionLiquidityAddedEvent, RangePositionLiquidityRemovedEvent
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.strategy_v2_base import StrategyV2Base
from hummingbot.strategy_v2.executors.executor_base import ExecutorBase
from hummingbot.strategy_v2.executors.gateway_utils import parse_provider, validate_and_normalize_connector
from hummingbot.strategy_v2.executors.lp_executor.data_types import LPExecutorConfig, LPExecutorState, LPExecutorStates
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType, TrackedOrder

# Default native currency fallback when connector doesn't have _native_currency set
DEFAULT_NATIVE_CURRENCY = "SOL"


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
        self._max_retries = max_retries
        self.lp_position_state = LPExecutorState()
        self._pool_info: Optional[Union[CLMMPoolInfo, AMMPoolInfo]] = None
        self._current_price: Optional[Decimal] = None  # Updated from pool_info or position_info
        # Position tracking - store LP position for position aggregation when keep_position=True
        self._held_position_orders: List[Dict] = []
        # Swap tracking for close-out flow
        self._swap_not_found_count: int = 0
        # Parse lp_provider into dex_name and trading_type for gateway calls
        self.lp_dex_name, self.lp_trading_type = parse_provider(
            config.lp_provider, default_trading_type="clmm"
        )

    def _validate_and_normalize_connector(self, connector_name: str) -> Optional[str]:
        """
        Validate and normalize connector name for LP executor.

        - If connector already has /clmm suffix, validates it exists
        - If connector is base name only (e.g., "meteora"), auto-appends /clmm
        - Uses GATEWAY_DEXS list populated at gateway startup

        Args:
            connector_name: Connector name from config

        Returns:
            Normalized connector name, or None if validation failed (executor stopped)
        """
        normalized, success = validate_and_normalize_connector(
            connector_name, "clmm", self.logger().error
        )
        if not success:
            self.close_type = CloseType.FAILED
            self.stop()
            return None
        return normalized

    async def on_start(self):
        """Start executor - resolves providers and creates position."""
        await super().on_start()

        # Log LP provider info
        self.logger().info(
            f"Using LP provider: {self.config.lp_provider} "
            f"(dex={self.lp_dex_name}, type={self.lp_trading_type})"
        )

        # Resolve swap_provider from network default if not provided and keep_position=False
        # (needed for close-out swaps when returning to original quote asset)
        if not self.config.keep_position and not self.config.swap_provider:
            gateway = GatewayHttpClient.get_instance()
            default_provider = await gateway.get_default_swap_provider(self.config.connector_name)
            if default_provider:
                self.config = self.config.model_copy(update={'swap_provider': default_provider})
                self.logger().info(f"Using network default swap provider: {default_provider}")
            else:
                self.logger().warning(
                    f"No swap provider found for {self.config.connector_name}. "
                    "Close-out swaps will not be available."
                )

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
                # Position creation in progress - connector handles retry
                # If we're still in OPENING state, the previous attempt failed
                # and we should retry (connector will handle max retries)
                await self._create_position()

            case LPExecutorStates.CLOSING:
                # Position close in progress - connector handles retry
                # If we're still in CLOSING state, the previous attempt failed
                # and we should retry (connector will handle max retries)
                await self._close_position()

            case LPExecutorStates.SWAPPING:
                # Close-out swap in progress (keep_position=False)
                # Similar to grid executor placing close order to rebalance
                await self._execute_closeout_swap()

            case LPExecutorStates.FAILED:
                # Max retries reached - stop executor with failure
                self.close_type = CloseType.FAILED
                self.stop()

            case LPExecutorStates.IN_RANGE:
                # Position active and in range - just monitor
                pass

            case LPExecutorStates.OUT_OF_RANGE:
                # Position active but out of range
                # Close if price exceeds limit prices (like grid executor)
                if self._current_price is not None:
                    should_close = False
                    direction = ""

                    # Check if price exceeded upper limit
                    if self.config.upper_limit_price is not None and self._current_price >= self.config.upper_limit_price:
                        should_close = True
                        direction = "above upper limit"
                    # Check if price exceeded lower limit
                    elif self.config.lower_limit_price is not None and self._current_price <= self.config.lower_limit_price:
                        should_close = True
                        direction = "below lower limit"

                    if should_close:
                        self.logger().info(
                            f"Price {self._current_price} {direction} "
                            f"(upper_limit={self.config.upper_limit_price}, lower_limit={self.config.lower_limit_price}), closing"
                        )
                        # Respect keep_position config - use POSITION_HOLD to track net position, EARLY_STOP otherwise
                        self.close_type = CloseType.POSITION_HOLD if self.config.keep_position else CloseType.EARLY_STOP
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
                dex_name=self.lp_dex_name,
                trading_type=self.lp_trading_type,
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
            self._handle_create_failure(ValueError(f"Connector {self.config.connector_name} not found"))
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
            # Directly await the async operation - connector handles retry for timeouts
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
                max_retries=self._max_retries,
                dex_name=self.lp_dex_name,
                trading_type=self.lp_trading_type,
            )
            # Note: If operation fails after all retries, connector re-raises the exception
            # so it will be caught by the except block below

            self.logger().info(f"Gateway returned signature={signature}")

            # Extract position_address from connector's metadata
            # Gateway response: {"signature": "...", "data": {"positionAddress": "...", ...}}
            metadata = connector._lp_orders_metadata.get(order_id, {})
            position_address = metadata.get("position_address", "")

            if not position_address:
                self.logger().error(f"No position_address in metadata: {metadata}")
                self._handle_create_failure(ValueError("Position creation failed - no position address in response"))
                return

            # Store position address, rent, tx_fee, and transaction hash from response
            self.lp_position_state.position_address = position_address
            self.lp_position_state.position_rent = metadata.get("position_rent", Decimal("0"))
            self.lp_position_state.tx_fee = metadata.get("tx_fee", Decimal("0"))
            self.lp_position_state.open_tx_hash = signature

            # Position is created - clear open order
            self.lp_position_state.active_open_order = None

            # Clean up connector metadata
            if order_id in connector._lp_orders_metadata:
                del connector._lp_orders_metadata[order_id]

            # Fetch full position info from chain to get actual amounts and bounds
            position_info = await connector.get_position_info(
                trading_pair=self.config.trading_pair,
                dex_name=self.lp_dex_name,
                trading_type=self.lp_trading_type,
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
            native_currency = getattr(connector, '_native_currency', DEFAULT_NATIVE_CURRENCY) or DEFAULT_NATIVE_CURRENCY
            trade_fee = TradeFeeBase.new_spot_fee(
                fee_schema=connector.trade_fee_schema(),
                trade_type=TradeType.RANGE,
                flat_fees=[TokenAmount(amount=self.lp_position_state.tx_fee, token=native_currency)]
            )
            event = connector._trigger_add_liquidity_event(
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

            # Store ADD event for position tracking (like spot grid stores orders)
            if self.config.keep_position:
                self._store_lp_event_from_add(event)

            # Update state immediately (don't wait for next tick)
            self.lp_position_state.update_state(current_price, self._strategy.current_timestamp)

        except Exception as e:
            self._handle_create_failure(e)

    def _handle_create_failure(self, error: Exception):
        """Handle position creation failure - transition to FAILED state."""
        self.logger().error(f"Position creation failed: {error}")
        self.lp_position_state.active_open_order = None
        self.lp_position_state.state = LPExecutorStates.FAILED

    async def _close_position(self):
        """
        Close position by directly awaiting the gateway operation.
        No events needed - result is available immediately after await.
        """
        connector = self.connectors.get(self.config.connector_name)
        if connector is None:
            self.logger().error(f"Connector {self.config.connector_name} not found")
            self._handle_close_failure(ValueError(f"Connector {self.config.connector_name} not found"))
            return

        # Verify position still exists before trying to close (handles timeout-but-succeeded case)
        try:
            position_info = await connector.get_position_info(
                trading_pair=self.config.trading_pair,
                dex_name=self.lp_dex_name,
                trading_type=self.lp_trading_type,
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
            # Directly await the async operation - connector handles retry for timeouts
            signature = await connector._clmm_close_position(
                trade_type=TradeType.RANGE,
                order_id=order_id,
                trading_pair=self.config.trading_pair,
                position_address=self.lp_position_state.position_address,
                max_retries=self._max_retries,
                dex_name=self.lp_dex_name,
                trading_type=self.lp_trading_type,
            )
            # Note: If operation fails after all retries, connector re-raises the exception
            # so it will be caught by the except block below

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
            self.lp_position_state.close_tx_hash = signature

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
            current_price = self._current_price if self._current_price else Decimal("0")
            # Create trade_fee with close tx_fee in native currency for proper tracking
            native_currency = getattr(connector, '_native_currency', DEFAULT_NATIVE_CURRENCY) or DEFAULT_NATIVE_CURRENCY
            trade_fee = TradeFeeBase.new_spot_fee(
                fee_schema=connector.trade_fee_schema(),
                trade_type=TradeType.RANGE,
                flat_fees=[TokenAmount(amount=close_tx_fee, token=native_currency)]
            )
            event = connector._trigger_remove_liquidity_event(
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

            # Store REMOVE event for position tracking (like spot grid stores orders)
            if self.config.keep_position or self.close_type == CloseType.POSITION_HOLD:
                self._store_lp_event_from_remove(event)

            self.lp_position_state.active_close_order = None
            self.lp_position_state.position_address = None

            # If keep_position=False, execute close-out swap to return to original position
            # Similar to how grid executor sells/buys back to rebalance
            if not self.config.keep_position and self.close_type != CloseType.POSITION_HOLD:
                # Calculate net base change using helper (same calculation as position_hold)
                base_diff = self._calculate_net_base_difference()
                if abs(base_diff) > Decimal("0.000001"):  # Non-trivial difference
                    self.logger().info(
                        f"Close-out swap needed: base_diff={base_diff:.6f} "
                        f"(received={self.lp_position_state.base_amount + self.lp_position_state.base_fee:.6f}, "
                        f"initial={self.lp_position_state.initial_base_amount:.6f})"
                    )
                    self.lp_position_state.state = LPExecutorStates.SWAPPING
                else:
                    self.logger().info("No close-out swap needed (base amounts match)")
                    self.lp_position_state.state = LPExecutorStates.COMPLETE
            else:
                self.lp_position_state.state = LPExecutorStates.COMPLETE

        except Exception as e:
            self._handle_close_failure(e)

    def _handle_close_failure(self, error: Exception):
        """Handle position close failure.

        Retry logic is handled by the connector. This method handles
        final failures after connector exhausted retries.
        """
        # Connector exhausted retries or non-retryable error - transition to FAILED
        self.logger().error(f"Position close failed: {error}")
        self.lp_position_state.active_close_order = None
        self.lp_position_state.state = LPExecutorStates.FAILED

    async def _execute_closeout_swap(self):
        """
        Execute close-out swap to return to original position when keep_position=False.
        Similar to grid executor's place_close_order_and_cancel_open_orders().

        This sells excess base tokens or buys back base tokens to match the initial position.
        """
        connector = self.connectors.get(self.config.connector_name)
        if connector is None:
            self.logger().error(f"Connector {self.config.connector_name} not found")
            self._handle_swap_failure(ValueError(f"Connector {self.config.connector_name} not found"))
            return

        if not self.config.swap_provider:
            self.logger().error("No swap_provider configured for close-out swap")
            self._handle_swap_failure(ValueError("No swap_provider configured"))
            return

        # Check if we already have an active swap order
        if self.lp_position_state.active_swap_order is not None:
            # Check swap order status
            order = connector.get_order(self.lp_position_state.active_swap_order.order_id)
            if order is None:
                # Order not found - might have completed or failed
                self._swap_not_found_count += 1
                if self._swap_not_found_count >= 3:
                    self.logger().warning(
                        f"Swap order {self.lp_position_state.active_swap_order.order_id} not found after "
                        f"{self._swap_not_found_count} checks. Assuming completed."
                    )
                    self.lp_position_state.active_swap_order = None
                    self.lp_position_state.state = LPExecutorStates.COMPLETE
                return

            from hummingbot.core.data_type.in_flight_order import OrderState
            if order.current_state == OrderState.FILLED:
                self.logger().info(f"Close-out swap completed: {order.client_order_id}")
                self.lp_position_state.active_swap_order = None
                self.lp_position_state.state = LPExecutorStates.COMPLETE
            elif order.current_state == OrderState.FAILED:
                self.logger().error(f"Close-out swap failed: {order.client_order_id}")
                self._handle_swap_failure(ValueError("Swap order failed"))
            elif order.current_state == OrderState.CANCELED:
                self.logger().warning(f"Close-out swap cancelled: {order.client_order_id}")
                self._handle_swap_failure(ValueError("Swap order cancelled"))
            # Otherwise still pending - wait for next tick
            return

        # Calculate swap amount and direction using helper (consistent with _close_position)
        base_diff = self._calculate_net_base_difference()

        if abs(base_diff) < Decimal("0.000001"):
            # No swap needed
            self.lp_position_state.state = LPExecutorStates.COMPLETE
            return

        # Determine trade direction
        # If base_diff > 0: We received more base than deposited → SELL excess base
        # If base_diff < 0: We received less base than deposited → BUY base to restore
        is_buy = base_diff < 0
        amount = abs(base_diff)
        side = TradeType.BUY if is_buy else TradeType.SELL

        self.logger().info(
            f"Executing close-out swap: {side.name} {amount:.6f} base (diff={base_diff:.6f})"
        )

        try:
            # Place swap order using connector's place_order with swap_provider
            order_id = connector.place_order(
                is_buy=is_buy,
                trading_pair=self.config.trading_pair,
                amount=amount,
                price=Decimal("0"),  # Market order
                dex_name=self.config.swap_provider,
                slippage_pct=Decimal("1.0"),  # 1% slippage for close-out
                max_retries=self._max_retries,
            )
            self.lp_position_state.active_swap_order = TrackedOrder(order_id=order_id)
            self._swap_not_found_count = 0
            self.logger().info(f"Close-out swap order placed: {order_id}")

        except Exception as e:
            self.logger().error(f"Failed to place close-out swap: {e}")
            self._handle_swap_failure(e)

    def _handle_swap_failure(self, error: Exception):
        """Handle close-out swap failure - transition to FAILED state."""
        self.logger().error(f"Close-out swap failed: {error}")
        self.lp_position_state.active_swap_order = None
        self.lp_position_state.state = LPExecutorStates.FAILED

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
        current_price = self._current_price if self._current_price else Decimal("0")

        self.logger().info(
            f"Emitting synthetic close event for already-closed position: "
            f"{self.lp_position_state.position_address}, "
            f"base: {self.lp_position_state.base_amount}, quote: {self.lp_position_state.quote_amount}, "
            f"fees: {self.lp_position_state.base_fee} base / {self.lp_position_state.quote_fee} quote"
        )

        # For synthetic events, we don't have the actual close tx_fee, so use 0
        native_currency = getattr(connector, '_native_currency', DEFAULT_NATIVE_CURRENCY) or DEFAULT_NATIVE_CURRENCY
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

    def _store_lp_event_from_add(self, event: RangePositionLiquidityAddedEvent):
        """Store ADD event data for later net trade calculation at REMOVE.

        Instead of recording ADD as a separate trade, we store the deposit amounts
        and calculate the net trade when the position is closed (REMOVE).
        """
        # Store ADD data for net trade calculation at REMOVE
        self._add_base_amount = event.base_amount
        self._add_quote_amount = event.quote_amount
        self._add_order_id = event.exchange_order_id

        # Store actual TX fee for ADD (from trade_fee, NOT position_rent which is refundable)
        native_to_quote = self._get_native_to_quote_rate()
        tx_fee = sum(fee.amount for fee in event.trade_fee.flat_fees) if event.trade_fee.flat_fees else Decimal("0")
        self._add_tx_fee_quote = float(tx_fee * native_to_quote)

    def _store_lp_event_from_remove(self, event: RangePositionLiquidityRemovedEvent):
        """Calculate net trade from ADD/REMOVE and store single order.

        The LP position net change determines if this was effectively a BUY or SELL:
        - net_base > 0, net_quote < 0: BUY (gained base, spent quote)
        - net_base < 0, net_quote > 0: SELL (spent base, gained quote)
        - net_base ≈ 0, net_quote ≈ 0: No trade (same assets in/out)
        """
        # Get ADD data (stored when position was opened)
        add_base = getattr(self, '_add_base_amount', Decimal("0"))
        add_quote = getattr(self, '_add_quote_amount', Decimal("0"))
        add_tx_fee = getattr(self, '_add_tx_fee_quote', 0.0)

        # Calculate net change (REMOVE - ADD)
        # Include LP fees earned in the returned amounts
        total_base_returned = event.base_amount + event.base_fee
        total_quote_returned = event.quote_amount + event.quote_fee
        net_base = total_base_returned - add_base
        net_quote = total_quote_returned - add_quote

        # TX fee for REMOVE
        native_to_quote = self._get_native_to_quote_rate()
        tx_fee = sum(fee.amount for fee in event.trade_fee.flat_fees) if event.trade_fee.flat_fees else Decimal("0")
        remove_tx_fee_quote = float(tx_fee * native_to_quote)

        # Total TX fees for this LP position
        total_tx_fee_quote = add_tx_fee + remove_tx_fee_quote

        # Determine trade type based on net change
        threshold = Decimal("0.0001")

        if abs(net_base) < threshold and abs(net_quote) < threshold:
            # No significant conversion - don't record a trade
            # But still track fees if any
            if total_tx_fee_quote > 0:
                self._held_position_orders.append({
                    "client_order_id": event.exchange_order_id,
                    "trade_type": "BUY",  # Dummy, won't affect P&L with 0 amounts
                    "price": float(event.mid_price),
                    "executed_amount_base": 0.0,
                    "executed_amount_quote": 0.0,
                    "cumulative_fee_paid_quote": total_tx_fee_quote,
                    "lp_source": True,
                    "lp_net_trade": True,
                })
            return

        if net_base > threshold and net_quote < -threshold:
            # Gained base, lost quote = BUY
            trade_type = "BUY"
            amount_base = float(net_base)
            amount_quote = float(abs(net_quote))
            price = amount_quote / amount_base if amount_base > 0 else float(event.mid_price)
        elif net_base < -threshold and net_quote > threshold:
            # Lost base, gained quote = SELL
            trade_type = "SELL"
            amount_base = float(abs(net_base))
            amount_quote = float(net_quote)
            price = amount_quote / amount_base if amount_base > 0 else float(event.mid_price)
        elif abs(net_base) > threshold:
            # Base changed but quote didn't significantly - use mid_price
            # This happens when LP fees are collected in the same asset
            if net_base > 0:
                trade_type = "BUY"
                amount_base = float(net_base)
            else:
                trade_type = "SELL"
                amount_base = float(abs(net_base))
            amount_quote = amount_base * float(event.mid_price)
            price = float(event.mid_price)
        else:
            # Only quote changed - record as 0-base trade (fees only)
            self._held_position_orders.append({
                "client_order_id": event.exchange_order_id,
                "trade_type": "BUY",
                "price": float(event.mid_price),
                "executed_amount_base": 0.0,
                "executed_amount_quote": float(abs(net_quote)),
                "cumulative_fee_paid_quote": total_tx_fee_quote,
                "lp_source": True,
                "lp_net_trade": True,
            })
            return

        # Create single order representing the net trade
        self._held_position_orders.append({
            "client_order_id": event.exchange_order_id,
            "order_id": event.order_id,
            "exchange_order_id": event.exchange_order_id,
            "trading_pair": event.trading_pair,
            "trade_type": trade_type,
            "price": price,
            "amount": amount_base,
            "executed_amount_base": amount_base,
            "executed_amount_quote": amount_quote,
            "cumulative_fee_paid_quote": total_tx_fee_quote,
            "lp_source": True,
            "lp_net_trade": True,
        })

    def early_stop(self, keep_position: bool = True):
        """Stop executor - transitions to CLOSING state.

        Args:
            keep_position: If True (default), after closing the LP position on-chain,
                          the net token change will be tracked as a spot position.
                          This matches spot grid executor behavior where keep_position
                          means "track the net position" not "keep orders open".
        """
        self._status = RunnableStatus.SHUTTING_DOWN
        # Use parameter directly like grid/position executors (controller decides keep_position)
        self.close_type = CloseType.POSITION_HOLD if keep_position else CloseType.EARLY_STOP

        # ALWAYS close the LP position on-chain
        # If keep_position=True, we'll capture the difference after closing
        if self.lp_position_state.state in [LPExecutorStates.IN_RANGE, LPExecutorStates.OUT_OF_RANGE]:
            self.lp_position_state.state = LPExecutorStates.CLOSING
        elif self.lp_position_state.state == LPExecutorStates.OPENING:
            # Position creation in progress - mark as failed to stop retries
            # The executor will complete without creating a position
            self.lp_position_state.state = LPExecutorStates.FAILED
            self.close_type = CloseType.EARLY_STOP
        elif self.lp_position_state.state == LPExecutorStates.NOT_ACTIVE:
            # No position was created, just complete
            self.lp_position_state.state = LPExecutorStates.COMPLETE

    def _calculate_net_base_difference(self) -> Decimal:
        """
        Calculate net base token difference from LP position lifecycle.

        This is the difference between what we received when closing the position
        (including fees) and what we initially deposited.

        Returns:
            Positive: We have more base than we started with (need to SELL)
            Negative: We have less base than we started with (need to BUY)
            Zero: Position is balanced

        Used by:
            - _close_position: To determine if close-out swap is needed
            - _execute_closeout_swap: To determine swap amount and direction
            - position_hold: Uses same calculation (ADD as SELL, REMOVE+fees as BUY)
        """
        # What we received when closing: base_amount + base_fee
        received_base = self.lp_position_state.base_amount + self.lp_position_state.base_fee
        # What we deposited when opening: initial_base_amount
        initial_base = self.lp_position_state.initial_base_amount
        return received_base - initial_base

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
        native_currency = getattr(connector, '_native_currency', DEFAULT_NATIVE_CURRENCY) or DEFAULT_NATIVE_CURRENCY
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
    def filled_amount_base(self) -> Decimal:
        """Returns current base token amount in the LP position.

        Used for position tracking aggregation.
        """
        return self.lp_position_state.base_amount

    @property
    def filled_amount_quote(self) -> Decimal:
        """Returns initial investment value in quote currency.

        For LP positions, this represents the capital deployed (initial deposit)
        expressed in the pool's quote currency (e.g., SOL for PERCOLATOR-SOL).
        Returns 0 if position was never created (FAILED state).
        """
        # If position was never created, nothing was filled
        if self.lp_position_state.initial_base_amount == 0 and self.lp_position_state.initial_quote_amount == 0:
            return Decimal("0")

        # Use stored add_mid_price, fall back to current price if not set
        add_price = self.lp_position_state.add_mid_price
        if add_price <= 0:
            add_price = self._current_price if self._current_price else Decimal("0")

        if add_price == 0:
            return Decimal("0")

        # Use stored initial amounts (actual deposited)
        initial_base = self.lp_position_state.initial_base_amount
        initial_quote = self.lp_position_state.initial_quote_amount

        # Initial investment value in pool quote currency
        return initial_base * add_price + initial_quote

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
            # Initial amounts (actual deposited) for inventory tracking, fallback to config
            "initial_base_amount": float(
                self.lp_position_state.initial_base_amount
                if self.lp_position_state.initial_base_amount > 0 or self.lp_position_state.initial_quote_amount > 0
                else self.config.base_amount
            ),
            "initial_quote_amount": float(
                self.lp_position_state.initial_quote_amount
                if self.lp_position_state.initial_base_amount > 0 or self.lp_position_state.initial_quote_amount > 0
                else self.config.quote_amount
            ),
            # Position tracking fields (consistent with grid/position/swap executors)
            "filled_amount_base": float(self.lp_position_state.base_amount),
            "filled_amount_quote": float(self.lp_position_state.quote_amount),
            "held_position_orders": self._held_position_orders,
        }

    # Required abstract methods from ExecutorBase
    async def validate_sufficient_balance(self):
        """Validate sufficient balance for LP position. ExecutorBase calls this in on_start()."""
        # LP connector handles balance validation during add_liquidity
        pass

    def get_net_pnl_quote(self) -> Decimal:
        """
        Returns net P&L in pool quote currency.

        P&L = (current_position_value + fees_earned) - initial_value - tx_fees

        Uses stored initial amounts and add_mid_price for accurate calculation.
        Works for both open positions and closed positions (using final returned amounts).
        Falls back to config values if initial amounts not yet set.
        """
        if self._current_price is None or self._current_price == 0:
            return Decimal("0")
        current_price = self._current_price

        # If executor failed before creating a position, P&L is 0
        if (self.lp_position_state.state == LPExecutorStates.FAILED and
                not self.lp_position_state.position_address):
            return Decimal("0")

        # Use stored add_mid_price for initial value, fall back to current price if not set
        add_price = self.lp_position_state.add_mid_price if self.lp_position_state.add_mid_price > 0 else current_price

        # Use stored initial amounts, fall back to config if not set (position not yet created)
        initial_base = self.lp_position_state.initial_base_amount
        initial_quote = self.lp_position_state.initial_quote_amount
        if initial_base == 0 and initial_quote == 0:
            initial_base = self.config.base_amount
            initial_quote = self.config.quote_amount

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

        return pnl_in_quote - tx_fee_quote

    def get_net_pnl_pct(self) -> Decimal:
        """Returns net P&L as percentage of initial investment.

        Both P&L and initial value are in quote currency.
        Falls back to config values if initial amounts not yet set.
        """
        pnl_quote = self.get_net_pnl_quote()
        if pnl_quote == Decimal("0"):
            return Decimal("0")

        if self._current_price is None or self._current_price == 0:
            return Decimal("0")
        current_price = self._current_price

        # Use stored add_mid_price for initial value to match get_net_pnl_quote()
        add_price = self.lp_position_state.add_mid_price if self.lp_position_state.add_mid_price > 0 else current_price

        # Use stored initial amounts, fall back to config if not set
        initial_base = self.lp_position_state.initial_base_amount
        initial_quote = self.lp_position_state.initial_quote_amount
        if initial_base == 0 and initial_quote == 0:
            initial_base = self.config.base_amount
            initial_quote = self.config.quote_amount

        # Initial value in pool quote currency
        initial_value_quote = initial_base * add_price + initial_quote

        if initial_value_quote == Decimal("0"):
            return Decimal("0")

        return (pnl_quote / initial_value_quote) * Decimal("100")

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
            self._pool_info = await connector.get_pool_info_by_address(
                self.config.pool_address,
                dex_name=self.lp_dex_name,
                trading_type=self.lp_trading_type,
            )
            if self._pool_info:
                self._current_price = Decimal(str(self._pool_info.price))
        except Exception as e:
            self.logger().warning(f"Error fetching pool info: {e}")
