import json
import os
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


class OrderLevel(BaseModel):
    """Configuration for a single order level"""
    bid_spread: Decimal = Field(description="Bid spread for this level")
    ask_spread: Decimal = Field(description="Ask spread for this level")


class WeexVccPMMConfig(BaseClientModel):
    """
    Configuration for WEEX VCC-USDT Market Making
    """
    script_file_name: str = os.path.basename(__file__)

    # Exchange Configuration
    exchange: str = Field(default="weex", description="Exchange name")
    trading_pair: str = Field(default="VCC-USDT", description="Trading pair")

    # Order Configuration
    order_amount: Decimal = Field(default=Decimal("12500"), description="Order amount in VCC per level (~$1.88 at $0.00015)")
    number_of_orders: int = Field(default=4, description="Number of order levels per side")
    order_levels: List[OrderLevel] = Field(
        default=[
            OrderLevel(bid_spread=Decimal("0.0066"), ask_spread=Decimal("0.0066")),
            OrderLevel(bid_spread=Decimal("0.0131"), ask_spread=Decimal("0.0131")),
            OrderLevel(bid_spread=Decimal("0.0177"), ask_spread=Decimal("0.0177")),
            OrderLevel(bid_spread=Decimal("0.0222"), ask_spread=Decimal("0.0222")),
        ],
        description="Spread configuration for each order level"
    )

    # Timing
    order_refresh_time: int = Field(default=30, description="Refresh orders every N seconds")
    immediate_replenishment: bool = Field(default=True, description="Immediately replace filled orders")
    min_order_interval: int = Field(default=2, description="Minimum seconds between order placements")

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
        self.monitor_health_file = "/tmp/weex_mm_health.json"
        self.last_health_check = 0.0
        self.health_check_interval = 5.0  # Check health every 5 seconds

    def on_tick(self):
        """
        Called every tick. Refreshes orders based on order_refresh_time.
        """
        # Check monitor health status
        if not self._check_monitor_health():
            return  # Skip this tick if monitor signals pause

        if self.create_timestamp <= self.current_timestamp:
            self.cancel_all_orders()
            proposal: List[OrderCandidate] = self.create_proposal()
            proposal_adjusted: List[OrderCandidate] = self.adjust_proposal_to_budget(proposal)
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

        orders = []

        # Create orders for each level
        num_levels = min(self.config.number_of_orders, len(self.config.order_levels))

        for level_idx in range(num_levels):
            level_config = self.config.order_levels[level_idx]

            # Calculate prices for this level
            buy_price = ref_price * Decimal(1 - level_config.bid_spread)
            sell_price = ref_price * Decimal(1 + level_config.ask_spread)

            # Create buy order for this level
            buy_order = OrderCandidate(
                trading_pair=self.config.trading_pair,
                is_maker=True,
                order_type=OrderType.LIMIT,
                order_side=TradeType.BUY,
                amount=Decimal(self.config.order_amount),
                price=buy_price
            )

            # Create sell order for this level
            sell_order = OrderCandidate(
                trading_pair=self.config.trading_pair,
                is_maker=True,
                order_type=OrderType.LIMIT,
                order_side=TradeType.SELL,
                amount=Decimal(self.config.order_amount),
                price=sell_price
            )

            orders.extend([buy_order, sell_order])

        # Log the proposal
        self.logger().info(f"Creating {num_levels}-level proposal at ref price: {ref_price:.8f}")
        for i, level in enumerate(self.config.order_levels[:num_levels]):
            buy_p = ref_price * Decimal(1 - level.bid_spread)
            sell_p = ref_price * Decimal(1 + level.ask_spread)
            self.logger().info(f"  Level {i + 1}: Buy @ {buy_p:.8f} ({-level.bid_spread * 100:.2f}%), "
                               f"Sell @ {sell_p:.8f} (+{level.ask_spread * 100:.2f}%)")

        return orders

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
        """
        active_orders = self.get_active_orders(connector_name=self.config.exchange)
        if not active_orders:
            return

        # Convert to LimitOrder objects for batch cancel
        limit_orders = []
        for order in active_orders:
            limit_order = LimitOrder(
                client_order_id=order.client_order_id,
                trading_pair=order.trading_pair,
                is_buy=order.is_buy,
                base_currency=order.trading_pair.split("-")[0],
                quote_currency=order.trading_pair.split("-")[1],
                price=order.price,
                quantity=order.quantity,
            )
            limit_orders.append(limit_order)

        # Use batch cancel
        connector = self.connectors[self.config.exchange]
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

        # Immediate replenishment if enabled
        if self.config.immediate_replenishment:
            time_since_last_order = self.current_timestamp - self.last_order_timestamp

            if time_since_last_order >= self.config.min_order_interval:
                self.logger().info("Order filled - triggering immediate replenishment")
                self.cancel_all_orders()
                proposal: List[OrderCandidate] = self.create_proposal()
                proposal_adjusted: List[OrderCandidate] = self.adjust_proposal_to_budget(proposal)
                self.place_orders(proposal_adjusted)
                self.last_order_timestamp = self.current_timestamp
                # Reset scheduled refresh timer
                self.create_timestamp = self.current_timestamp + self.config.order_refresh_time
            else:
                self.logger().info(f"Skipping immediate replenishment - too soon ({time_since_last_order:.1f}s < {self.config.min_order_interval}s)")

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

        # Active orders
        active_orders = self.get_active_orders(self.config.exchange)
        lines.append(f"  Active Orders: {len(active_orders)}")

        for order in active_orders:
            side = "BUY" if order.is_buy else "SELL"
            lines.append(f"    {side} {order.quantity:,.2f} @ {order.price:.8f}")

        # Strategy parameters
        lines.append("\n  Strategy Parameters:")
        lines.append(f"  Order Levels: {self.config.number_of_orders} per side")
        lines.append(f"  Order Amount per Level: {self.config.order_amount:,.0f} VCC")
        lines.append(f"  Total Liquidity: {self.config.number_of_orders * self.config.order_amount:,.0f} VCC per side")
        for i, level in enumerate(self.config.order_levels[:self.config.number_of_orders]):
            lines.append(f"    Level {i + 1}: -{level.bid_spread * 100:.2f}% / +{level.ask_spread * 100:.2f}%")
        lines.append(f"  Refresh Time: {self.config.order_refresh_time}s")

        return "\n".join(lines)
