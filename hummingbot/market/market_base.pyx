from decimal import Decimal
import pandas as pd
from typing import (
    Dict,
    List,
    Tuple,
    Iterator)

from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.order_book_query_result import (
    OrderBookQueryResult,
    ClientOrderBookQueryResult
)
from hummingbot.core.data_type.order_book_row import (
    ClientOrderBookRow
)
from hummingbot.core.event.events import (
    MarketEvent,
    OrderType,
    TradeType,
    TradeFee
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.network_iterator import NetworkIterator
from hummingbot.core.data_type.order_book import OrderBook

from .deposit_info import DepositInfo

NaN = float("nan")
s_decimal_NaN = Decimal("nan")
s_decimal_0 = Decimal(0)

cdef class MarketBase(NetworkIterator):
    MARKET_EVENTS = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.WithdrawAsset,
        MarketEvent.OrderCancelled,
        MarketEvent.TransactionFailure,
        MarketEvent.OrderFilled,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderExpired
    ]

    def __init__(self):
        super().__init__()
        self.event_reporter = EventReporter(event_source=self.name)
        self.event_logger = EventLogger(event_source=self.name)
        for event_tag in self.MARKET_EVENTS:
            self.c_add_listener(event_tag.value, self.event_reporter)
            self.c_add_listener(event_tag.value, self.event_logger)

        self._account_balances = {}  # Dict[asset_name:str, Decimal]
        self._account_available_balances = {}  # Dict[asset_name:str, Decimal]
        self._order_book_tracker = None

    @staticmethod
    def split_symbol(symbol: str) -> Tuple[str, str]:
        try:
            return tuple(symbol.split('-'))
        except Exception:
            raise ValueError(f"Error parsing symbol {symbol}")

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {}

    @property
    def display_name(self) -> str:
        return self.name

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def event_logs(self) -> List[any]:
        return self.event_logger.event_log

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        raise NotImplementedError

    @property
    def ready(self) -> bool:
        raise NotImplementedError

    @property
    def limit_orders(self) -> List[LimitOrder]:
        raise NotImplementedError

    @property
    def tracking_states(self) -> Dict[str, any]:
        return {}

    def get_mid_price(self, symbol: str) -> Decimal:
        return (self.get_price(symbol, True) + self.get_price(symbol, False)) / Decimal("2")

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        """
        Restores the tracking states from a previously saved state.

        :param saved_states: Previously saved tracking states from `tracking_states` property.
        """
        pass

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        """
        :return: data frame with symbol as index, and at least the following columns --
                 ["baseAsset", "quoteAsset", "volume", "USDVolume"]
        """
        raise NotImplementedError

    async def get_deposit_info(self, asset: str) -> DepositInfo:
        raise NotImplementedError

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        raise NotImplementedError

    cdef str c_buy(self, str symbol, object amount, object order_type=OrderType.MARKET,
                   object price=s_decimal_NaN, dict kwargs={}):
        raise NotImplementedError

    cdef str c_sell(self, str symbol, object amount, object order_type=OrderType.MARKET,
                    object price=s_decimal_NaN, dict kwargs={}):
        raise NotImplementedError

    cdef c_cancel(self, str symbol, str client_order_id):
        raise NotImplementedError

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price):
        raise NotImplementedError

    def get_all_balances(self) -> Dict[str, Decimal]:
        """
        *required
        :return: Dict[asset_name: asst_balance]: Balances of all assets being traded
        """
        return self._account_balances.copy()

    cdef object c_get_balance(self, str currency):
        """
        :returns: Total balance for a specific asset
        """
        return self._account_balances.get(currency, s_decimal_0)

    cdef object c_get_available_balance(self, str currency):
        """
        :returns: Balance available for trading for a specific asset
        (balances used to place open orders are not available for trading)
        """
        return self._account_available_balances.get(currency, s_decimal_0)

    cdef str c_withdraw(self, str address, str currency, object amount):
        raise NotImplementedError

    cdef OrderBook c_get_order_book(self, str symbol):
        raise NotImplementedError

    cdef object c_get_order_price_quantum(self, str symbol, object price):
        raise NotImplementedError

    cdef object c_get_order_size_quantum(self, str symbol, object order_size):
        raise NotImplementedError

    cdef object c_quantize_order_price(self, str symbol, object price):
        if price == s_decimal_NaN:
            return price
        price_quantum = self.c_get_order_price_quantum(symbol, price)
        return round(price / price_quantum) * price_quantum

    cdef object c_quantize_order_amount(self, str symbol, object amount, object price=s_decimal_NaN):
        order_size_quantum = self.c_get_order_size_quantum(symbol, amount)
        return (amount // order_size_quantum) * order_size_quantum

    # ----------------------------------------------------------------------------------------------------------
    # </editor-fold>

    # <editor-fold desc="+ Decimal interface to OrderBook">
    # ----------------------------------------------------------------------------------------------------------
    cdef object c_get_price(self, str symbol, bint is_buy):
        """
        :returns: Top bid/ask price for a specific trading pair
        """
        cdef:
            OrderBook order_book = self.c_get_order_book(symbol)
            object top_price
        try:
            top_price = Decimal(order_book.c_get_price(is_buy))
        except EnvironmentError as e:
            self.logger().warning(f"{'Ask' if is_buy else 'Buy'} orderbook for {symbol} is empty.")
            return s_decimal_NaN

        return self.c_quantize_order_price(symbol, top_price)

    cdef ClientOrderBookQueryResult c_get_vwap_for_volume(self, str symbol, bint is_buy, object volume):
        cdef:
            OrderBook order_book = self.c_get_order_book(symbol)
            OrderBookQueryResult result = order_book.c_get_vwap_for_volume(is_buy, float(volume))
            object query_volume = self.c_quantize_order_amount(symbol, Decimal(result.query_volume))
            object result_price = self.c_quantize_order_price(symbol, Decimal(result.result_price))
            object result_volume = self.c_quantize_order_amount(symbol, Decimal(result.result_volume))
        return ClientOrderBookQueryResult(s_decimal_NaN,
                                          query_volume,
                                          result_price,
                                          result_volume)

    cdef ClientOrderBookQueryResult c_get_price_for_volume(self, str symbol, bint is_buy, object volume):
        cdef:
            OrderBook order_book = self.c_get_order_book(symbol)
            OrderBookQueryResult result = order_book.c_get_price_for_volume(is_buy, float(volume))
            object query_volume = self.c_quantize_order_amount(symbol, Decimal(result.query_volume))
            object result_price = self.c_quantize_order_price(symbol, Decimal(result.result_price))
            object result_volume = self.c_quantize_order_amount(symbol, Decimal(result.result_volume))
        return ClientOrderBookQueryResult(s_decimal_NaN,
                                          query_volume,
                                          result_price,
                                          result_volume)

    cdef ClientOrderBookQueryResult c_get_quote_volume_for_base_amount(self, str symbol, bint is_buy, object base_amount):
        cdef:
            OrderBook order_book = self.c_get_order_book(symbol)
            OrderBookQueryResult result = order_book.c_get_quote_volume_for_base_amount(is_buy, float(base_amount))
            object query_volume = self.c_quantize_order_amount(symbol, Decimal(result.query_volume))
            object result_volume = self.c_quantize_order_amount(symbol, Decimal(result.result_volume))
        return ClientOrderBookQueryResult(s_decimal_NaN,
                                          query_volume,
                                          s_decimal_NaN,
                                          result_volume)

    cdef ClientOrderBookQueryResult c_get_volume_for_price(self, str symbol, bint is_buy, object price):
        cdef:
            OrderBook order_book = self.c_get_order_book(symbol)
            OrderBookQueryResult result = order_book.c_get_volume_for_price(is_buy, float(price))
            object query_price = self.c_quantize_order_price(symbol, Decimal(result.query_price))
            object result_price = self.c_quantize_order_price(symbol, Decimal(result.result_price))
            object result_volume = self.c_quantize_order_amount(symbol, Decimal(result.result_volume))
        return ClientOrderBookQueryResult(query_price,
                                          s_decimal_NaN,
                                          result_price,
                                          result_volume)

    cdef ClientOrderBookQueryResult c_get_quote_volume_for_price(self, str symbol, bint is_buy, object price):
        cdef:
            OrderBook order_book = self.c_get_order_book(symbol)
            OrderBookQueryResult result = order_book.c_get_volume_for_price(is_buy, float(price))
            object query_price = self.c_quantize_order_price(symbol, Decimal(result.query_price))
            object result_price = self.c_quantize_order_price(symbol, Decimal(result.result_price))
            object result_volume = self.c_quantize_order_amount(symbol, Decimal(result.result_volume))
        return ClientOrderBookQueryResult(query_price,
                                          s_decimal_NaN,
                                          result_price,
                                          result_volume)

    def order_book_bid_entries(self, symbol) -> Iterator[ClientOrderBookRow]:
        cdef:
            OrderBook order_book = self.c_get_order_book(symbol)
        for entry in order_book.bid_entries():
            yield ClientOrderBookRow(self.c_quantize_order_price(symbol, Decimal(entry.price)),
                                     self.c_quantize_order_amount(symbol, Decimal(entry.amount)),
                                     entry.update_id)

    def order_book_ask_entries(self, symbol) -> Iterator[ClientOrderBookRow]:
        cdef:
            OrderBook order_book = self.c_get_order_book(symbol)
        for entry in order_book.ask_entries():
            yield ClientOrderBookRow(self.c_quantize_order_price(symbol, Decimal(entry.price)),
                                     self.c_quantize_order_amount(symbol, Decimal(entry.amount)),
                                     entry.update_id)
    # ----------------------------------------------------------------------------------------------------------
    # </editor-fold>

    # <editor-fold desc="+ Wrapper for cython functions">
    # ----------------------------------------------------------------------------------------------------------
    def get_vwap_for_volume(self, symbol: str, is_buy: bool, volume: Decimal):
        return self.c_get_vwap_for_volume(symbol, is_buy, volume)

    def get_price_for_volume(self, symbol: str, is_buy: bool, volume: Decimal):
        return self.c_get_price_for_volume(symbol, is_buy, volume)

    def get_quote_volume_for_base_amount(self, symbol: str, is_buy: bool,
                                         base_amount: Decimal) -> ClientOrderBookQueryResult:
        return self.c_get_quote_volume_for_base_amount(symbol, is_buy, base_amount)

    def get_volume_for_price(self, symbol: str, is_buy: bool, price: Decimal) -> ClientOrderBookQueryResult:
        return self.c_get_volume_for_price(symbol, is_buy, price)

    def get_quote_volume_for_price(self, symbol: str, is_buy: bool, price: Decimal) -> ClientOrderBookQueryResult:
        return self.c_get_quote_volume_for_price(symbol, is_buy, price)

    def get_balance(self, currency: str) -> Decimal:
        return self.c_get_balance(currency)

    def get_price(self, symbol: str, is_buy: bool) -> Decimal:
        return self.c_get_price(symbol, is_buy)

    def buy(self, symbol: str, amount: Decimal, order_type=OrderType.MARKET,
            price: Decimal = s_decimal_NaN, **kwargs) -> str:
        return self.c_buy(symbol, amount, order_type, price, kwargs)

    def sell(self, symbol: str, amount: Decimal, order_type=OrderType.MARKET,
             price: Decimal = s_decimal_NaN, **kwargs) -> str:
        return self.c_sell(symbol, amount, order_type, price, kwargs)

    def cancel(self, symbol: str, client_order_id: str):
        return self.c_cancel(symbol, client_order_id)

    def get_available_balance(self, currency: str) -> Decimal:
        return self.c_get_available_balance(currency)

    def withdraw(self, address: str, currency: str, amount: Decimal) -> str:
        return self.c_withdraw(address, currency, amount)

    def get_order_book(self, symbol: str) -> OrderBook:
        return self.c_get_order_book(symbol)

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = NaN) -> TradeFee:
        return self.c_get_fee(base_currency, quote_currency, order_type, order_side, amount, price)

    def get_order_price_quantum(self, symbol: str, price: Decimal) -> Decimal:
        return self.c_get_order_price_quantum(symbol, price)

    def get_order_size_quantum(self, symbol: str, order_size: Decimal) -> Decimal:
        return self.c_get_order_size_quantum(symbol, order_size)

    def quantize_order_price(self, symbol: str, price: Decimal) -> Decimal:
        return self.c_quantize_order_price(symbol, price)

    def quantize_order_amount(self, symbol: str, amount: Decimal) -> Decimal:
        return self.c_quantize_order_amount(symbol, amount)

    # ----------------------------------------------------------------------------------------------------------
    # </editor-fold>
