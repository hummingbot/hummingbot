from decimal import Decimal
import time

from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.event.events import OrderType
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class SimpleMM(ScriptStrategyBase):
    """
    A basic market making strategy that places buy and sell orders at a fixed spread from mid price.
    """

    markets = {"binance_paper_trade": {"ETH-USDT"}}
    
    def __init__(self, connectors=None):
        super().__init__(connectors)
        self.trading_pair = "ETH-USDT"
        self.exchange = "binance_paper_trade"
        self.order_amount = Decimal("0.1")
        self.spread = Decimal("0.005")  # 0.5% spread
        self.order_refresh_time = 30  # in seconds
        self.last_order_refresh_timestamp = 0
        self.base_asset, self.quote_asset = self.trading_pair.split("-")

    def on_tick(self):
        """
        Called on every clock tick (1 second by default)
        """
        now = int(time.time())
        if now - self.last_order_refresh_timestamp <= self.order_refresh_time:
            return
        
        self.logger().info("Refreshing orders...")
        self.cancel_all()
        self.place_orders()
        self.last_order_refresh_timestamp = now

    def place_orders(self):
        """
        Place buy and sell orders
        """
        # Get mid price and calculate order prices
        mid_price = self.connectors[self.exchange].get_price_by_type(self.trading_pair)
        buy_price = mid_price * (Decimal("1") - self.spread)
        sell_price = mid_price * (Decimal("1") + self.spread)

        # Place buy order
        self.buy(
            connector_name=self.exchange,
            trading_pair=self.trading_pair,
            amount=self.order_amount,
            order_type=OrderType.LIMIT,
            price=buy_price,
        )
        self.logger().info(f"Placed buy order: {self.order_amount} {self.base_asset} at {buy_price} {self.quote_asset}")

        # Place sell order
        self.sell(
            connector_name=self.exchange,
            trading_pair=self.trading_pair,
            amount=self.order_amount,
            order_type=OrderType.LIMIT,
            price=sell_price,
        )
        self.logger().info(f"Placed sell order: {self.order_amount} {self.base_asset} at {sell_price} {self.quote_asset}")

    def cancel_all(self):
        """
        Cancel all active orders
        """
        for connector_name, trading_pairs in self.markets.items():
            for trading_pair in trading_pairs:
                self.cancel_all_orders(connector_name=connector_name, trading_pair=trading_pair)


def start(script_name, strategy_file_name):
    """
    Start the script strategy
    """
    strategy = SimpleMM()
    print("Simple Market Making strategy started.")
    print(f"Trading on {strategy.exchange}: {strategy.trading_pair}")
    print(f"Order amount: {strategy.order_amount} {strategy.base_asset}")
    print(f"Spread: {float(strategy.spread) * 100:.2f}%")
    return strategy 