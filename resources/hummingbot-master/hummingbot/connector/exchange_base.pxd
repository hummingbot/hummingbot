from hummingbot.core.event.event_reporter cimport EventReporter
from hummingbot.core.event.event_logger cimport EventLogger
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.connector.connector_base cimport ConnectorBase
from hummingbot.core.data_type.order_book_query_result cimport(
    ClientOrderBookQueryResult,
    OrderBookQueryResult,
)

cdef class ExchangeBase(ConnectorBase):
    cdef:
        object _order_book_tracker
        object _budget_checker
        object _trading_pair_symbol_map
        object _mapping_initialization_lock

    cdef str c_buy(self, str trading_pair, object amount, object order_type= *, object price= *, dict kwargs= *)
    cdef str c_sell(self, str trading_pair, object amount, object order_type= *, object price= *, dict kwargs= *)
    cdef c_cancel(self, str trading_pair, str client_order_id)
    cdef c_stop_tracking_order(self, str order_id)
    cdef OrderBook c_get_order_book(self, str trading_pair)
    cdef object c_get_price(self, str trading_pair, bint is_buy)
    cdef ClientOrderBookQueryResult c_get_quote_volume_for_base_amount(
        self,
        str trading_pair,
        bint is_buy,
        object base_amount)
    cdef ClientOrderBookQueryResult c_get_volume_for_price(self, str trading_pair, bint is_buy, object price)
    cdef ClientOrderBookQueryResult c_get_quote_volume_for_price(self, str trading_pair, bint is_buy, object price)
    cdef ClientOrderBookQueryResult c_get_vwap_for_volume(self, str trading_pair, bint is_buy, object volume)
    cdef ClientOrderBookQueryResult c_get_price_for_quote_volume(self, str trading_pair, bint is_buy, double volume)
    cdef ClientOrderBookQueryResult c_get_price_for_volume(self, str trading_pair, bint is_buy, object volume)
    cdef object c_get_fee(
        self,
        str base_currency,
        str quote_currency,
        object order_type,
        object order_side,
        object amount,
        object price,
        object is_maker= *)
