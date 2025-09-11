# distutils: sources=['hummingbot/core/cpp/Utils.cpp', 'hummingbot/core/cpp/LimitOrder.cpp', 'hummingbot/core/cpp/OrderExpirationEntry.cpp']

import asyncio
import math
import random
from collections import defaultdict, deque
from decimal import Decimal, ROUND_DOWN
from typing import Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

from cpython cimport PyObject
from cython.operator cimport address, dereference as deref, postincrement as inc
from libcpp cimport bool as cppbool
from libcpp.vector cimport vector

from hummingbot.connector.budget_checker import BudgetChecker
from hummingbot.connector.connector_metrics_collector import DummyMetricsCollector
from hummingbot.connector.exchange.paper_trade.trading_pair import TradingPair
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.clock cimport Clock
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.composite_order_book import CompositeOrderBook
from hummingbot.core.data_type.composite_order_book cimport CompositeOrderBook
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.limit_order cimport c_create_limit_order_from_cpp_limit_order
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.event_listener cimport EventListener
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderBookEvent,
    OrderBookTradeEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.Utils cimport getIteratorFromReverseIterator, reverse_iterator
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.estimate_fee import build_trade_fee

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

ptm_logger = None
s_decimal_0 = Decimal(0)


cdef class QuantizationParams:
    def __init__(self,
                 str trading_pair,
                 int price_precision,
                 int price_decimals,
                 int order_size_precision,
                 int order_size_decimals):
        self.trading_pair = trading_pair
        self.price_precision = price_precision
        self.price_decimals = price_decimals
        self.order_size_precision = order_size_precision
        self.order_size_decimals = order_size_decimals

    def __repr__(self) -> str:
        return (f"QuantizationParams('{self.trading_pair}', {self.price_precision}, {self.price_decimals}, "
                f"{self.order_size_precision}, {self.order_size_decimals})")


cdef class QueuedOrder:
    cdef:
        double create_timestamp
        str _order_id
        bint _is_buy
        str _trading_pair
        object _amount

    def __init__(self, create_timestamp: float, order_id: str, is_buy: bool, trading_pair: str, amount: Decimal):
        self.create_timestamp = create_timestamp
        self._order_id = order_id
        self._is_buy = is_buy
        self._trading_pair = trading_pair
        self._amount = amount

    @property
    def timestamp(self) -> double:
        return self.create_timestamp

    @property
    def order_id(self) -> str:
        return self._order_id

    @property
    def is_buy(self) -> bint:
        return self._is_buy

    @property
    def trading_pair(self) -> str:
        return self._trading_pair

    @property
    def amount(self) -> Decimal:
        return self._amount

    def __repr__(self) -> str:
        return (f"QueuedOrder({self.create_timestamp}, '{self.order_id}', {self.is_buy}, '{self.trading_pair}', "
                f"{self.amount})")


cdef class OrderBookTradeListener(EventListener):
    cdef:
        ExchangeBase _market

    def __init__(self, market: ExchangeBase):
        super().__init__()
        self._market = market

    cdef c_call(self, object event_object):
        try:
            self._market.match_trade_to_limit_orders(event_object)
        except Exception as e:
            self.logger().error("Error call trade listener.", exc_info=True)

cdef class OrderBookMarketOrderFillListener(EventListener):
    cdef:
        ExchangeBase _market

    def __init__(self, market: ExchangeBase):
        super().__init__()
        self._market = market

    cdef c_call(self, object event_object):

        if event_object.trading_pair not in self._market.order_books or event_object.order_type != OrderType.MARKET:
            return
        order_book = self._market.order_books[event_object.trading_pair]
        order_book.record_filled_order(event_object)


cdef class PaperTradeExchange(ExchangeBase):
    TRADE_EXECUTION_DELAY = 5.0
    ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled.value
    SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted.value
    BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted.value
    MARKET_ORDER_CANCELED_EVENT_TAG = MarketEvent.OrderCancelled.value
    MARKET_ORDER_FAILURE_EVENT_TAG = MarketEvent.OrderFailure.value
    ORDER_BOOK_TRADE_EVENT_TAG = OrderBookEvent.TradeEvent.value
    MARKET_SELL_ORDER_CREATED_EVENT_TAG = MarketEvent.SellOrderCreated.value
    MARKET_BUY_ORDER_CREATED_EVENT_TAG = MarketEvent.BuyOrderCreated.value

    def __init__(
        self,
        order_book_tracker: OrderBookTracker,
        target_market: Callable,
        exchange_name: str,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
    ):
        order_book_tracker.data_source.order_book_create_function = lambda: CompositeOrderBook()
        super().__init__(balance_asset_limit, rate_limits_share_pct)
        self._set_order_book_tracker(order_book_tracker)
        self._budget_checker = BudgetChecker(exchange=self)
        self._exchange_name = exchange_name
        self._account_balances = {}
        self._account_available_balances = {}
        self._paper_trade_market_initialized = False
        self._trading_pairs = {}
        self._queued_orders = deque()
        self._quantization_params = {}
        self._order_book_trade_listener = OrderBookTradeListener(self)
        self._target_market = target_market
        self._market_order_filled_listener = OrderBookMarketOrderFillListener(self)
        self.c_add_listener(self.ORDER_FILLED_EVENT_TAG, self._market_order_filled_listener)

        # Trade volume metrics should never be gather for paper trade connector
        self._trade_volume_metric_collector = DummyMetricsCollector()

    @property
    def budget_checker(self) -> BudgetChecker:
        return self._budget_checker

    @classmethod
    def random_order_id(cls, order_side: str, trading_pair: str) -> str:
        vals = [random.choice(range(0, 256)) for i in range(0, 13)]
        return f"{order_side}://" + trading_pair + "/" + "".join([f"{val:02x}" for val in vals])

    def init_paper_trade_market(self):
        for trading_pair_str, order_book in self.order_book_tracker.order_books.items():
            assert type(order_book) is CompositeOrderBook
            base_asset, quote_asset = self.split_trading_pair(trading_pair_str)
            self._trading_pairs[self._target_market.convert_from_exchange_trading_pair(trading_pair_str)] = TradingPair(trading_pair_str, base_asset, quote_asset)
            (<CompositeOrderBook>order_book).c_add_listener(
                self.ORDER_BOOK_TRADE_EVENT_TAG,
                self._order_book_trade_listener
            )

    def split_trading_pair(self, trading_pair: str) -> Tuple[str, str]:
        return self._target_market.split_trading_pair(trading_pair)

    #  <editor-fold desc="Property">
    @property
    def trading_pair(self) -> Dict[str, TradingPair]:
        return self._trading_pairs

    @property
    def trading_pairs(self) -> List[str]:
        return [trading_pair for trading_pair in self._trading_pairs]

    @property
    def name(self) -> str:
        return self._exchange_name

    @property
    def display_name(self) -> str:
        return f"{self._exchange_name}_PaperTrade"

    @property
    def order_books(self) -> Dict[str, CompositeOrderBook]:
        return self.order_book_tracker.order_books

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "order_books_initialized": self.order_book_tracker and len(self.order_book_tracker.order_books) > 0
        }

    @property
    def ready(self):
        if not self.order_book_tracker.ready:
            return False
        if all(self.status_dict.values()):
            if not self._paper_trade_market_initialized:
                self.init_paper_trade_market()
                self._paper_trade_market_initialized = True
            return True
        else:
            return False

    @property
    def queued_orders(self) -> List[QueuedOrder]:
        return self._queued_orders

    @property
    def limit_orders(self) -> List[LimitOrder]:
        cdef:
            LimitOrdersIterator map_it
            SingleTradingPairLimitOrders *single_trading_pair_collection_ptr
            SingleTradingPairLimitOrdersIterator collection_it
            SingleTradingPairLimitOrdersRIterator collection_rit
            const CPPLimitOrder *cpp_limit_order_ptr
            list retval = []

        map_it = self._bid_limit_orders.begin()
        while map_it != self._bid_limit_orders.end():
            single_trading_pair_collection_ptr = address(deref(map_it).second)
            collection_rit = single_trading_pair_collection_ptr.rbegin()
            while collection_rit != single_trading_pair_collection_ptr.rend():
                cpp_limit_order_ptr = address(deref(collection_rit))
                retval.append(c_create_limit_order_from_cpp_limit_order(deref(cpp_limit_order_ptr)))
                inc(collection_rit)
            inc(map_it)

        map_it = self._ask_limit_orders.begin()
        while map_it != self._ask_limit_orders.end():
            single_trading_pair_collection_ptr = address(deref(map_it).second)
            collection_it = single_trading_pair_collection_ptr.begin()
            while collection_it != single_trading_pair_collection_ptr.end():
                cpp_limit_order_ptr = address(deref(collection_it))
                retval.append(c_create_limit_order_from_cpp_limit_order(deref(cpp_limit_order_ptr)))
                inc(collection_it)
            inc(map_it)

        return retval

    @property
    def on_hold_balances(self) -> Dict[str, Decimal]:
        _on_hold_balances = defaultdict(Decimal)
        for limit_order in self.limit_orders:
            if limit_order.is_buy:
                _on_hold_balances[limit_order.quote_currency] += limit_order.quantity * limit_order.price
            else:
                _on_hold_balances[limit_order.base_currency] += limit_order.quantity
        return _on_hold_balances

    @property
    def available_balances(self) -> Dict[str, Decimal]:
        _available_balances = self._account_balances.copy()
        for trading_pair_str, balance in _available_balances.items():
            _available_balances[trading_pair_str] -= self.on_hold_balances[trading_pair_str]
        return _available_balances

    # </editor-fold>

    cdef c_start(self, Clock clock, double timestamp):
        ExchangeBase.c_start(self, clock, timestamp)

    async def start_network(self):
        await self.stop_network()
        self.order_book_tracker.start()

    async def stop_network(self):
        self.order_book_tracker.stop()

    async def check_network(self) -> NetworkStatus:
        return NetworkStatus.CONNECTED

    cdef c_set_balance(self, str currency, object balance):
        self._account_balances[currency.upper()] = Decimal(balance)

    cdef object c_get_balance(self, str currency):
        if currency.upper() not in self._account_balances:
            self.logger().warning(f"Account balance does not have asset {currency.upper()}.")
            return Decimal(0.0)
        return self._account_balances[currency.upper()]

    cdef c_tick(self, double timestamp):
        ExchangeBase.c_tick(self, timestamp)
        self.c_process_market_orders()
        self.c_process_crossed_limit_orders()

    cdef str c_buy(self,
                   str trading_pair_str,
                   object amount,
                   object order_type=OrderType.MARKET,
                   object price=s_decimal_0,
                   dict kwargs={}):
        if trading_pair_str not in self._trading_pairs:
            raise ValueError(f"Trading pair '{trading_pair_str}' does not existing in current data set.")

        cdef:
            str order_id = self.random_order_id("buy", trading_pair_str)
            str quote_asset = self._trading_pairs[trading_pair_str].quote_asset
            string cpp_order_id = order_id.encode("utf8")
            string cpp_trading_pair_str = trading_pair_str.encode("utf8")
            string cpp_base_asset = self._trading_pairs[trading_pair_str].base_asset.encode("utf8")
            string cpp_quote_asset = quote_asset.encode("utf8")
            string cpp_position = "NIL".encode("utf8")
            LimitOrdersIterator map_it
            SingleTradingPairLimitOrders *limit_orders_collection_ptr = NULL
            pair[LimitOrders.iterator, cppbool] insert_result

        quantized_price = (self.c_quantize_order_price(trading_pair_str, price)
                           if order_type is OrderType.LIMIT
                           else s_decimal_0)
        quantized_amount = self.c_quantize_order_amount(trading_pair_str, amount)
        if order_type is OrderType.MARKET:
            self._queued_orders.append(QueuedOrder(self._current_timestamp, order_id, True, trading_pair_str,
                                                   quantized_amount))
        elif order_type is OrderType.LIMIT:

            map_it = self._bid_limit_orders.find(cpp_trading_pair_str)

            if map_it == self._bid_limit_orders.end():
                insert_result = self._bid_limit_orders.insert(LimitOrdersPair(cpp_trading_pair_str,
                                                                              SingleTradingPairLimitOrders()))
                map_it = insert_result.first
            limit_orders_collection_ptr = address(deref(map_it).second)
            limit_orders_collection_ptr.insert(CPPLimitOrder(
                cpp_order_id,
                cpp_trading_pair_str,
                True,
                cpp_base_asset,
                cpp_quote_asset,
                <PyObject *> quantized_price,
                <PyObject *> quantized_amount,
                <PyObject *> None,
                int(self._current_timestamp * 1e6),
                0,
                cpp_position,
            ))
        safe_ensure_future(self.trigger_event_async(
            self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
            BuyOrderCreatedEvent(self._current_timestamp,
                                 order_type,
                                 trading_pair_str,
                                 quantized_amount,
                                 quantized_price,
                                 order_id,
                                 self._current_timestamp)))
        return order_id

    cdef str c_sell(self,
                    str trading_pair_str,
                    object amount,
                    object order_type=OrderType.MARKET,
                    object price=s_decimal_0,
                    dict kwargs={}):

        if trading_pair_str not in self._trading_pairs:
            raise ValueError(f"Trading pair '{trading_pair_str}' does not existing in current data set.")
        cdef:
            str order_id = self.random_order_id("sell", trading_pair_str)
            str base_asset = self._trading_pairs[trading_pair_str].base_asset
            string cpp_order_id = order_id.encode("utf8")
            string cpp_trading_pair_str = trading_pair_str.encode("utf8")
            string cpp_base_asset = base_asset.encode("utf8")
            string cpp_quote_asset = self._trading_pairs[trading_pair_str].quote_asset.encode("utf8")
            string cpp_position = "NIL".encode("utf8")
            LimitOrdersIterator map_it
            SingleTradingPairLimitOrders *limit_orders_collection_ptr = NULL
            pair[LimitOrders.iterator, cppbool] insert_result

        quantized_price = (self.c_quantize_order_price(trading_pair_str, price)
                           if order_type is OrderType.LIMIT
                           else s_decimal_0)
        quantized_amount = self.c_quantize_order_amount(trading_pair_str, amount)
        if order_type is OrderType.MARKET:
            self._queued_orders.append(QueuedOrder(self._current_timestamp, order_id, False, trading_pair_str,
                                                   quantized_amount))
        elif order_type is OrderType.LIMIT:
            map_it = self._ask_limit_orders.find(cpp_trading_pair_str)

            if map_it == self._ask_limit_orders.end():
                insert_result = self._ask_limit_orders.insert(LimitOrdersPair(cpp_trading_pair_str,
                                                                              SingleTradingPairLimitOrders()))
                map_it = insert_result.first
            limit_orders_collection_ptr = address(deref(map_it).second)
            limit_orders_collection_ptr.insert(CPPLimitOrder(
                cpp_order_id,
                cpp_trading_pair_str,
                False,
                cpp_base_asset,
                cpp_quote_asset,
                <PyObject *> quantized_price,
                <PyObject *> quantized_amount,
                <PyObject *> None,
                int(self._current_timestamp * 1e6),
                0,
                cpp_position,
            ))
        safe_ensure_future(self.trigger_event_async(
            self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
            SellOrderCreatedEvent(self._current_timestamp,
                                  order_type,
                                  trading_pair_str,
                                  quantized_amount,
                                  quantized_price,
                                  order_id,
                                  self._current_timestamp)))
        return order_id

    cdef c_execute_buy(self, str order_id, str trading_pair_str, object amount):
        cdef:
            str quote_asset = self._trading_pairs[trading_pair_str].quote_asset
            str base_asset = self._trading_pairs[trading_pair_str].base_asset
            object quote_balance = self.c_get_balance(quote_asset)
            object base_balance = self.c_get_balance(base_asset)

        order_book = self.order_books[trading_pair_str]

        buy_entries = order_book.simulate_buy(float(amount))

        # Get the weighted average price of the trade
        avg_price = Decimal(0)
        for entry in buy_entries:
            avg_price += Decimal(entry.price) * Decimal(entry.amount)
        avg_price = avg_price / amount

        order_candidate = OrderCandidate(
            trading_pair=trading_pair_str,
            # Market orders are not maker orders
            is_maker=False,
            order_type=OrderType.MARKET,
            order_side=TradeType.BUY,
            amount=amount,
            price=avg_price,
            from_total_balances=True
        )

        adjusted_order_candidate = self._budget_checker.populate_collateral_entries(order_candidate)

        # Quote currency used, including fees.
        paid_amount = adjusted_order_candidate.order_collateral.amount
        # Base currency acquired, including fees.
        acquired_amount = adjusted_order_candidate.potential_returns.amount

        # It's not possible to fulfill the order, the possible acquired amount is less than requested
        if paid_amount > quote_balance:
            self.logger().warning(f"Insufficient {quote_asset} balance available for buy order. "
                                  f"{quote_balance} {quote_asset} available vs. "
                                  f"{paid_amount} {quote_asset} required for the order.")
            self.c_trigger_event(
                self.MARKET_ORDER_FAILURE_EVENT_TAG,
                MarketOrderFailureEvent(self._current_timestamp, order_id, OrderType.MARKET)
            )
            return

        # The order was successfully executed
        self.c_set_balance(quote_asset,
                           quote_balance - paid_amount)
        self.c_set_balance(base_asset,
                           base_balance + acquired_amount)

        # add fee
        fees = build_trade_fee(
            exchange=self.name,
            is_maker=False,
            base_currency="",
            quote_currency="",
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("0"),
            price=Decimal("0"),
        )

        order_filled_events = OrderFilledEvent.order_filled_events_from_order_book_rows(
            self._current_timestamp, order_id, trading_pair_str, TradeType.BUY, OrderType.MARKET,
            fees, buy_entries
        )

        for order_filled_event in order_filled_events:
            self.c_trigger_event(self.ORDER_FILLED_EVENT_TAG, order_filled_event)

        self.c_trigger_event(
            self.BUY_ORDER_COMPLETED_EVENT_TAG,
            BuyOrderCompletedEvent(self._current_timestamp,
                                   order_id,
                                   base_asset,
                                   quote_asset,
                                   acquired_amount,
                                   paid_amount,
                                   OrderType.MARKET))

    cdef c_execute_sell(self, str order_id, str trading_pair_str, object amount):
        cdef:
            str quote_asset = self._trading_pairs[trading_pair_str].quote_asset
            str base_asset = self._trading_pairs[trading_pair_str].base_asset
            object quote_balance = self.c_get_balance(quote_asset)
            object base_balance = self.c_get_balance(base_asset)

        order_book = self.order_books[trading_pair_str]

        sell_entries = order_book.simulate_sell(float(amount))

        # Get the weighted average price of the trade
        avg_price = Decimal(0)
        for entry in sell_entries:
            avg_price += Decimal(entry.price) * Decimal(entry.amount)
        avg_price = avg_price / amount

        order_candidate = OrderCandidate(
            trading_pair=trading_pair_str,
            # Market orders are not maker orders
            is_maker=False,
            order_type=OrderType.MARKET,
            order_side=TradeType.SELL,
            amount=amount,
            price=avg_price,
            from_total_balances=True
        )

        adjusted_order_candidate = self._budget_checker.populate_collateral_entries(order_candidate)

        # Base currency used, including fees.
        sold_amount = adjusted_order_candidate.order_collateral.amount
        # Quote currency acquired, including fees.
        acquired_amount = adjusted_order_candidate.potential_returns.amount

        # It's not possible to fulfill the order, the possible sold amount is less than requested
        if sold_amount > base_balance:
            self.logger().warning(f"Insufficient {base_asset} balance available for sell order. "
                                  f"{base_balance} {base_asset} available vs. "
                                  f"{amount} {base_asset} required for the order.")
            self.c_trigger_event(
                self.MARKET_ORDER_FAILURE_EVENT_TAG,
                MarketOrderFailureEvent(self._current_timestamp, order_id, OrderType.MARKET)
            )
            return

        # The order was successfully executed
        self.c_set_balance(quote_asset,
                           quote_balance + acquired_amount)
        self.c_set_balance(base_asset,
                           base_balance - sold_amount)

        # add fee
        fees = build_trade_fee(
            exchange=self.name,
            is_maker=False,
            base_currency="",
            quote_currency="",
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("0"),
            price=Decimal("0"),
        )

        order_filled_events = OrderFilledEvent.order_filled_events_from_order_book_rows(
            self._current_timestamp, order_id, trading_pair_str, TradeType.SELL,
            OrderType.MARKET, fees, sell_entries
        )

        for order_filled_event in order_filled_events:
            self.c_trigger_event(self.ORDER_FILLED_EVENT_TAG, order_filled_event)

        self.c_trigger_event(
            self.SELL_ORDER_COMPLETED_EVENT_TAG,
            SellOrderCompletedEvent(self._current_timestamp,
                                    order_id,
                                    base_asset,
                                    quote_asset,
                                    sold_amount,
                                    acquired_amount,
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
                        self.c_execute_buy(front_order.order_id, front_order.trading_pair, front_order.amount)
                    else:
                        self.c_execute_sell(front_order.order_id, front_order.trading_pair, front_order.amount)
                except Exception as e:
                    self.logger().error("Error executing queued order.", exc_info=True)
            else:
                return

    cdef c_delete_limit_order(self,
                              LimitOrders *limit_orders_map_ptr,
                              LimitOrdersIterator *map_it_ptr,
                              const SingleTradingPairLimitOrdersIterator orders_it):
        cdef:
            SingleTradingPairLimitOrders *orders_collection_ptr = address(deref(deref(map_it_ptr)).second)
        try:
            orders_collection_ptr.erase(orders_it)
            if orders_collection_ptr.empty():
                map_it_ptr[0] = limit_orders_map_ptr.erase(deref(map_it_ptr))
            return True
        except Exception as err:
            self.logger().error("Error deleting limit order.", exc_info=True)
            return False

    cdef c_process_limit_bid_order(self,
                                   LimitOrders *limit_orders_map_ptr,
                                   LimitOrdersIterator *map_it_ptr,
                                   SingleTradingPairLimitOrdersIterator orders_it):
        cdef:
            const CPPLimitOrder *cpp_limit_order_ptr = address(deref(orders_it))
            str trading_pair_str = cpp_limit_order_ptr.getTradingPair().decode("utf8")
            str quote_asset = cpp_limit_order_ptr.getQuoteCurrency().decode("utf8")
            str base_asset = cpp_limit_order_ptr.getBaseCurrency().decode("utf8")
            str order_id = cpp_limit_order_ptr.getClientOrderID().decode("utf8")
            object amount = <object> cpp_limit_order_ptr.getQuantity()
            object price = <object> cpp_limit_order_ptr.getPrice()
            object quote_balance = self.c_get_balance(quote_asset)
            object base_balance = self.c_get_balance(base_asset)

        order_candidate = OrderCandidate(
            trading_pair=trading_pair_str,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=amount,
            price=price,
            from_total_balances=True
        )

        adjusted_order_candidate = self._budget_checker.populate_collateral_entries(order_candidate)

        # Quote currency used, including fees.
        paid_amount = adjusted_order_candidate.order_collateral.amount
        # Base currency acquired, including fees.
        acquired_amount = adjusted_order_candidate.potential_returns.amount

        # It's not possible to fulfill the order, the possible acquired amount is less than requested
        if paid_amount > quote_balance:
            self.logger().warning(f"Not enough {quote_asset} balance to fill limit buy order on {trading_pair_str}. "
                                  f"{paid_amount:.8g} {quote_asset} needed vs. "
                                  f"{quote_balance:.8g} {quote_asset} available.")

            self.c_delete_limit_order(limit_orders_map_ptr, map_it_ptr, orders_it)
            self.c_trigger_event(self.MARKET_ORDER_CANCELED_EVENT_TAG,
                                 OrderCancelledEvent(self._current_timestamp,
                                                     order_id)
                                 )
            return

        # The order was successfully executed
        self.c_set_balance(quote_asset,
                           quote_balance - paid_amount)
        self.c_set_balance(base_asset,
                           base_balance + acquired_amount)

        # add fee
        fees = build_trade_fee(
            exchange=self.name,
            is_maker=True,
            base_currency="",
            quote_currency="",
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("0"),
            price=Decimal("0"),
        )

        # Emit the trade and order completed events.
        self.c_trigger_event(
            self.ORDER_FILLED_EVENT_TAG,
            OrderFilledEvent(
                self._current_timestamp,
                order_id,
                trading_pair_str,
                TradeType.BUY,
                OrderType.LIMIT,
                <object> cpp_limit_order_ptr.getPrice(),
                <object> cpp_limit_order_ptr.getQuantity(),
                fees,
                exchange_trade_id=str(int(self._time() * 1e6))
            ))

        self.c_trigger_event(
            self.BUY_ORDER_COMPLETED_EVENT_TAG,
            BuyOrderCompletedEvent(
                self._current_timestamp,
                order_id,
                base_asset,
                quote_asset,
                acquired_amount,
                paid_amount,
                OrderType.LIMIT
            ))
        self.c_delete_limit_order(limit_orders_map_ptr, map_it_ptr, orders_it)

    cdef c_process_limit_ask_order(self,
                                   LimitOrders *limit_orders_map_ptr,
                                   LimitOrdersIterator *map_it_ptr,
                                   SingleTradingPairLimitOrdersIterator orders_it):
        cdef:
            const CPPLimitOrder *cpp_limit_order_ptr = address(deref(orders_it))
            str trading_pair_str = cpp_limit_order_ptr.getTradingPair().decode("utf8")
            str quote_asset = cpp_limit_order_ptr.getQuoteCurrency().decode("utf8")
            str base_asset = cpp_limit_order_ptr.getBaseCurrency().decode("utf8")
            str order_id = cpp_limit_order_ptr.getClientOrderID().decode("utf8")
            object amount = <object> cpp_limit_order_ptr.getQuantity()
            object price = <object> cpp_limit_order_ptr.getPrice()
            object quote_balance = self.c_get_balance(quote_asset)
            object base_balance = self.c_get_balance(base_asset)

        order_candidate = OrderCandidate(
            trading_pair=trading_pair_str,
            # Market orders are not maker orders
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=amount,
            price=price,
            from_total_balances=True
        )

        adjusted_order_candidate = self._budget_checker.populate_collateral_entries(order_candidate)

        # Base currency used, including fees.
        sold_amount = adjusted_order_candidate.order_collateral.amount
        # Quote currency acquired, including fees.
        acquired_amount = adjusted_order_candidate.potential_returns.amount

        # It's not possible to fulfill the order, the possible sold amount is less than requested
        if sold_amount > base_balance:
            self.logger().warning(f"Not enough {base_asset} balance to fill limit sell order on {trading_pair_str}. "
                                  f"{sold_amount:.8g} {base_asset} needed vs. "
                                  f"{base_balance:.8g} {base_asset} available.")
            self.c_delete_limit_order(limit_orders_map_ptr, map_it_ptr, orders_it)
            self.c_trigger_event(self.MARKET_ORDER_CANCELED_EVENT_TAG,
                                 OrderCancelledEvent(self._current_timestamp,
                                                     order_id)
                                 )
            return

        # The order was successfully executed
        self.c_set_balance(quote_asset,
                           quote_balance + acquired_amount)
        self.c_set_balance(base_asset,
                           base_balance - sold_amount)

        # add fee
        fees = build_trade_fee(
            exchange=self.name,
            is_maker=True,
            base_currency="",
            quote_currency="",
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=Decimal("0"),
            price=Decimal("0"),
        )

        # Emit the trade and order completed events.
        self.c_trigger_event(
            self.ORDER_FILLED_EVENT_TAG,
            OrderFilledEvent(
                self._current_timestamp,
                order_id,
                trading_pair_str,
                TradeType.SELL,
                OrderType.LIMIT,
                <object> cpp_limit_order_ptr.getPrice(),
                <object> cpp_limit_order_ptr.getQuantity(),
                fees,
                exchange_trade_id=str(int(self._time() * 1e6))
            ))

        self.c_trigger_event(
            self.SELL_ORDER_COMPLETED_EVENT_TAG,
            SellOrderCompletedEvent(
                self._current_timestamp,
                order_id,
                base_asset,
                quote_asset,
                sold_amount,
                acquired_amount,
                OrderType.LIMIT
            ))
        self.c_delete_limit_order(limit_orders_map_ptr, map_it_ptr, orders_it)

    cdef c_process_limit_order(self,
                               bint is_buy,
                               LimitOrders *limit_orders_map_ptr,
                               LimitOrdersIterator *map_it_ptr,
                               SingleTradingPairLimitOrdersIterator orders_it):
        try:
            if is_buy:
                self.c_process_limit_bid_order(limit_orders_map_ptr, map_it_ptr, orders_it)
            else:
                self.c_process_limit_ask_order(limit_orders_map_ptr, map_it_ptr, orders_it)
        except Exception as e:
            self.logger().error(f"Error processing limit order.", exc_info=True)

    cdef c_process_crossed_limit_orders_for_trading_pair(self,
                                                         bint is_buy,
                                                         LimitOrders *limit_orders_map_ptr,
                                                         LimitOrdersIterator *map_it_ptr):
        """
        Trigger limit orders when the opposite side of the order book has crossed the limit order's price.
        This implies someone was ready to fill the limit order, if that limit order was on the market.

        :param is_buy: are the limit orders on the bid side?
        :param limit_orders_map_ptr: pointer to the limit orders map
        :param map_it_ptr: limit orders map iterator, which implies the trading pair being processed
        """
        cdef:
            str trading_pair = deref(deref(map_it_ptr)).first.decode("utf8")
            object opposite_order_book_price = self.c_get_price(trading_pair, is_buy)
            SingleTradingPairLimitOrders *orders_collection_ptr = address(deref(deref(map_it_ptr)).second)
            SingleTradingPairLimitOrdersIterator orders_it = orders_collection_ptr.begin()
            SingleTradingPairLimitOrdersRIterator orders_rit = orders_collection_ptr.rbegin()
            vector[SingleTradingPairLimitOrdersIterator] process_order_its
            const CPPLimitOrder *cpp_limit_order_ptr = NULL

        if is_buy:
            while orders_rit != orders_collection_ptr.rend():
                cpp_limit_order_ptr = address(deref(orders_rit))
                if opposite_order_book_price > <object>cpp_limit_order_ptr.getPrice():
                    break
                process_order_its.push_back(getIteratorFromReverseIterator(
                    <reverse_iterator[SingleTradingPairLimitOrdersIterator]>orders_rit))
                inc(orders_rit)
        else:
            while orders_it != orders_collection_ptr.end():
                cpp_limit_order_ptr = address(deref(orders_it))
                if opposite_order_book_price < <object>cpp_limit_order_ptr.getPrice():
                    break
                process_order_its.push_back(orders_it)
                inc(orders_it)

        for orders_it in process_order_its:
            self.c_process_limit_order(is_buy, limit_orders_map_ptr, map_it_ptr, orders_it)

    cdef c_process_crossed_limit_orders(self):
        cdef:
            LimitOrders *limit_orders_ptr = address(self._bid_limit_orders)
            LimitOrdersIterator map_it = limit_orders_ptr.begin()

        while map_it != limit_orders_ptr.end():
            self.c_process_crossed_limit_orders_for_trading_pair(True, limit_orders_ptr, address(map_it))
            if map_it != limit_orders_ptr.end():
                inc(map_it)

        limit_orders_ptr = address(self._ask_limit_orders)
        map_it = limit_orders_ptr.begin()

        while map_it != limit_orders_ptr.end():
            self.c_process_crossed_limit_orders_for_trading_pair(False, limit_orders_ptr, address(map_it))
            if map_it != limit_orders_ptr.end():
                inc(map_it)

    # <editor-fold desc="Event listener functions">
    cdef c_match_trade_to_limit_orders(self, object order_book_trade_event):
        """
        Trigger limit orders when incoming market orders have crossed the limit order's price.

        :param order_book_trade_event: trade event from order book
        """
        cdef:
            string cpp_trading_pair = order_book_trade_event.trading_pair.encode("utf8")
            bint is_maker_buy = order_book_trade_event.type is TradeType.SELL
            object trade_price = order_book_trade_event.price
            object trade_quantity = order_book_trade_event.amount
            LimitOrders *limit_orders_map_ptr = (address(self._bid_limit_orders)
                                                 if is_maker_buy
                                                 else address(self._ask_limit_orders))
            LimitOrdersIterator map_it = limit_orders_map_ptr.find(cpp_trading_pair)
            SingleTradingPairLimitOrders *orders_collection_ptr = NULL
            SingleTradingPairLimitOrdersIterator orders_it
            SingleTradingPairLimitOrdersRIterator orders_rit
            vector[SingleTradingPairLimitOrdersIterator] process_order_its
            const CPPLimitOrder *cpp_limit_order_ptr = NULL

        if map_it == limit_orders_map_ptr.end():
            return

        orders_collection_ptr = address(deref(map_it).second)
        if is_maker_buy:
            orders_rit = orders_collection_ptr.rbegin()
            while orders_rit != orders_collection_ptr.rend():
                cpp_limit_order_ptr = address(deref(orders_rit))
                if <object>cpp_limit_order_ptr.getPrice() <= trade_price:
                    break
                process_order_its.push_back(getIteratorFromReverseIterator(
                    <reverse_iterator[SingleTradingPairLimitOrdersIterator]>orders_rit))
                inc(orders_rit)
        else:
            orders_it = orders_collection_ptr.begin()
            while orders_it != orders_collection_ptr.end():
                cpp_limit_order_ptr = address(deref(orders_it))
                if <object>cpp_limit_order_ptr.getPrice() >= trade_price:
                    break
                process_order_its.push_back(orders_it)
                inc(orders_it)

        for orders_it in process_order_its:
            self.c_process_limit_order(is_maker_buy, limit_orders_map_ptr, address(map_it), orders_it)

    # </editor-fold>

    cdef object c_get_available_balance(self, str currency):
        return self.available_balances.get(currency.upper(), s_decimal_0)

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        cdef:
            LimitOrders *limit_orders_map_ptr
            list cancellation_results = []
        limit_orders_map_ptr = address(self._bid_limit_orders)
        for trading_pair_str in self._trading_pairs.keys():
            results = self.c_cancel_order_from_orders_map(limit_orders_map_ptr, trading_pair_str, cancel_all=True)
            cancellation_results.extend(results)

        limit_orders_map_ptr = address(self._ask_limit_orders)
        for trading_pair_str in self._trading_pairs.keys():
            results = self.c_cancel_order_from_orders_map(limit_orders_map_ptr, trading_pair_str, cancel_all=True)
            cancellation_results.extend(results)
        return cancellation_results

    cdef object c_cancel_order_from_orders_map(self,
                                               LimitOrders *orders_map,
                                               str trading_pair_str,
                                               bint cancel_all=False,
                                               str client_order_id=None):
        cdef:
            string cpp_trading_pair = trading_pair_str.encode("utf8")
            LimitOrdersIterator map_it = orders_map.find(cpp_trading_pair)
            SingleTradingPairLimitOrders *limit_orders_collection_ptr = NULL
            SingleTradingPairLimitOrdersIterator orders_it
            vector[SingleTradingPairLimitOrdersIterator] process_order_its
            const CPPLimitOrder *limit_order_ptr = NULL
            str limit_order_cid
            list cancellation_results = []
        try:
            if map_it == orders_map.end():
                return []

            limit_orders_collection_ptr = address(deref(map_it).second)
            orders_it = limit_orders_collection_ptr.begin()
            while orders_it != limit_orders_collection_ptr.end():
                limit_order_ptr = address(deref(orders_it))
                limit_order_cid = limit_order_ptr.getClientOrderID().decode("utf8")
                if (not cancel_all and limit_order_cid == client_order_id) or cancel_all:
                    process_order_its.push_back(orders_it)
                inc(orders_it)

            for orders_it in process_order_its:
                limit_order_ptr = address(deref(orders_it))
                limit_order_cid = limit_order_ptr.getClientOrderID().decode("utf8")
                delete_success = self.c_delete_limit_order(orders_map, address(map_it), orders_it)
                cancellation_results.append(CancellationResult(limit_order_cid,
                                                               delete_success))
                self.c_trigger_event(self.MARKET_ORDER_CANCELED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp,
                                                         limit_order_cid)
                                     )
            return cancellation_results
        except Exception as err:
            self.logger().error(f"Error canceling order.", exc_info=True)

    cdef c_cancel(self, str trading_pair_str, str client_order_id):
        cdef:
            string cpp_trading_pair = trading_pair_str.encode("utf8")
            string cpp_client_order_id = client_order_id.encode("utf8")
            str trade_type = client_order_id.split("://")[0]
            bint is_maker_buy = trade_type.upper() == "BUY"
            LimitOrders *limit_orders_map_ptr = (address(self._bid_limit_orders)
                                                 if is_maker_buy
                                                 else address(self._ask_limit_orders))
        self.c_cancel_order_from_orders_map(limit_orders_map_ptr, trading_pair_str, False, client_order_id)

    cdef object c_get_fee(self,
                          str base_asset,
                          str quote_asset,
                          object order_type,
                          object order_side,
                          object amount,
                          object price,
                          object is_maker = None):
        return build_trade_fee(
            self.name,
            is_maker=is_maker if is_maker is not None else order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER],
            base_currency=base_asset,
            quote_currency=quote_asset,
            order_type=order_type,
            order_side=order_side,
            amount=amount,
            price=price,
        )

    cdef OrderBook c_get_order_book(self, str trading_pair):
        if trading_pair not in self._trading_pairs:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        trading_pair = self._target_market.convert_to_exchange_trading_pair(trading_pair)
        return self._order_book_tracker.order_books[trading_pair]

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        cdef:
            QuantizationParams q_params
        if trading_pair in self._quantization_params:
            q_params = self._quantization_params[trading_pair]
            decimals_quantum = Decimal(f"1e-{q_params.price_decimals}")
            if price.is_finite() and price > s_decimal_0:
                precision_quantum = Decimal(f"1e{math.ceil(math.log10(price)) - q_params.price_precision}")
            else:
                precision_quantum = Decimal(0)
            return max(precision_quantum, decimals_quantum)
        else:
            return Decimal(f"1e-10")

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        return self.c_get_order_price_quantum(trading_pair, price)

    cdef object c_get_order_size_quantum(self,
                                         str trading_pair,
                                         object order_size):
        cdef:
            QuantizationParams q_params
        if trading_pair in self._quantization_params:
            q_params = self._quantization_params[trading_pair]
            decimals_quantum = Decimal(f"1e-{q_params.order_size_decimals}")
            if order_size.is_finite() and order_size > s_decimal_0:
                precision_quantum = Decimal(f"1e{math.ceil(math.log10(order_size)) - q_params.order_size_precision}")
            else:
                precision_quantum = Decimal(0)
            return max(precision_quantum, decimals_quantum)
        else:
            return Decimal(f"1e-7")

    cdef object c_quantize_order_price(self,
                                       str trading_pair,
                                       object price):
        price = Decimal('%.7g' % price)  # hard code to round to 8 significant digits
        price_quantum = self.c_get_order_price_quantum(trading_pair, price)
        return (price // price_quantum) * price_quantum

    cdef object c_quantize_order_amount(self,
                                        str trading_pair,
                                        object amount,
                                        object price=s_decimal_0):
        amount = amount.quantize(Decimal('1e-7'), rounding=ROUND_DOWN)
        if amount <= 1e-7:
            amount = Decimal("0")
        order_size_quantum = self.c_get_order_size_quantum(trading_pair, amount)
        return (amount // order_size_quantum) * order_size_quantum

    def get_available_balance(self, currency: str) -> Decimal:
        return self.c_get_available_balance(currency)

    def get_all_balances(self) -> Dict[str, Decimal]:
        return self._account_balances.copy()

    # <editor-fold desc="Python wrapper for cdef functions">
    def match_trade_to_limit_orders(self, event_object: OrderBookTradeEvent):
        self.c_match_trade_to_limit_orders(event_object)

    def set_balance(self, currency: str, balance: Decimal):
        self.c_set_balance(currency, balance)
    # </editor-fold>

    def get_price(self, trading_pair: str, is_buy: bool) -> Decimal:
        return self.c_get_price(trading_pair, is_buy)

    def buy(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
            price: Decimal = s_decimal_0, **kwargs) -> str:
        return self.c_buy(trading_pair, amount, order_type, price, kwargs)

    def sell(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
             price: Decimal = s_decimal_0, **kwargs) -> str:
        return self.c_sell(trading_pair, amount, order_type, price, kwargs)

    def cancel(self, trading_pair: str, client_order_id: str):
        return self.c_cancel(trading_pair, client_order_id)

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_0,
                is_maker: Optional[bool] = None):
        return self.c_get_fee(base_currency, quote_currency, order_type, order_side, amount, price, is_maker)

    def get_order_book(self, trading_pair: str) -> OrderBook:
        return self.c_get_order_book(trading_pair)

    def get_maker_order_type(self):
        return OrderType.LIMIT

    def get_taker_order_type(self):
        return OrderType.LIMIT

    async def trigger_event_async(self,
                                  event_tag,
                                  event):
        await asyncio.sleep(0.01)
        self.c_trigger_event(event_tag, event)
