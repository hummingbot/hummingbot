
from collections import deque
from cpython cimport PyObject
from cython.operator cimport (
    postincrement as inc,
    dereference as deref,
    address
)
from libcpp cimport bool as cppbool
import logging
import pandas as pd
import random
from typing import (
    Dict,
    List
)

from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.limit_order cimport c_create_limit_order_from_cpp_limit_order
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.event.events import MarketEvent, OrderType
from hummingbot.core.event.event_listener cimport EventListener
from hummingbot.market.deposit_info import DepositInfo
from hummingbot.market.market_base import MarketBase
from hummingbot.core.data_type.cancellation_result import CancellationResult
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

    def __repr__(self) -> str:
        return (f"QueuedOrder({self.create_timestamp}, '{self.order_id}', {self.is_buy}, '{self.symbol}', "
                f"{self.amount})")


cdef class PaperTradeMarket(MarketBase):
    MARKET_RECEIVED_ASSET_EVENT_TAG = MarketEvent.ReceivedAsset.value
    MARKET_BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted.value
    MARKET_SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted.value
    MARKET_WITHDRAW_ASSET_EVENT_TAG = MarketEvent.WithdrawAsset.value
    MARKET_ORDER_CANCELLED_EVENT_TAG = MarketEvent.OrderCancelled.value
    MARKET_TRANSACTION_FAILURE_EVENT_TAG = MarketEvent.TransactionFailure.value
    MARKET_ORDER_FAILURE_EVENT_TAG = MarketEvent.OrderFailure.value
    MARKET_ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled.value
    MARKET_BUY_ORDER_CREATED_EVENT_TAG = MarketEvent.BuyOrderCreated.value
    MARKET_SELL_ORDER_CREATED_EVENT_TAG = MarketEvent.SellOrderCreated.value

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

    def __init__(self, order_book_tracker):
        super(MarketBase, self).__init__()

        self._symbol_pairs = {}
        self._account_balance = {}
        self._order_book_tracker = order_book_tracker
        self._config = MarketConfig.default_config()
        self._queued_orders = deque()
        self._quantization_params = {}

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def ready(self):
        return len(self._order_book_tracker.order_books) > 0

    def add_symbol_pair(self, *symbol_pairs):
        for symbol_pair in symbol_pairs:
            self._symbol_pairs[symbol_pair.symbol]= symbol_pair

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

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        pass

    def get_all_balances(self) -> Dict[str, float]:
        pass

    async def get_deposit_info(self, asset: str) -> DepositInfo:
        pass

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        pass

    cdef str c_sell(self, str symbol, double amount, object order_type = OrderType.MARKET, double price = 0.0,
                    dict kwargs = {}):
        pass

    cdef c_cancel(self, str symbol, str client_order_id):
        pass

    cdef object c_get_fee(self, str base_currency, str quote_currency, object order_type, object order_side,
                          double amount, double price):
        pass

    cdef double c_get_balance(self, str currency) except? -1:
        pass

    cdef double c_get_available_balance(self, str currency) except? -1:
        pass

    cdef str c_withdraw(self, str address, str currency, double amount):
        pass

    cdef OrderBook c_get_order_book(self, str symbol):
        pass

    cdef double c_get_price(self, str symbol, bint is_buy) except? -1:
        pass

    cdef object c_get_order_price_quantum(self, str symbol, double price):
        pass

    cdef object c_get_order_size_quantum(self, str symbol, double order_size):
        pass


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
