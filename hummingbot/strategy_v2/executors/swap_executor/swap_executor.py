"""
SwapExecutor - Executes single swaps on Gateway AMM connectors.

Uses Gateway connector's place_order functionality for proper order tracking,
event emission, and retry logic at the connector level.
"""
import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Union

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.gateway.gateway import Gateway
from hummingbot.connector.gateway.gateway_base import extract_error_code
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    MarketOrderFailureEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
)
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.strategy_v2_base import StrategyV2Base
from hummingbot.strategy_v2.executors.executor_base import ExecutorBase
from hummingbot.strategy_v2.executors.gateway_utils import validate_and_normalize_connector
from hummingbot.strategy_v2.executors.swap_executor.data_types import SwapExecutorConfig, SwapExecutorStates
from hummingbot.strategy_v2.models.executors import CloseType


class SwapExecutor(ExecutorBase):
    """
    Executor for single swap operations on Gateway AMM connectors.

    Uses the Gateway connector's place_order functionality which handles:
    - Order tracking
    - Event emission (OrderCreated, OrderFilled, OrderCompleted)
    - Retry logic for transaction timeouts

    State Flow:
        NOT_STARTED -> EXECUTING -> COMPLETED (success)
                                 -> FAILED (max retries or error)
    """
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @staticmethod
    def parse_network(network: str) -> tuple:
        """Parse network string into chain and network_name.

        Args:
            network: Network string like "solana-mainnet-beta" or "ethereum-mainnet"

        Returns:
            Tuple of (chain, network_name)
        """
        parts = network.split("-", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return parts[0], "mainnet"

    def __init__(
        self,
        strategy: StrategyV2Base,
        config: SwapExecutorConfig,
        update_interval: float = 1.0,
        max_retries: int = 10,
    ):
        """
        Initialize SwapExecutor.

        Args:
            strategy: The strategy instance
            config: SwapExecutorConfig with swap parameters
            update_interval: Interval between control_task calls
            max_retries: Maximum retries for swap operations (passed to connector)
        """
        # Pass connector_name to ExecutorBase so it registers for events
        super().__init__(strategy, [config.connector_name], config, update_interval)
        self.config: SwapExecutorConfig = config
        self._max_retries = max_retries
        self._state = SwapExecutorStates.NOT_STARTED
        self._executed_amount: Decimal = Decimal("0")
        self._executed_price: Decimal = Decimal("0")
        self._tx_fee: Decimal = Decimal("0")
        self._exchange_order_id: Optional[str] = None  # Transaction hash/signature
        self._order_id: Optional[str] = None  # Internal order ID from connector
        self._order: Optional[InFlightOrder] = None  # Order object for to_json() (same pattern as order_executor)
        self._selected_provider: Optional[str] = None  # Provider used for multi-provider comparison
        # Network info - parsed from connector_name (which is now the network identifier)
        if config.connector_name:
            self._chain, self._network_name = self.parse_network(config.connector_name)
        else:
            self._chain = None
            self._network_name = None
        # Position tracking - store completed swaps for position aggregation
        self._held_position_orders: List[Dict] = []

    def _validate_and_normalize_swap_provider(self, swap_provider: str) -> Optional[str]:
        """
        Validate and normalize swap provider for swap executor.

        - If provider already has /router suffix, validates it exists
        - If provider is base name only (e.g., "jupiter"), auto-appends /router
        - Uses GATEWAY_CONNECTORS list populated at gateway startup

        Args:
            swap_provider: Swap provider from config (e.g., "jupiter/router")

        Returns:
            Normalized swap provider, or None if validation failed (executor stopped)
        """
        normalized, success = validate_and_normalize_connector(
            swap_provider, "router", self.logger().error
        )
        if not success:
            self.close_type = CloseType.FAILED
            self.stop()
            return None
        return normalized

    async def on_start(self):
        """Start executor - validates swap provider and resolves network from connector_name."""
        await super().on_start()

        # Validate and normalize swap provider (auto-append /router if needed)
        normalized_provider = self._validate_and_normalize_swap_provider(self.config.swap_provider)
        if normalized_provider is None:
            # Validation failed - executor already stopped
            return

        if normalized_provider != self.config.swap_provider:
            self.logger().info(f"Normalized swap provider: {self.config.swap_provider} -> {normalized_provider}")
            object.__setattr__(self.config, 'swap_provider', normalized_provider)

        # Resolve network from connector_name (connector_name IS the network in new architecture)
        connector = self._get_connector()
        if connector:
            self._chain = connector.chain
            self._network_name = connector.network
            self.logger().info(f"Using connector network: {self._chain}-{self._network_name}")
        else:
            # Parse network from connector_name directly (e.g., "solana-mainnet-beta")
            self._chain, self._network_name = self.parse_network(self.config.connector_name)
            self.logger().info(f"Parsed network from connector_name: {self._chain}-{self._network_name}")

    def _get_connector(self) -> Optional[Gateway]:
        """Get the connector for this swap (network connector)."""
        connector_name = self.config.connector_name
        # Try exact match first
        if connector_name in self.connectors:
            return self.connectors[connector_name]
        # Try matching by connector name pattern
        for name, conn in self.connectors.items():
            if name.startswith(connector_name):
                return conn
        return None

    async def control_task(self):
        """
        Main control loop implementing state machine.

        Transitions:
        - NOT_STARTED: Begin executing swap
        - EXECUTING: Monitor order completion
        - COMPLETED: Stop executor with success
        - FAILED: Stop executor with failure
        """
        match self._state:
            case SwapExecutorStates.NOT_STARTED:
                self._state = SwapExecutorStates.EXECUTING
                await self._execute_swap()

            case SwapExecutorStates.EXECUTING:
                # Check order status if we have an order ID
                if self._order_id:
                    await self._check_order_status()

            case SwapExecutorStates.COMPLETED:
                # Store the swap as a held position for position tracking
                self._store_held_position()
                self.close_type = CloseType.POSITION_HOLD
                self.stop()

            case SwapExecutorStates.FAILED:
                self.close_type = CloseType.FAILED
                self.stop()

    async def _fetch_quotes(
        self,
        gateway: GatewayHttpClient,
        base: str,
        quote: str,
        amount: Decimal,
        swap_providers: List[str]
    ) -> List[Dict]:
        """
        Fetch quotes from all swap_providers in parallel.

        Args:
            gateway: Gateway instance
            base: Base token symbol
            quote: Quote token symbol
            amount: Amount to swap
            swap_providers: List of providers to fetch quotes from (e.g., ["jupiter/router", "orca/clmm"])

        Returns:
            List of dicts with provider, quote, and pool_address for successful quotes
        """
        async def get_quote_for_provider(provider: str) -> Optional[Dict]:
            try:
                pool_address = None
                if "/" in provider:
                    dex_name, trading_type = provider.split("/", 1)
                else:
                    dex_name = provider
                    trading_type = "router"

                # Look up pool address for CLMM/AMM providers
                if trading_type in ("clmm", "amm"):
                    pool_info = await gateway.get_pool(
                        trading_pair=self.config.trading_pair,
                        dex=dex_name,
                        network=self._network_name,
                        trading_type=trading_type
                    )
                    pool_address = pool_info.get("address")
                    if not pool_address:
                        self.logger().debug(f"No pool found for {provider}")
                        return None

                # Fetch quote
                quote_result = await gateway.quote_swap(
                    network=self._network_name,
                    dex=dex_name,
                    trading_type=trading_type,
                    base_asset=base,
                    quote_asset=quote,
                    amount=amount,
                    side=self.config.side,
                    slippage_pct=self.config.slippage_pct,
                    pool_address=pool_address,
                    fail_silently=True
                )
                if quote_result and "error" not in quote_result:
                    self.logger().info(
                        f"Quote from {provider}: price={quote_result.get('price')}, "
                        f"amountIn={quote_result.get('amountIn')}, amountOut={quote_result.get('amountOut')}"
                    )
                    return {"provider": provider, "quote": quote_result, "pool_address": pool_address}
            except Exception as e:
                self.logger().debug(f"Quote from {provider} failed: {e}")
            return None

        # Fetch all quotes in parallel
        tasks = [get_quote_for_provider(p) for p in swap_providers]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]

    def _select_best_quote(self, quotes: List[Dict]) -> Optional[Dict]:
        """
        Select best quote based on trade side.

        For BUY: lower price is better (pay less quote to get base)
        For SELL: higher price is better (get more quote for base)
        """
        if not quotes:
            return None

        def get_price(q):
            return Decimal(str(q["quote"].get("price", 0)))

        if self.config.side == TradeType.BUY:
            return min(quotes, key=lambda q: get_price(q))
        else:
            return max(quotes, key=lambda q: get_price(q))

    async def _get_pool_address_for_provider(
        self,
        gateway: GatewayHttpClient,
        provider: str
    ) -> Optional[str]:
        """Get pool address for CLMM/AMM providers."""
        if "/" in provider:
            dex_name, trading_type = provider.split("/", 1)
        else:
            dex_name = provider
            trading_type = "router"

        # Only CLMM/AMM providers need pool address lookup
        if trading_type not in ("clmm", "amm"):
            return None

        try:
            pool_info = await gateway.get_pool(
                trading_pair=self.config.trading_pair,
                dex=dex_name,
                network=self._network_name,
                trading_type=trading_type
            )
            return pool_info.get("address")
        except Exception as e:
            self.logger().debug(f"Pool lookup failed for {provider}: {e}")
            return None

    async def _execute_swap(self):
        """Execute the swap operation using the connector's place_order method."""
        connector = self._get_connector()
        if not connector:
            self.logger().error(f"No connector found for {self.config.connector_name}")
            self._state = SwapExecutorStates.FAILED
            return

        gateway = GatewayHttpClient.get_instance()
        base, quote = self.config.trading_pair.split("-")
        amount = self.config.amount
        side = self.config.side
        trading_pair = self.config.trading_pair

        # Track if we're using flipped direction
        is_flipped = False

        try:
            # Determine swap providers for quote comparison
            swap_providers = list(self.config.additional_swap_providers or [])
            # Always include the main swap_provider
            if self.config.swap_provider not in swap_providers:
                swap_providers.insert(0, self.config.swap_provider)

            # If multiple providers, fetch quotes and select best
            selected_pool_address = None
            if len(swap_providers) > 1:
                quotes = await self._fetch_quotes(gateway, base, quote, amount, swap_providers)
                best = self._select_best_quote(quotes)

                if not best:
                    self.logger().error("No valid quotes from any swap provider")
                    self._state = SwapExecutorStates.FAILED
                    return

                self._selected_provider = best["provider"]
                selected_pool_address = best.get("pool_address")
                self.logger().info(
                    f"Selected {self._selected_provider} with price {best['quote'].get('price')} "
                    f"(from {len(quotes)} quotes)"
                )

                # If best quote is from a different provider, we need that connector
                if self._selected_provider != self.config.swap_provider:
                    self.logger().warning(
                        f"Best quote from {self._selected_provider} but using {self.config.swap_provider}. "
                        "For optimal execution, configure the controller to use the best provider."
                    )
            else:
                self._selected_provider = self.config.swap_provider
                selected_pool_address = await self._get_pool_address_for_provider(
                    gateway, self.config.swap_provider
                )

            self.logger().info(
                f"Executing swap: {side.name} {amount} {base} "
                f"on {self.config.swap_provider} (network: {self.config.connector_name})"
            )

            # Use connector's place_order method
            # This handles order tracking, events, and retry logic
            is_buy = side == TradeType.BUY

            # Get a price estimate for the order (connector will use it for tracking)
            # This also serves as a route check - will fail with NO_ROUTE_FOUND if no route
            price = Decimal("0")
            try:
                price = await connector.get_quote_price(
                    trading_pair,
                    is_buy,
                    amount,
                    self.config.slippage_pct,
                    selected_pool_address
                ) or Decimal("0")
            except Exception as e:
                error_str = str(e)
                error_code = extract_error_code(error_str)

                # Check for NO_ROUTE_FOUND - can retry with flipped direction
                if error_code == "NO_ROUTE_FOUND" or "No route" in error_str or "No routes" in error_str:
                    self.logger().warning(
                        f"No route found for {side.name} on {trading_pair}. "
                        "Retrying with flipped direction (ExactIn instead of ExactOut)..."
                    )

                    # Flip direction: BUY -> SELL on flipped pair, SELL -> BUY on flipped pair
                    flipped_pair = f"{quote}-{base}"
                    flipped_side = TradeType.SELL if side == TradeType.BUY else TradeType.BUY
                    flipped_is_buy = flipped_side == TradeType.BUY

                    # Get price for flipped direction
                    try:
                        flipped_price = await connector.get_quote_price(
                            flipped_pair,
                            flipped_is_buy,
                            amount,  # Use same amount initially to get price
                            self.config.slippage_pct,
                            selected_pool_address
                        ) or Decimal("0")

                        if flipped_price > 0:
                            # Calculate flipped amount
                            # For BUY X base that failed -> SELL (X * price) quote on flipped pair
                            # For SELL X base that failed -> BUY (X * price) quote on flipped pair
                            flipped_amount = amount * flipped_price * Decimal("1.02")  # 2% buffer

                            self.logger().info(
                                f"Flipping to: {flipped_side.name} {flipped_amount:.6f} on {flipped_pair}"
                            )

                            # Update variables for the swap
                            trading_pair = flipped_pair
                            base, quote = quote, base  # Swap base and quote
                            amount = flipped_amount
                            side = flipped_side
                            is_buy = flipped_is_buy
                            price = flipped_price
                            is_flipped = True
                        else:
                            self.logger().error("Could not get price for flipped direction")
                            self._state = SwapExecutorStates.FAILED
                            return
                    except Exception as flip_e:
                        self.logger().error(f"Flipped direction also failed: {flip_e}")
                        self._state = SwapExecutorStates.FAILED
                        return
                else:
                    self.logger().debug(f"Could not get quote price: {e}")

            # Place the order through the connector (connector handles retries internally)
            self._order_id = connector.place_order(
                is_buy=is_buy,
                trading_pair=trading_pair,
                amount=amount,
                price=price,
                pool_address=selected_pool_address,
                slippage_pct=self.config.slippage_pct,
                max_retries=self._max_retries,
            )

            flip_info = " (flipped direction)" if is_flipped else ""
            self.logger().info(f"Swap order placed: {self._order_id}{flip_info}")

        except Exception as e:
            self.logger().error(f"Failed to execute swap: {e}", exc_info=True)
            self._state = SwapExecutorStates.FAILED

    async def _check_order_status(self):
        """Check the status of the submitted order."""
        connector = self._get_connector()
        if not connector or not self._order_id:
            return

        order = connector.get_order(self._order_id)
        if not order:
            # Order not found - might have been cleaned up
            self.logger().warning(f"Order {self._order_id} not found in tracker")
            return

        # Check order state
        if order.current_state == OrderState.FILLED:
            # Order completed successfully - store order for to_json() (same pattern as order_executor)
            self._order = order
            self._exchange_order_id = order.exchange_order_id
            self._executed_amount = order.executed_amount_base or order.amount
            # Handle NaN price from market orders - use 0 if no valid price
            if order.average_executed_price is not None:
                self._executed_price = order.average_executed_price
            elif order.price is not None and not order.price.is_nan():
                self._executed_price = order.price
            # Get fee from the order's fee if available
            if order.fee_paid is not None:
                self._tx_fee = order.fee_paid
            self._state = SwapExecutorStates.COMPLETED
            self.logger().info(
                f"Swap completed: {self.config.side.name} {self._executed_amount} "
                f"at {self._executed_price}, tx={self._exchange_order_id}"
            )

        elif order.current_state == OrderState.FAILED:
            # Order failed
            self._state = SwapExecutorStates.FAILED
            self.logger().error(f"Swap order failed: {self._order_id}")

        elif order.current_state == OrderState.CANCELED:
            # Order cancelled
            self._state = SwapExecutorStates.FAILED
            self.logger().warning(f"Swap order cancelled: {self._order_id}")

    def process_order_filled_event(
        self,
        event_tag: int,
        market: ConnectorBase,
        event: OrderFilledEvent
    ):
        """Process order filled events from the connector."""
        if self._order_id and event.order_id == self._order_id:
            self._exchange_order_id = event.exchange_trade_id
            self._executed_amount = event.amount
            self._executed_price = event.price
            if event.trade_fee and event.trade_fee.flat_fees:
                self._tx_fee = sum(fee.amount for fee in event.trade_fee.flat_fees)
            self.logger().debug(f"Order filled: {event.order_id}, amount={event.amount}, price={event.price}")

    def process_order_completed_event(
        self,
        event_tag: int,
        market: ConnectorBase,
        event: Union[BuyOrderCompletedEvent, SellOrderCompletedEvent]
    ):
        """Process order completed events from the connector."""
        if self._order_id and event.order_id == self._order_id:
            self._state = SwapExecutorStates.COMPLETED
            self.logger().info(f"Order completed: {event.order_id}")

    def process_order_failed_event(
        self,
        event_tag: int,
        market: ConnectorBase,
        event: MarketOrderFailureEvent
    ):
        """Process order failed events from the connector."""
        if self._order_id and event.order_id == self._order_id:
            self._state = SwapExecutorStates.FAILED
            self.logger().error(f"Order failed: {event.order_id}")

    def _store_held_position(self):
        """Store the completed swap as a held position for position tracking.

        Uses order.to_json() when available (same pattern as order_executor).
        """
        if self._order:
            # Use order.to_json() for consistency with order_executor
            self._held_position_orders.append(self._order.to_json())
        elif self._executed_amount > 0:
            # Fallback for early_stop case where order may not be available
            self._held_position_orders.append({
                "client_order_id": self._order_id,
                "order_id": self._order_id,
                "exchange_order_id": self._exchange_order_id,
                "trading_pair": self.config.trading_pair,
                "trade_type": self.config.side.name,
                "price": float(self._executed_price),
                "amount": float(self.config.amount),
                "executed_amount_base": float(self._executed_amount),
                "executed_amount_quote": float(self._executed_amount * self._executed_price),
                "cumulative_fee_paid_quote": float(self._tx_fee),
            })

    def early_stop(self, keep_position: bool = True):
        """
        Stop the executor early.

        Args:
            keep_position: If True and swap has executed, mark as POSITION_HOLD.
                          If False, mark as EARLY_STOP regardless.
        """
        if self._state == SwapExecutorStates.COMPLETED:
            # Already completed - will be handled by control_task
            return

        if self._state == SwapExecutorStates.EXECUTING and self._executed_amount > 0 and keep_position:
            # Swap has executed some amount - treat as position hold
            self._store_held_position()
            self.close_type = CloseType.POSITION_HOLD
        else:
            self.close_type = CloseType.EARLY_STOP

        self._state = SwapExecutorStates.FAILED
        self.stop()

    # Required ExecutorBase methods

    @property
    def filled_amount_base(self) -> Decimal:
        """Returns the filled amount in base currency."""
        return self._executed_amount

    @property
    def filled_amount_quote(self) -> Decimal:
        """Returns the filled amount in quote currency."""
        return self._executed_amount * self._executed_price

    def get_net_pnl_quote(self) -> Decimal:
        """
        Returns net P&L in quote currency.

        For single swaps, P&L is not tracked as there's no entry/exit pair.
        Returns 0.
        """
        return Decimal("0")

    def get_net_pnl_pct(self) -> Decimal:
        """Returns net P&L as percentage. Always 0 for single swaps."""
        return Decimal("0")

    def get_cum_fees_quote(self) -> Decimal:
        """Returns cumulative transaction fees."""
        return self._tx_fee

    async def validate_sufficient_balance(self):
        """
        Validate sufficient balance for the swap.

        Gateway handles balance validation during execute_swap,
        so we don't need to pre-validate here.
        """
        pass

    def get_custom_info(self) -> Dict:
        """Return custom info for reporting."""
        # Use resolved network or connector_name (which is the network)
        network = f"{self._chain}-{self._network_name}" if self._chain and self._network_name else self.config.connector_name
        return {
            "state": self._state.value,
            "network": network,
            "connector_name": self.config.connector_name,
            "swap_provider": self.config.swap_provider,
            "selected_provider": self._selected_provider,
            "side": self.config.side.name,
            "amount": float(self.config.amount),
            "executed_amount": float(self._executed_amount),
            "executed_price": float(self._executed_price),
            "tx_fee": float(self._tx_fee),
            "tx_hash": self._exchange_order_id,
            "order_id": self._order_id,
            "exchange_order_id": self._exchange_order_id,
            # Position tracking fields (consistent with order_executor)
            "filled_amount_base": float(self._executed_amount),
            "filled_amount_quote": float(self._executed_amount * self._executed_price),
            "held_position_orders": self._held_position_orders,
        }
