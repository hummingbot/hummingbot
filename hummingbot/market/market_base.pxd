from hummingbot.core.event.event_reporter cimport EventReporter
from hummingbot.core.event.event_logger cimport EventLogger
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.network_iterator cimport NetworkIterator


cdef class MarketBase(NetworkIterator):
    cdef:
        EventReporter event_reporter
        EventLogger event_logger
        dict _account_available_balances
        dict _account_balances
        bint _trading_required
        object _order_book_tracker

    cdef str c_buy(self, str symbol, object amount, object order_type=*, object price=*, dict kwargs=*)
    cdef str c_sell(self, str symbol, object amount, object order_type=*, object price=*, dict kwargs=*)
    cdef c_cancel(self, str symbol, str client_order_id)
    cdef object c_get_balance(self, str currency)
    cdef object c_get_available_balance(self, str currency)
    cdef str c_withdraw(self, str address, str currency, double amount)
    cdef OrderBook c_get_order_book(self, str symbol)
    cdef object c_get_price(self, str symbol, bint is_buy)
    cdef object c_get_order_price_quantum(self, str symbol, object price)
    cdef object c_get_order_size_quantum(self, str symbol, object order_size)
    cdef object c_quantize_order_price(self, str symbol, object price)
    cdef object c_quantize_order_amount(self, str symbol, object amount, object price=*)
    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price)
