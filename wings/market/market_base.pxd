from wings.event_reporter cimport EventReporter
from wings.order_book cimport OrderBook
from wings.time_iterator cimport TimeIterator
from wings.wallet.wallet_base cimport WalletBase


cdef class MarketBase(TimeIterator):
    cdef:
        EventReporter event_reporter
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
    cdef list c_calculate_fees(self,
                               str symbol,
                               double amount,
                               double price,
                               object order_type,
                               object order_side)
