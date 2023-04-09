from collections import deque
from decimal import Decimal
from statistics import mean

from hummingbot.core.data_type.common import OrderType
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class BuyLowSellHigh(ScriptStrategyBase):
    """
    BotCamp Cohort: Sept 2022
    Design Template: https://hummingbot-foundation.notion.site/Buy-low-sell-high-35b89d84f0d94d379951a98f97179053
    Video: -
    Description:
    The script will be calculating the MA for a certain pair, and will execute a buy_order at the golden cross
    and a sell_order at the death cross.
    For the sake of simplicity in testing, we will define fast MA as the 5-secondly-MA, and slow MA as the
    20-secondly-MA. User can change this as desired
    """
    markets = {"binance_paper_trade": {"BTC-USDT"}}
    #: pingpong is a variable to allow alternating between buy & sell signals
    pingpong = 0
    de_fast_ma = deque([], maxlen=5)
    de_slow_ma = deque([], maxlen=20)

    def on_tick(self):
        p = self.connectors["binance_paper_trade"].get_price("BTC-USDT", True)

        #: with every tick, the new price of the trading_pair will be appended to the deque and MA will be calculated
        self.de_fast_ma.append(p)
        self.de_slow_ma.append(p)
        fast_ma = mean(self.de_fast_ma)
        slow_ma = mean(self.de_slow_ma)

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
