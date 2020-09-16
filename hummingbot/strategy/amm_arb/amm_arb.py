from decimal import Decimal
import logging
import asyncio
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase


NaN = float("nan")
s_decimal_zero = Decimal(0)
amm_logger = None
NODE_SYNCED_CHECK_INTERVAL = 60.0 * 5.0


class AmmArbStrategy(StrategyPyBase):
    OPTION_LOG_NULL_ORDER_SIZE = 1 << 0
    OPTION_LOG_REMOVING_ORDER = 1 << 1
    OPTION_LOG_ADJUST_ORDER = 1 << 2
    OPTION_LOG_CREATE_ORDER = 1 << 3
    OPTION_LOG_MAKER_ORDER_FILLED = 1 << 4
    OPTION_LOG_STATUS_REPORT = 1 << 5
    OPTION_LOG_MAKER_ORDER_HEDGED = 1 << 6
    OPTION_LOG_ALL = 0x7fffffffffffffff
    CANCEL_EXPIRY_DURATION = 60.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global amm_logger
        if amm_logger is None:
            amm_logger = logging.getLogger(__name__)
        return amm_logger

    def __init__(self,
                 market_info_1: MarketTradingPairTuple,
                 market_info_2: MarketTradingPairTuple,
                 min_profitability: Decimal,
                 order_amount: Decimal,
                 slippage_buffer: Decimal = Decimal("0.0001"),
                 logging_options: int = OPTION_LOG_ALL,
                 status_report_interval: float = 900,
                 hb_app_notification: bool = True):
        super().__init__()
        self._market_info_1 = market_info_1
        self._market_info_2 = market_info_2
        self._min_profitability = min_profitability
        self._order_amount = order_amount
        self._slippage_buffer = slippage_buffer
        self._last_no_arb_reported = 0
        self._trade_profits = None
        self._all_markets_ready = False
        self._logging_options = logging_options

        self._ev_loop = asyncio.get_event_loop()
        self._async_scheduler = None
        self._last_synced_checked = 0
        self._node_synced = False

        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self._hb_app_notification = hb_app_notification
        self.add_markets([market_info_1.market, market_info_2.market])

    @property
    def min_profitability(self) -> Decimal:
        return self._min_profitability

    @property
    def order_amount(self) -> Decimal:
        return self._order_amount

    @order_amount.setter
    def order_amount(self, value):
        self._order_amount = value

    @property
    def logging_options(self) -> int:
        return self._logging_options

    def tick(self, timestamp: float):
        """
        Clock tick entry point, is run every second (on normal tick setting).
        :param timestamp: current tick timestamp
        """
        if not self._all_markets_ready:
            self._all_markets_ready = all([market.ready for market in self.active_markets])
            if not self._all_markets_ready:
                self.logger().warning(f"Markets are not ready. Please wait...")
                return
            else:
                self.logger().info(f"Markets are ready. Trading started.")
        self.main()

    def main(self):
        self.logger().info("amm arb main...")
