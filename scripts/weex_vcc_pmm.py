import os
from decimal import Decimal
from typing import Dict, List

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class OrderLevel(BaseClientModel):
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

    def on_tick(self):
        """
        Called every tick. Refreshes orders based on order_refresh_time.
        """
        if self.create_timestamp <= self.current_timestamp:
            self.cancel_all_orders()
            proposal: List[OrderCandidate] = self.create_proposal()
            proposal_adjusted: List[OrderCandidate] = self.adjust_proposal_to_budget(proposal)
            self.place_orders(proposal_adjusted)
            self.last_order_timestamp = self.current_timestamp
            self.create_timestamp = self.config.order_refresh_time + self.current_timestamp

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
        Places the orders from the proposal.
        """
        for order in proposal:
            self.place_order(connector_name=self.config.exchange, order=order)

    def place_order(self, connector_name: str, order: OrderCandidate):
        """
        Places a single order and logs the action.
        """
        if order.order_side == TradeType.SELL:
            self.sell(connector_name=connector_name,
                      trading_pair=order.trading_pair,
                      amount=order.amount,
                      order_type=order.order_type,
                      price=order.price)
        elif order.order_side == TradeType.BUY:
            self.buy(connector_name=connector_name,
                     trading_pair=order.trading_pair,
                     amount=order.amount,
                     order_type=order.order_type,
                     price=order.price)

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
                self.create_timestamp = self.config.order_refresh_time + self.current_timestamp
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
