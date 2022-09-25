from hummingbot.strategy.script_strategy_base import Decimal, OrderType, ScriptStrategyBase
from hummingbot.core.event.events import OrderType, PositionAction

class FutureSentiment(ScriptStrategyBase):
    """
    This script is designed to buy a token when the sentiment is fear and sell when the sentiment is greed.
    Calculate the value of the sentiment based on the price difference between the futures and the spot.
    """
    markets = {
        "binance": {"MATIC-USDT"},
        "binance_perpetual": {"MATIC-USDT"},
        # "binance_paper_trade": {"MATIC-USDT"},
    }

    connector_name = "binance"
    trading_pair = "MATIC-USDT"
    order_type = OrderType.LIMIT

    # The value of the sentiment is fear
    sentiment_fear = Decimal("-0.0012")
    # The value of the sentiment is greed
    sentiment_greed = Decimal("0.0014")
    #: Buying amount (in dollars - MATIC)
    buy_quote_amount = Decimal("15")
    #: The last time the strategy places a  buy order
    last_ordered_ts = 0.
    #: Buying interval (in seconds)
    buy_interval = 1000.

    def cancel_all(self):
        active_orders = self.get_active_orders(self.connector_name)
        for order in active_orders:
            self.cancel(self.connector_name, self.trading_pair,order.client_order_id)

    def on_tick(self):
        # Return if interval is not reached
        if self.last_ordered_ts > (self.current_timestamp - self.buy_interval):
            return
        # Check if the sentiment is fear or greed
        spot_price = self.connectors["binance"].get_price(self.trading_pair, False)
        perp_price = self.connectors["binance_perpetual"].get_price(self.trading_pair, False)
        sentiment_value = (perp_price - spot_price) * 2 / (spot_price + perp_price)
        is_fear =  sentiment_value < self.sentiment_fear
        is_greed = sentiment_value > self.sentiment_greed
        amount = self.buy_quote_amount / spot_price

        # Open or Close position
        if is_fear:
            self.logger().info("Fear detected, opening position")
            self.cancel_all()
            self.buy(
                self.connector_name,
                self.trading_pair,
                amount,
                order_type=self.order_type,
                price=perp_price,
                position_action=PositionAction.OPEN,
            )
            self.last_ordered_ts = self.current_timestamp
        elif is_greed:
            self.logger().info("Greed detected, closing position")
            self.cancel_all()
            self.sell(
                self.connector_name,
                self.trading_pair,
                amount,
                order_type=self.order_type,
                price=perp_price,
                position_action=PositionAction.CLOSE,
            )
            self.last_ordered_ts = self.current_timestamp
        else:
            self.logger().info("Neutral sentiment, doing nothing")