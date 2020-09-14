from hummingbot.core.event.event_reporter cimport EventReporter
from hummingbot.core.event.event_logger cimport EventLogger
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.network_iterator cimport NetworkIterator
from hummingbot.core.data_type.order_book_query_result cimport(
    OrderBookQueryResult,
    ClientOrderBookQueryResult
)

cdef class MarketBase(NetworkIterator):
    cdef:
        EventReporter _event_reporter
        EventLogger _event_logger
        dict _account_available_balances
        dict _account_balances
        dict _asset_limit
        bint _real_time_balance_update
        bint _trading_required
        object _order_book_tracker
        dict _in_flight_orders_snapshot
        double _in_flight_orders_snapshot_timestamp

    cdef str c_buy(self, str trading_pair, object amount, object order_type=*, object price=*, dict kwargs=*)
    cdef str c_sell(self, str trading_pair, object amount, object order_type=*, object price=*, dict kwargs=*)
    cdef c_cancel(self, str trading_pair, str client_order_id)
    cdef c_stop_tracking_order(self, str order_id)
    cdef object c_get_balance(self, str currency)
    cdef object c_get_available_balance(self, str currency)
    cdef str c_withdraw(self, str address, str currency, object amount)
    cdef OrderBook c_get_order_book(self, str trading_pair)
    cdef object c_get_price(self, str trading_pair, bint is_buy)
    cdef object c_get_order_price_quantum(self, str trading_pair, object price)
    cdef object c_get_order_size_quantum(self, str trading_pair, object order_size)
    cdef object c_quantize_order_price(self, str trading_pair, object price)
    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=*)
    cdef ClientOrderBookQueryResult c_get_quote_volume_for_base_amount(self, str trading_pair, bint is_buy, object base_amount)
    cdef ClientOrderBookQueryResult c_get_volume_for_price(self, str trading_pair, bint is_buy, object price)
    cdef ClientOrderBookQueryResult c_get_quote_volume_for_price(self, str trading_pair, bint is_buy, object price)
    cdef ClientOrderBookQueryResult c_get_vwap_for_volume(self, str trading_pair, bint is_buy, object volume)
    cdef ClientOrderBookQueryResult c_get_price_for_volume(self, str trading_pair, bint is_buy, object volume)
    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price)
