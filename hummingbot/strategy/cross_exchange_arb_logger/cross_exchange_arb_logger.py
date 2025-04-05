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

    def __init__(
        self,
        market_infos: list[MarketTradingPairTuple],
    ):
        super().__init__()
        self._market_info_1 = market_infos[0]
        self._market_info_2 = market_infos[1]
        self._connector_1_ready = False
        self._connector_2_ready = False
        self.add_markets([self._market_info_1.market, self._market_info_2.market])

    def tick(self, timestamp: float):
        if not self._connector_1_ready:
            self._connector_1_ready = self._market_info_1.market.ready
            if not self._connector_1_ready:
                self.logger().warning(
                    f"{self._market_info_1.market.name} is not ready. Please wait..."
                )
                return
            else:
                self.logger().warning(f"{self._market_info_1.market.name} is ready.")

        if not self._connector_2_ready:
            self._connector_2_ready = self._market_info_2.market.ready
            if not self._connector_2_ready:
                self.logger().warning(
                    f"{self._market_info_2.market.name} is not ready. Please wait..."
                )
                return
            else:
                self.logger().warning(f"{self._market_info_2.market.name} is ready.")

        self.logger().info("Logging started.")

        best_buy_1 = self._market_info_1.get_price(is_buy=False)
        best_sell_1 = self._market_info_1.get_price(is_buy=True)
        self.logger().info(f"Bid: {best_buy_1} Ask: {best_sell_1}")

        best_buy_2 = self._market_info_2.get_price(is_buy=False)
        best_sell_2 = self._market_info_2.get_price(is_buy=True)
        self.logger().info(f"Bid: {best_buy_2} Ask: {best_sell_2}")
