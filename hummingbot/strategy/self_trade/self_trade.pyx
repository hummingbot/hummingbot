# distutils: language=c++
from decimal import Decimal
from libc.stdint cimport int64_t
import logging
import random
from typing import (
    List,
    Tuple,
    Optional,
    Dict
)
from hummingbot.core.clock cimport Clock

from hummingbot.core.rate_oracle.rate_oracle import RateOracle, RateOracleSource
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.limit_order cimport LimitOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.core.event.events import (
    OrderType,
    TradeType
)
from hummingbot.core.data_type.order_book cimport OrderBook
from datetime import datetime, timedelta

from hummingbot.strategy.self_trade.trade_band import TradeBand
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_base import StrategyBase

NaN = float("nan")
s_decimal_zero = Decimal(0)
s_decimal_nan = Decimal("nan")
ds_logger = None


cdef class SelfTradeStrategy(StrategyBase):
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
                 market_infos: List[MarketTradingPairTuple],
                 time_delay: Dict[str, float],
                 min_order_amount: Dict[str, Decimal],
                 max_order_amount: Dict[str, Decimal],
                 trade_bands: Dict[str, List[TradeBand]],
                 delta_price_changed_percent: Dict[str, Decimal],
                 percentage_of_acceptable_price_change: Dict[str, Decimal],
                 cancel_order_wait_time: Optional[float] = 60.0,
                 logging_options: int = OPTION_LOG_ALL,
                 status_report_interval: float = 900,
                 use_only_oracle_price: bool = False):
        """
        :param market_infos: list of market trading pairs
        :param market_infos: float value percent
        :param cancel_order_wait_time: how long to wait before cancelling an order
        :param time_delay: how long to wait between placing trades
        :param min_order_amount: min qty of the order to place
        :param max_order_amount: max qty of the order to place
        :param logging_options: select the types of logs to output
        :param status_report_interval: how often to report network connection related warnings, if any
        :param trade_bands: list restrictions on the trading volume in the timestamp
        """

        if len(market_infos) < 1:
            raise ValueError(f"market_infos must not be empty.")

        super().__init__()
        self.rate_oracle: RateOracle = RateOracle.get_instance()
        self.rate_oracle.start()

        self._market_infos = {
            (market_info.market, market_info.trading_pair): market_info
            for market_info in market_infos
        }

        self._start_timestamp = 0
        self._last_timestamp = 0
        self._logging_options = logging_options
        self._use_only_oracle_price = use_only_oracle_price

        if cancel_order_wait_time is not None:
            self._cancel_order_wait_time = cancel_order_wait_time

        self._status_report_interval = status_report_interval
        self._time_to_cancel = {}

        self._all_markets_ready = False
        self._place_orders = True

        self._time_delay: Dict[str, float] = time_delay
        self._delta_price_changed_percent: Dict[str, Decimal] = delta_price_changed_percent
        self._percentage_of_acceptable_price_change: Dict[str, Decimal] = percentage_of_acceptable_price_change
        self._min_order_amount: Dict[str, Decimal] = min_order_amount
        self._max_order_amount: Dict[str, Decimal] = max_order_amount
        self._trade_bands: Dict[str, List[TradeBand]] = trade_bands

        self._last_trade_timestamp: Dict[str, float] = {market_info.trading_pair: 0 for market_info in market_infos}

        cdef:
            set all_markets = set([market_info.market for market_info in market_infos])

        self.c_add_markets(list(all_markets))

    def get_active_orders(self, market_info):
        return self.market_info_to_active_orders.get(market_info, [])

    @staticmethod
    def get_price_multiplier(delta_price_changed_percent: Decimal) -> Decimal:
        if delta_price_changed_percent == s_decimal_zero:
            return Decimal(1)
        delimiter = Decimal(10 ** 4)
        min_percent = (Decimal(-1) * delimiter * delta_price_changed_percent).quantize(Decimal("0.0001"))
        max_percent = (delimiter * delta_price_changed_percent).quantize(Decimal("0.0001"))
        multiplier = ((random.randint(min_percent, max_percent) / delimiter) / Decimal(100)).quantize(Decimal("0.0001"))

        return Decimal(1) - multiplier

    @property
    def active_bids(self) -> List[Tuple[ExchangeBase, LimitOrder]]:
        return self._sb_order_tracker.active_bids

    @property
    def active_asks(self) -> List[Tuple[ExchangeBase, LimitOrder]]:
        return self._sb_order_tracker.active_asks

    @property
    def active_limit_orders(self) -> List[Tuple[ExchangeBase, LimitOrder]]:
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
            lines.extend(["", "  Markets:"] + ["    " + line for line in str(markets_df).split("\n")])

            assets_df = self.wallet_balance_data_frame([market_info])
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

    cdef c_did_fill_order(self, object order_filled_event):
        """
        Output log for filled order.

        :param order_filled_event: Order filled event
        """
        cdef:
            str order_id = order_filled_event.order_id
            object market_info = self._sb_order_tracker.c_get_shadow_market_pair_from_order_id(order_id)
            tuple order_fill_record

        if market_info is not None:
            limit_order_record = self._sb_order_tracker.c_get_shadow_limit_order(order_id)
            order_fill_record = (limit_order_record, order_filled_event)

            if order_filled_event.trade_type is TradeType.BUY:
                if self._logging_options & self.OPTION_LOG_MAKER_ORDER_FILLED:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_info.trading_pair}) Limit buy order of "
                        f"{order_filled_event.amount} {market_info.base_asset} filled."
                    )
            else:
                if self._logging_options & self.OPTION_LOG_MAKER_ORDER_FILLED:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_info.trading_pair}) Limit sell order of "
                        f"{order_filled_event.amount} {market_info.base_asset} filled."
                    )

    cdef c_did_complete_buy_order(self, object order_completed_event):
        """
        Output log for completed buy order.

        :param order_completed_event: Order completed event
        """
        cdef:
            str order_id = order_completed_event.order_id
            object market_info = self._sb_order_tracker.c_get_market_pair_from_order_id(order_id)
            LimitOrder limit_order_record

        if market_info is not None:
            limit_order_record = self._sb_order_tracker.c_get_limit_order(market_info, order_id)
            # If its not market order
            if limit_order_record is not None:
                self.log_with_clock(
                    logging.INFO,
                    f"({market_info.trading_pair}) Limit buy order {order_id} "
                    f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                    f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
                )

    cdef c_did_complete_sell_order(self, object order_completed_event):
        """
        Output log for completed sell order.

        :param order_completed_event: Order completed event
        """
        cdef:
            str order_id = order_completed_event.order_id
            object market_info = self._sb_order_tracker.c_get_market_pair_from_order_id(order_id)
            LimitOrder limit_order_record

        if market_info is not None:
            limit_order_record = self._sb_order_tracker.c_get_limit_order(market_info, order_id)
            # If its not market order
            if limit_order_record is not None:
                self.log_with_clock(
                    logging.INFO,
                    f"({market_info.trading_pair}) Limit sell order {order_id} "
                    f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                    f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
                )

    cdef c_start(self, Clock clock, double timestamp):
        StrategyBase.c_start(self, clock, timestamp)
        self._start_timestamp = timestamp
        self._last_timestamp = timestamp

        for key in self._last_trade_timestamp.keys():
            self._last_trade_timestamp[key] = timestamp

        for key, value in self._time_delay.items():
            # self._time_delay[key] = 30
            self.logger().info(f"Waiting for {value} to place {key} orders")

    cdef c_tick(self, double timestamp):
        """
        Clock tick entry point.

        For the simple trade strategy, this function simply checks for the readiness and connection status of markets, and
        then delegates the processing of each market info to c_process_market().

        :param timestamp: current tick timestamp
        """
        StrategyBase.c_tick(self, timestamp)
        cdef:
            int64_t current_tick = <int64_t>(timestamp // self._status_report_interval)
            int64_t last_tick = <int64_t>(self._last_timestamp // self._status_report_interval)
            bint should_report_warnings = ((current_tick > last_tick) and (self._logging_options & self.OPTION_LOG_STATUS_REPORT))
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

            for bands in self._trade_bands.values():
                list(map(lambda x: x.tick(current_timestamp=timestamp), bands))
            for market_info in self._market_infos.values():
                self.c_process_market(market_info)
        finally:
            self._last_timestamp = timestamp

    cdef c_place_orders(self, object market_info, is_buy: bool, order_price: Decimal, order_amount: Decimal):
        """
        Places an order specified by the user input if the user has enough balance

        :param market_info: a market trading pair
        :param is_buy:
        :param order_price:
        :param order_amount:
        """
        cdef:
            ExchangeBase market = market_info.market
            object quantized_amount = market.c_quantize_order_amount(market_info.trading_pair, order_amount)
            object quantized_price

        self.logger().info(f"Checking to see if the user has enough balance to place orders")
        if self.c_has_enough_balance(market_info, is_buy=is_buy, order_price=order_price, order_amount=order_amount):
            quantized_price = market.c_quantize_order_price(market_info.trading_pair, order_price)
            if is_buy:
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

            self._time_to_cancel[order_id] = self._current_timestamp + self._cancel_order_wait_time
        else:
            self.logger().info(f"Not enough balance to run the strategy. Please check balances and try again.")

    cdef c_has_enough_balance(self, object market_info, is_buy: bool, order_price: Decimal, order_amount: Decimal):
        """
        Checks to make sure the user has the sufficient balance in order to place the specified order

        :param market_info: a market trading pair
        :param is_buy:
        :param order_price:
        :param order_amount:
        :return: True if user has enough balance, False if not
        """
        cdef:
            ExchangeBase market = market_info.market
            object base_asset_balance = market.c_get_balance(market_info.base_asset)
            object quote_asset_balance = market.c_get_balance(market_info.quote_asset)
            OrderBook order_book = market_info.order_book
            object price = market_info.get_price_for_volume(True, order_amount).result_price if order_price is None else order_price

        return quote_asset_balance >= order_amount * price if is_buy else base_asset_balance >= order_amount

    def get_price(self, maker_market: ExchangeBase, trading_pair: str):
        price_multiplier = self.get_price_multiplier(delta_price_changed_percent=self._delta_price_changed_percent[trading_pair])
        oracle_price = self.rate_oracle.rate(trading_pair) or s_decimal_nan

        if oracle_price is not None and not oracle_price.is_nan() and oracle_price > s_decimal_zero:
            quantized_oracle_price = maker_market.c_quantize_order_price(trading_pair=trading_pair, price=oracle_price * price_multiplier)
        else:
            raise ValueError(f"Oracle price ({oracle_price}) must be > 0")

        buy_price = maker_market.get_price(trading_pair=trading_pair, is_buy=False) or s_decimal_nan
        sell_price = maker_market.get_price(trading_pair=trading_pair, is_buy=True) or s_decimal_nan

        self.logger().info(f"price_multiplier: {price_multiplier}")
        self.logger().info(f"buy_price: {buy_price}")
        self.logger().info(f"sell_price: {sell_price}")
        self.logger().info(f"raw_oracle_price: {oracle_price}")
        self.logger().info(f"oracle_price: {quantized_oracle_price}")

        if self._use_only_oracle_price is True:
            quantized_price = quantized_oracle_price
        elif buy_price.is_nan() or sell_price.is_nan():
            quantized_price = quantized_oracle_price
            self.logger().warning(
                f"No sell orders or no buy orders were found, the price will be taken from an open source. "
                f"price={quantized_price}")
        elif not buy_price.is_nan() and not sell_price.is_nan():
            if buy_price > sell_price:
                raise ValueError("buy_price must be less than sell_price")

            price = (buy_price + ((sell_price - buy_price) / Decimal(2)))
            quantized_price = maker_market.c_quantize_order_price(trading_pair=trading_pair, price=price * price_multiplier)

        currently_percentage_price_change = abs(
            Decimal("100") - (quantized_price * Decimal("100")) / quantized_oracle_price
        ).quantize(Decimal("0.0001"))

        if currently_percentage_price_change > self._percentage_of_acceptable_price_change[trading_pair]:
            self.logger().warning(f"the price ({quantized_price}) should not differ from the market "
                                  f"price ({quantized_oracle_price}) by more than {self._percentage_of_acceptable_price_change[trading_pair]}%."
                                  f" Currently differ is {currently_percentage_price_change}%. Used Oracle Price")
            quantized_price = quantized_oracle_price

        buy_price = maker_market.get_price(trading_pair=trading_pair, is_buy=False) or s_decimal_nan
        sell_price = maker_market.get_price(trading_pair=trading_pair, is_buy=True) or s_decimal_nan
        if not buy_price.is_nan() and not buy_price < quantized_price:
            self.logger().warning(f"price ({quantized_price}) must be > buy_price ({buy_price})")
            raise ValueError("price must be > buy_price")
        if not sell_price.is_nan() and not sell_price > quantized_price:
            self.logger().warning(f"price ({quantized_price}) must be < sell_price ({sell_price})")
            raise ValueError("price must be < sell_price")

        self.logger().info(f"price for {trading_pair} pair = {quantized_price}")
        return quantized_price

    cdef c_process_market(self, object market_info):
        """
        Checks if enough time has elapsed to place orders and if so, calls c_place_orders() and cancels orders if they
        are older than self._cancel_order_wait_time.

        :param market_info: a market trading pair
        """
        cdef:
            ExchangeBase maker_market = market_info.market
            set cancel_order_ids = set()
            str trading_pair = market_info.trading_pair

        if self._current_timestamp > self._last_trade_timestamp[trading_pair] + self._time_delay[trading_pair]:
            self.logger().info(f"Current time: "
                               f"{datetime.fromtimestamp(self._current_timestamp).strftime('%Y-%m-%d %H:%M:%S')} "
                               f"- start trading {trading_pair}")
            try:
                quant = Decimal(10**27)
                amount = random.randint(self._min_order_amount[trading_pair] * quant, self._max_order_amount[trading_pair] * quant) / quant
                amount = maker_market.quantize_order_amount(trading_pair=trading_pair, amount=amount)

                if all(map(lambda x: x.check(amount=amount), self._trade_bands[trading_pair])):
                    price: Decimal = self.get_price(maker_market=maker_market, trading_pair=trading_pair)
                    self.c_place_orders(market_info, is_buy=True, order_price=price, order_amount=amount)
                    self.c_place_orders(market_info, is_buy=False, order_price=price, order_amount=amount)
                    self._last_trade_timestamp[trading_pair] = self._current_timestamp
                    list(map(lambda x: x.create_trade(amount=amount), self._trade_bands[trading_pair]))
                else:
                    self.logger().info(f"Не проходит BAND")
            except Exception as e:
                self.logger().error(e, exc_info=True)

        active_orders = self.get_active_orders(market_info)
        if len(active_orders) > 0:
            for active_order in active_orders:
                if self._current_timestamp >= self._time_to_cancel[active_order.client_order_id]:
                    cancel_order_ids.add(active_order.client_order_id)

        if len(cancel_order_ids) > 0:
            for order in cancel_order_ids:
                self.c_cancel_order(market_info, order)
