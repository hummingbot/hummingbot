# distutils: sources=['hummingbot/core/cpp/Utils.cpp', 'hummingbot/core/cpp/LimitOrder.cpp', 'hummingbot/core/cpp/OrderExpirationEntry.cpp']

import asyncio
from async_timeout import timeout
from collections import deque
from cpython cimport PyObject
from cython.operator cimport (
    postincrement as inc,
    dereference as deref,
    address
)
from decimal import Decimal
from functools import partial
import hummingbot
from libcpp cimport bool as cppbool
from libcpp.vector cimport vector
import logging
import math
import pandas as pd
import random
import time
from typing import (
    Dict,
    List,
    Coroutine
)

from hummingbot.core.clock cimport Clock
from hummingbot.core.clock import (
    ClockMode,
    Clock
)
from hummingbot.core.Utils cimport (
    getIteratorFromReverseIterator,
    reverse_iterator
)

from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order cimport c_create_limit_order_from_cpp_limit_order
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.event.events import MarketEvent, OrderType, OrderExpiredEvent, TradeType, TradeFee, \
    BuyOrderCompletedEvent, OrderFilledEvent, SellOrderCompletedEvent
from hummingbot.core.event.event_listener cimport EventListener
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.market.deposit_info import DepositInfo
from hummingbot.market.market_base import MarketBase
from hummingbot.market.paper_trade.symbol_pair import SymbolPair

from .market_config import (
    MarketConfig,
    AssetType
)

s_logger = None


cdef class QuantizationParams:
    cdef:
        str symbol
        int price_precision
        int price_decimals
        int order_size_precision
        int order_size_decimals

    def __init__(self,
                 str symbol,
                 int price_precision,
                 int price_decimals,
                 int order_size_precision,
                 int order_size_decimals):
        self.symbol = symbol
        self.price_precision = price_precision
        self.price_decimals = price_decimals
        self.order_size_precision = order_size_precision
        self.order_size_decimals = order_size_decimals

    def __repr__(self) -> str:
        return (f"QuantizationParams('{self.symbol}', {self.price_precision}, {self.price_decimals}, "
                f"{self.order_size_precision}, {self.order_size_decimals})")


cdef class QueuedOrder:
    cdef:
        double create_timestamp
        str order_id
        bint is_buy
        str symbol
        double amount

    def __init__(self, create_timestamp: float, order_id: str, is_buy: bool, symbol: str, amount: float):
        self.create_timestamp = create_timestamp
        self.order_id = order_id
        self.is_buy = is_buy
        self.symbol = symbol
        self.amount = amount

    @property
    def timestamp(self) -> double:
        return self.create_timestamp

    @property
    def order_id(self) -> str:
        return self.order_id

    @property
    def is_buy(self) -> bint:
        return self.is_buy

    @property
    def symbol(self) -> str:
        return self.symbol

    @property
    def amount(self) -> double:
        return self.amount

    def __repr__(self) -> str:
        return (f"QueuedOrder({self.create_timestamp}, '{self.order_id}', {self.is_buy}, '{self.symbol}', "
                f"{self.amount})")


cdef class PaperTradeMarket(MarketBase):
    TRADE_EXECUTION_DELAY = 5.0
    API_CALL_TIMEOUT = 10.0
    ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled.value
    SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted.value
    BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted.value
    MARKET_ORDER_CANCELLED_EVENT_TAG = MarketEvent.OrderCancelled.value

    @classmethod
    def random_buy_order_id(cls, symbol: str) -> str:
        vals = [random.choice(range(0, 256)) for i in range(0, 32)]
        return "buy://" + symbol + "/" + "".join([f"{val:02x}" for val in vals])

    @classmethod
    def random_sell_order_id(cls, symbol: str) -> str:
        vals = [random.choice(range(0, 256)) for i in range(0, 32)]
        return "sell://" + symbol + "/" + "".join([f"{val:02x}" for val in vals])

    @classmethod
    def logger(cls) -> logging.Logger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self, order_book_tracker: OrderBookTracker, config: MarketConfig):
        super(MarketBase, self).__init__()

        self._symbol_pairs = {}
        self._account_balance = {}
        self._order_book_tracker = order_book_tracker
        self._config = config
        self._queued_orders = deque()
        self._quantization_params = {}
        self._order_tracker_task = None
        self._network_status = NetworkStatus.STOPPED

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def ready(self):
        return len(self._order_book_tracker.order_books) > 0

    @property
    def queued_orders(self) -> List[QueuedOrder]:
        return self._queued_orders

    @property
    def limit_orders(self) -> List[LimitOrder]:
        cdef:
            LimitOrdersIterator map_it
            SingleSymbolLimitOrders *single_symbol_collection_ptr
            SingleSymbolLimitOrdersIterator collection_it
            SingleSymbolLimitOrdersRIterator collection_rit
            const CPPLimitOrder *cpp_limit_order_ptr
            list retval = []

        map_it = self._bid_limit_orders.begin()
        while map_it != self._bid_limit_orders.end():
            single_symbol_collection_ptr = address(deref(map_it).second)
            collection_rit = single_symbol_collection_ptr.rbegin()
            while collection_rit != single_symbol_collection_ptr.rend():
                cpp_limit_order_ptr = address(deref(collection_rit))
                retval.append(c_create_limit_order_from_cpp_limit_order(deref(cpp_limit_order_ptr)))
                inc(collection_rit)
            inc(map_it)

        map_it = self._ask_limit_orders.begin()
        while map_it != self._ask_limit_orders.end():
            single_symbol_collection_ptr = address(deref(map_it).second)
            collection_it = single_symbol_collection_ptr.begin()
            while collection_it != single_symbol_collection_ptr.end():
                cpp_limit_order_ptr = address(deref(collection_it))
                retval.append(c_create_limit_order_from_cpp_limit_order(deref(cpp_limit_order_ptr)))
                inc(collection_it)
            inc(map_it)

        return retval

    cdef c_start(self, Clock clock, double timestamp):
        MarketBase.c_start(self, clock, timestamp)
        self._network_status = NetworkStatus.CONNECTED
        self._order_tracker_task = asyncio.ensure_future(self._order_book_tracker.start())

    async def start_network(self):
        if self._order_tracker_task is not None:
            self._stop_network()

    def _stop_network(self):
        if self._order_tracker_task is not None:
            self._order_tracker_task.cancel()

    async def check_network(self) -> NetworkStatus:
        return self._network_status

    async def _check_network_loop(self):
        # Override the check network loop to exit immediately.
        self._network_status = await self.check_network()

    def add_symbol_pair(self, *symbol_pairs):
        for symbol_pair in symbol_pairs:
            self._symbol_pairs[symbol_pair.symbol]= symbol_pair

    def set_balance(self, currency: str, balance: double):
        self.c_set_balance(currency, balance)

    cdef c_set_balance(self, str currency, double balance):
        self._account_balance[currency] = balance

    def get_balance(self, currency: str):
        return self.c_get_balance(currency)

    cdef double c_get_balance(self, str currency) except? -1:
        return self._account_balance[currency]

    cdef c_tick(self, double timestamp):
        MarketBase.c_tick(self, timestamp)
        self.c_process_market_orders()
        # self.c_process_limit_order_expiration()
        # self.c_process_crossed_limit_orders()

    cdef str c_buy(self, str symbol, double amount, object order_type = OrderType.MARKET, double price = 0.0,
                   dict kwargs = {}):
        if symbol not in self._symbol_pairs:
            raise ValueError(f"Trading symbol '{symbol}' does not existing in current data set.")

        cdef:
            str order_id = self.random_buy_order_id(symbol)
            string cpp_order_id = order_id.encode("utf8")
            string cpp_symbol = symbol.encode("utf8")
            string cpp_base_currency = self._symbol_pairs[symbol].base_currency.encode("utf8")
            string cpp_quote_currency = self._symbol_pairs[symbol].quote_currency.encode("utf8")
            LimitOrdersIterator map_it
            SingleSymbolLimitOrders *limit_orders_collection_ptr = NULL
            pair[LimitOrders.iterator, cppbool] insert_result
            double time_now = self._current_timestamp
            double order_expiration_ts = kwargs.get("expiration_ts", 0)

        if order_type is OrderType.MARKET:
            self._queued_orders.append(QueuedOrder(self._current_timestamp, order_id, True, symbol, amount))
        elif order_type is OrderType.LIMIT:
            quantized_price = self.c_quantize_order_price(symbol, price)
            quantized_amount = self.c_quantize_order_amount(symbol, amount)
            map_it = self._bid_limit_orders.find(cpp_symbol)

            if map_it == self._bid_limit_orders.end():
                insert_result = self._bid_limit_orders.insert(LimitOrdersPair(cpp_symbol, SingleSymbolLimitOrders()))
                map_it = insert_result.first
            limit_orders_collection_ptr = address(deref(map_it).second)
            limit_orders_collection_ptr.insert(CPPLimitOrder(
                cpp_order_id,
                cpp_symbol,
                True,
                cpp_base_currency,
                cpp_quote_currency,
                <PyObject *> quantized_price,
                <PyObject *> quantized_amount
            ))

    cdef str c_sell(self, str symbol, double amount, object order_type = OrderType.MARKET, double price = 0.0,
                    dict kwargs = {}):
        if symbol not in self._symbol_pairs:
                raise ValueError(f"Trading symbol '{symbol}' does not existing in current data set.")
        cdef:
            str order_id = self.random_buy_order_id(symbol)
            string cpp_order_id = order_id.encode("utf8")
            string cpp_symbol = symbol.encode("utf8")
            string cpp_base_currency = self._symbol_pairs[symbol].base_currency.encode("utf8")
            string cpp_quote_currency = self._symbol_pairs[symbol].quote_currency.encode("utf8")
            LimitOrdersIterator map_it
            SingleSymbolLimitOrders *limit_orders_collection_ptr = NULL
            pair[LimitOrders.iterator, cppbool] insert_result
            double time_now = self._current_timestamp
            double order_expiration_ts = kwargs.get("expiration_ts", 0)
        if order_type is OrderType.MARKET:
            self._queued_orders.append(QueuedOrder(self._current_timestamp, order_id, False, symbol, amount))
        elif order_type is OrderType.LIMIT:
            quantized_price = self.c_quantize_order_price(symbol, price)
            quantized_amount = self.c_quantize_order_amount(symbol, amount)
            map_it = self._ask_limit_orders.find(cpp_symbol)

            if map_it == self._ask_limit_orders.end():
                insert_result = self._ask_limit_orders.insert(LimitOrdersPair(cpp_symbol, SingleSymbolLimitOrders()))
                map_it = insert_result.first
            limit_orders_collection_ptr = address(deref(map_it).second)
            limit_orders_collection_ptr.insert(CPPLimitOrder(
                cpp_order_id,
                cpp_symbol,
                False,
                cpp_base_currency,
                cpp_quote_currency,
                <PyObject *> quantized_price,
                <PyObject *> quantized_amount
            ))

    cdef c_execute_buy(self, str order_id, str symbol, double amount):
        cdef:
            double quote_currency_amount
            double base_currency_amount

        config = self._config
        quote_currency = self._symbol_pairs[symbol].quote_currency
        quote_currency_amount = self.c_get_balance(quote_currency)
        base_currency = self._symbol_pairs[symbol].base_currency
        base_currency_amount = self.c_get_balance(base_currency)

        order_book = self.order_books[symbol]
        buy_entries = order_book.simulate_buy(amount)
        # Calculate the quote currency needed, including fees.
        total_needed = sum(row.price * row.amount for row in buy_entries)
        sold_amount = total_needed
        fee_amount = total_needed * config.buy_fees_amount
        if config.buy_fees_asset is AssetType.QUOTE_CURRENCY:
            total_needed += fee_amount
        if total_needed > quote_currency_amount:
            raise ValueError(f"Insufficient {quote_currency} balance available for buy order. "
                             f"{quote_currency_amount} {quote_currency} available vs. "
                             f"{total_needed} {quote_currency} required for the order.")

        # Calculate the base currency acquired, including fees.
        acquired_amount = sum(row.amount for row in buy_entries)
        bought_amount = acquired_amount
        if config.buy_fees_asset is AssetType.BASE_CURRENCY:
            fee_amount = acquired_amount * config.buy_fees_amount
            acquired_amount -= fee_amount

        self.c_set_balance(quote_currency, quote_currency_amount - total_needed)
        self.c_set_balance(base_currency, base_currency_amount + acquired_amount)

        order_filled_events = OrderFilledEvent.order_filled_events_from_order_book_rows(
            self._current_timestamp, order_id, symbol, TradeType.BUY, OrderType.MARKET, TradeFee(0.0), buy_entries
        )

        for order_filled_event in order_filled_events:
            self.c_trigger_event(self.ORDER_FILLED_EVENT_TAG, order_filled_event)
        self.c_trigger_event(self.BUY_ORDER_COMPLETED_EVENT_TAG,
                             BuyOrderCompletedEvent(self._current_timestamp,
                                                    order_id,
                                                    base_currency,
                                                    quote_currency,
                                                    base_currency if \
                                                        config.buy_fees_asset is AssetType.BASE_CURRENCY else \
                                                        quote_currency,
                                                    bought_amount,
                                                    sold_amount,
                                                    fee_amount,
                                                    OrderType.MARKET))

    cdef c_execute_sell(self, str order_id, str symbol, double amount):
        cdef:
            double quote_currency_amount
            double base_currency_amount

        config = self._config
        quote_currency = self._symbol_pairs[symbol].quote_currency
        quote_currency_amount = self.c_get_balance(quote_currency)
        base_currency = self._symbol_pairs[symbol].base_currency
        base_currency_amount = self.c_get_balance(base_currency)

        if amount > base_currency_amount:
            raise ValueError(f"Insufficient {base_currency} balance available for sell order. "
                             f"{base_currency_amount} {base_currency} available vs. "
                             f"{amount} {base_currency} required for the order.")

        order_book = self.order_books[symbol]

        # Calculate the base currency used, including fees.
        sold_amount = amount
        fee_amount = amount * config.sell_fees_amount
        if config.sell_fees_asset is AssetType.BASE_CURRENCY:
            sold_amount -= fee_amount
        sell_entries = order_book.simulate_sell(sold_amount)

        # Calculate the quote currency acquired, including fees.
        acquired_amount = sum(row.price * row.amount for row in sell_entries)
        bought_amount = acquired_amount
        if config.sell_fees_asset is AssetType.QUOTE_CURRENCY:
            fee_amount = acquired_amount * config.sell_fees_amount
            acquired_amount -= fee_amount

        self.c_set_balance(quote_currency,
                           quote_currency_amount + acquired_amount)
        self.c_set_balance(base_currency,
                           base_currency_amount - amount)

        order_filled_events = OrderFilledEvent.order_filled_events_from_order_book_rows(
            self._current_timestamp, order_id, symbol, TradeType.SELL, OrderType.MARKET, TradeFee(0.0), sell_entries
        )

        for order_filled_event in order_filled_events:
            self.c_trigger_event(self.ORDER_FILLED_EVENT_TAG, order_filled_event)

        self.c_trigger_event(self.SELL_ORDER_COMPLETED_EVENT_TAG,
                             SellOrderCompletedEvent(self._current_timestamp,
                                                     order_id,
                                                     base_currency,
                                                     quote_currency,
                                                     base_currency if \
                                                        config.sell_fees_asset is AssetType.BASE_CURRENCY else \
                                                        quote_currency,
                                                     sold_amount,
                                                     bought_amount,
                                                     fee_amount,
                                                     OrderType.MARKET))

    cdef c_process_market_orders(self):
        cdef:
            QueuedOrder front_order = None
        while len(self._queued_orders) > 0:
            front_order = self._queued_orders[0]
            if front_order.create_timestamp <= self._current_timestamp - self.TRADE_EXECUTION_DELAY:
                self._queued_orders.popleft()
                try:
                    if front_order.is_buy:
                        self.c_execute_buy(front_order.order_id, front_order.symbol, front_order.amount)
                    else:
                        self.c_execute_sell(front_order.order_id, front_order.symbol, front_order.amount)
                except Exception:
                    self.logger().error("Error executing queued order.", exc_info=True)
            else:
                return

    # cdef bint c_delete_expired_limit_orders(self, LimitOrders *orders_map, str symbol, str client_order_id):
    #     cdef:
    #         string cpp_symbol = symbol.encode("utf8")
    #         string cpp_client_order_id = client_order_id.encode("utf8")
    #         LimitOrdersIterator map_it = orders_map.find(cpp_symbol)
    #         SingleSymbolLimitOrders *limit_orders_collection_ptr = NULL
    #         SingleSymbolLimitOrdersIterator orders_it
    #         const CPPLimitOrder *limit_order_ptr = NULL
    #
    #     if map_it == orders_map.end():
    #         return False
    #
    #     limit_orders_collection_ptr = address(deref(map_it).second)
    #
    #     orders_it = limit_orders_collection_ptr.begin()
    #     while orders_it != limit_orders_collection_ptr.end():
    #         limit_order_ptr = address(deref(orders_it))
    #         if limit_order_ptr.getClientOrderID() == cpp_client_order_id:
    #             self.c_delete_limit_order(orders_map, address(map_it), orders_it)
    #             self.c_trigger_event(self.ORDER_EXPIRED_EVENT_TAG,
    #                                  OrderExpiredEvent(self.current_timestamp, client_order_id))
    #             return True
    #         inc(orders_it)
    #     return False
    #
    # cdef c_process_limit_order_expiration(self):
    #     cdef:
    #         LimitOrderExpirationSetIterator order_expiration_it
    #         const CPPOrderExpirationEntry *order_expiration_entry_ptr = NULL
    #         double time_now = self.current_timestamp
    #         double expiration_time
    #         str symbol
    #         str client_order_id
    #
    #     order_expiration_it = self._limit_order_expiration_set.begin()
    #     while order_expiration_it != self._limit_order_expiration_set.end():
    #         order_expiration_entry_ptr = address(deref(order_expiration_it))
    #         expiration_time = order_expiration_entry_ptr.getExpirationTimestamp()
    #         if expiration_time <= time_now:
    #             symbol = order_expiration_entry_ptr.getSymbol().decode("utf8")
    #             client_order_id = order_expiration_entry_ptr.getClientOrderID().decode("utf8")
    #             if not self.c_delete_expired_limit_orders(address(self._bid_limit_orders), symbol, client_order_id):
    #                 self.c_delete_expired_limit_orders(address(self._ask_limit_orders), symbol, client_order_id)
    #             self._limit_order_expiration_set.erase(inc(order_expiration_it))
    #         else:
    #             break
    #
    # cdef c_delete_limit_order(self,
    #                           LimitOrders *limit_orders_map_ptr,
    #                           LimitOrdersIterator *map_it_ptr,
    #                           const SingleSymbolLimitOrdersIterator orders_it):
    #     cdef:
    #         SingleSymbolLimitOrders *orders_collection_ptr = address(deref(deref(map_it_ptr)).second)
    #     orders_collection_ptr.erase(orders_it)
    #     if orders_collection_ptr.empty():
    #         map_it_ptr[0] = limit_orders_map_ptr.erase(deref(map_it_ptr))
    #
    # cdef c_process_limit_bid_order(self,
    #                                LimitOrders *limit_orders_map_ptr,
    #                                LimitOrdersIterator *map_it_ptr,
    #                                SingleSymbolLimitOrdersIterator orders_it):
    #     cdef:
    #         const CPPLimitOrder *cpp_limit_order_ptr = address(deref(orders_it))
    #         str symbol = cpp_limit_order_ptr.getSymbol().decode("utf8")
    #         str quote_currency = cpp_limit_order_ptr.getQuoteCurrency().decode("utf8")
    #         str base_currency = cpp_limit_order_ptr.getBaseCurrency().decode("utf8")
    #         str order_id = cpp_limit_order_ptr.getClientOrderID().decode("utf8")
    #         double quote_currency_balance = self.c_get_balance(quote_currency)
    #         double quote_currency_traded = (float(<object> cpp_limit_order_ptr.getPrice()) *
    #                                         float(<object> cpp_limit_order_ptr.getQuantity()))
    #         double base_currency_traded = float(<object> cpp_limit_order_ptr.getQuantity())
    #
    #     # Check if there's enough balance to satisfy the order. If not, remove the limit order without doing anything.
    #     if quote_currency_balance < quote_currency_traded:
    #         self.logger().warning(f"Not enough {quote_currency} balance to fill limit buy order on {symbol}. "
    #                               f"{quote_currency_traded:.8g} {quote_currency} needed vs. "
    #                               f"{quote_currency_balance:.8g} {quote_currency} available.")
    #         self.c_delete_limit_order(limit_orders_map_ptr, map_it_ptr, orders_it)
    #         return
    #
    #     # Adjust the market balances according to the trade done.
    #     self.c_set_balance(quote_currency, self.c_get_balance(quote_currency) - quote_currency_traded)
    #     self.c_set_balance(base_currency, self.c_get_balance(base_currency) + base_currency_traded)
    #
    #     # Emit the trade and order completed events.
    #     config = self._config
    #     self.c_trigger_event(self.ORDER_FILLED_EVENT_TAG,
    #                          OrderFilledEvent(self._current_timestamp,
    #                                           order_id,
    #                                           symbol,
    #                                           TradeType.BUY,
    #                                           OrderType.LIMIT,
    #                                           float(<object> cpp_limit_order_ptr.getPrice()),
    #                                           float(<object> cpp_limit_order_ptr.getQuantity()),
    #                                           TradeFee(0.0)
    #                                           ))
    #     self.c_trigger_event(self.BUY_ORDER_COMPLETED_EVENT_TAG,
    #                          BuyOrderCompletedEvent(self._current_timestamp,
    #                                                 order_id,
    #                                                 base_currency,
    #                                                 quote_currency,
    #                                                 base_currency if \
    #                                                     config.buy_fees_asset is AssetType.BASE_CURRENCY else \
    #                                                     quote_currency,
    #                                                 base_currency_traded,
    #                                                 quote_currency_traded,
    #                                                 0.0,
    #                                                 OrderType.LIMIT))
    #     self.c_delete_limit_order(limit_orders_map_ptr, map_it_ptr, orders_it)
    #
    # cdef c_process_limit_ask_order(self,
    #                                LimitOrders *limit_orders_map_ptr,
    #                                LimitOrdersIterator *map_it_ptr,
    #                                SingleSymbolLimitOrdersIterator orders_it):
    #     cdef:
    #         const CPPLimitOrder *cpp_limit_order_ptr = address(deref(orders_it))
    #         str symbol = cpp_limit_order_ptr.getSymbol().decode("utf8")
    #         str quote_currency = cpp_limit_order_ptr.getQuoteCurrency().decode("utf8")
    #         str base_currency = cpp_limit_order_ptr.getBaseCurrency().decode("utf8")
    #         str order_id = cpp_limit_order_ptr.getClientOrderID().decode("utf8")
    #         double base_currency_balance = self.c_get_balance(base_currency)
    #         double quote_currency_traded = (float(<object> cpp_limit_order_ptr.getPrice()) *
    #                                         float(<object> cpp_limit_order_ptr.getQuantity()))
    #         double base_currency_traded = float(<object> cpp_limit_order_ptr.getQuantity())
    #
    #     # Check if there's enough balance to satisfy the order. If not, remove the limit order without doing anything.
    #     if base_currency_balance < base_currency_traded:
    #         self.logger().warning(f"Not enough {base_currency} balance to fill limit sell order on {symbol}. "
    #                               f"{base_currency_traded:.8g} {base_currency} needed vs. "
    #                               f"{base_currency_balance:.8g} {base_currency} available.")
    #         self.c_delete_limit_order(limit_orders_map_ptr, map_it_ptr, orders_it)
    #         return
    #
    #     # Adjust the market balances according to the trade done.
    #     self.c_set_balance(quote_currency, self.c_get_balance(quote_currency) + quote_currency_traded)
    #     self.c_set_balance(base_currency, self.c_get_balance(base_currency) - base_currency_traded)
    #
    #     # Emit the trade and order completed events.
    #     config = self._config
    #     self.c_trigger_event(self.ORDER_FILLED_EVENT_TAG,
    #                          OrderFilledEvent(self._current_timestamp,
    #                                           order_id,
    #                                           symbol,
    #                                           TradeType.SELL,
    #                                           OrderType.LIMIT,
    #                                           float(<object> cpp_limit_order_ptr.getPrice()),
    #                                           float(<object> cpp_limit_order_ptr.getQuantity()),
    #                                           TradeFee(0.0)
    #                                           ))
    #     self.c_trigger_event(self.SELL_ORDER_COMPLETED_EVENT_TAG,
    #                          SellOrderCompletedEvent(self._current_timestamp,
    #                                                  order_id,
    #                                                  base_currency,
    #                                                  quote_currency,
    #                                                  base_currency if \
    #                                                      config.sell_fees_asset is AssetType.BASE_CURRENCY else \
    #                                                      quote_currency,
    #                                                  base_currency_traded,
    #                                                  quote_currency_traded,
    #                                                  0.0,
    #                                                  OrderType.LIMIT))
    #     self.c_delete_limit_order(limit_orders_map_ptr, map_it_ptr, orders_it)
    #
    # cdef c_process_limit_order(self,
    #                            bint is_buy,
    #                            LimitOrders *limit_orders_map_ptr,
    #                            LimitOrdersIterator *map_it_ptr,
    #                            SingleSymbolLimitOrdersIterator orders_it):
    #     if is_buy:
    #         self.c_process_limit_bid_order(limit_orders_map_ptr, map_it_ptr, orders_it)
    #     else:
    #         self.c_process_limit_ask_order(limit_orders_map_ptr, map_it_ptr, orders_it)
    #
    # cdef c_process_crossed_limit_orders_for_symbol(self,
    #                                                bint is_buy,
    #                                                LimitOrders *limit_orders_map_ptr,
    #                                                LimitOrdersIterator *map_it_ptr):
    #     """
    #     Trigger limit orders when the opposite side of the order book has crossed the limit order's price.
    #     This implies someone was ready to fill the limit order, if that limit order was on the market.
    #
    #     :param is_buy: are the limit orders on the bid side?
    #     :param limit_orders_map_ptr: pointer to the limit orders map
    #     :param map_it_ptr: limit orders map iterator, which implies the symbol being processed
    #     """
    #
    #     cdef:
    #         str symbol = deref(deref(map_it_ptr)).first.decode("utf8")
    #         double opposite_order_book_price = self.c_get_price(symbol, is_buy)
    #         SingleSymbolLimitOrders *orders_collection_ptr = address(deref(deref(map_it_ptr)).second)
    #         SingleSymbolLimitOrdersIterator orders_it = orders_collection_ptr.begin()
    #         SingleSymbolLimitOrdersRIterator orders_rit = orders_collection_ptr.rbegin()
    #         vector[SingleSymbolLimitOrdersIterator] process_order_its
    #         const CPPLimitOrder *cpp_limit_order_ptr = NULL
    #
    #     if is_buy:
    #         while orders_rit != orders_collection_ptr.rend():
    #             cpp_limit_order_ptr = address(deref(orders_rit))
    #             if opposite_order_book_price > float(<object>cpp_limit_order_ptr.getPrice()):
    #                 break
    #             process_order_its.push_back(getIteratorFromReverseIterator(
    #                 <reverse_iterator[SingleSymbolLimitOrdersIterator]>orders_rit))
    #             inc(orders_rit)
    #     else:
    #         while orders_it != orders_collection_ptr.end():
    #             cpp_limit_order_ptr = address(deref(orders_it))
    #             if opposite_order_book_price < float(<object>cpp_limit_order_ptr.getPrice()):
    #                 break
    #             process_order_its.push_back(orders_it)
    #             inc(orders_it)
    #
    #     for orders_it in process_order_its:
    #         self.c_process_limit_order(is_buy, limit_orders_map_ptr, map_it_ptr, orders_it)
    #
    # cdef c_process_crossed_limit_orders(self):
    #     cdef:
    #         LimitOrders *limit_orders_ptr = address(self._bid_limit_orders)
    #         LimitOrdersIterator map_it = limit_orders_ptr.begin()
    #
    #     while map_it != limit_orders_ptr.end():
    #         self.c_process_crossed_limit_orders_for_symbol(True, limit_orders_ptr, address(map_it))
    #         if map_it != limit_orders_ptr.end():
    #             inc(map_it)
    #
    #     limit_orders_ptr = address(self._ask_limit_orders)
    #     map_it = limit_orders_ptr.begin()
    #
    #     while map_it != limit_orders_ptr.end():
    #         self.c_process_crossed_limit_orders_for_symbol(False, limit_orders_ptr, address(map_it))
    #         if map_it != limit_orders_ptr.end():
    #             inc(map_it)
    #
    # cdef c_match_trade_to_limit_orders(self, object order_book_trade_event):
    #     """
    #     Trigger limit orders when incoming market orders have crossed the limit order's price.
    #
    #     :param order_book_trade_event: trade event from order book
    #     """
    #     cdef:
    #         string cpp_symbol = order_book_trade_event.symbol.encode("utf8")
    #         bint is_maker_buy = order_book_trade_event.type is TradeType.SELL
    #         double trade_price = order_book_trade_event.price
    #         double trade_quantity = order_book_trade_event.amount
    #         LimitOrders *limit_orders_map_ptr = (address(self._bid_limit_orders)
    #                                              if is_maker_buy
    #                                              else address(self._ask_limit_orders))
    #         LimitOrdersIterator map_it = limit_orders_map_ptr.find(cpp_symbol)
    #         SingleSymbolLimitOrders *orders_collection_ptr = NULL
    #         SingleSymbolLimitOrdersIterator orders_it
    #         SingleSymbolLimitOrdersRIterator orders_rit
    #         vector[SingleSymbolLimitOrdersIterator] process_order_its
    #         const CPPLimitOrder *cpp_limit_order_ptr = NULL
    #
    #     if map_it == limit_orders_map_ptr.end():
    #         return
    #
    #     orders_collection_ptr = address(deref(map_it).second)
    #
    #     if is_maker_buy:
    #         orders_rit = orders_collection_ptr.rbegin()
    #         while orders_rit != orders_collection_ptr.rend():
    #             cpp_limit_order_ptr = address(deref(orders_rit))
    #             if float(<object>cpp_limit_order_ptr.getPrice()) <= trade_price:
    #                 break
    #             process_order_its.push_back(getIteratorFromReverseIterator(
    #                 <reverse_iterator[SingleSymbolLimitOrdersIterator]>orders_rit))
    #             inc(orders_rit)
    #     else:
    #         orders_it = orders_collection_ptr.begin()
    #         while orders_it != orders_collection_ptr.end():
    #             cpp_limit_order_ptr = address(deref(orders_it))
    #             if float(<object>cpp_limit_order_ptr.getPrice()) >= trade_price:
    #                 break
    #             process_order_its.push_back(orders_it)
    #             inc(orders_it)
    #
    #     for orders_it in process_order_its:
    #         self.c_process_limit_order(is_maker_buy, limit_orders_map_ptr, address(map_it), orders_it)

    cdef double c_get_available_balance(self, str currency) except? -1:
        pass

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        pass

    def get_all_balances(self) -> Dict[str, float]:
        return self._account_balance

    async def get_deposit_info(self, asset: str) -> DepositInfo:
        pass

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        pass

    cdef c_cancel(self, str symbol, str client_order_id):
        pass

    cdef object c_get_fee(self, str base_currency, str quote_currency, object order_type, object order_side,
                          double amount, double price):
        pass

    cdef str c_withdraw(self, str address, str currency, double amount):
        pass

    cdef OrderBook c_get_order_book(self, str symbol):
        if symbol not in self._symbol_pairs:
            raise ValueError(f"No order book exists for '{symbol}'.")
        return self._order_book_tracker[symbol]

    cdef double c_get_price(self, str symbol, bint is_buy) except? -1:
        cdef:
            OrderBook order_book
        order_book = self.c_get_order_book(symbol)
        return order_book.c_get_price(is_buy)

    cdef object c_get_order_price_quantum(self, str symbol, double price):
        cdef:
            QuantizationParams q_params
        if symbol in self._quantization_params:
            q_params = self._quantization_params[symbol]
            decimals_quantum = Decimal(f"1e-{q_params.price_decimals}")
            if price > 0:
                precision_quantum = Decimal(f"1e{math.ceil(math.log10(price)) - q_params.price_precision}")
            else:
                precision_quantum = Decimal(0)
            return max(precision_quantum, decimals_quantum)
        else:
            return Decimal(f"1e-15")

    cdef object c_get_order_size_quantum(self, str symbol, double order_size):
        cdef:
            QuantizationParams q_params
        if symbol in self._quantization_params:
            q_params = self._quantization_params[symbol]
            decimals_quantum = Decimal(f"1e-{q_params.order_size_decimals}")
            if order_size > 0:
                precision_quantum = Decimal(f"1e{math.ceil(math.log10(order_size)) - q_params.order_size_precision}")
            else:
                precision_quantum = Decimal(0)
            return max(precision_quantum, decimals_quantum)
        else:
            return Decimal(f"1e-15")


"""
@property
    
    # Default implementation
    def status_dict(self) -> Dict[str, bool]:
        return {}

    # Default implementation
    @property
    def name(self) -> str:
        return self.__class__.__name__

    # Default implementation
    @property
    def event_logs(self) -> List[any]:
        return self.event_logger.event_log

    # Implemented
    @property
    def order_books(self) -> Dict[str, OrderBook]:
        raise NotImplementedError

    # Implemented
    @property
    def ready(self) -> bool:
        raise NotImplementedError

    # Implemented
    @property
    def limit_orders(self) -> List[LimitOrder]:
        raise NotImplementedError

    # Default implementation
    @property
    def tracking_states(self) -> Dict[str, any]:
        return {}

    # Default implementation
    def restore_tracking_states(self, saved_states: Dict[str, any]):
        '''        
        Restores the tracking states from a previously saved state.
        
        :param saved_states: Previously saved tracking states from `tracking_states` property.
        '''
        pass

    # Not implemented above
    async def get_active_exchange_markets(self) -> pd.DataFrame:
        '''
        :return: data frame with symbol as index, and at least the following columns --
                 ["baseAsset", "quoteAsset", "volume", "USDVolume"]
        '''
        raise NotImplementedError

    # Default implementation
    def get_balance(self, currency: str) -> float:
        return self.c_get_balance(currency)

    # Default implementation
    def get_available_balance(self, currency: str) -> float:
        return self.c_get_available_balance(currency)

    # Temporarily implemented
    def get_all_balances(self) -> Dict[str, float]:
        raise NotImplementedError

    # Default implementation
    def get_price(self, symbol: str, is_buy: bool) -> float:
        return self.c_get_price(symbol, is_buy)

    # Default implementation
    def withdraw(self, address: str, currency: str, amount: float) -> str:
        return self.c_withdraw(address, currency, amount)

    # Not implemented above
    async def get_deposit_info(self, asset: str) -> DepositInfo:
        raise NotImplementedError

    # Default implementation
    def get_order_book(self, symbol: str) -> OrderBook:
        return self.c_get_order_book(symbol)

    # Default implementation
    def buy(self, symbol: str, amount: float, order_type = OrderType.MARKET, price: float = 0.0, **kwargs) -> str:
        return self.c_buy(symbol, amount, order_type, price, kwargs)

    # Default implementation
    def sell(self, symbol: str, amount: float, order_type = OrderType.MARKET, price: float = 0.0, **kwargs) -> str:
        return self.c_sell(symbol, amount, order_type, price, kwargs)

    # Default implementation
    def cancel(self, symbol: str, client_order_id: str):
        return self.c_cancel(symbol, client_order_id)

    # Temporary implementation
    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        raise NotImplementedError

    # Default implementation
    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: float,
                price: float = NaN) -> TradeFee:
        return self.c_get_fee(base_currency, quote_currency, order_type, order_side, amount, price)

    # Default implementation
    def get_order_price_quantum(self, symbol: str, price: float) -> Decimal:
        return self.c_get_order_price_quantum(symbol, price)

    # Default implementation
    def get_order_size_quantum(self, symbol: str, order_size: float) -> Decimal:
        return self.c_get_order_size_quantum(symbol, order_size)

    # Default implementation
    def quantize_order_price(self, symbol: str, price: float) -> Decimal:
        return self.c_quantize_order_price(symbol, price)

    # Default implementation
    def quantize_order_amount(self, symbol: str, amount: float) -> Decimal:
        return self.c_quantize_order_amount(symbol, amount)

    # Temporary implementation
    cdef str c_buy(self, str symbol, double amount, object order_type = OrderType.MARKET, double price = 0.0, dict kwargs = {}):
        raise NotImplementedError

    # Temporary implementation
    cdef str c_sell(self, str symbol, double amount, object order_type = OrderType.MARKET, double price = 0.0, dict kwargs = {}):
        raise NotImplementedError

    # Temporary implementation
    cdef c_cancel(self, str symbol, str client_order_id):
        raise NotImplementedError

    # Temporary implementation
    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          double amount,
                          double price):
        raise NotImplementedError

    # Temporary implementation
    cdef double c_get_balance(self, str currency) except? -1:
        raise NotImplementedError

    # Temporary implementation
    cdef double c_get_available_balance(self, str currency) except? -1:
        raise NotImplementedError

    # Temporary implementation
    cdef str c_withdraw(self, str address, str currency, double amount):
        raise NotImplementedError

    # Temporary implementation
    cdef OrderBook c_get_order_book(self, str symbol):
        raise NotImplementedError

    # Temporary implementation
    cdef double c_get_price(self, str symbol, bint is_buy) except? -1:
        raise NotImplementedError

    # Temporary implementation
    cdef object c_get_order_price_quantum(self, str symbol, double price):
        raise NotImplementedError

    # Temporary implementation
    cdef object c_get_order_size_quantum(self, str symbol, double order_size):
        raise NotImplementedError

    # Default implementation
    cdef object c_quantize_order_price(self, str symbol, double price):
        price_quantum = self.c_get_order_price_quantum(symbol, price)
        return round(Decimal(price) / price_quantum) * price_quantum

    # Default implementation
    cdef object c_quantize_order_amount(self, str symbol, double amount, double price = 0.0):
        order_size_quantum = self.c_get_order_size_quantum(symbol, amount)
        return (Decimal(amount) // order_size_quantum) * order_size_quantum
"""
