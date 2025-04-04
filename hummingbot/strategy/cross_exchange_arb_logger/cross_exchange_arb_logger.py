import logging

from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase

hws_logger = None


class CrossExchangeArbLogger(StrategyPyBase):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global hws_logger
        if hws_logger is None:
            hws_logger = logging.getLogger(__name__)
        return hws_logger

    def __init__(self,
                 market_info_1: MarketTradingPairTuple,
                 market_info_2: MarketTradingPairTuple,
                 ):

        super().__init__()
        self._market_info_1 = market_info_1
        self._market_info_2 = market_info_2
        self._connector_1_ready = False
        self._connector_2_ready = False
        self.add_markets([market_info_1.market, market_info_2.market])

    # After initializing the required variables, we define the tick method.
    # The tick method is the entry point for the strategy.
    def tick(self, timestamp: float):
        if not self._connector_1_ready:
            self._connector_1_ready = self._market_info_1.market.ready
            if not self._connector_1_ready:
                self.logger().warning(f"{self._market_info_1.market.name} is not ready. Please wait...")
                return
            else:
                self.logger().warning(f"{self._market_info_1.market.name} is ready.")

        if not self._connector_2_ready:
            self._connector_2_ready = self._market_info_2.market.ready
            if not self._connector_2_ready:
                self.logger().warning(f"{self._market_info_2.market.name} is not ready. Please wait...")
                return
            else:
                self.logger().warning(f"{self._market_info_2.market.name} is ready.")

        self.logger().info("Logging started.")

        mid_price_1 = self._market_info_1.get_mid_price()
        self.logger().info(f"Market_1 mid price {mid_price_1}")

        mid_price_2 = self._market_info_2.get_mid_price()
        self.logger().info(f"Market_2 mid price {mid_price_2}")
