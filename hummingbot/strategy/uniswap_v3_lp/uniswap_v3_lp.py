from decimal import Decimal
import asyncio
import logging
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase
from hummingbot.core.utils.async_utils import safe_ensure_future

ulp_logger = None


class UniswapV3LpStrategy(StrategyPyBase):

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global ulp_logger
        if ulp_logger is None:
            ulp_logger = logging.getLogger(__name__)
        return ulp_logger

    def __init__(self,
                 market_info: MarketTradingPairTuple,
                 upper_price_bound: Decimal,
                 lower_price_bound: Decimal,
                 boundaries_margin: Decimal,
                 token: str,
                 token_amount: Decimal,
                 status_report_interval: float = 900):
        super().__init__()
        self._market_info = market_info
        self._upper_price_bound = upper_price_bound
        self._lower_price_bound = lower_price_bound
        self._boundaries_margin = boundaries_margin
        self._token = token
        self._token_amount = token_amount

        self._ev_loop = asyncio.get_event_loop()
        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self.add_markets([market_info.market])
        self._connector_ready = False

    async def format_status(self) -> str:
        return "to be done."

    def tick(self, timestamp: float):
        """
        Clock tick entry point, is run every second (on normal tick setting).
        :param timestamp: current tick timestamp
        """
        if not self._connector_ready:
            self._connector_ready = self._market_info.market.ready
            if not self._connector_ready:
                self.logger().warning("Uniswap v3 connector is not ready. Please wait...")
                return
            else:
                self.logger().info("Uniswap v3 connector is ready. Trading started.")
        if self._main_task is None or self._main_task.done():
            self._main_task = safe_ensure_future(self.main())

    async def main(self):
        pass
