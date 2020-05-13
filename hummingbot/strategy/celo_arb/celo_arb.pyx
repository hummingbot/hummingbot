# distutils: language=c++
from decimal import Decimal
from libc.stdint cimport int64_t
import logging
from typing import (
    List,
    Tuple,
    Dict
)
import time

from hummingbot.core.clock cimport Clock
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.limit_order cimport LimitOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.network_iterator import NetworkStatus
from libc.stdint cimport int64_t
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.market.market_base import MarketBase
from hummingbot.market.market_base cimport MarketBase
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_base import StrategyBase
from hummingbot.market.celo.celo_cli import (
    CeloCLI,
    CELO_BASE,
    CELO_QUOTE,
)
from hummingbot.market.celo.celo_data_types import (
    CeloOrder,
    CeloArbTradeProfit
)
from hummingbot.core.event.events import (
    TradeType,
    OrderType,
)

NaN = float("nan")
s_decimal_zero = Decimal(0)
ds_logger = None


# returns a list of tuple (is_celo_buy, ctp_price, celo_price, profit)
def get_trade_profits(market, trading_pair: str, order_amount: Decimal) -> List[CeloArbTradeProfit]:
    order_amount = Decimal(str(order_amount))
    results = []
    # Find Celo counter party price for the order_amount
    query_result = market.get_vwap_for_volume(trading_pair, True, float(order_amount))
    ctp_buy = Decimal(str(query_result.result_price))
    query_result = market.get_vwap_for_volume(trading_pair, False, float(order_amount))
    ctp_sell = Decimal(str(query_result.result_price))
    # Celo exchange rate show buy result in USD amount
    celo_buy_amount = ctp_sell * order_amount
    celo_ex_rates = CeloCLI.exchange_rate(celo_buy_amount)
    print(celo_ex_rates)
    celo_buy_ex_rate = [r for r in celo_ex_rates if r.to_token == CELO_BASE and r.from_token == CELO_QUOTE][0]
    celo_buy = celo_buy_ex_rate.from_amount / celo_buy_ex_rate.to_amount
    celo_ex_rates = CeloCLI.exchange_rate(order_amount)
    print(celo_ex_rates)
    celo_sell_ex_rate = [r for r in celo_ex_rates if r.from_token == CELO_BASE and r.to_token == CELO_QUOTE][0]
    celo_sell = celo_sell_ex_rate.to_amount / celo_sell_ex_rate.from_amount
    celo_buy_profit = (ctp_sell - celo_buy) / celo_buy
    results.append(CeloArbTradeProfit(True, ctp_sell, celo_buy, celo_buy_profit))
    celo_sell_profit = (celo_sell - ctp_buy) / ctp_buy
    results.append(CeloArbTradeProfit(False, ctp_buy, celo_sell, celo_sell_profit))
    return results


cdef class CeloArbStrategy(StrategyBase):
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
        global ds_logger
        if ds_logger is None:
            ds_logger = logging.getLogger(__name__)
        return ds_logger

    def __init__(self,
                 market_info: MarketTradingPairTuple,
                 min_profitability: Decimal,
                 order_amount: Decimal,
                 logging_options: int = OPTION_LOG_ALL,
                 status_report_interval: float = 900):
        super().__init__()
        self._market_info = market_info
        self._exchange = market_info.market.name
        self._min_profitability = min_profitability
        self._order_amount = order_amount
        self._celo_orders = []
        self._all_markets_ready = False
        self._logging_options = logging_options

        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self.c_add_markets([market_info.market])

    @property
    def celo_orders(self) -> List[CeloOrder]:
        return self._celo_orders

    @property
    def active_bids(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return self._sb_order_tracker.active_bids

    @property
    def active_asks(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return self._sb_order_tracker.active_asks

    @property
    def active_maker_orders(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return self._sb_order_tracker.active_maker_orders

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

        active_orders = self.market_info_to_active_orders.get(self._market_info, [])

        warning_lines.extend(self.network_warning([self._market_info]))

        lines.extend(["", "  Assets:"] + ["    " + str(self._asset_trading_pair) + "    " +
                                          str(self._market_info.market.get_balance(self._asset_trading_pair))])

        warning_lines.extend(self.balance_warning([self._market_info]))

        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    cdef c_tick(self, double timestamp):
        """
        Clock tick entry point.

        :param timestamp: current tick timestamp
        """
        StrategyBase.c_tick(self, timestamp)

        cdef:
            int64_t current_tick = <int64_t>(timestamp // self._status_report_interval)
            int64_t last_tick = <int64_t>(self._last_timestamp // self._status_report_interval)
            bint should_report_warnings = ((current_tick > last_tick) and
                                           (self._logging_options & self.OPTION_LOG_STATUS_REPORT))
        try:
            if not self._all_markets_ready:
                self._all_markets_ready = all([market.ready for market in self._sb_markets])
                if not self._all_markets_ready:
                    # Markets not ready yet. Don't do anything.
                    if should_report_warnings:
                        self.logger().warning(f"Markets are not ready. No arbitrage trading is permitted.")
                    return
                else:
                    if self.OPTION_LOG_STATUS_REPORT:
                        self.logger().info(f"Markets are ready. Trading started.")

            if not all([market.network_status is NetworkStatus.CONNECTED for market in self._sb_markets]):
                if should_report_warnings:
                    self.logger().warning(f"Markets are not all online. No arbitrage trading is permitted.")
                return

            self.c_main()
        finally:
            self._last_timestamp = timestamp

    cdef c_main(self):
        trade_profits = get_trade_profits(self._market_info.market, self._market_info.trading_pair, self._order_amount)
        arb_trades = [t for t in trade_profits if t.profit >= self._min_profitability]
        if arb_trades > 1:
            raise Exception("Found 2 profitable trades from 2 markets, something went wrong.")
        if arb_trades == 0:
            return
        if arb_trades[0][0]:
            self.c_execute_buy_celo_sell_ctp(arb_trades[0])
        else:
            self.c_execute_sell_celo_buy_ctp(arb_trades[0])

    cdef c_execute_buy_celo_sell_ctp(self, object trade_profit):
        """
        Executes arbitrage trades for the input trade profit tuple.

        :type trade_profit: tuple
        """
        cdef:
            object quantized_buy_amount
            object quantized_sell_amount
            object quantized_order_amount = Decimal("0")

        quantized_sell_amount = self._market_info.market.c_quantize_order_amount(self._market_info.trading_pair,
                                                                                 self._order_amount)
        buy_amount = min(quantized_sell_amount, self._order_amount)

        if quantized_order_amount > 0:
            sell_balance = self._market_info.market.c_get_balance(self._market_info.quote_asset)
            if sell_balance < quantized_sell_amount:
                self.log_with_clock(logging.INFO, f"Can't execute arbitrage, {self._exchange} "
                                                  f"{self._market_info.base_asset} balance "
                                                  f"({sell_balance}) is below required sell amount"
                                                  f" ({quantized_sell_amount}).")
                return
            cusd_required = buy_amount * trade_profit.celo_price
            celo_bals = CeloCLI.balances()
            if celo_bals[CELO_QUOTE] < cusd_required:
                self.log_with_clock(logging.INFO, f"Can't execute arbitrage, Celo {CELO_QUOTE} balance "
                                                  f"({celo_bals[CELO_QUOTE]}) is below required buy amount "
                                                  f"({cusd_required}).")
                return

            if self._logging_options & self.OPTION_LOG_CREATE_ORDER:
                self.log_with_clock(logging.INFO,
                                    f"Buying {CELO_BASE} at Celo for {cusd_required} {CELO_QUOTE} and selling "
                                    f"{quantized_order_amount} {self._market_info.base_asset} at "
                                    f"{self._market_info.market.name} ({self._market_info.trading_pair.trading_pair})"
                                    f"at {trade_profit.ctp_price} price, "
                                    f"and profitability of {trade_profit.profit}")
            tx_hash = CeloCLI.buy_cgld(cusd_required)
            celo_order = CeloOrder(tx_hash, True, trade_profit.celo_price, buy_amount, time.time())
            self._celo_orders.append(celo_order)

            self.c_sell_with_specific_market(self._market_info, quantized_sell_amount,
                                             order_type=OrderType.LIMIT, price=trade_profit.ctp_price)

    cdef c_execute_sell_celo_buy_ctp(self, object trade_profit):
        """
        Executes arbitrage trades for the input trade profit tuple.

        :type trade_profit: tuple
        """
        cdef:
            object quantized_buy_amount
            object quantized_sell_amount
            object quantized_order_amount = Decimal("0")

        quantized_buy_amount = self._market_info.market.c_quantize_order_amount(self._market_info.trading_pair,
                                                                                self._order_amount)
        sell_amount = min(quantized_buy_amount, self._order_amount)

        if sell_amount > 0:
            buy_balance = self._market_info.market.c_get_balance(self._market_info.quote_asset)
            buy_required = trade_profit.ctp_price * quantized_buy_amount
            if buy_balance < buy_required:
                self.log_with_clock(logging.INFO, f"Can't execute arbitrage, {self._exchange} "
                                                  f"{self._market_info.base_asset} balance "
                                                  f"({buy_balance}) is below required buy amount"
                                                  f" ({buy_required}).")
                return
            celo_bals = CeloCLI.balances()
            if celo_bals[CELO_BASE] < sell_amount:
                self.log_with_clock(logging.INFO, f"Can't execute arbitrage, Celo {CELO_BASE} balance "
                                                  f"({celo_bals[CELO_BASE]}) is below required sell amount "
                                                  f"({sell_amount}).")
                return
            if self._logging_options & self.OPTION_LOG_CREATE_ORDER:
                self.log_with_clock(logging.INFO,
                                    f"Selling {sell_amount} {CELO_BASE} at Celo and buying "
                                    f"{quantized_buy_amount} {self._market_info.base_asset} at "
                                    f"{self._market_info.market.name} ({self._market_info.trading_pair.trading_pair})"
                                    f"at {trade_profit.ctp_price} price, "
                                    f"and profitability of {trade_profit.profit}")
            tx_hash = CeloCLI.sell_cgld(sell_amount)
            celo_order = CeloOrder(tx_hash, True, trade_profit.celo_price, sell_amount, time.time())
            self._celo_orders.append(celo_order)
            self.c_buy_with_specific_market(self._market_info, quantized_buy_amount,
                                            order_type=OrderType.LIMIT, price=trade_profit.ctp_price)
