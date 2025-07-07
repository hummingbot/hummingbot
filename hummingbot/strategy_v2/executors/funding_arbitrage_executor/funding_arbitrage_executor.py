import asyncio
import logging
from decimal import Decimal
from typing import List, Optional, Union

from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType
from hummingbot.core.data_type.order_candidate import PerpetualOrderCandidate
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    FundingPaymentCompletedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.executor_base import ExecutorBase
from hummingbot.strategy_v2.executors.funding_arbitrage_executor.data_types import FundingArbitrageExecutorConfig
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType, TrackedOrder


class FundingArbitrageExecutor(ExecutorBase):
    """
    FundingArbitrageExecutor manages a pair of opposing positions (long and short)
    on two different exchanges to capture funding rate differentials.

    This executor:
    - Opens synchronized positions on two exchanges (long on one, short on another)
    - Tracks funding payments from both positions
    - Monitors combined PnL (trade PnL + funding PnL)
    - Closes positions based on risk controls (TP/SL/duration)
    """

    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 strategy: ScriptStrategyBase,
                 config: FundingArbitrageExecutorConfig,
                 update_interval: float = 1.0,
                 max_retries: int = 10):
        """
        Initialize the FundingArbitrageExecutor.

        :param strategy: The strategy to be used by the executor
        :param config: Configuration for the funding arbitrage executor
        :param update_interval: How often to run the control loop (seconds)
        :param max_retries: Maximum number of retries for failed operations
        """
        super().__init__(
            strategy=strategy,
            connectors=[config.long_market.connector_name, config.short_market.connector_name],
            config=config,
            update_interval=update_interval
        )

        self.config: FundingArbitrageExecutorConfig = config
        self._max_retries = max_retries
        self._current_retries = 0

        # Order tracking - simplified approach following PositionExecutor pattern
        self._long_order: TrackedOrder = TrackedOrder()
        self._short_order: TrackedOrder = TrackedOrder()
        self._long_close_order: Optional[TrackedOrder] = None
        self._short_close_order: Optional[TrackedOrder] = None

        # Failed orders tracking
        self._failed_orders: List[TrackedOrder] = []

        # PnL tracking
        self._trade_pnl_quote = Decimal("0")
        self._realized_pnl_quote = Decimal("0")
        self._funding_payments: list = []
        self._cumulative_funding_pnl = Decimal("0")

        # Timing controls for cooldown
        self._last_order_time: Optional[float] = None
        self._order_cooldown_seconds = 2.0

        # Asymmetric fill tracking and timeout
        self._asymmetric_fill_start_time: Optional[float] = None
        self._asymmetric_fill_timeout_seconds = config.asymmetric_fill_timeout_seconds

        # Position tracking
        self._start_timestamp = strategy.current_timestamp

        # Leverage setup tracking
        self._leverage_setup_complete = False
        self._leverage_setup_attempts = 0
        self._max_leverage_setup_attempts = 3

        # Cancellation tracking to prevent duplicate requests
        self._pending_cancellations = set()  # Track order IDs pending cancellation

    @property
    def long_order(self) -> TrackedOrder:
        """The long position order"""
        return self._long_order

    @property
    def short_order(self) -> TrackedOrder:
        """The short position order"""
        return self._short_order

    @property
    def trade_pnl_quote(self) -> Decimal:
        """Current trade PnL in quote currency"""
        return self._trade_pnl_quote

    @property
    def funding_pnl_quote(self) -> Decimal:
        """Cumulative funding PnL in quote currency"""
        return self._cumulative_funding_pnl

    @property
    def realized_pnl_quote(self) -> Decimal:
        """Realized PnL in quote currency from completed orders"""
        return self._realized_pnl_quote

    @property
    def total_pnl_quote(self) -> Decimal:
        """Total PnL (trade + realized + funding) in quote currency"""
        return self.trade_pnl_quote + self.realized_pnl_quote + self.funding_pnl_quote

    @property
    def position_age_seconds(self) -> float:
        """Age of the position in seconds"""
        if not self.is_position_active:
            return 0.0

        # Get creation timestamps from orders (with fallback)
        long_timestamp = (self._long_order.creation_timestamp
                          if self._long_order.creation_timestamp else self._strategy.current_timestamp)
        short_timestamp = (self._short_order.creation_timestamp
                           if self._short_order.creation_timestamp else self._strategy.current_timestamp)

        return self._strategy.current_timestamp - min(long_timestamp, short_timestamp)

    @property
    def is_position_active(self) -> bool:
        """Check if both legs of the arbitrage position are active"""
        return (self._long_order.is_filled and
                self._short_order.is_filled)

    @property
    def entry_orders_partially_filled(self) -> bool:
        """Check if entry orders have asymmetric fills (one side filled, other not)"""
        # Simple check: one side filled, other not filled
        return ((self._long_order.is_filled and not self._short_order.is_filled) or
                (self._short_order.is_filled and not self._long_order.is_filled))

    @property
    def all_close_orders_completed(self) -> bool:
        """Check if all close orders have been completed"""
        long_closed = (self._long_close_order is None or
                       (self._long_close_order.order and bool(self._long_close_order.order.is_filled)))
        short_closed = (self._short_close_order is None or
                        (self._short_close_order.order and bool(self._short_close_order.order.is_filled)))
        return bool(long_closed and short_closed)

    def get_net_pnl_quote(self) -> Decimal:
        """
        Returns the net profit or loss in quote currency.
        Includes trade PnL, realized PnL, and funding payments minus trading fees.
        """
        return self.total_pnl_quote - self.get_cum_fees_quote()

    def get_net_pnl_pct(self) -> Decimal:
        """
        Returns the net profit or loss as a percentage.
        Based on the position size in quote currency.
        """
        if self.config.position_size_quote > 0:
            return self.total_pnl_quote / self.config.position_size_quote
        return Decimal("0")

    async def validate_sufficient_balance(self) -> bool:
        """
        Validate that both connectors have sufficient balance for the planned positions.
        Uses OrderCandidate pattern for accurate validation and stores adjusted amounts.
        """
        try:
            # Get current prices for amount calculations
            long_price = self.get_price(
                self.config.long_market.connector_name,
                self.config.long_market.trading_pair
            )
            short_price = self.get_price(
                self.config.short_market.connector_name,
                self.config.short_market.trading_pair
            )

            if not long_price or not short_price:
                self.logger().warning("Unable to get current prices for balance validation")
                return False

            # Calculate base amounts needed
            long_base_amount = self.config.position_size_quote / long_price
            short_base_amount = self.config.position_size_quote / short_price

            # Get trading rules for minimum size validation
            long_trading_rules = self.get_trading_rules(
                self.config.long_market.connector_name,
                self.config.long_market.trading_pair
            )
            short_trading_rules = self.get_trading_rules(
                self.config.short_market.connector_name,
                self.config.short_market.trading_pair
            )

            # Validate minimum sizes before creating order candidates
            long_notional = long_base_amount * long_price
            short_notional = short_base_amount * short_price

            if long_base_amount < long_trading_rules.min_order_size:
                self.logger().error(f"Long base amount {long_base_amount} below minimum {long_trading_rules.min_order_size}")
                return False

            if long_notional < long_trading_rules.min_notional_size:
                self.logger().error(f"Long notional {long_notional} below minimum {long_trading_rules.min_notional_size}")
                return False

            if short_base_amount < short_trading_rules.min_order_size:
                self.logger().error(f"Short base amount {short_base_amount} below minimum {short_trading_rules.min_order_size}")
                return False

            if short_notional < short_trading_rules.min_notional_size:
                self.logger().error(f"Short notional {short_notional} below minimum {short_trading_rules.min_notional_size}")
                return False

            # Create OrderCandidates for validation - using limit orders
            long_order_candidate = PerpetualOrderCandidate(
                trading_pair=self.config.long_market.trading_pair,
                is_maker=True,
                order_type=OrderType.LIMIT_MAKER,
                order_side=TradeType.BUY,
                amount=long_base_amount,
                price=long_price,
                leverage=self.config.leverage,
            )

            short_order_candidate = PerpetualOrderCandidate(
                trading_pair=self.config.short_market.trading_pair,
                is_maker=True,
                order_type=OrderType.LIMIT_MAKER,
                order_side=TradeType.SELL,
                amount=short_base_amount,
                price=short_price,
                leverage=self.config.leverage,
            )

            # Validate balances using adjust_order_candidates
            long_adjusted = self.adjust_order_candidates(
                self.config.long_market.connector_name,
                [long_order_candidate]
            )
            short_adjusted = self.adjust_order_candidates(
                self.config.short_market.connector_name,
                [short_order_candidate]
            )

            if not long_adjusted or long_adjusted[0].amount == Decimal("0"):
                self.logger().error(f"Insufficient balance on {self.config.long_market.connector_name} "
                                    f"for long position of {long_base_amount}")
                return False

            if not short_adjusted or short_adjusted[0].amount == Decimal("0"):
                self.logger().error(f"Insufficient balance on {self.config.short_market.connector_name} "
                                    f"for short position of {short_base_amount}")
                return False

            # Store adjusted amounts for use in actual order placement
            self._validated_long_amount = long_adjusted[0].amount
            self._validated_short_amount = short_adjusted[0].amount
            self._validated_long_price = long_adjusted[0].price
            self._validated_short_price = short_adjusted[0].price

            self.logger().info(f"Balance validation successful - Adjusted amounts: Long={self._validated_long_amount}, Short={self._validated_short_amount}")
            return True

        except Exception as e:
            self.logger().error(f"Error during balance validation: {e}")
            return False

    async def control_task(self):
        """Control task that manages the executor lifecycle using simplified approach"""
        if self.status == RunnableStatus.RUNNING:
            # Setup leverage first if not done
            if not self._leverage_setup_complete:
                await self._setup_leverage()
            else:
                self.control_open_orders()
                self.control_barriers()
        elif self.status == RunnableStatus.SHUTTING_DOWN:
            await self._control_shutdown_process()
        self.evaluate_max_retries()

    def control_open_orders(self):
        """Control the placement and management of open orders"""
        # Control each order independently
        self.control_long_order()
        self.control_short_order()

        # Monitor existing orders and renew if needed
        self._monitor_existing_orders()

    def control_long_order(self):
        """Control the long order independently"""
        current_time = self._strategy.current_timestamp
        cooldown_remaining = 0
        if self._last_order_time:
            cooldown_remaining = max(0, self._order_cooldown_seconds - (current_time - self._last_order_time))

        if not self._long_order.order_id:
            self.logger().debug(f"Long order missing - cooldown remaining: {cooldown_remaining:.1f}s")
            # Check if we should place a new long order
            if self._can_place_orders():
                # Check for asymmetric fill requiring aggressive hedge
                if self._short_order.is_filled and not self._long_order.order_id:
                    self.logger().info("Asymmetric fill detected: short filled, placing aggressive long hedge")
                    self._place_aggressive_long_hedge()
                else:
                    # Normal case: place both orders (if this is the first control call)
                    if not self._short_order.order_id:
                        self.logger().info("Placing initial order pair")
                        self.place_open_orders()
                    else:
                        self.logger().debug("Short order exists, waiting for individual long placement logic")
            else:
                self.logger().debug(f"Cannot place orders yet - cooldown: {cooldown_remaining:.1f}s")
        else:
            # Monitor existing long order
            long_status = "filled" if self._long_order.is_filled else ("open" if self._long_order.order and self._long_order.order.is_open else "unknown")
            self.logger().debug(f"Long order {self._long_order.order_id} status: {long_status}")
            self._monitor_long_order()

    def control_short_order(self):
        """Control the short order independently"""
        current_time = self._strategy.current_timestamp
        cooldown_remaining = 0
        if self._last_order_time:
            cooldown_remaining = max(0, self._order_cooldown_seconds - (current_time - self._last_order_time))

        if not self._short_order.order_id:
            self.logger().debug(f"Short order missing - cooldown remaining: {cooldown_remaining:.1f}s")
            # Check if we should place a new short order
            if self._can_place_orders():
                # Check for asymmetric fill requiring aggressive hedge
                if self._long_order.is_filled and not self._short_order.order_id:
                    self.logger().info("Asymmetric fill detected: long filled, placing aggressive short hedge")
                    self._place_aggressive_short_hedge()
                else:
                    # Normal case handled in control_long_order to avoid duplication
                    self.logger().debug("Normal case handled in control_long_order")
            else:
                self.logger().debug(f"Cannot place orders yet - cooldown: {cooldown_remaining:.1f}s")
        else:
            # Monitor existing short order
            short_status = "filled" if self._short_order.is_filled else ("open" if self._short_order.order and self._short_order.order.is_open else "unknown")
            self.logger().debug(f"Short order {self._short_order.order_id} status: {short_status}")
            self._monitor_short_order()

    def control_barriers(self):
        """Control risk management barriers (take profit, stop loss, time limit)"""
        if self.is_position_active:
            self._update_trade_pnl()
            self._check_exit_conditions()

    def _can_place_orders(self) -> bool:
        """Check if orders can be placed (cooldown and validation)"""
        current_time = self._strategy.current_timestamp

        # Check cooldown
        if (self._last_order_time and
                current_time - self._last_order_time < self._order_cooldown_seconds):
            return False

        return True

    def place_open_orders(self):
        """Place normal limit orders for both long and short positions (non-asymmetric case)"""
        try:
            # Get current prices for limit order placement
            long_price_raw = self.get_price(
                self.config.long_market.connector_name,
                self.config.long_market.trading_pair
            )
            short_price_raw = self.get_price(
                self.config.short_market.connector_name,
                self.config.short_market.trading_pair
            )

            if not long_price_raw or not short_price_raw:
                self.logger().warning("Unable to get current prices for order placement")
                return

            # Quantize prices to 5 decimal precision like Hyperliquid connector
            long_price = Decimal(round(float(f"{long_price_raw:.5g}"), 5))
            short_price = Decimal(round(float(f"{short_price_raw:.5g}"), 5))

            self.logger().info(f"Placing normal orders - Long price: {long_price_raw} -> {long_price}, Short price: {short_price_raw} -> {short_price}")

            # Use validated amounts if available, otherwise calculate from config
            if hasattr(self, '_validated_long_amount') and hasattr(self, '_validated_short_amount'):
                long_amount = self._validated_long_amount
                short_amount = self._validated_short_amount
                self.logger().info(f"Using validated amounts - Long: {long_amount}, Short: {short_amount}")
            else:
                # Fallback to calculated amounts using quantized prices
                long_amount = self.config.position_size_quote / long_price
                short_amount = self.config.position_size_quote / short_price
                self.logger().info(f"Calculated amounts - Long: {long_amount}, Short: {short_amount}")

            # Normal case: place both orders with conservative spread on quantized prices
            spread_bps = self.config.entry_limit_order_spread_bps
            spread_pct = Decimal(str(spread_bps)) / Decimal("10000")

            # Apply spread to quantized prices
            long_limit_price = long_price * (Decimal("1") - spread_pct)  # Buy below market
            short_limit_price = short_price * (Decimal("1") + spread_pct)  # Sell above market

            self.logger().info(f"Order prices with {spread_bps} bps spread - Long: {long_limit_price}, Short: {short_limit_price}")

            # Place long order (buy) only if not already present
            if not self._long_order.order_id:
                long_order_id = self.place_order(
                    connector_name=self.config.long_market.connector_name,
                    trading_pair=self.config.long_market.trading_pair,
                    order_type=OrderType.LIMIT_MAKER,
                    side=TradeType.BUY,
                    amount=long_amount,
                    price=long_limit_price,
                    position_action=PositionAction.OPEN
                )

                if long_order_id:
                    self._long_order.order_id = long_order_id
                    self.logger().info(f"Long limit order placed: {long_order_id} at {long_limit_price}")
                else:
                    self.logger().error("Failed to place long order - order_id is None")
            else:
                self.logger().debug(f"Long order already exists: {self._long_order.order_id}")

            # Place short order (sell) only if not already present
            if not self._short_order.order_id:
                short_order_id = self.place_order(
                    connector_name=self.config.short_market.connector_name,
                    trading_pair=self.config.short_market.trading_pair,
                    order_type=OrderType.LIMIT_MAKER,
                    side=TradeType.SELL,
                    amount=short_amount,
                    price=short_limit_price,
                    position_action=PositionAction.OPEN
                )

                if short_order_id:
                    self._short_order.order_id = short_order_id
                    self.logger().info(f"Short limit order placed: {short_order_id} at {short_limit_price}")
                else:
                    self.logger().error("Failed to place short order - order_id is None")
            else:
                self.logger().debug(f"Short order already exists: {self._short_order.order_id}")

            self._last_order_time = self._strategy.current_timestamp

        except Exception as e:
            self.logger().error(f"Error placing open orders: {e}")
            self._current_retries += 1

    def _monitor_existing_orders(self):
        """Monitor existing orders and renew if market has moved significantly"""
        try:
            renewal_threshold = self.config.order_renewal_threshold_pct

            # Check long order
            if (self._long_order.order_id and
                self._long_order.order and
                    self._long_order.order.is_open):

                current_price = self.get_price(
                    self.config.long_market.connector_name,
                    self.config.long_market.trading_pair
                )

                if current_price:
                    price_diff_pct = abs(current_price - self._long_order.order.price) / current_price
                    if price_diff_pct > renewal_threshold:
                        self._renew_long_order()

            # Check short order
            if (self._short_order.order_id and
                self._short_order.order and
                    self._short_order.order.is_open):

                current_price = self.get_price(
                    self.config.short_market.connector_name,
                    self.config.short_market.trading_pair
                )

                if current_price:
                    price_diff_pct = abs(current_price - self._short_order.order.price) / current_price
                    if price_diff_pct > renewal_threshold:
                        self._renew_short_order()

        except Exception as e:
            self.logger().error(f"Error monitoring existing orders: {e}")

    def _renew_long_order(self):
        """Cancel and replace long order with updated price"""
        if self._can_place_orders():
            self.cancel_long_order()
            # New order will be placed in next control loop iteration

    def _renew_short_order(self):
        """Cancel and replace short order with updated price"""
        if self._can_place_orders():
            self.cancel_short_order()
            # New order will be placed in next control loop iteration

    def _monitor_long_order(self):
        """Monitor the long order for renewal needs"""
        if (self._long_order.order_id and
            self._long_order.order and
                self._long_order.order.is_open):

            current_price = self.get_price(
                self.config.long_market.connector_name,
                self.config.long_market.trading_pair
            )

            if current_price:
                renewal_threshold = self.config.order_renewal_threshold_pct
                price_diff_pct = abs(current_price - self._long_order.order.price) / current_price
                if price_diff_pct > renewal_threshold:
                    self.logger().info(f"Long order price difference {price_diff_pct:.4%} exceeds threshold {renewal_threshold:.4%}, renewing")
                    self._renew_long_order()

    def _monitor_short_order(self):
        """Monitor the short order for renewal needs"""
        if (self._short_order.order_id and
            self._short_order.order and
                self._short_order.order.is_open):

            current_price = self.get_price(
                self.config.short_market.connector_name,
                self.config.short_market.trading_pair
            )

            if current_price:
                renewal_threshold = self.config.order_renewal_threshold_pct
                price_diff_pct = abs(current_price - self._short_order.order.price) / current_price
                if price_diff_pct > renewal_threshold:
                    self.logger().info(f"Short order price difference {price_diff_pct:.4%} exceeds threshold {renewal_threshold:.4%}, renewing")
                    self._renew_short_order()

    def _place_aggressive_long_hedge(self):
        """Place aggressive long hedge order for asymmetric fill recovery"""
        try:
            long_price_raw = self.get_price(
                self.config.long_market.connector_name,
                self.config.long_market.trading_pair
            )

            if not long_price_raw:
                self.logger().warning("Unable to get long price for aggressive hedge")
                return

            # Quantize price to 5 decimal precision
            long_price = Decimal(round(float(f"{long_price_raw:.5g}"), 5))

            # Use validated amount if available
            if hasattr(self, '_validated_long_amount'):
                long_amount = self._validated_long_amount
            else:
                long_amount = self.config.position_size_quote / long_price

            # Use aggressive 1 bps spread for quick fill on quantized price
            aggressive_spread_pct = Decimal("0.0001")  # 1 bps = 0.01%
            long_limit_price = long_price * (Decimal("1") - aggressive_spread_pct)  # Buy below market

            long_order_id = self.place_order(
                connector_name=self.config.long_market.connector_name,
                trading_pair=self.config.long_market.trading_pair,
                order_type=OrderType.LIMIT_MAKER,
                side=TradeType.BUY,
                amount=long_amount,
                price=long_limit_price,
                position_action=PositionAction.OPEN
            )

            if long_order_id:
                self._long_order.order_id = long_order_id
                self.logger().info(f"Aggressive long hedge placed: {long_order_id} at {long_limit_price}")
                self._last_order_time = self._strategy.current_timestamp

        except Exception as e:
            self.logger().error(f"Error placing aggressive long hedge: {e}")
            self._current_retries += 1

    def _place_aggressive_short_hedge(self):
        """Place aggressive short hedge order for asymmetric fill recovery"""
        try:
            short_price_raw = self.get_price(
                self.config.short_market.connector_name,
                self.config.short_market.trading_pair
            )

            if not short_price_raw:
                self.logger().warning("Unable to get short price for aggressive hedge")
                return

            # Quantize price to 5 decimal precision
            short_price = Decimal(round(float(f"{short_price_raw:.5g}"), 5))

            # Use validated amount if available
            if hasattr(self, '_validated_short_amount'):
                short_amount = self._validated_short_amount
            else:
                short_amount = self.config.position_size_quote / short_price

            # Use aggressive 1 bps spread for quick fill on quantized price
            aggressive_spread_pct = Decimal("0.0001")  # 1 bps = 0.01%
            short_limit_price = short_price * (Decimal("1") + aggressive_spread_pct)  # Sell above market

            short_order_id = self.place_order(
                connector_name=self.config.short_market.connector_name,
                trading_pair=self.config.short_market.trading_pair,
                order_type=OrderType.LIMIT_MAKER,
                side=TradeType.SELL,
                amount=short_amount,
                price=short_limit_price,
                position_action=PositionAction.OPEN
            )

            if short_order_id:
                self._short_order.order_id = short_order_id
                self.logger().info(f"Aggressive short hedge placed: {short_order_id} at {short_limit_price}")
                self._last_order_time = self._strategy.current_timestamp

        except Exception as e:
            self.logger().error(f"Error placing aggressive short hedge: {e}")
            self._current_retries += 1

    def cancel_long_order(self):
        """Cancel the long order"""
        if self._long_order.order_id:
            order = self.get_in_flight_order(
                self.config.long_market.connector_name,
                self._long_order.order_id
            )
            if order and order.is_open:
                self._strategy.cancel(
                    connector_name=self.config.long_market.connector_name,
                    trading_pair=self.config.long_market.trading_pair,
                    order_id=self._long_order.order_id
                )
                self.logger().info(f"Cancelling long order {self._long_order.order_id}")
                # NOTE: Order state will be cleared in process_order_canceled_event() when exchange confirms cancellation

    def cancel_short_order(self):
        """Cancel the short order"""
        if self._short_order.order_id:
            order = self.get_in_flight_order(
                self.config.short_market.connector_name,
                self._short_order.order_id
            )
            if order and order.is_open:
                self._strategy.cancel(
                    connector_name=self.config.short_market.connector_name,
                    trading_pair=self.config.short_market.trading_pair,
                    order_id=self._short_order.order_id
                )
                self.logger().info(f"Cancelling short order {self._short_order.order_id}")
                # NOTE: Order state will be cleared in process_order_canceled_event() when exchange confirms cancellation

    def cancel_all_open_orders(self):
        """Cancel all open orders"""
        self.cancel_long_order()
        self.cancel_short_order()

    def _check_exit_conditions(self):
        """Check various exit conditions for the position"""
        # Check if we have any position to monitor (full or asymmetric)
        if not self.is_position_active and not self.entry_orders_partially_filled:
            return

        # Update PnL for any filled positions
        if self.is_position_active or self.entry_orders_partially_filled:
            self._update_trade_pnl()

        # Check asymmetric fill timeout
        if self.entry_orders_partially_filled:
            self._check_asymmetric_fill_timeout()

        # Take profit check (applies to both full and asymmetric positions)
        if self.config.take_profit_pct:
            total_pnl_pct = self.total_pnl_quote / self.config.position_size_quote
            self.logger().debug(f"Take profit check: PnL={self.total_pnl_quote:.6f}, Position Size={self.config.position_size_quote:.6f}, PnL%={total_pnl_pct:.4%}, Threshold={self.config.take_profit_pct:.4%}")
            if total_pnl_pct >= self.config.take_profit_pct:
                self.logger().info(f"Take profit triggered: {total_pnl_pct:.4%} >= {self.config.take_profit_pct:.4%}")
                self.logger().info(f"PnL breakdown - Trade: {self.trade_pnl_quote:.6f}, Realized: {self.realized_pnl_quote:.6f}, Funding: {self.funding_pnl_quote:.6f}, Fees: {self.get_cum_fees_quote():.6f}, Net: {self.get_net_pnl_quote():.6f}")
                self.close_type = CloseType.TAKE_PROFIT
                self.place_close_orders()

        # Stop loss check (applies to both full and asymmetric positions)
        if self.config.stop_loss_pct:
            total_pnl_pct = self.total_pnl_quote / self.config.position_size_quote
            self.logger().debug(f"Stop loss check: PnL={self.total_pnl_quote:.6f}, Position Size={self.config.position_size_quote:.6f}, PnL%={total_pnl_pct:.4%}, Threshold={-self.config.stop_loss_pct:.4%}")
            if total_pnl_pct <= -self.config.stop_loss_pct:
                self.logger().info(f"Stop loss triggered: {total_pnl_pct:.4%} <= {-self.config.stop_loss_pct:.4%}")
                self.logger().info(f"PnL breakdown - Trade: {self.trade_pnl_quote:.6f}, Realized: {self.realized_pnl_quote:.6f}, Funding: {self.funding_pnl_quote:.6f}, Fees: {self.get_cum_fees_quote():.6f}, Net: {self.get_net_pnl_quote():.6f}")
                self.close_type = CloseType.STOP_LOSS
                self.place_close_orders()

        # Time limit check (applies to both full and asymmetric positions)
        if self.config.max_position_duration_seconds:
            if self.position_age_seconds >= self.config.max_position_duration_seconds:
                self.logger().info(f"Position duration limit reached: {self.position_age_seconds}s")
                self.close_type = CloseType.TIME_LIMIT
                self.place_close_orders()

        # Funding rate deterioration check (only applies to full positions)
        if self.is_position_active:
            self._check_funding_rate_deterioration()

    def _check_funding_rate_deterioration(self):
        """Monitor funding rate deterioration and close position if needed"""
        try:
            # Get current funding rates
            long_funding_info = self.connectors[self.config.long_market.connector_name].get_funding_info(
                self.config.long_market.trading_pair
            )
            short_funding_info = self.connectors[self.config.short_market.connector_name].get_funding_info(
                self.config.short_market.trading_pair
            )

            if not long_funding_info or not short_funding_info:
                return

            # Calculate current differential (short - long for profitable arbitrage)
            current_differential = short_funding_info.rate - long_funding_info.rate

            # Check for deterioration below configured threshold
            if current_differential < self.config.min_funding_rate_differential:
                self.logger().info(f"Funding rate differential deteriorated to {current_differential:.6f}, "
                                   f"below threshold {self.config.min_funding_rate_differential:.6f}")
                self.close_type = CloseType.STOP_LOSS
                self.place_close_orders()

        except Exception as e:
            self.logger().error(f"Error monitoring funding rate deterioration: {e}")

    def _check_asymmetric_fill_timeout(self):
        """Check and handle asymmetric fill timeout"""
        current_time = self._strategy.current_timestamp

        # Start tracking asymmetric fill time if not already started
        if self._asymmetric_fill_start_time is None:
            self._asymmetric_fill_start_time = current_time
            self.logger().info("Asymmetric fill detected - starting timeout timer")
            return

        # Check if timeout has been reached
        time_elapsed = current_time - self._asymmetric_fill_start_time
        if time_elapsed >= self._asymmetric_fill_timeout_seconds:
            self.logger().warning(f"Asymmetric fill timeout reached after {time_elapsed:.1f}s - closing positions gracefully")
            self.close_type = CloseType.TIME_LIMIT
            self.place_close_orders()

    def place_close_orders(self):
        """Place market orders to close both positions"""
        self.cancel_all_open_orders()

        try:
            # Close long position (sell)
            if self._long_order.is_filled:
                long_close_order_id = self.place_order(
                    connector_name=self.config.long_market.connector_name,
                    trading_pair=self.config.long_market.trading_pair,
                    order_type=OrderType.MARKET,
                    side=TradeType.SELL,
                    amount=self._long_order.executed_amount_base,
                    price=Decimal("NaN"),
                    position_action=PositionAction.CLOSE
                )

                if long_close_order_id:
                    self._long_close_order = TrackedOrder(order_id=long_close_order_id)
                    self.logger().info(f"Long close order placed: {long_close_order_id}")

            # Close short position (buy)
            if self._short_order.is_filled:
                short_close_order_id = self.place_order(
                    connector_name=self.config.short_market.connector_name,
                    trading_pair=self.config.short_market.trading_pair,
                    order_type=OrderType.MARKET,
                    side=TradeType.BUY,
                    amount=self._short_order.executed_amount_base,
                    price=Decimal("NaN"),
                    position_action=PositionAction.CLOSE
                )

                if short_close_order_id:
                    self._short_close_order = TrackedOrder(order_id=short_close_order_id)
                    self.logger().info(f"Short close order placed: {short_close_order_id}")

            self._status = RunnableStatus.SHUTTING_DOWN
            self.close_timestamp = self._strategy.current_timestamp

        except Exception as e:
            self.logger().error(f"Error placing close orders: {e}")
            self._current_retries += 1

    def _update_trade_pnl(self):
        """Update the current trade PnL based on positions (full or asymmetric)"""
        try:
            # Initialize PnL components
            long_pnl = Decimal("0")
            short_pnl = Decimal("0")

            # Calculate long position unrealized PnL
            if self._long_order.is_filled:
                current_long_price = self.get_price(
                    self.config.long_market.connector_name,
                    self.config.long_market.trading_pair
                )
                if current_long_price and self._long_order.average_executed_price:
                    # Long PnL = (current_price - entry_price) * amount
                    long_pnl = (current_long_price - self._long_order.average_executed_price) * self._long_order.executed_amount_base
                    self.logger().debug(f"Long PnL: ({current_long_price} - {self._long_order.average_executed_price}) * {self._long_order.executed_amount_base} = {long_pnl}")

            # Calculate short position unrealized PnL
            if self._short_order.is_filled:
                current_short_price = self.get_price(
                    self.config.short_market.connector_name,
                    self.config.short_market.trading_pair
                )
                if current_short_price and self._short_order.average_executed_price:
                    # Short PnL = (entry_price - current_price) * amount
                    short_pnl = (self._short_order.average_executed_price - current_short_price) * self._short_order.executed_amount_base
                    self.logger().debug(f"Short PnL: ({self._short_order.average_executed_price} - {current_short_price}) * {self._short_order.executed_amount_base} = {short_pnl}")

            # Total unrealized PnL
            self._trade_pnl_quote = long_pnl + short_pnl
            self.logger().debug(f"Total unrealized PnL: {long_pnl} + {short_pnl} = {self._trade_pnl_quote}")

        except Exception as e:
            self.logger().error(f"Error updating trade PnL: {e}")
            self._trade_pnl_quote = Decimal("0")

    async def _setup_leverage(self):
        """Setup leverage on both exchanges before placing orders"""
        try:
            self._leverage_setup_attempts += 1

            # Check if both connectors are perpetual
            long_connector = self.connectors.get(self.config.long_market.connector_name)
            short_connector = self.connectors.get(self.config.short_market.connector_name)

            if not long_connector or not short_connector:
                self.logger().error("One or both connectors not available for leverage setup")
                return

            # Check if connectors support leverage (are perpetual)
            long_is_perpetual = hasattr(long_connector, 'set_leverage')
            short_is_perpetual = hasattr(short_connector, 'set_leverage')

            if not long_is_perpetual or not short_is_perpetual:
                self.logger().warning("One or both connectors do not support leverage - skipping leverage setup")
                self._leverage_setup_complete = True
                return

            # Set leverage on long market
            current_long_leverage = long_connector.get_leverage(self.config.long_market.trading_pair)
            if current_long_leverage != self.config.leverage:
                self.logger().info(f"Setting leverage on {self.config.long_market.connector_name} from {current_long_leverage} to {self.config.leverage}")
                long_connector.set_leverage(self.config.long_market.trading_pair, self.config.leverage)

            # Set leverage on short market
            current_short_leverage = short_connector.get_leverage(self.config.short_market.trading_pair)
            if current_short_leverage != self.config.leverage:
                self.logger().info(f"Setting leverage on {self.config.short_market.connector_name} from {current_short_leverage} to {self.config.leverage}")
                short_connector.set_leverage(self.config.short_market.trading_pair, self.config.leverage)

            # Wait a moment for leverage to be applied
            await asyncio.sleep(2.0)

            # Verify leverage was set correctly
            final_long_leverage = long_connector.get_leverage(self.config.long_market.trading_pair)
            final_short_leverage = short_connector.get_leverage(self.config.short_market.trading_pair)

            if final_long_leverage == self.config.leverage and final_short_leverage == self.config.leverage:
                self.logger().info(f"Leverage setup complete: Long={final_long_leverage}x, Short={final_short_leverage}x")
                self._leverage_setup_complete = True
            else:
                self.logger().warning(f"Leverage verification failed: Long={final_long_leverage}x (expected {self.config.leverage}x), Short={final_short_leverage}x (expected {self.config.leverage}x)")

                # Retry if we haven't exceeded max attempts
                if self._leverage_setup_attempts >= self._max_leverage_setup_attempts:
                    self.logger().error(f"Failed to setup leverage after {self._max_leverage_setup_attempts} attempts - proceeding anyway")
                    self._leverage_setup_complete = True

        except Exception as e:
            self.logger().error(f"Error setting up leverage: {e}")
            if self._leverage_setup_attempts >= self._max_leverage_setup_attempts:
                self.logger().error("Max leverage setup attempts reached - proceeding without leverage verification")
                self._leverage_setup_complete = True

    def _validate_leverage_before_orders(self) -> bool:
        """Validate that leverage is correctly set before placing orders"""
        try:
            if not self._leverage_setup_complete:
                self.logger().warning("Leverage setup not complete - skipping order placement")
                return False

            # Check current leverage on both exchanges
            long_connector = self.connectors.get(self.config.long_market.connector_name)
            short_connector = self.connectors.get(self.config.short_market.connector_name)

            if not long_connector or not short_connector:
                return False

            # Skip validation if connectors don't support leverage
            if not hasattr(long_connector, 'get_leverage') or not hasattr(short_connector, 'get_leverage'):
                return True

            long_leverage = long_connector.get_leverage(self.config.long_market.trading_pair)
            short_leverage = short_connector.get_leverage(self.config.short_market.trading_pair)

            if long_leverage != self.config.leverage or short_leverage != self.config.leverage:
                self.logger().warning(f"Leverage mismatch detected: Long={long_leverage}x, Short={short_leverage}x, Expected={self.config.leverage}x")
                self._leverage_setup_complete = False  # Trigger re-setup
                return False

            return True

        except Exception as e:
            self.logger().error(f"Error validating leverage: {e}")
            return False

    def evaluate_max_retries(self):
        """
        This method is responsible for evaluating the maximum number of retries to place an order and stop the executor
        if the maximum number of retries is reached.

        :return: None
        """
        if self._current_retries > self._max_retries:
            self.close_type = CloseType.FAILED
            self.stop()

    async def _control_shutdown_process(self):
        """Control the shutdown process"""
        if not self.all_close_orders_completed:
            self.close_type = CloseType.FAILED
            self.stop()

    def close_execution_by(self, close_type):
        """Close execution with specified close type"""
        self.close_type = close_type

    def early_stop(self, keep_position: bool = False):
        """Stop the executor early"""
        if keep_position:
            self.logger().info("Early stop requested with position preservation")
            self.stop()
        else:
            self.logger().info("Early stop requested, closing positions")
            self.close_type = CloseType.EARLY_STOP

    def update_tracked_orders_with_order_id(self, order_id: str):
        """
        Update the tracked orders with the information from the InFlightOrder, using
        the order_id as a reference.

        :param order_id: The order_id to be used as a reference.
        :return: None
        """
        # Get InFlightOrder for long market
        if self._long_order and self._long_order.order_id == order_id:
            in_flight_order = self.get_in_flight_order(self.config.long_market.connector_name, order_id)
            if in_flight_order:
                self._long_order.order = in_flight_order

        # Get InFlightOrder for short market
        elif self._short_order and self._short_order.order_id == order_id:
            in_flight_order = self.get_in_flight_order(self.config.short_market.connector_name, order_id)
            if in_flight_order:
                self._short_order.order = in_flight_order

        # Get InFlightOrder for long close order
        elif self._long_close_order and self._long_close_order.order_id == order_id:
            in_flight_order = self.get_in_flight_order(self.config.long_market.connector_name, order_id)
            if in_flight_order:
                self._long_close_order.order = in_flight_order

        # Get InFlightOrder for short close order
        elif self._short_close_order and self._short_close_order.order_id == order_id:
            in_flight_order = self.get_in_flight_order(self.config.short_market.connector_name, order_id)
            if in_flight_order:
                self._short_close_order.order = in_flight_order

    def process_order_created_event(self, _event_tag, _market, event: Union[BuyOrderCreatedEvent, SellOrderCreatedEvent]):
        """
        Process order created events. Updates TrackedOrder with the InFlightOrder information
        using the order_id as a reference.
        """
        self.update_tracked_orders_with_order_id(event.order_id)

    def process_order_filled_event(self, _event_tag, _market, event: OrderFilledEvent):
        """
        Process order filled events. Updates TrackedOrder with the InFlightOrder information
        and handles PnL tracking for fills.
        """
        order_id = event.order_id

        self.logger().info(f"Order fill confirmed: {order_id} - Amount: {event.amount}, Price: {event.price}")

        # Update tracked order with latest information
        self.update_tracked_orders_with_order_id(order_id)

        # Log fill details and check for asymmetric state
        if order_id == self._long_order.order_id:
            self.logger().info(f"Long order filled: {order_id}")
            self._update_realized_pnl_from_fill(event, TradeType.BUY)
            # Check for asymmetric fill
            if not self._short_order.is_filled:
                self.logger().debug("ASYMMETRIC FILL: Long filled but short not filled yet")
        elif order_id == self._short_order.order_id:
            self.logger().info(f"Short order filled: {order_id}")
            self._update_realized_pnl_from_fill(event, TradeType.SELL)
            # Check for asymmetric fill
            if not self._long_order.is_filled:
                self.logger().debug("ASYMMETRIC FILL: Short filled but long not filled yet")
        elif self._long_close_order and order_id == self._long_close_order.order_id:
            self.logger().info(f"Long close order filled: {order_id}")
            self._update_realized_pnl_from_fill(event, TradeType.SELL)
        elif self._short_close_order and order_id == self._short_close_order.order_id:
            self.logger().info(f"Short close order filled: {order_id}")
            self._update_realized_pnl_from_fill(event, TradeType.BUY)
        else:
            self.logger().warning(f"Received fill for unknown order: {order_id}")

        # Reset asymmetric fill timer if both orders are now filled
        if self.is_position_active and self._asymmetric_fill_start_time is not None:
            self.logger().info("Both positions now filled - resetting asymmetric fill timer")
            self._asymmetric_fill_start_time = None

    def _update_realized_pnl_from_fill(self, event: OrderFilledEvent, trade_type: TradeType):
        """Update realized PnL and fees from order fill events"""
        try:
            fill_amount = event.amount
            fill_price = event.price

            # For entry orders: No realized PnL yet (position just opened)
            # For exit orders: Calculate actual realized PnL = (exit_price - entry_price) * amount

            # Check if this is a close order (exit)
            if self._long_close_order and event.order_id == self._long_close_order.order_id:
                # Calculate realized PnL for long close: (exit_price - entry_price) * amount
                if self._long_order.average_executed_price:
                    realized_pnl = (fill_price - self._long_order.average_executed_price) * fill_amount
                    self._realized_pnl_quote += realized_pnl
                    self.logger().debug(f"Long close realized PnL: ({fill_price} - {self._long_order.average_executed_price}) * {fill_amount} = {realized_pnl}")
            elif self._short_close_order and event.order_id == self._short_close_order.order_id:
                # Calculate realized PnL for short close: (entry_price - exit_price) * amount
                if self._short_order.average_executed_price:
                    realized_pnl = (self._short_order.average_executed_price - fill_price) * fill_amount
                    self._realized_pnl_quote += realized_pnl
                    self.logger().debug(f"Short close realized PnL: ({self._short_order.average_executed_price} - {fill_price}) * {fill_amount} = {realized_pnl}")

        except Exception as e:
            self.logger().error(f"Error updating realized PnL and fees from fill: {e}")

    def process_order_completed_event(self, _event_tag, _market, event: Union[BuyOrderCompletedEvent, SellOrderCompletedEvent]):
        """
        Process order completed events. Updates TrackedOrder with the InFlightOrder information
        and handles final PnL calculations.
        """
        order_id = event.order_id

        # Update tracked order with latest information
        self.update_tracked_orders_with_order_id(order_id)

        # Note: Realized PnL is now calculated in _update_realized_pnl_from_fill during order fills
        # No additional processing needed for completed orders

    def process_order_failed_event(self, _event_tag, _market, event: MarketOrderFailureEvent):
        """Process order failure events"""
        order_id = event.order_id
        self.logger().error(f"Order failed: {order_id} - {event.order_type}")

        # Clear failed order state
        if order_id == self._long_order.order_id:
            self._failed_orders.append(self._long_order)
            self._long_order = TrackedOrder()
            self.logger().error(f"Long order failed {order_id}")
        elif order_id == self._short_order.order_id:
            self._failed_orders.append(self._short_order)
            self._short_order = TrackedOrder()
            self.logger().error(f"Short order failed {order_id}")
        elif self._long_close_order and order_id == self._long_close_order.order_id:
            self._failed_orders.append(self._long_close_order)
            self._long_close_order = None
            self.logger().error(f"Long close order failed {order_id}")
        elif self._short_close_order and order_id == self._short_close_order.order_id:
            self._failed_orders.append(self._short_close_order)
            self._short_close_order = None
            self.logger().error(f"Short close order failed {order_id}")

        # Increment retry counter for failed orders
        self._current_retries += 1

        # Mark executor as failed if max retries exceeded
        if self._current_retries > self._max_retries:
            self.logger().error(f"Max retries exceeded for executor {self.config.id}. Stopping executor.")
            self.close_type = CloseType.FAILED
            self.stop()

    def process_order_canceled_event(self, _event_tag, _market, event: OrderCancelledEvent):
        """
        Process order canceled events. Handles cleanup for canceled orders.
        """
        order_id = event.order_id

        self.logger().info(f"Order cancellation confirmed by exchange: {order_id}")

        # Remove from pending cancellations
        self._pending_cancellations.discard(order_id)

        # Clean up canceled order state
        if self._long_order and order_id == self._long_order.order_id:
            self._failed_orders.append(self._long_order)
            self._long_order = TrackedOrder()
            self.logger().info(f"Long order canceled and state cleared: {order_id}")
            # Log asymmetric state
            if self._short_order.is_filled:
                self.logger().debug("ASYMMETRIC STATE: Long order canceled but short order is filled")
        elif self._short_order and order_id == self._short_order.order_id:
            self._failed_orders.append(self._short_order)
            self._short_order = TrackedOrder()
            self.logger().info(f"Short order canceled and state cleared: {order_id}")
            # Log asymmetric state
            if self._long_order.is_filled:
                self.logger().debug("ASYMMETRIC STATE: Short order canceled but long order is filled")
        elif self._long_close_order and order_id == self._long_close_order.order_id:
            self._failed_orders.append(self._long_close_order)
            self._long_close_order = None
            self.logger().info(f"Long close order canceled and state cleared: {order_id}")
        elif self._short_close_order and order_id == self._short_close_order.order_id:
            self._failed_orders.append(self._short_close_order)
            self._short_close_order = None
            self.logger().info(f"Short close order canceled and state cleared: {order_id}")
        else:
            self.logger().warning(f"Received cancellation for unknown order: {order_id}")

    def did_complete_funding_payment(self, funding_event: FundingPaymentCompletedEvent):
        """
        Handle funding payment events.
        This method should be called by the strategy when funding payments are received.
        """
        # Check if this funding payment is for one of our positions
        if (funding_event.market == self.config.long_market.connector_name and
            funding_event.trading_pair == self.config.long_market.trading_pair) or \
           (funding_event.market == self.config.short_market.connector_name and
                funding_event.trading_pair == self.config.short_market.trading_pair):

            self._funding_payments.append(funding_event)
            self._cumulative_funding_pnl += funding_event.amount

            self.logger().info(f"Funding payment received: {funding_event.amount} "
                               f"on {funding_event.market} for {funding_event.trading_pair}")

    def get_cum_fees_quote(self) -> Decimal:
        """
        Calculate the cumulative fees in quote asset
        :return: The cumulative fees in quote asset.
        """
        orders = [self._long_order, self._short_order, self._long_close_order, self._short_close_order]
        return sum([order.cum_fees_quote for order in orders if order and order.cum_fees_quote])
