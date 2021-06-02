from hummingbot.connector.exchange_base cimport ExchangeBase

cdef class ExchangePyBase(ExchangeBase):

    cdef object c_quantize_order_price(self, str trading_pair, object price)
    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=*)
