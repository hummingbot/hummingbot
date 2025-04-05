import itertools
import logging

from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase

from .utils import create_arb_proposals

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
        with_fees: bool,
    ):
        super().__init__()
        self._market_infos = market_infos
        self._with_fees = with_fees
        self._all_markets_ready = False
        self.add_markets([market_info.market for market_info in market_infos])

    @property
    def all_markets_ready(self) -> bool:
        return self._all_markets_ready

    @all_markets_ready.setter
    def all_markets_ready(self, value: bool):
        self._all_markets_ready = value

    def tick(self, timestamp: float):
        if not self.all_markets_ready:
            self.all_markets_ready = all([market.ready for market in self.active_markets])
            if not self.all_markets_ready:
                if int(timestamp) % 10 == 0:  # prevent spamming by logging every 10 secs
                    unready_markets = [market for market in self.active_markets if market.ready is False]
                    for market in unready_markets:
                        msg = ', '.join([k for k, v in market.status_dict.items() if v is False])
                        self.logger().warning(f"{market.name} not ready: waiting for {msg}.")
                return
            else:
                self.logger().info("Markets are ready. Logging started.")

        for market_combination in itertools.combinations(self._market_infos, 2):
            arb_proposals = create_arb_proposals(*market_combination)
            self.logger().info(f"Arbitration proposals: {arb_proposals}")
