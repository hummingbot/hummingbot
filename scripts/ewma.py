from decimal import Decimal

from hummingbot.core.data_type.common import OrderType
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class buyLowSellHigh(ScriptStrategyBase):
    markets = {"binance_paper_trade": {"BTC-USDT"}}
    #: pingpong is a variable to allow alternating between buy & sell signals
    pingpong = 0

    """
    for the sake of simplicity in testing, we will define fast MA as the 5-secondly-MA, and slow MA as the
    20-secondly-MA. User can change this as desired
    """

    de_fast_ma = []
    de_slow_ma = []

    def on_tick(self):
        p = self.connectors["binance_paper_trade"].get_price("BTC-USDT", True)

        #: with every tick, the new price of the trading_pair will be appended to the list and MA will be calculated
        self.de_fast_ma.append(p)
        # if the list is longer than 5, remove the oldest price
        if len(self.de_fast_ma) > 5:
            self.de_fast_ma.pop(0)

        self.de_slow_ma.append(p)
        # if the list is longer than 20, remove the oldest price
        if len(self.de_slow_ma) > 20:
            self.de_slow_ma.pop(0)

        fast_ma = self.ewma(self.de_fast_ma)
        slow_ma = self.ewma(self.de_slow_ma)

        #: logic for golden cross
        if (fast_ma > slow_ma) & (self.pingpong == 0):
            self.buy(
                connector_name="binance_paper_trade",
                trading_pair="BTC-USDT",
                amount=Decimal(0.01),
                order_type=OrderType.MARKET,
            )
            self.logger().info(f'{"0.01 BTC bought"}')
            self.pingpong = 1

        #: logic for death cross
        elif (slow_ma > fast_ma) & (self.pingpong == 1):
            self.sell(
                connector_name="binance_paper_trade",
                trading_pair="BTC-USDT",
                amount=Decimal(0.01),
                order_type=OrderType.MARKET,
            )
            self.logger().info(f'{"0.01 BTC sold"}')
            self.pingpong = 0

        else:
            self.logger().info(f'{"wait for a signal to be generated"}')

    # calculate the exponential moving average
    def ewma(self, prices):
        # if deque is empty, return 0
        if len(prices) == 0:
            return 0

        # if deque is not empty, calculate the ewma
        else:
            # set the smoothing factor
            smoothing_factor = 2 / (len(prices) + 1)
            # set the initial ewma
            ewma = prices[0]
            # loop through the deque and calculate the ewma
            for price in prices[1:]:
                # convert all variables to Decimal
                price = Decimal(price)
                ewma = Decimal(ewma)
                smoothing_factor = Decimal(smoothing_factor)
                # calculate the ewma
                ewma = (price - ewma) * smoothing_factor + ewma
            return ewma
# This is a new line that ends the file.
