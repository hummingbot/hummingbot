import time
from hummingbot.strategy.lite_strategy_base import LiteStrategyBase, Decimal, OrderType


class DCAExample(LiteStrategyBase):
    """
    This example shows how to set up a simple strategy to buy a token on fixed (dollar) amount on a regular basis
    """
    #: Define markets to instruct Hummingbot to create connectors on the exchanges and markets you need
    markets = {"binance_paper_trade": {"BTC-USDT"}}
    #: The last time the strategy places a buy order
    last_ordered_ts = 0.
    #: Buying interval (in seconds)
    buy_interval = 10.
    #: Buying amount (in dollars - USDT)
    buy_quote_amount = Decimal("100")

    async def on_tick(self):
        # Check if it is time to buy
        if self.last_ordered_ts < time.time() - self.buy_interval:
            # Lets set the order price to the best bid
            price = self.connectors["binance_paper_trade"].get_price("BTC-USDT", False)
            amount = self.buy_quote_amount / price
            self.buy("binance_paper_trade", "BTC-USDT", amount, OrderType.LIMIT, price)
            self.last_ordered_ts = time.time()
