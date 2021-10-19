# distutils: language=c++
from decimal import Decimal
from libc.stdint cimport int64_t
import logging
from typing import (
    List,
    Tuple,
    Dict, Optional
)
from hummingbot.core.clock cimport Clock

from hummingbot.core.rate_oracle.rate_oracle import RateOracle
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

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_base import StrategyBase

from hummingbot.strategy.stones.order_levels import OrderLevel

NaN = float("nan")
s_decimal_zero = Decimal(0)
hundred = Decimal('100')
s_decimal_nan = Decimal("nan")
ds_logger = None


cdef class StonesWithPaybackStrategy(StrategyBase):
    OPTION_LOG_NULL_ORDER_SIZE = 1 << 0
    OPTION_LOG_REMOVING_ORDER = 1 << 1
    OPTION_LOG_ADJUST_ORDER = 1 << 2
    OPTION_LOG_CREATE_ORDER = 1 << 3
    OPTION_LOG_MAKER_ORDER_FILLED = 1 << 4
    OPTION_LOG_STATUS_REPORT = 1 << 5
    OPTION_LOG_MAKER_ORDER_HEDGED = 1 << 6
    OPTION_LOG_ALL = 0x7fffffffffffffff

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global ds_logger
        if ds_logger is None:
            ds_logger = logging.getLogger(__name__)
        return ds_logger

    def __init__(self,
                 market_infos: List[MarketTradingPairTuple],
                 total_buy_order_amount: dict,
                 total_sell_order_amount: dict,
                 payback_info: Optional[Dict[MarketTradingPairTuple, MarketTradingPairTuple]] = None,
                 time_delay: float = 10.0,
                 logging_options: int = OPTION_LOG_ALL,
                 status_report_interval: float = 900,
                 buy_order_levels: List[OrderLevel] = None,
                 sell_order_levels: List[OrderLevel] = None,
                 ):
        """
        :param market_infos: list of market trading pairs
        :param market_infos: float value percent
        :param time_delay: how long to wait between placing trades
        :param logging_options: select the types of logs to output
        :param status_report_interval: how often to report network connection related warnings, if any
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

        self._status_report_interval = status_report_interval

        self._all_markets_ready = False
        self._logging_options = logging_options

        self._start_timestamp = 0
        self._last_timestamp = 0

        cdef:
            set all_markets = set([market_info.market for market_info in market_infos])

        self.c_add_markets(list(all_markets))

        self.buy_levels: List[OrderLevel] = []
        self.sell_levels: List[OrderLevel] = []
        self.map_order_id_to_level = dict()
        self.map_order_id_to_oracle_price = dict()
        self.percentage_price_shift_during_payback = hundred / Decimal("0.1")

        self._time_delay = time_delay
        self._total_buy_order_amount = total_buy_order_amount
        self._total_sell_order_amount = total_sell_order_amount

        self._last_opened_order_timestamp = dict()

        self._payback_info = payback_info

        for buy_order_level in buy_order_levels or []:
            self.add_buy_order_level(buy_order_level)
            self._last_opened_order_timestamp[buy_order_level] = 0

        for sell_order_level in sell_order_levels or []:
            self.add_sell_order_level(sell_order_level)
            self._last_opened_order_timestamp[sell_order_level] = 0

    def get_active_orders_by_market_info(self, market_info):
        return self.market_info_to_active_orders.get(market_info, [])

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

        :param order_filled_event: Order filled event
        """
        cdef:
            str order_id = order_filled_event.order_id
            object market_info = self._sb_order_tracker.c_get_shadow_market_pair_from_order_id(order_id)
            tuple order_fill_record

        if market_info is not None:
            limit_order_record = self._sb_order_tracker.c_get_shadow_limit_order(order_id)
            order_fill_record = (limit_order_record, order_filled_event)
            payback_info = self._payback_info.get(market_info)

            if order_filled_event.trade_type is TradeType.BUY:
                if self._logging_options & self.OPTION_LOG_MAKER_ORDER_FILLED:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_info.trading_pair}) Limit buy order of "
                        f"{order_filled_event.amount} {market_info.base_asset} filled."
                    )
                if payback_info is not None:
                    price_multiplier = (Decimal('1') - self.percentage_price_shift_during_payback)
                    payback_price = self.map_order_id_to_oracle_price[order_filled_event.order_id] * price_multiplier
                    best_market_price = payback_info.market.get_price(trading_pair=payback_info.trading_pair,
                                                                      is_buy=False) * price_multiplier

                    # payback_order_id = self.c_place_orders(market_info=payback_info, is_buy=False,
                    #                     order_price=max(payback_price, best_market_price),
                    #                     order_amount=order_filled_event.amount)
                    payback_order_id = "TEST_SELL"

                    if payback_order_id is not None:
                        self.logger().info(
                            f"place buy order {payback_order_id} to {payback_info.market.name} exchange to payback of order {order_filled_event.order_id}."
                            f" Order amount={order_filled_event.amount},"
                            f" order_price={min(payback_price, best_market_price)},"
                            f" op={payback_price},"
                            f" bmp={best_market_price}")
            else:
                if self._logging_options & self.OPTION_LOG_MAKER_ORDER_FILLED:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_info.trading_pair}) Limit sell order of "
                        f"{order_filled_event.amount} {market_info.base_asset} filled."
                    )
                if payback_info is not None:
                    price_multiplier = (Decimal('1') + self.percentage_price_shift_during_payback)
                    payback_price = self.map_order_id_to_oracle_price[order_filled_event.order_id] * price_multiplier
                    best_market_price = payback_info.market.get_price(trading_pair=payback_info.trading_pair,
                                                                      is_buy=True) * price_multiplier

                    # payback_order_id = self.c_place_orders(market_info=payback_info, is_buy=True,
                    #                     order_price=min(payback_price, best_market_price),
                    #                     order_amount=order_filled_event.amount)
                    payback_order_id = "TEST_BUY"
                    if payback_order_id is not None:
                        self.logger().info(f"place buy order {payback_order_id} to {payback_info.market.name} exchange to payback of order {order_filled_event.order_id}."
                                           f" Order amount={order_filled_event.amount},"
                                           f" order_price={min(payback_price, best_market_price)},"
                                           f" op={payback_price},"
                                           f" bmp={best_market_price}")

    cdef c_did_complete_buy_order(self, object order_completed_event):
        """

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
        self.logger().info(f"Waiting for {self._time_delay} to place orders")
        self._start_timestamp = timestamp
        self._last_timestamp = timestamp

        for key in self._last_opened_order_timestamp.keys():
            self._last_opened_order_timestamp[key] = timestamp

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
                else:
                    # Markets are ready, ok to proceed.
                    if self.OPTION_LOG_STATUS_REPORT:
                        self.logger().info(f"Markets are ready. Trading started.")

            if should_report_warnings:
                if not all([market.network_status is NetworkStatus.CONNECTED for market in self._sb_markets]):
                    self.logger().warning(f"WARNING: Some markets are not connected or are down at the moment. Market "
                                          f"making may be dangerous when markets or networks are unstable.")

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
        if quantized_amount == s_decimal_zero:
            self.logger().debug(f"amount ({order_amount}) == 0")
            return
        if self.c_has_enough_balance(market_info, is_buy=is_buy, order_price=order_price, order_amount=quantized_amount):
            quantized_price = market.c_quantize_order_price(market_info.trading_pair, order_price)
            if is_buy:
                order_id = self.c_buy_with_specific_market(market_info,
                                                           amount=quantized_amount,
                                                           order_type=OrderType.LIMIT,
                                                           price=quantized_price)
                self.logger().debug("Limit buy order has been placed")
            else:
                order_id = self.c_sell_with_specific_market(market_info,
                                                            amount=quantized_amount,
                                                            order_type=OrderType.LIMIT,
                                                            price=quantized_price)
                self.logger().debug("Limit sell order has been placed")
            self.logger().info(f"place order {'buy' if is_buy is True else 'sell'} for amount {quantized_amount} with price {quantized_price}. order_id={order_id}")
            return order_id
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

    def get_oracle_price(self, maker_market: ExchangeBase, trading_pair: str):
        oracle_price = self.rate_oracle.rate(trading_pair) or s_decimal_nan

        if oracle_price is not None and not oracle_price.is_nan() and oracle_price > s_decimal_zero:
            oracle_price = maker_market.c_quantize_order_price(trading_pair=trading_pair, price=oracle_price)
        else:
            raise ValueError(f"Oracle price ({oracle_price}) must be > 0")

        return oracle_price

    def find_orders_that_need_closed(self, market_info: MarketTradingPairTuple):
        active_orders = self.get_active_orders_by_market_info(market_info=market_info)
        return list(filter(lambda x: not self.check_on_close_order(exchange=market_info.market, order=x), active_orders))

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

        orders_for_cancel = self.find_orders_that_need_closed(market_info=market_info)

        for order in orders_for_cancel:
            self.logger().info(f"cancel {'buy' if order.is_buy else 'ask'} LIMIT order with {order.client_order_id} ID")
            self.c_cancel_order(market_info, order.client_order_id)

        oracle_price = self.get_oracle_price(maker_market=maker_market, trading_pair=trading_pair)

        buy_orders_data = self.get_data_for_orders(market_info=market_info, current_price=oracle_price, liquidity=self._total_buy_order_amount[trading_pair], is_buy=True)
        for is_buy, price, liquidity, order_level in buy_orders_data:
            if self._last_opened_order_timestamp[order_level] + self._time_delay > self._current_timestamp:
                self.logger().info(f"Delay {(self._last_opened_order_timestamp[order_level] + self._time_delay) - self._current_timestamp} for {order_level}")
                break
            if price > s_decimal_zero and liquidity > s_decimal_zero:
                order_id = self.c_place_orders(market_info, is_buy=is_buy, order_price=price, order_amount=liquidity)
                # order_id = None
                # self.logger().info(f"self.c_place_orders({market_info}, is_buy={is_buy}, order_price={price}, order_amount={liquidity})")
                if order_id is not None:
                    self._last_opened_order_timestamp[order_level] = self._current_timestamp
                    self.map_order_id_to_level[order_id] = order_level
                    self.map_order_id_to_oracle_price[order_id] = oracle_price

        sell_orders_data = self.get_data_for_orders(market_info=market_info, current_price=oracle_price, liquidity=self._total_sell_order_amount[trading_pair], is_buy=False)
        for is_buy, price, liquidity, order_level in sell_orders_data:
            if self._last_opened_order_timestamp[order_level] + self._time_delay > self._current_timestamp:
                break
            if price > s_decimal_zero and liquidity > s_decimal_zero:
                order_id = self.c_place_orders(market_info, is_buy=is_buy, order_price=price, order_amount=liquidity)
                # order_id = None
                # self.logger().info(f"self.c_place_orders({market_info}, is_buy={is_buy}, order_price={price}, order_amount={liquidity})")
                if order_id is not None:
                    self._last_opened_order_timestamp[order_level] = self._current_timestamp
                    self.map_order_id_to_level[order_id] = order_level
                    self.map_order_id_to_oracle_price[order_id] = oracle_price

    def add_order_level(self, level: OrderLevel, is_buy: bool):
        if is_buy is True:
            self.buy_levels.append(level)
        else:
            self.sell_levels.append(level)

    def add_buy_order_level(self, level: OrderLevel):
        self.add_order_level(level=level, is_buy=True)

    def add_sell_order_level(self, level: OrderLevel):
        self.add_order_level(level=level, is_buy=False)

    def get_data_for_orders(self, market_info, current_price: Decimal, liquidity: Decimal, is_buy: bool):
        results = []
        available_liquidity = liquidity
        map_level_to_active_amount = self.get_active_amount_on_levels(market_info=market_info)
        for level in filter(lambda x: x.trading_pair == market_info.trading_pair, self.buy_levels if is_buy is True else self.sell_levels):
            level_liquidity = ((liquidity * level.percentage_of_liquidity) / hundred) - map_level_to_active_amount.get(level, s_decimal_zero)
            self.logger().debug(f"get orders data for {level} with {level_liquidity} liquidity")
            if level_liquidity < level.min_order_amount or available_liquidity < level_liquidity:
                continue
            orders_data = level.get_trades_data(is_buy, current_price, level_liquidity)
            results.extend(orders_data)
            available_liquidity = available_liquidity - sum(map(lambda x: x[2], orders_data))

        return results

    def get_active_amount_on_levels(self, market_info):
        result = {}
        active_orders = self.get_active_orders_by_market_info(market_info)
        for order in active_orders:
            level = self.map_order_id_to_level[order.client_order_id]
            result[level] = result.get(level, s_decimal_zero) + order.quantity
        return result

    def check_on_close_order(self, exchange: ExchangeBase, order: LimitOrder):
        oracle_price = self.get_oracle_price(maker_market=exchange, trading_pair=order.trading_pair)

        try:
            level = self.map_order_id_to_level[order.client_order_id]
            is_at_level = level.is_at_level_of(oracle_price=oracle_price, order_price=order.price, amount=order.quantity, is_buy=order.is_buy)
        except Exception as e:
            self.logger().error(e)
            is_at_level = False

        if not is_at_level:
            self.logger().debug(f"The {order.client_order_id} order has gone beyond the level")

        return is_at_level
