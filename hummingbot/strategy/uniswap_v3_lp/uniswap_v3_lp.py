from decimal import Decimal
import asyncio
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase


class UniswapV3LpStrategy(StrategyPyBase):

    def __init__(self,
                 market_info: MarketTradingPairTuple,
                 range_order_quote_amount: Decimal,
                 range_order_spread: Decimal,
                 status_report_interval: float = 900):
        super().__init__()
        self._market_info = market_info
        self._range_order_quote_amount = range_order_quote_amount
        self._range_order_spread = range_order_spread

        self._ev_loop = asyncio.get_event_loop()

        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self.add_markets([market_info.market])
