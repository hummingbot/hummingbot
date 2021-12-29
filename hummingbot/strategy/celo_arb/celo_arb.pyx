# distutils: language=c++
from decimal import Decimal
from libc.stdint cimport int64_t
import logging
from typing import (
    List,
    Tuple,
    Dict
)
import pandas as pd
import asyncio
from functools import partial
from hummingbot.core.clock cimport Clock
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.limit_order cimport LimitOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler, safe_ensure_future
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_base import StrategyBase
from hummingbot.connector.other.celo.celo_cli import (
    CeloCLI,
    CELO_BASE,
    CELO_QUOTE,
)
from hummingbot.connector.other.celo.celo_data_types import (
    CeloOrder,
    CeloArbTradeProfit
)
from hummingbot.core.event.events import (
    OrderType
)
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.model.trade_fill import TradeFill


NaN = float("nan")
s_decimal_zero = Decimal(0)
ds_logger = None
NODE_SYNCED_CHECK_INTERVAL = 60.0 * 5.0


def get_trade_profits(market, trading_pair: str, order_amount: Decimal) -> List[CeloArbTradeProfit]:
    order_amount = Decimal(str(order_amount))
    results = []
    # Find Celo counter party price for the order_amount
    # volume weighted average price is used for profit calculation.
    query_result = market.get_vwap_for_volume(trading_pair, True, float(order_amount))
    ctp_vwap_buy = Decimal(str(query_result.result_price))
    # actual price for order is the last price the volume reaches.
    query_result = market.get_price_for_volume(trading_pair, True, float(order_amount))
    ctp_buy = Decimal(str(query_result.result_price))

    query_result = market.get_vwap_for_volume(trading_pair, False, float(order_amount))
    ctp_vwap_sell = Decimal(str(query_result.result_price))
    query_result = market.get_price_for_volume(trading_pair, False, float(order_amount))
    ctp_sell = Decimal(str(query_result.result_price))
    # Celo exchange rate show buy result in USD amount
    celo_buy_amount = ctp_vwap_sell * order_amount
    celo_ex_rates = CeloCLI.exchange_rate(celo_buy_amount)
    celo_buy_ex_rate = [r for r in celo_ex_rates if r.to_token == CELO_BASE and r.from_token == CELO_QUOTE][0]
    celo_buy = celo_buy_ex_rate.from_amount / celo_buy_ex_rate.to_amount
    celo_ex_rates = CeloCLI.exchange_rate(order_amount)
    celo_sell_ex_rate = [r for r in celo_ex_rates if r.from_token == CELO_BASE and r.to_token == CELO_QUOTE][0]
    celo_sell = celo_sell_ex_rate.to_amount / celo_sell_ex_rate.from_amount
    celo_buy_profit = (ctp_vwap_sell - celo_buy) / celo_buy
    results.append(CeloArbTradeProfit(True, ctp_sell, ctp_vwap_sell, celo_buy, celo_buy_profit))
    celo_sell_profit = (celo_sell - ctp_vwap_buy) / ctp_vwap_buy
    results.append(CeloArbTradeProfit(False, ctp_buy, ctp_vwap_buy, celo_sell, celo_sell_profit))
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

    def init_params(self,
                    market_info: MarketTradingPairTuple,
                    min_profitability: Decimal,
                    order_amount: Decimal,
                    celo_slippage_buffer: Decimal = Decimal("0.0001"),
                    logging_options: int = OPTION_LOG_ALL,
                    status_report_interval: float = 900,
                    hb_app_notification: bool = True,
                    mock_celo_cli_mode: bool = False):
        self._market_info = market_info
        self._exchange = market_info.market.name
        self._min_profitability = min_profitability
        self._order_amount = order_amount
        self._celo_slippage_buffer = celo_slippage_buffer
        self._mock_celo_cli_mode = mock_celo_cli_mode
        self._last_no_arb_reported = 0
        self._trade_profits = None
        self._celo_orders = []
        self._all_markets_ready = False
        self._logging_options = logging_options

        self._ev_loop = asyncio.get_event_loop()
        self._async_scheduler = None
        self._main_task = None
        self._last_synced_checked = 0
        self._node_synced = False

        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self._hb_app_notification = hb_app_notification
        self.c_add_markets([market_info.market])

    @property
    def celo_slippage_buffer(self):
        return self._celo_slippage_buffer

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
    def celo_orders(self) -> List[CeloOrder]:
        return self._celo_orders

    @property
    def active_bids(self) -> List[Tuple[ExchangeBase, LimitOrder]]:
        return self._sb_order_tracker.active_bids

    @property
    def active_asks(self) -> List[Tuple[ExchangeBase, LimitOrder]]:
        return self._sb_order_tracker.active_asks

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

        if self._trade_profits is None:
            return "  The strategy is not ready, please try again later."
        active_orders = self.market_info_to_active_orders.get(self._market_info, [])

        markets_df = self.market_status_data_frame([self._market_info])
        celo_buy = [trade for trade in self._trade_profits if trade.is_celo_buy][0]
        celo_sell = [trade for trade in self._trade_profits if not trade.is_celo_buy][0]
        celo_ask_price = round(celo_buy.celo_price, 3)
        celo_bid_price = round(celo_sell.celo_price, 3)
        celo_mid_price = round((celo_bid_price + celo_ask_price) / 2, 3)

        series = [pd.Series(["Celo", f"{CELO_BASE}-{CELO_QUOTE}", celo_bid_price, celo_ask_price, celo_mid_price],
                            index=markets_df.columns)]
        markets_df = markets_df.append(series, ignore_index=True)
        lines.extend(["", "  Markets:"] + ["    " + line for line in markets_df.to_string(index=False).split("\n")])

        warning_lines.extend(self.network_warning([self._market_info]))

        assets_df = self.wallet_balance_data_frame([self._market_info])
        celo_bals = CeloCLI.balances()
        series = []
        for token, bal in celo_bals.items():
            series.append(pd.Series(["Celo", token, round(bal.total, 2), round(bal.available(), 2)],
                                    index=assets_df.columns))
        assets_df = assets_df.append(series, ignore_index=True)
        lines.extend(["", "  Assets:"] +
                     ["    " + line for line in str(assets_df).split("\n")])

        lines.extend(["", "  Profitability:"] +
                     [f"    buy at celo, sell at {self._exchange}: {celo_buy.profit:.2%}"] +
                     [f"    sell at celo, buy at {self._exchange}: {celo_sell.profit:.2%}"])

        warning_lines.extend(self.balance_warning([self._market_info]))

        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    cdef c_stop(self, Clock clock):
        if self._main_task is not None and not self._main_task.done():
            self._main_task.cancel()
            self._main_task = None
        StrategyBase.c_stop(self, clock)

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
            if self._async_scheduler is None:
                self._async_scheduler = AsyncCallScheduler(call_interval=1)
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
        if self._mock_celo_cli_mode:
            self.main_process()
        else:
            if self._main_task is None or self._main_task.done():
                coro = self._async_scheduler.call_async(self.main_process, timeout_seconds=30)
                self._main_task = safe_ensure_future(coro)

    def main_process(self):
        if self._last_synced_checked < self._current_timestamp - NODE_SYNCED_CHECK_INTERVAL:
            err_msg = CeloCLI.validate_node_synced()
            self._node_synced = err_msg is None
            self._last_synced_checked = self._current_timestamp
            check_msg = "synced" if err_msg is None else f"Error: {err_msg}"
            self.log_with_clock(logging.INFO, f"Node sync check - {check_msg}")
        if not self._node_synced:
            return
        self._trade_profits = get_trade_profits(self._market_info.market, self._market_info.trading_pair, self._order_amount)
        arb_trades = [t for t in self._trade_profits if t.profit >= self._min_profitability]
        if len(arb_trades) == 0:
            if self._last_no_arb_reported < self._current_timestamp - 20:
                self.logger().info(f"No arbitrage opportunity: {self._trade_profits[0]} {self._trade_profits[1]}")
                self._last_no_arb_reported = self._current_timestamp
            return
        for arb_trade in arb_trades:
            self.logger().info(f"Found arbitrage opportunity!: {arb_trade}")
            if arb_trade.is_celo_buy:
                self.c_execute_buy_celo_sell_ctp(arb_trade)
            else:
                self.c_execute_sell_celo_buy_ctp(arb_trade)

    cdef c_execute_buy_celo_sell_ctp(self, object celo_buy_trade):
        """
        Executes arbitrage trades for the input trade profit tuple.

        :type celo_buy_trade: tuple
        """
        cdef:
            object quantized_buy_amount
            object quantized_sell_amount
            ExchangeBase market = self._market_info.market

        quantized_sell_amount = market.c_quantize_order_amount(self._market_info.trading_pair,
                                                               self._order_amount)
        buy_amount = min(quantized_sell_amount, self._order_amount)
        if buy_amount <= 0:
            return

        sell_balance = market.c_get_available_balance(self._market_info.base_asset)
        if sell_balance < quantized_sell_amount:
            self.logger().info(f"Can't arbitrage, {self._exchange} "
                               f"{self._market_info.base_asset} balance "
                               f"({sell_balance}) is below required sell amount ({quantized_sell_amount}).")
            return
        cusd_required = buy_amount * celo_buy_trade.celo_price
        celo_bals = CeloCLI.balances()
        if celo_bals[CELO_QUOTE].available() < cusd_required:
            self.logger().info(f"Can't arbitrage, Celo {CELO_QUOTE} available balance "
                               f"({celo_bals[CELO_QUOTE].available()}) is below required buy amount "
                               f"({cusd_required}).")
            return
        self.log_with_clock(logging.INFO,
                            f"Buying {buy_amount} {CELO_BASE} at Celo at {celo_buy_trade.celo_price:.3f} price")
        min_cgld_returned = buy_amount * (Decimal("1") - self._celo_slippage_buffer)
        try:
            tx_hash = CeloCLI.buy_cgld(cusd_required, min_cgld_returned=min_cgld_returned)
        except Exception as err:
            self.log_with_clock(logging.INFO, str(err))
            return
        celo_order = CeloOrder(tx_hash, True, celo_buy_trade.celo_price, buy_amount, self._current_timestamp)
        self._celo_orders.append(celo_order)
        self.log_n_notify(f"Bought {celo_order.amount} {CELO_BASE} at Celo at {celo_order.price:.3f} price "
                          f"and selling {quantized_sell_amount} {self._market_info.base_asset} at "
                          f"{market.name} ({self._market_info.trading_pair}) "
                          f"at {celo_buy_trade.ctp_price:.3f} price. "
                          f"Arb profit: {celo_buy_trade.profit:.2%}")
        if self._mock_celo_cli_mode:
            self.sell_with_specific_market(self._market_info, quantized_sell_amount, order_type=OrderType.LIMIT,
                                           price=celo_buy_trade.ctp_price)
        else:
            self._ev_loop.call_soon_threadsafe(partial(self.sell_with_specific_market,
                                                       self._market_info,
                                                       quantized_sell_amount,
                                                       order_type=OrderType.LIMIT,
                                                       price=celo_buy_trade.ctp_price))

    cdef c_execute_sell_celo_buy_ctp(self, object celo_sell_trade):
        """
        Executes arbitrage trades for the input trade profit tuple.

        :type celo_sell_trade: tuple
        """
        cdef:
            object quantized_buy_amount
            object quantized_sell_amount
            object quantized_order_amount = Decimal("0")
            ExchangeBase market = self._market_info.market

        quantized_buy_amount = market.c_quantize_order_amount(self._market_info.trading_pair,
                                                              self._order_amount,
                                                              price=celo_sell_trade.ctp_price)
        sell_amount = min(quantized_buy_amount, self._order_amount)

        if sell_amount <= 0:
            return

        buy_balance = market.c_get_available_balance(self._market_info.quote_asset)
        buy_required = celo_sell_trade.ctp_price * quantized_buy_amount
        if buy_balance < buy_required:
            self.logger().info(f"Can't arbitrage, {self._exchange} "
                               f"{self._market_info.quote_asset} balance "
                               f"({buy_balance}) is below required buy amount ({buy_required}).")
            return
        celo_bals = CeloCLI.balances()
        if celo_bals[CELO_BASE].available() < sell_amount:
            self.logger().info(f"Can't arbitrage, Celo {CELO_BASE} available balance "
                               f"({celo_bals[CELO_BASE].available()}) is below required sell amount "
                               f"({sell_amount}).")
            return
        self.log_with_clock(logging.INFO,
                            f"Selling {sell_amount} {CELO_BASE} at Celo at {celo_sell_trade.celo_price:.3f}")
        min_cusd_returned = sell_amount * celo_sell_trade.celo_price * (Decimal("1") -
                                                                        self._celo_slippage_buffer)
        try:
            tx_hash = CeloCLI.sell_cgld(sell_amount, min_cusd_returned=min_cusd_returned)
        except Exception as err:
            self.log_with_clock(logging.INFO, str(err))
            return
        celo_order = CeloOrder(tx_hash, False, celo_sell_trade.celo_price, sell_amount, self._current_timestamp)
        self._celo_orders.append(celo_order)
        self.log_n_notify(f"Sold {celo_order.amount} {CELO_BASE} at Celo at {celo_order.price:.3f} "
                          f"price and buying {quantized_buy_amount} {self._market_info.base_asset} at "
                          f"{market.name} ({self._market_info.trading_pair}) "
                          f"at {celo_sell_trade.ctp_price:.3f} price. "
                          f"Arb profit: {celo_sell_trade.profit:.2%}")
        if self._mock_celo_cli_mode:
            self.buy_with_specific_market(self._market_info, quantized_buy_amount, order_type=OrderType.LIMIT,
                                          price=celo_sell_trade.ctp_price)
        else:
            self._ev_loop.call_soon_threadsafe(partial(self.buy_with_specific_market,
                                                       self._market_info,
                                                       quantized_buy_amount,
                                                       order_type=OrderType.LIMIT,
                                                       price=celo_sell_trade.ctp_price))

    def log_n_notify(self, msg: str):
        self.log_with_clock(logging.INFO, msg)
        if self._hb_app_notification:
            from hummingbot.client.hummingbot_application import HummingbotApplication
            HummingbotApplication.main_application()._notify(msg)

    def celo_orders_to_trade_fills(self):
        results = []
        for order in self._celo_orders:
            results.append(TradeFill(strategy="celo_arb",
                                     market="celo",
                                     symbol=f"{CELO_BASE}-{CELO_QUOTE}",
                                     base_asset=CELO_BASE,
                                     quote_asset=CELO_QUOTE,
                                     timestamp=int(order.timestamp * 1e3),
                                     order_id=order.tx_hash,
                                     trade_type="buy" if order.is_buy else "sell",
                                     order_type="n/a",
                                     price=float(order.price),
                                     amount=float(order.amount),
                                     trade_fee=AddedToCostTradeFee(Decimal("0")).to_json(),
                                     exchange_trade_id=order.tx_hash))
        return results
