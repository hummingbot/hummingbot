from wings.event_reporter cimport EventReporter
from wings.event_logger cimport EventLogger
from wings.order_book cimport OrderBook
from wings.network_iterator cimport NetworkIterator
from wings.wallet.wallet_base cimport WalletBase


cdef class MarketBase(NetworkIterator):
    cdef:
        EventReporter event_reporter
        EventLogger event_logger
    cdef str c_buy(self, str symbol, double amount, object order_type=*, double price=*, dict kwargs=*)
    cdef str c_sell(self, str symbol, double amount, object order_type=*, double price=*, dict kwargs=*)
    cdef c_cancel(self, str symbol, str client_order_id)
    cdef double c_get_balance(self, str currency) except? -1
    cdef str c_withdraw(self, str address, str currency, double amount)
    cdef str c_deposit(self, WalletBase from_wallet, str currency, double amount)
    cdef OrderBook c_get_order_book(self, str symbol)
    cdef double c_get_price(self, str symbol, bint is_buy) except? -1
    cdef object c_get_order_price_quantum(self, str symbol, double price)
    cdef object c_get_order_size_quantum(self, str symbol, double order_size)
    cdef object c_quantize_order_price(self, str symbol, double price)
    cdef object c_quantize_order_amount(self, str symbol, double amount)
    cdef object c_get_fee(self,
                          str symbol,
                          object order_type,
                          object order_side,
                          double amount,
                          double price)
