import json

# Disable rate oracle completely to prevent CoinGecko rate limit warnings
import logging
import os
import random
from decimal import Decimal
from typing import Dict, List

from pydantic import BaseModel, Field

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase

logging.getLogger("hummingbot.core.rate_oracle").setLevel(logging.CRITICAL)


class OrderLevel(BaseModel):
    """Configuration for a single order level"""
    bid_spread: Decimal = Field(description="Bid spread for this level")
    ask_spread: Decimal = Field(description="Ask spread for this level")
    order_amount: Decimal = Field(description="Order amount in base asset for this level")


class WeexVccPMMConfig(BaseClientModel):
    """
    Configuration for WEEX VCC-USDT Market Making
    """
    script_file_name: str = os.path.basename(__file__)

    # Exchange Configuration
    exchange: str = Field(default="weex", description="Exchange name")
    trading_pair: str = Field(default="VCC-USDT", description="Trading pair")

    # Order Configuration
    order_amount_usd: Decimal = Field(default=Decimal("2.0"), description="Order amount in USD (quote currency) per level")
    order_amount: Decimal = Field(default=Decimal("0"), description="DEPRECATED: Use order_amount_usd instead")
    number_of_orders: int = Field(default=10, description="Number of order levels per side")
    min_active_orders_refresh: int = Field(default=11, description="Trigger refresh if active orders fall below this")
    # Dynamic levels (tighter spreads + randomized amounts around median)
    use_dynamic_levels: bool = Field(default=True, description="Generate dynamic levels each cycle")
    min_spread: Decimal = Field(default=Decimal("0.0050"), description="Tightest spread for inner level (0.50%)")
    max_spread: Decimal = Field(default=Decimal("0.0150"), description="Widest spread for outer level (1.50%)")
    amount_random_pct: Decimal = Field(default=Decimal("0.08"), description="Randomize order amount by +/- % around median")
    order_levels: List[OrderLevel] = Field(
        default=[],
        description="Optional static spread configuration for each order level"
    )

    # Timing
    order_refresh_time: int = Field(default=30, description="Refresh orders every N seconds")
    immediate_replenishment: bool = Field(default=True, description="Immediately replace filled orders")
    min_order_interval: int = Field(default=2, description="Minimum seconds between order placements")

    # Inventory Management
    target_vcc_pct: Decimal = Field(default=Decimal("0.40"), description="Target VCC inventory percentage (40% = 40/60 split)")
    inventory_skew_enabled: bool = Field(default=True, description="Enable spread skewing based on inventory")
    inventory_alert_threshold: Decimal = Field(default=Decimal("0.05"), description="Alert when +/- this far from target (5%)")
    max_inventory_skew: Decimal = Field(default=Decimal("0.30"), description="Maximum spread adjustment (30%)")

    # Price Source
    price_type: str = Field(default="mid", description="Price source: 'mid' or 'last'")

    # Risk Management
    max_order_age: int = Field(default=1800, description="Maximum order age in seconds (30 min)")
    min_profitability: Decimal = Field(default=Decimal("0.001"), description="Minimum spread to maintain (0.1%)")
    kill_switch_enabled: bool = Field(default=False, description="Enable automatic kill switch")
    kill_switch_rate: Decimal = Field(default=Decimal("-0.03"), description="Stop trading if portfolio drops by this amount")


class WeexVccPMM(ScriptStrategyBase):
    """
    WEEX VCC-USDT Pure Market Making Strategy

    This strategy places symmetric buy and sell orders around the mid price
    to provide liquidity and profit from the spread.

    Features:
    - Automatic order refresh
    - Budget checking
    - $5 minimum order size compliance
    - Mid/last price source selection
    """

    create_timestamp = 0
    price_source = PriceType.MidPrice
    last_order_timestamp = 0  # Track last order placement time

    @classmethod
    def init_markets(cls, config: WeexVccPMMConfig):
        cls.markets = {config.exchange: {config.trading_pair}}
        cls.price_source = PriceType.LastTrade if config.price_type == "last" else PriceType.MidPrice

    def __init__(self, connectors: Dict[str, ConnectorBase], config: WeexVccPMMConfig):
        super().__init__(connectors)
        self.config = config
        # Initialize timestamps as instance variables to avoid class-level sharing
        self.create_timestamp = 0.0
        self.last_order_timestamp = 0.0
        # Monitor health file path
        self.monitor_health_file = "/home/hummingbot/health/weex_mm_health.json"
        self.last_health_check = 0.0
        self.health_check_interval = 5.0  # Check health every 5 seconds
        # Track cancellation state to prevent placing new orders before async cancels complete
        self.pending_cancel_timestamp = 0.0
        self.min_cancel_wait = 2.0  # Wait at least 2 seconds after cancel before placing new orders
        self.max_cancel_wait = 10.0  # Force proceed after 10 seconds even if orders still tracked

    def on_tick(self):
        """
        Called every tick. Refreshes orders based on order_refresh_time.
        """
        # Check monitor health status
        if not self._check_monitor_health():
            return  # Skip this tick if monitor signals pause

        # Check active order count to defend against liquidity drain
        try:
            connector = self.connectors.get(self.config.exchange)
            if not connector or not hasattr(connector, '_order_tracker'):
                return
            active_orders = list(connector._order_tracker.active_orders.values())
        except Exception as e:
            self.logger().warning(f"Error accessing connector orders: {e}")
            return

        if len(active_orders) < self.config.min_active_orders_refresh and self.pending_cancel_timestamp == 0:
            self.logger().warning(
                f"Active orders below threshold ({len(active_orders)}/{self.config.min_active_orders_refresh}); forcing refresh"
            )
            # Restart refresh cycle baseline
            self.create_timestamp = self.current_timestamp
            self.last_order_timestamp = 0.0
            if active_orders:
                self.cancel_all_orders()
                self.pending_cancel_timestamp = self.current_timestamp
                self.logger().info(f"Canceling {len(active_orders)} orders due to low active order count")
                return

        if self.create_timestamp <= self.current_timestamp:
            # Check if we still have active orders from the previous cycle
            # CRITICAL: Check connector tracker directly, not strategy aggregator
            # Strategy aggregator lags behind connector tracker by up to 3+ seconds

            remaining_active_orders = []
            if active_orders:
                # Still have orders from previous cycle - cancel them and wait for them to clear
                if self.pending_cancel_timestamp == 0:
                    # First time seeing old orders: initiate cancel
                    self.cancel_all_orders()
                    self.pending_cancel_timestamp = self.current_timestamp
                    self.logger().info(f"Canceling {len(active_orders)} old orders before placing new ones")
                    return
                else:
                    # Already initiated cancel, check if enough time has passed
                    time_since_cancel = self.current_timestamp - self.pending_cancel_timestamp
                    if time_since_cancel < self.min_cancel_wait:
                        # Still waiting for cancels to complete
                        return

                    # Check again if orders are actually gone
                    try:
                        active_orders = list(connector._order_tracker.active_orders.values())
                    except Exception:
                        return

                    if active_orders:
                        if time_since_cancel >= self.max_cancel_wait:
                            # Timeout reached - force proceed anyway
                            self.logger().warning(
                                f"Cancel timeout after {time_since_cancel:.1f}s: {len(active_orders)} orders still tracked, forcing proceed"
                            )
                            self.pending_cancel_timestamp = 0.0
                            remaining_active_orders = active_orders
                        elif len(active_orders) <= 1:
                            # Avoid empty book when only one order lingers
                            self.logger().warning(
                                f"Only {len(active_orders)} order still active after {time_since_cancel:.1f}s; placing remaining levels"
                            )
                            self.pending_cancel_timestamp = 0.0
                            remaining_active_orders = active_orders
                        else:
                            # Orders still there, give it more time
                            self.logger().warning(
                                f"Orders still active after {time_since_cancel:.1f}s, waiting longer..."
                            )
                            return

                    # Orders are finally gone, proceed to place new ones
                    self.pending_cancel_timestamp = 0.0

            # No active orders (or we decided to proceed), place new ones
            proposal: List[OrderCandidate] = self.create_proposal()
            proposal_adjusted: List[OrderCandidate] = self.adjust_proposal_to_budget(proposal)
            if remaining_active_orders:
                try:
                    existing_levels = {
                        (o.trade_type, connector.quantize_order_price(o.trading_pair, o.price))
                        for o in remaining_active_orders
                    }
                    proposal_adjusted = [
                        p for p in proposal_adjusted
                        if (p.order_side, connector.quantize_order_price(p.trading_pair, p.price)) not in existing_levels
                    ]
                except Exception:
                    # Fallback to raw price comparison if quantization fails
                    existing_levels = {(o.trade_type, o.price) for o in remaining_active_orders}
                    proposal_adjusted = [
                        p for p in proposal_adjusted if (p.order_side, p.price) not in existing_levels
                    ]
            self.place_orders(proposal_adjusted)
            self.last_order_timestamp = self.current_timestamp
            self.create_timestamp = self.current_timestamp + self.config.order_refresh_time
            self.logger().info(f"Orders placed. Next refresh at timestamp: {self.create_timestamp} (in {self.config.order_refresh_time}s)")

    def create_proposal(self) -> List[OrderCandidate]:
        """
        Creates multiple buy and sell order proposals at different price levels.
        """
        ref_price = self.connectors[self.config.exchange].get_price_by_type(
            self.config.trading_pair,
            self.price_source
        )

        # Calculate inventory ratio and apply spread skewing
        inventory_skew_multiplier = self._calculate_inventory_skew(ref_price)

        orders = []

        # Build dynamic levels if enabled, otherwise use static config
        if self.config.use_dynamic_levels:
            levels = self._generate_dynamic_levels(ref_price)
        else:
            levels = self.config.order_levels

        # Apply inventory skew to spreads
        if self.config.inventory_skew_enabled and inventory_skew_multiplier != (Decimal("1.0"), Decimal("1.0")):
            buy_skew, sell_skew = inventory_skew_multiplier
            levels = [
                OrderLevel(
                    bid_spread=level.bid_spread * buy_skew,
                    ask_spread=level.ask_spread * sell_skew,
                    order_amount=level.order_amount
                )
                for level in levels
            ]

        # Create orders for each level
        num_levels = min(self.config.number_of_orders, len(levels))

        for level_idx in range(num_levels):
            level_config = levels[level_idx]

            # Calculate prices for this level
            buy_price = ref_price * Decimal(1 - level_config.bid_spread)
            sell_price = ref_price * Decimal(1 + level_config.ask_spread)

            # Use order amount from this level's config
            order_amount = level_config.order_amount

            # Create buy order for this level
            buy_order = OrderCandidate(
                trading_pair=self.config.trading_pair,
                is_maker=True,
                order_type=OrderType.LIMIT,
                order_side=TradeType.BUY,
                amount=order_amount,
                price=buy_price
            )

            # Create sell order for this level
            sell_order = OrderCandidate(
                trading_pair=self.config.trading_pair,
                is_maker=True,
                order_type=OrderType.LIMIT,
                order_side=TradeType.SELL,
                amount=order_amount,
                price=sell_price
            )

            orders.extend([buy_order, sell_order])

        # Log the proposal
        self.logger().info(f"Creating {num_levels}-level proposal at ref price: {ref_price:.8f}")
        for i, level in enumerate(levels[:num_levels]):
            buy_p = ref_price * Decimal(1 - level.bid_spread)
            sell_p = ref_price * Decimal(1 + level.ask_spread)
            self.logger().info(f"  Level {i + 1}: Buy @ {buy_p:.8f} ({-level.bid_spread * 100:.2f}%), "
                               f"Sell @ {sell_p:.8f} (+{level.ask_spread * 100:.2f}%)")

        return orders

    def _generate_dynamic_levels(self, mid_price: Decimal) -> List[OrderLevel]:
        """
        Generate 8 levels with USDT-based amounts (converts to VCC based on current price).
        Each level has randomized amount around $2 USD target.
        """
        num_levels = max(1, self.config.number_of_orders)
        min_spread = self.config.min_spread
        max_spread = self.config.max_spread
        if num_levels == 1:
            spreads = [min_spread]
        else:
            step = (max_spread - min_spread) / Decimal(num_levels - 1)
            spreads = [min_spread + step * Decimal(i) for i in range(num_levels)]

        levels: List[OrderLevel] = []
        for spread in spreads:
            # Apply randomization to USD amount, then convert to VCC
            rand_pct = float(self.config.amount_random_pct)
            usd_amount = self.config.order_amount_usd * Decimal(str(1 + random.uniform(-rand_pct, rand_pct)))

            # Convert USD to VCC based on current mid price
            vcc_amount = (usd_amount / mid_price).quantize(Decimal("1"))

            levels.append(OrderLevel(bid_spread=spread, ask_spread=spread, order_amount=vcc_amount))
        return levels

    def _calculate_inventory_skew(self, mid_price: Decimal) -> tuple:
        """
        Calculate spread skew multipliers based on current inventory ratio.
        Returns (buy_spread_multiplier, sell_spread_multiplier)

        Target: 40% VCC / 60% USDT by value
        - If > 45% VCC: widen buys (discourage buying), tighten sells (encourage selling)
        - If < 35% VCC: tighten buys (encourage buying), widen sells (discourage selling)
        """
        if not self.config.inventory_skew_enabled:
            return (Decimal("1.0"), Decimal("1.0"))

        try:
            connector = self.connectors[self.config.exchange]
            base_asset = self.config.trading_pair.split("-")[0]
            quote_asset = self.config.trading_pair.split("-")[1]

            # Get balances
            base_balance = connector.get_available_balance(base_asset)
            quote_balance = connector.get_available_balance(quote_asset)

            if base_balance <= 0 or quote_balance <= 0:
                self.logger().warning(f"Invalid balances: {base_asset}={base_balance}, {quote_asset}={quote_balance}")
                return (Decimal("1.0"), Decimal("1.0"))

            # Calculate inventory ratio (VCC value / total portfolio value)
            base_value = base_balance * mid_price
            total_value = base_value + quote_balance
            inventory_ratio = base_value / total_value

            # Calculate deviation from target
            target = self.config.target_vcc_pct
            deviation = inventory_ratio - target

            # Log inventory status periodically (every 5 ticks to avoid spam)
            if not hasattr(self, '_inventory_log_counter'):
                self._inventory_log_counter = 0
            self._inventory_log_counter += 1

            if self._inventory_log_counter >= 5:
                self._inventory_log_counter = 0
                status = "⚖️ BALANCED"
                ratio_pct = inventory_ratio * Decimal("100")
                target_pct = target * Decimal("100")
                if abs(deviation) > self.config.inventory_alert_threshold:
                    if deviation > 0:
                        status = f"⚠️ HIGH VCC ({ratio_pct:.1f}% > {target_pct:.0f}%)"
                    else:
                        status = f"⚠️ LOW VCC ({ratio_pct:.1f}% < {target_pct:.0f}%)"

                self.logger().info(
                    f"Inventory: {base_value:.2f} VCC + {quote_balance:.2f} USDT = ${total_value:.2f} | "
                    f"Ratio: {ratio_pct:.1f}% | {status}"
                )

            # Apply skew: linearly scale from 0% to max_inventory_skew based on deviation
            # Max skew at ±10% deviation from target (35% or 45% when target is 40%)
            max_deviation = Decimal("0.10")
            skew_amount = min(abs(deviation) / max_deviation, Decimal("1.0")) * self.config.max_inventory_skew

            if deviation > 0:
                # Too much VCC: widen buys, tighten sells
                buy_multiplier = Decimal("1.0") + skew_amount
                sell_multiplier = Decimal("1.0") - skew_amount
            else:
                # Too little VCC: tighten buys, widen sells
                buy_multiplier = Decimal("1.0") - skew_amount
                sell_multiplier = Decimal("1.0") + skew_amount

            # Ensure multipliers stay within reasonable bounds (0.7 to 1.3)
            buy_multiplier = max(Decimal("0.7"), min(Decimal("1.3"), buy_multiplier))
            sell_multiplier = max(Decimal("0.7"), min(Decimal("1.3"), sell_multiplier))

            if abs(deviation) > self.config.inventory_alert_threshold:
                self.logger().info(
                    f"Applying inventory skew: buy spreads ×{buy_multiplier:.2f}, sell spreads ×{sell_multiplier:.2f}"
                )

            return (buy_multiplier, sell_multiplier)

        except Exception as e:
            self.logger().error(f"Error calculating inventory skew: {e}")
            return (Decimal("1.0"), Decimal("1.0"))

    def adjust_proposal_to_budget(self, proposal: List[OrderCandidate]) -> List[OrderCandidate]:
        """
        Adjusts order amounts based on available balance.
        """
        proposal_adjusted = self.connectors[self.config.exchange].budget_checker.adjust_candidates(
            proposal,
            all_or_none=False  # Place what we can even if we can't place both
        )
        return proposal_adjusted

    def place_orders(self, proposal: List[OrderCandidate]) -> None:
        """
        Places the orders from the proposal using batch order creation.
        This reduces API weight from 8 orders × 5 weight = 40 to 1 batch × 10 weight = 10.
        """
        if not proposal:
            return

        # Get connector
        connector = self.connectors[self.config.exchange]

        # Convert OrderCandidate to LimitOrder for batch creation
        limit_orders = []
        for order_candidate in proposal:
            # Extract base and quote assets from trading pair
            base, quote = order_candidate.trading_pair.split("-")

            limit_order = LimitOrder(
                client_order_id="",  # Will be generated by batch_order_create
                trading_pair=order_candidate.trading_pair,
                is_buy=(order_candidate.order_side == TradeType.BUY),
                base_currency=base,
                quote_currency=quote,
                price=order_candidate.price,
                quantity=order_candidate.amount,
            )
            limit_orders.append(limit_order)

        # Use batch order create - single API call for all orders
        # NO WAIT HERE - let on_tick() state machine handle synchronization
        if limit_orders:
            created_orders = connector.batch_order_create(orders_to_create=limit_orders)
            self.logger().info(
                f"Batch order create initiated: {len(created_orders)} orders "
                f"({len([o for o in limit_orders if o.is_buy])} buys, "
                f"{len([o for o in limit_orders if not o.is_buy])} sells)"
            )

    def _check_monitor_health(self) -> bool:
        """
        Checks monitor health file and returns True if trading should continue.
        Returns False if monitor signals pause or critical issues.
        """
        # Rate limit health checks
        if self.current_timestamp - self.last_health_check < self.health_check_interval:
            return True  # No change, continue

        self.last_health_check = self.current_timestamp

        try:
            # Read monitor health file
            if not os.path.exists(self.monitor_health_file):
                # No health file = monitor not running, continue with caution
                return True

            with open(self.monitor_health_file, 'r') as f:
                health = json.load(f)

            # Check if monitor requests pause
            if health.get('pause_requested', False):
                issues = health.get('issues', [])
                self.logger().warning(f"MONITOR PAUSE REQUESTED: {', '.join(issues)}")
                self.logger().warning("Canceling all orders and pausing trading")
                self.cancel_all_orders()
                return False

            # Check health status
            if not health.get('healthy', True):
                issues = health.get('issues', [])
                self.logger().warning(f"Monitor health warning: {', '.join(issues)}")
                # Continue but log the warning

            # Check staleness (monitor should update every ~60s)
            last_update = health.get('last_update', 0)
            if last_update > 0 and self.current_timestamp - last_update > 300:
                self.logger().warning(f"Monitor health file is stale (last update: {int(self.current_timestamp - last_update)}s ago)")
                # Continue anyway - don't auto-pause if monitor goes down

            return True

        except Exception as e:
            self.logger().error(f"Error reading monitor health file: {e}")
            return True  # Continue on error - don't halt trading due to file read issues

    def cancel_all_orders(self):
        """
        Cancels all active orders on the exchange using batch cancel.
        Reduces API weight from 8 cancels × 3 weight = 24 to 1 batch × 10 weight = 10.

        Simply initiates the cancel without waiting - on_tick() handles the wait logic.
        """
        connector = self.connectors.get(self.config.exchange)
        if not connector or not hasattr(connector, '_order_tracker'):
            return

        connector_active = list(connector._order_tracker.active_orders.values())

        if not connector_active:
            return

        # Convert to LimitOrder objects for batch cancel
        limit_orders = []
        for order in connector_active:
            # Skip orders without exchange_order_id - prevents FAILED_ORDER_NOT_FOUND
            if not order.exchange_order_id:
                self.logger().debug(f"Skipping cancel for {order.client_order_id}: no exchange_order_id yet")
                continue
            limit_order = LimitOrder(
                client_order_id=order.client_order_id,
                trading_pair=order.trading_pair,
                is_buy=order.trade_type == TradeType.BUY,
                base_currency=order.trading_pair.split("-")[0],
                quote_currency=order.trading_pair.split("-")[1],
                price=order.price,
                quantity=order.amount,
            )
            limit_orders.append(limit_order)

        # Use batch cancel (fire-and-forget)
        if limit_orders:
            connector.batch_order_cancel(orders_to_cancel=limit_orders)
            self.logger().info(f"Batch cancel initiated for {len(limit_orders)} orders")

    def did_fill_order(self, event: OrderFilledEvent):
        """
        Called when an order is filled. Log the trade details and optionally replenish immediately.
        """
        msg = (f"{'Sold' if event.trade_type == TradeType.SELL else 'Bought'} "
               f"{event.amount} {event.trading_pair.split('-')[0]} "
               f"at {event.price:.8f} "
               f"for {event.amount * event.price:.2f} USDT")
        self.logger().info(msg)
        self.notify_hb_app_with_timestamp(msg)

        # Immediate replenishment is DISABLED to prevent database insert conflicts
        # When an order fills, the markets_recorder tries to save the completed order state
        # to the database. If replenishment immediately places new orders with overlapping
        # timestamps, the database can try to insert the same order twice, causing
        # UNIQUE constraint violations on Order.id
        # The 120-second refresh cycle safely handles replenishment.
        if False:  # self.config.immediate_replenishment:
            pass

    def format_status(self) -> str:
        """
        Returns status string with information about the current state.
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."

        lines = []
        lines.append("\n  WEEX VCC-USDT Market Making Status")
        lines.append("  " + "=" * 50)

        # Market info
        ref_price = self.connectors[self.config.exchange].get_price_by_type(
            self.config.trading_pair,
            self.price_source
        )
        lines.append(f"  Market: {self.config.trading_pair}")
        lines.append(f"  Reference Price: {ref_price:.8f} USDT")

        # Balance info
        base_asset = self.config.trading_pair.split("-")[0]
        quote_asset = self.config.trading_pair.split("-")[1]
        base_balance = self.connectors[self.config.exchange].get_available_balance(base_asset)
        quote_balance = self.connectors[self.config.exchange].get_available_balance(quote_asset)

        lines.append(f"  {base_asset} Balance: {base_balance:,.2f}")
        lines.append(f"  {quote_asset} Balance: {quote_balance:,.2f}")

        # Active orders - use connector tracker directly (like polling loop)
        # This ensures we see orders immediately when they're created
        connector = self.connectors[self.config.exchange]
        active_orders = list(connector._order_tracker.active_orders.values())
        lines.append(f"  Active Orders: {len(active_orders)}")

        for order in active_orders:
            side = "BUY" if order.trade_type == TradeType.BUY else "SELL"
            lines.append(f"    {side} {order.amount:,.2f} @ {order.price:.8f}")

        # Strategy parameters
        lines.append("\n  Strategy Parameters:")
        lines.append(f"  Order Levels: {self.config.number_of_orders} per side")

        # Generate current levels to show actual spreads
        if self.config.use_dynamic_levels:
            current_levels = self._generate_dynamic_levels(ref_price)

            # Calculate inventory skew if enabled
            inventory_skew = self._calculate_inventory_skew(ref_price)
            if self.config.inventory_skew_enabled and inventory_skew != (Decimal("1.0"), Decimal("1.0")):
                buy_skew, sell_skew = inventory_skew
                lines.append(f"  Inventory Skew: Buy ×{buy_skew:.2f}, Sell ×{sell_skew:.2f}")
                # Apply skew to display levels
                current_levels = [
                    OrderLevel(
                        bid_spread=level.bid_spread * buy_skew,
                        ask_spread=level.ask_spread * sell_skew,
                        order_amount=level.order_amount
                    )
                    for level in current_levels
                ]
        else:
            current_levels = self.config.order_levels

        total_per_side = sum(level.order_amount for level in current_levels[:self.config.number_of_orders])
        lines.append(f"  Total Liquidity: {total_per_side:,.0f} VCC per side")

        for i, level in enumerate(current_levels[:self.config.number_of_orders]):
            lines.append(f"    Level {i + 1}: {level.order_amount:,.0f} VCC @ -{level.bid_spread * 100:.2f}% / +{level.ask_spread * 100:.2f}%")

        lines.append(f"  Refresh Time: {self.config.order_refresh_time}s")

        return "\n".join(lines)
