# distutils: language=c++
from decimal import Decimal
from libc.stdint cimport int64_t
import logging
from typing import (
    List,
    Tuple,
    Optional,
    Dict
)

from hummingbot.core.clock cimport Clock
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.limit_order cimport LimitOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.market.market_base import (
    MarketBase,
    OrderType
)
from hummingbot.market.market_base cimport MarketBase

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_base import StrategyBase


s_decimal_NaN = Decimal("nan")
s_decimal_zero = Decimal(0)
pt_logger = None


cdef class PerformTradeStrategy(StrategyBase):
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
        global pt_logger
        if pt_logger is None:
            pt_logger = logging.getLogger(__name__)
        return pt_logger

    def __init__(self,
                 market_infos: List[MarketTradingPairTuple],
                 order_type: str = "limit",
                 order_price: Optional[Decimal] = None,
                 is_buy: bool = True,
                 order_amount: Decimal = Decimal(1),
                 logging_options: int = OPTION_LOG_ALL,
                 status_report_interval: float = 900):

        if len(market_infos) < 1:
            raise ValueError(f"market_infos must not be empty.")

        super().__init__()
        self._market_infos = {
            (market_info.market, market_info.trading_pair): market_info
            for market_info in market_infos
        }
        self._all_markets_ready = False
        self._place_orders = True
        self._logging_options = logging_options
        self._status_report_interval = status_report_interval
        self._order_type = order_type
        self._is_buy = is_buy
        self._order_amount = Decimal(order_amount)
        self._order_price = s_decimal_NaN if order_price is None else Decimal(order_price)

        cdef:
            set all_markets = set([market_info.market for market_info in market_infos])

        self.c_add_markets(list(all_markets))

    @property
    def active_bids(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return self._sb_order_tracker.active_bids

    @property
    def active_asks(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return self._sb_order_tracker.active_asks

    @property
    def active_limit_orders(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return self._sb_order_tracker.active_limit_orders

    @property
    def in_flight_cancels(self) -> Dict[str, float]:
        return self._sb_order_tracker.in_flight_cancels

    @property
    def market_info_to_active_orders(self) -> Dict[MarketTradingPairTuple, List[LimitOrder]]:
        return self._sb_order_tracker.market_pair_to_active_orders

    @property
    def logging_options(self) -> int:
        return self._logging_options

    @logging_options.setter
    def logging_options(self, int64_t logging_options):
        self._logging_options = logging_options

    @property
    def place_orders(self):
        return self._place_orders

    def format_status(self) -> str:
        cdef:
            list lines = []
            list warning_lines = []
            dict market_info_to_active_orders = self.market_info_to_active_orders
            list active_orders = []

        for market_info in self._market_infos.values():
            active_orders = self.market_info_to_active_orders.get(market_info, [])

            warning_lines.extend(self.network_warning([market_info]))

            markets_df = self.market_status_data_frame([market_info])
            markets_df = markets_df.drop(columns=["Adjusted Bid", "Adjusted Ask"])
            lines.extend(["", "  Markets:"] + ["    " + line for line in str(markets_df).split("\n")])

            assets_df = self.wallet_balance_data_frame([market_info])
            assets_df = assets_df.drop(columns=["Conversion Rate"])
            lines.extend(["", "  Assets:"] + ["    " + line for line in str(assets_df).split("\n")])

            # See if there're any open orders.
            if len(active_orders) > 0:
                df = LimitOrder.to_pandas(active_orders)
                df_lines = str(df).split("\n")
                lines.extend(["", "  Active orders:"] +
                             ["    " + line for line in df_lines])
            else:
                lines.extend(["", "  No active maker orders."])

            warning_lines.extend(self.balance_warning([market_info]))

        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    cdef c_start(self, Clock clock, double timestamp):
        StrategyBase.c_start(self, clock, timestamp)

    cdef c_tick(self, double timestamp):
        StrategyBase.c_tick(self, timestamp)
        cdef:
            bint should_report_warnings = self._logging_options & self.OPTION_LOG_STATUS_REPORT
            list active_maker_orders = self.active_limit_orders

        try:
            if not self._all_markets_ready:
                self._all_markets_ready = all([market.ready for market in self._sb_markets])
                if not self._all_markets_ready:
                    # Markets not ready yet. Don't do anything.
                    if should_report_warnings:
                        self.logger().warning(f"Markets are not ready. No market making trades are permitted.")
                    return

            if should_report_warnings:
                if not all([market.network_status is NetworkStatus.CONNECTED for market in self._sb_markets]):
                    self.logger().warning(f"WARNING: Some markets are not connected or are down at the moment. Market "
                                          f"making may be dangerous when markets or networks are unstable.")

            for market_info in self._market_infos.values():
                self.c_process_market(market_info)
        finally:
            return

    cdef c_place_order(self, object market_info):
        cdef:
            MarketBase market = market_info.market
            object quantized_amount = market.c_quantize_order_amount(market_info.trading_pair, self._order_amount)
            object quantized_price

        self.logger().info(f"Checking to see if the user has enough balance to place orders")

        if self.c_has_enough_balance(market_info):
            if self._order_type == "market":
                if self._is_buy:
                    order_id = self.c_buy_with_specific_market(market_info,
                                                               amount=quantized_amount)
                    self.logger().info("Market buy order has been executed")
                else:
                    order_id = self.c_sell_with_specific_market(market_info,
                                                                amount=quantized_amount)
                    self.logger().info("Market sell order has been executed")
            else:
                quantized_price = market.c_quantize_order_price(market_info.trading_pair, self._order_price)
                if self._is_buy:
                    order_id = self.c_buy_with_specific_market(market_info,
                                                               amount=quantized_amount,
                                                               order_type=OrderType.LIMIT,
                                                               price=quantized_price)
                    self.logger().info("Limit buy order has been placed")

                else:
                    order_id = self.c_sell_with_specific_market(market_info,
                                                                amount=quantized_amount,
                                                                order_type=OrderType.LIMIT,
                                                                price=quantized_price)
                    self.logger().info("Limit sell order has been placed")

        else:
            self.logger().info(f"Not enough balance to run the strategy. Please check balances and try again.")

    cdef c_has_enough_balance(self, object market_info):
        cdef:
            MarketBase market = market_info.market
            object base_asset_balance = market.c_get_balance(market_info.base_asset)
            object quote_asset_balance = market.c_get_balance(market_info.quote_asset)
            OrderBook order_book = market_info.order_book
            object price = market_info.get_price_for_volume(True, self._order_amount).result_price

        return quote_asset_balance >= self._order_amount * price if self._is_buy else base_asset_balance >= self._order_amount

    cdef c_process_market(self, object market_info):
        cdef:
            MarketBase maker_market = market_info.market

        if self._place_orders:
            self._place_orders = False
            self.c_place_order(market_info)
