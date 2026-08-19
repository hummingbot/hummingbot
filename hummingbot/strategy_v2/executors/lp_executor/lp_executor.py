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
        super().__init__(strategy, connectors, config, update_interval, max_retries=max_retries)
        self.config: LPExecutorConfig = config
        self._max_retries = max_retries
        self.lp_position_state = LPExecutorState()
        self._pool_info: Optional[Union[CLMMPoolInfo, AMMPoolInfo]] = None
        self._current_price: Optional[Decimal] = None  # Updated from pool_info or position_info
        self._max_retries_reached = False  # True when max retries reached, requires intervention
        self._last_attempted_signature: Optional[str] = None  # Track for retry logging
        # Position tracking - store LP position for position aggregation when keep_position=True
        self._held_position_orders: List[Dict] = []
        # Swap tracking for close-out flow
        self._swap_not_found_count: int = 0
        # Consecutive definitive "position does not exist" reads while monitoring;
        # guards against a single lagging RPC node being read as an external close.
        # Uses get_position_info_fresh so each miss is an independent Gateway read
        # (the cached get_position_info would serve one 404 for several ticks).
        self._position_not_found_count: int = 0
        # External-close detection is only trusted once the position has been
        # observed on-chain at least once; before that, a not-found streak is far
        # more likely RPC lag on a just-created position than a real close.
        self._position_seen_onchain: bool = False
        # Backoff between close attempts (set by _handle_close_failure) so a burst
        # of instant transport failures (e.g. a Gateway restart) cannot burn the
        # whole retry budget in seconds
        self._close_backoff_until: float = 0.0
        # Why a POSITION_HOLD terminal was involuntary (e.g. "close_retries_exhausted");
        # None for voluntary holds (keep_position=True stops). Consumers use this,
        # not close_type, to distinguish stranded exposure from a requested hold.
        self._hold_reason: Optional[str] = None
        # early_stop() arrived while the create was in flight: let the create
        # resolve, then route straight to CLOSING (killing the state mid-await used
        # to strand a landed position behind a FAILED terminal).
        self._close_after_open: bool = False
        # Close-out swap attempts (each failure re-places with a fresh quote)
        self._swap_failure_count: int = 0
        # Parse lp_provider into dex_name and trading_type for gateway calls
        self.lp_dex_name, self.lp_trading_type = parse_provider(config.lp_provider)

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

        # Resolve swap_provider up front when the config already expects to unwind,
        # so a missing provider surfaces at start instead of mid-close-out.
        if not self.config.keep_position:
            await self._resolve_swap_provider()

    async def _resolve_swap_provider(self) -> bool:
        """Fill in swap_provider from the network default if it is not set.

        Also called lazily from the close-out path: early_stop(keep_position=False)
        can unwind an executor whose config said keep_position=True, which never
        resolved a provider at start.

        Returns True if a provider is available.
        """
        if self.config.swap_provider:
            return True

        gateway = GatewayHttpClient.get_instance()
        default_provider = await gateway.get_default_swap_provider(self.config.connector_name)
        if default_provider:
            # The network default comes straight from Gateway's config, which is not
            # covered by LPExecutorConfig's validator — reject an untyped one here
            # instead of letting it become a 400 mid close-out swap.
            if "/" not in default_provider:
                self.logger().error(
                    f"Network default swap provider '{default_provider}' for "
                    f"{self.config.connector_name} is not in 'name/type' form "
                    "(e.g. 'jupiter/router'). Fix swapProvider in the Gateway network config."
                )
                return False
            self.config = self.config.model_copy(update={'swap_provider': default_provider})
            self.logger().info(f"Using network default swap provider: {default_provider}")
            return True

        self.logger().warning(
            f"No swap provider found for {self.config.connector_name}. "
            "Close-out swaps will not be available."
        )
        return False

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
                # Position creation in progress (connector retries timeouts;
                # any other open failure is terminal — see _handle_create_failure)
                await self._create_position()

            case LPExecutorStates.CLOSING:
                # This re-entry IS the close retry loop: _handle_close_failure counts
                # the failed attempt and backs off, evaluate_max_retries terminates
                await self._close_position()

            case LPExecutorStates.SWAPPING:
                # Close-out swap in progress (keep_position=False)
                # Similar to grid executor placing close order to rebalance
                await self._execute_closeout_swap()

            case LPExecutorStates.FAILED:
                # Stop with failure — but never clobber a more specific close_type
                # already assigned (e.g. EARLY_STOP set by early_stop() before the
                # create failed).
                if self.close_type is None:
                    self.close_type = CloseType.FAILED
                self.stop()

            case LPExecutorStates.IN_RANGE | LPExecutorStates.OUT_OF_RANGE:
                # Position active - close if price exceeds limit prices (like grid
                # executor). Checked in BOTH range states: limit prices are
                # independent of the position's bounds, and the on-chain bounds can
                # be wider than the configured ones (bin rounding at open), so a
                # price beyond a limit can still be inside the position's range.
                self._check_limit_prices()

            case LPExecutorStates.COMPLETE:
                # Position closed - close_type already set by early_stop()
                self.stop()

    def _check_limit_prices(self):
        """Close the position when the price crosses a configured limit price."""
        if self._current_price is None:
            return

        if self.config.upper_limit_price is not None and self._current_price >= self.config.upper_limit_price:
            direction = "above upper limit"
        elif self.config.lower_limit_price is not None and self._current_price <= self.config.lower_limit_price:
            direction = "below lower limit"
        else:
            return

        self.logger().info(
            f"Price {self._current_price} {direction} "
            f"(upper_limit={self.config.upper_limit_price}, lower_limit={self.config.lower_limit_price}), closing"
        )
        # Respect keep_position config - use POSITION_HOLD to track net position, EARLY_STOP otherwise
        self.close_type = CloseType.POSITION_HOLD if self.config.keep_position else CloseType.EARLY_STOP
        self.lp_position_state.state = LPExecutorStates.CLOSING

    async def _update_position_info(self):
        """Fetch current position info from connector to update amounts and fees"""
        if not self.lp_position_state.position_address:
            return

        connector = self.connectors.get(self.config.connector_name)
        if connector is None:
            return

        try:
            # Fresh (uncached) read: this method makes existence decisions, and the
            # cached variant would serve a single 404 for several consecutive ticks
            position_info = await connector.get_position_info_fresh(
                trading_pair=self.config.trading_pair,
                dex_name=self.lp_dex_name,
                trading_type=self.lp_trading_type,
                position_address=self.lp_position_state.position_address
            )

            if position_info:
                self._position_not_found_count = 0
                self._position_seen_onchain = True
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
                # None from the connector is a definitive Gateway 404 (transient errors
                # raise and are handled below). Two gates before acting on it: the
                # position must have been observed on-chain at least once (a miss on a
                # just-created position is RPC lag, not a close), and the miss must
                # repeat across independent reads.
                self._position_not_found_count += 1
                if self._position_seen_onchain and self._position_not_found_count >= 3:
                    self.logger().info(
                        f"Position {self.lp_position_state.position_address} no longer exists on-chain "
                        "(closed externally or by a prior attempt) - marking complete"
                    )
                    # An external close still needs a terminal type — and under
                    # keep_position=False it still owes the close-out swap (the
                    # withdrawn tokens landed in the wallet either way).
                    if self.close_type is None:
                        self.close_type = (CloseType.POSITION_HOLD if self.config.keep_position
                                           else CloseType.EARLY_STOP)
                    self._handle_position_gone()
                else:
                    self.logger().warning(
                        f"Position {self.lp_position_state.position_address} not found "
                        f"({self._position_not_found_count} consecutive reads, "
                        f"seen_onchain={self._position_seen_onchain})"
                    )
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
            elif "position not found" in error_msg:
                # Position-specific 404 only: a bare "not found" also matches the HTTP
                # client's "(Not Found)" suffix on unrelated 404s (missing route/wallet)
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

            # Fetch full position info from chain to get actual amounts and bounds.
            # This enriches bookkeeping only - the position is already open, so a
            # transient fetch error must not fail the create (which would route to
            # CLOSING); fall back to config values instead.
            try:
                # Fresh read: caching a lagging 404 here would poison the next ticks'
                # existence checks with "position gone" for a position that is live
                position_info = await connector.get_position_info_fresh(
                    trading_pair=self.config.trading_pair,
                    dex_name=self.lp_dex_name,
                    trading_type=self.lp_trading_type,
                    position_address=position_address
                )
            except Exception as info_error:
                self.logger().warning(f"Position info fetch after create failed: {info_error}")
                position_info = None

            if position_info:
                self._position_seen_onchain = True

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

            # Record the deposit unconditionally. This is bookkeeping, not a
            # decision: whether the round trip is kept as a hold is settled at
            # stop time by early_stop(keep_position=...), long after this runs.
            # Gating it on config.keep_position left a runtime keep_position=True
            # with no deposit to net against, booking the entire withdrawn
            # balance as a BUY.
            self._store_lp_event_from_add(event)

            if self._close_after_open:
                # early_stop() arrived while this create was in flight: the position
                # is live and funded, so close it now (close_type was already set by
                # early_stop from its keep_position argument).
                self.logger().info(
                    f"Create resolved after early_stop: closing {position_address} immediately."
                )
                self.lp_position_state.state = LPExecutorStates.CLOSING
                return

            # Update state immediately (don't wait for next tick)
            self.lp_position_state.update_state(current_price, self._strategy.current_timestamp)

        except Exception as e:
            self._handle_create_failure(e)

    def _handle_create_failure(self, error: Exception):
        """Handle position creation failure.

        A position_address means add_liquidity already landed on-chain and only
        the bookkeeping after it threw, so the funds are real. FAILED would stop
        the executor without ever calling _close_position, stranding them: the
        add-liquidity event that records the position for lphistory is emitted
        after the code most likely to throw, so the position would survive only
        in this log line. Close it instead, and name the address either way.

        Retrying the open is not an option here -- the add succeeded, so a retry
        would deposit a second position on top of the first.
        """
        self.lp_position_state.active_open_order = None

        if self.lp_position_state.position_address:
            self.logger().error(
                f"Position creation failed after the position was opened at "
                f"{self.lp_position_state.position_address} ({self.config.trading_pair}): "
                f"{error}. Closing it to recover the funds."
            )
            self.close_type = CloseType.FAILED
            self.lp_position_state.state = LPExecutorStates.CLOSING
            return

        self.logger().error(f"Position creation failed: {error}")
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

        # Respect the backoff set by a failed attempt: without it, a burst of instant
        # transport failures (e.g. Gateway restarting) would burn the whole retry
        # budget in as many seconds as there are retries.
        if self._strategy.current_timestamp < self._close_backoff_until:
            return

        # Verify position still exists before trying to close (handles timeout-but-succeeded
        # case). Fresh read; but ONE miss is never proof (a lagging RPC node's 404
        # would otherwise declare a freshly funded position closed with a
        # success-shaped event). Same 3-consecutive-miss gate as the monitoring
        # path (retry-architecture §3.2).
        try:
            position_info = await connector.get_position_info_fresh(
                trading_pair=self.config.trading_pair,
                dex_name=self.lp_dex_name,
                trading_type=self.lp_trading_type,
                position_address=self.lp_position_state.position_address
            )
        except Exception as e:
            # Gateway returns HttpError with message patterns for a definitively
            # missing position; treat those exactly like a None read (a miss).
            error_msg = str(e).lower()
            if "position closed" in error_msg or "position not found" in error_msg:
                position_info = None
            else:
                # Transient error - proceed with the close attempt
                position_info = False

        if position_info is None:
            self._position_not_found_count += 1
            if self._position_not_found_count >= 3:
                self.logger().info(
                    f"Position {self.lp_position_state.position_address} definitively absent "
                    f"({self._position_not_found_count} consecutive misses) - already closed"
                )
                self._handle_position_gone()
                return
            self.logger().warning(
                f"Pre-flight miss {self._position_not_found_count}/3 for "
                f"{self.lp_position_state.position_address}; not closing this tick"
            )
            # Don't submit a close against a position we cannot currently see —
            # re-enter next tick; misses do not burn the close retry budget.
            return
        if position_info is not False:
            self._position_not_found_count = 0
            self._position_seen_onchain = True

        # Generate order_id for tracking
        order_id = connector.create_market_order_id(TradeType.RANGE, self.config.trading_pair)
        self.lp_position_state.active_close_order = TrackedOrder(order_id=order_id)

        try:
            # One gateway request per attempt (max_retries=0): this CLOSING loop is the
            # only owner of close retries. Each re-entry rebuilds from fresh on-chain
            # state, and the pre-flight above reconciles an attempt that landed after a
            # timeout — a connector-level retry would re-submit without that check.
            signature = await connector._clmm_close_position(
                trade_type=TradeType.RANGE,
                order_id=order_id,
                trading_pair=self.config.trading_pair,
                position_address=self.lp_position_state.position_address,
                max_retries=0,
                dex_name=self.lp_dex_name,
                trading_type=self.lp_trading_type,
            )
            # Note: on failure the connector re-raises and _handle_close_failure counts it
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

            # Store REMOVE event for position tracking (like spot grid stores orders).
            # Keyed off close_type alone: that is the runtime decision made by
            # early_stop(keep_position=...), which overrides config.keep_position.
            if self.close_type == CloseType.POSITION_HOLD:
                self._store_lp_event_from_remove(event)

            self.lp_position_state.active_close_order = None
            self.lp_position_state.position_address = None

            # Not holding the net means swapping back to the original position.
            # Same runtime decision as the REMOVE gate above, and stated
            # positively so an unexpected close_type skips the on-chain swap
            # rather than firing one nobody asked for. Both transitions into
            # CLOSING set close_type to POSITION_HOLD or EARLY_STOP first.
            if self.close_type == CloseType.EARLY_STOP:
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

        The connector retries transport and stale-state errors within a single
        attempt; this handles an attempt that failed after those retries. The
        position is still open on-chain, so going terminal here would strand it
        (see gateway#678). Count the attempt, arm the backoff, and stay in
        CLOSING — control_task re-enters _close_position on the next tick, and
        each re-entry re-POSTs to Gateway, which rebuilds the transaction from
        fresh on-chain state (the pre-flight reconciles a close that already
        landed). Termination on exhaustion is decided by evaluate_max_retries,
        the family hook the base control_loop calls right after this
        control_task returns.
        """
        self._current_retries += 1
        self.lp_position_state.active_close_order = None

        if self._current_retries > self._max_retries:
            # evaluate_max_retries terminates after this control_task returns.
            self.logger().warning(f"Position close attempt failed: {error}. Retry budget exhausted.")
            return

        # Exponential backoff (capped at 30s) so instant failures — e.g. connection
        # errors while Gateway restarts — spread the retry budget over minutes
        # instead of burning it in seconds
        backoff = min(30.0, 2.0 ** self._current_retries)
        self._close_backoff_until = self._strategy.current_timestamp + backoff
        self.logger().warning(
            f"Position close attempt failed ({self._current_retries}/{self._max_retries} retries used): "
            f"{error}. Rebuilding with fresh state in {backoff:.0f}s."
        )
        # State stays CLOSING - control_task re-enters _close_position after backoff.

    def evaluate_max_retries(self):
        """Terminate when the close-retry budget is exhausted.

        Base-class semantics (``> max_retries``, i.e. ``max_retries + 1`` total
        attempts — the family convention) decide *when*; this override decides
        *how*. A position still on-chain is residual exposure, and the family
        contract (see ``force_stop_with_position_hold``) ends residual exposure
        as POSITION_HOLD, reserving FAILED for executors with nothing left
        behind. PositionHold cannot book a live LP position as spot amounts, so
        the hold carries a zero-amount marker order with the position's identity
        instead — visible and durable in the hold store on both the bot and the
        hummingbot-api topology, with accounting untouched.
        """
        if self._current_retries <= self._max_retries:
            return
        self._max_retries_reached = True
        position_address = self.lp_position_state.position_address
        if position_address:
            self._hold_reason = "close_retries_exhausted"
            self._record_unclosed_position_marker()
            self.close_type = CloseType.POSITION_HOLD
            self.logger().error(
                f"Position close failed after {self._current_retries} attempts: position "
                f"{position_address} ({self.config.trading_pair}) is still open on-chain. "
                "Terminating as an involuntary POSITION_HOLD (hold_reason=close_retries_exhausted) - "
                "close it via the gateway and resolve the orphan record."
            )
        else:
            self.close_type = CloseType.FAILED
            self.logger().error(
                f"Retry budget exhausted after {self._current_retries} attempts with no position "
                "on-chain - terminating as FAILED."
            )
        self.stop()

    def _record_unclosed_position_marker(self):
        """Append a zero-amount marker order carrying the unclosed position's identity.

        A live on-chain position cannot be booked as spot amounts — the tokens
        are in the pool, not the wallet — but an empty held_position_orders would
        make the POSITION_HOLD invisible to the hold store. Zero amounts keep
        accounting untouched (PositionHold._process_order skips them) while the
        marker carries the address every recovery path needs.
        """
        self._held_position_orders.append({
            "client_order_id": f"{self.config.id}-unclosed-lp",
            "trading_pair": self.config.trading_pair,
            "trade_type": "BUY",  # dummy; zero amounts never reach accounting
            "price": float(self._current_price) if self._current_price else 0.0,
            "executed_amount_base": 0.0,
            "executed_amount_quote": 0.0,
            "cumulative_fee_paid_quote": getattr(self, '_add_tx_fee_quote', 0.0),
            "lp_source": True,
            "lp_unclosed_position": True,
            "position_address": self.lp_position_state.position_address,
        })

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

        if not await self._resolve_swap_provider():
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
            # Place swap order using connector's place_order with swap_provider.
            # No slippage_pct: omitted, the connector-configured slippagePct applies
            # (hardcoding 1.0 here used to override the operator's Gateway config).
            order_id = connector.place_order(
                is_buy=is_buy,
                trading_pair=self.config.trading_pair,
                amount=amount,
                price=Decimal("0"),  # Market order
                dex_name=self.config.swap_provider,
                max_retries=self._max_retries,
            )
            self.lp_position_state.active_swap_order = TrackedOrder(order_id=order_id)
            self._swap_not_found_count = 0
            self.logger().info(f"Close-out swap order placed: {order_id}")

        except Exception as e:
            self.logger().error(f"Failed to place close-out swap: {e}")
            self._handle_swap_failure(e)

    def _handle_position_gone(self):
        """The position is definitively absent on-chain: a prior close attempt
        landed, or it was closed externally. Emit the synthetic close event and
        route exactly like a successful close — EARLY_STOP (keep_position=False)
        still owes the close-out swap, since the withdrawn tokens are in the
        wallet either way. Going straight to COMPLETE here used to leave that
        net base change unswapped and unrecorded.
        """
        self._emit_already_closed_event()
        self.lp_position_state.active_close_order = None
        self.lp_position_state.position_address = None

        if self.close_type == CloseType.EARLY_STOP:
            base_diff = self._calculate_net_base_difference()
            if abs(base_diff) > Decimal("0.000001"):
                self.logger().info(
                    f"Close-out swap needed after already-closed reconcile: base_diff={base_diff:.6f}"
                )
                self.lp_position_state.state = LPExecutorStates.SWAPPING
                return
        self.lp_position_state.state = LPExecutorStates.COMPLETE

    # Close-out swap attempts before the executor stops fighting the market and
    # holds the withdrawn tokens instead (each attempt re-quotes at market).
    MAX_CLOSEOUT_SWAP_ATTEMPTS = 3

    def _handle_swap_failure(self, error: Exception):
        """Handle close-out swap failure.

        Bounded retries with a fresh quote each attempt; on exhaustion the
        executor terminates POSITION_HOLD carrying the withdrawn tokens. The old
        first-failure jump to FAILED reported "no residual exposure" while the
        REMOVE's proceeds sat in the wallet, unrecorded.
        """
        self.lp_position_state.active_swap_order = None
        self._swap_failure_count += 1

        if self._swap_failure_count < self.MAX_CLOSEOUT_SWAP_ATTEMPTS:
            self.logger().error(
                f"Close-out swap failed (attempt {self._swap_failure_count}/"
                f"{self.MAX_CLOSEOUT_SWAP_ATTEMPTS}): {error}. Retrying with a fresh quote."
            )
            return  # stay in SWAPPING; next tick re-places at market

        self.logger().error(
            f"Close-out swap failed {self._swap_failure_count} times: {error}. "
            "Holding the withdrawn tokens instead of reporting FAILED with hidden exposure."
        )
        self._hold_reason = "closeout_swap_failed"
        self.close_type = CloseType.POSITION_HOLD
        connector = self.connectors.get(self.config.connector_name)
        current_price = self._current_price if self._current_price else Decimal("0")
        if connector is not None:
            order_id = connector.create_market_order_id(TradeType.RANGE, self.config.trading_pair)
            self._store_net_trade_from_withdrawal(
                total_base_returned=self.lp_position_state.base_amount + self.lp_position_state.base_fee,
                total_quote_returned=self.lp_position_state.quote_amount + self.lp_position_state.quote_fee,
                mid_price=current_price,
                remove_tx_fee_quote=0.0,
                order_id=order_id,
                exchange_order_id="closeout-swap-failed",
                trading_pair=self.config.trading_pair,
            )
        self.lp_position_state.state = LPExecutorStates.COMPLETE

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

        # Record the hold from the same last-known amounts. Without this the
        # executor completes as POSITION_HOLD reporting no orders at all, and
        # consumers fall back to filled_amount_base -- which for an LP executor
        # is the base sitting in the pool, not base the executor acquired.
        if self.close_type == CloseType.POSITION_HOLD:
            self._store_net_trade_from_withdrawal(
                total_base_returned=self.lp_position_state.base_amount + self.lp_position_state.base_fee,
                total_quote_returned=self.lp_position_state.quote_amount + self.lp_position_state.quote_fee,
                mid_price=current_price,
                remove_tx_fee_quote=0.0,
                order_id=order_id,
                exchange_order_id="already-closed",
                trading_pair=self.config.trading_pair,
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
        """Calculate net trade from ADD/REMOVE and store single order."""
        # TX fee for REMOVE
        native_to_quote = self._get_native_to_quote_rate()
        tx_fee = sum(fee.amount for fee in event.trade_fee.flat_fees) if event.trade_fee.flat_fees else Decimal("0")
        remove_tx_fee_quote = float(tx_fee * native_to_quote)
        self._store_net_trade_from_withdrawal(
            total_base_returned=event.base_amount + event.base_fee,
            total_quote_returned=event.quote_amount + event.quote_fee,
            mid_price=event.mid_price,
            remove_tx_fee_quote=remove_tx_fee_quote,
            order_id=event.order_id,
            exchange_order_id=event.exchange_order_id,
            trading_pair=event.trading_pair,
        )

    def _store_net_trade_from_withdrawal(self, total_base_returned: Decimal, total_quote_returned: Decimal,
                                         mid_price: Decimal, remove_tx_fee_quote: float,
                                         order_id: str, exchange_order_id: str, trading_pair: str):
        """Store the net trade of a liquidity withdrawal against the recorded ADD.

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
        net_base = total_base_returned - add_base
        net_quote = total_quote_returned - add_quote

        # Total TX fees for this LP position
        total_tx_fee_quote = add_tx_fee + remove_tx_fee_quote

        # Determine trade type based on net change
        threshold = Decimal("0.0001")

        if abs(net_base) < threshold and abs(net_quote) < threshold:
            # No significant conversion - record a zero-amount order carrying only
            # the fees. Appended even when there are no fees: an empty
            # held_position_orders is indistinguishable from "this executor does
            # not report orders", and consumers then fall back to
            # filled_amount_base, which for an LP executor is the pool balance
            # rather than acquired base. A zero-amount order says "nothing" plainly.
            self._held_position_orders.append({
                "client_order_id": exchange_order_id,
                "trade_type": "BUY",  # Dummy, won't affect P&L with 0 amounts
                "price": float(mid_price),
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
            price = amount_quote / amount_base if amount_base > 0 else float(mid_price)
        elif net_base < -threshold and net_quote > threshold:
            # Lost base, gained quote = SELL
            trade_type = "SELL"
            amount_base = float(abs(net_base))
            amount_quote = float(net_quote)
            price = amount_quote / amount_base if amount_base > 0 else float(mid_price)
        elif abs(net_base) > threshold:
            # Base changed but quote didn't significantly - use mid_price
            # This happens when LP fees are collected in the same asset
            if net_base > 0:
                trade_type = "BUY"
                amount_base = float(net_base)
            else:
                trade_type = "SELL"
                amount_base = float(abs(net_base))
            amount_quote = amount_base * float(mid_price)
            price = float(mid_price)
        else:
            # Only quote changed - record as 0-base trade (fees only)
            self._held_position_orders.append({
                "client_order_id": exchange_order_id,
                "trade_type": "BUY",
                "price": float(mid_price),
                "executed_amount_base": 0.0,
                "executed_amount_quote": float(abs(net_quote)),
                "cumulative_fee_paid_quote": total_tx_fee_quote,
                "lp_source": True,
                "lp_net_trade": True,
            })
            return

        # Create single order representing the net trade
        self._held_position_orders.append({
            "client_order_id": exchange_order_id,
            "order_id": order_id,
            "exchange_order_id": exchange_order_id,
            "trading_pair": trading_pair,
            "trade_type": trade_type,
            "price": price,
            "amount": amount_base,
            "executed_amount_base": amount_base,
            "executed_amount_quote": amount_quote,
            "cumulative_fee_paid_quote": total_tx_fee_quote,
            "lp_source": True,
            "lp_net_trade": True,
        })

    def _collect_held_position_orders(self) -> List[Dict]:
        """Snapshot residual exposure for a forced stop at the shutdown deadline.

        Mid-SWAPPING the liquidity is already out of the pool but the close-out swap
        has not confirmed, so the withdrawn tokens sit in the wallet as spot. Record
        the same net trade the keep_position path would have stored at REMOVE, so the
        exposure becomes a tracked hold instead of invisible dust. (A swap submitted
        in the same tick can still land after the stop; next-start reconciliation
        absorbs that one fill.)

        A position still on-chain (address set, REMOVE not confirmed) cannot be
        represented as spot orders — log it loudly so it can be recovered.
        """
        if not self._held_position_orders and self.lp_position_state.state == LPExecutorStates.SWAPPING:
            mid_price = self._current_price if self._current_price else Decimal("0")
            self._store_net_trade_from_withdrawal(
                total_base_returned=self.lp_position_state.base_amount + self.lp_position_state.base_fee,
                total_quote_returned=self.lp_position_state.quote_amount + self.lp_position_state.quote_fee,
                mid_price=mid_price,
                remove_tx_fee_quote=0.0,
                order_id=f"{self.config.id}-forced-hold",
                exchange_order_id=f"{self.config.id}-forced-hold",
                trading_pair=self.config.trading_pair,
            )
        if not self._held_position_orders and self.lp_position_state.position_address:
            self.logger().error(
                f"Forced stop with LP position still on-chain at {self.lp_position_state.position_address} "
                f"({self.config.trading_pair}). An on-chain position cannot be held as spot orders; "
                f"recover it on the next start or manually."
            )
        return list(self._held_position_orders)

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
            # The create is in flight and its transaction may LAND — killing the
            # state here used to strand a live, funded position behind a FAILED
            # terminal ("nothing on-chain"). Let the create resolve; its success
            # tail routes straight to CLOSING, and its failure path ends normally.
            self._close_after_open = True
            self.logger().info(
                "early_stop during OPENING: waiting for the in-flight create to "
                "resolve, then closing."
            )
        elif self.lp_position_state.state == LPExecutorStates.NOT_ACTIVE:
            # No position was created, just complete
            self.lp_position_state.state = LPExecutorStates.COMPLETE

    def _calculate_net_base_difference(self) -> Decimal:
        """
        Calculate net base token difference from LP position lifecycle.

        This is the difference between what we received when closing the position
        (including fees) and what we initially deposited.

        Deliberately the net, NOT the entire withdrawn balance. The executor owns
        the LP round trip, not the base it was handed: the deposit was funded by
        whoever opened the slot (typically an entry order_executor that recorded a
        PositionHold), so unwinding to the net leaves that hold accurate and the
        executor position-neutral. Selling the full balance instead disposes of
        base the ledger still counts as held -- and since the keep_position=False
        path does not call _store_lp_event_from_remove, that sale is recorded
        nowhere, stranding a phantom hold. Ending flat is the entry executor's
        job, via its own keep_position=False.

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
            # Retry observability (consistent with order executor)
            "current_retries": self._current_retries,
            "max_retries": self._max_retries,
            "max_retries_reached": self._max_retries_reached,
            "hold_reason": self._hold_reason,
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
        """Returns net P&L ratio relative to initial investment.

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

        return pnl_quote / initial_value_quote

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
