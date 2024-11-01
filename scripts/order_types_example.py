import logging

from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.strategy.script_strategy_base import Decimal, OrderType, ScriptStrategyBase


class DCAExample(ScriptStrategyBase):
    """
    This example shows how to set up a simple strategy to buy a token on fixed (dollar) amount on a regular basis
    """
    #: Define markets to instruct Hummingbot to create connectors on the exchanges and markets you need
    markets = {"kraken": {"BTC-USD"}}
    #: The last time the strategy places a buy order
    last_ordered_ts = 0.
    #: Buying interval (in seconds)
    buy_interval = 60.
    #: Buying amount (in dollars - USDT)
    buy_quote_amount = Decimal("100")

    def on_tick(self):
        # Check if it is time to buy
        if self.last_ordered_ts < (self.current_timestamp - self.buy_interval):
            # Lets set the order price to the best bid
            price = self.connectors["kraken"].get_price("BTC-USD", False)
            amount = self.buy_quote_amount / price
            self.buy("kraken", "BTC-USD", amount, OrderType.LIMIT, price)
            self.sell("kraken", "BTC-USD", amount * Decimal("0.5"), OrderType.STOP_LOSS, Decimal("2"), price_in_percent=True)
            self.sell("kraken", "BTC-USD", amount * Decimal("0.5"), OrderType.TAKE_PROFIT, Decimal("10"), price_in_percent=True)
            self.sell("kraken", "BTC-USD", amount * Decimal("0.5"), OrderType.TRAILING_STOP, Decimal("1"), price_in_percent=True)
            self.last_ordered_ts = self.current_timestamp

    def did_create_buy_order(self, event: BuyOrderCreatedEvent):
        """
        Method called when the connector notifies a buy order has been created
        """
        self.logger().info(logging.INFO, f"The buy order {event.order_id} has been created")

    def did_create_sell_order(self, event: SellOrderCreatedEvent):
        """
        Method called when the connector notifies a sell order has been created
        """
        self.logger().info(logging.INFO, f"The sell order {event.order_id} has been created")

    def did_fill_order(self, event: OrderFilledEvent):
        """
        Method called when the connector notifies that an order has been partially or totally filled (a trade happened)
        """
        self.logger().info(logging.INFO, f"The order {event.order_id} has been filled")

    def did_fail_order(self, event: MarketOrderFailureEvent):
        """
        Method called when the connector notifies an order has failed
        """
        self.logger().info(logging.INFO, f"The order {event.order_id} failed")

    def did_cancel_order(self, event: OrderCancelledEvent):
        """
        Method called when the connector notifies an order has been cancelled
        """
        self.logger().info(f"The order {event.order_id} has been cancelled")

    def did_complete_buy_order(self, event: BuyOrderCompletedEvent):
        """
        Method called when the connector notifies a buy order has been completed (fully filled)
        """
        self.logger().info(f"The buy order {event.order_id} has been completed")

    def did_complete_sell_order(self, event: SellOrderCompletedEvent):
        """
        Method called when the connector notifies a sell order has been completed (fully filled)
        """
        self.logger().info(f"The sell order {event.order_id} has been completed")
